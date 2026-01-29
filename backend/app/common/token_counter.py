"""
Token Counter Module

Provides Token counting implementations for different protocols (OpenAI, Anthropic).
"""

import base64
import json
import math
from abc import ABC, abstractmethod
from typing import Any, Optional

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class TokenCounter(ABC):
    """
    Token Counter Abstract Base Class

    Defines the standard interface for Token counting, with concrete implementations provided by subclasses.
    """

    @abstractmethod
    def count_tokens(self, text: str, model: str = "") -> int:
        """
        Count tokens in text

        Args:
            text: Text to count
            model: Model name (different models may use different tokenizers)

        Returns:
            int: Token count
        """
        pass

    @abstractmethod
    def count_messages(self, messages: list[dict[str, Any]], model: str = "") -> int:
        """
        Count tokens in a message list

        Args:
            messages: Message list, e.g., [{"role": "user", "content": "Hello"}]
            model: Model name

        Returns:
            int: Token count
        """
        pass

    def count_input(self, input_data: str | list[Any], model: str = "") -> int:
        """
        Count tokens in input (for embeddings)

        Args:
            input_data: Input string or list of strings/tokens
            model: Model name

        Returns:
            int: Token count
        """
        if isinstance(input_data, str):
            return self.count_tokens(input_data, model)

        if isinstance(input_data, list):
            total = 0
            for item in input_data:
                if isinstance(item, str):
                    total += self.count_tokens(item, model)
                elif isinstance(item, dict):
                    text = _extract_text_from_content(item)
                    if text:
                        total += self.count_tokens(text, model)
                    else:
                        total += _count_openai_content(item, model, self)
                elif isinstance(item, list) and all(isinstance(x, int) for x in item):
                    # List of tokens
                    total += len(item)
                elif isinstance(item, int):
                    # Single token? Usually input is list of tokens or list of list of tokens?
                    # OpenAI API: "Token array" -> [1, 2, 3]
                    # "Array of token arrays" -> [[1, 2], [3, 4]]
                    # If input is [1, 2, 3], loop gets 1 (int).
                    # So if item is int, it counts as 1 token.
                    total += 1
            return total

        return 0

    def count_request(self, body: dict[str, Any], model: str = "") -> int:
        """
        Count tokens in a request body (messages/input).
        """
        if not isinstance(body, dict):
            return 0
        if "input" in body:
            input_val = body.get("input")
            # OpenAI Responses API: input can be a list of messages
            if (
                isinstance(input_val, list)
                and input_val
                and isinstance(input_val[0], dict)
                and "role" in input_val[0]
            ):
                return self.count_messages(input_val, model)
            return self.count_input(input_val, model)
        messages = body.get("messages")
        if isinstance(messages, list):
            return self.count_messages(messages, model)
        prompt = body.get("prompt")
        if isinstance(prompt, str):
            return self.count_tokens(prompt, model)
        return 0

    def count_output_body(self, body: Any, model: str = "") -> int:
        """
        Estimate output tokens from a response body when upstream usage is missing.
        """
        if not body:
            return 0
        if isinstance(body, (bytes, bytearray)):
            try:
                body = json.loads(body.decode("utf-8"))
            except Exception:
                return 0
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                return self.count_tokens(body, model)

        if isinstance(body, dict):
            # OpenAI Chat/Completions
            choices = body.get("choices")
            if isinstance(choices, list):
                text_parts: list[str] = []
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    message = choice.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        text_parts.append(_extract_text_from_content(content))
                    text = choice.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
                text = "".join(text_parts)
                return self.count_tokens(text, model)

            # OpenAI Responses API
            output_items = body.get("output")
            if isinstance(output_items, list):
                text_parts = []
                for item in output_items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        text_parts.append(_extract_text_from_content(content))
                text = "".join(text_parts)
                return self.count_tokens(text, model)

            # Anthropic Messages
            content = body.get("content")
            if isinstance(content, list):
                text = _extract_text_from_content(content)
                return self.count_tokens(text, model)

        return 0


