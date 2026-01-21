# Troubleshooting Guide - Stream Display Not Showing

## Problem
Stream requests are showing a dash (-) instead of the wave icon (🌊), even for actual stream requests.

## Diagnosis Steps

### Step 1: Check if the database has the is_stream column

Run this from the `backend` directory:

```bash
python3 check_migration.py
```

This script will:
- ✅ Check if the `is_stream` column exists
- ✅ Add it automatically if missing
- ✅ Show recent log entries and their is_stream values
- ✅ Detect any mismatches

**Expected output if column is missing:**
```
⚠️  Column 'is_stream' not found. Adding it now...
✅ Successfully added 'is_stream' column to request_logs table
```

**Expected output if column exists:**
```
✅ Column 'is_stream' already exists in request_logs table

📊 Recent log entries:
ID | is_stream | Expected (from response_body)
--------------------------------------------------
  45 |         1 | should_be_stream
  44 |         0 | non_stream
```

### Step 2: Check Backend Logs

When you make a request, the backend prints debug information. Look for:

```
[DEBUG] Request Log: {"id":...,"is_stream":true,...}
```

or

```
[DEBUG] Request Log: {"id":...,"is_stream":false,...}
```

**If you see `"is_stream":true` or `"is_stream":false` in the logs:**
✅ The backend is correctly setting the field

**If you DON'T see is_stream in the debug output:**
❌ The backend code changes weren't applied - make sure you restarted the backend after pulling changes

### Step 3: Check API Response

Open browser DevTools (F12) → Network tab, and look at the response from `/admin/logs`:

```json
{
  "items": [
    {
      "id": 123,
      "is_stream": true,   ← Should be here!
      ...
    }
  ]
}
```

**If `is_stream` is missing from API response:**
- The backend wasn't restarted after the code changes
- The repository layer is not mapping the field (check `backend/app/repositories/sqlalchemy/log_repo.py`)

**If `is_stream` is null or undefined:**
- Old database records won't have this field (they were created before the column existed)
- Make a NEW request after running the migration

### Step 4: Check Frontend Console

Open browser console and check for any errors when the LogList component renders.

## Solutions

### Solution 1: Run the Migration

From `backend` directory:

```bash
# Option A: Use the automated checker
python3 check_migration.py

# Option B: Run SQL manually
sqlite3 llm_gateway.db < migrations/add_is_stream_column.sql
```

### Solution 2: Restart Backend

After adding the column, you MUST restart the backend:

```bash
cd backend
# Stop the running backend (Ctrl+C)
# Then start it again
uv run python -m app.main
```

### Solution 3: Make Fresh Requests

**Important:** Old log records (created before the is_stream column was added) will show as non-stream even if they were stream requests.

To test properly:
1. Run the migration
2. Restart backend
3. Make a NEW stream request
4. Make a NEW non-stream request
5. Check the logs page - new entries should show correctly

### Solution 4: Verify Code Changes

Make sure these files have the is_stream field:

```bash
# Check if is_stream is in the repository
cd backend
grep "is_stream" app/repositories/sqlalchemy/log_repo.py

# Should see 2 matches:
#   is_stream=entity.is_stream,
#   is_stream=data.is_stream,
```

## Quick Test

To verify everything is working:

1. **Run migration checker:**
   ```bash
   cd backend
   python3 check_migration.py
   ```

2. **Restart backend** (important!)

3. **Make a stream request:**
   ```bash
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4",
       "messages": [{"role": "user", "content": "Hello"}],
       "stream": true
     }'
   ```

4. **Check backend logs** - Look for:
   ```
   [DEBUG] Request Log: {...,"is_stream":true,...}
   ```

5. **Check frontend** - The newest log entry should show 🌊

## Still Not Working?

If you've done all the above and it's still not working, please provide:

1. Output from `python3 check_migration.py`
2. The `[DEBUG] Request Log:` line from backend console
3. The API response from browser DevTools Network tab (`/admin/logs`)
4. Browser console errors (if any)

This will help identify exactly where the issue is occurring.
