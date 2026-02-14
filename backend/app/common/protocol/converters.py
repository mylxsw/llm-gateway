"""
Protocol Converters Implementation

Uses llm_api_converter SDK for protocol conversion through
Intermediate Representation (IR).
"""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from .base import (
    ConversionResult,
    IRequestConverter,
    IResponseConverter,
    IStreamConverter,
    Protocol,
    ProtocolConversionError,
    ValidationError,
)

# Import llm_api_converter SDK
try:
    import os
    import sys

    # Add llm_api_converter to path if needed
    llm_converter_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "..", "llm_api_converter"
    )
    if llm_converter_path not in sys.path:
        sys.path.insert(0, os.path.abspath(llm_converter_path))

    from api_protocol_converter import (
        Protocol as SDKProtocol,
    )
    from api_protocol_converter import (
        convert_request,
        convert_response,
    )
    from api_protocol_converter.converters import (
        AnthropicMessagesDecoder,
        AnthropicMessagesEncoder,
        OpenAIChatDecoder,
        OpenAIChatEncoder,
        OpenAIResponsesDecoder,
        OpenAIResponsesEncoder,
    )
    from api_protocol_converter.ir import (
        IRRequest,
        IRResponse,
        IRStreamEvent,
        StopReason,
        StreamEventType,
    )
    from api_protocol_converter.stream import SSEFormatter, SSEParser

    _HAS_SDK = True
except ImportError as e:
    _HAS_SDK = False
    _SDK_IMPORT_ERROR = str(e)

logger = logging.getLogger(__name__)

_OPENAI_CHAT_PATH = "/v1/chat/completions"
_OPENAI_COMPLETIONS_PATH = "/v1/completions"
_OPENAI_EMBEDDINGS_PATH = "/v1/embeddings"
_OPENAI_RESPONSES_PATH = "/v1/responses"
_OPENAI_IMAGE_PATHS = {
    "/v1/images/generations",
    "/v1/images/edits",
    "/v1/images/variations",
}


def _protocol_to_sdk(protocol: Protocol) -> "SDKProtocol":
    """Convert internal Protocol to SDK Protocol."""
    mapping = {
        Protocol.OPENAI: SDKProtocol.OPENAI_CHAT,
        Protocol.OPENAI_RESPONSES: SDKProtocol.OPENAI_RESPONSES,
        Protocol.ANTHROPIC: SDKProtocol.ANTHROPIC_MESSAGES,
    }
    if protocol not in mapping:
        raise ValueError(f"Protocol {protocol.value} is not available in SDK mapping")
    return mapping[protocol]


def _normalize_openai_tooling_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize legacy OpenAI function-calling fields to modern tool-calling fields.

    - functions -> tools
    - function_call -> tool_choice
    """
    out = copy.deepcopy(body)

    # Legacy: functions + function_call -> tools + tool_choice
    if "tools" not in out and isinstance(out.get("functions"), list):
        tools: List[Dict[str, Any]] = []
        for fn in out["functions"]:
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not isinstance(name, str) or not name:
                continue
            tool: Dict[str, Any] = {"type": "function", "function": {}}
            tool_fn = tool["function"]
            tool_fn["name"] = name
            if isinstance(fn.get("description"), str):
                tool_fn["description"] = fn.get("description")
            if isinstance(fn.get("parameters"), dict):
                tool_fn["parameters"] = fn.get("parameters")
            tools.append(tool)
        if tools:
            out["tools"] = tools

    if "tool_choice" not in out and "function_call" in out:
        fc = out.get("function_call")
        if isinstance(fc, str):
            out["tool_choice"] = fc
        elif isinstance(fc, dict):
            name = fc.get("name")
            if isinstance(name, str) and name:
                out["tool_choice"] = {"type": "function", "function": {"name": name}}

    return out


def _normalize_openai_responses_tooling_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize OpenAI Responses tooling fields to the shape expected by SDK decoder.

    The upstream SDK decoder currently expects:
    - tool_choice: {"type": "..."} or {"type":"function","name":"..."}
    - tools.function: {"type":"function","name":"...","parameters":...}
    """
    out = copy.deepcopy(body)

    if "tool_choice" in out:
        raw_tool_choice = out.get("tool_choice")
        normalized_tool_choice: Optional[Dict[str, Any]] = None

        if isinstance(raw_tool_choice, str):
            normalized_tool_choice = {"type": raw_tool_choice}
        elif isinstance(raw_tool_choice, dict):
            choice_type = raw_tool_choice.get("type")
            if (
                choice_type == "function"
                and isinstance(raw_tool_choice.get("function"), dict)
                and isinstance(raw_tool_choice["function"].get("name"), str)
                and raw_tool_choice["function"]["name"]
            ):
                normalized_tool_choice = {
                    "type": "function",
                    "name": raw_tool_choice["function"]["name"],
                }
            else:
                normalized_tool_choice = raw_tool_choice

        if normalized_tool_choice is None:
            del out["tool_choice"]
        else:
            out["tool_choice"] = normalized_tool_choice

    if isinstance(out.get("tools"), list):
        normalized_tools: List[Dict[str, Any]] = []
        for tool in out["tools"]:
            if not isinstance(tool, dict):
                continue

            tool_type = tool.get("type", "function")
            if tool_type != "function":
                normalized_tools.append(tool)
                continue

            # Chat Completions-style function tool.
            if isinstance(tool.get("function"), dict):
                fn = tool["function"]
                name = fn.get("name")
                if not isinstance(name, str) or not name:
                    continue
                normalized_tool: Dict[str, Any] = {"type": "function", "name": name}
                if isinstance(fn.get("description"), str):
                    normalized_tool["description"] = fn.get("description")
                if isinstance(fn.get("parameters"), dict):
                    normalized_tool["parameters"] = fn.get("parameters")
                if isinstance(fn.get("strict"), bool):
                    normalized_tool["strict"] = fn.get("strict")
                normalized_tools.append(normalized_tool)
                continue

            # Responses-style function tool.
            if isinstance(tool.get("name"), str) and tool.get("name"):
                normalized_tools.append(tool)

        out["tools"] = normalized_tools

    return out


def _build_gemini_generate_path(model: str, stream: bool) -> str:
    suffix = "streamGenerateContent?alt=sse" if stream else "generateContent"
    return f"/v1beta/models/{model}:{suffix}"


def _map_openai_finish_reason_to_gemini(reason: Optional[str]) -> Optional[str]:
    mapping = {
        "stop": "STOP",
        "length": "MAX_TOKENS",
        "tool_calls": "STOP",
        "content_filter": "SAFETY",
    }
    if reason is None:
        return None
    return mapping.get(reason, "STOP")


def _map_gemini_finish_reason_to_openai(reason: Optional[str]) -> Optional[str]:
    mapping = {
        "STOP": "stop",
        "MAX_TOKENS": "length",
        "SAFETY": "content_filter",
        "RECITATION": "content_filter",
    }
    if reason is None:
        return None
    return mapping.get(reason, "stop")


def _normalize_prompt_to_text(prompt: Any) -> str:
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        parts: list[str] = []
        for item in prompt:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, (int, float)):
                parts.append(str(item))
        return "\n".join([p for p in parts if p])
    if prompt is None:
        return ""
    return str(prompt)


