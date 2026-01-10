# LLM Gateway 架构设计文档

## 1. 宏观架构设计

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端层                                        │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │ OpenAI SDK   │    │ Anthropic SDK│    │  直接 HTTP   │                │
│    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
└───────────┼───────────────────┼───────────────────┼────────────────────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM Gateway 代理层                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        FastAPI 后端服务                                 │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │  Proxy API  │  │  Admin API  │  │   Auth      │  │  Middleware │   │ │
│  │  │ (代理接口)   │  │ (管理接口)  │  │  (鉴权)     │  │   (中间件)  │   │ │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘   │ │
│  │         │                │                                             │ │
│  │         ▼                ▼                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                      Service 业务层                               │ │ │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │ │ │
│  │  │  │  Proxy     │ │  Rule      │ │  Provider  │ │  Strategy  │    │ │ │
│  │  │  │  Service   │ │  Engine    │ │  Client    │ │  (轮询)    │    │ │ │
│  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │ │ │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │ │ │
│  │  │  │  Retry     │ │  Token     │ │  Log       │ │  Provider  │    │ │ │
│  │  │  │  Handler   │ │  Counter   │ │  Service   │ │  Service   │    │ │ │
│  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                          │                                             │ │
│  │                          ▼                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Repository 数据访问层                          │ │ │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │ │ │
│  │  │  │  Provider  │ │  Model     │ │  ApiKey    │ │  Log       │    │ │ │
│  │  │  │  Repo      │ │  Repo      │ │  Repo      │ │  Repo      │    │ │ │
│  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                          │                                             │ │
│  │                          ▼                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                     Database Layer                                │ │ │
│  │  │         ┌───────────────────┬───────────────────┐                │ │ │
│  │  │         │      SQLite       │    PostgreSQL     │                │ │ │
│  │  │         │     (默认)        │      (可选)       │                │ │ │
│  │  │         └───────────────────┴───────────────────┘                │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           上游供应商层                                       │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │   OpenAI     │    │  Anthropic   │    │ 其他兼容供应商│                │
│    └──────────────┘    └──────────────┘    └──────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           前端管理面板                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     Next.js + TypeScript                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │供应商管理   │  │ 模型管理    │  │ API Key管理 │  │  日志查询   │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心请求流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          代理请求处理流程                                    │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────┐
     │  开始   │
     └────┬────┘
          │
          ▼
    ┌───────────────┐
    │ 1. 接收请求    │ ◄── OpenAI/Anthropic 格式请求
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐     ┌─────────────┐
    │ 2. API Key    │────►│  验证失败   │──► 返回 401
    │    鉴权       │     └─────────────┘
    └───────┬───────┘
            │ 验证成功
            ▼
    ┌───────────────┐
    │ 3. 解析请求体  │ ◄── 提取 requested_model, messages 等
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 4. 计算输入   │ ◄── Token 计数器
    │    Token      │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 5. 规则引擎   │ ◄── 上下文: model, headers, body, token_usage
    │    匹配       │ ──► 输出: 候选供应商列表 + 各自 target_model
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 6. 轮询策略   │ ◄── 从候选列表中选择当前供应商
    │    选择       │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 7. 替换 model │ ◄── 仅修改 model 字段
    │    字段       │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 8. 转发请求   │
    │    到上游     │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐     ┌─────────────────────────────────┐
    │ 9. 检查响应   │────►│ status >= 500:                  │
    │    状态码     │     │   - 同供应商重试 (max 3, 1s间隔)│
    └───────┬───────┘     │ status < 500:                   │
            │             │   - 切换下一供应商              │
            │             └─────────────┬───────────────────┘
            │                           │
            │ ◄─────────────────────────┘
            ▼
    ┌───────────────┐     ┌─────────────┐
    │ 10. 所有供应商│────►│ 返回最后    │
    │     均失败?   │ 是  │ 失败响应    │
    └───────┬───────┘     └─────────────┘
            │ 否
            ▼
    ┌───────────────┐
    │ 11. 计算输出  │
    │     Token     │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 12. 记录日志  │ ◄── 脱敏 authorization 后入库
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 13. 返回响应  │
    │     给客户端  │
    └───────┬───────┘
            │
            ▼
       ┌─────────┐
       │  结束   │
       └─────────┘
