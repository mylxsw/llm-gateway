# Field Mapping Tables

Comprehensive field-by-field mapping for all 6 conversion directions.

## 1. Request Field Mappings

### 1.1 OpenAI Classic → OpenAI Responses

| OpenAI Classic Field | OpenAI Responses Field | Transformation |
|---------------------|----------------------|----------------|
| `model` | `model` | Direct copy |
| `messages` | `input` | Convert message array to item array |
| `messages[role=system].content` | `instructions` | Extract and concatenate |
| `messages[role=developer].content` | `instructions` | Extract and concatenate |
| `max_tokens` | `max_output_tokens` | Direct copy |
| `max_completion_tokens` | `max_output_tokens` | Direct copy |
| `temperature` | `temperature` | Direct copy |
| `top_p` | `top_p` | Direct copy |
| `stop` | `stop` | Ensure array format |
| `stream` | `stream` | Direct copy |
| `seed` | `seed` | Direct copy |
| `user` | `user` | Direct copy |
| `tools` | `tools` | Transform structure (see below) |
| `tool_choice` | `tool_choice` | Transform structure |
| `parallel_tool_calls` | N/A | Store in metadata |
| `response_format` | `text.format` | Transform structure |
| `logprobs` | N/A | Store in metadata |
| `top_logprobs` | N/A | Store in metadata |
| `n` | N/A | Store in metadata (not supported) |
| `presence_penalty` | N/A | Store in metadata |
| `frequency_penalty` | N/A | Store in metadata |
| `stream_options` | N/A | Handle separately |

**Tool Transformation:**
```python
# OpenAI Classic
{"type": "function", "function": {"name": "x", "description": "y", "parameters": {...}}}
# → OpenAI Responses
{"type": "function", "name": "x", "description": "y", "parameters": {...}}
```

### 1.2 OpenAI Classic → Anthropic Messages

| OpenAI Classic Field | Anthropic Messages Field | Transformation |
|---------------------|-------------------------|----------------|
| `model` | `model` | Map model names |
| `messages` | `messages` + `system` | Extract system messages |
| `messages[role=system].content` | `system` | Extract to system param |
| `messages[role=developer].content` | `system` | Extract to system param |
| `max_tokens` | `max_tokens` | Direct copy (required in Anthropic) |
| `max_completion_tokens` | `max_tokens` | Direct copy |
| `temperature` | `temperature` | Clamp to 0-1 range |
| `top_p` | `top_p` | Direct copy |
| `stop` | `stop_sequences` | Ensure array format |
| `stream` | `stream` | Direct copy |
| `seed` | N/A | Store in metadata |
| `user` | `metadata.user_id` | Move to metadata |
| `tools` | `tools` | Transform structure (see below) |
| `tool_choice` | `tool_choice` | Transform structure |
| `parallel_tool_calls=false` | `tool_choice.disable_parallel_tool_use=true` | Invert logic |
| `response_format` | N/A | Store in metadata (not supported) |
| `logprobs` | N/A | Store in metadata |
| `n` | N/A | Not supported |
| `presence_penalty` | N/A | Store in metadata |
| `frequency_penalty` | N/A | Store in metadata |

**Tool Transformation:**
```python
# OpenAI Classic
{"type": "function", "function": {"name": "x", "description": "y", "parameters": {...}}}
# → Anthropic Messages
{"name": "x", "description": "y", "input_schema": {...}}
```

**Tool Choice Transformation:**
```python
# OpenAI Classic → Anthropic Messages
"auto" → {"type": "auto"}
"none" → {"type": "none"}
"required" → {"type": "any"}
{"type": "function", "function": {"name": "x"}} → {"type": "tool", "name": "x"}
```

### 1.3 OpenAI Responses → OpenAI Classic

| OpenAI Responses Field | OpenAI Classic Field | Transformation |
|-----------------------|---------------------|----------------|
| `model` | `model` | Direct copy |
| `input` (string) | `messages` | Wrap in user message |
| `input` (array) | `messages` | Convert items to messages |
| `instructions` | `messages` (prepend) | Create system message |
| `max_output_tokens` | `max_tokens` | Direct copy |
| `temperature` | `temperature` | Direct copy |
| `top_p` | `top_p` | Direct copy |
| `stop` | `stop` | Direct copy |
| `stream` | `stream` | Direct copy |
| `seed` | `seed` | Direct copy |
| `user` | `user` | Direct copy |
| `tools` | `tools` | Transform structure (see below) |
| `tool_choice` | `tool_choice` | Transform structure |
| `text.format` | `response_format` | Transform structure |
| `previous_response_id` | N/A | Expand history (requires API call or stored data) |
| `store` | `store` | Direct copy |