def _openai_completions_to_chat_request(body: Dict[str, Any]) -> Dict[str, Any]:
    prompt = _normalize_prompt_to_text(body.get("prompt"))
    out: Dict[str, Any] = {
        "model": body.get("model"),
        "messages": [{"role": "user", "content": prompt}],
    }
    passthrough = (
        "temperature",
        "top_p",
        "n",
        "stream",
        "stop",
        "max_tokens",
        "presence_penalty",
        "frequency_penalty",
        "logprobs",
        "user",
    )
    for key in passthrough:
        if key in body:
            out[key] = body[key]
    return out


def _safe_json_loads(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    try:
        return json.loads(text)
    except Exception:
        return text


def _normalize_openai_embedding_inputs(input_value: Any) -> list[str]:
    if isinstance(input_value, str):
        return [input_value]
    if isinstance(input_value, list):
        out: list[str] = []
        for item in input_value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, list) and all(isinstance(x, int) for x in item):
                out.append(" ".join(str(x) for x in item))
            elif isinstance(item, int):
                out.append(str(item))
            else:
                out.append(str(item))
        return out
    if input_value is None:
        return [""]
    return [str(input_value)]


def _openai_embeddings_to_gemini_request(
    body: Dict[str, Any],
    target_model: str,
) -> ConversionResult:
    inputs = _normalize_openai_embedding_inputs(body.get("input"))
    output_dim = body.get("dimensions")

    if len(inputs) <= 1:
        payload: Dict[str, Any] = {
            "content": {"parts": [{"text": inputs[0] if inputs else ""}]},
        }
        if isinstance(output_dim, int) and output_dim > 0:
            payload["outputDimensionality"] = output_dim
        return ConversionResult(
            path=f"/v1beta/models/{target_model}:embedContent",
            body=payload,
        )

    requests: list[Dict[str, Any]] = []
    for text in inputs:
        req: Dict[str, Any] = {
            "model": f"models/{target_model}",
            "content": {"parts": [{"text": text}]},
        }
        if isinstance(output_dim, int) and output_dim > 0:
            req["outputDimensionality"] = output_dim
        requests.append(req)

    return ConversionResult(
        path=f"/v1beta/models/{target_model}:batchEmbedContents",
        body={"requests": requests},
    )


def _size_to_aspect_ratio(size: Any) -> Optional[str]:
    mapping = {
        "1024x1024": "1:1",
        "1024x1536": "2:3",
        "1536x1024": "3:2",
        "1024x1792": "9:16",
        "1792x1024": "16:9",
    }
    if isinstance(size, str):
        return mapping.get(size)
    return None


def _openai_images_to_gemini_request(
    body: Dict[str, Any],
    target_model: str,
    path: str,
) -> ConversionResult:
    prompt = body.get("prompt")
    prompt_text = prompt if isinstance(prompt, str) else ""
    parts: list[Dict[str, Any]] = []
    if prompt_text:
        parts.append({"text": prompt_text})

    files = body.get("_files")
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if not isinstance(data, (bytes, bytearray)):
                continue
            import base64

            b64 = base64.b64encode(bytes(data)).decode("utf-8")
            parts.append(
                {
                    "inlineData": {
                        "mimeType": item.get("content_type") or "image/png",
                        "data": b64,
                    }
                }
            )

    if not parts:
        parts.append({"text": "Generate an image"})

    payload: Dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    aspect_ratio = _size_to_aspect_ratio(body.get("size"))
    if aspect_ratio:
        payload["generationConfig"]["imageConfig"] = {"aspectRatio": aspect_ratio}

    return ConversionResult(
        path=f"/v1beta/models/{target_model}:generateContent",
        body=payload,
    )


def _openai_content_to_gemini_parts(content: Any) -> list[Dict[str, Any]]:
    parts: list[Dict[str, Any]] = []
    if isinstance(content, str):
        if content:
            parts.append({"text": content})
        return parts

    if isinstance(content, dict):
        content = [content]

    if not isinstance(content, list):
        if content is not None:
            parts.append({"text": str(content)})
        return parts

    for block in content:
        if isinstance(block, str):
            if block:
                parts.append({"text": block})
            continue
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type in ("text", "input_text", "output_text"):
            text = block.get("text") or block.get("content")
            if isinstance(text, str) and text:
                parts.append({"text": text})
            continue

        if block_type in ("image_url", "input_image"):
            image_url = block.get("image_url")
            url = None
            if isinstance(image_url, dict):
                url = image_url.get("url")
            elif isinstance(image_url, str):
                url = image_url
            if isinstance(url, str) and url:
                if url.startswith("data:") and ";base64," in url:
                    prefix, encoded = url.split(";base64,", 1)
                    mime = prefix[5:] if prefix.startswith("data:") else "image/png"
                    parts.append(
                        {
                            "inlineData": {
                                "mimeType": mime,
                                "data": encoded,
                            }
                        }
                    )
                else:
                    parts.append(
                        {
                            "fileData": {
                                "mimeType": "image/*",
                                "fileUri": url,
                            }
                        }
                    )
            continue

        text = block.get("text")
        if isinstance(text, str) and text:
            parts.append({"text": text})

    return parts


def _openai_tools_to_gemini_tools(tools: Any) -> Optional[list[Dict[str, Any]]]:
    if not isinstance(tools, list):
        return None
    declarations: list[Dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "function":
            continue
        fn = tool.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            continue
        decl: Dict[str, Any] = {"name": name}
        if isinstance(fn.get("description"), str):
            decl["description"] = fn["description"]
        params = fn.get("parameters")
        if isinstance(params, dict):
            decl["parameters"] = params
        declarations.append(decl)

    if not declarations:
        return None
    return [{"functionDeclarations": declarations}]


def _openai_tool_choice_to_gemini_tool_config(choice: Any) -> Optional[Dict[str, Any]]:
    if choice is None:
        return None

    if isinstance(choice, str):
        mode = "AUTO"
        if choice == "none":
            mode = "NONE"
        elif choice in ("required", "any"):
            mode = "ANY"
        return {"functionCallingConfig": {"mode": mode}}

    if isinstance(choice, dict):
        if choice.get("type") == "function":
            fn = choice.get("function")
            if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                return {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [fn["name"]],
                    }
                }
        choice_type = choice.get("type")
        if isinstance(choice_type, str):
            mode = "AUTO"
            if choice_type == "none":
                mode = "NONE"
            elif choice_type in ("required", "any"):
                mode = "ANY"
            return {"functionCallingConfig": {"mode": mode}}
    return None