```

### 1.3 技术选型

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| 后端框架 | Python + FastAPI | 高性能异步框架 |
| 数据库 | SQLite (默认) / PostgreSQL | 通过配置切换 |
| ORM | SQLAlchemy | 支持多数据库 |
| 数据库迁移 | Alembic | 版本化迁移管理 |
| HTTP 客户端 | httpx | 异步 HTTP 客户端 |
| 前端框架 | Next.js + TypeScript | 现代化 React 框架 |
| UI 组件 | shadcn/ui + Tailwind CSS | 现代化组件库 |
| 状态管理 | React Query | 服务端状态管理 |

## 2. 代码结构设计

### 2.1 后端目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置管理
│   │
│   ├── api/                       # API 路由层
│   │   ├── __init__.py
│   │   ├── deps.py                # 依赖注入
│   │   ├── proxy/                 # 代理接口
│   │   │   ├── __init__.py
│   │   │   ├── openai.py          # OpenAI 兼容接口
│   │   │   └── anthropic.py       # Anthropic 兼容接口
│   │   └── admin/                 # 管理接口
│   │       ├── __init__.py
│   │       ├── providers.py       # 供应商管理
│   │       ├── models.py          # 模型管理
│   │       ├── api_keys.py        # API Key 管理
│   │       └── logs.py            # 日志查询
│   │
│   ├── services/                  # 业务服务层
│   │   ├── __init__.py
│   │   ├── proxy_service.py       # 代理核心服务
│   │   ├── provider_service.py    # 供应商服务
│   │   ├── model_service.py       # 模型服务
│   │   ├── api_key_service.py     # API Key 服务
│   │   ├── log_service.py         # 日志服务
│   │   ├── retry_handler.py       # 重试处理器
│   │   └── strategy.py            # 策略服务(轮询)
│   │
│   ├── rules/                     # 规则引擎
│   │   ├── __init__.py
│   │   ├── engine.py              # 规则引擎核心
│   │   ├── context.py             # 规则上下文
│   │   ├── evaluator.py           # 规则评估器
│   │   └── models.py              # 规则模型定义
│   │
│   ├── providers/                 # 上游供应商适配
│   │   ├── __init__.py
│   │   ├── base.py                # 基础适配器接口
│   │   ├── openai_client.py       # OpenAI 客户端
│   │   └── anthropic_client.py    # Anthropic 客户端
│   │
│   ├── repositories/              # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py                # 基础 Repository 接口
│   │   ├── provider_repo.py       # 供应商 Repository 接口
│   │   ├── model_repo.py          # 模型 Repository 接口
│   │   ├── api_key_repo.py        # API Key Repository 接口
│   │   ├── log_repo.py            # 日志 Repository 接口
│   │   └── sqlalchemy/            # SQLAlchemy 实现
│   │       ├── __init__.py
│   │       ├── provider_repo.py
│   │       ├── model_repo.py
│   │       ├── api_key_repo.py
│   │       └── log_repo.py
│   │
│   ├── db/                        # 数据库层
│   │   ├── __init__.py
│   │   ├── session.py             # 数据库会话管理
│   │   ├── models.py              # SQLAlchemy ORM 模型
│   │   └── migrations/            # Alembic 迁移
│   │       ├── env.py
│   │       ├── versions/
│   │       └── alembic.ini
│   │
│   ├── domain/                    # 领域模型
│   │   ├── __init__.py
│   │   ├── provider.py            # 供应商 DTO
│   │   ├── model.py               # 模型 DTO
│   │   ├── api_key.py             # API Key DTO
│   │   ├── log.py                 # 日志 DTO
│   │   └── request.py             # 请求/响应 DTO
│   │
│   └── common/                    # 公共模块
│       ├── __init__.py
│       ├── http_client.py         # HTTP 客户端封装
│       ├── token_counter.py       # Token 计数器
│       ├── sanitizer.py           # 数据脱敏
│       ├── errors.py              # 错误定义
│       ├── timer.py               # 计时器
│       └── utils.py               # 工具函数
│
├── tests/                         # 测试目录
│   ├── __init__.py
│   ├── conftest.py                # 测试配置
│   ├── unit/                      # 单元测试
│   │   ├── test_rules/
│   │   ├── test_services/
│   │   ├── test_providers/
│   │   ├── test_repositories/
│   │   └── test_common/
│   └── integration/               # 集成测试
│       └── test_proxy_flow.py
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── README.md
```

