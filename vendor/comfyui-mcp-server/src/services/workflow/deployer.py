"""
ComfyUI Extension Deployer / ComfyUI 插件部署器

Auto-deploys the `mcp_event_dispatcher` custom node into the ComfyUI
`custom_nodes/` directory when SYNC_MODE=push and COMFY_UI_INSTALL_PATH
is configured. Enables real-time save-event push notifications.

当 SYNC_MODE=push 且配置了 COMFY_UI_INSTALL_PATH 时，
自动将 `mcp_event_dispatcher` 自定义节点部署到 ComfyUI 的 `custom_nodes/`
目录，以启用实时保存事件推送通知。
"""

import os
from ...logger import logger
from ...config import settings


class ExtensionDeployer:
    """Handles auto-deployment of the MCP event dispatcher ComfyUI plugin.
    负责自动部署 MCP 事件推送分发器 ComfyUI 插件。
    """

    @staticmethod
    def try_deploy_extension() -> bool:
        """Attempt to deploy or update the ComfyUI event dispatcher custom node.
        尝试部署或更新 ComfyUI 事件推送分发器自定义节点。

        Returns True  → extension is already in place and up-to-date;
                        event-driven push mode is active after ComfyUI restarts.
                True  → 插件已就位且为最新版本；
                        ComfyUI 重启后 push 模式即可生效。

        Returns False → COMFY_UI_INSTALL_PATH not set, extension source missing,
                        or the plugin was just written/updated (requires ComfyUI restart).
                False → COMFY_UI_INSTALL_PATH 未配置、插件源文件缺失，
                        或插件刚被写入/更新（需重启 ComfyUI 才能生效）。
        """
        install_path = settings.COMFY_UI_INSTALL_PATH
        if not install_path:
            # Push mode requires local ComfyUI access; skip if not configured.
            # push 模式需要本地 ComfyUI 访问权限；未配置时跳过。
            return False

        # Target: <ComfyUI>/custom_nodes/mcp_event_dispatcher/__init__.py
        target_dir = os.path.join(install_path, "custom_nodes", "mcp_event_dispatcher")
        target_init = os.path.join(target_dir, "__init__.py")

        # Source: this package's bundled extension file
        # 源文件：本包捆绑的插件文件
        src_init = os.path.join(
            os.path.dirname(__file__), "..", "..", "comfy_extension", "mcp_event_dispatcher", "__init__.py"
        )

        if not os.path.exists(src_init):
            logger.warning("ComfyUI extension source not found. Event-driven mode unavailable.")
            return False

        with open(src_init, "r", encoding="utf-8") as f:
            new_content = f.read()

        # If the deployed file already matches the source, no action needed.
        # 若已部署的文件与源文件内容一致，无需任何操作。
        if os.path.exists(target_init):
            with open(target_init, "r", encoding="utf-8") as f:
                if f.read() == new_content:
                    logger.info("ComfyUI event extension is up-to-date. Event-driven mode ACTIVE.")
                    return True

        # Deploy (or update) the extension file.
        # 部署（或更新）插件文件。
        os.makedirs(target_dir, exist_ok=True)
        with open(target_init, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.warning(
            "ComfyUI event extension deployed/updated. "
            "Please restart ComfyUI to activate event-driven mode. "
            "Falling back to polling until then."
        )
        return False
