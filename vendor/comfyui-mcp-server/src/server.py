"""
MCP Server Setup / MCP 服务器设置

Builds the MCP application object, registers all tool schemas, and routes
incoming tool calls to the appropriate handler functions in `handlers/tool_handlers.py`.

构建 MCP 应用对象，注册所有工具的 Schema，
并将传入的工具调用路由到 `handlers/tool_handlers.py` 中对应的处理函数。

Note: We use the low-level `mcp.server.Server` instead of `FastMCP` because
our tools have fully dynamic JSON Schemas generated at runtime (parameterised
by user-configurable tool name overrides and i18n descriptions). FastMCP
requires static Pydantic models for input validation which does not fit this
design.
注意：这里使用底层 `mcp.server.Server` 而非 `FastMCP`，
因为我们的工具具有完全动态的运行时 JSON Schema（通过可配置的工具名称覆盖和 i18n 描述参数化）。
FastMCP 需要静态 Pydantic 模型做输入校验，不适合这个设计。
"""

import json
import asyncio
import mcp.types as types
from mcp.server import Server
from .logger import logger
from .config import settings
from .client.ws_client import ComfyUIWebSocketClient
from .dependencies import container
from .services.workflow_scanner import WorkflowScanner

async def initialize_server():
    """Bootstrap all application services before accepting tool calls.
    在接受工具调用前启动所有应用服务。

    Call order / 调用顺序:
      1. `container.initialize()`         — instantiate all shared services / 实例化所有共享服务
      2. `rebuild_catalog()`              — build the initial workflow index / 构建初始工作流目录
      3. `WorkflowScanner.start()`        — run first scan + start background loop / 首次扫描 + 启动后台循环
    """
    logger.info("Initializing ComfyUI MCP Server...")
    # Lazily import and instantiate all shared services (avoids circular imports at module level).
    # 延迟导入并实例化所有共享服务（避免模块级循环导入）。
    container.initialize()

    # Rebuild the catalog immediately so `get_workflows_catalog` works from the very first call.
    # 立即重建目录，确保 `get_workflows_catalog` 工具从首次调用起就可用。
    await container.catalog_service.rebuild_catalog()

    # Create the dedicated WebSocket client for the workflow scanner.
    # 为工作流扫描器建立专用 WebSocket 客户端。
    logger.info("Starting background WorkflowScanner...")
    ws_client = ComfyUIWebSocketClient(client_id="mcp_workflow_scanner")
    await ws_client.connect()

    scanner = WorkflowScanner(ws_client)
    # Register on container so tool handlers can trigger on-demand refreshes via `container.scanner`.
    # 注册到容器，使工具处理器可通过 `container.scanner` 触发按需刷新。
    container.scanner = scanner
    # FUSION PATCH #1 (PartMe.AI): run the first scan as a BACKGROUND task.
    # Upstream `await scanner.start()` blocks stdio initialization until every
    # saved workflow has been scanned/converted (~7s each on a ComfyUI with a
    # large third-party workflow library, e.g. 65 workflows ≈ 7+ minutes), which
    # exceeds every MCP host's startup timeout and makes the server look hung.
    # The catalog starts empty and is rebuilt by the background scan;
    # `_trigger_ondemand_refresh()` on tool calls keeps it fresh afterwards.
    scan_task = asyncio.create_task(scanner.start())

    def _log_scan_failure(task: "asyncio.Task[None]") -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error(f"Background workflow scan failed: {task.exception()}")

    scan_task.add_done_callback(_log_scan_failure)


# MCP application instance. Named "comfy-ui-advanced" to identify this server to MCP hosts.
# MCP 应用实例，命名为 "comfy-ui-advanced" 以便 MCP Host 识别。
app_server = Server("comfy-ui-advanced")

