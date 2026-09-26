"""
Workflow Catalog Service / 工作流目录服务

Maintains the `workflow_catalog.json` index file that aggregates all
locally-stored workflow API JSON files. Provides create/update operations
and change-detection logic to avoid unnecessary rebuilds.

维护 `workflow_catalog.json` 索引文件，汇总所有本地存储的工作流 API JSON 文件。
提供创建/更新操作及变更检测逻辑，避免不必要的重建。
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from ..logger import logger


class CatalogService:
    """Builds and maintains the workflow catalog JSON index.
    构建并维护工作流目录 JSON 索引。

    The catalog is stored as `workflow/workflow_catalog.json` and lists
    each valid workflow with its name, description, parameters, and timestamps.
    目录存储为 `workflow/workflow_catalog.json`，列出每个有效工作流的
    名称、描述、参数列表和时间戳。
    """

    def __init__(self):
        self.workflow_dir = os.path.join(os.getcwd(), 'workflow')
        self.catalog_path = os.path.join(self.workflow_dir, 'workflow_catalog.json')
        # Track modification times of workflow files to detect changes.
        # 追踪工作流文件的修改时间，用于检测变更。
        self._last_mtimes: Dict[str, float] = {}
        # Async lock to prevent concurrent catalog rebuilds.
        # 异步锁，防止并发重建目录。
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Internal helpers / 内部辅助方法
    # ------------------------------------------------------------------

    def _get_current_mtimes(self) -> Dict[str, float]:
        """Collect modification timestamps of all workflow API JSON files.
        收集所有工作流 API JSON 文件的修改时间戳。

        Excludes the catalog file itself and the legacy workflow.json.
        排除目录文件本身和旧版 workflow.json。
        """
        mtimes = {}
        if not os.path.exists(self.workflow_dir):
            return mtimes

        for filename in os.listdir(self.workflow_dir):
            if filename.endswith(".json") and filename not in ("workflow_catalog.json", "workflow.json"):
                filepath = os.path.join(self.workflow_dir, filename)
                try:
                    mtimes[filepath] = os.path.getmtime(filepath)
                except OSError:
                    pass
        return mtimes

    def _has_changes(self, current_mtimes: Dict[str, float]) -> bool:
        """Return True if the workflow directory contents have changed since last build.
        若自上次构建以来工作流目录内容有变化，返回 True。

        Detects file additions, removals, and modifications.
        检测文件的新增、删除和修改。
        """
        if set(current_mtimes.keys()) != set(self._last_mtimes.keys()):
            return True
        for path, mtime in current_mtimes.items():
            if self._last_mtimes.get(path) != mtime:
                return True
        return False

    def _parse_workflow_data(self, data: Dict[str, Any], mtime: float = 0) -> Optional[Dict[str, Any]]:
        """Parse raw workflow JSON data and extract catalog-level overview fields.
        解析原始工作流 JSON 数据，提取目录级别的概览字段。

        Returns a catalog entry dict, or None if the workflow lacks a valid name node.
        返回目录条目字典，若工作流缺少有效名称节点则返回 None。
        """
        try:
            name = None
            description = ""
            parameters = []
            prompt_id = ""
            inspection_status = "External"

            for node_id, node in data.items():
                if not isinstance(node, dict):
                    continue

                title = node.get("_meta", {}).get("title", "")

                # Detect the workflow name descriptor node.
                # 检测工作流名称描述节点。
                if "PrimitiveStringMultiline" in node.get("class_type", ""):
                    from ..config import settings as _s
                    match = _s.WORKFLOW_NAME_REGEX.search(title)
                    if match:
                        name = match.group(1).strip()
                        inputs = node.get("inputs", {})
                        # Description may be stored under different input key names.
                        # 描述内容可能存储在不同的输入键名下。
                        description = inputs.get("value", inputs.get("string", inputs.get("text", "")))
                        prompt_id = node.get("_meta", {}).get("prompt_id", "")
                        inspection_status = node.get("_meta", {}).get("inspection_status", "External")

                # Collect parameter labels from '=>label' marker nodes.
                # 从 '=>标签' 标识节点中收集参数标签。
                from ..config import settings as _s
                param_match = _s.WORKFLOW_PARAM_REGEX.search(title)
                if param_match:
                    param_name = param_match.group(1).strip()
                    parameters.append(param_name)

            if name:
                return {
                    "name": name,
                    "id": prompt_id,
                    "description": description,
                    "parameters": parameters,
                    "last_updated": int(mtime * 1000),  # UNIX ms / 毫秒时间戳
                    "inspection_status": inspection_status
                }
        except Exception as e:
            logger.error(f"Failed to parse workflow data: {e}")

        return None

    def _parse_workflow(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Load a workflow JSON file from disk and parse it for the catalog.
        从磁盘加载工作流 JSON 文件并解析为目录条目。
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            mtime = os.path.getmtime(filepath)
            return self._parse_workflow_data(data, mtime)
        except Exception as e:
            logger.error(f"Failed to read workflow {filepath}: {e}")

        return None

    # ------------------------------------------------------------------
    # Public API / 公共接口
    # ------------------------------------------------------------------

    async def save_custom_workflow(self, filename: str, api_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and persist a user-supplied workflow, then rebuild the catalog.
        校验并持久化用户提供的工作流，然后重建目录。

        Raises Exception if the workflow has no valid ==name== node (un-mountable).
        若工作流缺少有效 ==名称== 节点（无法挂载），抛出 Exception。

        Returns the catalog entry dict for the saved workflow.
        返回已保存工作流的目录条目字典。
        """
        if not filename.endswith(".json"):
            filename += ".json"

        # Pre-validate before writing to disk.
        # 写入磁盘前先行校验。
        parsed_data = self._parse_workflow_data(api_json, mtime=0)
        if not parsed_data:
            raise Exception(
                "Invalid workflow format: No valid '==Name==' node found. "
                "Cannot save an un-indexable workflow."
            )

        filepath = os.path.join(self.workflow_dir, filename)

        async with self._lock:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(api_json, f, ensure_ascii=False, indent=2)
                # Update the mtime cache immediately to avoid a spurious rebuild on next check.
                # 立即更新 mtime 缓存，避免下次检查时触发多余的重建。
                if os.path.exists(filepath):
                    self._last_mtimes[filepath] = os.path.getmtime(filepath)
            except Exception as e:
                logger.error(f"Failed to save workflow {filepath}: {e}")
                raise Exception(f"Failed to save workflow file: {e}")

        # Rebuild the catalog to reflect the new workflow.
        # 重建目录以反映新工作流。
        await self.rebuild_catalog()

        # Update the returned entry with the real mtime now that the file exists.
        # 用实际 mtime 更新返回的目录条目。
        if os.path.exists(filepath):
            parsed_data["last_updated"] = int(os.path.getmtime(filepath) * 1000)

        return parsed_data

    async def rebuild_catalog(self):
        """Rebuild `workflow_catalog.json` if any workflow files have changed.
        若有工作流文件发生变化，重建 `workflow_catalog.json`。

        Uses mtime comparison to avoid unnecessary disk writes.
        使用 mtime 对比避免不必要的磁盘写入。
        """
        async with self._lock:
            current_mtimes = self._get_current_mtimes()
            if not self._has_changes(current_mtimes):
                return  # No changes detected — skip rebuild. / 无变化，跳过重建。

        logger.info("Changes detected in workflow directory. Rebuilding catalog...")
        catalog = []

        for filepath in current_mtimes.keys():
            parsed_data = self._parse_workflow(filepath)
            if parsed_data:
                catalog.append(parsed_data)

        # Atomically write the catalog file.
        # 原子写入目录文件。
        try:
            with open(self.catalog_path, "w", encoding="utf-8") as f:
                json.dump(catalog, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully rebuilt workflow catalog: {len(catalog)} workflows.")
            self._last_mtimes = current_mtimes
        except Exception as e:
            logger.error(f"Failed to write workflow catalog: {e}")
