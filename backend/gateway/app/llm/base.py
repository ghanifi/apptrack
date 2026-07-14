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
