import os, sqlite3, uuid, json, hmac, secrets, hashlib, time, base64
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
from extensions import router as extensions_router, tool_definitions, execute_tool, enabled_skill_text
from settings_api import router as settings_router, memory_context

app = FastAPI(docs_url=None, redoc_url=None)
DB = os.getenv('OPENUI_DB', '/data/chat.db')
PASSWORD = os.getenv('OPENUI_PASSWORD', '')
SECRET_PATH = Path(DB).with_suffix('.secret')
Path(DB).parent.mkdir(parents=True, exist_ok=True)
if not PASSWORD: raise RuntimeError('OPENUI_PASSWORD required')
if not SECRET_PATH.exists():
    SECRET_PATH.write_text(secrets.token_hex(32)); SECRET_PATH.chmod(0o600)
SECRET = SECRET_PATH.read_text().strip().encode()

def db():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.execute('CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created INTEGER NOT NULL)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id,created)')
    c.execute('CREATE TABLE IF NOT EXISTS attachments (id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, message_id TEXT, filename TEXT NOT NULL, mime TEXT NOT NULL, content BLOB NOT NULL, created INTEGER NOT NULL)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_attachments_chat ON attachments(chat_id)')

if Path('static').is_dir():
    app.mount('/static', StaticFiles(directory='static'), name='static')
app.include_router(extensions_router)
app.include_router(settings_router)

def token():
    ts = str(int(time.time()))
    sig = hmac.new(SECRET, ts.encode(), hashlib.sha256).hexdigest()
    return ts + '.' + sig