def _openai_chat_to_gemini_request(
    body: Dict[str, Any],
    target_model: str,
) -> ConversionResult:
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValidationError("messages", "OpenAI request missing messages array")

    contents: list[Dict[str, Any]] = []
    system_parts: list[Dict[str, Any]] = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue

        role = msg.get("role") if isinstance(msg.get("role"), str) else "user"
        if role == "system":
            system_parts.extend(_openai_content_to_gemini_parts(msg.get("content")))
            continue

        parts = _openai_content_to_gemini_parts(msg.get("content"))

        if role == "assistant":
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function")
                    if not isinstance(fn, dict):
                        continue
                    name = fn.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    args = _safe_json_loads(fn.get("arguments"))
                    if not isinstance(args, dict):
                        args = {"value": args}
                    parts.append({"functionCall": {"name": name, "args": args}})

        if role == "tool":
            response_name = msg.get("name") or "tool"
            tool_payload: Any = msg.get("content")
            if isinstance(tool_payload, str):
                tool_payload = _safe_json_loads(tool_payload)
            parts.append(
                {
                    "functionResponse": {
                        "name": response_name,
                        "response": {"content": tool_payload},
                    }
                }
            )
            role = "user"

        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": parts or [{"text": ""}],
            }
        )

    out: Dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": ""}]}]}

    if system_parts:
        out["systemInstruction"] = {"parts": system_parts}

    tools = _openai_tools_to_gemini_tools(body.get("tools"))
    if tools:
        out["tools"] = tools

    tool_config = _openai_tool_choice_to_gemini_tool_config(body.get("tool_choice"))
    if tool_config:
        out["toolConfig"] = tool_config

    generation_config: Dict[str, Any] = {}
    for src, dst in (
        ("temperature", "temperature"),
        ("top_p", "topP"),
        ("top_k", "topK"),
    ):
        if body.get(src) is not None:
            generation_config[dst] = body.get(src)

    max_tokens = body.get("max_completion_tokens")
    if max_tokens is None:
        max_tokens = body.get("max_tokens")
    if isinstance(max_tokens, int):
        generation_config["maxOutputTokens"] = max_tokens

    stop = body.get("stop")
    if isinstance(stop, str):
        generation_config["stopSequences"] = [stop]
    elif isinstance(stop, list):
        seqs = [x for x in stop if isinstance(x, str)]
        if seqs:
            generation_config["stopSequences"] = seqs

    response_format = body.get("response_format")
    if isinstance(response_format, dict):
        r_type = response_format.get("type")
        if r_type in ("json_object", "json_schema"):
            generation_config["responseMimeType"] = "application/json"
            schema_payload = response_format.get("json_schema")
            if isinstance(schema_payload, dict):
                schema = schema_payload.get("schema")
                if isinstance(schema, dict):
                    generation_config["responseSchema"] = schema

    if generation_config:
        out["generationConfig"] = generation_config

    stream = bool(body.get("stream"))
    return ConversionResult(
        path=_build_gemini_generate_path(target_model, stream),
        body=out,
    )


def _gemini_request_to_openai_chat(
    path: str,
    body: Dict[str, Any],
    target_model: str,
) -> ConversionResult:
    if path.endswith(":embedContent") or path.endswith(":batchEmbedContents"):
        requests = body.get("requests")
        if isinstance(requests, list):
            inputs: list[str] = []
            for item in requests:
                if not isinstance(item, dict):
                    continue
                content = item.get("content", {})
                text = ""
                if isinstance(content, dict):
                    parts = content.get("parts")
                    if isinstance(parts, list):
                        for part in parts:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                text += part["text"]
                inputs.append(text)
            return ConversionResult(
                path=_OPENAI_EMBEDDINGS_PATH,
                body={"model": target_model, "input": inputs},
            )

        content = body.get("content", {})
        text = ""
        if isinstance(content, dict):
            parts = content.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        text += part["text"]
        return ConversionResult(
            path=_OPENAI_EMBEDDINGS_PATH,
            body={"model": target_model, "input": text},
        )

    contents = body.get("contents")
    if not isinstance(contents, list):
        raise ValidationError("contents", "Gemini request missing contents array")

    messages: list[Dict[str, Any]] = []
    for content in contents:
        if not isinstance(content, dict):
            continue
        role = content.get("role")
        openai_role = "assistant" if role == "model" else "user"
        parts = content.get("parts")
        text_blocks: list[Dict[str, Any]] = []
        tool_calls: list[Dict[str, Any]] = []
        if isinstance(parts, list):
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if isinstance(part.get("text"), str):
                    text_blocks.append({"type": "text", "text": part["text"]})
                fc = part.get("functionCall")
                if isinstance(fc, dict) and isinstance(fc.get("name"), str):
                    args = fc.get("args")
                    tool_calls.append(
                        {
                            "id": f"call_{uuid.uuid4().hex}",
                            "type": "function",
                            "function": {
                                "name": fc["name"],
                                "arguments": json.dumps(args or {}, ensure_ascii=False),
                            },
                        }
                    )
                fr = part.get("functionResponse")
                if isinstance(fr, dict):
                    tool_name = fr.get("name") if isinstance(fr.get("name"), str) else "tool"
                    tool_content = fr.get("response", {}).get("content")
                    messages.append(
                        {
                            "role": "tool",
                            "name": tool_name,
                            "content": json.dumps(tool_content, ensure_ascii=False),
                        }
                    )

        msg: Dict[str, Any] = {"role": openai_role}
        if tool_calls:
            msg["tool_calls"] = tool_calls
            msg["content"] = ""
        else:
            if len(text_blocks) == 1 and text_blocks[0].get("type") == "text":
                msg["content"] = text_blocks[0].get("text", "")
            else:
                msg["content"] = text_blocks
        messages.append(msg)

    system_instruction = body.get("systemInstruction")
    if isinstance(system_instruction, dict):
        parts = system_instruction.get("parts")
        system_text = ""
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    system_text += part["text"]
        if system_text:
            messages.insert(0, {"role": "system", "content": system_text})

    out: Dict[str, Any] = {"model": target_model, "messages": messages}

    generation = body.get("generationConfig")
    if isinstance(generation, dict):
        for src, dst in (
            ("temperature", "temperature"),
            ("topP", "top_p"),
            ("topK", "top_k"),
        ):
            if generation.get(src) is not None:
                out[dst] = generation.get(src)
        if isinstance(generation.get("maxOutputTokens"), int):
            out["max_tokens"] = generation.get("maxOutputTokens")
        stop_sequences = generation.get("stopSequences")
        if isinstance(stop_sequences, list):
            out["stop"] = [s for s in stop_sequences if isinstance(s, str)]

    tools = body.get("tools")
    if isinstance(tools, list):
        openai_tools: list[Dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            for decl in tool.get("functionDeclarations", []):
                if not isinstance(decl, dict):
                    continue
                name = decl.get("name")
                if not isinstance(name, str) or not name:
                    continue
                fn: Dict[str, Any] = {"name": name}
                if isinstance(decl.get("description"), str):
                    fn["description"] = decl["description"]
                if isinstance(decl.get("parameters"), dict):
                    fn["parameters"] = decl["parameters"]
                openai_tools.append({"type": "function", "function": fn})
        if openai_tools:
            out["tools"] = openai_tools

    tool_config = body.get("toolConfig")
    if isinstance(tool_config, dict):
        fc = tool_config.get("functionCallingConfig")
        if isinstance(fc, dict):
            mode = fc.get("mode")
            if mode == "NONE":
                out["tool_choice"] = "none"
            elif mode == "ANY":
                allowed = fc.get("allowedFunctionNames")
                if isinstance(allowed, list) and allowed and isinstance(allowed[0], str):
                    out["tool_choice"] = {
                        "type": "function",
                        "function": {"name": allowed[0]},
                    }
                else:
                    out["tool_choice"] = "required"
            elif mode == "AUTO":
                out["tool_choice"] = "auto"

    stream = "streamGenerateContent" in path
    if stream:
        out["stream"] = True

    return ConversionResult(path=_OPENAI_CHAT_PATH, body=out)


def _gemini_usage_to_openai(usage: Any) -> Dict[str, Any]:
    if not isinstance(usage, dict):
        return {}
    prompt = usage.get("promptTokenCount", 0)
    completion = usage.get("candidatesTokenCount", 0)
    total = usage.get("totalTokenCount", prompt + completion)
    out = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }
    cached = usage.get("cachedContentTokenCount")
    if isinstance(cached, int):
        out["prompt_tokens_details"] = {"cached_tokens": cached}
    return out