### 2.2 前端目录结构

```
frontend/
├── src/
│   ├── app/                       # Next.js App Router
│   │   ├── layout.tsx             # 根布局
│   │   ├── page.tsx               # 首页
│   │   ├── providers/             # 供应商管理页面
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── models/                # 模型管理页面
│   │   │   ├── page.tsx
│   │   │   └── [model]/
│   │   │       └── page.tsx
│   │   ├── api-keys/              # API Key 管理页面
│   │   │   └── page.tsx
│   │   └── logs/                  # 日志查询页面
│   │       ├── page.tsx
│   │       └── [id]/
│   │           └── page.tsx
│   │
│   ├── components/                # 组件
│   │   ├── ui/                    # 基础 UI 组件 (shadcn)
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── table.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── form.tsx
│   │   │   └── ...
│   │   ├── common/                # 通用业务组件
│   │   │   ├── DataTable.tsx      # 通用数据表格
│   │   │   ├── Pagination.tsx     # 分页组件
│   │   │   ├── FilterBar.tsx      # 筛选栏
│   │   │   ├── JsonEditor.tsx     # JSON 编辑器
│   │   │   ├── JsonViewer.tsx     # JSON 查看器
│   │   │   ├── ConfirmDialog.tsx  # 确认对话框
│   │   │   └── LoadingState.tsx   # 加载状态
│   │   ├── providers/             # 供应商相关组件
│   │   │   ├── ProviderForm.tsx
│   │   │   └── ProviderList.tsx
│   │   ├── models/                # 模型相关组件
│   │   │   ├── ModelForm.tsx
│   │   │   ├── ModelProviderForm.tsx
│   │   │   └── RuleEditor.tsx     # 规则编辑器
│   │   ├── api-keys/              # API Key 相关组件
│   │   │   ├── ApiKeyForm.tsx
│   │   │   └── ApiKeyList.tsx
│   │   └── logs/                  # 日志相关组件
│   │       ├── LogFilters.tsx
│   │       ├── LogList.tsx
│   │       └── LogDetail.tsx
│   │
│   ├── lib/                       # 工具库
│   │   ├── api/                   # API 客户端
│   │   │   ├── client.ts          # HTTP 客户端
│   │   │   ├── providers.ts       # 供应商 API
│   │   │   ├── models.ts          # 模型 API
│   │   │   ├── api-keys.ts        # API Key API
│   │   │   └── logs.ts            # 日志 API
│   │   ├── hooks/                 # 自定义 Hooks
│   │   │   ├── useProviders.ts
│   │   │   ├── useModels.ts
│   │   │   ├── useApiKeys.ts
│   │   │   └── useLogs.ts
│   │   └── utils/                 # 工具函数
│   │       ├── format.ts
│   │       └── validation.ts
│   │
│   └── types/                     # TypeScript 类型定义
│       ├── provider.ts
│       ├── model.ts
│       ├── api-key.ts
│       ├── log.ts
│       └── common.ts
│
├── public/
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── next.config.js
└── README.md
```

## 3. 数据库模型设计

### 3.1 ER 图

