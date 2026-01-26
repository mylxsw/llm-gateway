#!/usr/bin/env python3
"""
Tool Calling Conversion Examples

Demonstrates converting tool/function calling requests and responses between protocols.
"""

import json
import sys
sys.path.insert(0, "/home/user/playground")

from api_protocol_converter import (
    openai_chat_to_anthropic_messages_request,
    openai_chat_to_anthropic_messages_response,
    anthropic_messages_to_openai_chat_request,
    anthropic_messages_to_openai_chat_response,
    openai_chat_to_openai_responses_request,
    openai_chat_to_openai_responses_response,
)


def print_json(title: str, data: dict) -> None:
    """Pretty print JSON data with a title."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)
    print(json.dumps(data, indent=2))


def example_openai_tools_to_anthropic():
    """Convert OpenAI Chat with tools to Anthropic format."""
    print("\n" + "#"*70)
    print("# OpenAI Chat (with tools) -> Anthropic Messages")
    print("#"*70)

    # OpenAI Chat request with tool definitions
    openai_request = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "What's the weather like in Paris and London?"}
        ],
        "max_tokens": 200,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "The city name"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "Temperature unit"
                            }
                        },
                        "required": ["city"]
                    }
                }
            }
        ],
        "tool_choice": "auto"
    }
    print_json("OpenAI Chat Request (with tools)", openai_request)

    # Convert to Anthropic
    anthropic_request = openai_chat_to_anthropic_messages_request(openai_request)
    print_json("Anthropic Messages Request (converted)", anthropic_request)

    # Note the differences:
    # - OpenAI: tools[].function.{name, parameters}
    # - Anthropic: tools[].{name, input_schema}


def example_tool_call_response_conversion():
    """Convert tool call responses between protocols."""
    print("\n" + "#"*70)
    print("# Tool Call Response Conversion")
    print("#"*70)

    # OpenAI response with tool call
    openai_response = {
        "id": "chatcmpl-tool123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [{
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
                            "arguments": '{"city": "Paris", "unit": "celsius"}'
                        }
                    },
                    {
                        "id": "call_def456",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "London", "unit": "celsius"}'
                        }
                    }
                ]
            },
            "finish_reason": "tool_calls"
        }],
        "usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120}
    }
    print_json("OpenAI Chat Response (with tool calls)", openai_response)

    # Convert to Anthropic
    anthropic_response = openai_chat_to_anthropic_messages_response(openai_response)
    print_json("Anthropic Messages Response (converted)", anthropic_response)

    # Key differences:
    # - OpenAI: tool_calls[].function.arguments (JSON string)
    # - Anthropic: content[].input (parsed object)
    # - OpenAI: finish_reason = "tool_calls"
    # - Anthropic: stop_reason = "tool_use"


def example_tool_result_conversation():
    """Convert a full tool-calling conversation."""
    print("\n" + "#"*70)
    print("# Full Tool Calling Conversation")
    print("#"*70)

    # OpenAI conversation with tool result
    openai_request = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "What's the weather in Tokyo?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_xyz789",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "Tokyo", "unit": "celsius"}'
                    }
                }]
            },
            {
                "role": "tool",
                "tool_call_id": "call_xyz789",
                "content": '{"temperature": 18, "condition": "partly cloudy", "humidity": 65}'
            }
        ],
        "max_tokens": 200,
        "tools": [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather data",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}, "unit": {"type": "string"}},
                    "required": ["city"]
                }
            }
        }]
    }
    print_json("OpenAI Chat Request (with tool result)", openai_request)

    # Convert to Anthropic
    anthropic_request = openai_chat_to_anthropic_messages_request(openai_request)
    print_json("Anthropic Messages Request (converted)", anthropic_request)

    # Key differences in tool results:
    # - OpenAI: Separate message with role="tool" and tool_call_id
    # - Anthropic: Content block with type="tool_result" and tool_use_id


def example_openai_to_responses_tools():
    """Convert OpenAI Chat tools to OpenAI Responses format."""
    print("\n" + "#"*70)
    print("# OpenAI Chat -> OpenAI Responses (tool format)")
    print("#"*70)

    openai_chat_request = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Search for restaurants nearby"}
        ],
        "max_tokens": 100,
        "tools": [{
            "type": "function",
            "function": {
                "name": "search_places",
                "description": "Search for places near a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "location": {"type": "string"}
                    },
                    "required": ["query"]
                }
            }
        }]
    }
    print_json("OpenAI Chat Request", openai_chat_request)

    # Convert to Responses API
    responses_request = openai_chat_to_openai_responses_request(openai_chat_request)
    print_json("OpenAI Responses Request", responses_request)

    # Key difference:
    # - Chat: tools[].function.{name, parameters}
    # - Responses: tools[].{name, parameters} (no nested function key)


if __name__ == "__main__":
    example_openai_tools_to_anthropic()
    example_tool_call_response_conversion()
    example_tool_result_conversation()
    example_openai_to_responses_tools()
