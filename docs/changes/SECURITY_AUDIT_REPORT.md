# LLM Gateway 安全审查报告与修复计划

> 审查日期: 2026-02-28
> 审查范围: 后端 API、数据存储、前端、容器部署、第三方集成

## 概述

对 LLM Gateway 项目进行了全面的安全审查，涵盖后端 API、数据存储、前端、容器部署和第三方集成五个方面。发现了 **6 个严重漏洞**、**7 个高危问题**、**8 个中危问题**。

---

## 🔴 CRITICAL (严重) - 必须立即修复

### 1. 第三方 API 密钥明文存储
- **位置**: `backend/app/db/models.py:57`
- **问题**: `ServiceProvider.api_key` 以明文存储在数据库
- **风险**: 数据库泄露将导致所有 OpenAI/Anthropic 等 API Key 泄露，攻击者可调用付费 API
- **修复**: 使用 AES-256-GCM 加密存储

### 2. 管理员密码明文存储
- **位置**: `backend/app/config.py:50`, `backend/app/common/admin_auth.py`
- **问题**: 密码以明文形式存储在环境变量中，使用 SHA256 作为签名密钥
- **风险**: 环境变量泄露导致管理员账户被接管
- **修复**: 使用 bcrypt 或 PBKDF2 进行密码哈希

### 3. Redis 缺少密码认证
- **位置**: `backend/app/db/redis.py:44-47`
- **问题**: Redis 连接没有密码保护
- **风险**: 任何人可连接 Redis 读取/修改会话数据
- **修复**: 配置 Redis 密码认证

### 4. 默认硬编码密码
- **位置**: `docker-compose.yml:7`
- **问题**: 使用默认密码 `llm_gateway_password`
- **风险**: 使用默认配置部署时数据库凭证泄露
- **修复**: 强制要求设置环境变量，移除默认密码

### 5. 数据库端口暴露
- **位置**: `docker-compose.yml:9`
- **问题**: PostgreSQL 5432 端口直接暴露到主机
- **风险**: 数据库直接暴露给网络攻击
- **修复**: 移除端口映射，使用内部网络

### 6. CORS 配置过于宽松
- **位置**: `backend/app/main.py:70-76`
- **问题**: `allow_origins=["*"]` 允许任何来源的跨域请求
- **风险**: 可能导致 CSRF 攻击，敏感数据泄露
- **修复**: 限制为特定的可信域名列表

---

## 🟠 HIGH (高危) - 优先修复

### 7. 缺少速率限制
- **位置**: 整个 API 服务
- **问题**: 未对 API 端点实施速率限制
- **风险**: 暴力破解、DDoS 攻击
- **修复**: 实现基于 IP 和 API Key 的速率限制 (slowapi)

### 8. 客户端 API Key 明文存储
- **位置**: `backend/app/db/models.py:216`
- **问题**: `ApiKey.key_value` 明文存储
- **风险**: 数据库泄露时所有客户端 API Key 被获取
- **修复**: 实施哈希存储（可逆性要求较低）

### 9. Token 存储在 localStorage
- **位置**: `frontend/src/lib/api/client.ts:25,34`
- **问题**: 认证 Token 存储在 localStorage
- **风险**: XSS 攻击可窃取 Token
- **修复**: 使用 httpOnly Cookie 或 sessionStorage

### 10. CSRF 防护缺失
- **位置**: 所有 API 调用
- **问题**: 没有 CSRF Token 机制
- **风险**: 攻击者可诱导用户执行恶意操作
- **修复**: 实现 CSRF Token 机制

### 11. HTTPS 证书验证未强制
- **位置**: `backend/app/providers/*.py`
- **问题**: httpx.AsyncClient 未强制验证 HTTPS 证书
- **风险**: 中间人攻击
- **修复**: 添加 `verify=True` 参数

### 12. 代理 URL 未验证
- **位置**: `backend/app/providers/openai_client.py:115`
- **问题**: 代理 URL 直接使用，无验证
- **风险**: 恶意代理劫持流量
- **修复**: 实现代理 URL 白名单验证

### 13. 管理端点暴露过多信息
- **位置**: `backend/app/api/admin/api_keys.py:91-106`
- **问题**: `/raw` 端点返回完整 API Key
- **风险**: API Key 泄露
- **修复**: 移除或需要二次验证

---

## 🟡 MEDIUM (中危) - 计划修复

### 14. Cookie 安全配置不完善
- **位置**: `frontend/src/components/common/IntlProvider.tsx:77`
- **问题**: Cookie 缺少 `secure; httponly` 标志
- **修复**: 添加安全标志

### 15. 基础镜像未锁定版本
- **位置**: `Dockerfile:3,14`, `docker-compose.yml:3,20`
- **问题**: 使用 `node:current-bookworm-slim` 等未锁定版本
- **修复**: 使用具体版本号

