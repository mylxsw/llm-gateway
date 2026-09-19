"""Track OpenAI deltas as sequential content blocks, shared by SDK and gateway."""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from ..ir import IRStreamEvent, IRTextBlock, IRToolUseBlock, StreamEventType
from .exceptions import StreamConversionError


@dataclass
class _Block:
    index: int
    tool: bool = False
    source_index: Optional[int] = None
    id: str = ""
    name: str = ""
    fragments: List[str] = field(default_factory=list)
    started: bool = False


class OpenAIChatStreamBlocks:
    """Keep each tool's arguments in one block, even when calls are interleaved.

    OpenAI has no per-tool end marker. The first tool can stream immediately;
    subsequent blocks wait until finish so no delta targets a closed block.
    Empty metadata is a placeholder, never a new identity.
    """

    def __init__(self):
        self._pending: Deque[_Block] = deque()
        self._tools: List[_Block] = []
        self._by_index: Dict[int, _Block] = {}
        self._by_id: Dict[str, _Block] = {}
        self._next_index = 0
        self._finished = False

    def _new_block(self, tool: bool = False) -> _Block:
        block = _Block(index=self._next_index, tool=tool)
        self._next_index += 1
        self._pending.append(block)
        if tool:
            self._tools.append(block)
        return block

    def _tool_block(self, call: Dict[str, Any]) -> _Block:
        source_index = call.get("index")
        tool_id = call.get("id") or ""
        if source_index is not None and (
            type(source_index) is not int or source_index < 0
        ):
            raise StreamConversionError("Invalid tool call index")
        if not isinstance(tool_id, str):
            raise StreamConversionError("Invalid tool call ID")

        block = self._by_index.get(source_index)
        by_id = self._by_id.get(tool_id)
        if block is not None and by_id is not None and block is not by_id:
            raise StreamConversionError("Conflicting tool call index and ID")
        if block is None:
            block = by_id
        if block is None and source_index is None:
            # An anonymous initial fragment may acquire its ID later. Otherwise
            # only a single known tool permits an unaddressed continuation.
            if tool_id:
                candidates = [tool for tool in self._tools if not tool.id]
            else:
                candidates = self._tools
            if len(candidates) > 1:
                raise StreamConversionError("Ambiguous tool call continuation")
            if candidates:
                block = candidates[0]
        if block is None:
            block = self._new_block(tool=True)

        if source_index is not None:
            if block.source_index is not None and block.source_index != source_index:
                raise StreamConversionError("Tool call ID reused across indices")
            block.source_index = source_index
            self._by_index[source_index] = block
        if tool_id:
            if block.id and block.id != tool_id:
                raise StreamConversionError("Tool call ID changed within an index")
            block.id = tool_id
            self._by_id[tool_id] = block
        name = (call.get("function") or {}).get("name") or ""
        if not isinstance(name, str):
            raise StreamConversionError("Invalid tool call name")
        if name:
            if block.name and block.name != name:
                raise StreamConversionError("Tool call name changed within a call")
            block.name = name
        return block

    def feed(self, delta: Dict[str, Any]) -> List[IRStreamEvent]:
        content = delta.get("content")
        calls = delta.get("tool_calls") or []
        if self._finished:
            if content or calls:
                raise StreamConversionError("Content received after stream finish")
            return []
        if content:
            if not self._pending or self._pending[-1].tool:
                self._new_block()
            self._pending[-1].fragments.append(content)
        for call in calls:
            block = self._tool_block(call)
            arguments = (call.get("function") or {}).get("arguments")
            if arguments:
                if not isinstance(arguments, str):
                    raise StreamConversionError("Tool arguments delta must be a string")
                block.fragments.append(arguments)
        return self._flush(final=False)

    def finish(self) -> List[IRStreamEvent]:
        if self._finished:
            return []
        # Validate all queued identities before emitting any final blocks.
        if any(not tool.id or not tool.name for tool in self._tools):
            raise StreamConversionError("Tool call ended without an ID or name")
        events = self._flush(final=True)
        self._finished = True
        return events

    def _flush(self, *, final: bool) -> List[IRStreamEvent]:
        events = []
        while self._pending:
            block = self._pending[0]
            if block.tool and (not block.id or not block.name):
                break
            if not block.started:
                block.started = True
                events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_START,
                        index=block.index,
                        content_block=(
                            IRToolUseBlock(id=block.id, name=block.name)
                            if block.tool
                            else IRTextBlock(text="")
                        ),
                    )
                )
            for fragment in block.fragments:
                events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_DELTA,
                        index=block.index,
                        delta_type="input_json" if block.tool else "text",
                        delta_json=fragment if block.tool else None,
                        delta_text=None if block.tool else fragment,
                    )
                )
            block.fragments.clear()
            if not final and (block.tool or len(self._pending) == 1):
                break
            events.append(
                IRStreamEvent(
                    type=StreamEventType.CONTENT_BLOCK_STOP,
                    index=block.index,
                )
            )
            self._pending.popleft()
        return events
