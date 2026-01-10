# LLM Gateway API 文档

## 概述

本文档定义了 LLM Gateway 的前后端接口规范。

- **Base URL**: `http://localhost:8000`
- **认证方式**: API 代理接口使用 `Authorization: Bearer <api_key>` 认证
- **数据格式**: JSON

---

## 一、代理接口 (Proxy API)

### ⚠️ 透传原则（重要）

**所有代理接口必须遵循严格的透传原则：**

1. **请求透传**：
   - 客户端发送的请求体（body）**原样转发**到上游供应商
   - **仅修改 `model` 字段**为目标模型名（target_model）
   - 其他所有字段（messages、temperature、max_tokens、tools、stream 等）**不做任何修改**
   - 请求头（headers）中除鉴权相关字段外，**原样转发**

2. **响应透传**：
   - 上游供应商返回的响应**原样返回**给客户端
   - **不修改**响应体中的任何字段
   - **不修改**响应头

3. **URL 路由**：
   - 根据请求路径和供应商协议，将请求转发到正确的上游 URL
   - 例如：`/v1/chat/completions` → `{provider.base_url}/v1/chat/completions`

4. **实现要点**：
   ```python
   # 伪代码示例
   def forward_request(request_body, target_model, provider):
       # 仅替换 model 字段
       forwarded_body = request_body.copy()
       forwarded_body["model"] = target_model
       
       # 其他字段保持不变
       # ❌ 不要做: forwarded_body["temperature"] = 0.7
       # ❌ 不要做: forwarded_body["max_tokens"] = min(request_body["max_tokens"], 4096)
       # ✅ 正确: 直接使用 request_body 中的原始值
       
       return forward_to_provider(provider.base_url, forwarded_body)
   ```

---

### 1.1 OpenAI 兼容接口

#### POST /v1/chat/completions

Chat Completions 代理接口

**请求头**
```
Authorization: Bearer <api_key>
Content-Type: application/json
```

**请求体** (与 OpenAI 格式一致)
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

**响应** (与 OpenAI 格式一致)
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

**错误响应**
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

Text Completions 代理接口

**请求体**
```json
{
  "model": "gpt-3.5-turbo-instruct",
  "prompt": "Say hello",
  "max_tokens": 100
}
```

---

#### POST /v1/embeddings

Embeddings 代理接口

**请求体**
```json
{
  "model": "text-embedding-ada-002",
  "input": "The food was delicious"
}
```

---

### 1.2 Anthropic 兼容接口

#### POST /v1/messages

Anthropic Messages 代理接口

**请求头**
```
Authorization: Bearer <api_key>
Content-Type: application/json
x-api-key: <api_key>
anthropic-version: 2023-06-01
```

**请求体**
```json
{
  "model": "claude-3-opus-20240229",
  "max_tokens": 1024,
  "messages": [
    {"role": "user", "content": "Hello, Claude!"}
  ]
}
```

**响应**
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

## 二、管理接口 (Admin API)

### 2.1 供应商管理

#### GET /admin/providers

获取供应商列表

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| is_active | boolean | 否 | 过滤激活状态 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |

**响应**
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

获取单个供应商详情

