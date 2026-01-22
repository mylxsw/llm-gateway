<p align="center">
  <h1 align="center">Squirrel</h1>
  <p align="center">
    <strong>企业级 LLM 网关</strong>
  </p>
  <p align="center">
    面向 OpenAI、Anthropic 及兼容 API 的统一代理服务
  </p>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README_zh-CN.md"><strong>中文</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/fastapi-latest-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/nextjs-15-black.svg" alt="Next.js">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
</p>

---

## 概述

**Squirrel** 是一个高性能、生产就绪的代理服务，用于统一管理和访问多个大语言模型（LLM）供应商。它作为应用程序与 LLM 服务之间的智能网关，提供无缝的故障转移、负载均衡、全面的可观测性以及现代化的管理面板。

### 为什么选择 Squirrel？

- **单一集成点**：一次接入，通过统一 API 访问多个 LLM 供应商
- **零代码改动**：完全兼容 OpenAI 和 Anthropic SDK，即插即用
- **成本优化**：基于规则、优先级或成本智能路由请求
- **生产就绪**：内置重试逻辑、故障转移机制和详细的请求日志
- **全面可见**：追踪每个请求的 Token 用量、延迟指标和成本分析

---

## 核心特性

### 统一 API 接口

- **兼容 OpenAI**：全面支持 `/v1/chat/completions`、`/v1/completions`、`/v1/embeddings`、`/v1/audio/*`、`/v1/images/*`
- **兼容 Anthropic**：原生支持 `/v1/messages` 端点
- **协议转换**：使用 [litellm](https://github.com/BerriAI/litellm) 自动在 OpenAI 和 Anthropic 格式之间转换
- **流式支持**：完整的 Server-Sent Events (SSE) 支持，实现实时响应

### 智能路由

- **规则路由**：基于模型名称、请求头、消息内容或 Token 数量路由请求
- **负载均衡策略**：
  - **轮询（Round-Robin）**：在供应商之间均匀分配请求
  - **优先级（Priority）**：优先使用首选供应商，失败时回退到其他
  - **权重（Weight）**：按自定义权重比例分配请求
  - **最优成本（Cost-Based）**：根据 API 价格，自动选择价格最低的模型
- **模型映射**：将虚拟模型名称映射到多个后端供应商

### 高可用

- **自动重试**：针对服务器错误（HTTP 500+）可配置重试次数
- **供应商故障转移**：失败时无缝切换到备用供应商
- **超时管理**：可配置的请求超时，支持长时间流式响应（默认：30 分钟）

### 全面可观测性

- **全量日志记录**：完整记录请求体和响应体（包括流式响应），便于问题追溯、调试及 AI 系统效果优化
- **Token 统计**：使用 [tiktoken](https://github.com/openai/tiktoken) 自动计算 Token 用量
- **延迟指标**：首字节延迟和总响应时间
- **成本分析**：按时间、模型、供应商和 API Key 聚合统计
- **数据脱敏**：日志中自动对敏感信息进行脱敏处理

### 现代化管理面板

基于 **Next.js 15** + **TypeScript** + **shadcn/ui** 构建：

- 供应商管理，支持连接测试
- 模型映射配置，内置规则编辑器
- API Key 生成和生命周期管理
- 高级日志查看器，支持多维度筛选
- 成本统计和用量分析

---

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          客户端应用                               │
│              (OpenAI SDK, Anthropic SDK, HTTP 客户端)            │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Squirrel 网关                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      代理 API 层                           │  │
│  │         /v1/chat/completions, /v1/messages 等             │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                       服务层                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │  │
│  │  │  规则引擎   │ │  路由策略   │ │    协议转换器       │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │  │
│  │  │ Token 计数  │ │  日志服务   │ │    重试处理器       │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     数据访问层                             │  │
│  │               SQLite / PostgreSQL 数据库                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      上游 LLM 供应商                             │
│    ┌──────────┐   ┌───────────┐   ┌────────────────────────┐    │
│    │  OpenAI  │   │ Anthropic │   │   OpenAI 兼容 API      │    │
│    └──────────┘   └───────────┘   └────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

详细架构文档请参阅 [docs/architecture.md](docs/architecture.md)。

---

## 快速开始

### Docker Compose（推荐）

使用 PostgreSQL 的最快启动方式：

```bash
# 克隆仓库
git clone https://github.com/mylxsw/llm-gateway.git
cd llm-gateway

# 配置环境
cp .env.example .env
# 按需编辑 .env（可选：设置 ADMIN_USERNAME 和 ADMIN_PASSWORD）

# 启动服务
./start-docker.sh

# 停止服务
./stop-docker.sh
```

访问管理面板：**http://localhost:8000**

### Docker（单容器）

使用 SQLite 进行简单部署：

```bash
docker build -t llm-gateway .
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  --name llm-gateway \
  llm-gateway
```

### 手动安装

#### 环境要求

- Python 3.12+
- Node.js 18+
- pnpm（用于前端）

#### 后端设置

```bash
cd backend

# 安装依赖（选择一种方式）
uv sync          # 推荐：使用 uv
pip install -r requirements.txt  # 或使用 pip

# 初始化数据库
alembic upgrade head

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 前端设置

```bash
cd frontend

# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 生产构建
pnpm build && pnpm start
```

---

## 使用方法

### 基本配置

1. **添加供应商**：进入供应商页面，添加您的 LLM 供应商（如 OpenAI）
   - 设置基础 URL（如 `https://api.openai.com/v1`）
   - 添加您的 API Key
   - 选择协议类型（OpenAI 或 Anthropic）

2. **创建模型映射**：进入模型页面创建映射
   - 定义模型名称（如 `gpt-4`）
   - 关联一个或多个供应商
   - 设置路由优先级/权重

3. **生成 API Key**：在 API Keys 页面创建网关 API Key

4. **连接您的应用**：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="lgw-your-gateway-api-key"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "你好！"}]
)
```

### API 端点

#### 代理端点（OpenAI 兼容）

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/v1/models` | 获取可用模型列表 |
| POST | `/v1/chat/completions` | 对话补全 |
| POST | `/v1/completions` | 文本补全 |
| POST | `/v1/embeddings` | 生成向量嵌入 |
| POST | `/v1/audio/speech` | 文字转语音 |
| POST | `/v1/audio/transcriptions` | 语音转文字 |
| POST | `/v1/images/generations` | 图像生成 |

