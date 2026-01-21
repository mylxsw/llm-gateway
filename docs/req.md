# Final Requirements Document: Model Routing & Proxy Service (OpenAI/Anthropic Compatible) + Admin Dashboard

## 1. Background
Develop a proxy service to handle client requests from OpenAI or Anthropic. The system matches the request based on the user's requested model, provided specifications, and internal rules. Without **modifying other fields in the request body**, the system replaces only the **model name** in the request body with the target model, forwards the request to the configured upstream Provider/Vendor, and returns the result to the client. The system must support automatic retries and failover, log key request information and performance metrics to a database, and provide an admin dashboard for configuration and query.

## 2. Goals
1.  **Transparent Proxy**: Compatible with OpenAI/Anthropic client invocation methods, returning compatible format responses.
2.  **Model Name Modification Only**: Only allowed to modify the `model` field during request forwarding; other content of the request body must remain unchanged.
3.  **Rule Engine Matching**: Process all rules through a rule engine to output a set of available providers and their target models.
4.  **Round Robin Selection**: Use a Round Robin strategy to select the current node from the matched provider nodes.
5.  **Reliable Retry & Failover**: Execute retries on the same provider or switch to the next provider node based on status codes.
6.  **Token Statistics**: Count input/output tokens according to "Standard Large Model Interface Token Counting Methods" and log them.
7.  **Full Observability**: Record detailed request logs, including time, model, provider, retries, latency, tokens, request/response, errors, etc.
8.  **Configurable & Manageable**: Provide a modern admin panel to support CRUD operations for Providers, Models/Rules, API Cases, and log queries/filtering.
9.  **Multi-Database Engine**: Support SQLite and PostgreSQL, defaulting to SQLite; abstract data access to facilitate switching.
10. **Engineering Quality**: All code must have unit tests, and all unit tests must pass during execution.

## 3. Scope & Out of Scope
### 3.1 Scope (In Scope)
-   Access and proxy forwarding of OpenAI/Anthropic style requests (only modify model name).
-   Rule Engine: Match based on context and output candidate providers and target models.
-   Round Robin strategy for selecting provider nodes.
-   Retry and failover logic.
-   Token statistics and database logging.
-   Database storage: Providers, Model Mappings/Rules, Strategies, API Cases (API Keys), Request Logs.
-   Admin Panel: CRUD for Providers/Models/Rules/API Cases; Request log query and multi-condition filtering.

### 3.2 Out of Scope
-   **No Rate Limiting**.
-   **No Account-Level Control** (Account/Tenant quotas, tiered permissions, usage control, etc.).
-   Rewriting request/response content other than the `model` field (Not done).
-   Permission systems (Admin background login/role permissions) are not defined in this requirement (can be added later).

## 4. Terminology & Key Concepts
-   **Requested Model**: The model name carried in the client request body.
-   **Target Model**: The model name replaced into the request body after system matching.
-   **Provider/Vendor**: Upstream provider node, possessing interface address, protocol, and API type.
-   **Vendor Node**: A callable provider node (usually corresponding to a provider configuration record).
-   **API Case**: API Key entity used for authentication (containing `key_name` and `key_value`/token).
-   **Strategy**: Currently only supports **Round Robin**.
-   **Rule Engine Context**: The input data set used for rule matching.

## 5. Overall Architecture
### 5.1 System Components
-   **Backend**: Python + FastAPI
    -   Proxy Interface (OpenAI/Anthropic compatible)
    -   Admin Interface (called by frontend panel)
    -   Rule Engine
    -   Provider Client (Multi-protocol/Multi-API adapter)
    -   Retry & Failover Handler
    -   Token Counter
    -   Log Recording & Sanitization Module
    -   Data Access Abstraction Layer (Repository/DAO) + Multi-DB Adapter (SQLite/PG)
-   **Frontend**: Next.js + TypeScript
    -   Provider Management
    -   Model & Rule Management (including Provider-Target Model differentiated configuration)
    -   API Case Management
    -   Request Log View & Multi-condition Filtering

