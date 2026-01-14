# LLM Gateway Module Decomposition Design

## Module Overview

The project is split into the following independent modules, each of which can be developed in parallel by different developers.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Module Dependency Graph                          │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌───────────────────┐
                    │   M1: Infrastructure│
                    │  (DB/Config/Common)│
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ M2: Data Access  │  │ M3: Rule Engine │  │ M4: Upstream    │
│  Layer          │  │ (Rule Engine)   │  │ Adapters        │
│  (Repository)   │  │                 │  │ (Providers)     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   M5: Business      │
                    │    Service Layer    │
                    │    (Services)       │
                    └─────────┬───────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
    ┌─────────────────┐             ┌─────────────────┐
    │ M6: Proxy API   │             │ M7: Admin API   │
    │ (Proxy Routes)  │             │ (Admin Routes)  │
    └─────────────────┘             └─────────────────┘

                              │
                              ▼
    ┌─────────────────────────────────────────────────────┐
    │                  M8: Frontend Admin Dashboard         │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
    │  │ Provider │ │  Model   │ │ API Key  │ │ Log      ││
    │  │ Mgmt     │ │  Mgmt    │ │ Mgmt     │ │ Query    ││
    │  └──────────┘ └──────────┘ └──────────┘ └──────────┘│
    └─────────────────────────────────────────────────────┘
```

---

## M1: Infrastructure Module

### Module Responsibilities
- Database connection and session management
- Configuration management (Environment variables, multi-database switching)
- Common utility functions (Sanitization, Token counting, Timer, Error handling, etc.)

### File Structure
```
backend/app/
├── config.py                 # Configuration management
├── db/
│   ├── __init__.py
│   ├── session.py            # Database session management
│   └── models.py             # ORM Model definitions
└── common/
    ├── __init__.py
    ├── http_client.py        # HTTP Client wrapper
    ├── token_counter.py      # Token Counter
    ├── sanitizer.py          # Data Sanitizer
    ├── errors.py             # Error Definitions
    ├── timer.py              # Timer
    └── utils.py              # Utility functions
```

### Interface Definition

#### config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database Config
    DATABASE_TYPE: str = "sqlite"  # sqlite | postgresql
    DATABASE_URL: str = "sqlite:///./llm_gateway.db"
    
    # App Config
    APP_NAME: str = "LLM Gateway"
    DEBUG: bool = False
    
    # Retry Config
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_DELAY_MS: int = 1000

    class Config:
        env_file = ".env"
```

#### common/sanitizer.py
```python
def sanitize_authorization(value: str) -> str:
    """Sanitize authorization field"""
    # Bearer sk-xxx...xxx -> Bearer sk-***...***
    pass

def sanitize_headers(headers: dict) -> dict:
    """Sanitize request headers"""
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
        # Use tiktoken for calculation
        pass

class AnthropicTokenCounter(TokenCounter):
    def count_tokens(self, text: str, model: str) -> int:
        pass
```

### Test Points
- [ ] Configuration loading correctness (Environment variable priority)
- [ ] Database connection (SQLite/PostgreSQL switching)
- [ ] Sanitization functions (authorization field masking)
- [ ] Token counting accuracy

### Estimated Effort
**2-3 Days**

---

## M2: Data Access Layer Module

### Module Responsibilities
- Define Repository abstract interfaces
- Implement SQLAlchemy concrete implementation
- Support SQLite and PostgreSQL

### File Structure
```
backend/app/
├── domain/                        # Domain Models/DTO
│   ├── __init__.py
│   ├── provider.py
│   ├── model.py
│   ├── api_key.py
│   └── log.py
└── repositories/
    ├── __init__.py
    ├── base.py                    # Base Repository Interface
    ├── provider_repo.py           # Provider Repository Interface
    ├── model_repo.py              # Model Repository Interface
    ├── api_key_repo.py            # API Key Repository Interface
    ├── log_repo.py                # Log Repository Interface
    └── sqlalchemy/                # SQLAlchemy Implementation
        ├── __init__.py
        ├── provider_repo.py
        ├── model_repo.py
        ├── api_key_repo.py
        └── log_repo.py
```

### Interface Definition

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

### Test Points
- [ ] CRUD operations correctness
- [ ] Pagination query
- [ ] Multi-condition filtering
- [ ] Foreign key constraints
- [ ] SQLite and PostgreSQL compatibility

### Estimated Effort
**3-4 Days**

---

## M3: Rule Engine Module

### Module Responsibilities
- Define rule context structure
- Implement rule evaluation logic
- Output candidate providers and their target models

### File Structure
```
backend/app/rules/
├── __init__.py
├── engine.py              # Rule Engine Core
├── context.py             # Rule Context
├── evaluator.py           # Rule Evaluator
└── models.py              # Rule Model Definition
```

### Interface Definition

