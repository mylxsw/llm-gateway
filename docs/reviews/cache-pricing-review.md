# Code Review Prompt: 缓存计费修复 (Cache Pricing Fix)

## 背景 (Context)

Squirrel 是一个多供应商 LLM 网关，支持 Anthropic、OpenAI、Gemini。

用户报告了一个 bug：**Cache Read 的 token 被按照 Cache Write 的价格计费了**。

排查后发现这不是单点 bug，而是一组**概念错位 + 缺字段**的问题：

1. **后端只有一个 `cached_input_price`**，但它在 `costs.py` 里实际被乘到了 `cache_read_input_tokens`（缓存读 token）上 —— 也就是说 `cached_input_price` 实际语义是"缓存读价"。
2. **前端却把 `cached_input_price` 标签写成了"缓存写入价格 / Cache Write Price"**（`messages/en.json:528`、`messages/zh.json:528`），导致用户在"Cache Write Price"框里填的写价，被后端拿去给**缓存读** token 计费。
3. **真正的缓存写 token（`cache_creation_input_tokens`）从来不计费** —— proxy 从不提取它用于计费。

**目标**：引入一个语义清晰的 `cache_creation_input_price`（缓存写价）字段，让 `cached_input_price`（缓存读价）和 `cache_creation_input_price`（缓存写价）分别作用于对应的 token，前后端标签、计费、持久化、日志展示全链路语义一致。

## 改动范围 (Files Changed)

### 后端 (Backend)

| 文件 | 改动 |
|------|------|
| `backend/app/common/costs.py` | `ResolvedBilling` 新增 `cache_creation_input_price`；`_select_tier` 返回 5 元组；`_resolve_cache_fields` 返回 4 元组；`resolve_billing` 在 `inherit_model_default` 清零块补一行、tiered 路径用 tier 写价覆盖、flat 路径补回退；`calculate_cost_from_billing` 新增 `cache_creation_input_tokens` 入参；`calculate_cost` 新增 `cache_creation_input_tokens`/`cache_creation_input_price` 入参，按 read + write + non-cached 三段拆分，并在 read+write 之和超过 `in_tokens` 时按比例收缩避免双重计算 |
| `backend/app/domain/model.py` | 9 个 DTO 平行新增 `cache_creation_input_price` 字段（含 `TokenTierPrice`、`ModelMappingCreate/Update`、`ModelMapping`、`ModelMatchProviderResponse`、`ModelMappingProviderCreate/Update`、`ModelProviderBulkUpgradeRequest`、`ModelMappingProvider`、`ModelProviderExport`）和 `resolved_cache_creation_input_price` |
| `backend/app/db/models.py` | `ModelMapping` 和 `ModelMappingProvider` ORM 各加一列 `cache_creation_input_price: Mapped[Optional[float]]` (Numeric(12, 4)) |
| `backend/app/db/session.py` | `ensure_columns` 两个表都加 `"cache_creation_input_price": "cache_creation_input_price NUMERIC(12,4)"` |
| `backend/migrations/add_cache_creation_price_columns.sql` | **新增迁移文件**，两表各 `ALTER TABLE ... ADD COLUMN cache_creation_input_price NUMERIC(12, 4)` |
| `backend/app/repositories/sqlalchemy/model_repo.py` | to_domain 读列、create 写列；update_* 用 `model_dump(exclude_unset=True)` 自动兼容 |
| `backend/app/services/model_service.py` | resolved_* 字段设置；`update_provider_mapping` 的 merged dict 补字段；响应构造补字段 |
| `backend/app/services/proxy_service.py` | 4 处 `resolve_billing` 调用补 `model_cache_creation_input_price` 和 `provider_cache_creation_input_price`；2 处 `calculate_cost_from_billing` 调用补 `cache_creation_input_tokens` 并提取 `usage_details.get("cache_creation_input_tokens")` |

### 前端 (Frontend)

