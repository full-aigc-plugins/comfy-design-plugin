"""
WebSocket Client for ComfyUI / ComfyUI WebSocket 客户端

Maintains a persistent WebSocket connection to ComfyUI and dispatches
typed events (e.g. "executed", "progress") to registered async handlers.

维护与 ComfyUI 的持久 WebSocket 连接，并将类型化事件
（如 "executed"、"progress"）分发给已注册的异步处理函数。
"""

import asyncio
import json
import websockets
from typing import Optional, Callable, Dict, Any, Awaitable
from ..logger import logger
from ..config import settings

# Type alias for async event handler callbacks.
# 异步事件回调处理函数的类型别名。
EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class ComfyUIWebSocketClient:
    """Event-driven WebSocket client for ComfyUI.
    基于事件驱动的 ComfyUI WebSocket 客户端。

    Supports multiple handlers per event type via `on()` / `off()`.
    通过 `on()` / `off()` 支持每种事件类型注册多个处理函数。
    """

    def __init__(self, client_id: str, ws_url: Optional[str] = None):
        self.client_id = client_id
        host = settings.COMFY_UI_SERVER_IP
        if host.endswith('/'):
            host = host[:-1]

        # Convert http(s):// to ws(s):// for the WebSocket URL.
        # 将 http(s):// 转换为 ws(s):// 构建 WebSocket 连接地址。
        default_ws_url = host.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = ws_url or f"{default_ws_url}/ws?clientId={client_id}"

        self.connection: Optional[websockets.WebSocketClientProtocol] = None
        self._task: Optional[asyncio.Task] = None
        # event_type -> list of handlers
        # 事件类型 -> 处理函数列表
        self._handlers: Dict[str, list[EventHandler]] = {}

    def on(self, event_type: str, handler: EventHandler):
        """Register a handler for the given event type.
        为指定事件类型注册处理函数。
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: EventHandler):
        """Unregister a previously registered handler.
        注销已注册的处理函数。
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def connect(self):
        """Open the WebSocket connection and start the background listener task.
        建立 WebSocket 连接并启动后台监听任务。
        """
        logger.info(f"Connecting to ComfyUI WebSocket at {self.ws_url}")
        self.connection = await websockets.connect(self.ws_url)
        self._task = asyncio.create_task(self._listen())

    async def disconnect(self):
        """Gracefully cancel the listener task and close the connection.
        优雅地取消监听任务并关闭 WebSocket 连接。
        """
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.connection:
            await self.connection.close()
            logger.info("Disconnected from ComfyUI WebSocket")

    async def _listen(self):
        """Background loop that receives and dispatches WebSocket messages.
        后台循环：接收 WebSocket 消息并将其分发给对应的事件处理函数。
        """
        try:
            async for message in self.connection:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        event_type = data.get("type")
                        event_data = data.get("data", {})

                        logger.debug(f"WS Event received: {event_type}")

                        # Invoke all registered handlers for this event type.
                        # 调用该事件类型的所有已注册处理函数。
                        if event_type in self._handlers:
                            for handler in self._handlers[event_type]:
                                await handler(event_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse WebSocket message: {message}")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket listening error: {e}")
