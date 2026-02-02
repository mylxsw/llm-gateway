"""
Test Fixtures

Sample payloads for testing protocol conversions.
"""

# =============================================================================
# OpenAI Chat Completions (Classic) Fixtures
# =============================================================================

OPENAI_CHAT_SIMPLE_REQUEST = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "max_tokens": 100,
}

OPENAI_CHAT_WITH_SYSTEM_REQUEST = {
    "model": "gpt-4o",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
    ],
    "max_tokens": 100,
    "temperature": 0.7,
}

OPENAI_CHAT_MULTIMODAL_REQUEST = {
    "model": "gpt-4o",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://example.com/image.jpg",
                        "detail": "auto",
                    },
                },
            ],
        }
    ],
    "max_tokens": 500,
}

OPENAI_CHAT_WITH_TOOLS_REQUEST = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "What's the weather in Paris?"}],
    "max_tokens": 200,
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    ],
    "tool_choice": "auto",
}

OPENAI_CHAT_TOOL_RESULT_REQUEST = {
    "model": "gpt-4o",
    "messages": [
        {"role": "user", "content": "What's the weather in Paris?"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Paris", "unit": "celsius"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "content": '{"temperature": 22, "condition": "sunny"}',
        },
    ],
    "max_tokens": 200,
}

OPENAI_CHAT_SIMPLE_RESPONSE = {
    "id": "chatcmpl-abc123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! I'm doing great, thank you for asking.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25,
    },
}

OPENAI_CHAT_TOOL_CALL_RESPONSE = {
    "id": "chatcmpl-xyz789",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Paris", "unit": "celsius"}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 30,
        "total_tokens": 80,
    },
}

# OpenAI tool call response with incorrect finish_reason (some providers return "stop" instead of "tool_calls")
OPENAI_CHAT_TOOL_CALL_RESPONSE_WRONG_FINISH_REASON = {
    "id": "chatcmpl-wrong123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-5-nano-2025-08-07",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_wrong456",
                        "type": "function",
                        "function": {
                            "name": "get_server_status",
                            "arguments": '{"server": "prod-1"}',
                        },
                    }
                ],
            },
            "finish_reason": "stop",  # Wrong! Should be "tool_calls"
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 42,
        "total_tokens": 142,
    },
}

# Streaming chunks
OPENAI_CHAT_STREAM_CHUNKS = [
    {
        "id": "chatcmpl-stream1",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }
        ],
    },
    {
        "id": "chatcmpl-stream1",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}],
    },
    {
        "id": "chatcmpl-stream1",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {"index": 0, "delta": {"content": " there!"}, "finish_reason": None}
        ],
    },
    {
        "id": "chatcmpl-stream1",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    },
]

# =============================================================================
# OpenAI Responses API Fixtures
# =============================================================================

OPENAI_RESPONSES_SIMPLE_REQUEST = {
    "model": "gpt-4o",
    "input": "Hello, how are you?",
    "max_output_tokens": 100,
}

OPENAI_RESPONSES_WITH_INSTRUCTIONS_REQUEST = {
    "model": "gpt-4o",
    "input": "What is 2+2?",
    "instructions": "You are a helpful assistant.",
    "max_output_tokens": 100,
    "temperature": 0.7,
}

OPENAI_RESPONSES_WITH_TOOLS_REQUEST = {
    "model": "gpt-4o",
    "input": [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "text", "text": "What's the weather in Paris?"}],
        }
    ],
    "max_output_tokens": 200,
    "tools": [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        }
    ],
}

OPENAI_RESPONSES_SIMPLE_RESPONSE = {
    "id": "resp_abc123",
    "object": "response",
    "created_at": 1700000000,
    "model": "gpt-4o",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "Hello! I'm doing great, thank you for asking.",
                }
            ],
        }
    ],
    "status": "completed",
    "usage": {
        "input_tokens": 10,
        "output_tokens": 15,
        "total_tokens": 25,
    },
}

