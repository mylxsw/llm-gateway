# In-Progress Request Logs Implementation Plan

> **For Hermes:** Implement task-by-task in order. Each task is a self-contained TDD cycle (RED-GREEN-REFACTOR-COMMIT).

**Goal:** Track in-progress requests in the log — write a log entry immediately when a request is received, update it when the request completes, and allow cancellation from the admin dashboard.

**Architecture:** Two-phase log writing — `create_initial()` on request arrival (with `is_completed=False`) and `update()` on completion (`is_completed=True`). A new `ActiveRequestTracker` singleton stores `asyncio.Task` references keyed by `log_id` so the admin API can cancel them. Frontend shows a spinner + elapsed timer for in-progress logs, plus a cancel button.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy (async), Alembic, Next.js 16, TypeScript, shadcn/ui

---

## Changes Overview

| Layer | Files | Change Type |
|---|---|---|
| DB Model | `backend/app/db/models.py` | Add `is_completed` column |
| Domain | `backend/app/domain/log.py` | Add `is_completed` field to all DTOs + query filter |
| Repository (abstract) | `backend/app/repositories/log_repo.py` | Add `create_initial`, `update` abstract methods |
| Repository (impl) | `backend/app/repositories/sqlalchemy/log_repo.py` | Implement `create_initial`, `update` |
| Service | `backend/app/services/log_service.py` | Expose new repo methods |
| Proxy Service | `backend/app/services/proxy_service.py` | Two-phase log writing + cancellation support |
| Active Tracker | `backend/app/services/active_requests.py` | **NEW** — track active tasks |
| Admin API | `backend/app/api/admin/logs.py` | Add `POST /{log_id}/cancel` endpoint |
| Migration | `backend/migrations/` | Alembic migration for `is_completed` column |
| Types | `frontend/src/types/log.ts` | Add `is_completed` |
| API Client | `frontend/src/lib/api/logs.ts` | Add `cancelLog()` |
| LogList | `frontend/src/components/logs/LogList.tsx` | In-progress indicator, elapsed time, cancel button |
| i18n en | `frontend/messages/en.json` | New strings |
| i18n zh | `frontend/messages/zh.json` | New strings |

---

### Task 1: Add `is_completed` column to DB model

**Objective:** Extend the `RequestLog` ORM model with a boolean `is_completed` column (default `True` for backward compat).

**Files:**
- Modify: `backend/app/db/models.py`

**Step 1: Write change**

After `is_stream` column (line ~358), add:
```python
    # Is request completed
    is_completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

**Step 2: Create alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add is_completed to request_logs"
```

Then run:
```bash
cd backend && alembic upgrade head
```

**Step 3: Commit**

```bash
git add backend/app/db/models.py backend/migrations/
git commit -m "feat(db): add is_completed column to request_logs"
```

---

### Task 2: Add `is_completed` to domain models

**Objective:** Extend all DTOs with `is_completed` field.

**Files:**
- Modify: `backend/app/domain/log.py`

**Changes:**

1. `RequestLogBase` — add:
```python
    is_completed: bool = Field(True, description="Whether the request has completed")
```

2. `RequestLogModel` — add (inherits from RequestLogCreate which inherits from RequestLogBase, so already covered)

3. `RequestLogSummary` — add:
```python
    is_completed: bool = True
```

4. `RequestLogResponse` — add:
```python
    is_completed: bool = True
```

5. `RequestLogQuery` — add filter field:
```python
    is_completed: Optional[bool] = Field(None, description="Is Completed")
```

**Step 1: Apply changes**

Use `patch` tool to edit `backend/app/domain/log.py` — add `is_completed: bool = Field(True, description="Whether the request has completed")` to `RequestLogBase`, `is_completed: bool = True` to `RequestLogSummary` and `RequestLogResponse`, and `is_completed: Optional[bool] = Field(None, description="Is Completed")` to `RequestLogQuery`.

**Step 2: Commit**

```bash
git add backend/app/domain/log.py
git commit -m "feat(domain): add is_completed to log DTOs"
```

---

### Task 3: Add `create_initial` and `update` to abstract repository

**Objective:** Define the new repository methods in the abstract interface.

**Files:**
- Modify: `backend/app/repositories/log_repo.py`

**Add after `create` method:**

```python
    @abstractmethod
    async def create_initial(self, data: RequestLogCreate) -> int:
        """
        Create a minimal log entry (is_completed=False) and return the log ID.
        Only summary fields are written; detail fields are left NULL.
        """
        pass

    @abstractmethod
    async def update(self, log_id: int, data: RequestLogCreate) -> RequestLogModel:
        """
        Update an existing log entry with completion data, setting is_completed=True.
        """
        pass
```

