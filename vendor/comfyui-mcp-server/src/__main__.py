"""
Entry point for the ComfyUI MCP Server.
启动入口 — 解析命令行参数并以选定的传输协议启动服务。

Usage / 用法:
    python -m src                               # stdio (default / 默认)
    python -m src --transport stdio
    python -m src --transport streamable-http   # Streamable HTTP
    python -m src --transport streamable-http --host 0.0.0.0 --port 8189
    python -m src --transport both              # stdio + Streamable HTTP 同时服务
"""

import sys
import argparse
import asyncio
import contextlib
from mcp.server.stdio import stdio_server
from .server import app, initialize_server
from .logger import logger


async def run_stdio():
    """Run the MCP server over stdio transport.
    以 stdio 协议运行 MCP 服务器。

    NOTE: MCP hosts communicate via stdout/stdin JSON-RPC.
          All application logs are routed to stderr via logger.py.
    注意：MCP Host 通过 stdout/stdin JSON-RPC 通信。
          所有应用日志均通过 logger.py 输出到 stderr，避免干扰协议流。
    """
    logger.info("Initializing application resources before standard IO starts...")
    await initialize_server()

    logger.info("Starting ComfyUI-MCP-Server on stdio...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def _build_http_server(host: str, port: int):
    """Build the uvicorn server for Streamable HTTP (shared by http/both modes).
    构建 Streamable HTTP 的 uvicorn 服务器（http / both 模式共用）。
    """
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    session_manager = StreamableHTTPSessionManager(app=app)

    @contextlib.asynccontextmanager
    async def lifespan(starlette_app):
        """Starlette lifespan: start/stop the session managers."""
        async with session_manager.run():
            logger.info(f"ComfyUI-MCP-Server (Streamable HTTP) listening on http://{host}:{port}/mcp")
            yield

    # FUSION PATCH #2b (PartMe.AI): mount the path-agnostic ASGI handler at the
    # ROOT instead of Mount("/mcp"). Starlette's Mount("/mcp") does NOT match the
    # bare "/mcp" URL and 307-redirects to "/mcp/", which POST clients (urllib,
    # curl, ChatGPT connectors) do not follow — breaking Streamable HTTP clients.
    # Mounted at "/", the documented endpoint http://host:port/mcp matches exactly.
    starlette_app = Starlette(
        routes=[
            Mount("/", app=session_manager.handle_request),
        ],
        lifespan=lifespan,
    )

    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="warning",  # uvicorn logs suppressed; use loguru via logger.py
    )
    return uvicorn.Server(config)


async def run_streamable_http(host: str = "127.0.0.1", port: int = 8189):
    """Run the MCP server over Streamable HTTP transport using Starlette + uvicorn.
    以 Streamable HTTP 协议运行 MCP 服务器（Starlette + uvicorn）。
    """
    try:
        import uvicorn  # noqa: F401
        from starlette.applications import Starlette  # noqa: F401
    except ImportError as e:
        logger.error(
            f"Streamable HTTP transport requires extra dependencies: {e}\n"
            "Install with: pip install uvicorn starlette"
        )
        sys.exit(1)

    logger.info("Initializing application resources before Streamable HTTP starts...")
    await initialize_server()

    server = _build_http_server(host, port)
    await server.serve()


async def run_both(host: str = "127.0.0.1", port: int = 8189):
    """FUSION PATCH #2 (PartMe.AI): serve stdio AND Streamable HTTP from ONE process.

    One initialize_server() (one workflow scan, one ComfyUI connection), then the
    uvicorn server runs as a task on the same event loop while stdio is served in
    the main coroutine. When the stdio host disconnects (stdin EOF), the HTTP
    server shuts down gracefully, and vice versa via process exit.
    单进程同时提供 stdio 与 Streamable HTTP：一次初始化、共享扫描与连接。
    """
    logger.info("Initializing application resources before dual-transport starts...")
    await initialize_server()

    server = _build_http_server(host, port)
    http_task = asyncio.create_task(server.serve())

    logger.info("Starting ComfyUI-MCP-Server on stdio (dual mode)...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(http_task, timeout=10)


def main():
    """CLI entry point. Parses --transport and dispatches to the appropriate runner.
    命令行入口，解析 --transport 参数并分发到对应的运行函数。
    """
    parser = argparse.ArgumentParser(description="ComfyUI MCP Server (Python)")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "both"],
        default="stdio",
        help="Transport protocol to use (default: stdio) / 传输协议（默认：stdio）"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for Streamable HTTP (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8189,
        help="Port to listen on for Streamable HTTP (default: 8189)"
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
    elif args.transport == "streamable-http":
        asyncio.run(run_streamable_http(host=args.host, port=args.port))
    elif args.transport == "both":
        asyncio.run(run_both(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
