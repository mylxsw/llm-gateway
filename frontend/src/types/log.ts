/**
 * 请求日志相关类型定义
 * 对应后端 request_logs 表
 */

/** 请求日志实体（列表展示用） */
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

/** 请求日志详情实体（包含完整请求/响应） */
export interface RequestLogDetail extends RequestLog {
  request_headers?: Record<string, string>;  // 已脱敏
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  request_body?: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  response_body?: any;
  error_info?: string;
}

/** 日志查询参数 */
export interface LogQueryParams {
  // 时间范围
  start_time?: string;
  end_time?: string;
  
  // 模型过滤
  requested_model?: string;
  target_model?: string;
  
  // 供应商过滤
  provider_id?: number;
  
  // 状态码过滤
  status_min?: number;
  status_max?: number;
  
  // 错误过滤
  has_error?: boolean;
  
  // API Key 过滤
  api_key_id?: number;
  api_key_name?: string;
  
  // 重试次数过滤
  retry_count_min?: number;
  retry_count_max?: number;
  
  // Token 区间过滤
  input_tokens_min?: number;
  input_tokens_max?: number;
  
  // 耗时区间过滤
  total_time_min?: number;
  total_time_max?: number;
  
  // 分页与排序
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}
