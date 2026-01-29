"""
Stream Adapters Module

Provides utilities for streaming conversion between protocols.
Supports incremental processing and various output formats.
"""

from typing import Any, Dict, Iterator, List, Optional, Union
import json

from ..ir import (
    IRStreamEvent,
    IRTextBlock,
    IRToolUseBlock,
    IRUsage,
    StreamEventType,
    StopReason,
)
from ..schemas import Protocol


class StreamAccumulator:
    """
    Accumulates streaming events and provides utilities for reconstructing
    complete responses or converting between protocols.
    """

    def __init__(self):
        self.response_id: Optional[str] = None
        self.model: Optional[str] = None
        self.created: Optional[int] = None

        # Content accumulation
        self.text_content: str = ""
        self.tool_calls: Dict[int, Dict[str, Any]] = {}  # index -> tool call data
        self.thinking_content: str = ""

        # State
        self.current_block_index: int = 0
        self.current_block_type: Optional[str] = None
        self.stop_reason: Optional[StopReason] = None
        self.stop_sequence: Optional[str] = None
        self.usage: Optional[IRUsage] = None

        # Partial JSON accumulation for tool arguments
        self._partial_json: Dict[int, str] = {}

    def process_event(self, event: IRStreamEvent) -> None:
        """Process an IR stream event and update accumulator state."""
        if event.type == StreamEventType.MESSAGE_START:
            if event.response:
                self.response_id = event.response.id
                self.model = event.response.model
                self.created = event.response.created

        elif event.type == StreamEventType.CONTENT_BLOCK_START:
            self.current_block_index = event.index
            if isinstance(event.content_block, IRToolUseBlock):
                self.current_block_type = "tool_use"
                self.tool_calls[event.index] = {
                    "id": event.content_block.id,
                    "name": event.content_block.name,
                    "arguments": "",
                }
                self._partial_json[event.index] = ""
            elif isinstance(event.content_block, IRTextBlock):
                self.current_block_type = "text"
            else:
                self.current_block_type = "text"

        elif event.type == StreamEventType.CONTENT_BLOCK_DELTA:
            if event.delta_type == "text":
                self.text_content += event.delta_text or ""
            elif event.delta_type == "input_json":
                if event.index in self._partial_json:
                    self._partial_json[event.index] += event.delta_json or ""
                    if event.index in self.tool_calls:
                        self.tool_calls[event.index]["arguments"] = self._partial_json[event.index]
            elif event.delta_type == "thinking":
                self.thinking_content += event.delta_text or ""

        elif event.type == StreamEventType.CONTENT_BLOCK_STOP:
            # Finalize the current block
            pass

        elif event.type == StreamEventType.MESSAGE_DELTA:
            if event.stop_reason:
                self.stop_reason = event.stop_reason
            if event.stop_sequence:
                self.stop_sequence = event.stop_sequence
            if event.usage:
                self.usage = event.usage

    def get_text_content(self) -> str:
        """Get accumulated text content."""
        return self.text_content

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """Get accumulated tool calls."""
        return list(self.tool_calls.values())

    def reset(self) -> None:
        """Reset accumulator state."""
        self.__init__()


class SSEParser:
    """Parser for Server-Sent Events (SSE) format."""

    def __init__(self):
        self._buffer = ""

    def feed(self, data: str) -> Iterator[Dict[str, Any]]:
        """
        Feed data to the parser and yield complete events.

        Args:
            data: Raw SSE data string

        Yields:
            Parsed event dictionaries
        """
        self._buffer += data

        while "\n\n" in self._buffer:
            event_str, self._buffer = self._buffer.split("\n\n", 1)
            event = self._parse_event(event_str)
            if event is not None:
                yield event

    def _parse_event(self, event_str: str) -> Optional[Dict[str, Any]]:
        """Parse a single SSE event string."""
        lines = event_str.strip().split("\n")
        event_type = None
        data_lines = []

        for line in lines:
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line.startswith(":"):
                # Comment, ignore
                continue

        if not data_lines:
            return None

        data_str = "\n".join(data_lines)

        # Handle [DONE] marker
        if data_str == "[DONE]":
            return {"type": "done", "data": "[DONE]"}

        try:
            data = json.loads(data_str)
            if event_type:
                data["_event_type"] = event_type
            return data
        except json.JSONDecodeError:
            return None


