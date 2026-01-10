# LLM Gateway 模块拆分设计

## 模块概览

项目拆分为以下独立可开发的模块，每个模块可由不同开发者并行开发。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              模块依赖关系图                                   │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │   M1: 基础设施    │
                    │  (DB/Config/Common)│
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ M2: 数据访问层   │  │ M3: 规则引擎    │  │ M4: 上游适配器  │
│  (Repository)   │  │ (Rule Engine)   │  │ (Providers)     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   M5: 业务服务层     │
                    │    (Services)       │
                    └─────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │ M6: 代理 API    │             │ M7: 管理 API    │
    │ (Proxy Routes)  │             │ (Admin Routes)  │
    └─────────────────┘             └─────────────────┘

                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │                  M8: 前端管理面板                     │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
    │  │供应商管理│ │ 模型管理 │ │API Key管理│ │ 日志查询 ││
    │  └──────────┘ └──────────┘ └──────────┘ └──────────┘│
    └─────────────────────────────────────────────────────┘
```

---

## M1: 基础设施模块

### 模块职责
- 数据库连接与会话管理
- 配置管理（环境变量、多数据库切换）
- 公共工具函数（脱敏、Token计数、计时器、错误处理等）

### 文件结构
```
backend/app/
├── config.py                 # 配置管理
├── db/
│   ├── __init__.py
│   ├── session.py            # 数据库会话管理
│   └── models.py             # ORM 模型定义
└── common/
    ├── __init__.py
    ├── http_client.py        # HTTP 客户端封装
    ├── token_counter.py      # Token 计数器
    ├── sanitizer.py          # 数据脱敏
    ├── errors.py             # 错误定义
    ├── timer.py              # 计时器
    └── utils.py              # 工具函数
```

### 接口定义

#### config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_TYPE: str = "sqlite"  # sqlite | postgresql
    DATABASE_URL: str = "sqlite:///./llm_gateway.db"
    
    # 应用配置
    APP_NAME: str = "LLM Gateway"
    DEBUG: bool = False
    
    # 重试配置
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_DELAY_MS: int = 1000

    class Config:
        env_file = ".env"
```

#### common/sanitizer.py
```python
def sanitize_authorization(value: str) -> str:
    """脱敏 authorization 字段"""
    # Bearer sk-xxx...xxx -> Bearer sk-***...***
    pass

def sanitize_headers(headers: dict) -> dict:
    """脱敏请求头"""
    pass
```

#### common/token_counter.py
```python
from abc import ABC, abstractmethod

class TokenCounter(ABC):
    @abstractmethod
    def count_tokens(self, text: str, model: str) -> int:
        pass

class OpenAITokenCounter(TokenCounter):
    def count_tokens(self, text: str, model: str) -> int:
        # 使用 tiktoken 计算
        pass

class AnthropicTokenCounter(TokenCounter):
    def count_tokens(self, text: str, model: str) -> int:
        pass
```

### 测试要点
- [ ] 配置加载正确性（环境变量优先级）
- [ ] 数据库连接（SQLite/PostgreSQL 切换）
- [ ] 脱敏函数（authorization 字段打码）
- [ ] Token 计数准确性

### 预估工时
**2-3 天**

---

## M2: 数据访问层模块

### 模块职责
- 定义 Repository 抽象接口
- 实现 SQLAlchemy 具体实现
- 支持 SQLite 和 PostgreSQL

### 文件结构
```
backend/app/
├── domain/                        # 领域模型/DTO
│   ├── __init__.py
│   ├── provider.py
│   ├── model.py
│   ├── api_key.py
│   └── log.py
└── repositories/
    ├── __init__.py
    ├── base.py                    # 基础 Repository 接口
    ├── provider_repo.py           # 供应商 Repository 接口
    ├── model_repo.py              # 模型 Repository 接口
    ├── api_key_repo.py            # API Key Repository 接口
    ├── log_repo.py                # 日志 Repository 接口
    └── sqlalchemy/                # SQLAlchemy 实现
        ├── __init__.py
        ├── provider_repo.py
        ├── model_repo.py
        ├── api_key_repo.py
        └── log_repo.py
```

### 接口定义

#### repositories/provider_repo.py
```python
from abc import ABC, abstractmethod
from typing import Optional, List
from app.domain.provider import Provider, ProviderCreate, ProviderUpdate

class ProviderRepository(ABC):
    @abstractmethod
    async def create(self, data: ProviderCreate) -> Provider:
        pass
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[Provider]:
        pass
    
    @abstractmethod
    async def get_all(self, is_active: Optional[bool] = None) -> List[Provider]:
        pass
    
    @abstractmethod
    async def update(self, id: int, data: ProviderUpdate) -> Optional[Provider]:
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        pass
```