### 5.2 Core Request Flow (Proxy Link)
1.  Client initiates request (OpenAI/Anthropic style).
2.  Backend authentication (API Case token), obtains `api_key_id`.
3.  Parse request body and headers, extract `requested_model`.
4.  Calculate input Tokens (Standard Token counting method).
5.  Rule engine processes all rules, outputs **candidate provider set** based on context (each provider corresponds to a target model).
6.  Round Robin strategy selects the current provider node from candidate providers.
7.  **Only replace the model field in the request body** with the target model corresponding to that provider.
8.  Forward request to that provider; execute retries on the same provider or switch to the next provider node according to failure strategy.
9.  Return final response to client.
10. Calculate output Tokens, record request logs (sanitize sensitive fields before storage).

## 6. Functional Requirements

### 6.1 Request Access & Forwarding
-   FR-REQ-1: Support receiving OpenAI or Anthropic client requests (compatible with their invocation methods).
-   FR-REQ-2: Keep request headers and body unchanged during forwarding, **only allowing modification of the model name field**.
-   FR-REQ-3: Forward requests to the upstream provider interface according to configuration and return the response to the client.

### 6.2 Model Replacement (Only Change Model)
-   FR-MDL-1: Get `requested_model` from request body.
-   FR-MDL-2: Determine `target_model` (bound to provider) based on rules and strategy.
-   FR-MDL-3: Only replace the `model` field in the request body, do not modify other fields (messages/tools/temperature/max_tokens, etc., remain consistent).

### 6.3 Rule Engine
-   FR-RULE-1: Rule engine must "process all rules" (full evaluation) for every request and output matching results.
-   FR-RULE-2: Rule engine context must include:
    -   `current_model`: Current requested model (`requested_model`)
    -   `headers`: Request headers (structured object)
    -   `request_body`: Request body (structured object)
    -   `token_usage`: Current Token consumption (at least includes this input Token; extensible)
-   FR-RULE-3: Rule engine output must include:
    -   List of candidate provider nodes (based on matching results)
    -   **Target model corresponding to each candidate provider** (Because: the same requested model maps to different target models under different providers)
    -   Meta-information required for strategy selection (such as priority, weight, availability, etc., extensible)

### 6.4 Provider Selection Strategy (Round Robin)
-   FR-STR-1: System must implement strategy mechanism; currently only supports **Round Robin**.
-   FR-STR-2: Round Robin rotates selection among candidate provider nodes.
-   FR-STR-3: Round Robin state must be concurrency-safe (can be implemented via DB/Cache/Atomic Counter, specific implementation decided by design).

### 6.5 Retry & Failover
-   FR-RT-1: When upstream response status code **≥ 500**:
    -   Retry on **same provider**
    -   Interval **1000ms** each time
    -   Max **3** retries
-   FR-RT-2: If 3 retries on the same provider still fail, switch to the **next matched provider node** and continue trying.
-   FR-RT-3: When upstream response status code **< 500**:
    -   Do not retry on the same provider
    -   Directly switch to the **next matched provider node** and try
-   FR-RT-4: When all candidate providers fail, the system should return a failure result to the client (suggest returning the status and error information of the last failure; specific response encapsulation can be defined uniformly during implementation).

### 6.6 Token Statistics
-   FR-TOK-1: Input Token: Use "Standard Large Model Interface Token Counting Method" to count user requests.
-   FR-TOK-2: Output Token: Count output Tokens for upstream responses.
-   FR-TOK-3: Input/Output Tokens must be written to request logs.

> Note: Token counting method needs to be consistent with the target protocol (OpenAI/Anthropic); implementation can use pluggable counters, selecting counting method by endpoint/protocol.

