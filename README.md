# OpenUI V4 — SvelteKit + FastAPI

Migrates the V3 frontend to SvelteKit/TypeScript while preserving the V3 FastAPI endpoints and SQLite database schema.

## Deploy (VPS)

1. Back up the existing `/root/openui` directory, including `data` and `.env`.
2. Extract this package into `/root/openui-v4`.
3. Copy `/root/openui/.env` and `/root/openui/data` into `/root/openui-v4`.
4. Stop the old container (`docker stop toolnet-openui`) to free port 3003. Do **not** remove volumes or the original directory.
5. Run `docker compose up -d --build` in `/root/openui-v4`.
6. Test `curl -I http://127.0.0.1:3003` and `docker compose logs --tail 50`.
7. Existing Cloudflare tunnel to 127.0.0.1:3003 continues to work.

Frontend on 127.0.0.1:3003, backend on 127.0.0.1:3004. Model remains optional/offline. Skills/MCP API uses original V3 backend and MCP tool execution is disabled by default.

**Security:** Do not expose port 3004 to the public internet. Only configure trusted MCP servers. Review code before deployment; this package has not been tested on your VPS.