Also add `cancel` to the abstract interface (implemented later):

```python
    @abstractmethod
    async def cancel(self, log_id: int, error_info: str = "Request cancelled by admin") -> None:
        """
        Mark an in-progress log as cancelled (is_completed=True, with error_info).
        """
        pass
```

**Step 1: Apply changes**

**Step 2: Commit**

```bash
git add backend/app/repositories/log_repo.py
git commit -m "feat(repo): add create_initial, update, cancel abstract methods"
```

---

### Task 4: Implement `create_initial`, `update`, `cancel` in SQLAlchemy repo

**Objective:** Implement the new repository methods in the SQLAlchemy-backed repository.

**Files:**
- Modify: `backend/app/repositories/sqlalchemy/log_repo.py`

**Important:** `_SUMMARY_COLUMNS` must include `RequestLogORM.is_completed`.

**Step 1: Add `is_completed` to `_SUMMARY_COLUMNS`**

Add to the list after `RequestLogORM.is_stream`:
```python
    RequestLogORM.is_completed,
```

**Step 2: Add `_row_to_summary` support**

In `_row_to_summary`, add:
```python
    is_completed=row["is_completed"],
```

**Step 3: Implement `create_initial`**

```python
    async def create_initial(self, data: RequestLogCreate) -> int:
        """Create a minimal log entry immediately when a request is received."""
        entity = RequestLogORM(
            request_time=to_utc_naive(data.request_time),
            api_key_id=data.api_key_id,
            api_key_name=data.api_key_name,
            user_id=data.user_id,
            requested_model=data.requested_model,
            target_model=data.target_model,
            trace_id=data.trace_id,
            is_stream=data.is_stream,
            is_completed=False,
            request_protocol=data.request_protocol,
            request_path=data.request_path,
            request_url=data.request_url,
            request_method=data.request_method,
            # All other fields remain NULL until update
        )
        self.session.add(entity)
        await self.session.flush()
        log_id = entity.id
        await self.session.commit()
        return log_id
```

**Step 4: Implement `update`**

```python
    async def update(self, log_id: int, data: RequestLogCreate) -> RequestLogModel:
        """Update a log entry with completion data."""
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(RequestLogORM)
            .where(RequestLogORM.id == log_id)
            .values(
                provider_id=data.provider_id,
                provider_name=data.provider_name,
                retry_count=data.retry_count,
                matched_provider_count=data.matched_provider_count,
                first_byte_delay_ms=data.first_byte_delay_ms,
                total_time_ms=data.total_time_ms,
                input_tokens=data.input_tokens,
                output_tokens=data.output_tokens,
                total_cost=data.total_cost,
                input_cost=data.input_cost,
                output_cost=data.output_cost,
                cached_input_cost=data.cached_input_cost,
                cached_output_cost=data.cached_output_cost,
                price_source=data.price_source,
                response_status=data.response_status,
                is_completed=True,
                target_model=data.target_model,
                supplier_protocol=data.supplier_protocol,
                upstream_url=data.upstream_url,
            )
        )
        await self.session.execute(stmt)

        # Create/update detail entity
        detail = RequestLogDetailORM(
            log_id=log_id,
            request_body=data.request_body,
            response_body=data.response_body,
            request_headers=data.request_headers,
            response_headers=data.response_headers,
            converted_request_body=data.converted_request_body,
            upstream_response_body=data.upstream_response_body,
            usage_details=data.usage_details,
            error_info=data.error_info,
        )
        await self.session.merge(detail)
        await self.session.commit()

        # Re-fetch
        result = await self.session.execute(
            select(RequestLogORM)
            .options(joinedload(RequestLogORM.detail))
            .where(RequestLogORM.id == log_id)
        )
        entity = result.unique().scalar_one()
        return self._to_domain(entity)
```

**Step 5: Implement `cancel`**

```python
    async def cancel(self, log_id: int, error_info: str = "Request cancelled by admin") -> None:
        """Mark an in-progress request as cancelled."""
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(RequestLogORM)
            .where(RequestLogORM.id == log_id, RequestLogORM.is_completed == False)
            .values(
                is_completed=True,
                error_info=error_info,
                response_status=499,  # Client Closed Request
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()

        if result.rowcount == 0:
            raise NotFoundError(
                message=f"No in-progress request found with id {log_id}",
                code="log_not_found_or_completed",
            )
```

**Step 6: Add query filter**

In the `query` method, after existing conditions, add:
```python
        if query.is_completed is not None:
            conditions.append(RequestLogORM.is_completed == query.is_completed)
```

**Step 7: Commit**

