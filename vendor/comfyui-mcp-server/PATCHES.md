# Fusion Patches (PartMe.AI)

Upstream: https://github.com/MetaBrain-Labs/ComfyUI-MCP-Server-Python (MIT)
This is a vendored, patched copy. Do NOT `git pull` over it — re-apply patches
after any upstream refresh. Patches are marked `FUSION PATCH` in source.

## Dependency pin (dep-pin)

`requirements-pinned.txt` freezes the full environment including **`mcp==1.9.4`**.
Upstream declares `mcp>=1.2.0` unbounded; MCP SDK 2.x removed the low-level
`Server.list_tools()`/`call_tool()` decorators this server is built on, so any
fresh unpinned install crashes at import (`AttributeError: 'Server' object has
no attribute 'list_tools'`). Always install from `requirements-pinned.txt`,
never from upstream `requirements.txt` (also UTF-16 encoded — pip cannot read it).

## FUSION PATCH #1 — background first scan (`src/server.py`)

Upstream `initialize_server()` awaited `scanner.start()`, which scans/converts
every saved ComfyUI workflow (~7s each) BEFORE the stdio handshake. On a ComfyUI
with a large third-party workflow library (e.g. 65 workflows ≈ 7+ min) every MCP
host startup times out and the server looks hung. The first scan now runs as a
background asyncio task; the catalog fills asynchronously and
`_trigger_ondemand_refresh()` keeps it fresh on tool calls.

## FUSION PATCH #2 — `--transport both` (`src/__main__.py`)

New mode: one process serves stdio AND Streamable HTTP simultaneously (one
initialize, shared scanner/connections). stdio EOF shuts the HTTP server down
gracefully.

## FUSION PATCH #2b — no-redirect `/mcp` endpoint (`src/__main__.py`)

Upstream mounted the path-agnostic session manager with `Mount("/mcp")`, which
307-redirects bare `/mcp` to `/mcp/`. POST clients (urllib, curl, ChatGPT
connectors) do not follow 307 — the HTTP transport was effectively unusable.
Now mounted at `/` so `http://host:port/mcp` matches exactly.

## FUSION PATCH #3 — API-surface completion tools

Four new tools close the practical gaps found by a code-level audit of ComfyUI
0.10 routes (generation loop was already fully covered; these are the useful
non-covered endpoints). Registered in `config.py`/`server.py`, implemented in
`handlers/tool_handlers.py` + `client/http_client.py`, i18n keys added to
`locales/zh-cn.json` / `locales/en.json`:

- `free_memory(unload_models=true, free_memory=true)` — POST /free, OOM recovery
- `list_embeddings()` — GET /embeddings
- `list_local_templates()` — GET /workflow_templates (LOCAL template tree, not the cloud registry)
- `upload_mask(file_path, original_ref?)` — POST /upload/mask (inpainting masks)

Still intentionally NOT covered: /free-style admin ops beyond the above,
user management, /experiment/*, /internal/*, frontend-only endpoints, and
custom-node dynamic routes. Tool count: 13 → 17.

## Operational notes

- `workflow_name` / client ids must be **ASCII only** — non-ASCII breaks the
  ComfyUI WebSocket connection.
- ComfyUI must be RUNNING before the server starts (it connects at startup);
  there is no launch_comfyui equivalent yet (fusion roadmap).
- Target ComfyUI host is configured via `.env` (`COMFY_UI_SERVER_IP` /
  `COMFY_UI_SERVER_HOST` + `COMFY_UI_SERVER_PORT`) — any host on the LAN works.
- Recommended `.env`: `LOCALE=zh-CN`, `SYNC_MODE=manual`.
