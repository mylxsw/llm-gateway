-- Add usage_details column to request_logs for structured token usage details.
ALTER TABLE request_logs ADD COLUMN usage_details JSON;
