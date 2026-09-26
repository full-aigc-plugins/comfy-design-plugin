"""
Application Configuration / 应用配置

Loads all user-configurable settings from the `.env` file via python-dotenv.
Each setting is exposed as a lazy property on the singleton `settings` object,
so environment variable changes made after import are always reflected.

All available variables and their defaults are documented in `.env.example`.

通过 python-dotenv 从 `.env` 文件加载所有用户可配置设置。
每项设置均以懒属性形式定义在单例 `settings` 对象上，
确保导入后修改的环境变量始终能被反映。

所有可用变量及其默认値说明诳见 `.env.example`。
"""

import os
import re
from dotenv import load_dotenv

# Load from .env file in project root. Existing OS env vars take precedence (override=False).
# 从项目根目录的 .env 文件加载配置。OS 环境变量优先（override=False）。
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=False)


class _Settings:
    """
    Application settings loaded exclusively from the .env file.
    All configurable values live in .env — see .env.example for the full list.
    This class provides typed attribute access with in-code fallbacks for
    programmatic consumers that run without a .env (e.g. CI, unit tests).
    应用设置类，从exclusively .env 文件加载。
    所有可配置项均在 .env 中，详见 .env.example。
    为无 .env 运行的场景（如 CI、单元测试）提供带内置默认値的类型属性访问。
    """

    # -------------------------------------------------------------------------
    # User Configuration / 用户配置
    # -------------------------------------------------------------------------
    @property
    def LOCALE(self) -> str:
        return os.getenv("LOCALE", "en")

    @property
    def COMFY_UI_SERVER_IP(self) -> str:
        return os.getenv("COMFY_UI_SERVER_IP", "http://127.0.0.1:8188")

    @property
    def COMFY_UI_SERVER_HOST(self) -> str:
        return os.getenv("COMFY_UI_SERVER_HOST", "127.0.0.1")

    @property
    def COMFY_UI_SERVER_PORT(self) -> str:
        return os.getenv("COMFY_UI_SERVER_PORT", "8188")

    @property
    def COMFY_UI_INSTALL_PATH(self) -> str:
        return os.getenv("COMFY_UI_INSTALL_PATH", "")

    # Polling interval (seconds) when event-driven (push) mode is NOT active.
    # 非事件驱动（push）模式下的后台轮询间隔（秒）。
    @property
    def SYNC_POLL_INTERVAL_SECONDS(self) -> int:
        return int(os.getenv("SYNC_POLL_INTERVAL_SECONDS", "3"))

    # Fallback polling interval (seconds) when event-driven (push) mode IS active.
    # Used as a safety net in case push events are lost.
    # 事件驱动（push）模式激活时的兜底轮询间隔（秒），用于防止推送事件丢失。
    @property
    def SYNC_EVENT_FALLBACK_INTERVAL_SECONDS(self) -> int:
        return int(os.getenv("SYNC_EVENT_FALLBACK_INTERVAL_SECONDS", "300"))

    # Background sync strategy. / 后台同步策略。
    # timed  — Periodic polling loop at SYNC_POLL_INTERVAL_SECONDS
    #          按 SYNC_POLL_INTERVAL_SECONDS 间隔定时轮询
    # push   — Real-time push events from the ComfyUI plugin + fallback polling
    #          依赖 ComfyUI 插件实时推送事件，同时保持兜底轮询
    # manual — No background loop; scan triggered only on tool calls
    #          无后台循环，仅在工具调用时按需扫描
    @property
    def SYNC_MODE(self) -> str:
        return os.getenv("SYNC_MODE", "timed").strip().lower()

    # Minimum wait (seconds) between consecutive on-demand refreshes (manual mode).
    # Prevents excessive ComfyUI API calls when tools are invoked in rapid succession.
    # 按需刷新（manual 模式）两次触发之间的最小冷却时间（秒）。
    # 防止工具被快速连续调用时产生过多的 ComfyUI API 请求。
    @property
    def ONDEMAND_REFRESH_COOLDOWN_SECONDS(self) -> int:
        return int(os.getenv("ONDEMAND_REFRESH_COOLDOWN_SECONDS", "30"))

    # -----------------------------------------------------------------------------
    # Workflow Marker Patterns / 工作流标识符正则表达式
    # -----------------------------------------------------------------------------

    # Regex to identify the "workflow name" node.
    # Must contain exactly ONE capture group that extracts the workflow/tool name.
    # Default: ^==(.+?)==$  (example match: "==generate_portrait==")
    # 工作流名称节点的标题识别正则表达式。
    # 必须包含【恰好一个】捕获组用于提取工具名称。
    # 默认：^==(.+?)==$（示例匹配：「==生成写实人像==」）
    @property
    def WORKFLOW_NAME_REGEX(self) -> re.Pattern:
        pattern = os.getenv("WORKFLOW_NAME_REGEX", r"^==(.+?)==$")
        return re.compile(pattern)

    # Regex to identify configurable parameter nodes.
    # Must contain exactly ONE capture group that extracts the parameter description.
    # Default: ^=>(.+)$  (example match: "=>negative_prompt")
    # 可配置参数节点的标题识别正则表达式。
    # 必须包含【恰好一个】捕获组用于提取参数描述。
    # 默认：^=>(.+)$（示例匹配：「=>负向提示词」）
    @property
    def WORKFLOW_PARAM_REGEX(self) -> re.Pattern:
        pattern = os.getenv("WORKFLOW_PARAM_REGEX", r"^=>(.+)$")
        return re.compile(pattern)

    # -------------------------------------------------------------------------
    # Tool Name Configurations / 工具名称配置
    # Each tool name can be overridden via the corresponding TOOL_NAME_* env var.
    # 每个工具名均可通过对应的 TOOL_NAME_* 环境变量覆盖，方便多语言或自定义命名。
    # -------------------------------------------------------------------------
    @property
    def TOOL_GET_WORKFLOWS_CATALOG(self) -> str:
        return os.getenv("TOOL_NAME_GET_WORKFLOWS_CATALOG", "get_workflows_catalog")

    @property
    def TOOL_GET_WORKFLOW_API(self) -> str:
        return os.getenv("TOOL_NAME_GET_WORKFLOW_API", "get_workflow_API")

    @property
    def TOOL_MOUNT_WORKFLOW(self) -> str:
        return os.getenv("TOOL_NAME_MOUNT_WORKFLOW", "mount_workflow")

    @property
    def TOOL_GET_PROMPT_RESULT(self) -> str:
        return os.getenv("TOOL_NAME_GET_PROMPT_RESULT", "get_prompt_result")

    @property
    def TOOL_QUEUE_PROMPT(self) -> str:
        return os.getenv("TOOL_NAME_QUEUE_PROMPT", "queue_prompt")

    @property
    def TOOL_QUEUE_CUSTOM_PROMPT(self) -> str:
        return os.getenv("TOOL_NAME_QUEUE_CUSTOM_PROMPT", "queue_custom_prompt")

    @property
    def TOOL_SAVE_CUSTOM_WORKFLOW(self) -> str:
        return os.getenv("TOOL_NAME_SAVE_CUSTOM_WORKFLOW", "save_custom_workflow")

    @property
    def TOOL_SAVE_TASK_ASSETS(self) -> str:
        return os.getenv("TOOL_NAME_SAVE_TASK_ASSETS", "save_task_assets")

    @property
    def TOOL_INTERRUPT_PROMPT(self) -> str:
        return os.getenv("TOOL_NAME_INTERRUPT_PROMPT", "interrupt_prompt")

    @property
    def TOOL_GET_SYSTEM_STATUS(self) -> str:
        return os.getenv("TOOL_NAME_GET_SYSTEM_STATUS", "get_system_status")

    @property
    def TOOL_LIST_MODELS(self) -> str:
        return os.getenv("TOOL_NAME_LIST_MODELS", "list_models")

    @property
    def TOOL_GET_CORE_MANUAL(self) -> str:
        return os.getenv("TOOL_NAME_GET_CORE_MANUAL", "get_core_manual")
        
    @property
    def TOOL_UPLOAD_ASSETS(self) -> str:
        return os.getenv("TOOL_NAME_UPLOAD_ASSETS", "upload_assets")

    # FUSION PATCH #3 (PartMe.AI): API-surface completion tools.
    @property
    def TOOL_FREE_MEMORY(self) -> str:
        return os.getenv("TOOL_NAME_FREE_MEMORY", "free_memory")

    @property
    def TOOL_LIST_EMBEDDINGS(self) -> str:
        return os.getenv("TOOL_NAME_LIST_EMBEDDINGS", "list_embeddings")

    @property
    def TOOL_LIST_LOCAL_TEMPLATES(self) -> str:
        return os.getenv("TOOL_NAME_LIST_LOCAL_TEMPLATES", "list_local_templates")

    @property
    def TOOL_UPLOAD_MASK(self) -> str:
        return os.getenv("TOOL_NAME_UPLOAD_MASK", "upload_mask")

    # -------------------------------------------------------------------------
    # System Configuration / 系统配置（内部参数，一般无需修改）
    # -------------------------------------------------------------------------
    @property
    def MCP_SERVER_URL(self) -> str:
        return os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8189/mcp")

    @property
    def MCP_SERVER_IP(self) -> str:
        return os.getenv("MCP_SERVER_IP", "http://127.0.0.1")

    @property
    def MCP_SERVER_PORT(self) -> str:
        return os.getenv("MCP_SERVER_PORT", "8189")


settings = _Settings()
