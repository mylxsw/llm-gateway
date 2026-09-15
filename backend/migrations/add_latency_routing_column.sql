-- Add per-model streaming TTFT routing policy.
ALTER TABLE model_mappings ADD COLUMN latency_routing JSON;
