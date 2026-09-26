"""
Workflow Queue Manager / 工作流队列管理器

Provides helpers for queue-related operations used by the WorkflowScanner:
  - Detect which workflow names are currently in ComfyUI's queue (deduplication)
  - Validate a workflow graph by dry-running it and immediately cancelling

提供 WorkflowScanner 使用的队列相关辅助功能：
  - 检测当前 ComfyUI 队列中已有哪些工作流名称（去重）
  - 通过试运行并立即取消的方式校验工作流图的合法性
"""

import asyncio
from typing import Dict, Any, Set
from ...logger import logger
from ...client.http_client import ComfyUIHttpClient
from .validator import WorkflowValidator


class QueueManager:
    """Queue utilities for the WorkflowScanner.
    WorkflowScanner 使用的队列管理工具类。
    """

    def __init__(self, http_client: ComfyUIHttpClient):
        self.http_client = http_client

    async def get_queued_workflow_names(self) -> Set[str]:
        """Return the set of workflow names currently present in the ComfyUI queue.
        返回当前 ComfyUI 队列中已存在的工作流名称集合，用于去重。

        Inspects both `queue_running` and `queue_pending` sections.
        同时检查 `queue_running` 和 `queue_pending` 两个队列区段。
        """
        queued_names = set()
        try:
            current_queue = await self.http_client.get_queue()
            if isinstance(current_queue, dict):
                for key in ["queue_running", "queue_pending"]:
                    for item in current_queue.get(key, []):
                        # Queue item format: [number, prompt_id, prompt_dict, ...]
                        # 队列项格式：[序号, prompt_id, prompt 字典, ...]
                        if isinstance(item, list) and len(item) > 2 and isinstance(item[2], dict):
                            name = WorkflowValidator.validate_and_extract(item[2].copy())
                            if name:
                                queued_names.add(name)
        except Exception as e:
            logger.warning(f"Failed to fetch queue for deduplication: {e}")

        return queued_names

    async def check_workflow_can_execute(
        self,
        prompt_config: Dict[str, Any],
        client_id: str,
        workflow_name: str
    ) -> bool:
        """Validate a workflow by submitting it and immediately cancelling.
        通过提交工作流后立即取消的方式验证其合法性（确认所有自定义节点存在）。

        This approach lets ComfyUI's graph engine perform its validation pass
        without wasting GPU resources on actual execution.
        利用 ComfyUI 图引擎的校验阶段进行验证，无需实际执行，节省 GPU 资源。

        Returns True if the submission succeeded (graph is valid).
        若提交成功（图合法），返回 True。
        Returns False if ComfyUI rejected the submission (missing nodes, bad graph).
        若 ComfyUI 拒绝提交（缺少节点或图非法），返回 False。
        """
        try:
            resp = await self.http_client.queue_prompt(prompt_config, client_id)
            prompt_id = resp.prompt_id
            logger.info(f"Queued validation prompt for workflow '{workflow_name}' with prompt_id {prompt_id}")

            # Immediately cancel the submitted prompt to free resources.
            # 立即取消已提交的 Prompt，释放资源。
            try:
                await self.http_client.delete_from_queue(prompt_id)
                # Check if the prompt slipped into execution before we could cancel it.
                # 检查 Prompt 是否在取消前已开始执行。
                q = await self.http_client.get_queue()
                running = q.get("queue_running", [])
                if running and len(running) > 0 and running[0][1] == prompt_id:
                    await self.http_client.interrupt()
                    logger.info(f"Interrupted validation prompt {prompt_id} that started executing.")
            except Exception as cancel_e:
                logger.warning(f"Could not cancel validation task {prompt_id}: {cancel_e}")

            return True
        except Exception as queue_e:
            logger.error(
                f"Failed to validate workflow '{workflow_name}'. "
                f"Missing nodes or invalid graph? Error: {queue_e}"
            )
            return False