**Tool Transformation:**
```python
# OpenAI Responses
{"type": "function", "name": "x", "description": "y", "parameters": {...}}
# → OpenAI Classic
{"type": "function", "function": {"name": "x", "description": "y", "parameters": {...}}}
```

### 1.4 OpenAI Responses → Anthropic Messages

| OpenAI Responses Field | Anthropic Messages Field | Transformation |
|-----------------------|-------------------------|----------------|
| `model` | `model` | Map model names |
| `input` (string) | `messages` | Wrap in user message |
| `input` (array) | `messages` + `system` | Convert and extract system |
| `instructions` | `system` | Direct use |
| `max_output_tokens` | `max_tokens` | Direct copy |
| `temperature` | `temperature` | Clamp to 0-1 |
| `top_p` | `top_p` | Direct copy |
| `stop` | `stop_sequences` | Direct copy |
| `stream` | `stream` | Direct copy |
| `seed` | N/A | Store in metadata |
| `user` | `metadata.user_id` | Move to metadata |
| `tools` | `tools` | Transform structure |
| `tool_choice` | `tool_choice` | Transform structure |
| `text.format` | N/A | Store in metadata |

### 1.5 Anthropic Messages → OpenAI Classic

| Anthropic Messages Field | OpenAI Classic Field | Transformation |
|-------------------------|---------------------|----------------|
| `model` | `model` | Map model names |
| `messages` | `messages` | Transform content blocks |
| `system` | `messages` (prepend) | Create system message |
| `max_tokens` | `max_tokens` | Direct copy |
| `temperature` | `temperature` | Scale 0-1 → 0-2 if needed |
| `top_p` | `top_p` | Direct copy |
| `top_k` | N/A | Store in metadata |
| `stop_sequences` | `stop` | Direct copy |
| `stream` | `stream` | Direct copy |
| `metadata.user_id` | `user` | Direct copy |
| `tools` | `tools` | Transform structure (see below) |
| `tool_choice` | `tool_choice` | Transform structure |
| `thinking` | N/A | Handle via model selection |

**Tool Transformation:**
```python
# Anthropic Messages
{"name": "x", "description": "y", "input_schema": {...}}
# → OpenAI Classic
{"type": "function", "function": {"name": "x", "description": "y", "parameters": {...}}}
```

**Tool Choice Transformation:**
```python
# Anthropic Messages → OpenAI Classic
{"type": "auto"} → "auto"
{"type": "none"} → "none"
{"type": "any"} → "required"
{"type": "tool", "name": "x"} → {"type": "function", "function": {"name": "x"}}
```

### 1.6 Anthropic Messages → OpenAI Responses

| Anthropic Messages Field | OpenAI Responses Field | Transformation |
|-------------------------|----------------------|----------------|
| `model` | `model` | Map model names |
| `messages` | `input` | Transform to items |
| `system` | `instructions` | Direct use |
| `max_tokens` | `max_output_tokens` | Direct copy |
| `temperature` | `temperature` | Direct copy |
| `top_p` | `top_p` | Direct copy |
| `top_k` | N/A | Store in metadata |
| `stop_sequences` | `stop` | Direct copy |
| `stream` | `stream` | Direct copy |
| `metadata.user_id` | `user` | Direct copy |
| `tools` | `tools` | Transform structure |
| `tool_choice` | `tool_choice` | Transform structure |

---

## 2. Response Field Mappings

### 2.1 OpenAI Classic → OpenAI Responses

| OpenAI Classic Field | OpenAI Responses Field | Transformation |
|---------------------|----------------------|----------------|
| `id` | `id` | Prefix change (chatcmpl → resp) |
| `object` | `object` | `"chat.completion"` → `"response"` |
| `created` | `created_at` | Direct copy |
| `model` | `model` | Direct copy |
| `choices[0].message.content` | `output[].content[].text` | Wrap in output item |
| `choices[0].message.tool_calls` | `output[]` (function_call items) | Transform structure |
| `choices[0].finish_reason` | `status` | Map values |
| `usage.prompt_tokens` | `usage.input_tokens` | Direct copy |
| `usage.completion_tokens` | `usage.output_tokens` | Direct copy |
| `usage.total_tokens` | `usage.total_tokens` | Direct copy |

**Finish Reason Mapping:**
```python
"stop" → "completed"
"length" → "incomplete"
"tool_calls" → "completed" (with function_call in output)
"content_filter" → "incomplete"
```

### 2.2 OpenAI Classic → Anthropic Messages

