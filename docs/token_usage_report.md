# Token 计算方式调研与统一规范

本报告总结 OpenAI、Anthropic、Google Gemini、OpenRouter 等厂商的 usage 结构与 Token 计算方式，并给出本项目的统一结构化记录与估算策略。重点：请求转发前的 Token 计算仅作路由决策参考；若响应包含 usage，则以响应为准并覆盖输入/输出 Token。

## 1. 厂商 usage 结构与 Token 统计

### 1.1 OpenAI
- Chat Completions:
  - `usage.prompt_tokens`、`usage.completion_tokens`、`usage.total_tokens`
- Responses API:
  - `usage.input_tokens`、`usage.output_tokens`、`usage.total_tokens`
  - 细分字段（可能存在）：`usage.input_tokens_details` / `usage.output_tokens_details`
    - 常见：`cached_tokens`、`audio_tokens`、`image_tokens`、`reasoning_tokens`、`tool_tokens`
- 缓存计费：
  - `prompt_tokens/input_tokens` 表示全部输入。
  - `cached_tokens` 表示缓存读取 token。
  - 未缓存输入需自行计算：`input_tokens - cached_tokens`。
- 多模态：
  - 文本：由模型 tokenizer 计数（tiktoken）。
  - 图片：低清细节通常为固定 Token，高细节按 512px tile 计数。
  - 音频：通常在 usage 的细分字段中体现 `audio_tokens`。
  - 视频：部分模型/接口提供 `video_tokens` 细分字段。

### 1.2 Anthropic
- Messages API:
  - `usage.input_tokens`、`usage.output_tokens`
  - 缓存相关：`cache_creation_input_tokens`、`cache_read_input_tokens`
- 缓存计费：
  - 原始 `usage.input_tokens` 表示未缓存输入，不是全部输入。
  - 全部输入需统一计算：`input_tokens + cache_creation_input_tokens + cache_read_input_tokens`。
  - `cache_creation_input_tokens` 使用缓存写入价，`cache_read_input_tokens` 使用缓存读取价。
- 多模态：
  - 图片信息计入 input/output tokens；usage 可能仅反映总量与缓存差异。

### 1.3 Google Gemini
- `usageMetadata`:
  - `promptTokenCount`、`candidatesTokenCount`、`totalTokenCount`
  - `cachedContentTokenCount`
- 多模态 token 已统一计入 prompt/candidates 的统计。
- 缓存计费：
  - `promptTokenCount` 表示全部输入。
  - `cachedContentTokenCount` 表示缓存读取 token。
  - 未缓存输入需自行计算：`promptTokenCount - cachedContentTokenCount`。
  - Explicit Cache 的存储费用是独立资源费用，当前日志 usage 仅记录推理响应中的 token 用量。

### 1.4 OpenRouter（兼容 OpenAI）
- 一般复用 OpenAI usage 字段：
  - `prompt_tokens`、`completion_tokens`、`total_tokens`
- 可能扩展：
  - `cached_tokens`、或与 OpenAI Responses 类似的细分字段

## 2. 统一结构化 usage 规范（日志表存储）

日志表新增 `usage_details`（JSON），统一结构如下（字段缺失时可为空）：

```json
{
  "input_tokens": 123,
  "output_tokens": 45,
  "total_tokens": 168,
  "cached_tokens": 12,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 12,
  "input_audio_tokens": 0,
  "output_audio_tokens": 0,
  "input_image_tokens": 85,
  "output_image_tokens": 0,
  "input_video_tokens": 0,
  "output_video_tokens": 0,
  "reasoning_tokens": 0,
  "tool_tokens": 0,
  "source": "upstream|estimated|mixed",
  "raw_usage": { "prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168 },
  "extra_usage": { "vendor_field": "..." }
}
```

说明：
- `source=upstream`：响应包含 usage，且使用该数值。
- `source=estimated`：响应缺少 usage，使用本地估算。
- `source=mixed`：部分字段缺失，混合使用响应与本地估算。
- `input_tokens`：统一表示全部 Prompt/Input token；Anthropic 会由三段输入相加得到。
- `cache_read_input_tokens`：缓存读取 token；OpenAI/Gemini 从各自缓存命中字段映射而来。
- `cache_creation_input_tokens`：缓存写入 token；主要来自 Anthropic，Gemini 显式缓存创建接口不一定出现在推理响应 usage 中。
- `raw_usage`：原始 usage 字段（尽可能完整保留）。
- `extra_usage`：非标准字段保留，避免丢失。

## 3. 多模态 Token 估算策略（本地估算，仅在无 usage 时使用）

### 3.1 文本（Text）
- OpenAI：使用 tiktoken（`cl100k_base` 等）。
- Anthropic：当前使用字符长度估算（平均 4 字符/Token），并兼容多模态内容块。

### 3.2 图片（Image）
- OpenAI 估算规则（参考官方计费思路）：
  - `detail=low`：约 85 tokens
  - `detail=high` 或未知：按 512px tile 计数，`tokens = tiles * 170`
  - tiles 计算：`ceil(width/512) * ceil(height/512)`
- Anthropic / Google / OpenRouter：暂使用同样 tile 估算，等待官方 tokenizer 时再细化。
- 若只有 Base64 数据，尝试解析图片尺寸（PNG/JPEG 头部）后再估算。

### 3.3 音频（Audio）
- 优先读取响应 usage（如 `audio_tokens`）。
- 无 usage 时估算：
  - 有时长：`tokens ≈ duration_seconds * 50`
  - 仅有数据大小：`tokens ≈ bytes / 1000`

### 3.4 视频（Video）
- 优先读取响应 usage（如 `video_tokens`）。
- 无 usage 时估算：
  - 有时长：`tokens ≈ duration_seconds * 200`
  - 仅有数据大小：`tokens ≈ bytes / 2000`

## 4. 处理策略与更新逻辑

1. **请求转发前**：根据请求体（文本/图片/音频/视频）估算 input tokens，用于路由策略参考。
2. **响应返回后**：
   - 若响应包含 usage：使用响应 usage 覆盖 input/output tokens。
   - 若不包含 usage：用本地估算填充 output tokens，并保留 input tokens。
3. **日志记录**：始终记录 `usage_details`，保留 raw usage 字段以便后续分析。

## 5. 统一计费公式

响应 usage 会先归一化为：

```text
promptTokens = input_tokens
completionTokens = output_tokens
cacheReadTokens = cache_read_input_tokens
cacheWriteTokens = cache_creation_input_tokens
regularInputTokens = max(input_tokens - cacheReadTokens - cacheWriteTokens, 0)
```

统一成本公式：

```text
Cost =
  cacheWriteTokens * CacheWritePrice
  + cacheReadTokens * CacheReadPrice
  + regularInputTokens * InputPrice
  + completionTokens * OutputPrice
```

`cached_input_cost` 当前记录缓存读取与缓存写入的合计成本，以保持日志表结构兼容。

## 6. 风险与改进方向

- 多模态 token 估算依赖厂商规则，现阶段用于“近似”与“路由参考”。
- 后续可接入官方 tokenizer（如 Anthropic tokenizer）或更精确的多模态成本模型。
- Gemini Explicit Cache 的 Cache Storage Fee 尚未并入请求级 token 计费，后续需要独立资源账单模型。