```bash
git add backend/app/repositories/sqlalchemy/log_repo.py
git commit -m "feat(repo): implement create_initial, update, cancel for SQLAlchemy"
```

---

### Task 5: Add service methods in LogService

**Objective:** Expose new repo methods through the service layer.

**Files:**
- Modify: `backend/app/services/log_service.py`

**Add three new methods:**

```python
    async def create_initial(self, data: RequestLogCreate) -> int:
        return await self.repo.create_initial(data)

    async def update(self, log_id: int, data: RequestLogCreate) -> RequestLogModel:
        return await self.repo.update(log_id, data)

    async def cancel(self, log_id: int) -> None:
        await self.repo.cancel(log_id)
```

**Step 1: Apply changes**

**Step 2: Commit**

```bash
git add backend/app/services/log_service.py
git commit -m "feat(service): add create_initial, update, cancel to LogService"
```

---

### Task 6: Create ActiveRequestTracker

**Objective:** A global tracker that stores `asyncio.Task` references keyed by `log_id`, allowing cancellation.

**Files:**
- Create: `backend/app/services/active_requests.py`

```python
"""
Active Request Tracker

Stores asyncio.Task references for in-progress proxy requests so
they can be cancelled via the admin API.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ActiveRequestTracker:
    """Thread-safe tracker for active request tasks."""

    def __init__(self):
        self._tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, log_id: int, task: asyncio.Task) -> None:
        async with self._lock:
            self._tasks[log_id] = task

    async def deregister(self, log_id: int) -> None:
        async with self._lock:
            self._tasks.pop(log_id, None)

    async def cancel(self, log_id: int) -> bool:
        async with self._lock:
            task = self._tasks.pop(log_id, None)
        if task is None:
            return False
        task.cancel()
        return True

    async def is_active(self, log_id: int) -> bool:
        async with self._lock:
            return log_id in self._tasks


# Global singleton
active_requests = ActiveRequestTracker()
```

**Step 1: Create file**

**Step 2: Register in deps**

In `backend/app/api/deps.py`, import and expose:
```python
from app.services.active_requests import active_requests
```

**Step 3: Commit**

```bash
git add backend/app/services/active_requests.py backend/app/api/deps.py
git commit -m "feat(service): add ActiveRequestTracker for request cancellation"
```

---

### Task 7: Modify ProxyService for two-phase logging and cancellation

**Objective:** Change `process_request` and `process_request_stream` to:
1. Write initial log at the start (get `log_id`)
2. Register the task with `ActiveRequestTracker`
3. Update the log on completion

**Files:**
- Modify: `backend/app/services/proxy_service.py`

**Strategy:** In both `process_request` and `process_request_stream`:
- After extracting basic info (trace_id, request_time, etc.) but BEFORE `_resolve_candidates`, call `_write_initial_log()` to create a minimal entry.
- Store `log_id` for later update.
- Register the current asyncio task.
- At the end, replace the `_write_log` call with `_update_log(log_id, ...)`.
- In `finally` blocks (wrapped_generator in stream), always deregister.

**Step 1: Import ActiveRequestTracker**

Add import at top:
```python
from app.services.active_requests import active_requests
```

**Step 2: Add `_write_initial_log` helper**

```python
    async def _write_initial_log(
        self,
        request_time: datetime,
        api_key_id: int | None,
        api_key_name: str | None,
        user_id: str | None,
        requested_model: str,
        trace_id: str,
        is_stream: bool,
        request_protocol: str,
        path: str,
        request_url: str | None,
        method: str,
    ) -> int:
        log_data = RequestLogCreate(
            request_time=request_time,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            user_id=user_id,
            requested_model=requested_model,
            trace_id=trace_id,
            is_stream=is_stream,
            request_protocol=request_protocol,
            request_path=path,
            request_url=request_url,
            request_method=method,
            is_completed=False,
        )
        async with self._repos() as (_model_repo, _provider_repo, log_repo):
            log_id = await log_repo.create_initial(log_data)
        return log_id
```

**Step 3: Add `_update_log` helper**

Replace the final `_write_log` call pattern. Instead of building a full `RequestLogCreate` and calling `_write_log`, call `_update_log`:

```python
    async def _update_log(
        self, log_id: int, log_data: RequestLogCreate, record_details: bool = True
    ) -> None:
        if not record_details:
            _strip_detail_payload(log_data)
        try:
            with anyio.CancelScope(shield=True):
                async with self._repos() as (_model_repo, _provider_repo, log_repo):
                    await log_repo.update(log_id, log_data)
        except Exception:
            logger.exception("Failed to update log: log_id=%s", log_id)
```