#### 代理端点（Anthropic 兼容）

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/v1/messages` | Messages API |

#### 管理端点

| 资源 | 端点 |
|------|------|
| 供应商 | `GET/POST /api/admin/providers`，`GET/PUT/DELETE /api/admin/providers/{id}` |
| 模型 | `GET/POST /api/admin/models`，`GET/PUT/DELETE /api/admin/models/{model}` |
| API Keys | `GET/POST /api/admin/api-keys`，`GET/PUT/DELETE /api/admin/api-keys/{id}` |
| 日志 | `GET /api/admin/logs`，`GET /api/admin/logs/stats` |

完整 API 文档请参阅 [docs/api.md](docs/api.md)。

---

## 配置说明

### 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `APP_NAME` | LLM Gateway | 应用名称 |
| `DEBUG` | false | 启用调试模式 |
| `DATABASE_TYPE` | sqlite | 数据库类型：`sqlite` 或 `postgresql` |
| `DATABASE_URL` | sqlite+aiosqlite:///./llm_gateway.db | 数据库连接字符串 |
| `RETRY_MAX_ATTEMPTS` | 3 | 500+ 错误的最大重试次数 |
| `RETRY_DELAY_MS` | 1000 | 重试间隔（毫秒） |
| `HTTP_TIMEOUT` | 1800 | 上游请求超时（秒） |
| `API_KEY_PREFIX` | lgw- | 生成的 API Key 前缀 |
| `API_KEY_LENGTH` | 32 | 生成的 API Key 长度 |
| `ADMIN_USERNAME` | - | 管理员登录用户名（可选） |
| `ADMIN_PASSWORD` | - | 管理员登录密码（可选） |
| `ADMIN_TOKEN_TTL_SECONDS` | 86400 | 管理员会话有效期（24 小时） |
| `LOG_RETENTION_DAYS` | 7 | 日志保留天数 |
| `LOG_CLEANUP_HOUR` | 4 | 日志清理时间（UTC 小时） |

### 数据库配置

**SQLite**（默认，简单部署）：
```env
DATABASE_TYPE=sqlite
DATABASE_URL=sqlite+aiosqlite:///./llm_gateway.db
```

**PostgreSQL**（推荐用于生产环境）：
```env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway
```

---

## 支持的供应商

Squirrel 可以代理任何 OpenAI 或 Anthropic 兼容的 API：

| 供应商 | 协议 | 说明 |
|--------|------|------|
| OpenAI | OpenAI | 全面支持 GPT-4、GPT-3.5、嵌入、语音、图像 |
| Anthropic | Anthropic | 通过 Messages API 支持 Claude 模型 |
| Azure OpenAI | OpenAI | 使用 Azure 端点 URL |
| 本地模型 | OpenAI | Ollama、vLLM、LocalAI 等 |
| 其他供应商 | OpenAI/Anthropic | 任何兼容的 API 端点 |

---

## 开发指南

### 项目结构

```
llm-gateway/
├── backend/
│   ├── app/
│   │   ├── api/           # API 路由（代理、管理）
│   │   ├── services/      # 业务逻辑
│   │   ├── providers/     # 协议适配器
│   │   ├── repositories/  # 数据访问层
│   │   ├── db/            # 数据库模型
│   │   ├── domain/        # DTO 和领域模型
│   │   ├── rules/         # 规则评估引擎
│   │   └── common/        # 工具类
│   ├── migrations/        # Alembic 数据库迁移
│   └── tests/             # 测试套件
├── frontend/
│   └── src/
│       ├── app/           # Next.js App Router 页面
│       ├── components/    # React 组件
│       └── lib/           # 工具类和 API 客户端
├── docker-compose.yml
└── Dockerfile
```

### 运行测试

```bash
cd backend
pytest
```

### 数据库迁移

```bash
cd backend

# 创建新的迁移
alembic revision --autogenerate -m "description"

# 应用迁移
alembic upgrade head
```

---

## 文档

- [架构设计](docs/architecture.md)
- [API 参考](docs/api.md)
- [模块详情](docs/modules.md)
- [需求文档](docs/req.md)

---

## 许可证

[MIT](LICENSE)

---

<p align="center">
  为 LLM 社区用心打造
</p>
