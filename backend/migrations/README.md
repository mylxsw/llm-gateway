# Database Migrations

This directory contains manual SQL migration scripts for the database schema.

## Running Migrations

### SQLite

```bash
sqlite3 your_database.db < migrations/add_is_stream_column.sql
```

### PostgreSQL

```bash
psql -U username -d database_name -f migrations/add_is_stream_column.sql
```

## Migration Files

- `add_is_stream_column.sql` - Adds the `is_stream` boolean field to the `request_logs` table to indicate whether a request is a stream request.
