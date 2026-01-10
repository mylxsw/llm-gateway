/**
 * API Key API 接口
 * 对应后端 /admin/api-keys 路由
 */

import { get, post, put, del } from './client';
import {
  ApiKey,
  ApiKeyCreate,
  ApiKeyUpdate,
  ApiKeyListParams,
  PaginatedResponse,
} from '@/types';

const BASE_URL = '/admin/api-keys';

/**
 * 获取 API Key 列表
 * @param params - 查询参数（分页、状态过滤）
 */
export async function getApiKeys(
  params?: ApiKeyListParams
): Promise<PaginatedResponse<ApiKey>> {
  return get<PaginatedResponse<ApiKey>>(BASE_URL, params as Record<string, unknown>);
}

/**
 * 获取单个 API Key 详情
 * @param id - API Key ID
 */
export async function getApiKey(id: number): Promise<ApiKey> {
  return get<ApiKey>(`${BASE_URL}/${id}`);
}

/**
 * 创建 API Key（key_value 由后端生成）
 * @param data - 创建数据（仅需 key_name）
 * @returns 完整的 API Key（包含完整的 key_value，仅此一次）
 */
export async function createApiKey(data: ApiKeyCreate): Promise<ApiKey> {
  return post<ApiKey>(BASE_URL, data);
}

/**
 * 更新 API Key
 * @param id - API Key ID
 * @param data - 更新数据（key_name、is_active）
 */
export async function updateApiKey(
  id: number,
  data: ApiKeyUpdate
): Promise<ApiKey> {
  return put<ApiKey>(`${BASE_URL}/${id}`, data);
}

/**
 * 删除 API Key
 * @param id - API Key ID
 */
export async function deleteApiKey(id: number): Promise<void> {
  return del<void>(`${BASE_URL}/${id}`);
}