| OpenAI Classic Field | Anthropic Messages Field | Transformation |
|---------------------|-------------------------|----------------|
| `id` | `id` | Prefix change (chatcmpl → msg) |
| `object` | `type` | `"chat.completion"` → `"message"` |
| `model` | `model` | Direct copy |
| `choices[0].message.content` | `content[0].text` | Wrap in text block |
| `choices[0].message.tool_calls` | `content[]` (tool_use blocks) | Transform structure |
| `choices[0].finish_reason` | `stop_reason` | Map values |
| `usage.prompt_tokens` | `usage.input_tokens` | Direct copy |
| `usage.completion_tokens` | `usage.output_tokens` | Direct copy |

**Tool Call Transformation:**
```python
# OpenAI Classic
{"id": "call_x", "type": "function", "function": {"name": "y", "arguments": "{...}"}}
# → Anthropic Messages
{"type": "tool_use", "id": "call_x", "name": "y", "input": {...}}  # Note: arguments parsed to input
```

### 2.3 OpenAI Responses → OpenAI Classic

| OpenAI Responses Field | OpenAI Classic Field | Transformation |
|-----------------------|---------------------|----------------|
| `id` | `id` | Prefix change (resp → chatcmpl) |
| `object` | `object` | `"response"` → `"chat.completion"` |
| `created_at` | `created` | Direct copy |
| `model` | `model` | Direct copy |
| `output[]` | `choices[0].message` | Aggregate output items |
| `status` | `choices[0].finish_reason` | Map values |
| `usage.input_tokens` | `usage.prompt_tokens` | Direct copy |
| `usage.output_tokens` | `usage.completion_tokens` | Direct copy |
| `usage.total_tokens` | `usage.total_tokens` | Direct copy |

### 2.4 OpenAI Responses → Anthropic Messages

| OpenAI Responses Field | Anthropic Messages Field | Transformation |
|-----------------------|-------------------------|----------------|
| `id` | `id` | Prefix change (resp → msg) |
| `object` | `type` | `"response"` → `"message"` |
| `model` | `model` | Direct copy |
| `output[]` | `content[]` | Transform items to blocks |
| `status` | `stop_reason` | Map values |
| `usage.input_tokens` | `usage.input_tokens` | Direct copy |
| `usage.output_tokens` | `usage.output_tokens` | Direct copy |

### 2.5 Anthropic Messages → OpenAI Classic

| Anthropic Messages Field | OpenAI Classic Field | Transformation |
|-------------------------|---------------------|----------------|
| `id` | `id` | Prefix change (msg → chatcmpl) |
| `type` | `object` | `"message"` → `"chat.completion"` |
| `model` | `model` | Direct copy |
| `content[]` | `choices[0].message` | Aggregate content blocks |
| `stop_reason` | `choices[0].finish_reason` | Map values |
| `usage.input_tokens` | `usage.prompt_tokens` | Direct copy |
| `usage.output_tokens` | `usage.completion_tokens` | Direct copy |

**Stop Reason Mapping:**
```python
"end_turn" → "stop"
"max_tokens" → "length"
"stop_sequence" → "stop"
"tool_use" → "tool_calls"
"refusal" → "content_filter"
```

### 2.6 Anthropic Messages → OpenAI Responses

| Anthropic Messages Field | OpenAI Responses Field | Transformation |
|-------------------------|----------------------|----------------|
| `id` | `id` | Prefix change (msg → resp) |
| `type` | `object` | `"message"` → `"response"` |
| `model` | `model` | Direct copy |
| `content[]` | `output[]` | Transform blocks to items |
| `stop_reason` | `status` | Map values |
| `usage.input_tokens` | `usage.input_tokens` | Direct copy |
| `usage.output_tokens` | `usage.output_tokens` | Direct copy |

---

## 3. Message/Content Block Mappings

### 3.1 User Message Content

| Source | Target | Transformation |
|--------|--------|----------------|
| OpenAI `{"type": "text", "text": "..."}` | Anthropic `{"type": "text", "text": "..."}` | Direct copy |
| OpenAI `{"type": "image_url", "image_url": {"url": "https://..."}}` | Anthropic `{"type": "image", "source": {"type": "url", "url": "..."}}` | Restructure |
| OpenAI `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}` | Anthropic `{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}` | Parse data URL |
| Anthropic `{"type": "image", "source": {"type": "url", "url": "..."}}` | OpenAI `{"type": "image_url", "image_url": {"url": "..."}}` | Restructure |
| Anthropic `{"type": "image", "source": {"type": "base64", ...}}` | OpenAI `{"type": "image_url", "image_url": {"url": "data:..."}}` | Create data URL |

### 3.2 Tool Result Content

| Source | Target | Transformation |
|--------|--------|----------------|
| OpenAI Classic `{"role": "tool", "tool_call_id": "x", "content": "..."}` | OpenAI Responses `{"type": "function_call_output", "call_id": "x", "output": "..."}` | Restructure |
| OpenAI Responses `{"type": "function_call_output", ...}` | Anthropic `{"type": "tool_result", "tool_use_id": "x", "content": "..."}` | Restructure |
| Anthropic `{"type": "tool_result", ...}` | OpenAI Classic `{"role": "tool", ...}` | Restructure |