#### rules/context.py
```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class RuleContext:
    """Rule Engine Context"""
    current_model: str              # requested_model
    headers: Dict[str, str]         # Request headers
    request_body: Dict[str, Any]    # Request body
    token_usage: TokenUsage         # Token consumption

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
    """Rule Definition"""
    field: str              # Matching field (model, headers.x-custom, body.temperature)
    operator: str           # Operator (eq, ne, gt, lt, gte, lte, contains, regex)
    value: Any              # Matching value
    
@dataclass
class RuleSet:
    """Rule Set (AND Logic)"""
    rules: List[Rule]
    
@dataclass
class CandidateProvider:
    """Candidate Provider"""
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
    """Rule Engine"""
    
    async def evaluate(
        self,
        context: RuleContext,
        model_mapping: ModelMapping,
        provider_mappings: List[ModelMappingProvider]
    ) -> List[CandidateProvider]:
        """
        Evaluate all rules, return list of candidate providers
        
        Process:
        1. Check model-level rules (model_mapping.matching_rules)
        2. Check provider-level rules for each provider (provider_mapping.provider_rules)
        3. Return all passed providers and their target_model
        """
        pass
```

### Rule Format Example
```json
{
  "rules": [
    {"field": "headers.x-priority", "operator": "eq", "value": "high"},
    {"field": "body.temperature", "operator": "lte", "value": 0.5}
  ],
  "logic": "AND"
}
```

### Test Points
- [ ] Various operators (eq, ne, gt, lt, contains, regex)
- [ ] Nested field access (headers.x-custom, body.messages[0].role)
- [ ] Multi-rule AND/OR combinations
- [ ] Empty rule handling (Default pass)
- [ ] No matching provider handling

### Estimated Effort
**2-3 Days**

---

## M4: Upstream Provider Adapter Module

### Module Responsibilities
- Encapsulate upstream API calls
- Support OpenAI and Anthropic protocols
- Handle streaming responses

### File Structure
```
backend/app/providers/
├── __init__.py
├── base.py                # Base Adapter Interface
├── openai_client.py       # OpenAI Client
└── anthropic_client.py    # Anthropic Client
```

### Interface Definition

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
    """Base class for upstream provider client"""
    
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
        """Forward request to upstream provider"""
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
        """Forward streaming request"""
        pass
```

#### providers/openai_client.py
```python
class OpenAIClient(ProviderClient):
    """OpenAI Protocol Client"""
    
    async def forward(self, ...) -> ProviderResponse:
        # 1. Copy body, replace model field
        # 2. Forward to base_url + path
        # 3. Record latency metrics
        pass
