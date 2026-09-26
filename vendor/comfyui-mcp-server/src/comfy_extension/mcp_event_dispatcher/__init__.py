# MCP Event Dispatcher - ComfyUI Custom Node
# Auto-deployed by MCP Server. Do not edit manually.
# Version: 1.0.0

import urllib.parse

try:
    import server
    from aiohttp.web import middleware

    _MCP_EXTENSION_VERSION = "1.0.0"

    @middleware
    async def _mcp_userdata_middleware(request, handler):
        response = await handler(request)
        # Only intercept successful POST/PUT writes to the workflows directory
        if response.status == 200 and request.method in ("POST", "PUT"):
            if request.path.startswith("/api/userdata/workflows/"):
                encoded_fname = request.path[len("/api/userdata/workflows/"):]
                fname = urllib.parse.unquote(encoded_fname)
                try:
                    server.PromptServer.instance.send_sync(
                        "mcp_workflow_saved",
                        {"file": fname, "version": _MCP_EXTENSION_VERSION}
                    )
                except Exception:
                    pass
        return response

    server.PromptServer.instance.app.middlewares.append(_mcp_userdata_middleware)

except Exception as _e:
    print(f"[MCP Event Dispatcher] Failed to register middleware: {_e}")

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = ""
