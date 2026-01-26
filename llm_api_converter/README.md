# API Protocol Converter SDK

A Python library for converting between OpenAI and Anthropic API protocols. Supports all 6 conversion directions for requests, responses, and streaming.

## Supported Protocols

| Protocol | Endpoint | Description |
|----------|----------|-------------|
| OpenAI Classic | `/v1/chat/completions` | OpenAI Chat Completions API |
| OpenAI Responses | `/v1/responses` | OpenAI Responses API (newer) |
| Anthropic Messages | `/v1/messages` | Anthropic Claude API |

## Features

- **6-way Protocol Conversion**: Convert between any two of the three protocols
- **Request Conversion**: Transform API requests between formats
- **Response Conversion**: Transform API responses between formats
- **Stream Conversion**: Convert streaming events in real-time
- **Tool/Function Calling**: Full support for tool definitions and tool calls
- **Multimodal Support**: Images, documents, and other content types
- **Type Safety**: Full type hints with TypedDict schemas

## Installation

```bash
pip install api-protocol-converter
```

Or install from source:

```bash
git clone https://github.com/example/api-protocol-converter.git
cd api-protocol-converter
pip install -e .
```

## Quick Start

### Basic Request Conversion

```python
from api_protocol_converter import (
    openai_chat_to_anthropic_messages_request,
    anthropic_messages_to_openai_chat_request,
)

# Convert OpenAI Chat request to Anthropic
openai_request = {
    "model": "gpt-4o",
    "messages": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100
}

anthropic_request = openai_chat_to_anthropic_messages_request(openai_request)
# Result:
# {
#     "model": "gpt-4o",
#     "messages": [{"role": "user", "content": "Hello!"}],
#     "system": "You are helpful.",
#     "max_tokens": 100
# }
```

### Generic Converter

```python
from api_protocol_converter import convert_request, convert_response, Protocol

# Using string protocol names
result = convert_request("openai_chat", "anthropic_messages", request)

# Using Protocol enum
result = convert_request(
    Protocol.OPENAI_CHAT,
    Protocol.ANTHROPIC_MESSAGES,
    request
)
```

### Response Conversion

```python
from api_protocol_converter import openai_chat_to_anthropic_messages_response

openai_response = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "choices": [{
        "message": {"role": "assistant", "content": "Hello!"},
        "finish_reason": "stop"
    }],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
}

anthropic_response = openai_chat_to_anthropic_messages_response(openai_response)
# Result:
# {
#     "id": "msg_abc123",
#     "type": "message",
#     "role": "assistant",
#     "content": [{"type": "text", "text": "Hello!"}],
#     "stop_reason": "end_turn",
#     "usage": {"input_tokens": 10, "output_tokens": 5}
# }
```

### Stream Conversion

```python
from api_protocol_converter import convert_stream, Protocol

# Convert OpenAI stream to Anthropic stream
anthropic_events = convert_stream(
    Protocol.OPENAI_CHAT,
    Protocol.ANTHROPIC_MESSAGES,
    openai_stream_iterator
)

for event in anthropic_events:
    print(event)
```

### Tool Calling

```python
from api_protocol_converter import openai_chat_to_anthropic_messages_request

# OpenAI tool format
openai_request = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Weather in Paris?"}],
    "max_tokens": 100,
    "tools": [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}
        }
    }]
}

# Converts to Anthropic format (input_schema instead of parameters)
anthropic_request = openai_chat_to_anthropic_messages_request(openai_request)
```

## API Reference

### Conversion Functions

All conversion functions follow the pattern:
- `{source}_to_{target}_request()` - Convert requests
- `{source}_to_{target}_response()` - Convert responses
- `{source}_to_{target}_stream()` - Convert streams

Available functions:
- `openai_chat_to_openai_responses_*`
- `openai_chat_to_anthropic_messages_*`
- `openai_responses_to_openai_chat_*`
- `openai_responses_to_anthropic_messages_*`
- `anthropic_messages_to_openai_chat_*`
- `anthropic_messages_to_openai_responses_*`

### Generic Functions

```python
convert_request(source_protocol, target_protocol, payload, *, stream=False, options=None)
convert_response(source_protocol, target_protocol, payload, *, options=None)
convert_stream(source_protocol, target_protocol, events_iter, *, options=None)
```

### Protocols

```python
from api_protocol_converter import Protocol

Protocol.OPENAI_CHAT        # OpenAI Chat Completions
Protocol.OPENAI_RESPONSES   # OpenAI Responses API
Protocol.ANTHROPIC_MESSAGES # Anthropic Messages API
```

## Architecture

The SDK uses an Intermediate Representation (IR) architecture:

```
Source Protocol → IR → Target Protocol
```

This design:
- Reduces complexity from O(n²) to O(n) converters
- Makes adding new protocols easier
- Ensures consistent behavior across all conversions

### IR Types

- `IRRequest` - Unified request representation
- `IRResponse` - Unified response representation
- `IRMessage` - Message with role and content blocks
- `IRContentBlock` - Text, image, tool_use, tool_result, etc.
- `IRToolDeclaration` - Tool/function definition
- `IRStreamEvent` - Streaming event

## Field Mapping

Key differences handled by the converter:

| Aspect | OpenAI Chat | OpenAI Responses | Anthropic |
|--------|-------------|------------------|-----------|
| System prompt | In messages | `instructions` | `system` param |
| Max tokens | `max_tokens` | `max_output_tokens` | `max_tokens` |
| Tools | `tools[].function.*` | `tools[].*` | `tools[].input_schema` |
| Tool calls | `tool_calls[]` | `function_call` items | `tool_use` blocks |
| Stop reason | `finish_reason` | `status` | `stop_reason` |

See [docs/PROTOCOL_COMPARISON.md](docs/PROTOCOL_COMPARISON.md) for complete mapping.

## Limitations

- **Temperature range**: Anthropic uses 0-1, OpenAI uses 0-2 (values are clamped)
- **Unsupported features**: Some protocol-specific features have no equivalent
- **Audio/Video**: Limited support for audio content (OpenAI only)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy api_protocol_converter

# Format code
black api_protocol_converter tests
isort api_protocol_converter tests
```

## License

MIT License - see [LICENSE](LICENSE) for details.