#### repositories/model_repo.py
```python
from abc import ABC, abstractmethod
from typing import Optional, List
from app.domain.model import ModelMapping, ModelMappingProvider

class ModelRepository(ABC):
    @abstractmethod
    async def create_mapping(self, data: ModelMappingCreate) -> ModelMapping:
        pass
    
    @abstractmethod
    async def get_mapping(self, requested_model: str) -> Optional[ModelMapping]:
        pass
    
    @abstractmethod
    async def get_all_mappings(self) -> List[ModelMapping]:
        pass
    
    @abstractmethod
    async def add_provider_mapping(self, data: ModelMappingProviderCreate) -> ModelMappingProvider:
        pass
    
    @abstractmethod
    async def get_provider_mappings(self, requested_model: str) -> List[ModelMappingProvider]:
        pass
```

#### repositories/log_repo.py
```python
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

class LogRepository(ABC):
    @abstractmethod
    async def create(self, data: LogCreate) -> RequestLog:
        pass
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[RequestLog]:
        pass
    
    @abstractmethod
    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        requested_model: Optional[str] = None,
        provider_id: Optional[int] = None,
        status_min: Optional[int] = None,
        status_max: Optional[int] = None,
        has_error: Optional[bool] = None,
        api_key_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[RequestLog], int]:
        pass
```

### 测试要点
- [ ] CRUD 操作正确性
- [ ] 分页查询
- [ ] 多条件过滤
- [ ] 外键约束
- [ ] SQLite 与 PostgreSQL 兼容性

### 预估工时
**3-4 天**

---

## M3: 规则引擎模块

### 模块职责
- 定义规则上下文结构
- 实现规则评估逻辑
- 输出候选供应商及其目标模型

### 文件结构
```
backend/app/rules/
├── __init__.py
├── engine.py              # 规则引擎核心
├── context.py             # 规则上下文
├── evaluator.py           # 规则评估器
└── models.py              # 规则模型定义
```

### 接口定义

#### rules/context.py
```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RuleContext:
    """规则引擎上下文"""
    current_model: str              # requested_model
    headers: Dict[str, str]         # 请求头
    request_body: Dict[str, Any]    # 请求体
    token_usage: TokenUsage         # Token 消耗

@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int = 0
```

#### rules/models.py
```python
from dataclasses import dataclass
from typing import List, Optional, Any

@dataclass
class Rule:
    """规则定义"""
    field: str              # 匹配字段 (model, headers.x-custom, body.temperature)
    operator: str           # 操作符 (eq, ne, gt, lt, gte, lte, contains, regex)
    value: Any              # 匹配值
    
@dataclass
class RuleSet:
    """规则集（AND 逻辑）"""
    rules: List[Rule]
    
@dataclass
class CandidateProvider:
    """候选供应商"""
    provider_id: int
    provider_name: str
    target_model: str
    priority: int
    weight: int
```

#### rules/engine.py
```python
from typing import List
from app.rules.context import RuleContext
from app.rules.models import CandidateProvider

class RuleEngine:
    """规则引擎"""
    
    async def evaluate(
        self,
        context: RuleContext,
        model_mapping: ModelMapping,
        provider_mappings: List[ModelMappingProvider]
    ) -> List[CandidateProvider]:
        """
        评估所有规则，返回候选供应商列表
        
        流程:
        1. 检查模型级规则 (model_mapping.matching_rules)
        2. 对每个供应商检查供应商级规则 (provider_mapping.provider_rules)
        3. 返回所有通过的供应商及其 target_model
        """
        pass
```

### 规则格式示例
```json
{
  "rules": [
    {"field": "headers.x-priority", "operator": "eq", "value": "high"},
    {"field": "body.temperature", "operator": "lte", "value": 0.5}
  ],
  "logic": "AND"
}
```

### 测试要点
- [ ] 各类操作符 (eq, ne, gt, lt, contains, regex)
- [ ] 嵌套字段访问 (headers.x-custom, body.messages[0].role)
- [ ] 多规则 AND/OR 组合
- [ ] 空规则处理（默认通过）
- [ ] 无匹配供应商处理

### 预估工时
**2-3 天**

---

## M4: 上游供应商适配器模块

### 模块职责
- 封装上游 API 调用
- 支持 OpenAI 和 Anthropic 协议
- 处理流式响应