class SSEFormatter:
    """Formatter for Server-Sent Events (SSE) format."""

    @staticmethod
    def format_event(
        event_type: Optional[str],
        data: Union[Dict[str, Any], str],
        *,
        include_newlines: bool = True,
    ) -> str:
        """
        Format an event as SSE.

        Args:
            event_type: Optional event type (e.g., "message_start")
            data: Event data (dict or string)
            include_newlines: Include trailing newlines

        Returns:
            Formatted SSE string
        """
        lines = []

        if event_type:
            lines.append(f"event: {event_type}")

        if isinstance(data, str):
            lines.append(f"data: {data}")
        else:
            lines.append(f"data: {json.dumps(data)}")

        result = "\n".join(lines)
        if include_newlines:
            result += "\n\n"

        return result

    @staticmethod
    def format_done() -> str:
        """Format a [DONE] marker."""
        return "data: [DONE]\n\n"


def convert_stream_sync(
    source_protocol: Protocol,
    target_protocol: Protocol,
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    output_format: str = "dict",
) -> Iterator[Union[Dict[str, Any], str]]:
    """
    Convert a stream of events synchronously.

    This is a convenience wrapper that provides a simpler interface
    for synchronous stream conversion.

    Args:
        source_protocol: Source protocol
        target_protocol: Target protocol
        events: Iterator of source events
        output_format: Output format ("dict" or "sse")

    Yields:
        Converted events
    """
    from ..converters import _DECODERS, _ENCODERS

    decoder = _DECODERS[source_protocol]
    encoder = _ENCODERS[target_protocol]

    for event in events:
        ir_events = decoder.decode_stream_event(event)
        for ir_event in ir_events:
            target_events = encoder.encode_stream_event(
                ir_event, options={"output_format": output_format}
            )
            yield from target_events


class StreamConverter:
    """
    Stateful stream converter that maintains context across events.

    Useful for conversions that require looking at previous events
    (e.g., to determine content block indices).
    """

    def __init__(
        self,
        source_protocol: Protocol,
        target_protocol: Protocol,
        *,
        output_format: str = "dict",
    ):
        self.source_protocol = source_protocol
        self.target_protocol = target_protocol
        self.output_format = output_format
        self.accumulator = StreamAccumulator()

        # Import here to avoid circular imports
        from ..converters import _DECODERS, _ENCODERS
        self._decoder = _DECODERS[source_protocol]
        self._encoder = _ENCODERS[target_protocol]

    def convert_event(
        self, event: Union[Dict[str, Any], str]
    ) -> List[Union[Dict[str, Any], str]]:
        """
        Convert a single event.

        Args:
            event: Source event

        Returns:
            List of converted events
        """
        # Decode to IR
        ir_events = self._decoder.decode_stream_event(event)

        results = []
        for ir_event in ir_events:
            # Update accumulator
            self.accumulator.process_event(ir_event)

            # Encode to target
            target_events = self._encoder.encode_stream_event(
                ir_event, options={"output_format": self.output_format}
            )
            results.extend(target_events)

        return results

    def convert_stream(
        self, events: Iterator[Union[Dict[str, Any], str]]
    ) -> Iterator[Union[Dict[str, Any], str]]:
        """
        Convert a stream of events.

        Args:
            events: Iterator of source events

        Yields:
            Converted events
        """
        for event in events:
            converted = self.convert_event(event)
            yield from converted

    def get_accumulated_content(self) -> str:
        """Get accumulated text content."""
        return self.accumulator.get_text_content()

    def get_accumulated_tool_calls(self) -> List[Dict[str, Any]]:
        """Get accumulated tool calls."""
        return self.accumulator.get_tool_calls()

    def reset(self) -> None:
        """Reset converter state."""
        self.accumulator.reset()


__all__ = [
    "StreamAccumulator",
    "SSEParser",
    "SSEFormatter",
    "StreamConverter",
    "convert_stream_sync",
]