**响应**
```json
{
  "id": 1,
  "name": "OpenAI Official",
  "base_url": "https://api.openai.com",
  "protocol": "openai",
  "api_type": "chat",
  "api_key": "sk-***...***",  // 脱敏显示
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

#### POST /admin/providers

创建供应商

**请求体**
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

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 供应商名称，唯一 |
| base_url | string | 是 | 接口地址 |
| protocol | string | 是 | 协议类型: openai / anthropic |
| api_type | string | 是 | API 类型: chat / completion / embedding |
| api_key | string | 否 | 供应商 API Key |
| is_active | boolean | 否 | 是否激活，默认 true |

**响应**: 201 Created
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

更新供应商

**请求体**
```json
{
  "name": "OpenAI Official Updated",
  "base_url": "https://api.openai.com/v1",
  "is_active": false
}
```

**响应**: 200 OK

---

#### DELETE /admin/providers/{id}

删除供应商

**响应**: 204 No Content

**错误响应** (被引用时)
```json
{
  "error": {
    "message": "Provider is referenced by model mappings",
    "code": "provider_in_use"
  }
}
```

---

### 2.2 模型映射管理

#### GET /admin/models

获取模型映射列表

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| is_active | boolean | 否 | 过滤激活状态 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |

**响应**
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

获取单个模型映射详情（含供应商配置）

**响应**
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

创建模型映射

**请求体**
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

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| requested_model | string | 是 | 请求模型名，主键 |
| strategy | string | 否 | 选择策略，默认 round_robin |
| matching_rules | object | 否 | 模型级匹配规则 |
| capabilities | object | 否 | 模型能力描述 |
| is_active | boolean | 否 | 是否激活，默认 true |

**响应**: 201 Created

---

#### PUT /admin/models/{requested_model}

更新模型映射

**请求体**
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

删除模型映射（同时删除关联的供应商配置）

**响应**: 204 No Content

---

### 2.3 模型-供应商映射管理

#### GET /admin/model-providers

获取所有模型-供应商映射

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| requested_model | string | 否 | 按模型过滤 |
| provider_id | int | 否 | 按供应商过滤 |
| is_active | boolean | 否 | 过滤激活状态 |

**响应**
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

创建模型-供应商映射

**请求体**
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

**字段说明**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| requested_model | string | 是 | 请求模型名 |
| provider_id | int | 是 | 供应商 ID |
| target_model_name | string | 是 | 目标模型名（该供应商使用的实际模型） |
| provider_rules | object | 否 | 供应商级匹配规则 |
| priority | int | 否 | 优先级，默认 0 |
| weight | int | 否 | 权重，默认 1 |
| is_active | boolean | 否 | 是否激活，默认 true |

**响应**: 201 Created

---

#### PUT /admin/model-providers/{id}

更新模型-供应商映射

**请求体**
```json
{
  "target_model_name": "gpt-4-turbo",
  "priority": 2,
  "is_active": false
}
```

---

#### DELETE /admin/model-providers/{id}

删除模型-供应商映射

**响应**: 204 No Content

---

### 2.4 API Key 管理

#### GET /admin/api-keys

获取 API Key 列表

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| is_active | boolean | 否 | 过滤激活状态 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |

**响应**
```json
{
  "items": [
    {
      "id": 1,
      "key_name": "Production Key",
      "key_value": "lgw-***...***",  // 脱敏显示
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

获取单个 API Key 详情

**响应**
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

创建 API Key

**请求体**
```json
{
  "key_name": "Production Key"
}
```

**响应**: 201 Created
```json
{
  "id": 1,
  "key_name": "Production Key",
  "key_value": "lgw-xxxxxxxxxxxxxxxxxxxx",  // 完整显示，仅此一次
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "last_used_at": null
}
```

> **注意**: `key_value` 仅在创建时完整返回，后续查询将脱敏显示

---

#### PUT /admin/api-keys/{id}

更新 API Key

**请求体**
```json
{
  "key_name": "Production Key Updated",
  "is_active": false
}
```

---

#### DELETE /admin/api-keys/{id}

删除 API Key

**响应**: 204 No Content

---

### 2.5 日志查询

#### GET /admin/logs

查询请求日志

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_time | datetime | 否 | 开始时间 (ISO 8601) |
| end_time | datetime | 否 | 结束时间 (ISO 8601) |
| requested_model | string | 否 | 请求模型 (模糊匹配) |
| target_model | string | 否 | 目标模型 (模糊匹配) |
| provider_id | int | 否 | 供应商 ID |
| status_min | int | 否 | 最小状态码 |
| status_max | int | 否 | 最大状态码 |
| has_error | boolean | 否 | 是否有错误 |
| api_key_id | int | 否 | API Key ID |
| api_key_name | string | 否 | API Key 名称 |
| retry_count_min | int | 否 | 最小重试次数 |
| retry_count_max | int | 否 | 最大重试次数 |
| input_tokens_min | int | 否 | 最小输入 Token |
| input_tokens_max | int | 否 | 最大输入 Token |
| total_time_min | int | 否 | 最小耗时 (ms) |
| total_time_max | int | 否 | 最大耗时 (ms) |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |
| sort_by | string | 否 | 排序字段，默认 request_time |
| sort_order | string | 否 | 排序方向: asc / desc，默认 desc |

**响应**
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

获取日志详情

**响应**
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

## 三、错误码定义

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 删除成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如重名） |
| 422 | 请求体校验失败 |
| 500 | 服务器内部错误 |
| 502 | 上游服务错误 |
| 503 | 服务不可用 |

### 错误响应格式

```json
{
  "error": {
    "message": "错误描述",
    "type": "error_type",
    "code": "error_code",
    "details": {}  // 可选，额外错误信息
  }
}
```

### 错误码列表

| code | type | 说明 |
|------|------|------|
| invalid_api_key | authentication_error | API Key 无效 |
| api_key_disabled | authentication_error | API Key 已禁用 |
| model_not_found | not_found_error | 模型未配置 |
| no_available_provider | service_error | 无可用供应商 |
| all_providers_failed | upstream_error | 所有供应商均失败 |
| provider_in_use | conflict_error | 供应商被引用 |
| duplicate_name | conflict_error | 名称重复 |
| validation_error | validation_error | 请求参数校验失败 |

---

## 四、规则格式定义

### 规则结构

```typescript
interface Rule {
  field: string;      // 字段路径
  operator: string;   // 操作符
  value: any;         // 匹配值
}

interface RuleSet {
  rules: Rule[];
  logic?: "AND" | "OR";  // 默认 AND
}
```

### 字段路径

| 路径前缀 | 说明 | 示例 |
|----------|------|------|
| model | 当前请求模型 | model |
| headers.* | 请求头字段 | headers.x-priority |
| body.* | 请求体字段 | body.temperature |
| token_usage.* | Token 统计 | token_usage.input_tokens |

### 操作符

| 操作符 | 说明 | 值类型 |
|--------|------|--------|
| eq | 等于 | any |
| ne | 不等于 | any |
| gt | 大于 | number |
| gte | 大于等于 | number |
| lt | 小于 | number |
| lte | 小于等于 | number |
| contains | 包含 | string |
| not_contains | 不包含 | string |
| regex | 正则匹配 | string (正则表达式) |
| in | 在列表中 | array |
| not_in | 不在列表中 | array |
| exists | 字段存在 | boolean |

### 规则示例

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

## 五、TypeScript 类型定义 (前端)

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