```

### Test Points
- [ ] Request forwarding correctness
- [ ] Only modify model field verification
- [ ] Streaming response handling
- [ ] Error response handling
- [ ] Timeout handling

### Estimated Effort
**2-3 Days**

---

## M5: Business Service Layer Module

### Module Responsibilities
- Proxy core logic orchestration
- Retry and failover
- Round Robin strategy implementation
- Log recording service

### File Structure
```
backend/app/services/
├── __init__.py
├── proxy_service.py       # Proxy Core Service
├── provider_service.py    # Provider Management Service
├── model_service.py       # Model Management Service
├── api_key_service.py     # API Key Service
├── log_service.py         # Log Service
├── retry_handler.py       # Retry Handler
└── strategy.py            # Strategy Service (Round Robin)
```

### Interface Definition

#### services/proxy_service.py
```python
class ProxyService:
    """Proxy Core Service"""
    
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
        Process proxy request
        
        Process:
        1. Extract requested_model
        2. Calculate Input Token
        3. Build Rule Context
        4. Rule Engine Match -> Candidate Provider List
        5. Round Robin Strategy selects Provider
        6. Forward Request (with Retry/Failover logic)
        7. Calculate Output Token
        8. Log Request
        9. Return Response
        """
        pass
```

#### services/retry_handler.py
```python
class RetryHandler:
    """Retry and Failover Handler"""
    
    async def execute_with_retry(
        self,
        candidates: List[CandidateProvider],
        forward_fn: Callable,
        **kwargs
    ) -> tuple[ProviderResponse, int, CandidateProvider]:
        """
        Execute request with retry
        
        Logic:
        - status >= 500: Retry on same provider 3 times, 1s interval
        - status < 500: Switch directly to next provider
        - All failed: Return last error
        
        Returns:
            (Response, Retry Count, Final Provider Used)
        """
        pass
```

#### services/strategy.py
```python
from abc import ABC, abstractmethod

class SelectionStrategy(ABC):
    """Provider Selection Strategy"""
    
    @abstractmethod
    async def select(
        self,
        candidates: List[CandidateProvider],
        requested_model: str
    ) -> CandidateProvider:
        pass

class RoundRobinStrategy(SelectionStrategy):
    """Round Robin Strategy"""
    
    async def select(self, candidates, requested_model) -> CandidateProvider:
        # Use atomic counter to implement concurrency-safe round robin
        pass
```

### Test Points
- [ ] Complete proxy flow
- [ ] Retry logic (>=500 Retry on same provider 3 times)
- [ ] Switch logic (<500 Switch directly)
- [ ] Round Robin strategy correctness and concurrency safety
- [ ] Log recording completeness

### Estimated Effort
**4-5 Days**

---

## M6: Proxy API Module

### Module Responsibilities
- OpenAI Compatible Interface
- Anthropic Compatible Interface
- API Key Authentication

### File Structure
```
backend/app/api/
├── __init__.py
├── deps.py                # Dependency Injection
└── proxy/
    ├── __init__.py
    ├── openai.py          # OpenAI Compatible Interface
    └── anthropic.py       # Anthropic Compatible Interface
```

### Interface Definition

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
    """OpenAI Chat Completions Proxy Interface"""
    pass

@router.post("/v1/completions")
async def completions(request: Request, ...):
    """OpenAI Completions Proxy Interface"""
    pass

@router.post("/v1/embeddings")
async def embeddings(request: Request, ...):
    """OpenAI Embeddings Proxy Interface"""
    pass
```

#### api/proxy/anthropic.py
```python
router = APIRouter()

@router.post("/v1/messages")
async def messages(request: Request, ...):
    """Anthropic Messages Proxy Interface"""
    pass
```

### Test Points
- [ ] API Key Authentication
- [ ] Request Parsing
- [ ] Response Format Correctness
- [ ] Streaming Response
- [ ] Error Handling

### Estimated Effort
**2-3 Days**

---

## M7: Admin API Module

### Module Responsibilities
- Provider CRUD API
- Model Mapping CRUD API
- API Key CRUD API
- Log Query API

### File Structure
```
backend/app/api/admin/
├── __init__.py
├── providers.py           # Provider Management
├── models.py              # Model Management
├── api_keys.py            # API Key Management
└── logs.py                # Log Query
```

### API Details see API Documentation below

### Test Points
- [ ] CRUD Operations
- [ ] Parameter Validation
- [ ] Pagination and Filtering
- [ ] Error Handling

### Estimated Effort
**2-3 Days**

---

## M8: Frontend Admin Dashboard Module

### Sub-module Breakdown

#### M8.1: Basic Framework and Common Components
- Project Initialization (Next.js + TypeScript)
- UI Component Library Integration (shadcn/ui)
- Common Component Development
- API Client Wrapper

**Estimated Effort: 2-3 Days**

#### M8.2: Provider Management Page
- Provider List
- Add/Edit Form
- Delete Confirmation

**Estimated Effort: 1-2 Days**

#### M8.3: Model Management Page
- Model Mapping List
- Model-Provider Mapping Configuration
- Rule Editor

**Estimated Effort: 3-4 Days**

#### M8.4: API Key Management Page
- API Key List
- Add (key_value generated by backend)
- State Management

**Estimated Effort: 1-2 Days**

#### M8.5: Log Query Page
- Log List (Pagination, Sorting)
- Multi-condition Filter
- Log Detail Page

**Estimated Effort: 2-3 Days**

---

## Development Sequence Suggestion

```
Phase 1 (Parallel):
├── M1: Infrastructure (Developer A)
├── M3: Rule Engine (Developer B)
└── M8.1: Frontend Basic Framework (Developer C)

Phase 2 (Parallel, Depends on M1):
├── M2: Data Access Layer (Developer A)
├── M4: Upstream Adapter (Developer B)
└── M8.2: Provider Management Page (Developer C)

Phase 3 (Parallel, Depends on M2, M3, M4):
├── M5: Business Service Layer (Developer A)
├── M7: Admin API (Developer B)
└── M8.3: Model Management Page (Developer C)

Phase 4 (Parallel, Depends on M5):
├── M6: Proxy API (Developer A)
├── M8.4: API Key Management Page (Developer B)
└── M8.5: Log Query Page (Developer C)

Phase 5:
└── Integration Test and Fixes
```

---

## Total Estimated Effort

| Module | Estimated Effort |
|--------|------------------|
| M1: Infrastructure | 2-3 Days |
| M2: Data Access Layer | 3-4 Days |
| M3: Rule Engine | 2-3 Days |
| M4: Upstream Adapter | 2-3 Days |
| M5: Business Service Layer | 4-5 Days |
| M6: Proxy API | 2-3 Days |
| M7: Admin API | 2-3 Days |
| M8: Frontend Admin Dashboard | 9-14 Days |
| Integration Test and Fixes | 3-5 Days |
| **Total** | **29-43 Days** (Single person) |

**Parallel Development (3 people)**: Approx **12-18 Days**