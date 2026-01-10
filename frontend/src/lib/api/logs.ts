/**
 * 日志查询 API 接口
 * 对应后端 /admin/logs 路由
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
 * 查询请求日志列表
 * 支持多条件筛选、分页、排序
 * @param params - 查询参数
 */
export async function getLogs(
  params?: LogQueryParams
): Promise<PaginatedResponse<RequestLog>> {
  // 过滤掉 undefined 值
  const cleanParams = params
    ? Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
      )
    : undefined;
  return get<PaginatedResponse<RequestLog>>(BASE_URL, cleanParams);
}

/**
 * 获取日志详情
 * 包含完整的请求头、请求体、响应体、错误信息
 * @param id - 日志 ID
 */
export async function getLogDetail(id: number): Promise<RequestLogDetail> {
  return get<RequestLogDetail>(`${BASE_URL}/${id}`);
}