| 文件 | 改动 |
|------|------|
| `frontend/messages/en.json` | 修正 `cachedInputPrice` 文案为 "Cache Read Price"、新增 `cacheCreationInputPrice` / `tierCacheCreationInputPrice`；`cacheSuffix` 加写价占位符 |
| `frontend/messages/zh.json` | 同步中文文案 |
| `frontend/src/types/model.ts` | 11 处接口新增 `cache_creation_input_price`（响应类加 `resolved_cache_creation_input_price`） |
| `frontend/src/lib/billing.ts` | `BillingSubmitData` / `BillingFormValues` / `buildBillingSubmitData()` 全分支 |
| `frontend/src/lib/modelProviderPricingHistory.ts` | `ProviderBillingFormValues` 和 `getPriceHistoryFormValues()` 全分支 |
| `frontend/src/lib/__tests__/modelProviderPricingHistory.test.ts` | fixture + 断言更新 |
| `frontend/src/components/models/ModelProviderBillingFields.tsx` | `TierInputValue` / `BillingFormValues`；tiered 行新增 Input（grid 7→8 列）；flat 段新增 Input（grid 2→3 列）；`appendTier()` 默认值 |
| `frontend/src/components/models/ModelForm.tsx` | FormData、defaults、mapping→form 转换、所有 submit 分支 |
| `frontend/src/components/models/ModelProviderForm.tsx` | 同 ModelForm 模式 + `setValue` 在 `applyPriceHistory` 中 |
| `frontend/src/components/providers/ProviderModelBulkUpgradeDialog.tsx` | FormData、buildDefaultPricing（5 分支）、payload 序列化 |
| `frontend/src/components/models/BillingDisplay.tsx` | `BillingTier` / props 加 `cacheCreationInputPrice`，cache suffix 同时显示读+写价 |
| `frontend/src/app/models/detail/page.tsx` | 两处 `<BillingDisplay>` 调用传新 prop |

## 关键设计决策 (Key Design Decisions)

### 1. Token 拆分语义

`calculate_cost` 中按 read + write + non-cached 三段拆分输入 token：

```python
c_in = min(int(cached_input_tokens or 0), in_tokens)
c_create = min(int(cache_creation_input_tokens or 0), in_tokens)
total_cached = c_in + c_create
if total_cached > in_tokens:
    # 按比例收缩，避免双重计算
    scale = Decimal(in_tokens) / Decimal(total_cached)
    c_in = int(Decimal(c_in) * scale)
    c_create = int(Decimal(c_create) * scale)
non_cached_in = max(in_tokens - c_in - c_create, 0)
```

**为什么需要收缩**：OpenAI 语义下 `cached_tokens ⊆ prompt_tokens`，Anthropic 语义下 `cache_read_input_tokens` 和 `cache_creation_input_tokens` 都是独立计数（理论上和 `input_tokens` 无关）。保守地按 `min(..., in_tokens)` 截断每个值，并当两者之和超过 `in_tokens` 时按比例缩放，保证总账单不超 input 量。

### 2. 价格回退链

`cache_creation_input_price` 为空时，回退顺序为：
1. `cache_creation_input_price`（显式写价）
2. `cached_input_price`（读价）
3. `input_price`（基础价）

### 3. CostBreakdown 字段

`cached_input_cost` 字段保持不变（缓存输入合计），写价成本折进这个字段，**不新增字段**，避免 DB schema 改动。`CostBreakdown` 注释已说明。

### 4. `cached_output_price` 不删除

保留字段不删（避免破坏已存数据/导入导出），但本次不再依赖它。**Reviewer 重点确认**：是否同意保留这个 dead path，或者应该单独开一个清理任务。

## 重点关注点 (Things to Review Carefully)

### 1. 计费正确性 ⭐⭐⭐

- `backend/app/common/costs.py:430-470` 的 read + write + non-cached 三段拆分逻辑
- 特别注意：现有的 `cached_exceeds_input` 测试（`cached_input_tokens=200k`、`input_tokens=100k`）期望 `cached_input_cost=0.1`，我的修改不应该破坏这个行为
- **务必跑一下**：
  ```bash
  cd backend && .venv/bin/python -m pytest tests/unit/test_common/test_costs.py -v
  ```
  应该有 44 个测试通过（34 旧 + 10 新）

### 2. 前端标签语义 ⭐⭐⭐

- **确认** `messages/en.json:528` 的 `cachedInputPrice` 现在是 "Cache Read Price"
- **确认** `messages/zh.json:528` 的 `cachedInputPrice` 现在是 "缓存读取价格"
- **确认** `cacheCreationInputPrice` 新增且文案正确
- **确认** `cachedOutputPrice` 标签是否需要保留（语义上是"缓存输出价"，但 `cached_output_tokens` 从未填充过）

### 3. 持久化往返 ⭐⭐

