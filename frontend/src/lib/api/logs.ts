/**
 * Log Query API
 * Corresponds to backend /admin/logs route
 */

import { get } from './client';
import {
  RequestLog,
  RequestLogDetail,
  LogQueryParams,
  PaginatedResponse,
} from '@/types';

const BASE_URL = '/admin/logs';

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