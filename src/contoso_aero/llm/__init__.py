"""Model access shared by intent detection and every agent module."""

from .client import (
    ChatCompletionClient,
    ModelClient,
    ModelError,
    ModelResponse,
    ToolCall,
)

__all__ = ["ChatCompletionClient", "ModelClient", "ModelError", "ModelResponse", "ToolCall"]