def _gemini_usage_to_openai_image(usage: Any) -> Dict[str, Any]:
    """Convert Gemini usageMetadata to OpenAI Images API usage format."""
    if not isinstance(usage, dict):
        return {}
    prompt = usage.get("promptTokenCount", 0)
    completion = usage.get("candidatesTokenCount", 0)
    total = usage.get("totalTokenCount", prompt + completion)

    input_details: Dict[str, int] = {}
    output_details: Dict[str, int] = {}
    prompt_details = usage.get("promptTokensDetails")
    if isinstance(prompt_details, list):
        for d in prompt_details:
            if isinstance(d, dict):
                modality = d.get("modality", "")
                count = d.get("tokenCount", 0)
                if modality == "TEXT":
                    input_details["text_tokens"] = count
                elif modality == "IMAGE":
                    input_details["image_tokens"] = count
    candidates_details = usage.get("candidatesTokensDetails")
    if isinstance(candidates_details, list):
        for d in candidates_details:
            if isinstance(d, dict):
                modality = d.get("modality", "")
                count = d.get("tokenCount", 0)
                if modality == "TEXT":
                    output_details["text_tokens"] = count
                elif modality == "IMAGE":
                    output_details["image_tokens"] = count

    result: Dict[str, Any] = {
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": total,
    }
    if input_details:
        result["input_tokens_details"] = input_details
    if output_details:
        result["output_tokens_details"] = output_details
    return result


