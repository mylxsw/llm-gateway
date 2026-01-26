# API Protocol Comparison Report

OpenAI Classic (Chat Completions) vs OpenAI Responses vs Anthropic Messages

## 1. Overview

| Aspect | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|--------|----------------|------------------|-------------------|
| Endpoint | `/v1/chat/completions` | `/v1/responses` | `/v1/messages` |
| Message Unit | `messages[]` (Message objects) | `input` (string or Item[]) | `messages[]` (Message objects) |
| System Prompt | Via `role: "system"` or `role: "developer"` | Via `instructions` parameter | Via `system` parameter |
| Tool Format | `tools[].function.{name,description,parameters}` | `tools[].{name,description,parameters}` | `tools[].{name,description,input_schema}` |
| Response Format | `choices[].message` | `output[]` (Item array) | `content[]` (ContentBlock array) |
| Streaming | SSE with `data: {...}` + `[DONE]` | SSE with event types | SSE with event types |

---

## 2. Request Fields Comparison

### 2.1 Core Parameters

| Parameter | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|-----------|----------------|------------------|-------------------|
| Model | `model` (required) | `model` (required) | `model` (required) |
| Messages/Input | `messages` (required) | `input` (required) | `messages` (required) |
| System Prompt | In `messages` with `role: "system"` | `instructions` | `system` (string or blocks) |
| Max Tokens | `max_tokens` or `max_completion_tokens` | `max_output_tokens` | `max_tokens` (required) |
| Temperature | `temperature` (0-2, default 1) | `temperature` (0-2, default 1) | `temperature` (0-1, default 1) |
| Top P | `top_p` (default 1) | `top_p` (default 1) | `top_p` |
| Top K | Not supported | Not supported | `top_k` |
| Stop Sequences | `stop` (string or array, max 4) | `stop` (array, max 4) | `stop_sequences` (array) |
| Stream | `stream` (boolean) | `stream` (boolean) | `stream` (boolean) |
| Seed | `seed` (integer) | `seed` (integer) | Not supported |
| User ID | `user` (string) | `user` (string) | `metadata.user_id` |
| Logprobs | `logprobs`, `top_logprobs` | Not directly supported | Not supported |
| N (multiple choices) | `n` (default 1) | Not supported | Not supported |
| Presence Penalty | `presence_penalty` (-2 to 2) | Not supported | Not supported |
| Frequency Penalty | `frequency_penalty` (-2 to 2) | Not supported | Not supported |

### 2.2 Tool/Function Calling

| Aspect | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|--------|----------------|------------------|-------------------|
| Tool Declaration | `tools[]` | `tools[]` | `tools[]` |
| Tool Type | `type: "function"` | `type: "function"` | Implicit function |
| Name Location | `function.name` | `name` | `name` |
| Description Location | `function.description` | `description` | `description` |
| Schema Location | `function.parameters` | `parameters` | `input_schema` |
| Strict Mode | `function.strict` | `strict` | Not supported |
| Tool Choice | `tool_choice` | `tool_choice` | `tool_choice` |
| Auto Choice | `"auto"` | `{"type": "auto"}` | `{"type": "auto"}` |
| None Choice | `"none"` | `{"type": "none"}` | `{"type": "none"}` |
| Required Choice | `"required"` | Not available | `{"type": "any"}` |
| Specific Tool | `{"type": "function", "function": {"name": "..."}}` | `{"type": "function", "name": "..."}` | `{"type": "tool", "name": "..."}` |
| Parallel Tool Calls | `parallel_tool_calls` (boolean) | Implicit | `tool_choice.disable_parallel_tool_use` |

#### Tool Declaration Format Examples

**OpenAI Classic:**
```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get current weather",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {"type": "string"}
      },
      "required": ["location"]
    },
    "strict": true
  }
}
```

