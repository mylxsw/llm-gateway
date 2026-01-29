#!/usr/bin/env python3
"""
Basic Conversion Examples

Demonstrates simple request and response conversion between all protocols.
"""

import json
import sys
sys.path.insert(0, "/home/user/playground")

from api_protocol_converter import (
    convert_request,
    convert_response,
    Protocol,
    # Direct conversion functions
    openai_chat_to_anthropic_messages_request,
    openai_chat_to_anthropic_messages_response,
    anthropic_messages_to_openai_chat_request,
    anthropic_messages_to_openai_chat_response,
)


def print_json(title: str, data: dict) -> None:
    """Pretty print JSON data with a title."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)
    print(json.dumps(data, indent=2))


def example_openai_to_anthropic():
    """Convert OpenAI Chat request/response to Anthropic format."""
    print("\n" + "#"*70)
    print("# OpenAI Chat -> Anthropic Messages")
    print("#"*70)

    # Sample OpenAI Chat request
    openai_request = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ],
        "max_tokens": 100,
        "temperature": 0.7,
    }
    print_json("Original OpenAI Chat Request", openai_request)

    # Convert to Anthropic format
    anthropic_request = openai_chat_to_anthropic_messages_request(openai_request)
    print_json("Converted Anthropic Messages Request", anthropic_request)

    # Sample OpenAI response
    openai_response = {
        "id": "chatcmpl-abc123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "The capital of France is Paris.",
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 25,
            "completion_tokens": 10,
            "total_tokens": 35,
        },
    }
    print_json("Original OpenAI Chat Response", openai_response)

    # Convert response
    anthropic_response = openai_chat_to_anthropic_messages_response(openai_response)
    print_json("Converted Anthropic Messages Response", anthropic_response)


def example_anthropic_to_openai():
    """Convert Anthropic request/response to OpenAI Chat format."""
    print("\n" + "#"*70)
    print("# Anthropic Messages -> OpenAI Chat")
    print("#"*70)

    # Sample Anthropic request
    anthropic_request = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "user", "content": "Explain quantum computing in simple terms."},
        ],
        "system": "You are a science educator who explains complex topics simply.",
        "max_tokens": 200,
        "temperature": 0.8,
    }
    print_json("Original Anthropic Messages Request", anthropic_request)

    # Convert to OpenAI format
    openai_request = anthropic_messages_to_openai_chat_request(anthropic_request)
    print_json("Converted OpenAI Chat Request", openai_request)

    # Sample Anthropic response
    anthropic_response = {
        "id": "msg_abc123",
        "type": "message",
        "role": "assistant",
        "model": "claude-3-5-sonnet-20241022",
        "content": [
            {
                "type": "text",
                "text": "Quantum computing uses quantum mechanics principles to process information in a fundamentally different way than classical computers.",
            }
        ],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 30,
            "output_tokens": 25,
        },
    }
    print_json("Original Anthropic Messages Response", anthropic_response)

    # Convert response
    openai_response = anthropic_messages_to_openai_chat_response(anthropic_response)
    print_json("Converted OpenAI Chat Response", openai_response)


def example_generic_converter():
    """Use the generic convert_request/convert_response functions."""
    print("\n" + "#"*70)
    print("# Using Generic Converters")
    print("#"*70)

    request = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello, world!"}
        ],
        "max_tokens": 50,
    }

    # Convert using string protocol names
    result = convert_request("openai_chat", "anthropic_messages", request)
    print_json("Converted using string protocol names", result)

    # Convert using Protocol enum
    result = convert_request(
        Protocol.OPENAI_CHAT,
        Protocol.OPENAI_RESPONSES,
        request
    )
    print_json("Converted to OpenAI Responses format", result)


if __name__ == "__main__":
    example_openai_to_anthropic()
    example_anthropic_to_openai()
    example_generic_converter()
