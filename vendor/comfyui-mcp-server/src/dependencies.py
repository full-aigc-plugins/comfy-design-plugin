"""
Dependency Container / 依赖容器

Provides a single global `container` instance that holds all shared service
objects. Using deferred (lazy) initialization inside `initialize()` avoids
circular import issues that would occur if services were imported at module
load time.

提供一个全局 `container` 实例，集中持有所有共享服务对象。
在 `initialize()` 内部延迟导入服务类，避免模块加载时的循环导入问题。
"""


class AppContainer:
    """Lightweight service locator / 轻量级服务定位器。

    Attributes / 属性:
        i18n:            I18nService      — Localisation / 国际化服务
        http_client:     ComfyUIHttpClient — HTTP client for ComfyUI REST API
        skills_service:  SkillsService    — Loads skill/manual documents
        task_service:    TaskExecutionService — Submit & track ComfyUI tasks
        catalog_service: CatalogService   — Manages the workflow catalog JSON
        ws_manager:      WebSocketConnectionManager — WS connection pool
        scanner:         WorkflowScanner  — Set by server.py after init
        initialized:     bool             — Guard against duplicate init
    """

    def __init__(self):
        self.i18n = None
        self.http_client = None
        self.skills_service = None
        self.catalog_service = None
        self.ws_manager = None
        # Assigned by server.py after WorkflowScanner is instantiated.
        # 由 server.py 在 WorkflowScanner 实例化后赋值。
        self.scanner = None
        self.initialized = False

    def initialize(self):
        """Lazily import and instantiate all services.
        延迟导入并实例化所有服务（仅执行一次）。
        """
        if self.initialized:
            return

        # Imports are intentionally deferred to avoid circular dependencies
        # at module parse time.
        # 故意延迟导入，避免模块解析时的循环依赖。
        from .services.i18n import I18nService
        from .client.http_client import ComfyUIHttpClient
        from .services.skills import SkillsService
        from .services.tasks import TaskExecutionService
        from .services.catalog_service import CatalogService
        from .client.connection_manager import WebSocketConnectionManager

        self.i18n = I18nService()
        self.http_client = ComfyUIHttpClient()
        self.skills_service = SkillsService()
        self.task_service = TaskExecutionService(self.http_client)
        self.catalog_service = CatalogService()
        self.ws_manager = WebSocketConnectionManager()

        self.initialized = True


# Singleton used throughout the application.
# 整个应用使用的全局单例。
container = AppContainer()