**Step 4: Modify `process_request`**

Before `_resolve_candidates` call, insert:
```python
        log_id = await self._write_initial_log(
            request_time=request_time,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            user_id=user_id,
            requested_model=requested_model,
            trace_id=trace_id,
            is_stream=False,
            request_protocol=request_protocol,
            path=path,
            request_url=request_url,
            method=method,
        )
        current_task = asyncio.current_task()
        if current_task:
            await active_requests.register(log_id, current_task)
        try:
            # ... existing resolution + forward logic ...
        finally:
            await active_requests.deregister(log_id)
```

Replace final `await self._write_log(log_data, record_details=record_details)` with:
```python
            await self._update_log(log_id, log_data, record_details=record_details)
```

**Step 5: Modify `process_request_stream`**

Same pattern — insert initial log before `_resolve_candidates`, wrap main logic in try/finally for deregistration.

In the `wrapped_generator`'s `finally` block, replace the `_write_log` call with `_update_log`.

**Step 6: Modify `_write_log` → keep for failed attempts**

The `log_failed_attempt` callbacks in both methods still use `_write_log` — these are independent log entries for failed retries, which is correct. Keep as-is.

**Step 7: Commit**

```bash
git add backend/app/services/proxy_service.py
git commit -m "feat(proxy): two-phase log writing with active request tracking"
```

---

### Task 8: Add cancel endpoint to admin API

**Objective:** Add `POST /api/admin/logs/{log_id}/cancel` that cancels an in-progress request.

**Files:**
- Modify: `backend/app/api/admin/logs.py`

**Add endpoint:**

```python
from app.services.active_requests import active_requests
from app.common.errors import NotFoundError

@router.post("/{log_id}/cancel")
async def cancel_request(
    log_id: int,
    log_service: LogServiceDep,
):
    """
    Cancel an in-progress request.

    Cancels the underlying asyncio task and marks the log as completed with
    an error indicating the cancellation.
    """
    # Cancel the underlying task first
    cancelled = await active_requests.cancel(log_id)
    if not cancelled:
        # The task may have already completed; still try to mark the log
        pass

    # Mark the log as cancelled
    try:
        await log_service.cancel(log_id)
    except NotFoundError:
        raise NotFoundError(
            message=f"No in-progress request found with id {log_id}",
            code="request_not_found_or_completed",
        )

    return {"status": "cancelled", "log_id": log_id}
```

**Step 1: Apply changes**

**Step 2: Commit**

```bash
git add backend/app/api/admin/logs.py
git commit -m "feat(api): add POST /admin/logs/{id}/cancel endpoint"
```

---

### Task 9: Update frontend types and API client

**Objective:** Add `is_completed` to frontend types and add `cancelLog()` API call.

**Files:**
- Modify: `frontend/src/types/log.ts`
- Modify: `frontend/src/lib/api/logs.ts`

**Step 1: Add `is_completed` to `RequestLog`**

```typescript
  is_completed: boolean;
```

**Step 2: Add to `LogQueryParams`**

```typescript
  is_completed?: boolean;
```

**Step 3: Add `cancelLog` to API client**

```typescript
export async function cancelLog(id: number): Promise<{ status: string; log_id: number }> {
  return post<{ status: string; log_id: number }>(`${BASE_URL}/${id}/cancel`);
}
```

**Step 4: Commit**

```bash
git add frontend/src/types/log.ts frontend/src/lib/api/logs.ts
git commit -m "feat(frontend): add is_completed type and cancelLog API"
```

---

### Task 10: Update LogList component for in-progress requests

**Objective:** Show a spinner indicator, real-time elapsed time, and cancel button for in-progress logs.

**Files:**
- Modify: `frontend/src/components/logs/LogList.tsx`

**Changes:**

1. Import additional icons and `cancelLog`:
```typescript
import { Eye, ArrowRight, Waves, Loader2, XCircle } from 'lucide-react';
import { cancelLog } from '@/lib/api/logs';
```

2. Add state for in-progress timers:
```typescript
const [now, setNow] = useState(Date.now());
useEffect(() => {
  const interval = setInterval(() => setNow(Date.now()), 1000);
  return () => clearInterval(interval);
}, []);
```

3. Modify the response time cell rendering:
```typescript
const renderResponseTime = (log: RequestLog) => {
  if (!log.is_completed) {
    const elapsedMs = Date.now() - new Date(log.request_time).getTime();
    return (
      <div className="flex items-center gap-1 text-xs">
        <Loader2 className="h-3 w-3 animate-spin text-blue-500" suppressHydrationWarning />
        <span className="font-mono text-blue-500">{formatDuration(elapsedMs)}</span>
      </div>
    );
  }
  // ... existing rendering ...
};
```