def _build_openai_image_response(
    image_parts: list[Dict[str, Any]],
    gemini_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Build OpenAI Images API compatible response from Gemini image parts."""
    result: Dict[str, Any] = {
        "created": int(time.time()),
        "data": [{"b64_json": img["data"]} for img in image_parts],
    }

    # Derive output_format from first image's mimeType
    first_mime = image_parts[0].get("mimeType", "") if image_parts else ""
    if first_mime:
        # "image/png" -> "png", "image/jpeg" -> "jpeg"
        fmt = first_mime.split("/", 1)[-1] if "/" in first_mime else first_mime
        result["output_format"] = fmt

    # Convert usage metadata
    usage_meta = gemini_body.get("usageMetadata")
    if isinstance(usage_meta, dict):
        result["usage"] = _gemini_usage_to_openai_image(usage_meta)

    return result


def _gemini_response_to_openai(
    body: Dict[str, Any],
    target_model: str,
) -> Dict[str, Any]:
    if "embedding" in body or "embeddings" in body:
        if isinstance(body.get("embedding"), dict):
            values = body["embedding"].get("values")
            if not isinstance(values, list):
                values = []
            return {
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": values}],
                "model": target_model,
                "usage": _gemini_usage_to_openai(body.get("usageMetadata")),
            }
        embeddings = body.get("embeddings")
        data: list[Dict[str, Any]] = []
        if isinstance(embeddings, list):
            for i, item in enumerate(embeddings):
                values = []
                if isinstance(item, dict) and isinstance(item.get("values"), list):
                    values = item["values"]
                data.append({"object": "embedding", "index": i, "embedding": values})
        return {
            "object": "list",
            "data": data,
            "model": target_model,
            "usage": _gemini_usage_to_openai(body.get("usageMetadata")),
        }

    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": target_model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "stop",
                }
            ],
            "usage": _gemini_usage_to_openai(body.get("usageMetadata")),
        }

    cand = candidates[0] if isinstance(candidates[0], dict) else {}
    content = cand.get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    text_parts: list[str] = []
    image_parts: list[Dict[str, Any]] = []
    tool_calls: list[Dict[str, Any]] = []

    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            if isinstance(part.get("text"), str):
                text_parts.append(part["text"])
            fc = part.get("functionCall")
            if isinstance(fc, dict) and isinstance(fc.get("name"), str):
                tool_calls.append(
                    {
                        "id": f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {
                            "name": fc["name"],
                            "arguments": json.dumps(fc.get("args") or {}, ensure_ascii=False),
                        },
                    }
                )
            inline = part.get("inlineData")
            if (
                isinstance(inline, dict)
                and isinstance(inline.get("data"), str)
                and inline.get("data")
            ):
                image_parts.append(
                    {"data": inline["data"], "mimeType": inline.get("mimeType", "")}
                )

    if image_parts and not text_parts and not tool_calls:
        return _build_openai_image_response(image_parts, body)

    message: Dict[str, Any] = {"role": "assistant"}
    if tool_calls:
        message["tool_calls"] = tool_calls
        message["content"] = "".join(text_parts)
    else:
        message["content"] = "".join(text_parts)

    return {
        "id": body.get("responseId") or f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": target_model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": _map_gemini_finish_reason_to_openai(
                    cand.get("finishReason")
                ),
            }
        ],
        "usage": _gemini_usage_to_openai(body.get("usageMetadata")),
    }


def _openai_response_to_gemini(
    body: Dict[str, Any],
    target_model: str,
) -> Dict[str, Any]:
    data = body.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if "embedding" in data[0]:
            if len(data) == 1:
                return {"embedding": {"values": data[0].get("embedding", [])}}
            return {
                "embeddings": [
                    {"values": item.get("embedding", [])}
                    for item in data
                    if isinstance(item, dict)
                ]
            }
        if "b64_json" in data[0]:
            return {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": item.get("b64_json", ""),
                                    }
                                }
                                for item in data
                                if isinstance(item, dict)
                            ],
                        },
                        "finishReason": "STOP",
                        "index": 0,
                    }
                ]
            }

    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message", {})
        parts: list[Dict[str, Any]] = []
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        parts.append({"text": block["text"]})
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function")
                    if not isinstance(fn, dict) or not isinstance(fn.get("name"), str):
                        continue
                    parts.append(
                        {
                            "functionCall": {
                                "name": fn["name"],
                                "args": _safe_json_loads(fn.get("arguments")),
                            }
                        }
                    )
        usage = body.get("usage", {})
        usage_meta = {
            "promptTokenCount": usage.get("prompt_tokens", 0),
            "candidatesTokenCount": usage.get("completion_tokens", 0),
            "totalTokenCount": usage.get(
                "total_tokens",
                (usage.get("prompt_tokens", 0) or 0)
                + (usage.get("completion_tokens", 0) or 0),
            ),
        }
        return {
            "candidates": [
                {
                    "content": {"role": "model", "parts": parts or [{"text": ""}]},
                    "finishReason": _map_openai_finish_reason_to_gemini(
                        first.get("finish_reason")
                    ),
                    "index": 0,
                }
            ],
            "usageMetadata": usage_meta,
            "modelVersion": target_model,
            "responseId": body.get("id") or f"resp_{uuid.uuid4().hex}",
        }

    return body


class SDKRequestConverter(IRequestConverter):
    """
    Request converter using llm_api_converter SDK.

    Uses the SDK's IR-based conversion pipeline.
    """

    def __init__(self, source: Protocol, target: Protocol):
        self._source = source
        self._target = target
        self._path_mapping = {
            Protocol.OPENAI: "/v1/chat/completions",
            Protocol.OPENAI_RESPONSES: "/v1/responses",
            Protocol.ANTHROPIC: "/v1/messages",
            Protocol.GEMINI: "/v1beta/models/{model}:generateContent",
        }

    @property
    def source_protocol(self) -> Protocol:
        return self._source

    @property
    def target_protocol(self) -> Protocol:
        return self._target

    def get_target_path(self, source_path: str) -> str:
        return self._path_mapping.get(self._target, source_path)

    def convert(
        self,
        path: str,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert request using SDK."""
        if not _HAS_SDK:
            raise ProtocolConversionError(
                message=f"llm_api_converter SDK not available: {_SDK_IMPORT_ERROR}",
                code="sdk_unavailable",
            )

        options = options or {}

        try:
            if self._source == Protocol.GEMINI:
                openai_result = _gemini_request_to_openai_chat(path, body, target_model)
                if self._target == Protocol.OPENAI:
                    return openai_result

                sdk_target = _protocol_to_sdk(self._target)
                converted = convert_request(
                    SDKProtocol.OPENAI_CHAT,
                    sdk_target,
                    openai_result.body,
                    stream=bool(openai_result.body.get("stream")),
                    options=options,
                )
                converted["model"] = target_model
                target_path = self.get_target_path(path)
                return ConversionResult(path=target_path, body=converted)

            if self._target == Protocol.GEMINI:
                if self._source == Protocol.OPENAI and path == _OPENAI_EMBEDDINGS_PATH:
                    return _openai_embeddings_to_gemini_request(body, target_model)
                if self._source == Protocol.OPENAI and path in _OPENAI_IMAGE_PATHS:
                    return _openai_images_to_gemini_request(body, target_model, path)

                if self._source == Protocol.OPENAI:
                    if path == _OPENAI_COMPLETIONS_PATH:
                        openai_body = _openai_completions_to_chat_request(body)
                    elif path in (_OPENAI_CHAT_PATH,):
                        openai_body = _normalize_openai_tooling_fields(body)
                    elif path == _OPENAI_RESPONSES_PATH:
                        from app.common.openai_responses import (
                            responses_request_to_chat_completions,
                        )

                        openai_body = responses_request_to_chat_completions(body)
                    else:
                        raise ValidationError(
                            "path",
                            f"Unsupported OpenAI endpoint for Gemini conversion: {path}",
                        )
                elif self._source == Protocol.OPENAI_RESPONSES:
                    from app.common.openai_responses import (
                        responses_request_to_chat_completions,
                    )

                    openai_body = responses_request_to_chat_completions(body)
                elif self._source == Protocol.ANTHROPIC:
                    openai_body = convert_request(
                        SDKProtocol.ANTHROPIC_MESSAGES,
                        SDKProtocol.OPENAI_CHAT,
                        body,
                        stream=bool(body.get("stream")),
                        options=options,
                    )
                else:
                    raise ValidationError(
                        "source_protocol",
                        f"Unsupported source protocol for Gemini conversion: {self._source.value}",
                    )

                openai_body["model"] = target_model
                return _openai_chat_to_gemini_request(openai_body, target_model)

            # Normalize OpenAI request
            if self._source == Protocol.OPENAI:
                body = _normalize_openai_tooling_fields(body)
            elif self._source == Protocol.OPENAI_RESPONSES:
                body = _normalize_openai_responses_tooling_fields(body)

            # Determine if streaming
            stream = body.get("stream", False)

            # Handle max_tokens for Anthropic target
            if self._target == Protocol.ANTHROPIC:
                body = self._ensure_max_tokens_for_anthropic(body)

            # Remove stream_options and include_usage when streaming to OpenAI or OpenAI Responses
            # These parameters are not supported by all providers and can cause errors
            if stream and self._target in (Protocol.OPENAI, Protocol.OPENAI_RESPONSES):
                body = self._remove_unsupported_stream_params(body)

            # Use SDK conversion
            sdk_source = _protocol_to_sdk(self._source)
            sdk_target = _protocol_to_sdk(self._target)

            converted = convert_request(
                sdk_source,
                sdk_target,
                body,
                stream=stream,
                options=options,
            )

            # Set target model
            converted["model"] = target_model

            # Get target path
            target_path = self.get_target_path(path)

            return ConversionResult(path=target_path, body=converted)

        except Exception as e:
            logger.error(
                "Request conversion failed: %s -> %s, error: %s",
                self._source.value,
                self._target.value,
                str(e),
            )
            raise ProtocolConversionError(
                message=f"Request conversion failed: {str(e)}",
                code="conversion_error",
                source_protocol=self._source.value,
                target_protocol=self._target.value,
            ) from e

    def _ensure_max_tokens_for_anthropic(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure max_tokens is set when converting to Anthropic protocol.

        Different source protocols use different field names:
        - OpenAI Chat: max_tokens or max_completion_tokens
        - OpenAI Responses: max_output_tokens
        - Anthropic: max_tokens

        We need to ensure the appropriate field exists for the source protocol
        so the SDK decoder can read it properly.
        """
        body = copy.deepcopy(body)

        if self._source == Protocol.OPENAI_RESPONSES:
            # For OpenAI Responses, ensure max_output_tokens is set
            if body.get("max_output_tokens") is None:
                body["max_output_tokens"] = 4096
        elif self._source == Protocol.OPENAI:
            # For OpenAI Chat, ensure max_tokens or max_completion_tokens is set
            if (
                body.get("max_tokens") is None
                and body.get("max_completion_tokens") is None
            ):
                body["max_tokens"] = 4096
        elif self._source == Protocol.ANTHROPIC:
            # For Anthropic source, ensure max_tokens is set
            if body.get("max_tokens") is None:
                if body.get("max_completion_tokens") is not None:
                    body["max_tokens"] = body["max_completion_tokens"]
                else:
                    body["max_tokens"] = 4096

        return body

    def _remove_unsupported_stream_params(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove stream_options and include_usage from request body.

        Some OpenAI-compatible providers do not support these parameters
        and will return an error like "Unknown parameter: 'include_usage'".
        """
        body = copy.deepcopy(body)

        # Remove stream_options (contains include_usage)
        if "stream_options" in body:
            del body["stream_options"]

        # Remove top-level include_usage (some clients send it at top level)
        if "include_usage" in body:
            del body["include_usage"]

        return body


class SDKResponseConverter(IResponseConverter):
    """
    Response converter using llm_api_converter SDK.

    Uses the SDK's IR-based conversion pipeline.
    """

    def __init__(self, source: Protocol, target: Protocol):
        self._source = source
        self._target = target

    @property
    def source_protocol(self) -> Protocol:
        return self._source

    @property
    def target_protocol(self) -> Protocol:
        return self._target

    def convert(
        self,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert response using SDK."""
        if not _HAS_SDK:
            raise ProtocolConversionError(
                message=f"llm_api_converter SDK not available: {_SDK_IMPORT_ERROR}",
                code="sdk_unavailable",
            )

        options = options or {}

        try:
            if self._source == Protocol.GEMINI:
                openai_body = _gemini_response_to_openai(body, target_model)
                if self._target == Protocol.OPENAI:
                    return openai_body

                sdk_target = _protocol_to_sdk(self._target)
                return convert_response(
                    SDKProtocol.OPENAI_CHAT,
                    sdk_target,
                    openai_body,
                    options=options,
                )

            if self._target == Protocol.GEMINI:
                if self._source == Protocol.OPENAI:
                    return _openai_response_to_gemini(body, target_model)

                sdk_source = _protocol_to_sdk(self._source)
                openai_body = convert_response(
                    sdk_source,
                    SDKProtocol.OPENAI_CHAT,
                    body,
                    options=options,
                )
                return _openai_response_to_gemini(openai_body, target_model)

            sdk_source = _protocol_to_sdk(self._source)
            sdk_target = _protocol_to_sdk(self._target)

            converted = convert_response(
                sdk_source,
                sdk_target,
                body,
                options=options,
            )

            return converted

        except Exception as e:
            logger.error(
                "Response conversion failed: %s -> %s, error: %s",
                self._source.value,
                self._target.value,
                str(e),
            )
            raise ProtocolConversionError(
                message=f"Response conversion failed: {str(e)}",
                code="conversion_error",
                source_protocol=self._source.value,
                target_protocol=self._target.value,
            ) from e


class SDKStreamConverter(IStreamConverter):
    """
    Stream converter using llm_api_converter SDK.

    Handles SSE stream conversion with stateful tracking.
    """

    def __init__(self, source: Protocol, target: Protocol):
        self._source = source
        self._target = target

    @property
    def source_protocol(self) -> Protocol:
        return self._source

    @property
    def target_protocol(self) -> Protocol:
        return self._target

    async def convert(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Convert stream using SDK."""
        if not _HAS_SDK:
            raise ProtocolConversionError(
                message=f"llm_api_converter SDK not available: {_SDK_IMPORT_ERROR}",
                code="sdk_unavailable",
            )

        # Use specialized converters for each direction
        if self._source == Protocol.ANTHROPIC and self._target == Protocol.OPENAI:
            async for chunk in self._convert_anthropic_to_openai(upstream, model):
                yield chunk
        elif self._source == Protocol.OPENAI and self._target == Protocol.ANTHROPIC:
            async for chunk in self._convert_openai_to_anthropic(upstream, model):
                yield chunk
        elif (
            self._source == Protocol.OPENAI_RESPONSES
            and self._target == Protocol.OPENAI
        ):
            async for chunk in self._convert_openai_responses_to_openai(
                upstream, model
            ):
                yield chunk
        elif (
            self._source == Protocol.OPENAI
            and self._target == Protocol.OPENAI_RESPONSES
        ):
            input_tokens = options.get("input_tokens") if options else None
            async for chunk in self._convert_openai_to_openai_responses(
                upstream, model, input_tokens=input_tokens
            ):
                yield chunk
        elif (
            self._source == Protocol.ANTHROPIC
            and self._target == Protocol.OPENAI_RESPONSES
        ):
            # Chain: Anthropic -> OpenAI Chat -> OpenAI Responses
            openai_stream = self._convert_anthropic_to_openai(upstream, model)
            input_tokens = options.get("input_tokens") if options else None
            async for chunk in self._convert_openai_to_openai_responses(
                openai_stream, model, input_tokens=input_tokens
            ):
                yield chunk
        elif (
            self._source == Protocol.OPENAI_RESPONSES
            and self._target == Protocol.ANTHROPIC
        ):
            # Chain: OpenAI Responses -> OpenAI Chat -> Anthropic
            openai_stream = self._convert_openai_responses_to_openai(upstream, model)
            async for chunk in self._convert_openai_to_anthropic(openai_stream, model):
                yield chunk
        elif self._source == Protocol.GEMINI and self._target == Protocol.OPENAI:
            async for chunk in self._convert_gemini_to_openai(upstream, model):
                yield chunk
        elif self._source == Protocol.OPENAI and self._target == Protocol.GEMINI:
            async for chunk in self._convert_openai_to_gemini(upstream, model):
                yield chunk
        elif (
            self._source == Protocol.GEMINI
            and self._target == Protocol.OPENAI_RESPONSES
        ):
            openai_stream = self._convert_gemini_to_openai(upstream, model)
            input_tokens = options.get("input_tokens") if options else None
            async for chunk in self._convert_openai_to_openai_responses(
                openai_stream, model, input_tokens=input_tokens
            ):
                yield chunk
        elif (
            self._source == Protocol.OPENAI_RESPONSES
            and self._target == Protocol.GEMINI
        ):
            openai_stream = self._convert_openai_responses_to_openai(upstream, model)
            async for chunk in self._convert_openai_to_gemini(openai_stream, model):
                yield chunk
        elif self._source == Protocol.GEMINI and self._target == Protocol.ANTHROPIC:
            openai_stream = self._convert_gemini_to_openai(upstream, model)
            async for chunk in self._convert_openai_to_anthropic(openai_stream, model):
                yield chunk
        elif self._source == Protocol.ANTHROPIC and self._target == Protocol.GEMINI:
            openai_stream = self._convert_anthropic_to_openai(upstream, model)
            async for chunk in self._convert_openai_to_gemini(openai_stream, model):
                yield chunk
        else:
            # Generic fallback using SDK
            async for chunk in self._generic_stream_conversion(upstream, model):
                yield chunk

    async def _convert_anthropic_to_openai(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert Anthropic stream to OpenAI format."""
        decoder = _SSEDecoder()
        response_id: Optional[str] = None
        sent_role = False
        current_tool_id: Optional[str] = None
        current_tool_name: Optional[str] = None
        current_tool_index = 0
        done = False
        final_usage: Optional[Dict[str, Any]] = None

        async for chunk in upstream:
            for payload in decoder.feed(chunk):
                if not payload:
                    continue
                if payload.strip() == "[DONE]":
                    continue

                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                event_type = data.get("type")

                if event_type == "message_start":
                    message = data.get("message", {})
                    if isinstance(message, dict):
                        response_id = message.get("id") or response_id
                        # Extract initial usage from message_start
                        initial_usage = message.get("usage")
                        if isinstance(initial_usage, dict):
                            input_tokens = initial_usage.get("input_tokens", 0)
                            # Initialize final_usage with input_tokens from message_start
                            final_usage = {
                                "prompt_tokens": input_tokens,
                                "completion_tokens": 0,
                                "total_tokens": input_tokens,
                            }
                    continue

                if event_type == "content_block_start":
                    content_block = data.get("content_block", {})
                    if isinstance(content_block, dict):
                        block_type = content_block.get("type")
                        if block_type == "text":
                            text = content_block.get("text") or ""
                            if text:
                                delta: Dict[str, Any] = {"content": text}
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(
                                        response_id, model, delta, None
                                    )
                                )
                        elif block_type == "tool_use":
                            current_tool_id = content_block.get("id")
                            current_tool_name = content_block.get("name")
                            if isinstance(data.get("index"), int):
                                current_tool_index = data["index"]
                            tool_args = content_block.get("input")
                            if isinstance(tool_args, dict):
                                arguments = json.dumps(tool_args, ensure_ascii=False)
                            elif isinstance(tool_args, str):
                                arguments = tool_args
                            else:
                                arguments = "{}"
                            delta = {
                                "tool_calls": [
                                    {
                                        "index": current_tool_index,
                                        "id": current_tool_id,
                                        "type": "function",
                                        "function": {
                                            "name": current_tool_name,
                                            "arguments": arguments,
                                        },
                                    }
                                ]
                            }
                            if not sent_role:
                                delta["role"] = "assistant"
                                sent_role = True
                            yield _encode_sse_json(
                                self._create_openai_chunk(
                                    response_id, model, delta, None
                                )
                            )
                    continue

                if event_type == "content_block_delta":
                    delta_obj = data.get("delta")
                    if isinstance(delta_obj, dict):
                        delta_type = delta_obj.get("type")
                        if delta_type == "text_delta":
                            text = delta_obj.get("text") or ""
                            if text:
                                delta = {"content": text}
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(
                                        response_id, model, delta, None
                                    )
                                )
                        elif delta_type == "input_json_delta":
                            partial_json = delta_obj.get("partial_json") or ""
                            if partial_json:
                                delta = {
                                    "tool_calls": [
                                        {
                                            "index": current_tool_index,
                                            "id": current_tool_id,
                                            "type": "function",
                                            "function": {
                                                "name": current_tool_name,
                                                "arguments": partial_json,
                                            },
                                        }
                                    ]
                                }
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(
                                        response_id, model, delta, None
                                    )
                                )
                    continue

                if event_type == "message_delta":
                    delta_dict = data.get("delta")
                    stop_reason = None
                    if isinstance(delta_dict, dict):
                        stop_reason = delta_dict.get("stop_reason")
                    finish_reason = _map_anthropic_to_openai_finish_reason(stop_reason)

                    # Extract usage from message_delta
                    usage_data = data.get("usage")
                    if isinstance(usage_data, dict):
                        # Convert Anthropic usage format to OpenAI format
                        input_tokens = usage_data.get("input_tokens", 0)
                        output_tokens = usage_data.get("output_tokens", 0)
                        final_usage = {
                            "prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                        }
                        # Include cache tokens if available
                        if "cache_creation_input_tokens" in usage_data:
                            final_usage["prompt_tokens_details"] = {
                                "cached_tokens": usage_data.get(
                                    "cache_read_input_tokens", 0
                                ),
                            }

                    yield _encode_sse_json(
                        self._create_openai_chunk(response_id, model, {}, finish_reason)
                    )

                    # Emit usage chunk before [DONE] (OpenAI format with empty choices)
                    if final_usage:
                        usage_chunk = {
                            "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [],
                            "usage": final_usage,
                        }
                        yield _encode_sse_json(usage_chunk)

                    yield _encode_sse_data("[DONE]")
                    done = True
                    continue

                if event_type == "message_stop":
                    if not done:
                        yield _encode_sse_data("[DONE]")
                        done = True
                    continue

        if not done:
            yield _encode_sse_data("[DONE]")

    async def _convert_openai_to_anthropic(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert OpenAI stream to Anthropic format."""
        decoder = _SSEDecoder()
        sent_message_start = False
        sent_message_stop = False

        # State tracking
        current_block_index = 0
        # current_block_type: "text" | "tool_use" | None
        current_block_type: Optional[str] = None
        # Track current tool call by id (more reliable than index which may be missing)
        current_tool_call_id: Optional[str] = None

        async for chunk in upstream:
            for payload in decoder.feed(chunk):
                if not payload:
                    continue
                if payload.strip() == "[DONE]":
                    continue

                if not sent_message_start:
                    sent_message_start = True
                    yield _encode_sse_json(
                        {
                            "type": "message_start",
                            "message": {
                                "id": f"msg_{uuid.uuid4().hex}",
                                "type": "message",
                                "role": "assistant",
                                "content": [],
                                "model": model,
                                "stop_reason": None,
                                "stop_sequence": None,
                                "usage": {"input_tokens": 0, "output_tokens": 0},
                            },
                        },
                        event="message_start",
                    )

                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason")

                # Handle Text Content
                content = delta.get("content")
                if content is not None:
                    # If we were in a tool block or this is the first block, start text block
                    if current_block_type != "text":
                        if current_block_type is not None:
                            # Close previous block
                            yield _encode_sse_json(
                                {
                                    "type": "content_block_stop",
                                    "index": current_block_index,
                                },
                                event="content_block_stop",
                            )
                            current_block_index += 1

                        # Start new text block
                        yield _encode_sse_json(
                            {
                                "type": "content_block_start",
                                "index": current_block_index,
                                "content_block": {"type": "text", "text": ""},
                            },
                            event="content_block_start",
                        )
                        current_block_type = "text"
                        current_tool_call_id = None

                    yield _encode_sse_json(
                        {
                            "type": "content_block_delta",
                            "index": current_block_index,
                            "delta": {"type": "text_delta", "text": content},
                        },
                        event="content_block_delta",
                    )

                # Handle Tool Calls
                tool_calls = delta.get("tool_calls")
                if tool_calls:
                    for tool_call in tool_calls:
                        t_id = tool_call.get("id")
                        t_name = tool_call.get("function", {}).get("name", "")

                        # Detect if this is a new tool call:
                        # 1. If we're not currently in a tool_use block, it's new
                        # 2. If the tool_call has an id and it differs from current, it's new
                        # Note: Some providers (like Gemini) don't provide index field
                        is_new_tool_call = False
                        if current_block_type != "tool_use":
                            is_new_tool_call = True
                        elif t_id is not None and t_id != current_tool_call_id:
                            is_new_tool_call = True

                        if is_new_tool_call:
                            if current_block_type is not None:
                                # Close previous block
                                yield _encode_sse_json(
                                    {
                                        "type": "content_block_stop",
                                        "index": current_block_index,
                                    },
                                    event="content_block_stop",
                                )
                                current_block_index += 1

                            # Start new tool block
                            yield _encode_sse_json(
                                {
                                    "type": "content_block_start",
                                    "index": current_block_index,
                                    "content_block": {
                                        "type": "tool_use",
                                        "id": t_id or "",
                                        "name": t_name,
                                        "input": {},  # Empty input for now
                                    },
                                },
                                event="content_block_start",
                            )
                            current_block_type = "tool_use"
                            current_tool_call_id = t_id

                        # Handle arguments
                        args = tool_call.get("function", {}).get("arguments")
                        if args:
                            yield _encode_sse_json(
                                {
                                    "type": "content_block_delta",
                                    "index": current_block_index,
                                    "delta": {
                                        "type": "input_json_delta",
                                        "partial_json": args,
                                    },
                                },
                                event="content_block_delta",
                            )

                # Handle Finish Reason
                if finish_reason:
                    # Close any open block
                    if current_block_type is not None:
                        yield _encode_sse_json(
                            {
                                "type": "content_block_stop",
                                "index": current_block_index,
                            },
                            event="content_block_stop",
                        )

                    stop_reason = _map_openai_to_anthropic_finish_reason(finish_reason)
                    yield _encode_sse_json(
                        {
                            "type": "message_delta",
                            "delta": {"stop_reason": stop_reason},
                            "usage": {"output_tokens": 0},
                        },
                        event="message_delta",
                    )

                    if not sent_message_stop:
                        sent_message_stop = True
                        yield _encode_sse_json(
                            {"type": "message_stop"}, event="message_stop"
                        )

        if not sent_message_stop:
            sent_message_stop = True
            yield _encode_sse_json({"type": "message_stop"}, event="message_stop")

    async def _convert_openai_responses_to_openai(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert OpenAI Responses stream to OpenAI Chat format."""
        # Import from openai_responses module
        from app.common.openai_responses import responses_sse_to_chat_completions_sse

        async for chunk in responses_sse_to_chat_completions_sse(
            upstream=upstream, model=model
        ):
            yield chunk

    async def _convert_openai_to_openai_responses(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
        input_tokens: Optional[int] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Convert OpenAI Chat stream to OpenAI Responses format."""
        from app.common.openai_responses import chat_completions_sse_to_responses_sse

        async for chunk in chat_completions_sse_to_responses_sse(
            upstream=upstream, model=model, input_tokens=input_tokens
        ):
            yield chunk

    async def _convert_gemini_to_openai(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        decoder = _SSEDecoder()
        sent_role = False
        response_id = f"chatcmpl-{uuid.uuid4().hex}"
        done = False

        async for chunk in upstream:
            for payload in decoder.feed(chunk):
                if not payload or payload.strip() == "[DONE]":
                    continue
                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                candidates = data.get("candidates")
                if isinstance(candidates, list) and candidates:
                    cand = candidates[0] if isinstance(candidates[0], dict) else {}
                    content = cand.get("content", {})
                    parts = content.get("parts", []) if isinstance(content, dict) else []
                    if isinstance(parts, list):
                        for part in parts:
                            if not isinstance(part, dict):
                                continue
                            if isinstance(part.get("text"), str) and part.get("text"):
                                delta: Dict[str, Any] = {"content": part["text"]}
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(response_id, model, delta, None)
                                )
                            fc = part.get("functionCall")
                            if isinstance(fc, dict) and isinstance(fc.get("name"), str):
                                args = fc.get("args")
                                if not isinstance(args, str):
                                    args = json.dumps(args or {}, ensure_ascii=False)
                                delta = {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": f"call_{uuid.uuid4().hex}",
                                            "type": "function",
                                            "function": {
                                                "name": fc["name"],
                                                "arguments": args,
                                            },
                                        }
                                    ]
                                }
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(response_id, model, delta, None)
                                )

                    finish_reason = _map_gemini_finish_reason_to_openai(
                        cand.get("finishReason")
                    )
                    if finish_reason:
                        yield _encode_sse_json(
                            self._create_openai_chunk(
                                response_id, model, {}, finish_reason
                            )
                        )

                usage = data.get("usageMetadata")
                if isinstance(usage, dict):
                    usage_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [],
                        "usage": _gemini_usage_to_openai(usage),
                    }
                    yield _encode_sse_json(usage_chunk)

        if not done:
            done = True
            yield _encode_sse_data("[DONE]")

    async def _convert_openai_to_gemini(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        decoder = _SSEDecoder()

        async for chunk in upstream:
            for payload in decoder.feed(chunk):
                if not payload:
                    continue
                if payload.strip() == "[DONE]":
                    continue
                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                choices = data.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice = choices[0] if isinstance(choices[0], dict) else {}
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason")

                parts: list[Dict[str, Any]] = []
                if isinstance(delta, dict):
                    text = delta.get("content")
                    if isinstance(text, str) and text:
                        parts.append({"text": text})
                    tool_calls = delta.get("tool_calls")
                    if isinstance(tool_calls, list):
                        for tool_call in tool_calls:
                            if not isinstance(tool_call, dict):
                                continue
                            fn = tool_call.get("function")
                            if not isinstance(fn, dict) or not isinstance(
                                fn.get("name"), str
                            ):
                                continue
                            args = _safe_json_loads(fn.get("arguments"))
                            if not isinstance(args, dict):
                                args = {"value": args}
                            parts.append(
                                {
                                    "functionCall": {
                                        "name": fn["name"],
                                        "args": args,
                                    }
                                }
                            )

                gemini_chunk: Dict[str, Any] = {
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": parts or [{"text": ""}],
                            },
                            "index": 0,
                        }
                    ]
                }
                mapped_finish_reason = _map_openai_finish_reason_to_gemini(finish_reason)
                if mapped_finish_reason:
                    gemini_chunk["candidates"][0]["finishReason"] = mapped_finish_reason

                usage = data.get("usage")
                if isinstance(usage, dict):
                    gemini_chunk["usageMetadata"] = {
                        "promptTokenCount": usage.get("prompt_tokens", 0),
                        "candidatesTokenCount": usage.get("completion_tokens", 0),
                        "totalTokenCount": usage.get(
                            "total_tokens",
                            (usage.get("prompt_tokens", 0) or 0)
                            + (usage.get("completion_tokens", 0) or 0),
                        ),
                    }

                yield _encode_sse_json(gemini_chunk)

    async def _generic_stream_conversion(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Generic stream conversion using SDK (fallback)."""
        # For unsupported combinations, pass through
        async for chunk in upstream:
            yield chunk

    def _create_openai_chunk(
        self,
        response_id: Optional[str],
        model: str,
        delta: Dict[str, Any],
        finish_reason: Optional[str],
    ) -> Dict[str, Any]:
        """Create an OpenAI chat completion chunk."""
        return {
            "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }


class _SSEDecoder:
    """SSE decoder for streaming responses."""

    def __init__(self):
        self._buffer = ""

    def feed(self, chunk: bytes) -> List[str]:
        """Feed bytes and return complete SSE data payloads."""
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return []

        self._buffer += text
        payloads = []

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()

            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    payloads.append(data)

        return payloads


def _encode_sse_data(payload: str) -> bytes:
    """Encode string as SSE data line."""
    return f"data: {payload}\n\n".encode("utf-8")


def _encode_sse_json(obj: Dict[str, Any], event: Optional[str] = None) -> bytes:
    """Encode dict as SSE JSON data line."""
    if event:
        return f"event: {event}\n".encode("utf-8") + _encode_sse_data(
            json.dumps(obj, ensure_ascii=False)
        )
    return _encode_sse_data(json.dumps(obj, ensure_ascii=False))


def _map_anthropic_to_openai_finish_reason(stop_reason: Optional[str]) -> str:
    """Map Anthropic stop reason to OpenAI finish reason."""
    if not stop_reason:
        return "stop"
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "stop_sequence": "stop",
    }
    return mapping.get(stop_reason, "stop")


def _map_openai_to_anthropic_finish_reason(finish_reason: Optional[str]) -> str:
    """Map OpenAI finish reason to Anthropic stop reason."""
    if not finish_reason:
        return "end_turn"
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }
    return mapping.get(finish_reason, "end_turn")
