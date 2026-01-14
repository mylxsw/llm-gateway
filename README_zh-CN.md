# LLM Gateway

[ [**English**](README.md) | [**中文**](README_zh-CN.md) ]

**LLM Gateway** 是一个高性能的企业级代理服务，旨在统一管理和路由对大语言模型（LLM）供应商（如 OpenAI 和 Anthropic）的访问。它提供了智能路由、强大的故障转移策略、全面的日志记录以及现代化的管理仪表板。

## ✨ 核心特性

- **统一接口**：兼容 OpenAI 和 Anthropic API 协议。客户端无需修改代码即可使用标准 SDK 接入。
- **智能路由**：基于模型名称、规则和策略将请求路由到不同的供应商。
- **透明代理**：以最小的干扰转发请求——仅根据路由规则动态替换模型名称，其余内容保持不变。
- **高可用性**：
  - **自动重试**：针对上游服务错误（HTTP 500+）的可配置重试机制。
  - **故障转移**：如果主供应商不可用，自动切换到备用供应商/节点。
- **可观测性**：
  - **详细日志**：记录每个请求的指标，包括延迟、状态码和重试次数。
  - **Token 统计**：使用标准计数方法追踪输入/输出 Token 使用量。
  - **安全**：自动对日志中的敏感信息（如 `Authorization` 头）进行脱敏处理。
- **现代化管理面板**：
  - 基于 **Next.js** 和 **shadcn/ui** 构建。
  - 管理供应商（Providers）、模型（Models）和 API 密钥（API Keys）。
  - 支持高级筛选的请求日志查看器。

## 🏗 架构

系统由 Python (FastAPI) 后端和 Next.js 前端组成。

- **后端**：处理请求代理、规则评估和数据库交互。支持 **SQLite**（默认）和 **PostgreSQL**。
- **前端**：用于配置和监控的 Web 界面。

深入了解请查看 [架构文档](docs/architecture.md)。

## 🚀 快速开始

### 前置要求

- **Python**: 3.12+
- **Node.js**: 18+ (用于前端)
- **包管理器**: `uv` 或 `pip` (Python), `pnpm` (Node.js)

### 1. 后端设置

1.  进入后端目录：
    ```bash
    cd backend
    ```

2.  安装依赖：
    ```bash
    # 推荐：使用 uv
    uv sync

    # 或者使用标准 pip
    pip install -r requirements.txt
    ```

3.  配置环境：
    复制示例配置（如果使用默认的 SQLite 配置可跳过此步）：
    ```bash
    # 如果需要自定义设置（如连接 PostgreSQL），请创建 .env 文件
    touch .env
    ```

4.  初始化数据库：
    ```bash
    alembic upgrade head
    ```

5.  启动服务：
    ```bash
    uvicorn app.main:app --reload
    ```
    API 服务将在 `http://localhost:8000` 启动。

### 2. 前端设置

1.  进入前端目录：
    ```bash
    cd frontend
    ```

2.  安装依赖：
    ```bash
    pnpm install
    ```

3.  启动开发服务器：
    ```bash
    pnpm dev
    ```
    管理面板将在 `http://localhost:3000` 启动。

## 🐳 Docker

构建一个同时包含后端与前端的单镜像：

```bash
docker build -t llm-gateway .
docker run --rm -p 8000:8000 -v $(pwd)/data:/data llm-gateway
```

- 管理面板：`http://localhost:8000`
- API：`http://localhost:8000/v1/...` 与 `http://localhost:8000/api/admin/...`
- 如使用 SQLite，建议挂载 `/data` 持久化数据库（或通过 `DATABASE_URL` 使用外部数据库）。

### Docker Compose（一键启动）

```bash
cp .env.example .env
./start.sh
```

- 停止：`./stop.sh`（或 `./start.sh down`）
- 默认数据库：PostgreSQL（服务名 `postgres`）
- 使用 SQLite：在 `.env` 中设置 `DATABASE_TYPE/DATABASE_URL`（见 `.env.example`）

## ⚙️ 配置说明

配置通过环境变量或 `backend/` 目录下的 `.env` 文件进行管理。

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `APP_NAME` | LLM Gateway | 应用名称。 |
| `DEBUG` | False | 是否开启调试模式。 |
| `DATABASE_TYPE` | sqlite | 数据库类型：`sqlite` 或 `postgresql`。 |
| `DATABASE_URL` | sqlite+aiosqlite:///./llm_gateway.db | 数据库连接字符串。 |
| `RETRY_MAX_ATTEMPTS` | 3 | 同一供应商遇到 500+ 错误时的最大重试次数。 |
| `RETRY_DELAY_MS` | 1000 | 重试间隔时间（毫秒）。 |
| `HTTP_TIMEOUT` | 60 | 上游请求超时时间（秒）。 |

## 📚 文档

- [架构设计](docs/architecture.md)
- [需求文档](req.md)
- [后端说明](backend/README.md)

## 📄 许可证

[MIT](LICENSE)
