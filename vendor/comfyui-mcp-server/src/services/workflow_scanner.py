"""
Workflow Scanner / 工作流扫描器

Core background service that keeps local workflow API JSON files in sync with
ComfyUI's userdata/workflows directory. Behaviour is controlled by SYNC_MODE:

  timed  — Runs `sync_and_prune()` on a configurable polling interval.
            以可配置间隔运行 `sync_and_prune()`轮询循环。

  push   — Deploys a lightweight ComfyUI plugin that pushes save events in real-
           time; `sync_and_prune()` runs at a long fallback interval as a safety net.
           部署轻量 ComfyUI 插件实时推送保存事件；`sync_and_prune()` 以较长间隔运行作为安全网。

  manual — No background loop. `check_and_refresh()` is called on-demand by
           specific tool handlers (get_workflows_catalog / mount_workflow / queue_prompt).
           无后台循环。`check_and_refresh()` 由指定工具处理器按需触发。

Synchronisation logic summary / 同步逻辑概述:
  1. `get_valid_userdata_names()` — Fetch the ComfyUI userdata inventory with timestamps.
                                      获取带时间戳的 ComfyUI userdata 清单。
  2. `scan_history()`             — Initial scan: match history prompts to userdata.
                                      初始扫描：将历史 Prompt 与 userdata 匹配。
  3. `scan_userdata_workflows()`  — Submit + validate workflows not reachable via history.
                                      提交并验证历史中无法匹配的工作流。
  4. `sync_and_prune()`           — Periodic loop: detect stale/deleted workflows and prune.
                                      周期循环：检测并清理过时/删除的工作流。
  5. `check_and_refresh()`        — On-demand diff: compare userdata timestamps vs local.
                                      按需差异比对：对比 userdata 时间戳与本地存档。
"""

import asyncio
import json

import os
import re
from typing import Dict, Any, Optional

from ..logger import logger

from ..client.ws_client import ComfyUIWebSocketClient
from ..dependencies import container
from .workflow.deployer import ExtensionDeployer
from .workflow.validator import WorkflowValidator
from .workflow.storage import StorageManager
from .workflow.queue_manager import QueueManager

