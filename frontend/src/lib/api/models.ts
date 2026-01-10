/**
 * 模型映射 API 接口
 * 对应后端 /admin/models 和 /admin/model-providers 路由
 */

import { get, post, put, del } from './client';
import {
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  ModelListParams,
  ModelProviderListParams,
  PaginatedResponse,
} from '@/types';

const MODELS_URL = '/admin/models';
const MODEL_PROVIDERS_URL = '/admin/model-providers';

// ============ 模型映射 CRUD ============

/**
 * 获取模型映射列表
 * @param params - 查询参数
 */
export async function getModels(
  params?: ModelListParams
): Promise<PaginatedResponse<ModelMapping>> {
  return get<PaginatedResponse<ModelMapping>>(MODELS_URL, params as Record<string, unknown>);
}

/**
 * 获取单个模型映射详情（含供应商配置）
 * @param requestedModel - 请求模型名
 */
export async function getModel(requestedModel: string): Promise<ModelMapping> {
  return get<ModelMapping>(`${MODELS_URL}/${encodeURIComponent(requestedModel)}`);
}

/**
 * 创建模型映射
 * @param data - 创建数据
 */
export async function createModel(data: ModelMappingCreate): Promise<ModelMapping> {
  return post<ModelMapping>(MODELS_URL, data);
}

/**
 * 更新模型映射
 * @param requestedModel - 请求模型名
 * @param data - 更新数据
 */
export async function updateModel(
  requestedModel: string,
  data: ModelMappingUpdate
): Promise<ModelMapping> {
  return put<ModelMapping>(`${MODELS_URL}/${encodeURIComponent(requestedModel)}`, data);
}

/**
 * 删除模型映射（同时删除关联的供应商配置）
 * @param requestedModel - 请求模型名
 */
export async function deleteModel(requestedModel: string): Promise<void> {
  return del<void>(`${MODELS_URL}/${encodeURIComponent(requestedModel)}`);
}

// ============ 模型-供应商映射 CRUD ============

/**
 * 获取模型-供应商映射列表
 * @param params - 查询参数
 */
export async function getModelProviders(
  params?: ModelProviderListParams
): Promise<{ items: ModelMappingProvider[]; total: number }> {
  return get<{ items: ModelMappingProvider[]; total: number }>(
    MODEL_PROVIDERS_URL,
    params as Record<string, unknown>
  );
}

/**
 * 创建模型-供应商映射
 * @param data - 创建数据
 */
export async function createModelProvider(
  data: ModelMappingProviderCreate
): Promise<ModelMappingProvider> {
  return post<ModelMappingProvider>(MODEL_PROVIDERS_URL, data);
}

/**
 * 更新模型-供应商映射
 * @param id - 映射 ID
 * @param data - 更新数据
 */
export async function updateModelProvider(
  id: number,
  data: ModelMappingProviderUpdate
): Promise<ModelMappingProvider> {
  return put<ModelMappingProvider>(`${MODEL_PROVIDERS_URL}/${id}`, data);
}

/**
 * 删除模型-供应商映射
 * @param id - 映射 ID
 */
export async function deleteModelProvider(id: number): Promise<void> {
  return del<void>(`${MODEL_PROVIDERS_URL}/${id}`);
}
