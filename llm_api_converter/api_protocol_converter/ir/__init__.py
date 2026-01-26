"""
Intermediate Representation (IR) Module

Provides a unified, protocol-agnostic representation for LLM API requests and responses.
This allows for simpler conversion logic by converting source → IR → target.
"""

from .types import (
    # Core types
    IRRequest,
    IRResponse,
    IRMessage,
    IRContentBlock,
    IRToolDeclaration,
    IRToolChoice,
    IRUsage,
    IRStreamEvent,
    IRGenerationConfig,
    IRResponseFormat,
    IRThinkingConfig,
    # Content block types
    IRTextBlock,
    IRImageBlock,
    IRToolUseBlock,
    IRToolResultBlock,
    IRAudioBlock,
    IRDocumentBlock,
    IRThinkingBlock,
    # Enums
    Role,
    ContentBlockType,
    StopReason,
    StreamEventType,
    ImageSourceType,
    ToolChoiceType,
)

__all__ = [
    # Core types
    "IRRequest",
    "IRResponse",
    "IRMessage",
    "IRContentBlock",
    "IRToolDeclaration",
    "IRToolChoice",
    "IRUsage",
    "IRStreamEvent",
    "IRGenerationConfig",
    "IRResponseFormat",
    "IRThinkingConfig",
    # Content block types
    "IRTextBlock",
    "IRImageBlock",
    "IRToolUseBlock",
    "IRToolResultBlock",
    "IRAudioBlock",
    "IRDocumentBlock",
    "IRThinkingBlock",
    # Enums
    "Role",
    "ContentBlockType",
    "StopReason",
    "StreamEventType",
    "ImageSourceType",
    "ToolChoiceType",
]
