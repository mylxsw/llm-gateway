# LLM Gateway API Documentation

## Overview

This document defines the interface specifications for the LLM Gateway backend and frontend.

- **Base URL**: `http://localhost:8000`
- **Authentication**: Proxy APIs use `Authorization: Bearer <api_key>` authentication.
- **Data Format**: JSON

---

## I. Proxy API

### ⚠️ Pass-through Principle (Important)

**All proxy interfaces must strictly adhere to the pass-through principle:**

1.  **Request Pass-through**:
    -   The request body sent by the client is **forwarded as-is** to the upstream provider.
    -   **Only the `model` field is modified** to the target model name (`target_model`).
    -   All other fields (messages, temperature, max_tokens, tools, stream, etc.) are **not modified**.
    -   Request headers (headers) are **forwarded as-is**, except for authentication-related fields.

2.  **Response Pass-through**:
    -   The response returned by the upstream provider is **returned as-is** to the client.
    -   **Do not modify** any fields in the response body.
    -   **Do not modify** response headers.

3.  **URL Routing**:
    -   Forward requests to the correct upstream URL based on the request path and provider protocol.
    -   Example: `/v1/chat/completions` → `{provider.base_url}/v1/chat/completions`

4.  **Implementation Points**:
    ```python
    # Pseudo-code example
    def forward_request(request_body, target_model, provider):
        # Only replace model field
        forwarded_body = request_body.copy()
        forwarded_body["model"] = target_model
        
        # Other fields remain unchanged
        # ❌ Do not do: forwarded_body["temperature"] = 0.7
        # ❌ Do not do: forwarded_body["max_tokens"] = min(request_body["max_tokens"], 4096)
        # ✅ Correct: Directly use original values from request_body
        
        return forward_to_provider(provider.base_url, forwarded_body)
    ```

---

### 1.1 OpenAI Compatible Interface

#### POST /v1/chat/completions

Chat Completions Proxy Interface

**Request Headers**
```
Authorization: Bearer <api_key>
Content-Type: application/json
```