**OpenAI Responses:**
```json
{
  "type": "function",
  "name": "get_weather",
  "description": "Get current weather",
  "parameters": {
    "type": "object",
    "properties": {
      "location": {"type": "string"}
    },
    "required": ["location"]
  },
  "strict": true
}
```

**Anthropic Messages:**
```json
{
  "name": "get_weather",
  "description": "Get current weather",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {"type": "string"}
    },
    "required": ["location"]
  }
}
```

### 2.3 Message/Content Structure

#### Role Mapping

| OpenAI Classic | OpenAI Responses | Anthropic Messages |
|----------------|------------------|-------------------|
| `system` | Via `instructions` | Via `system` parameter |
| `developer` | Via `instructions` | Via `system` parameter |
| `user` | `user` (in items) | `user` |
| `assistant` | `assistant` (in items) | `assistant` |
| `tool` | `function_call_output` (item type) | `tool_result` (content block) |

#### Content Block Types

| Content Type | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|--------------|----------------|------------------|-------------------|
| Text | `{"type": "text", "text": "..."}` | `{"type": "text", "text": "..."}` | `{"type": "text", "text": "..."}` |
| Image URL | `{"type": "image_url", "image_url": {"url": "..."}}` | `{"type": "image_url", "image_url": "..."}` | `{"type": "image", "source": {"type": "url", "url": "..."}}` |
| Image Base64 | `{"type": "image_url", "image_url": {"url": "data:..."}}` | `{"type": "image_url", "image_url": "data:..."}` | `{"type": "image", "source": {"type": "base64", "media_type": "...", "data": "..."}}` |
| Tool Call | In `tool_calls[]` | `function_call` item | `{"type": "tool_use", ...}` |
| Tool Result | `role: "tool"` message | `function_call_output` item | `{"type": "tool_result", ...}` |
| Audio | `{"type": "input_audio", ...}` | `{"type": "input_audio", ...}` | Not directly supported |
| Document/PDF | Not directly supported | File search tool | `{"type": "document", ...}` |

### 2.4 Response Format/Structured Outputs

| Aspect | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|--------|----------------|------------------|-------------------|
| JSON Mode | `response_format: {"type": "json_object"}` | `text: {"format": {"type": "json_object"}}` | Not directly supported |
| JSON Schema | `response_format: {"type": "json_schema", "json_schema": {...}}` | `text: {"format": {"type": "json_schema", ...}}` | Not directly supported |

---

## 3. Response Fields Comparison

### 3.1 Top-Level Response Structure

| Field | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|-------|----------------|------------------|-------------------|
| ID | `id` (chatcmpl-xxx) | `id` (resp_xxx) | `id` (msg_xxx) |
| Object Type | `object: "chat.completion"` | `object: "response"` | `type: "message"` |
| Created | `created` (unix timestamp) | `created_at` (unix timestamp) | Not included |
| Model | `model` | `model` | `model` |
| Content | `choices[].message` | `output[]` | `content[]` |
| Finish Reason | `choices[].finish_reason` | `output[].status` or `status` | `stop_reason` |
| Usage | `usage` object | `usage` object | `usage` object |

### 3.2 Finish/Stop Reason Mapping

| Reason | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|--------|----------------|------------------|-------------------|
| Normal completion | `stop` | `completed` | `end_turn` |
| Max tokens | `length` | `incomplete` (with `max_output_tokens`) | `max_tokens` |
| Tool call | `tool_calls` | N/A (continues in output) | `tool_use` |
| Stop sequence | `stop` | `completed` | `stop_sequence` |
| Content filter | `content_filter` | `incomplete` (with reason) | `refusal` |

### 3.3 Usage Structure

