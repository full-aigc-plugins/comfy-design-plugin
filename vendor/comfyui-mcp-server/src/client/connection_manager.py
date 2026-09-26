"""
WebSocket Connection Manager / WebSocket 连接管理器

Maintains a pool of active WebSocket connections keyed by client_id to
prevent repeated connect/disconnect ("connection thrashing") when the same
client calls multiple tools in quick succession.

维护一个以 client_id 为键的 WebSocket 活跃连接池，
避免同一客户端在短时间内连续调用工具时反复建立/断开连接（连接抖动）。
"""

from typing import Dict
from .ws_client import ComfyUIWebSocketClient


class WebSocketConnectionManager:
    """Pool of reusable ComfyUI WebSocket connections.
    可复用的 ComfyUI WebSocket 连接池。

    Connections are created on first use and reused for subsequent calls
    from the same client_id.
    连接在首次使用时创建，相同 client_id 的后续调用直接复用。
    """

    def __init__(self):
        # { client_id: ComfyUIWebSocketClient }
        self._pool: Dict[str, ComfyUIWebSocketClient] = {}

    async def get_connection(self, client_id: str) -> ComfyUIWebSocketClient:
        """Return an existing connection or create and connect a new one.
        返回已存在的连接，或新建并建立一个连接。
        """
        if client_id not in self._pool:
            ws_client = ComfyUIWebSocketClient(client_id)
            await ws_client.connect()
            self._pool[client_id] = ws_client
        return self._pool[client_id]

    async def close_all(self):
        """Gracefully disconnect and remove all pooled connections.
        优雅地断开并清除连接池中的所有连接。
        """
        for client in self._pool.values():
            await client.disconnect()
        self._pool.clear()
