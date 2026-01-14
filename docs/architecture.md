# LLM Gateway Architecture Design Document

## 1. Macro Architecture Design

### 1.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                   │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │ OpenAI SDK   │    │ Anthropic SDK│    │  Direct HTTP │                │
│    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
└───────────┼───────────────────┼───────────────────┼────────────────────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM Gateway Proxy Layer                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        FastAPI Backend Service                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │  Proxy API  │  │  Admin API  │  │   Auth      │  │  Middleware │   │ │
│  │  │ (Proxy I/F) │  │ (Admin I/F) │  │  (Auth)     │  │             │   │ │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘   │ │
│  │         │                │                                             │ │
│  │         ▼                ▼                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                      Service Layer                                │ │ │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │ │ │
│  │  │  │  Proxy     │ │  Rule      │ │  Provider  │ │  Strategy  │    │ │ │
│  │  │  │  Service   │ │  Engine    │ │  Client    │ │(RoundRobin)│    │ │ │
│  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │ │ │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │ │ │
│  │  │  │  Retry     │ │  Token     │ │  Log       │ │  Provider  │    │ │ │
│  │  │  │  Handler   │ │  Counter   │ │  Service   │ │  Service   │    │ │ │
│  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  │                          │                                             │ │
│  │                          ▼                                             │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Repository Data Access Layer                   │ │ │
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
│  │  │         │     (Default)     │     (Optional)    │                │ │ │
│  │  │         └───────────────────┴───────────────────┘                │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Upstream Provider Layer                           │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│    │   OpenAI     │    │  Anthropic   │    │ Other Compat │                │
│    └──────────────┘    └──────────────┘    └──────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend Admin Dashboard                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     Next.js + TypeScript                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │ │
│  │  │ Provider    │  │ Model       │  │ API Key     │  │ Log         │   │ │
│  │  │ Mgmt        │  │ Mgmt        │  │ Mgmt        │  │ Query       │   │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Proxy Request Processing Flow                       │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌─────────┐
     │  Start  │
     └────┬────┘
          │
          ▼
    ┌───────────────┐
    │ 1. Receive    │ ◄── OpenAI/Anthropic format request
    │    Request    │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐     ┌─────────────┐
    │ 2. API Key    │────►│ Validation  │──► Return 401
    │    Auth       │     │ Failed      │
    └───────┬───────┘     └─────────────┘
            │ Success
            ▼
    ┌───────────────┐
    │ 3. Parse Body │ ◄── Extract requested_model, messages, etc.
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 4. Calculate  │ ◄── Token Counter
    │    Input Token│
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 5. Rule Engine│ ◄── Context: model, headers, body, token_usage
    │    Match      │ ──► Output: Candidate provider list + target_model
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 6. Strategy   │ ◄── Select current provider from candidates
    │    Select     │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 7. Replace    │ ◄── Only modify model field
    │    Model      │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 8. Forward    │
    │    Request    │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐     ┌─────────────────────────────────┐
    │ 9. Check      │────►│ status >= 500:                  │
    │    Status     │     │   - Retry same provider (max 3) │
    └───────┬───────┘     │ status < 500:                   │
            │             │   - Switch to next provider     │
            │             └─────────────┬───────────────────┘
            │                           │
            │ ◄─────────────────────────┘
            ▼
    ┌───────────────┐     ┌─────────────┐
    │ 10. All       │────►│ Return Last │
    │     Failed?   │ Yes │ Error Resp  │
    └───────┬───────┘     └─────────────┘
            │ No
            ▼
    ┌───────────────┐
    │ 11. Calculate │
    │     Output Tok│
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 12. Log       │ ◄── Sanitize authorization then save
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ 13. Return    │
    │     Response  │
    └───────┬───────┘
            │
            ▼
       ┌─────────┐
       │   End   │
       └─────────┘
