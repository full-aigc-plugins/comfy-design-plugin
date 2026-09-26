"""
Task Execution Service / 任务执行服务

Manages the lifecycle of ComfyUI task submissions: submits prompts, tracks
completion via WebSocket events, optionally calls a progress callback, and
includes a fallback HTTP polling loop for reliability.

管理 ComfyUI 任务提交的完整生命周期：提交 Prompt、通过 WebSocket 事件
追踪完成状态、可选调用进度回调，并包含兜底 HTTP 轮询循环以提高可靠性。
"""

import asyncio
from typing import Dict, Any, Optional
from ..logger import logger
from ..client.http_client import ComfyUIHttpClient
from ..client.ws_client import ComfyUIWebSocketClient


class TaskExecutionService:
    """Submits ComfyUI workflow tasks and waits for their results.
    提交 ComfyUI 工作流任务并等待其执行结果。

    Uses WebSocket "executed" events as the primary completion signal,
    with a polling fallback in case events are missed.
    以 WebSocket "executed" 事件作为主要完成信号，
    以 HTTP 轮询作为兜底机制以防事件遗漏。
    """

    def __init__(self, http_client: ComfyUIHttpClient):
        self.http_client = http_client
        # prompt_id → asyncio.Future that resolves with task result
        # prompt_id → 解析为任务结果的 asyncio.Future
        self._futures: Dict[str, asyncio.Future] = {}
        # prompt_id → optional progress callback
        # prompt_id → 可选的进度回调函数
        self._progress_callbacks: Dict[str, callable] = {}
        # Tracks which WS clients already have event handlers attached.
        # 追踪哪些 WS 客户端已附加了事件处理函数。
        self._subscribed_clients = set()

    async def _handle_executed(self, data: Dict[str, Any]):
        """Handle ComfyUI 'executed' WebSocket event.
        处理 ComfyUI "executed" WebSocket 事件。

        Fetches the task history and resolves the corresponding Future.
        获取任务历史记录，并解析对应的 Future。
        """
        prompt_id = data.get("prompt_id")
        if prompt_id and prompt_id in self._futures:
            future = self._futures[prompt_id]
            if not future.done():
                try:
                    history = await self.http_client.get_history(prompt_id)
                    if isinstance(history, dict) and prompt_id in history:
                        future.set_result(history[prompt_id])
                except Exception as e:
                    logger.error(f"Error fetching history after exec: {e}")

    async def _handle_progress(self, data: Dict[str, Any]):
        """Handle ComfyUI 'progress' WebSocket event.
        处理 ComfyUI "progress" WebSocket 进度事件。

        Invokes the registered progress callback (sync or async) if present.
        若已注册进度回调（同步或异步均支持），则调用之。
        """
        prompt_id = data.get("prompt_id")
        if prompt_id and prompt_id in self._futures:
            logger.debug(f"Progress for {prompt_id}: {data}")
            if prompt_id in self._progress_callbacks:
                value = data.get("value", 0)
                max_value = data.get("max", 0)
                if max_value > 0:
                    callback = self._progress_callbacks[prompt_id]
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(value, max_value)
                        else:
                            callback(value, max_value)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {e}")

    def _ensure_subscribed(self, ws_client: ComfyUIWebSocketClient):
        """Attach event handlers to a WS client only once (idempotent).
        仅附加一次事件处理函数到 WS 客户端（幂等操作）。
        """
        client_id = getattr(ws_client, 'client_id', str(id(ws_client)))
        if client_id not in self._subscribed_clients:
            ws_client.on("executed", self._handle_executed)
            ws_client.on("progress", self._handle_progress)
            self._subscribed_clients.add(client_id)

    async def execute_workflow_task_by_prompts(
        self,
        prompt_config: Dict[str, Any],
        client_id: str,
        ws_client: ComfyUIWebSocketClient,
        timeout: int = 300,
        progress_callback=None,
        is_async: bool = False
    ) -> Dict[str, Any]:
        """Submit a workflow and either wait for completion or return immediately.
        提交工作流并等待完成，或立即返回（异步模式）。

        Args:
            prompt_config:     ComfyUI API-format prompt dict. / ComfyUI API 格式的 Prompt 字典。
            client_id:         WebSocket client identifier. / WebSocket 客户端标识符。
            ws_client:         Active WS client for event listening. / 用于监听事件的活跃 WS 客户端。
            timeout:           Seconds to wait before raising TimeoutError. / 超时秒数。
            progress_callback: Optional callable(value, max) for progress updates. / 可选的进度回调。
            is_async:          If True, return immediately after submission. / 若 True，提交后立即返回。
        """
        response = await self.http_client.queue_prompt(prompt_config, client_id)
        prompt_id = response.prompt_id
        logger.info(f"Task submitted with prompt_id: {prompt_id}")

        # Async mode: caller will poll result later via get_prompt_result tool.
        # 异步模式：调用方稍后通过 get_prompt_result 工具查询结果。
        if is_async:
            return {
                "prompt_id": prompt_id,
                "status": "queued",
                "message": "Task queued asynchronously. Please check status later using get_task_result."
            }

        if progress_callback:
            self._progress_callbacks[prompt_id] = progress_callback

        try:
            return await self.wait_for_execution_completion(prompt_id, ws_client, timeout)
        finally:
            # Always clean up the progress callback regardless of success/failure.
            # 无论成功还是失败，始终清理进度回调。
            self._progress_callbacks.pop(prompt_id, None)

    async def wait_for_execution_completion(
        self,
        prompt_id: str,
        ws_client: ComfyUIWebSocketClient,
        timeout: int
    ) -> Dict[str, Any]:
        """Block until the task completes or times out.
        阻塞等待任务完成或超时。

        Primary signal: WS "executed" event → resolves the Future.
        主要信号：WS "executed" 事件 → 解析 Future。
        Fallback: polls /history every 2 seconds in case the event is missed.
        兜底：每 2 秒轮询 /history 一次，以防事件遗漏。
        """
        self._ensure_subscribed(ws_client)

        future = asyncio.Future()
        self._futures[prompt_id] = future

        async def fallback_poll():
            """Backup polling loop in case WebSocket events are dropped.
            备用轮询循环，用于 WebSocket 事件丢失的情况。
            """
            while not future.done():
                try:
                    history = await self.http_client.get_history(prompt_id)
                    if isinstance(history, dict) and prompt_id in history:
                        if not future.done():
                            future.set_result(history[prompt_id])
                        break
                except Exception:
                    pass
                await asyncio.sleep(2)

        poll_task = asyncio.create_task(fallback_poll())

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Task {prompt_id} timed out")
            raise TimeoutError(f"Task {prompt_id} timed out after {timeout} seconds")
        finally:
            poll_task.cancel()
            self._futures.pop(prompt_id, None)