@app_server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return the complete list of tools exposed to the MCP host.
    返回向 MCP Host 公开的工具列表。

    Tool names come from `settings.TOOL_*` (overrideable via env) and descriptions
    are resolved through the i18n service so they reflect the active locale.
    工具名称来自 `settings.TOOL_*`（可通过环境变量覆盖），
    描述通过 i18n 服务解析以反映当前语言。
    """
    tools = [
        types.Tool(
            name=settings.TOOL_GET_WORKFLOWS_CATALOG,
            description=container.i18n.t("tool.get_workflows_catalog.description"),
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name=settings.TOOL_GET_PROMPT_RESULT,
            description=container.i18n.t("tool.get_prompt_result.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "string", "description": container.i18n.t("tool.get_prompt_result.param.prompt_id")}
                },
                "required": ["prompt_id"]
            }
        ),
        types.Tool(
            name=settings.TOOL_GET_WORKFLOW_API,
            description=container.i18n.t("tool.get_workflow_API.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": container.i18n.t("tool.get_workflow_API.param.workflow_name")}
                },
                "required": ["workflow_name"]
            }
        ),
        types.Tool(
            name=settings.TOOL_MOUNT_WORKFLOW,
            description=container.i18n.t("tool.mount_workflow.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": container.i18n.t("tool.mount_workflow.param.workflow_name")}
                },
                "required": ["workflow_name"]
            }
        ),
        types.Tool(
            name=settings.TOOL_QUEUE_PROMPT,
            description=container.i18n.t("tool.queue_prompt.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": container.i18n.t("tool.queue_prompt.param.workflow_name")},
                    "parameters": {"type": "object", "description": container.i18n.t("tool.queue_prompt.param.parameters")},
                    "is_async": {"type": "string", "description": container.i18n.t("tool.queue_prompt.param.is_async")}
                },
                "required": ["workflow_name", "parameters"]
            }
        ),
        types.Tool(
            name=settings.TOOL_QUEUE_CUSTOM_PROMPT,
            description=container.i18n.t("tool.queue_custom_prompt.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": container.i18n.t("tool.queue_custom_prompt.param.workflow_name")},
                    "api_json": {
                        "type": ["string", "object"], 
                        "description": container.i18n.t("tool.queue_custom_prompt.param.api_json")
                    },
                    "is_async": {"type": "string", "description": container.i18n.t("tool.queue_custom_prompt.param.is_async")}
                },
                "required": ["workflow_name", "api_json"]
            }
        ),
        types.Tool(
            name=settings.TOOL_SAVE_CUSTOM_WORKFLOW,
            description=container.i18n.t("tool.save_custom_workflow.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": container.i18n.t("tool.save_custom_workflow.param.filename")},
                    "api_json": {
                        "type": ["string", "object"], 
                        "description": container.i18n.t("tool.save_custom_workflow.param.api_json")
                    }
                },
                "required": ["filename", "api_json"]
            }
        ),
        types.Tool(
            name=settings.TOOL_SAVE_TASK_ASSETS,
            description=container.i18n.t("tool.save_task_assets.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "string", "description": container.i18n.t("tool.save_task_assets.param.prompt_id")},
                    "destination_dir": {"type": "string", "description": container.i18n.t("tool.save_task_assets.param.destination_dir")},
                    "overwrite": {"type": "boolean", "description": container.i18n.t("tool.save_task_assets.param.overwrite"), "default": False}
                },
                "required": ["prompt_id"]
            }
        ),
        types.Tool(
            name=settings.TOOL_UPLOAD_ASSETS,
            description=container.i18n.t("tool.upload_assets.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "fileSource": {"type": "string", "description": container.i18n.t("tool.upload_assets.param.fileSource")},
                    "mimeType": {"type": "string", "description": container.i18n.t("tool.upload_assets.param.mimeType")}
                },
                "required": ["fileSource"]
            }
        ),
        types.Tool(
            name=settings.TOOL_INTERRUPT_PROMPT,
            description=container.i18n.t("tool.interrupt_prompt.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_id": {"type": "string", "description": container.i18n.t("tool.interrupt_prompt.param.prompt_id")}
                },
                "required": ["prompt_id"]
            }
        ),

        types.Tool(
            name=settings.TOOL_GET_SYSTEM_STATUS,
            description=container.i18n.t("tool.get_system_status.description"),
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name=settings.TOOL_LIST_MODELS,
            description=container.i18n.t("tool.list_models.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "type_name": {
                        "type": "string", 
                        "description": container.i18n.t("tool.list_models.param.type_name"),
                        "default": "checkpoints"
                    }
                }
            }
        ),
        types.Tool(
            name=settings.TOOL_GET_CORE_MANUAL,
            description=container.i18n.t("tool.get_core_manual.description"),
            inputSchema={"type": "object", "properties": {}}
        ),
        # FUSION PATCH #3 (PartMe.AI): API-surface completion tools.
        types.Tool(
            name=settings.TOOL_FREE_MEMORY,
            description=container.i18n.t("tool.free_memory.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "unload_models": {"type": "boolean", "description": container.i18n.t("tool.free_memory.param.unload_models")},
                    "free_memory": {"type": "boolean", "description": container.i18n.t("tool.free_memory.param.free_memory")}
                }
            }
        ),
        types.Tool(
            name=settings.TOOL_LIST_EMBEDDINGS,
            description=container.i18n.t("tool.list_embeddings.description"),
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name=settings.TOOL_LIST_LOCAL_TEMPLATES,
            description=container.i18n.t("tool.list_local_templates.description"),
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name=settings.TOOL_UPLOAD_MASK,
            description=container.i18n.t("tool.upload_mask.description"),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": container.i18n.t("tool.upload_mask.param.file_path")},
                    "original_ref": {"type": "string", "description": container.i18n.t("tool.upload_mask.param.original_ref")}
                },
                "required": ["file_path"]
            }
        )
    ]
    
    return tools

@app_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Route an incoming tool call to the appropriate handler function.
    将传入的工具调用路由到对应的处理函数。

    Handler functions are imported lazily to keep startup time fast and
    avoid issues with circular imports at module level.
    处理函数采用延迟导入，保持启动速度并避免模块级循环导入问题。
    """
    logger.info(f"Tool called: {name}")
    try:
        from .handlers import tool_handlers
        if name == settings.TOOL_GET_CORE_MANUAL:
            return await tool_handlers.handle_get_core_manual(arguments, app_server)
        elif name == settings.TOOL_GET_WORKFLOWS_CATALOG:
            return await tool_handlers.handle_get_workflows_catalog(arguments, app_server)
        elif name == settings.TOOL_GET_PROMPT_RESULT:
            return await tool_handlers.handle_get_prompt_result(arguments, app_server)
        elif name == settings.TOOL_GET_WORKFLOW_API:
            return await tool_handlers.handle_get_workflow_API(arguments, app_server)
        elif name == settings.TOOL_MOUNT_WORKFLOW:
            return await tool_handlers.handle_mount_workflow(arguments, app_server)
        elif name == settings.TOOL_QUEUE_PROMPT:
            return await tool_handlers.handle_queue_prompt(arguments, app_server)
        elif name == settings.TOOL_QUEUE_CUSTOM_PROMPT:
            return await tool_handlers.handle_queue_custom_prompt(arguments, app_server)
        elif name == settings.TOOL_SAVE_CUSTOM_WORKFLOW:
            return await tool_handlers.handle_save_custom_workflow(arguments, app_server)
        elif name == settings.TOOL_SAVE_TASK_ASSETS:
            return await tool_handlers.handle_save_task_assets(arguments, app_server)
        elif name == settings.TOOL_UPLOAD_ASSETS:
            return await tool_handlers.handle_upload_assets(arguments, app_server)
        elif name == settings.TOOL_INTERRUPT_PROMPT:
            return await tool_handlers.handle_interrupt_prompt(arguments, app_server)

        elif name == settings.TOOL_GET_SYSTEM_STATUS:
            return await tool_handlers.handle_get_system_status(arguments, app_server)
        elif name == settings.TOOL_LIST_MODELS:
            return await tool_handlers.handle_list_models(arguments, app_server)
        elif name == settings.TOOL_FREE_MEMORY:
            return await tool_handlers.handle_free_memory(arguments, app_server)
        elif name == settings.TOOL_LIST_EMBEDDINGS:
            return await tool_handlers.handle_list_embeddings(arguments, app_server)
        elif name == settings.TOOL_LIST_LOCAL_TEMPLATES:
            return await tool_handlers.handle_list_local_templates(arguments, app_server)
        elif name == settings.TOOL_UPLOAD_MASK:
            return await tool_handlers.handle_upload_mask(arguments, app_server)
        else:
            return [types.TextContent(type="text", text=f"Unknown Tool: {name}")]
    except Exception as e:
        logger.error(f"Error handling tool '{name}': {e}")
        return [types.TextContent(type="text", text=f"Error executing tool '{name}': {e}")]


# Alias for backward-compatibility: `__main__.py` imports `app` by this name.
# 向后兼容别名：`__main__.py` 通过此名称导入 `app`。
app = app_server
