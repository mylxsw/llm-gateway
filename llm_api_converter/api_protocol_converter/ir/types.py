"""
Intermediate Representation Type Definitions

These types provide a unified, protocol-agnostic representation for LLM API
requests and responses, enabling simpler conversion logic.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class Role(str, Enum):
    """Unified role representation across all protocols."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ContentBlockType(str, Enum):
    """Types of content blocks in messages."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    REDACTED_THINKING = "redacted_thinking"


class ImageSourceType(str, Enum):
    """Image source types."""
    URL = "url"
    BASE64 = "base64"


class ToolChoiceType(str, Enum):
    """Tool choice options."""
    AUTO = "auto"
    NONE = "none"
    ANY = "any"  # Required in OpenAI, any in Anthropic
    SPECIFIC = "specific"  # Specific tool by name


class StopReason(str, Enum):
    """Unified stop/finish reason across protocols."""
    END_TURN = "end_turn"  # Normal completion
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


class StreamEventType(str, Enum):
    """Types of streaming events."""
    # Message-level events
    MESSAGE_START = "message_start"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"
    # Content block events
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_BLOCK_DELTA = "content_block_delta"
    CONTENT_BLOCK_STOP = "content_block_stop"
    # Utility events
    PING = "ping"
    ERROR = "error"
    DONE = "done"


@dataclass
class IRTextBlock:
    """Text content block."""
    type: ContentBlockType = field(default=ContentBlockType.TEXT, init=False)
    text: str = ""
    citations: Optional[List[Dict[str, Any]]] = None


@dataclass
class IRImageBlock:
    """Image content block."""
    type: ContentBlockType = field(default=ContentBlockType.IMAGE, init=False)
    source_type: ImageSourceType = ImageSourceType.URL
    url: Optional[str] = None
    base64_data: Optional[str] = None
    media_type: Optional[str] = None  # e.g., "image/jpeg", "image/png"
    detail: Optional[str] = None  # OpenAI-specific: "auto", "low", "high"


@dataclass
class IRAudioBlock:
    """Audio content block."""
    type: ContentBlockType = field(default=ContentBlockType.AUDIO, init=False)
    source_type: str = "base64"  # or "url"
    data: Optional[str] = None
    url: Optional[str] = None
    format: Optional[str] = None  # e.g., "wav", "mp3"


@dataclass
class IRDocumentBlock:
    """Document/file content block."""
    type: ContentBlockType = field(default=ContentBlockType.DOCUMENT, init=False)
    source_type: str = "base64"  # base64, url, or text
    data: Optional[str] = None
    url: Optional[str] = None
    media_type: Optional[str] = None  # e.g., "application/pdf"
    title: Optional[str] = None
    context: Optional[str] = None


@dataclass
class IRToolUseBlock:
    """Tool/function call content block."""
    type: ContentBlockType = field(default=ContentBlockType.TOOL_USE, init=False)
    id: str = ""
    name: str = ""
    input: Dict[str, Any] = field(default_factory=dict)
    # For streaming: partial arguments as string
    partial_arguments: Optional[str] = None


@dataclass
class IRToolResultBlock:
    """Tool/function result content block."""
    type: ContentBlockType = field(default=ContentBlockType.TOOL_RESULT, init=False)
    tool_use_id: str = ""
    content: Union[str, List["IRContentBlock"]] = ""
    is_error: bool = False


@dataclass
class IRThinkingBlock:
    """Extended thinking/reasoning content block."""
    type: ContentBlockType = field(default=ContentBlockType.THINKING, init=False)
    thinking: str = ""
    signature: Optional[str] = None  # Anthropic's verification signature
    # For redacted thinking
    is_redacted: bool = False
    redacted_data: Optional[str] = None


# Union type for all content blocks
IRContentBlock = Union[
    IRTextBlock,
    IRImageBlock,
    IRAudioBlock,
    IRDocumentBlock,
    IRToolUseBlock,
    IRToolResultBlock,
    IRThinkingBlock,
]


@dataclass
class IRMessage:
    """Unified message representation."""
    role: Role
    content: List[IRContentBlock] = field(default_factory=list)
    name: Optional[str] = None  # Optional name for the message author

    def get_text_content(self) -> str:
        """Extract text content from all text blocks."""
        texts = []
        for block in self.content:
            if isinstance(block, IRTextBlock):
                texts.append(block.text)
        return "".join(texts)

    def get_tool_calls(self) -> List[IRToolUseBlock]:
        """Extract all tool use blocks."""
        return [b for b in self.content if isinstance(b, IRToolUseBlock)]


@dataclass
class IRToolDeclaration:
    """Unified tool/function declaration."""
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)  # JSON Schema
    strict: bool = False  # OpenAI's strict mode


@dataclass
class IRToolChoice:
    """Unified tool choice configuration."""
    type: ToolChoiceType = ToolChoiceType.AUTO
    name: Optional[str] = None  # For SPECIFIC type
    disable_parallel: bool = False


@dataclass
class IRUsage:
    """Unified usage/token metrics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: Optional[int] = None
    # Cache-related
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    # Reasoning-related
    reasoning_tokens: int = 0
    # Audio-related (OpenAI)
    audio_tokens: int = 0
    # Extended details preserved from source
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.total_tokens is None:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class IRGenerationConfig:
    """Unified generation configuration."""
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None  # Anthropic only
    max_tokens: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    seed: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None
    n: Optional[int] = None  # Number of completions (OpenAI only)