class OpenAITokenCounter(TokenCounter):
    """
    OpenAI Token Counter

    Uses tiktoken library for precise Token counting.
    Supports models like GPT-3.5, GPT-4.
    """

    # Default encoding
    DEFAULT_ENCODING = "cl100k_base"

    # Map models to encodings
    MODEL_ENCODING_MAP = {
        "gpt-4": "cl100k_base",
        "gpt-4-32k": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-embedding-ada-002": "cl100k_base",
        "text-davinci-003": "p50k_base",
    }

    def __init__(self):
        """Initialize Counter"""
        self._encodings: dict[str, Any] = {}

    def _get_encoding(self, model: str) -> Any:
        """
        Get encoder for model

        Args:
            model: Model name

        Returns:
            tiktoken encoder instance
        """
        if not TIKTOKEN_AVAILABLE:
            return None

        # Find encoding for model
        encoding_name = self.DEFAULT_ENCODING
        for model_prefix, enc_name in self.MODEL_ENCODING_MAP.items():
            if model.startswith(model_prefix):
                encoding_name = enc_name
                break

        # Cache encoder
        if encoding_name not in self._encodings:
            self._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)

        return self._encodings[encoding_name]

    def count_tokens(self, text: str, model: str = "") -> int:
        """
        Count tokens in text

        Uses tiktoken for precise calculation. If tiktoken is unavailable,
        uses estimation (approx. 4 chars per token).

        Args:
            text: Text to count
            model: Model name

        Returns:
            int: Token count
        """
        if not text:
            return 0

        encoding = self._get_encoding(model)
        if encoding:
            return len(encoding.encode(text))

        # Fallback estimation: average 4 chars per token
        return len(text) // 4

    def count_messages(self, messages: list[dict[str, Any]], model: str = "") -> int:
        """
        Count tokens in a message list

        Calculates based on OpenAI message format, including role and content overhead.

        Args:
            messages: Message list
            model: Model name

        Returns:
            int: Token count
        """
        if not messages:
            return 0

        # Overhead per message
        tokens_per_message = 4  # <|start|>role<|separator|>content<|end|>
        tokens_per_name = -1  # If there's a name field

        total_tokens = 0
        for message in messages:
            total_tokens += tokens_per_message
            for key, value in message.items():
                if key == "content":
                    total_tokens += _count_openai_content(value, model, self)
                    continue
                if key in ("tool_calls", "function_call") and value is not None:
                    try:
                        total_tokens += self.count_tokens(
                            json.dumps(value, ensure_ascii=False), model
                        )
                    except Exception:
                        pass
                    continue
                if isinstance(value, str):
                    total_tokens += self.count_tokens(value, model)
                elif isinstance(value, list):
                    total_tokens += _count_openai_list(value, model, self)
                if key == "name":
                    total_tokens += tokens_per_name

        total_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        return total_tokens

    def count_request(self, body: dict[str, Any], model: str = "") -> int:
        total = super().count_request(body, model)
        tools = body.get("tools")
        if isinstance(tools, list) and tools:
            total += self.count_tokens(json.dumps(tools, ensure_ascii=False), model)
        tool_choice = body.get("tool_choice")
        if tool_choice is not None:
            try:
                total += self.count_tokens(
                    json.dumps(tool_choice, ensure_ascii=False), model
                )
            except Exception:
                pass
        return total


