"""
ComfyUI Data Models / ComfyUI 数据模型

Pydantic models that represent ComfyUI API request/response structures and
the internal parameter definitions used when mounting workflows as MCP tools.

使用 Pydantic 定义的数据模型，表示 ComfyUI API 的请求/响应结构
以及将工作流挂载为 MCP 工具时使用的内部参数定义。
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class ComfyPromptConfig(BaseModel):
    """Payload sent to the ComfyUI /prompt endpoint.
    发送到 ComfyUI /prompt 接口的请求体。
    """
    client_id: str
    prompt: Dict[str, Any]
    extra_data: Optional[Dict[str, Any]] = None


class ComfyNodeMeta(BaseModel):
    """Node metadata (_meta field) in a ComfyUI prompt graph.
    ComfyUI prompt 图中节点的元数据（_meta 字段）。
    """
    title: str


class ComfyNode(BaseModel):
    """A single node in a ComfyUI API-format workflow.
    ComfyUI API 格式工作流中的单个节点。
    """
    class_type: str
    inputs: Dict[str, Any]
    meta: Optional[ComfyNodeMeta] = Field(None, alias="_meta")


class ComfyTaskResponse(BaseModel):
    """Response returned by the ComfyUI /prompt endpoint after task submission.
    提交任务到 ComfyUI /prompt 接口后返回的响应体。
    """
    prompt_id: str  # Unique task identifier / 唯一任务标识符
    number: int     # Queue position / 队列位置
    node_errors: Dict[str, Any]  # Any node-level validation errors / 节点级校验错误


class ConfigurableParam(BaseModel):
    """Describes a single configurable parameter extracted from a mounted workflow.
    描述从已挂载工作流中提取的单个可配置参数。

    Attributes / 属性:
        path:             "{nodeId}.{inputKey}"  — Dotted access path / 点分访问路径
        nodeId:           ComfyUI node ID (string) / 节点 ID
        inputKey:         Input field name / 输入字段名称
        type:             JSON schema type: string / number / boolean / array
        defaultValue:     Value from the workflow template / 工作流模板中的默认值
        classType:        ComfyUI node class_type / 节点 class_type
        nodeTitle:        Node _meta.title / 节点标题
        nodeDescription:  Extracted from '=>...' marker / 从 '=>...' 标识提取的描述
        description:      Human-readable description for the LLM / 给 LLM 的可读描述
        required:         Whether the param must be supplied / 是否必须提供该参数
        enumValues:       Allowed values, if constrained / 允许的枚举值（如有约束）
    """
    path: str
    nodeId: str
    inputKey: str
    type: str
    defaultValue: Any
    classType: str
    nodeTitle: str
    nodeDescription: str
    description: str
    required: bool
    enumValues: Optional[list] = None
