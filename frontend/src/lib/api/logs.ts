/**
 * Log Query API
 * Corresponds to backend /api/admin/logs route
 */

import { get, post } from './client';
import {
  RequestLog,
  RequestLogDetail,
  LogQueryParams,
  LogCostStatsResponse,
  PaginatedResponse,
  RetryLogResponse,
  LogPlaygroundExecuteRequest,
} from '@/types';
import { getStoredAdminToken } from './client';

const BASE_URL = '/api/admin/logs';
const RETRY_TIMEOUT_MS = 5 * 60 * 1000;

/**
 * Query Request Logs List
 * Supports multi-condition filtering, pagination, sorting
 * @param params - Query parameters
 */
export async function getLogs(
  params?: LogQueryParams
): Promise<PaginatedResponse<RequestLog>> {
  // Filter out undefined values
  const cleanParams = params
    ? Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
      )
    : undefined;
  return get<PaginatedResponse<RequestLog>>(BASE_URL, cleanParams);
}

/**
 * Get Log Details
 * Includes full request/response info
 * @param id - Log ID
 */
export async function getLogDetail(id: number): Promise<RequestLogDetail> {
  return get<RequestLogDetail>(`${BASE_URL}/${id}`);
}

export async function retryLog(id: number): Promise<RetryLogResponse> {
  return post<RetryLogResponse>(`${BASE_URL}/${id}/retry`, undefined, {
    timeout: RETRY_TIMEOUT_MS,
  });
}

export async function executeLogPlaygroundRequest(
  id: number,
  data: LogPlaygroundExecuteRequest
): Promise<Response> {
  const token = getStoredAdminToken();
  return fetch(`${BASE_URL}/${id}/playground`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
  });
}

/**
 * Get cost stats for log list filters
 */
export async function getLogCostStats(
  params?: LogQueryParams
): Promise<LogCostStatsResponse> {
  const picked = params
    ? {
        start_time: params.start_time,
        end_time: params.end_time,
        timeline: params.timeline,
        requested_model: params.requested_model,
        provider_id: params.provider_id,
        api_key_id: params.api_key_id,
        api_key_name: params.api_key_name,
        tz_offset_minutes: params.tz_offset_minutes,
        bucket: params.bucket,
        bucket_minutes: params.bucket_minutes,
        group_by: params.group_by,
      }
    : undefined;

  const cleanParams = picked
    ? Object.fromEntries(
        Object.entries(picked).filter(([, v]) => v !== undefined && v !== '')
      )
    : undefined;

  return get<LogCostStatsResponse>(`${BASE_URL}/stats`, cleanParams);
}