class AnthropicTokenCounter(TokenCounter):
    """
    Anthropic Token Counter

    Anthropic uses its own tokenizer; providing estimation here.
    Ideally, integrate Anthropic's official tokenizer.
    """

    def count_tokens(self, text: str, model: str = "") -> int:
        """
        Count tokens in text

        Uses estimation method. Anthropic's tokenizer is similar to OpenAI's
        but implementation details may differ.

        Args:
            text: Text to count
            model: Model name

        Returns:
            int: Token count (Estimated)
        """
        if not text:
            return 0

        # Estimation: average 4 chars per token
        # TODO: Integrate Anthropic official tokenizer for precise counting
        return len(text) // 4

    def count_messages(self, messages: list[dict[str, Any]], model: str = "") -> int:
        """
        Count tokens in a message list

        Args:
            messages: Message list
            model: Model name

        Returns:
            int: Token count (Estimated)
        """
        if not messages:
            return 0

        total_tokens = 0
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            total_tokens += self.count_tokens(role, model)
            total_tokens += _count_anthropic_content(content, model, self)

            # Message overhead
            total_tokens += 4

        return total_tokens

    def count_request(self, body: dict[str, Any], model: str = "") -> int:
        if not isinstance(body, dict):
            return 0
        messages = body.get("messages")
        if isinstance(messages, list):
            total = self.count_messages(messages, model)
        else:
            total = 0

        system = body.get("system")
        if isinstance(system, str):
            total += self.count_tokens(system, model)
        elif isinstance(system, list):
            total += _count_anthropic_content(system, model, self)

        tools = body.get("tools")
        if isinstance(tools, list) and tools:
            total += self.count_tokens(json.dumps(tools, ensure_ascii=False), model)

        return total


def get_token_counter(protocol: str) -> TokenCounter:
    """
    Get Token Counter for specified protocol

    Args:
        protocol: Protocol type, "openai", "openai_responses", or "anthropic"

    Returns:
        TokenCounter: Corresponding counter instance
    """
    if protocol.lower() == "anthropic":
        return AnthropicTokenCounter()
    return OpenAITokenCounter()


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
                elif item.get("type") == "input_text" and isinstance(
                    item.get("text"), str
                ):
                    parts.append(item["text"])
                elif item.get("type") == "output_text" and isinstance(
                    item.get("text"), str
                ):
                    parts.append(item["text"])
        return "".join(parts)
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    return ""


def _count_openai_list(items: list[Any], model: str, counter: TokenCounter) -> int:
    total = 0
    for item in items:
        if isinstance(item, dict):
            total += _count_openai_content(item, model, counter)
        elif isinstance(item, str):
            total += counter.count_tokens(item, model)
    return total


def _count_openai_content(content: Any, model: str, counter: TokenCounter) -> int:
    if isinstance(content, str):
        return counter.count_tokens(content, model)
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                total += _count_openai_content(item, model, counter)
            elif isinstance(item, str):
                total += counter.count_tokens(item, model)
        return total
    if isinstance(content, dict):
        if content.get("type") in ("text", "input_text", "output_text"):
            text = content.get("text") or content.get("content")
            if isinstance(text, str):
                return counter.count_tokens(text, model)
        if content.get("type") in ("image_url", "input_image"):
            return _estimate_image_tokens(content, protocol="openai")
        if content.get("type") in ("input_audio", "audio"):
            return _estimate_audio_tokens(content)
        if content.get("type") in ("video", "input_video"):
            return _estimate_video_tokens(content)
        if "text" in content and isinstance(content["text"], str):
            return counter.count_tokens(content["text"], model)
    return 0


def _count_anthropic_content(content: Any, model: str, counter: TokenCounter) -> int:
    if isinstance(content, str):
        return counter.count_tokens(content, model)
    if isinstance(content, list):
        total = 0
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text" and isinstance(item.get("text"), str):
                total += counter.count_tokens(item["text"], model)
            elif item_type == "tool_use":
                total += counter.count_tokens(
                    json.dumps(item, ensure_ascii=False), model
                )
            elif item_type == "image":
                total += _estimate_image_tokens(item, protocol="anthropic")
        return total
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return counter.count_tokens(content["text"], model)
    return 0