OPENAI_RESPONSES_TOOL_CALL_RESPONSE = {
    "id": "resp_xyz789",
    "object": "response",
    "created_at": 1700000000,
    "model": "gpt-4o",
    "output": [
        {
            "type": "function_call",
            "id": "fc_abc123",
            "call_id": "call_abc123",
            "name": "get_weather",
            "arguments": '{"location": "Paris", "unit": "celsius"}',
            "status": "completed",
        }
    ],
    "status": "completed",
    "usage": {
        "input_tokens": 50,
        "output_tokens": 30,
        "total_tokens": 80,
    },
}

# =============================================================================
# Anthropic Messages API Fixtures
# =============================================================================

ANTHROPIC_SIMPLE_REQUEST = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "max_tokens": 100,
}

ANTHROPIC_WITH_SYSTEM_REQUEST = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {"role": "user", "content": "What is 2+2?"},
    ],
    "system": "You are a helpful assistant.",
    "max_tokens": 100,
    "temperature": 0.7,
}

ANTHROPIC_MULTIMODAL_REQUEST = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": "https://example.com/image.jpg",
                    },
                },
            ],
        }
    ],
    "max_tokens": 500,
}

ANTHROPIC_WITH_TOOLS_REQUEST = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "What's the weather in Paris?"}],
    "max_tokens": 200,
    "tools": [
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        }
    ],
    "tool_choice": {"type": "auto"},
}

ANTHROPIC_TOOL_RESULT_REQUEST = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {"role": "user", "content": "What's the weather in Paris?"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_abc123",
                    "name": "get_weather",
                    "input": {"location": "Paris", "unit": "celsius"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_abc123",
                    "content": '{"temperature": 22, "condition": "sunny"}',
                }
            ],
        },
    ],
    "max_tokens": 200,
}

ANTHROPIC_SIMPLE_RESPONSE = {
    "id": "msg_abc123",
    "type": "message",
    "role": "assistant",
    "model": "claude-3-5-sonnet-20241022",
    "content": [
        {"type": "text", "text": "Hello! I'm doing great, thank you for asking."}
    ],
    "stop_reason": "end_turn",
    "usage": {
        "input_tokens": 10,
        "output_tokens": 15,
    },
}

ANTHROPIC_TOOL_USE_RESPONSE = {
    "id": "msg_xyz789",
    "type": "message",
    "role": "assistant",
    "model": "claude-3-5-sonnet-20241022",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_abc123",
            "name": "get_weather",
            "input": {"location": "Paris", "unit": "celsius"},
        }
    ],
    "stop_reason": "tool_use",
    "usage": {
        "input_tokens": 50,
        "output_tokens": 30,
    },
}

# Streaming events
ANTHROPIC_STREAM_EVENTS = [
    {
        "type": "message_start",
        "message": {
            "id": "msg_stream1",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 0},
        },
    },
    {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": "Hello"},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": " there!"},
    },
    {
        "type": "content_block_stop",
        "index": 0,
    },
    {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 5},
    },
    {
        "type": "message_stop",
    },
]

# =============================================================================
# Error Response Fixtures
# =============================================================================

OPENAI_ERROR_RESPONSE = {
    "error": {
        "message": "Invalid API key provided",
        "type": "authentication_error",
        "code": "invalid_api_key",
    }
}

ANTHROPIC_ERROR_RESPONSE = {
    "type": "error",
    "error": {
        "type": "authentication_error",
        "message": "Invalid API key provided",
    },
}

# =============================================================================
# Complex/Edge Case Fixtures
# =============================================================================

OPENAI_CHAT_MULTI_TOOL_CALLS_RESPONSE = {
    "id": "chatcmpl-multi",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Paris"}',
                        },
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "London"}',
                        },
                    },
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
}

ANTHROPIC_MULTI_TOOL_USE_RESPONSE = {
    "id": "msg_multi",
    "type": "message",
    "role": "assistant",
    "model": "claude-3-5-sonnet-20241022",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "get_weather",
            "input": {"location": "Paris"},
        },
        {
            "type": "tool_use",
            "id": "toolu_2",
            "name": "get_weather",
            "input": {"location": "London"},
        },
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 100, "output_tokens": 50},
}

# OpenAI Responses API with input_text and input_image content types
OPENAI_RESPONSES_MULTIMODAL_REQUEST = {
    "model": "gpt-4o",
    "input": [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": "What is in this image?"},
                {
                    "type": "input_image",
                    "image_url": "https://example.com/image.jpg",
                },
            ],
        }
    ],
    "max_output_tokens": 500,
}

