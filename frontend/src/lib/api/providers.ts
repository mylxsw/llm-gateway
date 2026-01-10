/**
 * 供应商 API 接口
 * 对应后端 /admin/providers 路由
 */

import { get, post, put, del } from './client';
import {
  Provider,
  ProviderCreate,
  ProviderUpdate,
  ProviderListParams,
  PaginatedResponse,
} from '@/types';

const BASE_URL = '/admin/providers';

/**
 * 获取供应商列表
 * @param params - 查询参数（分页、状态过滤）
 */
export async function getProviders(
  params?: ProviderListParams
): Promise<PaginatedResponse<Provider>> {
  return get<PaginatedResponse<Provider>>(BASE_URL, params as Record<string, unknown>);
}

/**
 * 获取单个供应商详情
 * @param id - 供应商 ID
 */
export async function getProvider(id: number): Promise<Provider> {
  return get<Provider>(`${BASE_URL}/${id}`);
}

/**
 * 创建供应商
 * @param data - 创建数据
 */
export async function createProvider(data: ProviderCreate): Promise<Provider> {
  return post<Provider>(BASE_URL, data);
}

/**
 * 更新供应商
 * @param id - 供应商 ID
 * @param data - 更新数据
 */
export async function updateProvider(
  id: number,
  data: ProviderUpdate
): Promise<Provider> {
  return put<Provider>(`${BASE_URL}/${id}`, data);
}

/**
 * 删除供应商
 * @param id - 供应商 ID
 */
export async function deleteProvider(id: number): Promise<void> {
  return del<void>(`${BASE_URL}/${id}`);
}