def _estimate_image_tokens(item: dict[str, Any], protocol: str) -> int:
    detail = None
    if isinstance(item.get("detail"), str):
        detail = item.get("detail")
    image_url = item.get("image_url")
    if isinstance(image_url, dict) and isinstance(image_url.get("detail"), str):
        detail = image_url.get("detail")

    width = _safe_int(item.get("width"))
    height = _safe_int(item.get("height"))

    if width is None or height is None:
        # Try to decode data URLs or base64 payloads
        data = None
        if isinstance(image_url, dict):
            data = image_url.get("url")
        elif isinstance(item.get("source"), dict):
            data = item.get("source", {}).get("data")
        if isinstance(data, str):
            size = _extract_image_size_from_data(data)
            if size:
                width, height = size

    if protocol == "openai":
        return _estimate_openai_image_tokens(width, height, detail)
    if protocol == "anthropic":
        # Anthropic uses a different tokenizer; use a conservative tile-based estimate.
        return _estimate_openai_image_tokens(width, height, detail)
    return _estimate_openai_image_tokens(width, height, detail)


def _estimate_openai_image_tokens(
    width: Optional[int], height: Optional[int], detail: Optional[str]
) -> int:
    if detail == "low":
        return 85
    if width is None or height is None:
        return 170
    tiles = math.ceil(width / 512) * math.ceil(height / 512)
    return max(1, tiles) * 170


def _estimate_audio_tokens(item: dict[str, Any]) -> int:
    duration = _extract_duration_seconds(item)
    if duration is not None:
        return max(1, math.ceil(duration * 50))
    data = _extract_base64_bytes(item)
    if data is not None:
        return max(1, math.ceil(len(data) / 1000))
    return 0


def _estimate_video_tokens(item: dict[str, Any]) -> int:
    duration = _extract_duration_seconds(item)
    if duration is not None:
        return max(1, math.ceil(duration * 200))
    data = _extract_base64_bytes(item)
    if data is not None:
        return max(1, math.ceil(len(data) / 2000))
    return 0


def _extract_duration_seconds(item: dict[str, Any]) -> Optional[float]:
    for key in ("duration_seconds", "duration", "duration_s"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    duration_ms = item.get("duration_ms")
    if isinstance(duration_ms, (int, float)):
        return float(duration_ms) / 1000.0
    return None


def _extract_base64_bytes(item: dict[str, Any]) -> Optional[bytes]:
    data = item.get("data")
    if isinstance(item.get("audio"), dict):
        data = item.get("audio", {}).get("data") or data
    if isinstance(item.get("input_audio"), dict):
        data = item.get("input_audio", {}).get("data") or data
    if isinstance(item.get("video"), dict):
        data = item.get("video", {}).get("data") or data
    if isinstance(item.get("input_video"), dict):
        data = item.get("input_video", {}).get("data") or data
    if isinstance(data, str):
        return _decode_base64_data(data)
    return None


def _decode_base64_data(data: str) -> Optional[bytes]:
    if data.startswith("data:"):
        comma = data.find(",")
        if comma != -1:
            data = data[comma + 1 :]
    try:
        return base64.b64decode(data, validate=False)
    except Exception:
        return None


def _extract_image_size_from_data(data: str) -> Optional[tuple[int, int]]:
    raw = _decode_base64_data(data)
    if not raw:
        return None
    return _extract_image_size_from_bytes(raw)


def _extract_image_size_from_bytes(data: bytes) -> Optional[tuple[int, int]]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return width, height
    if data.startswith(b"\xff\xd8"):
        return _extract_jpeg_size(data)
    return None


def _extract_jpeg_size(data: bytes) -> Optional[tuple[int, int]]:
    idx = 2
    size = len(data)
    while idx < size:
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker = data[idx + 1] if idx + 1 < size else None
        idx += 2
        if marker in (
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        ):
            if idx + 7 <= size:
                height = int.from_bytes(data[idx + 3 : idx + 5], "big")
                width = int.from_bytes(data[idx + 5 : idx + 7], "big")
                return width, height
            return None
        if idx + 1 >= size:
            break
        segment_length = int.from_bytes(data[idx : idx + 2], "big")
        if segment_length < 2:
            break
        idx += segment_length
    return None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