```
┌─────────────────────┐
│   service_providers │
├─────────────────────┤
│ id (PK)             │
│ name                │
│ base_url            │
│ protocol            │
│ api_type            │
│ api_key             │
│ is_active           │
│ created_at          │
│ updated_at          │
└─────────┬───────────┘
          │
          │ 1:N
          │
┌─────────▼───────────┐         ┌─────────────────────┐
│model_mapping_providers│◄───────│   model_mappings    │
├─────────────────────┤   N:1   ├─────────────────────┤
│ id (PK)             │         │ requested_model(PK) │
│ requested_model(FK) │─────────│ strategy            │
│ provider_id (FK)    │         │ matching_rules      │
│ target_model_name   │         │ capabilities        │
│ provider_rules      │         │ is_active           │
│ priority            │         │ created_at          │
│ weight              │         │ updated_at          │
│ is_active           │         └─────────────────────┘
│ created_at          │
│ updated_at          │
└─────────────────────┘

┌─────────────────────┐         ┌─────────────────────┐
│     api_keys        │         │    request_logs     │
├─────────────────────┤    1:N  ├─────────────────────┤
│ id (PK)             │◄────────│ id (PK)             │
│ key_name (unique)   │         │ request_time        │
│ key_value           │         │ api_key_id (FK)     │
│ is_active           │         │ api_key_name        │
│ created_at          │         │ requested_model     │
│ last_used_at        │         │ target_model        │
└─────────────────────┘         │ provider_id (FK)    │
                                │ retry_count         │
                                │ first_byte_delay_ms │
                                │ total_time_ms       │
                                │ input_tokens        │
                                │ output_tokens       │
                                │ request_headers     │
                                │ request_body        │
                                │ response_status     │
                                │ response_body       │
                                │ error_info          │
                                │ trace_id            │
                                └─────────────────────┘
```

### 3.2 表结构详细定义

```sql
-- 供应商表
CREATE TABLE service_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    base_url VARCHAR(500) NOT NULL,
    protocol VARCHAR(50) NOT NULL,  -- 'openai' | 'anthropic'
    api_type VARCHAR(50) NOT NULL,
    api_key TEXT,                    -- 供应商的 API Key (加密存储)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模型映射表
CREATE TABLE model_mappings (
    requested_model VARCHAR(100) PRIMARY KEY,
    strategy VARCHAR(50) DEFAULT 'round_robin',
    matching_rules JSON,             -- 模型级规则
    capabilities JSON,               -- 功能描述
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模型-供应商映射表
CREATE TABLE model_mapping_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_model VARCHAR(100) NOT NULL,
    provider_id INTEGER NOT NULL,
    target_model_name VARCHAR(100) NOT NULL,
    provider_rules JSON,             -- 供应商级规则
    priority INTEGER DEFAULT 0,
    weight INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (requested_model) REFERENCES model_mappings(requested_model),
    FOREIGN KEY (provider_id) REFERENCES service_providers(id),
    UNIQUE (requested_model, provider_id)
);

-- API Key 表
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name VARCHAR(100) NOT NULL UNIQUE,
    key_value VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);

-- 请求日志表
CREATE TABLE request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_time TIMESTAMP NOT NULL,
    api_key_id INTEGER,
    api_key_name VARCHAR(100),
    requested_model VARCHAR(100),
    target_model VARCHAR(100),
    provider_id INTEGER,
    provider_name VARCHAR(100),
    retry_count INTEGER DEFAULT 0,
    first_byte_delay_ms INTEGER,
    total_time_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    request_headers JSON,            -- 已脱敏
    request_body JSON,
    response_status INTEGER,
    response_body TEXT,
    error_info TEXT,
    trace_id VARCHAR(100),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id),
    FOREIGN KEY (provider_id) REFERENCES service_providers(id)
);

-- 索引
CREATE INDEX idx_request_logs_time ON request_logs(request_time);
CREATE INDEX idx_request_logs_api_key ON request_logs(api_key_id);
CREATE INDEX idx_request_logs_model ON request_logs(requested_model);
CREATE INDEX idx_request_logs_provider ON request_logs(provider_id);
CREATE INDEX idx_request_logs_status ON request_logs(response_status);
```