| Field | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|-------|----------------|------------------|-------------------|
| Input Tokens | `prompt_tokens` | `input_tokens` | `input_tokens` |
| Output Tokens | `completion_tokens` | `output_tokens` | `output_tokens` |
| Total Tokens | `total_tokens` | `total_tokens` | (compute from above) |
| Cached Input | `prompt_tokens_details.cached_tokens` | `input_tokens_details.cached_tokens` | `cache_read_input_tokens` |
| Cache Creation | Not explicit | Not explicit | `cache_creation_input_tokens` |
| Reasoning Tokens | `completion_tokens_details.reasoning_tokens` | `output_tokens_details.reasoning_tokens` | Not exposed (in thinking) |

### 3.4 Tool Call Response Format

**OpenAI Classic:**
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"Paris\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

**OpenAI Responses:**
```json
{
  "output": [
    {
      "type": "function_call",
      "id": "fc_abc123",
      "call_id": "call_abc123",
      "name": "get_weather",
      "arguments": "{\"location\": \"Paris\"}"
    }
  ]
}
```

**Anthropic Messages:**
```json
{
  "content": [{
    "type": "tool_use",
    "id": "toolu_abc123",
    "name": "get_weather",
    "input": {"location": "Paris"}
  }],
  "stop_reason": "tool_use"
}
```

---

## 4. Streaming Events Comparison

### 4.1 Event Format

| Aspect | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|--------|----------------|------------------|-------------------|
| Format | `data: {...}` | `event: xxx\ndata: {...}` | `event: xxx\ndata: {...}` |
| Termination | `data: [DONE]` | `event: response.done` | `event: message_stop` |
| Chunk Object | `chat.completion.chunk` | Various event types | Various event types |

### 4.2 Stream Event Types

#### OpenAI Classic Stream Events
- Each chunk has `object: "chat.completion.chunk"`
- `choices[].delta` contains incremental content
- `choices[].delta.content` for text
- `choices[].delta.tool_calls` for tool calls
- Final chunk may have `choices[].finish_reason`
- Ends with `data: [DONE]`

#### OpenAI Responses Stream Events
| Event Type | Description |
|------------|-------------|
| `response.created` | Response object created |
| `response.in_progress` | Response is being generated |
| `response.output_item.added` | New output item added |
| `response.output_item.done` | Output item completed |
| `response.content_part.added` | Content part started |
| `response.content_part.delta` | Content delta |
| `response.content_part.done` | Content part completed |
| `response.text.delta` | Text content delta |
| `response.text.done` | Text content complete |
| `response.function_call_arguments.delta` | Function arguments delta |
| `response.function_call_arguments.done` | Function call complete |
| `response.done` | Response complete |
| `error` | Error occurred |

#### Anthropic Messages Stream Events
| Event Type | Description |
|------------|-------------|
| `message_start` | Message object with initial metadata |
| `content_block_start` | New content block started |
| `content_block_delta` | Content delta (text_delta, input_json_delta, thinking_delta) |
| `content_block_stop` | Content block completed |
| `message_delta` | Message-level delta (stop_reason, usage) |
| `message_stop` | Stream complete |
| `ping` | Keep-alive ping |
| `error` | Error occurred |

### 4.3 Delta Structures