```

### 1.3 Technology Stack

| Layer | Stack | Description |
|------|--------|------|
| Backend Framework | Python + FastAPI | High-performance asynchronous framework |
| Database | SQLite (Default) / PostgreSQL | Switchable via configuration |
| ORM | SQLAlchemy | Supports multiple databases |
| DB Migration | Alembic | Versioned migration management |
| HTTP Client | httpx | Asynchronous HTTP client |
| Frontend Framework | Next.js + TypeScript | Modern React framework |
| UI Components | shadcn/ui + Tailwind CSS | Modern component library |
| State Management | React Query | Server state management |

## 2. Code Structure Design

### 2.1 Backend Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   │
│   ├── api/                       # API Route Layer
│   │   ├── __init__.py
│   │   ├── deps.py                # Dependency injection
│   │   ├── proxy/                 # Proxy interfaces
│   │   │   ├── __init__.py
│   │   │   ├── openai.py          # OpenAI compatible interface
│   │   │   └── anthropic.py       # Anthropic compatible interface
│   │   └── admin/                 # Admin interfaces
│   │       ├── __init__.py
│   │       ├── providers.py       # Provider management
│   │       ├── models.py          # Model management
│   │       ├── api_keys.py        # API Key management
│   │       └── logs.py            # Log query
│   │
│   ├── services/                  # Business Service Layer
│   │   ├── __init__.py
│   │   ├── proxy_service.py       # Core proxy service
│   │   ├── provider_service.py    # Provider management service
│   │   ├── model_service.py       # Model management service
│   │   ├── api_key_service.py     # API Key service
│   │   ├── log_service.py         # Log service
│   │   ├── retry_handler.py       # Retry handler
│   │   └── strategy.py            # Strategy service (Round Robin)
│   │
│   ├── rules/                     # Rule Engine
│   │   ├── __init__.py
│   │   ├── engine.py              # Rule engine core
│   │   ├── context.py             # Rule context
│   │   ├── evaluator.py           # Rule evaluator
│   │   └── models.py              # Rule model definitions
│   │
│   ├── providers/                 # Upstream Provider Adapters
│   │   ├── __init__.py
│   │   ├── base.py                # Base adapter interface
│   │   ├── openai_client.py       # OpenAI client
│   │   └── anthropic_client.py    # Anthropic client
│   │
│   ├── repositories/              # Data Access Layer
│   │   ├── __init__.py
│   │   ├── base.py                # Base Repository interface
│   │   ├── provider_repo.py       # Provider Repository interface
│   │   ├── model_repo.py          # Model Repository interface
│   │   ├── api_key_repo.py        # API Key Repository interface
│   │   ├── log_repo.py            # Log Repository interface
│   │   └── sqlalchemy/            # SQLAlchemy implementation
│   │       ├── __init__.py
│   │       ├── provider_repo.py
│   │       ├── model_repo.py
│   │       ├── api_key_repo.py
│   │       └── log_repo.py
│   │
│   ├── db/                        # Database Layer
│   │   ├── __init__.py
│   │   ├── session.py             # Database session management
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── migrations/            # Alembic migrations
│   │       ├── env.py
│   │       ├── versions/
│   │       └── alembic.ini
│   │
│   ├── domain/                    # Domain Models
│   │   ├── __init__.py
│   │   ├── provider.py            # Provider DTO
│   │   ├── model.py               # Model DTO
│   │   ├── api_key.py             # API Key DTO
│   │   ├── log.py                 # Log DTO
│   │   └── request.py             # Request/Response DTO
│   │
│   └── common/                    # Common Modules
│       ├── __init__.py
│       ├── http_client.py         # HTTP client wrapper
│       ├── token_counter.py       # Token counter
│       ├── sanitizer.py           # Data sanitizer
│       ├── errors.py              # Error definitions
│       ├── timer.py               # Timer
│       └── utils.py               # Utility functions
│
├── tests/                         # Tests
│   ├── __init__.py
│   ├── conftest.py                # Test configuration
│   ├── unit/                      # Unit tests
│   │   ├── test_rules/
│   │   ├── test_services/
│   │   ├── test_providers/
│   │   ├── test_repositories/
│   │   └── test_common/
│   └── integration/               # Integration tests
│       └── test_proxy_flow.py
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── README.md
```

### 2.2 Frontend Directory Structure