### 文件结构
```
backend/app/providers/
├── __init__.py
├── base.py                # 基础适配器接口
├── openai_client.py       # OpenAI 客户端
└── anthropic_client.py    # Anthropic 客户端
```

### 接口定义

#### providers/base.py
```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any
from dataclasses import dataclass

@dataclass
class ProviderResponse:
    status_code: int
    headers: dict
    body: Any
    first_byte_delay_ms: int
    total_time_ms: int

class ProviderClient(ABC):
    """上游供应商客户端基类"""
    
    @abstractmethod
    async def forward(
        self,
        base_url: str,
        api_key: str,
        path: str,
        method: str,
        headers: dict,
        body: dict,
        target_model: str
    ) -> ProviderResponse:
        """转发请求到上游供应商"""
        pass
    
    @abstractmethod
    async def forward_stream(
        self,
        base_url: str,
        api_key: str,
        path: str,
        method: str,
        headers: dict,
        body: dict,
        target_model: str
    ) -> AsyncGenerator[bytes, None]:
        """转发流式请求"""
        pass
```

#### providers/openai_client.py
```python
class OpenAIClient(ProviderClient):
    """OpenAI 协议客户端"""
    
    async def forward(self, ...) -> ProviderResponse:
        # 1. 复制 body，替换 model 字段
        # 2. 转发到 base_url + path
        # 3. 记录延迟指标
        pass
```

### 测试要点
- [ ] 请求转发正确性
- [ ] 只修改 model 字段验证
- [ ] 流式响应处理
- [ ] 错误响应处理
- [ ] 超时处理

### 预估工时
**2-3 天**

---

## M5: 业务服务层模块

### 模块职责
- 代理核心逻辑编排
- 重试与故障切换
- 轮询策略实现
- 日志记录服务

### 文件结构
```
backend/app/services/
├── __init__.py
├── proxy_service.py       # 代理核心服务
├── provider_service.py    # 供应商管理服务
├── model_service.py       # 模型管理服务
├── api_key_service.py     # API Key 服务
├── log_service.py         # 日志服务
├── retry_handler.py       # 重试处理器
└── strategy.py            # 策略服务(轮询)
```

### 接口定义

#### services/proxy_service.py
```python
class ProxyService:
    """代理核心服务"""
    
    def __init__(
        self,
        model_repo: ModelRepository,
        provider_repo: ProviderRepository,
        log_repo: LogRepository,
        rule_engine: RuleEngine,
        strategy: SelectionStrategy,
        retry_handler: RetryHandler,
        token_counter: TokenCounter
    ):
        pass
    
    async def process_request(
        self,
        api_key_id: int,
        api_key_name: str,
        protocol: str,
        path: str,
        method: str,
        headers: dict,
        body: dict
    ) -> ProxyResponse:
        """
        处理代理请求
        
        流程:
        1. 提取 requested_model
        2. 计算输入 Token
        3. 构建规则上下文
        4. 规则引擎匹配 -> 候选供应商列表
        5. 轮询策略选择供应商
        6. 转发请求 (含重试/切换逻辑)
        7. 计算输出 Token
        8. 记录日志
        9. 返回响应
        """
        pass
```

#### services/retry_handler.py
```python
class RetryHandler:
    """重试与故障切换处理器"""
    
    async def execute_with_retry(
        self,
        candidates: List[CandidateProvider],
        forward_fn: Callable,
        **kwargs
    ) -> tuple[ProviderResponse, int, CandidateProvider]:
        """
        带重试的请求执行
        
        逻辑:
        - status >= 500: 同供应商重试 3 次，间隔 1s
        - status < 500: 直接切换下一供应商
        - 全部失败: 返回最后一次错误
        
        Returns:
            (响应, 重试次数, 最终使用的供应商)
        """
        pass
```

#### services/strategy.py
```python
from abc import ABC, abstractmethod

class SelectionStrategy(ABC):
    """供应商选择策略"""
    
    @abstractmethod
    async def select(
        self,
        candidates: List[CandidateProvider],
        requested_model: str
    ) -> CandidateProvider:
        pass

class RoundRobinStrategy(SelectionStrategy):
    """轮询策略"""
    
    async def select(self, candidates, requested_model) -> CandidateProvider:
        # 使用原子计数器实现并发安全的轮询
        pass
```

### 测试要点
- [ ] 完整代理流程
- [ ] 重试逻辑 (>=500 同供应商重试 3 次)
- [ ] 切换逻辑 (<500 直接切换)
- [ ] 轮询策略正确性与并发安全
- [ ] 日志记录完整性