**OpenAI Classic Delta:**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion.chunk",
  "choices": [{
    "index": 0,
    "delta": {"content": "Hello"},
    "finish_reason": null
  }]
}
```

**OpenAI Responses Delta:**
```json
event: response.text.delta
data: {"type": "response.text.delta", "item_id": "item_xxx", "output_index": 0, "content_index": 0, "delta": "Hello"}
```

**Anthropic Messages Delta:**
```json
event: content_block_delta
data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}
```

---

## 5. Error Response Comparison

### 5.1 Error Structure

**OpenAI (both APIs):**
```json
{
  "error": {
    "message": "Error description",
    "type": "invalid_request_error",
    "param": "messages",
    "code": "invalid_type"
  }
}
```

**Anthropic:**
```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "Error description"
  }
}
```

### 5.2 Error Code Mapping

| HTTP Status | OpenAI Type | Anthropic Type |
|-------------|-------------|----------------|
| 400 | `invalid_request_error` | `invalid_request_error` |
| 401 | `authentication_error` | `authentication_error` |
| 403 | `permission_error` | `permission_error` |
| 404 | `not_found_error` | `not_found_error` |
| 429 | `rate_limit_error` | `rate_limit_error` |
| 500 | `server_error` | `api_error` |
| 503 | `service_unavailable_error` | N/A |
| 529 | N/A | `overloaded_error` |

---

## 6. Multimodal Capabilities

### 6.1 Image Input Support

| Capability | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|------------|----------------|------------------|-------------------|
| URL images | Yes | Yes | Yes |
| Base64 images | Yes | Yes | Yes |
| Supported formats | JPEG, PNG, GIF, WebP | JPEG, PNG, GIF, WebP | JPEG, PNG, GIF, WebP |
| Max images | Multiple | Multiple | Up to 20 |
| Max size | 20MB | 20MB | 3.75MB each |

### 6.2 Image Generation

| Capability | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|------------|----------------|------------------|-------------------|
| Native support | No (separate API) | Yes (image_generation tool) | No |

### 6.3 Audio Support

| Capability | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|------------|----------------|------------------|-------------------|
| Audio input | Yes (GPT-4o) | Yes | No |
| Audio output | Yes (GPT-4o) | Yes | No |

### 6.4 Document/File Support

| Capability | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|------------|----------------|------------------|-------------------|
| PDF input | No | Via file_search tool | Yes (native) |
| Text files | No | Via file_search tool | Yes (native) |

---

## 7. Special Features

### 7.1 Extended Thinking

| Feature | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|---------|----------------|------------------|-------------------|
| Thinking blocks | Via reasoning models | Via reasoning models | `thinking` parameter |
| Budget control | Not explicit | Not explicit | `thinking.budget_tokens` |
| Thinking output | Summarized | Encrypted or summarized | Raw or signature-verified |

### 7.2 Caching

| Feature | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|---------|----------------|------------------|-------------------|
| Prompt caching | Automatic | Automatic | Explicit `cache_control` |
| Cache TTL | System-managed | System-managed | `5m` or `1h` |

### 7.3 Stateful Conversations

| Feature | OpenAI Classic | OpenAI Responses | Anthropic Messages |
|---------|----------------|------------------|-------------------|
| State management | Client-side (send full history) | `previous_response_id` | Client-side (send full history) |
| Storage | `store: true` | `store: true` (default) | No built-in storage |

---

## 8. Conversion Strategies

### 8.1 Lossless vs Lossy Conversions

**Lossless mappings:**
- Text content between all three APIs
- Basic tool declarations (name, description, schema)
- Role mappings (user, assistant)
- Temperature, max_tokens, stop sequences
- Image inputs (URL and base64)

**Lossy mappings (require degradation):**
- `top_k` (Anthropic → OpenAI): Drop or store in metadata
- `seed` (OpenAI → Anthropic): Drop or store in metadata
- `n` multiple completions (OpenAI → others): Not supported
- Presence/frequency penalty (OpenAI → others): Not supported
- `logprobs` (OpenAI → others): Not supported
- Native audio I/O (OpenAI → Anthropic): Not supported
- Extended thinking format differences

### 8.2 Recommended Degradation Strategies

1. **Unsupported parameters**: Store in `metadata.unsupported_params` for round-trip preservation
2. **Capability gaps**: Raise `CapabilityNotSupportedError` with details
3. **Value range differences**: Clamp values (e.g., temperature 0-2 → 0-1)
4. **Format differences**: Transform to equivalent format (e.g., tool schema nesting)

---

## 9. References

- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [OpenAI Migration Guide](https://platform.openai.com/docs/guides/migrate-to-responses)
- [Anthropic Messages API](https://docs.anthropic.com/en/api/messages)
- [Anthropic Streaming](https://docs.anthropic.com/en/api/messages-streaming)