# Streaming chunks: multiple tool calls WITHOUT index field (e.g., Google Gemini OpenAI-compat)
OPENAI_CHAT_STREAM_MULTI_TOOL_NO_INDEX = [
    # Chunk 1: role + first tool call (complete arguments in one chunk, no index field)
    {
        "id": "zCZ-aeCNCLDDjuMPrMTawQY",
        "object": "chat.completion.chunk",
        "created": 1769875148,
        "model": "gemini-3-pro-preview",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": '{"path":"IDENTITY.md","content":"# Identity"}',
                                "name": "write",
                            },
                            "id": "function-call-1111",
                            "type": "function",
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
    },
    # Chunk 2: second tool call (different id, no index field)
    {
        "id": "zCZ-aeCNCLDDjuMPrMTawQY",
        "object": "chat.completion.chunk",
        "created": 1769875149,
        "model": "gemini-3-pro-preview",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": '{"path":"USER.md","content":"# User"}',
                                "name": "write",
                            },
                            "id": "function-call-2222",
                            "type": "function",
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
    },
    # Chunk 3: finish
    {
        "id": "zCZ-aeCNCLDDjuMPrMTawQY",
        "object": "chat.completion.chunk",
        "created": 1769875149,
        "model": "gemini-3-pro-preview",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": "stop",
            }
        ],
    },
]

# Streaming chunks: standard OpenAI multi-tool with index fields
OPENAI_CHAT_STREAM_MULTI_TOOL_WITH_INDEX = [
    # Chunk 1: role + first tool call start
    {
        "id": "chatcmpl-toolstream",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_aaa",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location":',
                            },
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
    },
    # Chunk 2: first tool call arguments continuation
    {
        "id": "chatcmpl-toolstream",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"arguments": '"Paris"}'},
                        }
                    ]
                },
                "finish_reason": None,
            }
        ],
    },
    # Chunk 3: second tool call start
    {
        "id": "chatcmpl-toolstream",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 1,
                            "id": "call_bbb",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location":"London"}',
                            },
                        }
                    ]
                },
                "finish_reason": None,
            }
        ],
    },
    # Chunk 4: finish
    {
        "id": "chatcmpl-toolstream",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
    },
]

# Streaming chunks: OpenAI Responses multi-tool stream WITHOUT output_index fields
OPENAI_RESPONSES_STREAM_MULTI_TOOL_NO_INDEX = [
    # Stream creation event
    {
        "type": "response.created",
        "response": {
            "id": "resp_123",
            "model": "gpt-4.1-mini",
            "created_at": 1700000000,
        },
    },
    # First function_call output item, provider omits output_index
    {
        "type": "response.output_item.added",
        "item": {
            "id": "item_1",
            "type": "function_call",
            "name": "write",
            "call_id": "call_1",
            "arguments": '{"path":"IDENTITY.md"}',
        },
    },
    # Second function_call output item, also missing output_index
    {
        "type": "response.output_item.added",
        "item": {
            "id": "item_2",
            "type": "function_call",
            "name": "write",
            "call_id": "call_2",
            "arguments": '{"path":"USER.md"}',
        },
    },
    # Argument deltas for each tool call
    {
        "type": "response.function_call_arguments.delta",
        "delta": '{"path":"IDENTITY.md"}',
        "call_id": "call_1",
    },
    {
        "type": "response.function_call_arguments.delta",
        "delta": '{"path":"USER.md"}',
        "call_id": "call_2",
    },
    # Finish each output item
    {"type": "response.output_item.done", "call_id": "call_1"},
    {"type": "response.output_item.done", "call_id": "call_2"},
    # Stream done
    {
        "type": "response.done",
        "response": {
            "status": "completed",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
    },
]

OPENAI_CHAT_WITH_BASE64_IMAGE_REQUEST = {
    "model": "gpt-4o",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                    },
                },
            ],
        }
    ],
    "max_tokens": 100,
}

ANTHROPIC_WITH_BASE64_IMAGE_REQUEST = {
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                    },
                },
            ],
        }
    ],
    "max_tokens": 100,
}