**Request Body** (Consistent with OpenAI format)
```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**Response** (Consistent with OpenAI format)
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1704067200,
  "model": "gpt-4-0613",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

**Error Response**
```json
{
  "error": {
    "message": "Invalid API key",
    "type": "authentication_error",
    "code": "invalid_api_key"
  }
}
```

---

#### POST /v1/completions

Text Completions Proxy Interface

**Request Body**
```json
{
  "model": "gpt-3.5-turbo-instruct",
  "prompt": "Say hello",
  "max_tokens": 100
}
```

---

#### POST /v1/embeddings

Embeddings Proxy Interface

**Request Body**
```json
{
  "model": "text-embedding-ada-002",
  "input": "The food was delicious"
}
```

---

### 1.2 Anthropic Compatible Interface

#### POST /v1/messages

Anthropic Messages Proxy Interface

**Request Headers**
```
Authorization: Bearer <api_key>
Content-Type: application/json
x-api-key: <api_key>
anthropic-version: 2023-06-01
```

**Request Body**
```json
{
  "model": "claude-3-opus-20240229",
  "max_tokens": 1024,
  "messages": [
    {"role": "user", "content": "Hello, Claude!"}
  ]
}
```

**Response**
```json
{
  "id": "msg_xxx",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hello! How can I assist you today?"
    }
  ],
  "model": "claude-3-opus-20240229",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 15
  }
}
```

---

## II. Admin API

### 2.1 Provider Management

#### GET /admin/providers

Get Provider List

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| is_active | boolean | No | Filter by active status |
| page | int | No | Page number, default 1 |
| page_size | int | No | Items per page, default 20 |

**Response**
```json
{
  "items": [
    {
      "id": 1,
      "name": "OpenAI Official",
      "base_url": "https://api.openai.com",
      "protocol": "openai",
      "api_type": "chat",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

---

#### GET /admin/providers/{id}

Get Single Provider Details

**Response**
```json
{
  "id": 1,
  "name": "OpenAI Official",
  "base_url": "https://api.openai.com",
  "protocol": "openai",
  "api_type": "chat",
  "api_key": "sk-***...***",  // Sanitized display
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

#### POST /admin/providers

Create Provider

**Request Body**
```json
{
  "name": "OpenAI Official",
  "base_url": "https://api.openai.com",
  "protocol": "openai",
  "api_type": "chat",
  "api_key": "sk-xxxx",
  "is_active": true
}
```

**Field Description**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Provider name, unique |
| base_url | string | Yes | Interface address |
| protocol | string | Yes | Protocol type: openai / anthropic |
| api_type | string | Yes | API type: chat / completion / embedding |
| api_key | string | No | Provider API Key |
| is_active | boolean | No | Active status, default true |

**Response**: 201 Created
```json
{
  "id": 1,
  "name": "OpenAI Official",
  "base_url": "https://api.openai.com",
  "protocol": "openai",
  "api_type": "chat",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

#### PUT /admin/providers/{id}

Update Provider

**Request Body**
```json
{
  "name": "OpenAI Official Updated",
  "base_url": "https://api.openai.com/v1",
  "is_active": false
}
```

**Response**: 200 OK

---

#### DELETE /admin/providers/{id}

Delete Provider

**Response**: 204 No Content

**Error Response** (When referenced)
```json
{
  "error": {
    "message": "Provider is referenced by model mappings",
    "code": "provider_in_use"
  }
}
```

---

### 2.2 Model Mapping Management

#### GET /admin/models

Get Model Mapping List

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| is_active | boolean | No | Filter by active status |
| page | int | No | Page number, default 1 |
| page_size | int | No | Items per page, default 20 |

**Response**
```json
{
  "items": [
    {
      "requested_model": "gpt-4",
      "strategy": "round_robin",
      "matching_rules": null,
      "capabilities": {"streaming": true, "function_calling": true},
      "is_active": true,
      "provider_count": 3,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

---

#### GET /admin/models/{requested_model}

Get Single Model Mapping Details (Includes Provider Config)

**Response**
```json
{
  "requested_model": "gpt-4",
  "strategy": "round_robin",
  "matching_rules": {
    "rules": [
      {"field": "headers.x-priority", "operator": "eq", "value": "high"}
    ]
  },
  "capabilities": {"streaming": true, "function_calling": true},
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "providers": [
    {
      "id": 1,
      "provider_id": 1,
      "provider_name": "OpenAI Official",
      "target_model_name": "gpt-4-0613",
      "provider_rules": null,
      "priority": 1,
      "weight": 1,
      "is_active": true
    },
    {
      "id": 2,
      "provider_id": 2,
      "provider_name": "Azure OpenAI",
      "target_model_name": "gpt-4-azure",
      "provider_rules": null,
      "priority": 2,
      "weight": 1,
      "is_active": true
    }
  ]
}
```

---

#### POST /admin/models

Create Model Mapping

**Request Body**
```json
{
  "requested_model": "gpt-4",
  "strategy": "round_robin",
  "matching_rules": {
    "rules": [
      {"field": "headers.x-priority", "operator": "eq", "value": "high"}
    ]
  },
  "capabilities": {"streaming": true, "function_calling": true},
  "is_active": true
}
```

**Field Description**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requested_model | string | Yes | Requested model name, Primary Key |
| strategy | string | No | Selection strategy, default round_robin |
| matching_rules | object | No | Model level matching rules |
| capabilities | object | No | Model capabilities description |
| is_active | boolean | No | Active status, default true |

**Response**: 201 Created

---

#### PUT /admin/models/{requested_model}

Update Model Mapping

**Request Body**
```json
{
  "matching_rules": {
    "rules": [
      {"field": "body.temperature", "operator": "lte", "value": 0.5}
    ]
  },
  "is_active": true
}
```

---

#### DELETE /admin/models/{requested_model}

Delete Model Mapping (Simultaneously deletes associated provider configurations)

**Response**: 204 No Content

---

### 2.3 Model-Provider Mapping Management

#### GET /admin/model-providers

Get All Model-Provider Mappings

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| requested_model | string | No | Filter by model |
| provider_id | int | No | Filter by provider |
| is_active | boolean | No | Filter by active status |

**Response**
```json
{
  "items": [
    {
      "id": 1,
      "requested_model": "gpt-4",
      "provider_id": 1,
      "provider_name": "OpenAI Official",
      "target_model_name": "gpt-4-0613",
      "provider_rules": null,
      "priority": 1,
      "weight": 1,
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 10
}
```

---

#### POST /admin/model-providers

Create Model-Provider Mapping

**Request Body**
```json
{
  "requested_model": "gpt-4",
  "provider_id": 1,
  "target_model_name": "gpt-4-0613",
  "provider_rules": {
    "rules": [
      {"field": "token_usage.input_tokens", "operator": "lte", "value": 4000}
    ]
  },
  "priority": 1,
  "weight": 1,
  "is_active": true
}
```

**Field Description**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| requested_model | string | Yes | Requested model name |
| provider_id | int | Yes | Provider ID |
| target_model_name | string | Yes | Target model name (Actual model used by provider) |
| provider_rules | object | No | Provider level matching rules |
| priority | int | No | Priority, default 0 |
| weight | int | No | Weight, default 1 |
| is_active | boolean | No | Active status, default true |

**Response**: 201 Created

---

#### PUT /admin/model-providers/{id}

Update Model-Provider Mapping

**Request Body**
```json
{
  "target_model_name": "gpt-4-turbo",
  "priority": 2,
  "is_active": false
}
```

---

#### DELETE /admin/model-providers/{id}

Delete Model-Provider Mapping

**Response**: 204 No Content

---

### 2.4 API Key Management

#### GET /admin/api-keys

Get API Key List

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| is_active | boolean | No | Filter by active status |
| page | int | No | Page number, default 1 |
| page_size | int | No | Items per page, default 20 |

**Response**
```json
{
  "items": [
    {
      "id": 1,
      "key_name": "Production Key",
      "key_value": "lgw-***...***",  // Sanitized display
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "last_used_at": "2024-01-10T12:00:00Z"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20
}
```

---

#### GET /admin/api-keys/{id}

Get Single API Key Details

**Response**
```json
{
  "id": 1,
  "key_name": "Production Key",
  "key_value": "lgw-***...***",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "last_used_at": "2024-01-10T12:00:00Z"
}
```

---

#### POST /admin/api-keys

Create API Key

**Request Body**
```json
{
  "key_name": "Production Key"
}
```

**Response**: 201 Created
```json
{
  "id": 1,
  "key_name": "Production Key",
  "key_value": "lgw-xxxxxxxxxxxxxxxxxxxx",  // Full display, only this time
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "last_used_at": null
}
```

> **Note**: `key_value` is only returned in full upon creation, subsequent queries will display it sanitized.

---

#### PUT /admin/api-keys/{id}

Update API Key

**Request Body**
```json
{
  "key_name": "Production Key Updated",
  "is_active": false
}
```

---

#### DELETE /admin/api-keys/{id}

Delete API Key

**Response**: 204 No Content

---

### 2.5 Log Query

#### GET /admin/logs

Query Request Logs

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| start_time | datetime | No | Start time (ISO 8601) |
| end_time | datetime | No | End time (ISO 8601) |
| requested_model | string | No | Request model (Fuzzy match) |
| target_model | string | No | Target model (Fuzzy match) |
| provider_id | int | No | Provider ID |
| status_min | int | No | Min status code |
| status_max | int | No | Max status code |
| has_error | boolean | No | Has error |
| api_key_id | int | No | API Key ID |
| api_key_name | string | No | API Key Name |
| retry_count_min | int | No | Min retry count |
| retry_count_max | int | No | Max retry count |
| input_tokens_min | int | No | Min input tokens |
| input_tokens_max | int | No | Max input tokens |
| total_time_min | int | No | Min total time (ms) |
| total_time_max | int | No | Max total time (ms) |
| page | int | No | Page number, default 1 |
| page_size | int | No | Items per page, default 20 |
| sort_by | string | No | Sort field, default request_time |
| sort_order | string | No | Sort order: asc / desc, default desc |

**Response**
```json
{
  "items": [
    {
      "id": 1,
      "request_time": "2024-01-10T12:00:00Z",
      "api_key_id": 1,
      "api_key_name": "Production Key",
      "requested_model": "gpt-4",
      "target_model": "gpt-4-0613",
      "provider_id": 1,
      "provider_name": "OpenAI Official",
      "retry_count": 0,
      "first_byte_delay_ms": 500,
      "total_time_ms": 2000,
      "input_tokens": 100,
      "output_tokens": 50,
      "response_status": 200,
      "trace_id": "trace-xxx"
    }
  ],
  "total": 1000,
  "page": 1,
  "page_size": 20
}
```

---

#### GET /admin/logs/{id}

Get Log Details

**Response**
```json
{
  "id": 1,
  "request_time": "2024-01-10T12:00:00Z",
  "api_key_id": 1,
  "api_key_name": "Production Key",
  "requested_model": "gpt-4",
  "target_model": "gpt-4-0613",
  "provider_id": 1,
  "provider_name": "OpenAI Official",
  "retry_count": 0,
  "first_byte_delay_ms": 500,
  "total_time_ms": 2000,
  "input_tokens": 100,
  "output_tokens": 50,
  "request_headers": {
    "authorization": "Bearer lgw-***...***",
    "content-type": "application/json",
    "user-agent": "OpenAI/Python"
  },
  "request_body": {
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  },
  "response_status": 200,
  "response_body": {
    "id": "chatcmpl-xxx",
    "choices": [...]
  },
  "error_info": null,
  "trace_id": "trace-xxx"
}
```

---

## III. Error Code Definition

### HTTP Status Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created Successfully |
| 204 | Deleted Successfully |
| 400 | Bad Request |
| 401 | Authentication Failed |
| 403 | Forbidden |
| 404 | Resource Not Found |
| 409 | Resource Conflict (e.g., Duplicate Name) |
| 422 | Request Body Validation Failed |
| 500 | Internal Server Error |
| 502 | Upstream Service Error |
| 503 | Service Unavailable |

### Error Response Format

```json
{
  "error": {
    "message": "Error Description",
    "type": "error_type",
    "code": "error_code",
    "details": {}  // Optional, extra error info
  }
}
```

### Error Code List

| code | type | Description |
|------|------|-------------|
| invalid_api_key | authentication_error | Invalid API Key |
| api_key_disabled | authentication_error | API Key Disabled |
| model_not_found | not_found_error | Model Not Configured |
| no_available_provider | service_error | No Available Provider |
| all_providers_failed | upstream_error | All Providers Failed |
| provider_in_use | conflict_error | Provider Referenced |
| duplicate_name | conflict_error | Duplicate Name |
| validation_error | validation_error | Request Parameter Validation Failed |

---

## IV. Rule Format Definition

### Rule Structure

```typescript
interface Rule {
  field: string;      // Field path
  operator: string;   // Operator
  value: any;         // Match value
}

interface RuleSet {
  rules: Rule[];
  logic?: "AND" | "OR";  // Default AND
}
```

### Field Paths

| Path Prefix | Description | Example |
|-------------|-------------|---------|
| model | Current request model | model |
| headers.* | Request header field | headers.x-priority |
| body.* | Request body field | body.temperature |
| token_usage.* | Token statistics | token_usage.input_tokens |

### Operators

| Operator | Description | Value Type |
|----------|-------------|------------|
| eq | Equal | any |
| ne | Not Equal | any |
| gt | Greater Than | number |
| gte | Greater Than or Equal | number |
| lt | Less Than | number |
| lte | Less Than or Equal | number |
| contains | Contains | string |
| not_contains | Not Contains | string |
| regex | Regex Match | string (Regular Expression) |
| in | In List | array |
| not_in | Not In List | array |
| exists | Field Exists | boolean |

### Rule Example

```json
{
  "rules": [
    {"field": "model", "operator": "eq", "value": "gpt-4"},
    {"field": "headers.x-priority", "operator": "eq", "value": "high"},
    {"field": "body.temperature", "operator": "lte", "value": 0.5},
    {"field": "token_usage.input_tokens", "operator": "lt", "value": 4000}
  ],
  "logic": "AND"
}
```

---

## V. TypeScript Type Definitions (Frontend)

```typescript
// Provider
interface Provider {
  id: number;
  name: string;
  base_url: string;
  protocol: "openai" | "anthropic";
  api_type: string;
  api_key?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ProviderCreate {
  name: string;
  base_url: string;
  protocol: "openai" | "anthropic";
  api_type: string;
  api_key?: string;
  is_active?: boolean;
}

interface ProviderUpdate {
  name?: string;
  base_url?: string;
  protocol?: "openai" | "anthropic";
  api_type?: string;
  api_key?: string;
  is_active?: boolean;
}

// Model Mapping
interface ModelMapping {
  requested_model: string;
  strategy: string;
  matching_rules?: RuleSet;
  capabilities?: Record<string, any>;
  is_active: boolean;
  provider_count?: number;
  providers?: ModelMappingProvider[];
  created_at: string;
  updated_at: string;
}

interface ModelMappingProvider {
  id: number;
  requested_model: string;
  provider_id: number;
  provider_name: string;
  target_model_name: string;
  provider_rules?: RuleSet;
  priority: number;
  weight: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// API Key
interface ApiKey {
  id: number;
  key_name: string;
  key_value: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string;
}

// Request Log
interface RequestLog {
  id: number;
  request_time: string;
  api_key_id?: number;
  api_key_name?: string;
  requested_model?: string;
  target_model?: string;
  provider_id?: number;
  provider_name?: string;
  retry_count: number;
  first_byte_delay_ms?: number;
  total_time_ms?: number;
  input_tokens?: number;
  output_tokens?: number;
  request_headers?: Record<string, string>;
  request_body?: Record<string, any>;
  response_status?: number;
  response_body?: any;
  error_info?: string;
  trace_id?: string;
}

// Pagination
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// Rule
interface Rule {
  field: string;
  operator: "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "contains" | "not_contains" | "regex" | "in" | "not_in" | "exists";
  value: any;
}

interface RuleSet {
  rules: Rule[];
  logic?: "AND" | "OR";
}

// Error
interface ApiError {
  error: {
    message: string;
    type: string;
    code: string;
    details?: Record<string, any>;
  };
}
```