---

## 4. Stream Event Mappings

### 4.1 OpenAI Classic → OpenAI Responses

| OpenAI Classic Event | OpenAI Responses Event |
|---------------------|----------------------|
| First chunk | `response.created`, `response.in_progress` |
| `delta.role` | `response.output_item.added` |
| `delta.content` | `response.text.delta` |
| `delta.tool_calls[].function.name` | `response.output_item.added` (function_call) |
| `delta.tool_calls[].function.arguments` | `response.function_call_arguments.delta` |
| `finish_reason` + `[DONE]` | `response.done` |

### 4.2 OpenAI Classic → Anthropic Messages

| OpenAI Classic Event | Anthropic Messages Event |
|---------------------|-------------------------|
| First chunk | `message_start` |
| `delta.content` (first) | `content_block_start` + `content_block_delta` |
| `delta.content` | `content_block_delta` |
| `delta.tool_calls` (first) | `content_block_start` (tool_use) |
| `delta.tool_calls[].function.arguments` | `content_block_delta` (input_json_delta) |
| Before `finish_reason` | `content_block_stop` |
| `finish_reason` | `message_delta` |
| `[DONE]` | `message_stop` |

### 4.3 Anthropic Messages → OpenAI Classic

| Anthropic Messages Event | OpenAI Classic Event |
|-------------------------|---------------------|
| `message_start` | First chunk with `delta.role` |
| `content_block_start` (text) | (wait for delta) |
| `content_block_delta` (text_delta) | Chunk with `delta.content` |
| `content_block_start` (tool_use) | Chunk with `delta.tool_calls[].id`, `function.name` |
| `content_block_delta` (input_json_delta) | Chunk with `delta.tool_calls[].function.arguments` |
| `message_delta` | Chunk with `finish_reason` |
| `message_stop` | `[DONE]` |

---

## 5. Error Mapping

### 5.1 Error Type Mapping

| HTTP | OpenAI Type | Anthropic Type | Normalized |
|------|-------------|----------------|------------|
| 400 | `invalid_request_error` | `invalid_request_error` | `invalid_request` |
| 401 | `authentication_error` | `authentication_error` | `authentication` |
| 403 | `permission_error` | `permission_error` | `permission` |
| 404 | `not_found_error` | `not_found_error` | `not_found` |
| 429 | `rate_limit_error` | `rate_limit_error` | `rate_limit` |
| 500 | `server_error` | `api_error` | `server_error` |
| 503 | `service_unavailable_error` | N/A | `service_unavailable` |
| 529 | N/A | `overloaded_error` | `overloaded` |

### 5.2 Error Response Transformation

**OpenAI → Anthropic:**
```python
# From
{"error": {"message": "...", "type": "invalid_request_error", "code": "..."}}
# To
{"type": "error", "error": {"type": "invalid_request_error", "message": "..."}}
```

**Anthropic → OpenAI:**
```python
# From
{"type": "error", "error": {"type": "invalid_request_error", "message": "..."}}
# To
{"error": {"message": "...", "type": "invalid_request_error", "code": null}}
```

---

## 6. Unsupported Features Strategy

### 6.1 Features to Store in Metadata

When converting to a protocol that doesn't support a feature:

```python
# Store unsupported params in metadata/extra field
{
    "metadata": {
        "_unsupported": {
            "source_protocol": "openai_classic",
            "params": {
                "seed": 42,
                "logprobs": true,
                "top_logprobs": 5,
                "presence_penalty": 0.5
            }
        }
    }
}
```

### 6.2 Features Requiring Degradation

| Feature | From | To | Strategy |
|---------|------|-----|----------|
| Multiple completions (`n`) | OpenAI | Anthropic | Raise `CapabilityNotSupported` or return single |
| Logprobs | OpenAI | Anthropic | Store in metadata, omit from request |
| `top_k` | Anthropic | OpenAI | Store in metadata, omit from request |
| Audio I/O | OpenAI | Anthropic | Raise `CapabilityNotSupported` |
| Image generation | OpenAI Responses | Others | Raise `CapabilityNotSupported` |
| Extended thinking | Anthropic | OpenAI | Handle via model selection or omit |
| Document input | Anthropic | OpenAI Classic | Raise `CapabilityNotSupported` or extract text |

### 6.3 Value Range Adjustments

| Parameter | OpenAI Range | Anthropic Range | Conversion |
|-----------|-------------|-----------------|------------|
| `temperature` | 0-2 | 0-1 | Clamp or scale: `min(value, 1.0)` |
| `stop` length | Max 4 | Unlimited | Truncate with warning |
