"""
Protocol Schemas Module

Defines TypedDict schemas for each protocol's request and response structures.
These provide type hints and validation for protocol-specific payloads.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union


class Protocol(str, Enum):
    """Supported API protocols."""
    OPENAI_CHAT = "openai_chat"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC_MESSAGES = "anthropic_messages"


# =============================================================================
# OpenAI Chat Completions (Classic) Types
# =============================================================================

class OpenAIChatFunctionDef(TypedDict, total=False):
    """OpenAI function definition within a tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    strict: bool


class OpenAIChatTool(TypedDict, total=False):
    """OpenAI Chat tool definition."""
    type: Literal["function"]
    function: OpenAIChatFunctionDef


class OpenAIChatTextContent(TypedDict):
    """Text content block."""
    type: Literal["text"]
    text: str


class OpenAIChatImageUrl(TypedDict, total=False):
    """Image URL structure."""
    url: str
    detail: str  # "auto", "low", "high"


class OpenAIChatImageContent(TypedDict):
    """Image content block."""
    type: Literal["image_url"]
    image_url: Union[str, OpenAIChatImageUrl]


class OpenAIChatAudioContent(TypedDict, total=False):
    """Audio content block."""
    type: Literal["input_audio"]
    input_audio: Dict[str, Any]


OpenAIChatContentBlock = Union[
    str,
    OpenAIChatTextContent,
    OpenAIChatImageContent,
    OpenAIChatAudioContent,
]


class OpenAIChatFunctionCall(TypedDict):
    """Function call in a tool call."""
    name: str
    arguments: str  # JSON string


class OpenAIChatToolCall(TypedDict, total=False):
    """Tool call from assistant."""
    id: str
    type: Literal["function"]
    function: OpenAIChatFunctionCall


class OpenAIChatMessage(TypedDict, total=False):
    """OpenAI Chat message."""
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: Union[str, List[OpenAIChatContentBlock], None]
    name: str
    tool_calls: List[OpenAIChatToolCall]
    tool_call_id: str  # For tool role


class OpenAIChatResponseFormat(TypedDict, total=False):
    """Response format configuration."""
    type: Literal["text", "json_object", "json_schema"]
    json_schema: Dict[str, Any]


class OpenAIChatStreamOptions(TypedDict, total=False):
    """Stream options."""
    include_usage: bool


class OpenAIChatRequest(TypedDict, total=False):
    """OpenAI Chat Completions API request."""
    model: str
    messages: List[OpenAIChatMessage]
    max_tokens: int
    max_completion_tokens: int
    temperature: float
    top_p: float
    n: int
    stream: bool
    stream_options: OpenAIChatStreamOptions
    stop: Union[str, List[str]]
    presence_penalty: float
    frequency_penalty: float
    logprobs: bool
    top_logprobs: int
    seed: int
    user: str
    tools: List[OpenAIChatTool]
    tool_choice: Union[str, Dict[str, Any]]
    parallel_tool_calls: bool
    response_format: OpenAIChatResponseFormat
    store: bool


class OpenAIChatUsageDetails(TypedDict, total=False):
    """Detailed token usage."""
    cached_tokens: int
    reasoning_tokens: int
    audio_tokens: int


