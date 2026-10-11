# OpenUI V7 — SvelteKit + FastAPI + Multi-Provider

OpenUI V7 là bản nâng cấp hoàn chỉnh từ V6, thêm quản lý nhiều model (providers), bộ nhớ người dùng, và tính năng cá nhân hóa.

## Tính năng chính

- **Chat**: Streaming, upload ảnh (≤8 MB), lịch sử cuộc trò chuyện
- **Nhiều Provider (Mới V7)**: Quản lý nhiều API OpenAI-compatible (Groq, OpenRouter, OpenAI, Ollama qua gateway, Colab, v.v.)
  - Lưu Base URL, Model ID chính xác
  - Mã hóa API key trên disk (Fernet, key tồn tại qua container restart)
  - Chỉ định model mặc định, bật/tắt từng provider
  - Test kết nối API từ UI
- **Skills**: Quản lý SKILL.md, bật/tắt, được đưa vào system prompt
- **MCP Servers**: Kết nối server MCP từ xa (streamable_http / SSE), khám phá tools, gọi tool khi chat
- **Cá nhân hóa**: Tên hiển thị, hướng dẫn tùy chỉnh (custom instructions), phong cách trả lời (ngắn gọn / chi tiết)
- **Bộ nhớ**: Ghi nhớ ghi chú người dùng, bật/tắt, đưa vào context khi chat
- **Database**: SQLite (`data/chat.db`) lưu chats, messages, attachments, skills, mcp_servers, providers, preferences, memories

## Deploy (VPS)

```bash
# 1. Backup
cp -a /root/openui /root/openui-backup-$(date +%Y%m%d)

# 2. Cập nhật code
cd /root/openui
git pull origin main

# 3. Build & chạy
docker compose up -d --build

# 4. Kiểm tra
curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://127.0.0.1:3003/
curl -s -o /dev/null -w "Backend: %{http_code}\n" http://127.0.0.1:3004/api/me
docker compose logs --tail=50
```

## Kiến trúc

| Service | Port | Mô tả |
|---------|------|-------|
| Frontend (SvelteKit) | 3003 | UI chat, settings, providers, skills, mcp, memory |
| Backend (FastAPI) | 3004 | API REST + SSE streaming, MCP client, provider registry |

## Bảo mật

- **Không expose port 3004** ra internet công khai
- Chỉ thêm MCP server HTTPS từ nguồn tin cậy
- API key provider được mã hóa (Fernet) trong `data/providers.key` — backup file này khi chuyển VPS
- `.env` chứa `OPENUI_PASSWORD` (bắt buộc), `OPENAI_BASE_URL` (fallback legacy)

## Backup / Restore

```bash
# Backup dữ liệu
cp -a /root/openui/data /root/backup-data-$(date +%Y%m%d)
cp /root/openui/.env /root/backup-env-$(date +%Y%m%d)
cp /root/openui/data/providers.key /root/backup-providers-key-$(date +%Y%m%d)

# Restore
cp /root/backup-data-YYYYMMDD/chat.db /root/openui/data/chat.db
cp /root/backup-env-YYYYMMDD /root/openui/.env
cp /root/backup-providers-key-YYYYMMDD /root/openui/data/providers.key
docker compose up -d --build
```

## Kiểm thử nhanh

```bash
# 1. Đăng nhập
curl -c /tmp/c.txt -X POST http://127.0.0.1:3004/api/login -H "Content-Type: application/json" -d '{"password":"YOUR_PASSWORD"}'

# 2. Thêm provider
curl -b /tmp/c.txt -X POST http://127.0.0.1:3004/api/providers -H "Content-Type: application/json" -d '{
  "name":"Groq — Llama 3.3",
  "base_url":"https://api.groq.com/openai/v1",
  "model_id":"llama-3.3-70b-versatile",
  "api_key":"gsk_xxx",
  "enabled":true,
  "is_default":true
}'

# 3. Lấy danh sách models
curl -b /tmp/c.txt http://127.0.0.1:3004/api/models

# 4. Chat streaming
curl -b /tmp/c.txt -X POST http://127.0.0.1:3004/api/chats/<cid>/stream -H "Content-Type: application/json" -d '{"content":"Xin chào"}'
```

## Yêu cầu hệ thống

- Docker + Docker Compose
- VPS có RAM ≥ 1 GB (build frontend cần ~500 MB)
- Domain + Cloudflare Tunnel (khuyên dùng) để HTTPS

## Phiên bản

- **V7**: Multi-provider, memory, personalization, updated UI
- **V6**: Settings API, ChatGPT-style UI, MCP tools
- **V5**: SvelteKit rewrite
- **V4**: SvelteKit + FastAPI migration