### 6.7 Request Log Recording (Full, Traceable, Persisted)
-   FR-LOG-1: All requests must record detailed logs, fields at least include:
    -   Request time (`request_time`)
    -   API Case: `api_key_id` / `api_key_name`
    -   `requested_model`, `target_model`
    -   Provider: `provider_id` / `provider_name`
    -   `retry_count`
    -   `first_byte_delay` (TTFB)
    -   `total_time`
    -   `input_tokens`, `output_tokens`
    -   `request_headers` (structured, **after sanitization**)
    -   `request_body` (structured)
    -   `response_status`
    -   `response_body`
    -   `error_info` (Error information: structured or text)
-   FR-LOG-2: Logs must support multi-condition filtering queries (for frontend log page use).

### 6.8 Sensitive Information Sanitization
-   FR-SEC-LOG-1: `request_headers` recorded in logs must sanitize/mask the `authorization` field before storage.
    -   Example requirement: Keep field name, mask the value part (e.g., `Bearer *****` or only keep first/last few characters, mask the middle).
-   FR-SEC-LOG-2: Sanitization should be handled uniformly before storage, ensuring plain text authorization is not saved in the database.

### 6.9 API Case (API Key) Management
-   FR-KEY-1: System provides API Case table, containing:
    -   API key name
    -   API key value (token)
-   FR-KEY-2: API key value generated by random algorithm.
-   FR-KEY-3: The **ID** of the API Case used for each request **must be logged** (`api_key_id`).

## 7. Data Storage & Multi-Database Support

### 7.1 Database Storage Engine
-   FR-DB-1: Support **SQLite** and **PostgreSQL (PG)** storage engines.
-   FR-DB-2: Default to SQLite.
-   FR-DB-3: Switch database engine via configuration (e.g., environment variable or configuration file).

### 7.2 Data Access Abstraction & Layering
-   FR-DB-4: Database access must be abstracted (Repository/DAO Interface), business logic must not couple with specific database implementation.
-   FR-DB-5: Common data access patterns, transaction management, pagination queries, etc., should be consolidated in a common package to avoid duplicate implementation.

## 8. Data Models (Recommended Structure, Supports "Same Model + Different Provider = Different Target Model")
> Specific field types subject to implementation; suggest unifying designs compatible with SQLite/PG and maintaining via migration tools.

### 8.1 Service Provider Table: `service_providers`
-   `id` (PK)
-   `name`
-   `base_url` (Interface Address)
-   `protocol` (Protocol/Compatibility Type)
-   `api_type` / `api_name`
-   `is_active` (Suggested)
-   `created_at` / `updated_at` (Suggested)

### 8.2 Model Mapping Table: `model_mappings` (Keyed by `requested_model`)
-   `requested_model` (PK)
-   `strategy` (Currently fixed: Round Robin)
-   `matching_rules` (Model layer rules, optional; format defined by rule engine)
-   `capabilities` / `functionality` (Optional)
-   `created_at` / `updated_at` (Suggested)

### 8.3 Model-Provider Mapping Table: `model_mapping_providers` (Key: Each provider can have different `target_model`)
-   `id` (PK)
-   `requested_model` (FK -> model_mappings.requested_model)
-   `provider_id` (FK -> service_providers.id)
-   `target_model_name` (**Target model name corresponding to this provider**)
-   `provider_rules` (Optional: Provider-level rules for finer-grained control; format same as rule engine definition)
-   `priority` (Optional)
-   `weight` (Optional)
-   `is_active` (Suggested)
-   `created_at` / `updated_at` (Suggested)

### 8.4 API Case Table: `api_keys`
-   `id` (PK)
-   `key_name` (unique)
-   `key_value` (randomly generated token)
-   `is_active` (Suggested)
-   `created_at` / `last_used_at` (Suggested)