class OpenAIChatUsage(TypedDict, total=False):
    """Token usage in response."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_details: OpenAIChatUsageDetails
    completion_tokens_details: OpenAIChatUsageDetails


class OpenAIChatChoiceMessage(TypedDict, total=False):
    """Message in a choice."""
    role: Literal["assistant"]
    content: Optional[str]
    tool_calls: List[OpenAIChatToolCall]
    refusal: Optional[str]


class OpenAIChatChoice(TypedDict, total=False):
    """Choice in response."""
    index: int
    message: OpenAIChatChoiceMessage
    finish_reason: Literal["stop", "length", "tool_calls", "content_filter"]
    logprobs: Optional[Dict[str, Any]]


class OpenAIChatResponse(TypedDict, total=False):
    """OpenAI Chat Completions API response."""
    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: List[OpenAIChatChoice]
    usage: OpenAIChatUsage
    system_fingerprint: str


# Streaming types
class OpenAIChatChunkDelta(TypedDict, total=False):
    """Delta in a streaming chunk."""
    role: str
    content: str
    tool_calls: List[Dict[str, Any]]
    refusal: str


class OpenAIChatChunkChoice(TypedDict, total=False):
    """Choice in a streaming chunk."""
    index: int
    delta: OpenAIChatChunkDelta
    finish_reason: Optional[str]
    logprobs: Optional[Dict[str, Any]]


class OpenAIChatChunk(TypedDict, total=False):
    """Streaming chunk."""
    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    choices: List[OpenAIChatChunkChoice]
    usage: OpenAIChatUsage
    system_fingerprint: str


# =============================================================================
# OpenAI Responses API Types
# =============================================================================

class OpenAIResponsesTool(TypedDict, total=False):
    """OpenAI Responses tool definition."""
    type: Literal["function", "web_search", "file_search", "code_interpreter"]
    name: str
    description: str
    parameters: Dict[str, Any]
    strict: bool


class OpenAIResponsesTextFormat(TypedDict, total=False):
    """Text format configuration."""
    type: Literal["text", "json_object", "json_schema"]
    json_schema: Dict[str, Any]


class OpenAIResponsesText(TypedDict, total=False):
    """Text output configuration."""
    format: OpenAIResponsesTextFormat


class OpenAIResponsesRequest(TypedDict, total=False):
    """OpenAI Responses API request."""
    model: str
    input: Union[str, List[Dict[str, Any]]]
    instructions: str
    max_output_tokens: int
    temperature: float
    top_p: float
    stream: bool
    stop: List[str]
    seed: int
    user: str
    tools: List[OpenAIResponsesTool]
    tool_choice: Dict[str, Any]
    text: OpenAIResponsesText
    store: bool
    previous_response_id: str
    include: List[str]


class OpenAIResponsesOutputItem(TypedDict, total=False):
    """Output item in response."""
    type: str  # message, function_call, function_call_output, etc.
    id: str
    status: str
    role: str
    content: List[Dict[str, Any]]
    # For function_call
    call_id: str
    name: str
    arguments: str
    # For function_call_output
    output: str


class OpenAIResponsesUsage(TypedDict, total=False):
    """Token usage in response."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_tokens_details: Dict[str, Any]
    output_tokens_details: Dict[str, Any]


class OpenAIResponsesResponse(TypedDict, total=False):
    """OpenAI Responses API response."""
    id: str
    object: Literal["response"]
    created_at: int
    model: str
    output: List[OpenAIResponsesOutputItem]
    status: str
    usage: OpenAIResponsesUsage
    metadata: Dict[str, Any]


# =============================================================================
# Anthropic Messages API Types
# =============================================================================

