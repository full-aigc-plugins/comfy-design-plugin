"""
Workflow Storage Manager / 工作流存储管理器

Handles writing extracted workflow API JSON files to the local `workflow/`
directory and injecting source-tracking metadata into the descriptor node.

负责将提取的工作流 API JSON 文件写入本地 `workflow/` 目录，
并将来源追踪元数据注入描述节点的 `_meta` 字段。
"""

import os
import json
from typing import Dict, Any
from ...logger import logger
from ...config import settings


class StorageManager:
    """Persists workflow API JSON files to the local workflow directory.
    将工作流 API JSON 文件持久化到本地工作流目录。
    """

    def __init__(self, workflow_dir: str):
        self.workflow_dir = workflow_dir
        # Ensure the directory exists at startup.
        # 启动时确保目录存在。
        os.makedirs(self.workflow_dir, exist_ok=True)

    def save_workflow(
        self,
        workflow_name: str,
        prompt_data: Dict[str, Any],
        source_modified_ms: float = 0.0,
        source_bare_name: str = ""
    ):
        """Persist a workflow API JSON to disk, injecting source metadata.
        将工作流 API JSON 持久化到磁盘，同时注入来源元数据。

        Args:
            workflow_name:      Name used as the filename stem.
                                用作文件名主干的工作流名称。
            prompt_data:        The ComfyUI API-format prompt dict.
                                ComfyUI API 格式的 Prompt 字典。
            source_modified_ms: Modification timestamp of the originating userdata file (ms).
                                源 userdata 文件的修改时间戳（毫秒），用于增量同步比对。
            source_bare_name:   The bare filename from userdata (without extension).
                                userdata 中的裸文件名（不含扩展名），
                                用于 sync_and_prune 在 ==name== 与文件名不一致时仍能正确查找。
        """
        # Locate the descriptor node and inject source metadata.
        # 找到描述节点并注入来源元数据。
        for node in prompt_data.values():
            if isinstance(node, dict):
                title = node.get('_meta', {}).get('title', '')
                if "PrimitiveStringMultiline" in node.get("class_type", "") and settings.WORKFLOW_NAME_REGEX.search(title):
                    if source_modified_ms > 0:
                        node['_meta']['source_modified_ms'] = source_modified_ms
                    # Record which userdata filename this workflow came from.
                    # 记录该工作流来自哪个 userdata 文件名。
                    node['_meta']['source_bare_name'] = source_bare_name or workflow_name
                    break

        file_path = os.path.join(self.workflow_dir, f"{workflow_name}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(prompt_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved extracted workflow API: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save workflow {workflow_name}: {e}")