```
frontend/
├── src/
│   ├── app/                       # Next.js App Router
│   │   ├── layout.tsx             # Root layout
│   │   ├── page.tsx               # Homepage
│   │   ├── providers/             # Provider management page
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── models/                # Model management page
│   │   │   ├── page.tsx
│   │   │   └── [model]/
│   │   │       └── page.tsx
│   │   ├── api-keys/              # API Key management page
│   │   │   └── page.tsx
│   │   └── logs/                  # Log query page
│   │       ├── page.tsx
│   │       └── [id]/
│   │           └── page.tsx
│   │
│   ├── components/                # Components
│   │   ├── ui/                    # Base UI components (shadcn)
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── table.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── form.tsx
│   │   │   └── ...
│   │   ├── common/                # Common business components
│   │   │   ├── DataTable.tsx      # Generic data table
│   │   │   ├── Pagination.tsx     # Pagination component
│   │   │   ├── FilterBar.tsx      # Filter bar
│   │   │   ├── JsonEditor.tsx     # JSON editor
│   │   │   ├── JsonViewer.tsx     # JSON viewer
│   │   │   ├── ConfirmDialog.tsx  # Confirmation dialog
│   │   │   └── LoadingState.tsx   # Loading state
│   │   ├── providers/             # Provider related components
│   │   │   ├── ProviderForm.tsx
│   │   │   └── ProviderList.tsx
│   │   ├── models/                # Model related components
│   │   │   ├── ModelForm.tsx
│   │   │   ├── ModelProviderForm.tsx
│   │   │   └── RuleEditor.tsx     # Rule editor
│   │   ├── api-keys/              # API Key related components
│   │   │   ├── ApiKeyForm.tsx
│   │   │   └── ApiKeyList.tsx
│   │   └── logs/                  # Log related components
│   │       ├── LogFilters.tsx
│   │       ├── LogList.tsx
│   │       └── LogDetail.tsx
│   │
│   ├── lib/                       # Utility libraries
│   │   ├── api/                   # API clients
│   │   │   ├── client.ts          # HTTP client
│   │   │   ├── providers.ts       # Provider API
│   │   │   ├── models.ts          # Model API
│   │   │   ├── api-keys.ts        # API Key API
│   │   │   └── logs.ts            # Log API
│   │   ├── hooks/                 # Custom Hooks
│   │   │   ├── useProviders.ts
│   │   │   ├── useModels.ts
│   │   │   ├── useApiKeys.ts
│   │   │   └── useLogs.ts
│   │   └── utils/                 # Utility functions
│   │       ├── format.ts
│   │       └── validation.ts
│   │
│   └── types/                     # TypeScript definitions
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

## 3. Database Model Design

### 3.1 ER Diagram

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

### 3.2 Table Structure Detailed Definition

```sql
-- Service Providers Table
CREATE TABLE service_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    base_url VARCHAR(500) NOT NULL,
    protocol VARCHAR(50) NOT NULL,  -- 'openai' | 'anthropic'
    api_type VARCHAR(50) NOT NULL,
    api_key TEXT,                    -- Provider API Key (Encrypted storage recommended)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model Mappings Table
CREATE TABLE model_mappings (
    requested_model VARCHAR(100) PRIMARY KEY,
    strategy VARCHAR(50) DEFAULT 'round_robin',
    matching_rules JSON,             -- Model level rules
    capabilities JSON,               -- Capabilities description
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model-Provider Mappings Table
CREATE TABLE model_mapping_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_model VARCHAR(100) NOT NULL,
    provider_id INTEGER NOT NULL,
    target_model_name VARCHAR(100) NOT NULL,
    provider_rules JSON,             -- Provider level rules
    priority INTEGER DEFAULT 0,
    weight INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (requested_model) REFERENCES model_mappings(requested_model),
    FOREIGN KEY (provider_id) REFERENCES service_providers(id),
    UNIQUE (requested_model, provider_id)
);

-- API Keys Table
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name VARCHAR(100) NOT NULL UNIQUE,
    key_value VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);

-- Request Logs Table
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
    request_headers JSON,            -- Sanitized
    request_body JSON,
    response_status INTEGER,
    response_body TEXT,
    error_info TEXT,
    trace_id VARCHAR(100),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id),
    FOREIGN KEY (provider_id) REFERENCES service_providers(id)
);

-- Indices
CREATE INDEX idx_request_logs_time ON request_logs(request_time);
CREATE INDEX idx_request_logs_api_key ON request_logs(api_key_id);
CREATE INDEX idx_request_logs_model ON request_logs(requested_model);
CREATE INDEX idx_request_logs_provider ON request_logs(provider_id);
CREATE INDEX idx_request_logs_status ON request_logs(response_status);
```