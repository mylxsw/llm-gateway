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
- `add_extra_headers_column.sql` - Adds the `extra_headers` JSON field to the `service_providers` table for custom headers.
- `add_protocol_conversion_columns.sql` - Adds protocol conversion tracking columns to `request_logs` for debugging and analysis:
  - `request_protocol` - Client request protocol (openai/anthropic)
  - `supplier_protocol` - Upstream supplier protocol (openai/anthropic)
  - `converted_request_body` - Request body after protocol conversion
  - `upstream_response_body` - Original upstream response before protocol conversion
