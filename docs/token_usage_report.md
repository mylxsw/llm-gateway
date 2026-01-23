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
- 多模态：
  - 文本：由模型 tokenizer 计数（tiktoken）。
  - 图片：低清细节通常为固定 Token，高细节按 512px tile 计数。
  - 音频：通常在 usage 的细分字段中体现 `audio_tokens`。
  - 视频：部分模型/接口提供 `video_tokens` 细分字段。

### 1.2 Anthropic
- Messages API:
  - `usage.input_tokens`、`usage.output_tokens`
  - 缓存相关：`cache_creation_input_tokens`、`cache_read_input_tokens`
- 多模态：
  - 图片信息计入 input/output tokens；usage 可能仅反映总量与缓存差异。

### 1.3 Google Gemini
- `usageMetadata`:
  - `promptTokenCount`、`candidatesTokenCount`、`totalTokenCount`
  - `cachedContentTokenCount`
- 多模态 token 已统一计入 prompt/candidates 的统计。

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

## 5. 风险与改进方向

- 多模态 token 估算依赖厂商规则，现阶段用于“近似”与“路由参考”。
- 后续可接入官方 tokenizer（如 Anthropic tokenizer）或更精确的多模态成本模型。