### 8.5 Request Log Table: `request_logs`
-   `id` (PK)
-   `request_time`
-   `api_key_id` (FK -> api_keys.id)
-   `api_key_name` (Redundant allowed)
-   `requested_model`
-   `target_model`
-   `provider_id` (FK -> service_providers.id)
-   `retry_count`
-   `first_byte_delay_ms`
-   `total_time_ms`
-   `input_tokens`
-   `output_tokens`
-   `request_headers` (JSON / JSONB; **Sanitized**)
-   `request_body` (JSON / JSONB)
-   `response_status`
-   `response_body` (JSON/TEXT)
-   `error_info` (JSON/TEXT)
-   `trace_id` (Suggested)

## 9. Backend Interface (FastAPI)

### 9.1 Proxy Interface (Client Facing)
-   Core interfaces compatible with OpenAI/Anthropic (Specific path set determined by implementation).
-   Behavior: Auth -> Rule Match -> Round Robin Provider Selection -> Replace Model -> Forward -> Retry/Switch -> Return -> Log.

### 9.2 Admin Interface (For Frontend Panel)
-   `/admin/providers`: Provider CRUD
-   `/admin/models`: Model Mapping CRUD (including rule fields)
-   `/admin/model-providers`: Model-Provider Mapping CRUD (requested_model + provider_id + target_model + provider_rules)
-   `/admin/api-keys`: API Case CRUD
-   `/admin/logs`: Log Query (Pagination + Multi-condition Filtering)
-   `/admin/logs/{id}`: Log Detail

## 10. Frontend Admin Panel (Next.js + TypeScript)

### 10.1 General Requirements
-   FE-UI-1: Modern design style (clear hierarchy, unified spacing, responsive layout, good interaction feedback).
-   FE-UI-2: Common component consolidation: Table, Form, Modal, Pagination, Filter, JSON Display/Edit components, etc., avoiding duplicate code.
-   FE-UI-3: List pages support pagination, sorting, search; operations require confirmation and result notification.

### 10.2 Provider Management (CRUD)
-   List: Display ID, name, base_url, protocol, api_type/api_name, status, update time, etc.
-   Add/Edit: Form validation (Required, URL format, etc.).
-   Delete: Double confirmation; Prompt if referenced (specific constraints decided by backend).

### 10.3 Model Management (CRUD + Rule Setting + Provider Differentiated Target Model)
-   Model Mapping (`model_mappings`) CRUD:
    -   `requested_model`, strategy (Round Robin), model layer rules (if enabled), functionality description, etc.
-   **Model-Provider Mapping (`model_mapping_providers`) CRUD (Key)**:
    -   Under the same `requested_model`, can configure multiple providers
    -   **Each provider can configure a different `target_model_name`**
    -   Can configure `provider_rules` (if enabled) to support finer matching logic
    -   Can configure priority/weight (Optional)
-   Rule Editor:
    -   Needs to support rule setting and validation, rules can reference context: `model`, `headers`, `request_body`, `token_usage`.
    -   Suggested Form (Implementation Selection):
        1)  **Structured Rule Editor** (Preferred, reduces manual errors)
        2)  **JSON Rule Editor** (Fallback)
            -   Suggest evaluating open-source components: Monaco Editor (JSON + Schema validation), or JSON Schema-based form editor, etc. (Selected during implementation phase)

### 10.4 Request Log Page (View + Multi-condition Filtering)
-   List default sorted by time descending.
-   Must support filtering conditions (at least):
    -   Time range (Start/End)
    -   `requested_model` / `target_model` (Fuzzy)
    -   `provider` (Dropdown)
    -   `response_status` (Exact/Range, e.g., 2xx/4xx/5xx or >=500)
    -   Has Error (`error_info` is not empty)
    -   `api_key_id` / `api_key_name`
    -   `retry_count` (=0 / >0)
    -   Token range (Optional)
    -   Total time range (Optional)
-   Log Detail: Display sanitized `headers`, structured `request_body`, `response_body`, `error_info`, and support copy/collapse.

