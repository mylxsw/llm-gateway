# Quick Start Guide - Stream Display Feature

## Issue Fixed
The `is_stream` field was not being saved to or retrieved from the database because the repository layer was missing the field mapping.

## What Was Fixed
Added `is_stream` field handling to:
- `backend/app/repositories/sqlalchemy/log_repo.py` - Both `create()` and `_to_domain()` methods

## Steps to Deploy

### For New Installations
Just start the backend - the database will be created with the `is_stream` column automatically.

### For Existing Installations (IMPORTANT)

You MUST run the migration to add the `is_stream` column to your existing database:

#### If using SQLite:
```bash
cd backend
sqlite3 path/to/your/database.db < migrations/add_is_stream_column.sql
```

#### If using PostgreSQL:
```bash
cd backend
psql -U username -d database_name -f migrations/add_is_stream_column.sql
```

### Then Restart Services

```bash
# Backend
cd backend
source .venv/bin/activate
uv run python -m app.main

# Frontend (in another terminal)
cd frontend
npm run dev
```

## Testing Stream Display

1. Make a stream request through your API
2. Check the logs page - you should now see the wave icon (🌊) in the "Token消耗/Stream" column
3. For non-stream requests, you'll see a dash (-)

## Troubleshooting

**Problem**: Stream column still shows empty/undefined

**Solution**: 
1. Make sure you ran the migration script on your existing database
2. Restart the backend service after running the migration
3. Make a NEW stream request (old requests won't have the field)
4. Check browser console for any API errors

**Problem**: Database error about missing column

**Solution**: Run the migration script - see "For Existing Installations" above
