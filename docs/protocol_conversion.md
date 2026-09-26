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

## 纯转发型协议（如 Jev）

有些协议在网关中只做"透传"：对外暴露的接口与上游完全一致，中间不做任何语义转换。
这类协议不需要编写任何转换器，接入步骤比上面的最小步骤更短：

1. 在 `backend/app/common/provider_protocols.py` 中新增协议常量，并加入
   `FRONTEND_PROTOCOL_CONFIGS` 与 `IMPLEMENTATION_PROTOCOLS`。
2. 在 `backend/app/common/protocol/base.py` 的 `Protocol` 枚举与 `from_string` 中登记。
3. **不要**注册任何跨协议 converter。用户协议与供应商协议相同时，
   `ProtocolConverterManager` 会走 identity 路径；协议不同时会自然抛出
   `UnsupportedConversionError`，这正是我们期望的行为（禁止错配）。
4. 如果该协议的请求体不接受多余字段，需要在
   `ProtocolConverterManager._identity_request_conversion` 中为它加一条短路分支，
   跳过 `default_parameters` 注入与 chat 语义的规范化，只重写 `model` 字段。
   Jev 就是这样处理的——上游对未知字段返回 422。
5. 新增对应的 `ProviderClient` 实现与 `app/providers/factory.py` 注册；
   若协议不支持流式，`forward_stream` 应产出一个明确的错误响应而不是抛异常。
6. 若请求体结构与 chat 不同（没有 `messages` / `input` / `prompt`），
   需要新增对应的 `TokenCounter` 并在 `get_token_counter` 中注册，
   否则路由前的 token 预估恒为 0，`cost_first` 策略与阶梯计价选档会失效。
   最终计费仍以上游返回的 `usage` 为准。

## 常见注意事项

- **路径检查**：每个转换函数必须验证 `path` 是否受支持。
- **模型字段**：转换后需显式设置 `model`（除非下游协议不需要）。
- **流式结束信号**：不同协议的 stream 终止语义不同，注意互相转换。
- **工具调用**：需要对 `tools` / `tool_choice` / `tool_calls` 做双向兼容。

