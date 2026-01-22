/**
 * Request Log Related Type Definitions
 * Corresponds to backend request_logs table
 */

/** Request Log Entity (For List View) */
export interface RequestLog {
  id: number;
  request_time: string;
  api_key_id?: number;
  api_key_name?: string;
  requested_model?: string;
  target_model?: string;
  provider_id?: number;
  provider_name?: string;
  retry_count: number;
  first_byte_delay_ms?: number;
  total_time_ms?: number;
  input_tokens?: number;
  output_tokens?: number;
  total_cost?: number | null;
  input_cost?: number | null;
  output_cost?: number | null;
  response_status?: number;
  trace_id?: string;
  is_stream?: boolean;
}

/** Request Log Detail Entity (Includes full request/response) */
export interface RequestLogDetail extends RequestLog {
  request_headers?: Record<string, string>;  // Sanitized
  response_headers?: Record<string, string>; // Sanitized
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  request_body?: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  response_body?: any;
  error_info?: string;
  price_source?: 'SupplierOverride' | 'ModelFallback' | 'DefaultZero' | string | null;
  request_protocol?: string;
  supplier_protocol?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  converted_request_body?: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  upstream_response_body?: any;
}

/** Log Query Params */
export interface LogQueryParams {
  // Time range
  start_time?: string;
  end_time?: string;

  // Client timezone offset minutes for stats bucketing (UTC to local)
  tz_offset_minutes?: number;

  // Trend bucketing hint for stats (hour/day)
  bucket?: 'hour' | 'day';
  
  // Model filter
  requested_model?: string;
  target_model?: string;
  
  // Provider filter
  provider_id?: number;
  
  // Status code filter
  status_min?: number;
  status_max?: number;
  
  // Error filter
  has_error?: boolean;
  
  // API Key filter
  api_key_id?: number;
  api_key_name?: string;
  
  // Retry count filter
  retry_count_min?: number;
  retry_count_max?: number;
  
  // Token range filter
  input_tokens_min?: number;
  input_tokens_max?: number;
  
  // Duration range filter
  total_time_min?: number;
  total_time_max?: number;
  
  // Pagination and Sorting
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface LogCostSummary {
  request_count: number;
  total_cost: number;
  input_cost: number;
  output_cost: number;
  input_tokens: number;
  output_tokens: number;
}

export interface LogCostTrendPoint {
  bucket: string;
  request_count: number;
  total_cost: number;
  input_cost: number;
  output_cost: number;
  input_tokens: number;
  output_tokens: number;
  error_count: number;
  success_count: number;
}

export interface LogCostByModel {
  requested_model: string;
  request_count: number;
  total_cost: number;
}

export interface LogCostStatsResponse {
  summary: LogCostSummary;
  trend: LogCostTrendPoint[];
  by_model: LogCostByModel[];
}
