# 协议转换新增协议开发指南

本文档描述如何在 `backend/app/common/protocol_conversion.py` 中新增协议或扩展协议转换路径。

## 目标

- 通过注册表式的转换器，使新增协议或新增路径时无需改动既有核心逻辑。
- 统一请求、响应、流式三类转换的扩展方式。

## 关键位置

- 协议常量与归一化：`backend/app/common/provider_protocols.py`
- 协议转换核心：`backend/app/common/protocol_conversion.py`
- OpenAI Responses 相关转换：`backend/app/common/openai_responses.py`

## 新增协议的最小步骤

1. **声明协议常量**
   - 在 `backend/app/common/provider_protocols.py` 中新增协议常量。
   - 将协议加入 `IMPLEMENTATION_PROTOCOLS` 并完善 `resolve_implementation_protocol` 的映射规则。

2. **实现转换函数**
   - 请求转换：新增 `_convert_request_<from>_to_<to>`。
   - 响应转换：新增 `_convert_response_<from>_to_<to>`。
   - 流式转换：新增 `_convert_stream_<from>_to_<to>`。

3. **注册转换关系**
   - 在 `convert_request_for_supplier` 中的 `converters` 字典加入请求转换。
   - 在 `convert_response_for_user` 中的 `converters` 字典加入响应转换。
   - 在 `convert_stream_for_user` 中的 `converters` 字典加入流式转换。

4. **补齐转换行为**
   - 若新协议具备工具调用、系统消息等特殊字段，考虑复用或新增规范化函数。
   - 如果提供方 SDK 有官方转换器，优先使用；否则实现最小可用的 fallback。

5. **测试与验证**
   - 对新增路径进行单元测试（`backend/tests/unit/`）。
   - 手动验证流式响应的事件顺序与终止信号是否符合目标协议。

## 开发约定

- 请求/响应/流式转换函数必须保持幂等、可组合、尽量无副作用。
- 新增协议时优先复用现有工具函数（如 `_normalize_openai_tooling_fields`）。
- 不要在公共入口函数中堆叠协议判断逻辑，统一通过注册表进行路由。

## 示例（新增 Foo 协议）

以下为示意伪代码，展示从 OpenAI 转 Foo 的最小实现：

```python
# 1) 新增请求转换函数

def _convert_request_openai_to_foo(*, path: str, body: dict[str, Any], target_model: str) -> tuple[str, dict[str, Any]]:
    if path != "/v1/chat/completions":
        raise ServiceError(message=f"Unsupported OpenAI endpoint for conversion: {path}", code="unsupported_protocol_conversion")
    foo_body = {...}
    foo_body["model"] = target_model
    return "/v1/foo/messages", foo_body

# 2) 注册请求转换
converters = {
    (OPENAI_PROTOCOL, FOO_PROTOCOL): _convert_request_openai_to_foo,
}
```

## 常见注意事项

- **路径检查**：每个转换函数必须验证 `path` 是否受支持。
- **模型字段**：转换后需显式设置 `model`（除非下游协议不需要）。
- **流式结束信号**：不同协议的 stream 终止语义不同，注意互相转换。
- **工具调用**：需要对 `tools` / `tool_choice` / `tool_calls` 做双向兼容。

