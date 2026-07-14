"""LLM ağ geçidi ortak tipleri — sağlayıcıdan bağımsız arayüz."""
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    text: str
    model: str
    usage: dict = field(default_factory=dict)


class LLMError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON-schema (type/properties/required)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class AgenticResult:
    text: str
    tool_calls: list = field(default_factory=list)  # list[ToolCall]
    usage: dict = field(default_factory=dict)        # {input_tokens, output_tokens}
    stop_reason: str = ""