- `backend/app/repositories/sqlalchemy/model_repo.py` 的 update_* 方法用 `model_dump(exclude_unset=True)`，自动兼容新字段 ✅
- 确认 `_mapping_to_domain` 和 `_provider_mapping_to_domain` 都读取了新列
- **务必验证**：`backend/migrations/add_cache_creation_price_columns.sql` 的语法是否与你使用的数据库兼容（目前是 PostgreSQL/SQLite 共用 ALTER TABLE ADD COLUMN）

### 4. Proxy 集成 ⭐⭐

- `backend/app/services/proxy_service.py` 的 4 处 `resolve_billing` 调用，确认都补了 `model_cache_creation_input_price` 和 `provider_cache_creation_input_price`（用 `getattr(..., None)` 模式以兼容旧数据）
- 2 处 token 提取（line 821-832 非流式、line 1440-1452 流式）都从 `usage_details.get("cache_creation_input_tokens")` 读取
- 构造一个带 cache 的请求，确认日志中 `cached_input_cost` 是 read + write 合计

### 5. 前端表单 ⭐⭐

- 检查 `ModelProviderBillingFields.tsx` 的 grid 列数：tiered 行从 7 改到 8、flat 段从 2 改到 3
- 检查 `ModelForm.tsx` / `ModelProviderForm.tsx` / `ProviderModelBulkUpgradeDialog.tsx` 的所有 submit 分支
- 浏览器实测：填写读价和写价 → 保存 → 重新打开 → 值是否回填

### 6. 边界情况 ⭐

- 旧模型（未设写价）的回归：`cache_creation_input_price=None` 时，write tokens 应回退到 read price 或 input price（已写测试覆盖）
- `cache_billing_enabled=False` 时应忽略 write tokens（已写测试覆盖）
- `inherit_model_default` 时 provider 的写价应被清零（已写测试覆盖）

## 验证清单 (Verification Checklist)

### 后端

```bash
cd backend
.venv/bin/python -m pytest tests/unit/ -q          # 期望：596 passed
.venv/bin/python -m pytest tests/unit/test_common/test_costs.py -v  # 期望：44 passed
```

### 前端

```bash
cd frontend
npm test                                              # 期望：16 passed
node_modules/.bin/tsc --noEmit                        # 期望：无输出
node_modules/.bin/eslint src/types/model.ts src/lib/billing.ts \
  src/lib/modelProviderPricingHistory.ts \
  src/components/models/ModelProviderBillingFields.tsx \
  src/components/models/ModelForm.tsx \
  src/components/models/ModelProviderForm.tsx \
  src/components/providers/ProviderModelBulkUpgradeDialog.tsx \
  src/components/models/BillingDisplay.tsx \
  src/app/models/detail/page.tsx \
  src/lib/__tests__/modelProviderPricingHistory.test.ts
                                                       # 期望：无输出
```

### 端到端

1. 起 backend + frontend，构造一个带 cache 的 Anthropic 请求（usage 含 `cache_read_input_tokens` 和 `cache_creation_input_tokens`），走 proxy 后查 `request_logs.cached_input_cost`：
   - 缓存读 token × 读价 + 缓存写 token × 写价 = 合计
2. 起旧库跑一次，确认 `ensure_columns` 把两表的新列加上、二次启动不报错
3. 在前端填读价和写价，保存，重新打开，确认回填；切语言，确认标签语义对齐

## 不在本 PR 范围 (Out of Scope)

- **不删除 `cached_output_price` / `cached_output_tokens` 字段**：保留以避免破坏已存数据/导入导出；后续单独清理
- **不拆分 `CostBreakdown` 字段**：写价成本折进 `cached_input_cost`（不区分 read/write），避免 `RequestLog` schema 改动
- **不在日志中显示 read/write 成本拆分**：`cached_input_cost` / `cached_output_cost` 列写入但从不读回，本次默认不做

## 提问 (Questions for Reviewer)

1. 是否同意保留 `cached_output_price` / `cached_output_tokens` 这条死链？还是要求本次就清理？
2. `CostBreakdown` 是否需要拆出独立的 `cache_creation_input_cost` 字段？是否要求日志可读回？
3. i18n 标签用 "Cache Read / 缓存读取"、"Cache Write / 缓存写入" 是否符合产品命名？
4. 计费核心的 read + write + non-cached 三段拆分 + 比例收缩算法，是否同意这个保守实现？
5. 数据库迁移文件 `add_cache_creation_price_columns.sql` 是否需要额外加索引/约束？