@dataclass
class IRResponseFormat:
    """Unified response format configuration."""
    type: str = "text"  # text, json_object, json_schema
    json_schema: Optional[Dict[str, Any]] = None
    schema_name: Optional[str] = None
    strict: bool = False


@dataclass
class IRThinkingConfig:
    """Extended thinking configuration (Anthropic)."""
    enabled: bool = False
    budget_tokens: Optional[int] = None


@dataclass
class IRRequest:
    """
    Unified request representation.

    This is the intermediate representation that all source protocols
    are converted to before being converted to the target protocol.
    """
    model: str
    messages: List[IRMessage] = field(default_factory=list)
    system: Optional[str] = None  # System prompt

    # Generation configuration
    generation_config: IRGenerationConfig = field(default_factory=IRGenerationConfig)

    # Tools
    tools: List[IRToolDeclaration] = field(default_factory=list)
    tool_choice: Optional[IRToolChoice] = None

    # Response format
    response_format: Optional[IRResponseFormat] = None

    # Thinking (Anthropic extended thinking)
    thinking: Optional[IRThinkingConfig] = None

    # Streaming
    stream: bool = False

    # User tracking
    user: Optional[str] = None

    # Metadata and unsupported params
    metadata: Dict[str, Any] = field(default_factory=dict)
    unsupported_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IRResponse:
    """
    Unified response representation.

    This is the intermediate representation that all source protocol
    responses are converted to before being converted to the target protocol.
    """
    id: str
    model: str
    content: List[IRContentBlock] = field(default_factory=list)
    stop_reason: Optional[StopReason] = None
    stop_sequence: Optional[str] = None
    usage: Optional[IRUsage] = None

    # Original created timestamp
    created: Optional[int] = None

    # For multiple choices (OpenAI's n parameter)
    choice_index: int = 0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_text_content(self) -> str:
        """Extract text content from all text blocks."""
        texts = []
        for block in self.content:
            if isinstance(block, IRTextBlock):
                texts.append(block.text)
        return "".join(texts)

    def get_tool_calls(self) -> List[IRToolUseBlock]:
        """Extract all tool use blocks."""
        return [b for b in self.content if isinstance(b, IRToolUseBlock)]


@dataclass
class IRStreamEvent:
    """
    Unified stream event representation.

    Provides a common structure for streaming events across all protocols.
    """
    type: StreamEventType
    index: int = 0  # Content block index

    # For MESSAGE_START
    response: Optional[IRResponse] = None

    # For CONTENT_BLOCK_START
    content_block: Optional[IRContentBlock] = None

    # For CONTENT_BLOCK_DELTA
    delta_type: Optional[str] = None  # text, input_json, thinking
    delta_text: Optional[str] = None
    delta_json: Optional[str] = None  # Partial JSON for tool arguments

    # For MESSAGE_DELTA
    stop_reason: Optional[StopReason] = None
    stop_sequence: Optional[str] = None
    usage: Optional[IRUsage] = None

    # For ERROR
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Raw data for passthrough
    raw_data: Optional[Dict[str, Any]] = None