class WorkflowScanner:
    """Orchestrates incremental synchronisation between ComfyUI userdata and the local workflow store.
    协调 ComfyUI userdata 与本地工作流存储的增量同步。
    """

    def __init__(self, ws_client: ComfyUIWebSocketClient):
        self.ws_client = ws_client
        self.workflow_dir = os.path.join(os.getcwd(), 'workflow')
        self.storage = StorageManager(self.workflow_dir)
        self.queue_manager = QueueManager(container.http_client)
        # Tracks workflows currently being submitted/validated to prevent duplicate submissions.
        # 追踪正在提交/验证的工作流，防止多次重复提交。
        self.pending_workflows = {}
        # HTTP HEAD ETag/date cache for 304 Not Modified optimisation.
        # 用于 HTTP 304 已某 Not Modified 优化的 HEAD 缓存。
        self._timestamp_cache: Dict[str, str] = {}
        # Caches userdata files that lack ==name== markers so they are not re-scanned on every poll
        # cycle until their file timestamp actually changes (indicating the user edited them).
        # 缓存缺少 ==名称== 标识的 userdata 文件，避免每次轮询循环都重新扫描，
        # 直到文件时间戳发生变化（表明用户已编辑该文件）。
        self._invalid_userdata_cache: Dict[str, float] = {}
        # Cooldown state for manual (on-demand) refresh mode.
        # manual 按需刷新模式的冷却状态。
        self._last_ondemand_refresh_ts: float = 0.0
        self._ondemand_lock = asyncio.Lock()

    async def get_valid_userdata_names(self) -> Dict[str, float]:
        """Fetch workflow names from ComfyUI userdata/workflows with their last-modified timestamps.
        获取 ComfyUI userdata/workflows 中的工作流名称及其最后修改时间戳。

        Returns: { bare_name: modified_ms, ... }
          bare_name    — filename without .json extension / 文件名（不含 .json 后缀）
          modified_ms  — last-modified timestamp in milliseconds / 最后修改时间戳（毫秒）
        """
        valid_names: Dict[str, float] = {}
        from ..utils.workflow_converter import WorkflowConverter
        converter = WorkflowConverter(container.http_client)
        try:
            await converter.init()
            workflows = await container.http_client.get_user_data("workflows")
            if workflows and isinstance(workflows, list):
                import urllib.parse
                import httpx
                import asyncio
                from email.utils import parsedate_to_datetime
                
                semaphore = asyncio.Semaphore(20)  # Limit concurrent HEAD requests. / 限制并发 HEAD 请求数。
                
                async def fetch_timestamp(fname: str) -> float:
                    async with semaphore:
                        try:
                            encoded_path = urllib.parse.quote(f"workflows/{fname}", safe="")
                            url = f"{container.http_client.base_url}/api/userdata/{encoded_path}"
                            
                            headers = {}
                            cached_date = self._timestamp_cache.get(fname)
                            if cached_date:
                                headers["If-Modified-Since"] = cached_date
                                
                            async with httpx.AsyncClient() as client:
                                resp = await client.head(url, headers=headers)
                                
                                if resp.status_code == 304 and cached_date:
                                    # Not modified, reuse parsed time from the string
                                    dt = parsedate_to_datetime(cached_date)
                                    return dt.timestamp() * 1000
                                elif resp.status_code == 200:
                                    lm = resp.headers.get("last-modified")
                                    if lm:
                                        self._timestamp_cache[fname] = lm
                                        dt = parsedate_to_datetime(lm)
                                        return dt.timestamp() * 1000
                        except Exception:
                            pass
                        return 0.0

                json_files = []
                for file_info in workflows:
                    fname = file_info.get("name", "") if isinstance(file_info, dict) else file_info
                    if isinstance(fname, str) and fname.endswith(".json"):
                        json_files.append(fname)
                        
                tasks = [fetch_timestamp(fname) for fname in json_files]
                timestamps = await asyncio.gather(*tasks)
                
                for fname, ts in zip(json_files, timestamps):
                    bare_name = fname[:-5]
                    valid_names[bare_name] = ts
        except Exception as e:
            logger.error(f"Error fetching valid userdata names: {e}")
        return valid_names

    async def scan_history(self):
        """Initial scan: match ComfyUI execution history to userdata workflow files.
        初始扫描：将 ComfyUI 执行历史与 userdata 工作流文件匹配。

        History entries that are older than the corresponding userdata file are skipped
        as stale; those workflows fall back to `scan_userdata_workflows()`.
        历史条目如果旧于对应的 userdata 文件，则作为过时内容跳过；
        这些工作流回退到 `scan_userdata_workflows()` 处理。
        """
        try:
            valid_userdata_names = await self.get_valid_userdata_names()
            stale_or_missing_names = set(valid_userdata_names.keys())
            logger.info(f"[DIAG] scan_history: userdata keys={sorted(stale_or_missing_names)}")
            
            history = await container.http_client.get_all_history()
            history_keys = list(history.keys())
            if not history_keys:
                logger.info("History is empty. Fallback to scanning userdata workflows...")
                await self.scan_userdata_workflows(stale_or_missing_names)
                return

            for prompt_id in reversed(history_keys):
                item = history[prompt_id]
                prompt_data = item.get("prompt", {})
                
                actual_prompt = None
                history_time_ms = 0.0
                if isinstance(prompt_data, list) and len(prompt_data) > 2:
                    potential_prompt = prompt_data[2]
                    if isinstance(potential_prompt, dict):
                        actual_prompt = potential_prompt
                        if len(prompt_data) > 3 and isinstance(prompt_data[3], dict):
                            history_time_ms = prompt_data[3].get("create_time", 0.0)
                elif isinstance(prompt_data, dict):
                    actual_prompt = prompt_data

                if actual_prompt:
                    name = WorkflowValidator.validate_and_extract(actual_prompt, prompt_id, inspection_status="CompleteInspection")
                    if name:
                        in_userdata = name in valid_userdata_names
                        logger.info(f"[DIAG] history name='{name}' in_userdata={in_userdata} in_stale={name in stale_or_missing_names}")
                    if name and name in valid_userdata_names:
                        modified_ms = valid_userdata_names[name]
                        # If history is older than the saved file, we consider it stale.
                        if history_time_ms > 0 and history_time_ms < modified_ms:
                            logger.info(f"Skipping stale history for '{name}' (Modified: {modified_ms} > History: {history_time_ms})")
                            continue
                            
                        # If we reached here, it's valid and fresh enough
                        if name in stale_or_missing_names:
                            self.storage.save_workflow(name, actual_prompt, source_modified_ms=modified_ms)
                            stale_or_missing_names.remove(name)
                            
            logger.info(f"[DIAG] scan_history: remaining after history pass={sorted(stale_or_missing_names)}")
            # Any workflows that were not found in history, or were stale in history, need to be forcibly queued
            if stale_or_missing_names:
                logger.info(f"Found {len(stale_or_missing_names)} workflows lacking fresh history. Emulating scans...")
                await self.scan_userdata_workflows(stale_or_missing_names)
                
        except Exception as e:
            logger.error(f"Error during scan_history: {e}")


    async def scan_userdata_workflows(self, target_names: set = None):
        """Convert and validate userdata workflows that could not be resolved from history.
        转换并验证无法从历史中解析的 userdata 工作流。

        Converts ComfyUI saved-workflow JSON to API prompt format, submits to the
        queue for graph validation, then immediately cancels the test run.
        将 ComfyUI 保存的工作流 JSON 转换为 API Prompt 格式，
        提交到队列进行图校验，然后立即取消测试运行。

        Args:
            target_names: If provided, only process workflows with these bare names.
                          若提供，仅处理裸名在列表内的工作流。
        """
        try:
            from ..utils.workflow_converter import WorkflowConverter
            converter = WorkflowConverter(container.http_client)
            await converter.init()
            
            workflows = await container.http_client.get_user_data("workflows")
            if not workflows or not isinstance(workflows, list):
                return
                
            # Grab current ComfyUI queue to skip duplicate submissions
            queued_workflow_names = await self.queue_manager.get_queued_workflow_names()
            for file_info in workflows:
                if isinstance(file_info, dict):
                    name = file_info.get("name", "")
                elif isinstance(file_info, str):
                    name = file_info
                else:
                    continue
                    
                if not name.endswith(".json"):
                    continue
                    
                bare_name = name[:-5]
                if target_names is not None and bare_name not in target_names:
                    continue
                    
                path = f"workflows/{name}"
                workflow_res = await container.http_client.get_user_data_detail(path)
                if workflow_res:
                    try:
                        prompt_config = converter.convert(workflow_res)
                        # Verify if it has the required markers before even queueing
                        name_extracted = WorkflowValidator.validate_and_extract(prompt_config, inspection_status="InitialInspection")
                        if not name_extracted:
                            if target_names is not None and bare_name in target_names:
                                target_names.remove(bare_name)
                            # Record this bare_name as invalid so sync_and_prune skips it
                            # until the userdata file's timestamp changes.
                            valid_names_snapshot = await self.get_valid_userdata_names()
                            cached_ts = valid_names_snapshot.get(bare_name, 0.0)
                            self._invalid_userdata_cache[bare_name] = cached_ts
                            logger.info(
                                f"Workflow '{bare_name}' has no ==name== marker. "
                                f"Caching as invalid (ts={cached_ts}). Will retry only if file is updated."
                            )
                            continue
                            
                        import time
                        current_time = time.time()
                        if name_extracted in queued_workflow_names:
                            logger.info(f"Workflow '{name_extracted}' is actively in ComfyUI queue. Skipping duplicate.")
                            continue
                        if name_extracted in self.pending_workflows:
                            if current_time - self.pending_workflows[name_extracted] < 600:
                                logger.debug(f"Workflow '{name_extracted}' is currently pending validation locally. Skipping duplicate.")
                                continue
                        self.pending_workflows[name_extracted] = current_time
                            
                        # Check via QueueManager if workflow can really be executed
                        client_id = self.ws_client.client_id
                        if not await self.queue_manager.check_workflow_can_execute(prompt_config, client_id, name_extracted):
                            continue
                            
                        # Inject metadata since we're not waiting for History loop
                        WorkflowValidator.validate_and_extract(prompt_config, prompt_id="validation_pass", inspection_status="InitialInspection")
                        
                        valid_userdata_names = await self.get_valid_userdata_names()
                        # Look up by bare_name (the userdata filename), not name_extracted (the inner MCP name).
                        # They can differ when the user renames the ==name== marker without renaming the file.
                        lookup_key = bare_name if bare_name in valid_userdata_names else name_extracted
                        if lookup_key in valid_userdata_names:
                            modified_ms = valid_userdata_names[lookup_key]
                            self.storage.save_workflow(
                                name_extracted, prompt_config,
                                source_modified_ms=modified_ms,
                                source_bare_name=bare_name  # store userdata filename for prune resolution
                            )
                            logger.info(f"Successfully validated and saved workflow '{name_extracted}' (source file: '{bare_name}').")


                        self.pending_workflows.pop(name_extracted, None)
                        if target_names is not None and bare_name in target_names:
                            target_names.remove(bare_name)
                        
                    except Exception as inner_e:
                        logger.error(f"Failed to convert or queue workflow {path}: {inner_e}")
                        if "name_extracted" in locals():
                            self.pending_workflows.pop(name_extracted, None)
                        if target_names is not None and bare_name in target_names:
                            target_names.remove(bare_name)
        except Exception as e:
            logger.error(f"Error during scan_userdata_workflows: {e}")
            
        # Optimization 1: Rebuild catalog dynamically after modifying local files
        await container.catalog_service.rebuild_catalog()

    async def on_ws_message(self, msg: Dict[str, Any]):
        """Reserved WebSocket message hook (unused; events handled via on() handlers).
        预留的 WebSocket 消息钉子（当前未使用；事件通过 on() 处理函数处理）。
        """
        # The WS client only passes event_data. We need the event_type handled in the listener wrapper or we register specifically.
        pass

    def setup_ws_listeners(self):
        """Register WebSocket event handlers for push-mode and execution tracking.
        注册 push 模式和执行追踪所需的 WebSocket 事件处理函数。
        """
        async def handle_executed(event_data: Dict[str, Any]):
            prompt_id = event_data.get("prompt_id")
            if prompt_id:
                try:
                    history = await container.http_client.get_history(prompt_id)
                    item = history.get(prompt_id)
                    if item:
                        prompt_data = item.get("prompt", [])
                        actual_prompt = None
                        if isinstance(prompt_data, list) and len(prompt_data) > 2:
                            actual_prompt = prompt_data[2]
                        elif isinstance(prompt_data, dict):
                            actual_prompt = prompt_data
                            
                        if actual_prompt:
                            name = WorkflowValidator.validate_and_extract(actual_prompt, prompt_id, inspection_status="CompleteInspection")
                            if name:
                                self.pending_workflows.pop(name, None)
                                valid_userdata_names = await self.get_valid_userdata_names()
                                if name in valid_userdata_names:
                                    modified_ms = valid_userdata_names[name]
                                    self.storage.save_workflow(name, actual_prompt, source_modified_ms=modified_ms)
                                    await container.catalog_service.rebuild_catalog()
                                    logger.info(f"Successfully validated and saved workflow '{name}' from WS event.")
                                else:
                                    logger.info(f"Ignored workflow '{name}' from WS event because it is not in user_data.")
                except Exception as e:
                    logger.error(f"Failed to extract workflow from WS push {prompt_id}: {e}")

        async def handle_execution_error(event_data: Dict[str, Any]):
            exception_msg = event_data.get("exception_message")
            prompt_id = event_data.get("prompt_id")
            logger.error(f"Workflow execution failed for prompt_id {prompt_id}: {exception_msg}")
            # Stop the MCP server as requested: "若在上述步骤中，ComfyUI出现程序性错误，则停止运行，并抛出错误"
            raise RuntimeError(f"ComfyUI execution error: {exception_msg}")

        self.ws_client.on("executed", handle_executed)
        self.ws_client.on("execution_success", handle_executed)
        self.ws_client.on("execution_error", handle_execution_error)

        async def handle_workflow_saved_event(event_data: Dict[str, Any]):
            """Handler for push events sent by the ComfyUI event dispatcher custom node."""
            file_name = event_data.get("file", "")
            if file_name and file_name.endswith(".json"):
                bare_name = file_name[:-5]
                logger.info(f"Received push event for '{bare_name}'. Triggering targeted refresh.")
                await self.scan_userdata_workflows(target_names={bare_name})

        self.ws_client.on("mcp_workflow_saved", handle_workflow_saved_event)

    async def check_and_refresh(self):
        """Lightweight on-demand refresh for SYNC_MODE=manual.
        轻量级按需刷新，适用于 SYNC_MODE=manual。

        Compares userdata timestamps against locally saved `source_modified_ms`,
        then re-scans only stale or missing workflows. Respects cooldown interval
        to prevent excessive API calls on rapid successive tool invocations.
        将 userdata 时间戳与本地存储的 `source_modified_ms` 对比，
        只重新扫描过时或缺失的工作流。
        遵守冷却时间，防止工具被连续快速调用时频繁请求 API。
        """
        import time
        from ..config import settings as _s
        now = time.time()
        cooldown = _s.ONDEMAND_REFRESH_COOLDOWN_SECONDS

        async with self._ondemand_lock:
            if now - self._last_ondemand_refresh_ts < cooldown:
                logger.debug(f"[on_demand] Refresh skipped (cooldown {cooldown}s not elapsed).")
                return
            self._last_ondemand_refresh_ts = now

        logger.info("[on_demand] Checking userdata for workflow updates...")
        try:
            valid_userdata_names = await self.get_valid_userdata_names()
            if not valid_userdata_names:
                return

            # Read local saved source_modified_ms from each workflow file
            local_modified: Dict[str, float] = {}
            for filename in os.listdir(self.workflow_dir):
                if not filename.endswith(".json") or filename in ("workflow_catalog.json", "workflow.json"):
                    continue
                filepath = os.path.join(self.workflow_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for node in data.values():
                        if not isinstance(node, dict):
                            continue
                        title = node.get("_meta", {}).get("title", "")
                        from ..config import settings as _settings
                        if "PrimitiveStringMultiline" in node.get("class_type", "") and _settings.WORKFLOW_NAME_REGEX.search(title):
                            saved_ms = node.get("_meta", {}).get("source_modified_ms", 0.0)
                            source_bare = node.get("_meta", {}).get("source_bare_name", "")
                            match = _settings.WORKFLOW_NAME_REGEX.search(title)
                            name_in_file = match.group(1).strip() if match else ""
                            key = source_bare if source_bare else name_in_file
                            if key:
                                local_modified[key] = saved_ms
                            break
                except Exception:
                    pass

            stale_or_missing = set()
            for bare_name, userdata_ts in valid_userdata_names.items():
                local_ts = local_modified.get(bare_name, -1.0)
                if local_ts < 0 or userdata_ts > local_ts:
                    stale_or_missing.add(bare_name)

            if stale_or_missing:
                logger.info(f"[on_demand] Found {len(stale_or_missing)} stale/missing workflows: {stale_or_missing}. Refreshing...")
                await self.scan_userdata_workflows(target_names=stale_or_missing)
            else:
                logger.info("[on_demand] All local workflows are up-to-date.")
                await container.catalog_service.rebuild_catalog()
        except Exception as e:
            logger.error(f"[on_demand] Error during check_and_refresh: {e}")

    async def start(self):
        """Initialise the scanner: run first scan, rebuild catalog, start background loop.
        初始化扫描器：执行首次扫描、重建目录和（如需）启动后台同步循环。
        """
        logger.info("Starting workflow scanner...")
        self.setup_ws_listeners()
        # Perform the initial full scan against ComfyUI history + userdata.
        # 执行首次全量扫描：匹配 ComfyUI 历史记录 + userdata 。
        await self.scan_history()
        # Ensure the catalog reflects the initial state immediately.
        # 确保目录立即反映初始状态。
        await container.catalog_service.rebuild_catalog()

        from ..config import settings as _s
        if _s.SYNC_MODE == "manual":
            logger.info("Sync mode: manual — background sync loop disabled. Refreshes happen on tool calls only.")
        else:
            # timed or push: start the periodic background maintenance loop.
            # timed 或 push 模式：启动周期后台维护循环。
            asyncio.create_task(self.sync_and_prune())

    async def sync_and_prune(self):
        """Periodic maintenance loop: detect stale/deleted workflows, prune local files, rescan if needed.
        周期维护循环：检测过时/已删除的工作流，清理本地文件，按需触发重扫。

        Poll interval is determined by SYNC_MODE + whether the push-mode extension
        is deployed:
          timed   → SYNC_POLL_INTERVAL_SECONDS (default: fast, ~3s)
          push    → SYNC_EVENT_FALLBACK_INTERVAL_SECONDS (default: slow, ~300s)
        轮询间隔由 SYNC_MODE 和 push 模式插件是否已就位决定。
        """
        # Short initial delay to let the first scan settle before maintenance begins.
        # 短暂延迟，让首次扫描稳定后再开始维护循环。
        await asyncio.sleep(10)

        from ..config import settings as _s
        # push mode: either explicitly configured, or extension deployed successfully
        event_mode_active = (_s.SYNC_MODE == "push") or ExtensionDeployer.try_deploy_extension()
        poll_interval = _s.SYNC_EVENT_FALLBACK_INTERVAL_SECONDS if event_mode_active else _s.SYNC_POLL_INTERVAL_SECONDS
        logger.info(
            f"sync_and_prune: running in "
            f"{'event-driven (fallback every ' + str(poll_interval) + 's)' if event_mode_active else 'polling (every ' + str(poll_interval) + 's)'} mode."
        )
        
        while True:
            try:
                valid_history_prompt_ids = set()
                
                # 1. Fetch Userdata as SOURCE OF TRUTH
                valid_userdata_names = await self.get_valid_userdata_names()
                stale_or_missing_names = set(valid_userdata_names.keys())
                
                # Filter out workflows that previously failed ==name== validation and haven't been updated.
                # When userdata_ts changes, the cache entry is stale itself → re-include for retry.
                previously_invalid = {
                    name for name, cached_ts in self._invalid_userdata_cache.items()
                    if name in valid_userdata_names and valid_userdata_names[name] <= cached_ts
                }
                if previously_invalid:
                    stale_or_missing_names -= previously_invalid

                
                # 2. Fetch History (only to verify prompt_id for downgrading)
                try:
                    history = await container.http_client.get_all_history()
                    if history:
                        for prompt_id, item in history.items():
                            prompt_data = item.get("prompt", {})
                            actual_prompt = None
                            if isinstance(prompt_data, list) and len(prompt_data) > 2:
                                actual_prompt = prompt_data[2]
                            elif isinstance(prompt_data, dict):
                                actual_prompt = prompt_data
                                
                            if actual_prompt:
                                # validate_and_extract without passing source_type so it doesn't mutate
                                name = WorkflowValidator.validate_and_extract(actual_prompt.copy())
                                if name and name in valid_userdata_names:
                                    valid_history_prompt_ids.add(prompt_id)
                except Exception as e:
                    logger.debug(f"sync_and_prune history fetch error: {e}")
                                    
                # 3. Prune local files
                for filename in os.listdir(self.workflow_dir):
                    if filename.endswith(".json") and filename not in ["workflow_catalog.json", "workflow.json"]:
                        filepath = os.path.join(self.workflow_dir, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                
                            name_in_file = None
                            inspection_status = "External"
                            target_prompt_id = ""
                            saved_modified_ms = 0.0
                            source_bare_name_field = ""
                            
                            for node in data.values():
                                if isinstance(node, dict):
                                    title = node.get("_meta", {}).get("title", "")
                                    from ..config import settings as _s
                                    if "PrimitiveStringMultiline" in node.get("class_type", "") and _s.WORKFLOW_NAME_REGEX.search(title):
                                        match = _s.WORKFLOW_NAME_REGEX.search(title)
                                        if match:
                                            name_in_file = match.group(1).strip()
                                            inspection_status = node.get("_meta", {}).get("inspection_status", "External")
                                            target_prompt_id = node.get("_meta", {}).get("prompt_id", "")
                                            saved_modified_ms = node.get("_meta", {}).get("source_modified_ms", 0.0)
                                            # source_bare_name links the local file back to its userdata filename,
                                            # even when ==name== (MCP tool name) diverges from the filename.
                                            source_bare_name_field = node.get("_meta", {}).get("source_bare_name", "")
                                            break
                                            
                            # Resolve the key to use for valid_userdata_names lookup.
                            # Priority: source_bare_name > name_in_file (handles filename/inner-name divergence)
                            userdata_key = (
                                source_bare_name_field if source_bare_name_field and source_bare_name_field in valid_userdata_names
                                else name_in_file if name_in_file and name_in_file in valid_userdata_names
                                else None
                            )
                            if inspection_status in ["CompleteInspection", "InitialInspection"]:
                                if not userdata_key:
                                    logger.info(f"Pruning obsolete workflow API file: {filename} (source: {inspection_status}, not in user_data)")
                                    os.remove(filepath)
                                elif valid_userdata_names[userdata_key] > saved_modified_ms:
                                    logger.info(f"Pruning stale workflow API file: {filename} (Local: {saved_modified_ms}, UserData: {valid_userdata_names[userdata_key]}). Will rebuild/upgrade.")
                                    os.remove(filepath)
                                    # It remains in stale_or_missing_names
                                else:
                                    # Valid and fresh — remove the userdata key from stale set
                                    stale_or_missing_names.discard(userdata_key)
                                    stale_or_missing_names.discard(name_in_file)
                                        
                                    if inspection_status == "CompleteInspection":
                                        if not target_prompt_id or target_prompt_id not in valid_history_prompt_ids:
                                            logger.info(f"Downgrading workflow API file {filename} to user_data because history is cleared but userdata exists.")
                                            for k, v in data.items():
                                                if isinstance(v, dict):
                                                    vtitle = v.get("_meta", {}).get("title", "")
                                                    from ..config import settings as _s
                                                    if "PrimitiveStringMultiline" in v.get("class_type", "") and _s.WORKFLOW_NAME_REGEX.search(vtitle):
                                                        v["_meta"]["inspection_status"] = "InitialInspection"
                                                        break
                                            with open(filepath, "w", encoding="utf-8") as fw:
                                                json.dump(data, fw, ensure_ascii=False, indent=2)
                                            
                        except Exception as inner_e:
                            logger.error(f"Error checking file for pruning {filename}: {inner_e}")
                            
                # 4. Trigger scan for anything missing or just pruned
                if stale_or_missing_names:
                    logger.info(f"Detected {len(stale_or_missing_names)} missing or modified workflows during sync. Refreshing APIs...")
                    await self.scan_userdata_workflows(target_names=stale_or_missing_names)
                    
                # Event-driven catalog rebuild if anything changed
                await container.catalog_service.rebuild_catalog()
                            
            except Exception as e:
                logger.error(f"Error in sync_and_prune loop: {e}")
                
            await asyncio.sleep(poll_interval)