### 10.5 API Case Page (CRUD)
-   List: id, key_name, key_value (Hidden by default, copyable display strategy), status, create time, last used time, etc.
-   Add: Input `key_name`, `key_value` generated randomly by backend and returned; provide copy entry after successful creation.
-   Edit: Allow modifying name/status (Whether to support resetting key_value can be an extension).
-   Delete: Double confirmation.

## 11. Engineering Architecture & Code Standards (Backend)
### 11.1 Layering & Reusability
-   NFR-ARCH-1: Adopt clear layering, avoid writing business logic or SQL directly in the route layer.
-   NFR-ARCH-2: Business logic (Service) depends on Repository Interface rather than concrete database implementation.
-   NFR-ARCH-3: Common capabilities extracted to common package (`common`) to avoid duplicate code:
    -   Retrier, HTTP Client Wrapper, Timer, Token Counter, Sanitizer, Error Wrapper, Config Loading, etc.
-   NFR-ARCH-4: Module responsibility single, naming standard, testable, extensible.

### 11.2 Recommended Directory Structure (Example)
-   `app/`
    -   `api/` (Route Layer)
    -   `services/` (Business Orchestration: Match/RoundRobin/Forward/Retry/Log)
    -   `rules/` (Rule Engine: Rule Definition, Context, Executor)
    -   `providers/` (Upstream Adapter: openai-like / anthropic-like)
    -   `repositories/` (Repository Interface)
    -   `repositories/sqlalchemy/` (SQLite/PG Implementation)
    -   `db/` (Connection, Session, Migration)
    -   `domain/` (Domain Model/DTO)
    -   `common/` (Common Capabilities)
    -   `tests/`

## 12. Testing & Quality Gate (Mandatory)
-   NFR-TEST-1: **All code must have unit tests**.
-   NFR-TEST-2: **All unit tests must pass** during execution/delivery (Failure blocks).
-   NFR-TEST-3: Key coverage scope (at least):
    -   Rule Engine: Matching logic with context containing headers/request_body/token_usage/model
    -   Model Replacement: Only modify model, do not modify other fields
    -   Round Robin Strategy: Multi-node rotation correctness and concurrency consistency (Select testable scheme by design)
    -   Retry/Switch: ≥500 Same provider 1000ms * 3; < 500 Direct switch; Node exhaustion behavior
    -   Provider Forwarding: Request pass-through, Response pass-through, Error handling
    -   Token Counting: Input/Output statistics and logging
    -   Repository: Basic read/write and consistency under SQLite (default); Contract testing for extensible PG adapter
    -   Sanitization: Verification of authorization field masking before storage
-   NFR-TEST-4: External dependencies injectable/Mockable (DB, Upstream HTTP, Time, Random Number), ensuring stable and repeatable tests.

## 13. Acceptance Criteria (Definition of Done)
1.  Proxy link available: Request access, Rule matching, Round Robin selection, Only replace model, Forward, Retry/Switch per rules, Return response.
2.  Rule engine context includes: model, headers, request_body, token_usage; and can output candidate providers and their `target_model`.
3.  Log full storage: Fields complete; authorization sanitized; Queryable by conditions.
4.  Database support: Default SQLite runnable; Switch to PG without changing business code (Only config switch + implementation layer adapter).
5.  Admin Panel available: Provider CRUD, Model/Rule/Provider Target Model Configuration CRUD, API Case CRUD, Log Query & Multi-condition Filtering.
6.  Unit test coverage meets requirements, and all unit tests pass during project execution.

## 14. Next Steps (Implementation Suggestions)

1.  Clarify the specific endpoint list and field difference handling strategies for OpenAI/Anthropic compatibility in the first phase (Maintain "Only Change Model" principle).
2.  Define rule format (JSON/DSL) and validation mechanism, and synchronize frontend rule editor selection (Structured preferred + JSON editor fallback).
3.  Determine Multi-DB technical scheme (e.g., Unified ORM/Migration Tool), implement Repository interface and implementation separation.
4.  Establish test baseline: Test framework, Mock standards, Contract test templates, and CI gate process.