### 16. 缺少安全扫描
- **位置**: `.github/workflows/build.yml`
- **问题**: CI/CD 缺少 Docker 镜像安全扫描
- **修复**: 集成 Trivy 安全扫描

### 17. dangerouslySetInnerHTML 使用
- **位置**: `frontend/src/app/layout.tsx:48-59`
- **问题**: 主题初始化使用危险的 innerHTML
- **修复**: 改用安全的 Script 组件

### 18. URL 构建 SSRF 风险
- **位置**: `backend/app/providers/openai_client.py:74`
- **问题**: base_url 和 path 直接拼接，未限制内网访问
- **修复**: 实现 URL 白名单

### 19. 响应内容未验证
- **位置**: `backend/app/providers/*.py`
- **问题**: 直接返回第三方响应
- **修复**: 添加响应内容过滤

### 20. 输入验证不足
- **位置**: 多个表单组件
- **问题**: 主要依赖浏览器原生验证
- **修复**: 实施服务端输入验证

### 21. 错误信息泄露
- **位置**: `backend/app/common/errors.py`
- **问题**: 500 错误可能返回堆栈跟踪
- **修复**: 统一错误响应格式

---

## 🟢 LOW (低危) - 长期改进

### 22. 缺少健康检查配置
- **问题**: llm-gateway 服务缺少健康检查

### 23. 日志配置不完善
- **问题**: 可能产生大量日志数据

### 24. localStorage 异常处理不足
- **问题**: 隐私模式下可能导致应用崩溃

### 25. 缺少数据访问审计
- **问题**: 没有记录敏感数据访问

---

## ✅ 已有的良好安全实践

1. **SQL 注入防护** - 全部使用 SQLAlchemy ORM
2. **JWT 实现** - HMAC-SHA256 签名，包含过期时间
3. **敏感信息脱敏** - sanitizer.py 实现完善
4. **API Key 生成** - 使用 secrets.token_hex()
5. **输入验证** - 使用 Pydantic 进行数据验证
6. **配置管理** - Pydantic Settings + 环境变量

---

## 修复优先级与计划

### 第一阶段：紧急修复 (1-2天)
| # | 问题 | 文件 | 工作量 |
|---|------|------|--------|
| 1 | CORS 配置 | main.py | 0.5h |
| 2 | Redis 密码 | redis.py, docker-compose.yml | 0.5h |
| 3 | 移除默认密码 | docker-compose.yml | 0.5h |
| 4 | 移除端口暴露 | docker-compose.yml | 0.5h |
| 5 | 强制 HTTPS 验证 | providers/*.py | 1h |

### 第二阶段：高优先级 (3-5天)
| # | 问题 | 文件 | 工作量 |
|---|------|------|--------|
| 6 | API Key 加密存储 | models.py, 新增加密服务 | 4h |
| 7 | 密码哈希改进 | admin_auth.py, config.py | 2h |
| 8 | 速率限制 | main.py, 添加 slowapi | 2h |
| 9 | Token 存储改进 | frontend API client | 2h |
| 10 | CSRF 防护 | 全局 | 3h |

### 第三阶段：中优先级 (1周)
| # | 问题 | 文件 | 工作量 |
|---|------|------|--------|
| 11 | 锁定镜像版本 | Dockerfile, docker-compose | 1h |
| 12 | 安全扫描 | GitHub Actions | 2h |
| 13 | URL 白名单 | providers | 2h |
| 14 | 错误处理改进 | errors.py | 1h |
| 15 | Cookie 安全 | IntlProvider.tsx | 0.5h |

---

## 验证方法

1. **自动化测试**
   - 添加安全相关单元测试
   - 集成 OWASP ZAP 扫描

2. **手动验证**
   - 渗透测试关键端点
   - 验证加密/哈希实现
   - 测试速率限制效果

3. **代码审查**
   - PR 必须通过安全审查
   - 使用 code-security-reviewer agent

---

## 关键文件清单

### 需要修改的文件
- `backend/app/main.py` - CORS 配置
- `backend/app/db/models.py` - API Key 加密
- `backend/app/db/redis.py` - Redis 密码
- `backend/app/common/admin_auth.py` - 密码哈希
- `backend/app/providers/*.py` - HTTPS 验证
- `frontend/src/lib/api/client.ts` - Token 存储
- `docker-compose.yml` - 安全配置
- `Dockerfile` - 镜像版本

### 需要新增的文件
- `backend/app/common/encryption.py` - 加密服务
- `backend/app/middleware/rate_limit.py` - 速率限制
- `backend/app/middleware/csrf.py` - CSRF 防护
- `.github/workflows/security-scan.yml` - 安全扫描

---

## 总结

该项目在代码安全基础方面做得不错（SQL 注入防护、认证实现），但在**敏感数据存储**和**访问控制**方面存在严重问题。建议按优先级分三个阶段修复，预计总工作量约 2-3 周。
