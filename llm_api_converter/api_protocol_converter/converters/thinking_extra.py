"""Carry signed Anthropic thinking blocks through OpenAI Chat tool calls.

Anthropic-protocol upstreams (Anthropic, MiniMax, ...) require the thinking
blocks of an assistant tool-use turn to be sent back verbatim, signature
included. OpenAI Chat has no field for them, so - like Gemini's
`extra_content.google.thought_signature` - they ride on the tool call:

    tool_call["extra_content"] = {"anthropic": {"thinking_blocks": [...]}}

Each tool call carries the blocks that preceded it in the original message.
"""

from typing import Any, Dict, List, Optional

from ..ir import IRThinkingBlock

EXTRA_CONTENT_KEY = "extra_content"
ANTHROPIC_EXTRA_KEY = "anthropic"
THINKING_BLOCKS_KEY = "thinking_blocks"


def thinking_block_to_dict(block: IRThinkingBlock) -> Optional[Dict[str, Any]]:
    """Return the Anthropic wire form of a block that can be replayed."""
    if block.is_redacted:
        if block.redacted_data:
            return {"type": "redacted_thinking", "data": block.redacted_data}
        return None
    # Unsigned thinking (e.g. converted from reasoning_content) is rejected
    # upstream, so it is never carried.
    if block.signature:
        return {
            "type": "thinking",
            "thinking": block.thinking,
            "signature": block.signature,
        }
    return None


def thinking_extra(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {ANTHROPIC_EXTRA_KEY: {THINKING_BLOCKS_KEY: list(blocks)}}


def thinking_blocks_from_tool_call(tool_call: Any) -> List[IRThinkingBlock]:
    """Decode blocks carried on an OpenAI tool call; ignore malformed data."""
    if not isinstance(tool_call, dict):
        return []
    extra = tool_call.get(EXTRA_CONTENT_KEY)
    if not isinstance(extra, dict):
        return []
    anthropic = extra.get(ANTHROPIC_EXTRA_KEY)
    if not isinstance(anthropic, dict):
        return []
    raw_blocks = anthropic.get(THINKING_BLOCKS_KEY)
    if not isinstance(raw_blocks, list):
        return []

    blocks: List[IRThinkingBlock] = []
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            continue
        if raw.get("type") == "thinking":
            thinking = raw.get("thinking")
            signature = raw.get("signature")
            if isinstance(thinking, str) and isinstance(signature, str) and signature:
                blocks.append(IRThinkingBlock(thinking=thinking, signature=signature))
        elif raw.get("type") == "redacted_thinking":
            data = raw.get("data")
            if isinstance(data, str) and data:
                blocks.append(IRThinkingBlock(is_redacted=True, redacted_data=data))
    return blocks


def strip_anthropic_extra(tool_call: Any) -> None:
    """Remove carried Anthropic blocks before sending to a non-Anthropic upstream."""
    if not isinstance(tool_call, dict):
        return
    extra = tool_call.get(EXTRA_CONTENT_KEY)
    if not isinstance(extra, dict) or ANTHROPIC_EXTRA_KEY not in extra:
        return
    extra = {k: v for k, v in extra.items() if k != ANTHROPIC_EXTRA_KEY}
    if extra:
        tool_call[EXTRA_CONTENT_KEY] = extra
    else:
        tool_call.pop(EXTRA_CONTENT_KEY, None)
