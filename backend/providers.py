"""Multi-provider OpenAI-compatible model registry.

Provider credentials are encrypted on disk using a persistent Fernet key stored
beside the existing SQLite database. Neither GET API responses nor logs expose
API keys. No network connections occur when listing configured models.
"""
import ipaddress
import os
import socket
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix='/api')
DB = os.getenv('OPENUI_DB', '/data/chat.db')
KEY_FILE = Path(DB).with_name('providers.key')
Path(DB).parent.mkdir(parents=True, exist_ok=True)
if not KEY_FILE.exists():
    # A key must survive container re-creation; Docker bind-mounts /data.
    try:
        with KEY_FILE.open('xb') as f:
            f.write(Fernet.generate_key())
        KEY_FILE.chmod(0o600)
    except FileExistsError:
        pass
cipher = Fernet(KEY_FILE.read_bytes().strip())


def connect():
    conn = sqlite3.connect(DB, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


with connect() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS ai_providers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        base_url TEXT NOT NULL,
        model_id TEXT NOT NULL,
        api_key_cipher TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        is_default INTEGER NOT NULL DEFAULT 0,
        created INTEGER NOT NULL,
        updated INTEGER NOT NULL
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_ai_providers_default ON ai_providers(is_default, enabled)')


def require(request: Request):
    from main import require as auth
    auth(request)


def validate_url(value: str):
    """Only public HTTPS or loopback HTTP. Avoid sending keys to private LAN hosts."""
    value = value.strip().rstrip('/')
    if len(value) > 500:
        raise HTTPException(400, 'API URL quá dài')
    try:
        u = urlsplit(value)
        port = u.port
    except ValueError:
        raise HTTPException(400, 'API URL không hợp lệ')
    if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password or u.fragment or u.query:
        raise HTTPException(400, 'API URL phải là địa chỉ HTTP(S) không chứa username, password, query hoặc fragment')
    if port is not None and not (1 <= port <= 65535):
        raise HTTPException(400, 'Cổng API không hợp lệ')
    host = u.hostname.lower().rstrip('.')
    loopback = host == 'localhost'
    try:
        loopback = loopback or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if u.scheme == 'http' and not loopback:
        raise HTTPException(400, 'API từ xa phải dùng HTTPS; chỉ localhost/127.0.0.1 được dùng HTTP')
    if not loopback:
        if host.endswith(('.local', '.internal', '.localhost')):
            raise HTTPException(400, 'Không cho phép API URL trong mạng nội bộ')
        try:
            resolved = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
            if not resolved or any(not ipaddress.ip_address(item[4][0]).is_global for item in resolved):
                raise HTTPException(400, 'API URL phải trỏ tới địa chỉ IP công khai')
        except socket.gaierror:
            # Saving offline configuration is permitted. Connection will be
            # checked (including DNS validation) before each test/use.
            pass
    if u.path.endswith('/chat/completions'):
        raise HTTPException(400, 'Hãy nhập Base URL kết thúc bằng /v1, không phải /chat/completions')
    if u.path.endswith('/models'):
        raise HTTPException(400, 'Hãy nhập Base URL, không phải endpoint /models')
    return value


def encrypted(key: str):
    return cipher.encrypt(key.encode()).decode() if key else ''


def decrypted(row):
    if not row['api_key_cipher']:
        return ''
    try:
        return cipher.decrypt(row['api_key_cipher'].encode()).decode()
    except InvalidToken:
        raise HTTPException(500, 'Không giải mã được API key. Kiểm tra data/providers.key')


def public(row):
    return {'id': row['id'], 'name': row['name'], 'base_url': row['base_url'],
            'model_id': row['model_id'], 'has_api_key': bool(row['api_key_cipher']),
            'enabled': bool(row['enabled']), 'is_default': bool(row['is_default']),
            'created': row['created'], 'updated': row['updated']}


def all_providers():
    with connect() as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM ai_providers ORDER BY is_default DESC, created ASC')]


def model_options():
    rows = [r for r in all_providers() if r['enabled']]
    if rows:
        return [{'id': r['id'], 'name': r['name'], 'model_id': r['model_id'],
                 'is_default': bool(r['is_default']), 'source': 'saved'} for r in rows]
    # Legacy .env fallback only before any provider is registered. If providers
    # exist but are disabled, respect that intent: do not silently call Colab.
    if not all_providers():
        mid = os.getenv('OPENAI_MODEL', 'qwen35-abliterated')
        return [{'id': 'legacy', 'name': mid, 'model_id': mid, 'is_default': True, 'source': 'env'}]
    return []


def resolve_model(selected: str | None):
    """Resolve the *selected provider ID* to its model and credentials."""
    rows = all_providers()
    enabled = [r for r in rows if r['enabled']]
    if enabled:
        if selected:
            row = next((r for r in enabled if r['id'] == selected), None)
            if row is None:
                # Compatibility with V6, which posted the raw model ID.
                matches = [r for r in enabled if r['model_id'] == selected]
                if len(matches) == 1:
                    row = matches[0]
            if row is None:
                raise HTTPException(400, 'Mô hình đã chọn không tồn tại hoặc đang tắt')
        else:
            row = next((r for r in enabled if r['is_default']), enabled[0])
        validate_url(row['base_url'])
        return {'name': row['name'], 'model_id': row['model_id'],
                'base_url': row['base_url'], 'api_key': decrypted(row)}
    if rows:
        raise HTTPException(503, 'Chưa có mô hình đang bật. Vào Cài đặt → Mô hình để bật model.')
    legacy_model = os.getenv('OPENAI_MODEL', 'qwen35-abliterated')
    if selected and selected not in ('legacy', legacy_model):
        raise HTTPException(400, 'Mô hình đã chọn không tồn tại')
    return {'name': legacy_model, 'model_id': legacy_model,
            'base_url': validate_url(os.getenv('OPENAI_BASE_URL', 'http://127.0.0.1:18000/v1')),
            'api_key': os.getenv('OPENAI_API_KEY', '')}


@router.get('/providers')
def list_providers(request: Request):
    require(request)
    return {'items': [public(row) for row in all_providers()]}


async def parse_provider(request: Request):
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(400, 'Dữ liệu không hợp lệ')
    name = str(data.get('name') or '').strip()
    model_id = str(data.get('model_id') or '').strip()
    if not (1 <= len(name) <= 100) or not (1 <= len(model_id) <= 180):
        raise HTTPException(400, 'Tên và Model ID phải có từ 1 đến 100/180 ký tự')
    base_url = validate_url(str(data.get('base_url') or ''))
    key = data.get('api_key', '')
    if not isinstance(key, str) or len(key) > 8192:
        raise HTTPException(400, 'API key không hợp lệ')
    if not isinstance(data.get('enabled', True), bool) or not isinstance(data.get('is_default', False), bool):
        raise HTTPException(400, 'Giá trị enabled/is_default phải là boolean')
    return {'name': name, 'model_id': model_id, 'base_url': base_url,
            'api_key': key, 'enabled': int(data.get('enabled', True)),
            'is_default': int(data.get('is_default', False)),
            'clear_api_key': data.get('clear_api_key') is True}


def ensure_default(conn):
    active = conn.execute('SELECT id FROM ai_providers WHERE enabled=1 AND is_default=1 ORDER BY updated DESC').fetchall()
    if active:
        winner = active[0]['id']
        conn.execute('UPDATE ai_providers SET is_default=CASE WHEN id=? THEN 1 ELSE 0 END', (winner,))
        return
    first = conn.execute('SELECT id FROM ai_providers WHERE enabled=1 ORDER BY created,id LIMIT 1').fetchone()
    conn.execute('UPDATE ai_providers SET is_default=CASE WHEN id=? THEN 1 ELSE 0 END', (first['id'] if first else '',))


@router.post('/providers', status_code=201)
async def create_provider(request: Request):
    require(request)
    payload = await parse_provider(request)
    ident, now = str(uuid.uuid4()), int(time.time())
    with connect() as conn:
        if payload['is_default'] and payload['enabled']:
            conn.execute('UPDATE ai_providers SET is_default=0')
        conn.execute('''INSERT INTO ai_providers
            (id,name,base_url,model_id,api_key_cipher,enabled,is_default,created,updated)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (ident, payload['name'], payload['base_url'], payload['model_id'],
             encrypted(payload['api_key']), payload['enabled'],
             payload['is_default'] and payload['enabled'], now, now))
        ensure_default(conn)
        row = conn.execute('SELECT * FROM ai_providers WHERE id=?', (ident,)).fetchone()
    return public(row)


@router.put('/providers/{ident}')
async def update_provider(ident: str, request: Request):
    require(request)
    payload = await parse_provider(request)
    with connect() as conn:
        old = conn.execute('SELECT * FROM ai_providers WHERE id=?', (ident,)).fetchone()
        if not old:
            raise HTTPException(404, 'Không tìm thấy mô hình')
        if payload['is_default'] and payload['enabled']:
            conn.execute('UPDATE ai_providers SET is_default=0')
        if payload['clear_api_key']:
            secret = ''
        elif payload['api_key']:
            secret = encrypted(payload['api_key'])
        else:
            secret = old['api_key_cipher']
        conn.execute('''UPDATE ai_providers SET name=?,base_url=?,model_id=?,api_key_cipher=?,
            enabled=?,is_default=?,updated=? WHERE id=?''',
            (payload['name'], payload['base_url'], payload['model_id'], secret,
             payload['enabled'], payload['is_default'] and payload['enabled'], int(time.time()), ident))
        ensure_default(conn)
        row = conn.execute('SELECT * FROM ai_providers WHERE id=?', (ident,)).fetchone()
    return public(row)


@router.delete('/providers/{ident}')
def delete_provider(ident: str, request: Request):
    require(request)
    with connect() as conn:
        changed = conn.execute('DELETE FROM ai_providers WHERE id=?', (ident,)).rowcount
        if not changed:
            raise HTTPException(404, 'Không tìm thấy mô hình')
        ensure_default(conn)
    return {'ok': True}


@router.post('/providers/{ident}/test')
async def test_provider(ident: str, request: Request):
    require(request)
    with connect() as conn:
        row = conn.execute('SELECT * FROM ai_providers WHERE id=?', (ident,)).fetchone()
    if not row:
        raise HTTPException(404, 'Không tìm thấy mô hình')
    url = validate_url(row['base_url']) + '/models'
    headers = {'Authorization': 'Bearer ' + decrypted(row)} if row['api_key_cipher'] else {}
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = await client.get(url, headers=headers)
        if response.status_code == 200:
            try:
                data = response.json()
                ids = [str(m['id']) for m in data.get('data', []) if isinstance(m, dict) and m.get('id')]
                configured_found = row['model_id'] in ids
            except (ValueError, TypeError, AttributeError):
                ids, configured_found = [], False
            return {'ok': True, 'http_status': 200, 'model_found': configured_found,
                    'model_count': len(ids), 'note': 'API /models phản hồi HTTP 200. Chưa kiểm tra suy luận chat.'}
        return {'ok': False, 'http_status': response.status_code,
                'note': 'API /models không phản hồi thành công. Một số nhà cung cấp không hỗ trợ endpoint này.'}
    except (httpx.HTTPError, OSError) as exc:
        return {'ok': False, 'http_status': None, 'note': 'Không kết nối được: '+str(exc)[:160]}