4. Add cancel button in the action column:
```typescript
<TableCell className="text-right">
  <div className="flex items-center justify-end gap-1">
    {!log.is_completed && (
      <Button
        variant="ghost"
        size="icon"
        onClick={async (e) => {
          e.stopPropagation();
          try {
            await cancelLog(log.id);
            toast.success('Request cancelled');
          } catch {
            toast.error('Failed to cancel request');
          }
        }}
        title="Cancel request"
      >
        <XCircle className="h-4 w-4 text-red-500" suppressHydrationWarning />
      </Button>
    )}
    <Button
      variant="ghost"
      size="icon"
      onClick={() => onView(log)}
      title={t('list.viewDetails')}
    >
      <Eye className="h-4 w-4" suppressHydrationWarning />
    </Button>
  </div>
</TableCell>
```

5. Add badge for "In Progress" status:
```typescript
{!log.is_completed ? (
  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-300">
    <Loader2 className="mr-1 h-3 w-3 animate-spin inline" suppressHydrationWarning />
    {t('list.inProgress')}
  </Badge>
) : (
  <Badge variant="outline" className={statusColor}>
    {log.response_status ?? t('unknown')}
  </Badge>
)}
```

**Step 1: Apply changes**

**Step 2: Commit**

```bash
git add frontend/src/components/logs/LogList.tsx
git commit -m "feat(frontend): show in-progress indicator and cancel button in LogList"
```

---

### Task 11: Add i18n strings

**Objective:** Add translation keys for new UI elements.

**Files:**
- Modify: `frontend/messages/en.json`
- Modify: `frontend/messages/zh.json`

**English (`en.json`):**

Under `logs.list`:
```json
"inProgress": "In Progress",
"cancel": "Cancel",
"cancelConfirm": "Cancel this request?",
```

**Chinese (`zh.json`):**

Under `logs.list`:
```json
"inProgress": "处理中",
"cancel": "取消",
"cancelConfirm": "确认取消此请求？",
```

**Step 1: Apply changes**

**Step 2: Commit**

```bash
git add frontend/messages/en.json frontend/messages/zh.json
git commit -m "feat(i18n): add in-progress log translations"
```

---

### Task 12: Integration test and verification

**Objective:** Verify the full flow works end-to-end.

**Verification steps:**

1. Run backend tests:
```bash
cd backend && python -m pytest -x -q
```

2. Check that `is_completed` column was added:
```bash
cd backend && python -c "from app.db.models import RequestLog; print(RequestLog.is_completed)"
```

3. Manual test flow:
   - Start the backend server
   - Send a slow streaming request (e.g. to a slow model)
   - Check logs list — should see the in-progress entry with spinner
   - Wait for completion — entry should disappear from in-progress state
   - Send another request and click Cancel — request should terminate

**Step 1: Run tests**

**Step 2: Commit any fixes**

```bash
git add -A && git commit -m "fix: test fixes for in-progress log feature"
```

---

## Edge Cases & Risks

| Scenario | Handling |
|---|---|
| Server crash during request | On restart, stale `is_completed=False` entries exist. Next `process_request`/stream will have different log_id. A periodic cleanup (cron) can mark orphaned logs as completed with error. |
| Cancel during streaming | `asyncio.Task.cancel()` raises `CancelledError` inside the generator, which is caught in the existing error handler. The `finally` block in `wrapped_generator` runs and updates the log. |
| Cancel after already completed | `cancel` SQL checks `is_completed=False`, so it's a no-op + returns error. |
| Cancel race condition | `active_requests.cancel()` atomically pops the task; if already removed, returns False. Log repo's `cancel()` checks `is_completed=False` as a secondary guard. |
| Large database migration | Adding a boolean column with default=True is fast on both PostgreSQL and SQLite. |

## Open Questions

1. Should `is_completed=False` entries be excluded from cost stats? **Yes** — add filter in stats queries.
2. Should the default log query exclude completed-only or show both? Default should include both, with a filter toggle.
3. Should there be a periodic cleanup for orphaned in-progress logs? Yes — can be done as a follow-up cron or scheduled task in the app startup.

---

## Order of Implementation

Tasks must be executed in order (1→12) because:
- Domain models (Task 2) depend on DB model (Task 1)
- Repository impl (Task 4) depends on abstract (Task 3)
- Service (Task 5) depends on repository
- Proxy Service (Task 7) depends on ActiveRequestTracker (Task 6)
- API (Task 8) depends on Proxy Service changes
- Frontend (Tasks 9-11) can be done anytime after Task 5