def authorized(request):
    t = request.cookies.get('openui_session', '')
    try:
        ts, sig = t.split('.', 1)
        if abs(time.time()-int(ts)) > 86400*14: return False
        expected = hmac.new(SECRET, ts.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception: return False

def require(request):
    if not authorized(request): raise HTTPException(401, 'Login required')

@app.get('/')
async def index(): return {'service':'OpenUI API','ok':True}

@app.get('/api/me')
async def me(request:Request): return {'authenticated':authorized(request)}

@app.post('/api/login')
async def login(request:Request):
    payload = await request.json()
    if not hmac.compare_digest(str(payload.get('password','')), PASSWORD):
        raise HTTPException(401,'Wrong password')
    r=JSONResponse({'ok':True})
    r.set_cookie('openui_session',token(),httponly=True,samesite='lax',secure=request.url.scheme=='https',max_age=86400*14)
    return r

@app.post('/api/logout')
async def logout(request:Request):
    require(request)
    r=JSONResponse({'ok':True});r.delete_cookie('openui_session');return r

@app.get('/api/chats')
async def chats(request:Request):
    require(request)
    with db() as c: return [dict(x) for x in c.execute('SELECT * FROM chats ORDER BY updated DESC LIMIT 200')]

@app.post('/api/chats')
async def create(request:Request):
    require(request)
    uid=str(uuid.uuid4());now=int(time.time())
    with db() as c: c.execute('INSERT INTO chats VALUES (?,?,?,?)',(uid,'Cuộc trò chuyện mới',now,now))
    return {'id':uid,'title':'Cuộc trò chuyện mới'}

@app.get('/api/chats/{cid}')
async def get_chat(cid:str,request:Request):
    require(request)
    with db() as c:
        chat=c.execute('SELECT * FROM chats WHERE id=?',(cid,)).fetchone()
        if not chat: raise HTTPException(404)
        messages=[dict(x) for x in c.execute('SELECT id,role,content,created FROM messages WHERE chat_id=? ORDER BY created,rowid',(cid,))]
        for msg in messages:
            msg['attachments']=[{'id':a['id'],'filename':a['filename'],'mime':a['mime']} for a in c.execute('SELECT id,filename,mime FROM attachments WHERE message_id=?',(msg['id'],))]
        return {'chat':dict(chat),'messages':messages}

@app.delete('/api/chats/{cid}')
async def delete_chat(cid:str,request:Request):
    require(request)
    with db() as c:
        c.execute('DELETE FROM attachments WHERE chat_id=?',(cid,))
        c.execute('DELETE FROM messages WHERE chat_id=?',(cid,))
        c.execute('DELETE FROM chats WHERE id=?',(cid,))
    return {'ok':True}

@app.post('/api/chats/{cid}/attachments')
async def upload_attachment(cid:str, request:Request, file:UploadFile=File(...)):
    require(request)
    mime=(file.content_type or '').lower()
    allowed={'image/jpeg','image/png','image/webp','image/gif'}
    if mime not in allowed: raise HTTPException(415,'Chỉ hỗ trợ JPG, PNG, WebP, GIF')
    data=await file.read(8*1024*1024+1)
    if not data or len(data)>8*1024*1024: raise HTTPException(413,'Ảnh tối đa 8 MB')
    signatures={'image/jpeg':data.startswith(b'\xff\xd8\xff'), 'image/png':data.startswith(b'\x89PNG\r\n\x1a\n'), 'image/webp':data.startswith(b'RIFF') and data[8:12]==b'WEBP', 'image/gif':data.startswith((b'GIF87a',b'GIF89a'))}
    if not signatures[mime]: raise HTTPException(415,'Định dạng ảnh không hợp lệ')
    with db() as c:
        if not c.execute('SELECT 1 FROM chats WHERE id=?',(cid,)).fetchone(): raise HTTPException(404)
        aid=str(uuid.uuid4())
        c.execute('INSERT INTO attachments VALUES (?,?,?,?,?,?,?)',(aid,cid,None,(file.filename or 'image')[:150],mime,data,int(time.time())))
    return {'id':aid,'filename':(file.filename or 'image')[:150],'mime':mime}

@app.get('/api/attachments/{aid}')
async def get_attachment(aid:str,request:Request):
    require(request)
    with db() as c: a=c.execute('SELECT mime,content FROM attachments WHERE id=?',(aid,)).fetchone()
    if not a: raise HTTPException(404)
    from fastapi.responses import Response
    return Response(a['content'],media_type=a['mime'],headers={'Cache-Control':'private, max-age=300','X-Content-Type-Options':'nosniff'})

@app.delete('/api/attachments/{aid}')
async def delete_attachment(aid:str,request:Request):
    require(request)
    with db() as c: c.execute('DELETE FROM attachments WHERE id=? AND message_id IS NULL',(aid,))
    return {'ok':True}

@app.get('/api/models')
async def models(request:Request):
    require(request)
    base=os.getenv('OPENAI_BASE_URL','').rstrip('/')
    fallback=os.getenv('OPENAI_MODEL','qwen35-abliterated')
    headers={'Authorization':'Bearer '+os.getenv('OPENAI_API_KEY','')}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r=await client.get(base+'/models',headers=headers)
            r.raise_for_status()
            names=[x['id'] for x in r.json().get('data',[]) if x.get('id')]
            return {'models':names or [fallback],'online':True}
    except Exception: return {'models':[fallback],'online':False}

@app.post('/api/chats/{cid}/stream')
async def stream(cid:str,request:Request):
    require(request)
    data=await request.json()
    content=str(data.get('content','')).strip()
    ids=data.get('attachment_ids',[])
    if not isinstance(ids,list) or len(ids)>4 or any(not isinstance(i,str) for i in ids): raise HTTPException(400,'Tối đa 4 ảnh')
    if (not content and not ids) or len(content)>30000: raise HTTPException(400,'Invalid message')
    model=str(data.get('model') or os.getenv('OPENAI_MODEL','qwen35-abliterated'))
    with db() as c:
        chat=c.execute('SELECT id,title FROM chats WHERE id=?',(cid,)).fetchone()
        if not chat: raise HTTPException(404)
        now=int(time.time())
        mid=str(uuid.uuid4())
        attachments=[]
        for aid in ids:
            a=c.execute('SELECT id,mime,content FROM attachments WHERE id=? AND chat_id=? AND message_id IS NULL',(aid,cid)).fetchone()
            if not a: raise HTTPException(400,'Ảnh đính kèm không hợp lệ')
            attachments.append(a)
        c.execute('INSERT INTO messages VALUES (?,?,?,?,?)',(mid,cid,'user',content,now))
        for a in attachments: c.execute('UPDATE attachments SET message_id=? WHERE id=?',(mid,a['id']))
        if chat['title']=='Cuộc trò chuyện mới':
            c.execute('UPDATE chats SET title=? WHERE id=?',(content[:55],cid))
        c.execute('UPDATE chats SET updated=? WHERE id=?',(now,cid))
        history=[]
        for msg in c.execute('SELECT id,role,content FROM messages WHERE chat_id=? ORDER BY created,rowid',(cid,)):
            parts=[{'type':'text','text':msg['content']}] if msg['content'] else []
            for a in c.execute('SELECT mime,content FROM attachments WHERE message_id=?',(msg['id'],)):
                uri='data:'+a['mime']+';base64,'+base64.b64encode(a['content']).decode()
                parts.append({'type':'image_url','image_url':{'url':uri}})
            history.append({'role':msg['role'],'content':parts if len(parts)>1 or (parts and parts[0]['type']=='image_url') else msg['content']})

    async def generator():
        full=''
        def event(obj): return 'data: '+json.dumps(obj,ensure_ascii=False)+'\n\n'
        try:
            base=os.getenv('OPENAI_BASE_URL','http://127.0.0.1:18000/v1').rstrip('/')
            headers={'Authorization':'Bearer '+os.getenv('OPENAI_API_KEY','')}
            skills=enabled_skill_text()
            if skills: history.insert(0, {'role':'system','content':skills})
            user_context=memory_context()
            if user_context: history.insert(0, {'role':'system','content':user_context})
            async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=10)) as client:
                # MCP tools require a model supporting OpenAI tool calling.
                defs=await tool_definitions()
                for round_no in range(5):
                    payload={'model':model,'messages':history,'stream':False}
                    if defs: payload.update({'tools':defs,'tool_choice':'auto'})
                    if not defs: break
                    r=await client.post(base+'/chat/completions',headers=headers,json=payload)
                    if r.status_code!=200:
                        yield event({'error':f'API HTTP {r.status_code}: {r.text[:300]}'})
                        return
                    msg=r.json()['choices'][0]['message']
                    calls=msg.get('tool_calls') or []
                    if not calls:
                        # Tool round finished; stream a final answer below.
                        break
                    history.append({'role':'assistant','content':msg.get('content'),'tool_calls':calls})
                    for call in calls:
                        fn=call.get('function') or {}
                        try:
                            args=json.loads(fn.get('arguments') or '{}')
                            result=await execute_tool(fn.get('name',''),args)
                            yield event({'tool':fn.get('name',''),'status':'completed'})
                        except Exception as exc:
                            result={'error':str(exc)[:300]}
                            yield event({'tool':fn.get('name',''),'status':'error'})
                        history.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)[:16000]})
                async with client.stream('POST',base+'/chat/completions',headers=headers,json={'model':model,'messages':history,'stream':True}) as response:
                    if response.status_code!=200:
                        raw=(await response.aread()).decode(errors='replace')[:400]
                        yield event({'error':f'API HTTP {response.status_code}: {raw}'})
                        return
                    async for line in response.aiter_lines():
                        if not line.startswith('data: '): continue
                        raw=line[6:]
                        if raw=='[DONE]': break
                        try:
                            chunk=json.loads(raw)
                            delta=chunk.get('choices',[{}])[0].get('delta',{}).get('content','')
                            if isinstance(delta,str) and delta:
                                full+=delta
                                yield event({'delta':delta})
                        except (ValueError,IndexError,TypeError): continue
            if full:
                with db() as c:
                    c.execute('INSERT INTO messages VALUES (?,?,?,?,?)',(str(uuid.uuid4()),cid,'assistant',full,int(time.time())))
            yield event({'done':True})
        except Exception as e:
            yield event({'error':'Không kết nối được API model. Kiểm tra Colab và SSH tunnel.'})
    return StreamingResponse(generator(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