### 预估工时
**4-5 天**

---

## M6: 代理 API 模块

### 模块职责
- OpenAI 兼容接口
- Anthropic 兼容接口
- API Key 鉴权

### 文件结构
```
backend/app/api/
├── __init__.py
├── deps.py                # 依赖注入
└── proxy/
    ├── __init__.py
    ├── openai.py          # OpenAI 兼容接口
    └── anthropic.py       # Anthropic 兼容接口
```

### 接口定义

#### api/proxy/openai.py
```python
from fastapi import APIRouter, Depends, Request, Header
from app.api.deps import get_api_key, get_proxy_service

router = APIRouter()

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str = Header(...),
    proxy_service: ProxyService = Depends(get_proxy_service)
):
    """OpenAI Chat Completions 代理接口"""
    pass

@router.post("/v1/completions")
async def completions(request: Request, ...):
    """OpenAI Completions 代理接口"""
    pass

@router.post("/v1/embeddings")
async def embeddings(request: Request, ...):
    """OpenAI Embeddings 代理接口"""
    pass
```

#### api/proxy/anthropic.py
```python
router = APIRouter()

@router.post("/v1/messages")
async def messages(request: Request, ...):
    """Anthropic Messages 代理接口"""
    pass
```

### 测试要点
- [ ] API Key 鉴权
- [ ] 请求解析
- [ ] 响应格式正确性
- [ ] 流式响应
- [ ] 错误处理

### 预估工时
**2-3 天**

---

## M7: 管理 API 模块

### 模块职责
- 供应商 CRUD API
- 模型映射 CRUD API
- API Key CRUD API
- 日志查询 API

### 文件结构
```
backend/app/api/admin/
├── __init__.py
├── providers.py           # 供应商管理
├── models.py              # 模型管理
├── api_keys.py            # API Key 管理
└── logs.py                # 日志查询
```

### API 详情见下方 API 文档

### 测试要点
- [ ] CRUD 操作
- [ ] 参数校验
- [ ] 分页与过滤
- [ ] 错误处理

### 预估工时
**2-3 天**

---

## M8: 前端管理面板模块

### 子模块拆分

#### M8.1: 基础框架与通用组件
- 项目初始化 (Next.js + TypeScript)
- UI 组件库集成 (shadcn/ui)
- 通用组件开发
- API 客户端封装

**预估工时: 2-3 天**

#### M8.2: 供应商管理页面
- 供应商列表
- 新增/编辑表单
- 删除确认

**预估工时: 1-2 天**

#### M8.3: 模型管理页面
- 模型映射列表
- 模型-供应商映射配置
- 规则编辑器

**预估工时: 3-4 天**

#### M8.4: API Key 管理页面
- API Key 列表
- 新增（key_value 后端生成）
- 状态管理

**预估工时: 1-2 天**

#### M8.5: 日志查询页面
- 日志列表（分页、排序）
- 多条件筛选器
- 日志详情页

**预估工时: 2-3 天**

---

## 开发顺序建议

```
Phase 1 (并行):
├── M1: 基础设施 (开发者 A)
├── M3: 规则引擎 (开发者 B)
└── M8.1: 前端基础框架 (开发者 C)

Phase 2 (并行, 依赖 M1):
├── M2: 数据访问层 (开发者 A)
├── M4: 上游适配器 (开发者 B)
└── M8.2: 供应商管理页面 (开发者 C)

Phase 3 (并行, 依赖 M2, M3, M4):
├── M5: 业务服务层 (开发者 A)
├── M7: 管理 API (开发者 B)
└── M8.3: 模型管理页面 (开发者 C)

Phase 4 (并行, 依赖 M5):
├── M6: 代理 API (开发者 A)
├── M8.4: API Key 管理页面 (开发者 B)
└── M8.5: 日志查询页面 (开发者 C)

Phase 5:
└── 集成测试与修复
```

---

## 总预估工时

| 模块 | 预估工时 |
|------|----------|
| M1: 基础设施 | 2-3 天 |
| M2: 数据访问层 | 3-4 天 |
| M3: 规则引擎 | 2-3 天 |
| M4: 上游适配器 | 2-3 天 |
| M5: 业务服务层 | 4-5 天 |
| M6: 代理 API | 2-3 天 |
| M7: 管理 API | 2-3 天 |
| M8: 前端管理面板 | 9-14 天 |
| 集成测试与修复 | 3-5 天 |
| **总计** | **29-43 天** (单人) |

**并行开发 (3人)**: 约 **12-18 天**
