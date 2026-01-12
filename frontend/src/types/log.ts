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
  response_status?: number;
  trace_id?: string;
  is_stream?: boolean;
}

/** Request Log Detail Entity (Includes full request/response) */
export interface RequestLogDetail extends RequestLog {
  request_headers?: Record<string, string>;  // Sanitized
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  request_body?: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  response_body?: any;
  error_info?: string;
}

/** Log Query Params */
export interface LogQueryParams {
  // Time range
  start_time?: string;
  end_time?: string;
  
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