class AnthropicTool(TypedDict, total=False):
    """Anthropic tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    cache_control: Dict[str, Any]


class AnthropicToolChoice(TypedDict, total=False):
    """Anthropic tool choice configuration."""
    type: Literal["auto", "any", "tool", "none"]
    name: str
    disable_parallel_tool_use: bool


class AnthropicTextBlock(TypedDict):
    """Text content block."""
    type: Literal["text"]
    text: str


class AnthropicImageSource(TypedDict, total=False):
    """Image source."""
    type: Literal["base64", "url"]
    media_type: str
    data: str
    url: str


class AnthropicImageBlock(TypedDict):
    """Image content block."""
    type: Literal["image"]
    source: AnthropicImageSource


class AnthropicDocumentSource(TypedDict, total=False):
    """Document source."""
    type: Literal["base64", "url", "text"]
    media_type: str
    data: str
    url: str


class AnthropicDocumentBlock(TypedDict, total=False):
    """Document content block."""
    type: Literal["document"]
    source: AnthropicDocumentSource
    title: str
    context: str


class AnthropicToolUseBlock(TypedDict):
    """Tool use content block."""
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]


class AnthropicToolResultContent(TypedDict, total=False):
    """Content within tool result."""
    type: Literal["text", "image"]
    text: str
    source: AnthropicImageSource


class AnthropicToolResultBlock(TypedDict, total=False):
    """Tool result content block."""
    type: Literal["tool_result"]
    tool_use_id: str
    content: Union[str, List[AnthropicToolResultContent]]
    is_error: bool


class AnthropicThinkingBlock(TypedDict, total=False):
    """Thinking content block."""
    type: Literal["thinking"]
    thinking: str
    signature: str


AnthropicContentBlock = Union[
    AnthropicTextBlock,
    AnthropicImageBlock,
    AnthropicDocumentBlock,
    AnthropicToolUseBlock,
    AnthropicToolResultBlock,
    AnthropicThinkingBlock,
]


class AnthropicMessage(TypedDict, total=False):
    """Anthropic message."""
    role: Literal["user", "assistant"]
    content: Union[str, List[AnthropicContentBlock]]


class AnthropicThinkingConfig(TypedDict, total=False):
    """Thinking configuration."""
    type: Literal["enabled", "disabled"]
    budget_tokens: int


class AnthropicMetadata(TypedDict, total=False):
    """Request metadata."""
    user_id: str


class AnthropicRequest(TypedDict, total=False):
    """Anthropic Messages API request."""
    model: str
    messages: List[AnthropicMessage]
    max_tokens: int
    system: Union[str, List[AnthropicTextBlock]]
    temperature: float
    top_p: float
    top_k: int
    stop_sequences: List[str]
    stream: bool
    tools: List[AnthropicTool]
    tool_choice: AnthropicToolChoice
    thinking: AnthropicThinkingConfig
    metadata: AnthropicMetadata


class AnthropicUsage(TypedDict, total=False):
    """Token usage in response."""
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


class AnthropicResponse(TypedDict, total=False):
    """Anthropic Messages API response."""
    id: str
    type: Literal["message"]
    role: Literal["assistant"]
    model: str
    content: List[AnthropicContentBlock]
    stop_reason: Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]
    stop_sequence: Optional[str]
    usage: AnthropicUsage


# Streaming types
class AnthropicStreamEvent(TypedDict, total=False):
    """Base stream event."""
    type: str


class AnthropicMessageStartEvent(TypedDict):
    """Message start event."""
    type: Literal["message_start"]
    message: AnthropicResponse


class AnthropicContentBlockStartEvent(TypedDict):
    """Content block start event."""
    type: Literal["content_block_start"]
    index: int
    content_block: AnthropicContentBlock


class AnthropicTextDelta(TypedDict):
    """Text delta."""
    type: Literal["text_delta"]
    text: str


class AnthropicInputJsonDelta(TypedDict):
    """Input JSON delta for tool use."""
    type: Literal["input_json_delta"]
    partial_json: str


class AnthropicThinkingDelta(TypedDict):
    """Thinking delta."""
    type: Literal["thinking_delta"]
    thinking: str


AnthropicDelta = Union[AnthropicTextDelta, AnthropicInputJsonDelta, AnthropicThinkingDelta]


class AnthropicContentBlockDeltaEvent(TypedDict):
    """Content block delta event."""
    type: Literal["content_block_delta"]
    index: int
    delta: AnthropicDelta


class AnthropicContentBlockStopEvent(TypedDict):
    """Content block stop event."""
    type: Literal["content_block_stop"]
    index: int


class AnthropicMessageDeltaUsage(TypedDict, total=False):
    """Usage in message delta."""
    output_tokens: int


class AnthropicMessageDeltaContent(TypedDict, total=False):
    """Delta content in message delta."""
    stop_reason: str
    stop_sequence: Optional[str]


class AnthropicMessageDeltaEvent(TypedDict):
    """Message delta event."""
    type: Literal["message_delta"]
    delta: AnthropicMessageDeltaContent
    usage: AnthropicMessageDeltaUsage


class AnthropicMessageStopEvent(TypedDict):
    """Message stop event."""
    type: Literal["message_stop"]


class AnthropicErrorEvent(TypedDict):
    """Error event."""
    type: Literal["error"]
    error: Dict[str, Any]


# =============================================================================
# Error Types
# =============================================================================

class OpenAIError(TypedDict, total=False):
    """OpenAI error structure."""
    error: Dict[str, Any]  # Contains message, type, param, code


class AnthropicError(TypedDict, total=False):
    """Anthropic error structure."""
    type: Literal["error"]
    error: Dict[str, Any]  # Contains type, message


__all__ = [
    "Protocol",
    # OpenAI Chat types
    "OpenAIChatRequest",
    "OpenAIChatResponse",
    "OpenAIChatMessage",
    "OpenAIChatTool",
    "OpenAIChatToolCall",
    "OpenAIChatChunk",
    "OpenAIChatUsage",
    # OpenAI Responses types
    "OpenAIResponsesRequest",
    "OpenAIResponsesResponse",
    "OpenAIResponsesTool",
    "OpenAIResponsesOutputItem",
    "OpenAIResponsesUsage",
    # Anthropic types
    "AnthropicRequest",
    "AnthropicResponse",
    "AnthropicMessage",
    "AnthropicTool",
    "AnthropicToolChoice",
    "AnthropicUsage",
    "AnthropicContentBlock",
    "AnthropicStreamEvent",
    # Error types
    "OpenAIError",
    "AnthropicError",
]
