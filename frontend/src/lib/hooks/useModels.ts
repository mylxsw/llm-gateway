/**
 * 模型映射相关 React Query Hooks
 * 提供数据获取、缓存和状态管理
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getModels,
  getModel,
  createModel,
  updateModel,
  deleteModel,
  getModelProviders,
  createModelProvider,
  updateModelProvider,
  deleteModelProvider,
} from '@/lib/api';
import {
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  ModelListParams,
  ModelProviderListParams,
} from '@/types';

/** 查询键常量 */
const QUERY_KEYS = {
  models: ['models'] as const,
  modelList: (params?: ModelListParams) => [...QUERY_KEYS.models, 'list', params] as const,
  modelDetail: (requestedModel: string) => [...QUERY_KEYS.models, 'detail', requestedModel] as const,
  modelProviders: ['model-providers'] as const,
  modelProviderList: (params?: ModelProviderListParams) =>
    [...QUERY_KEYS.modelProviders, 'list', params] as const,
};

// ============ 模型映射 Hooks ============

/**
 * 获取模型映射列表 Hook
 */
export function useModels(params?: ModelListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.modelList(params),
    queryFn: () => getModels(params),
  });
}

/**
 * 获取单个模型映射详情 Hook（含供应商配置）
 */
export function useModel(requestedModel: string) {
  return useQuery({
    queryKey: QUERY_KEYS.modelDetail(requestedModel),
    queryFn: () => getModel(requestedModel),
    enabled: !!requestedModel, // 仅当 requestedModel 有效时执行
  });
}

/**
 * 创建模型映射 Mutation Hook
 */
export function useCreateModel() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ModelMappingCreate) => createModel(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
    },
  });
}

/**
 * 更新模型映射 Mutation Hook
 */
export function useUpdateModel() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({
      requestedModel,
      data,
    }: {
      requestedModel: string;
      data: ModelMappingUpdate;
    }) => updateModel(requestedModel, data),
    onSuccess: (_: ModelMapping, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.modelDetail(variables.requestedModel),
      });
    },
  });
}

/**
 * 删除模型映射 Mutation Hook
 */
export function useDeleteModel() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (requestedModel: string) => deleteModel(requestedModel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
    },
  });
}

// ============ 模型-供应商映射 Hooks ============

/**
 * 获取模型-供应商映射列表 Hook
 */
export function useModelProviders(params?: ModelProviderListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.modelProviderList(params),
    queryFn: () => getModelProviders(params),
  });
}

/**
 * 创建模型-供应商映射 Mutation Hook
 */
export function useCreateModelProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ModelMappingProviderCreate) => createModelProvider(data),
    onSuccess: (_: ModelMappingProvider, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.modelProviders });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      // 刷新对应模型的详情
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.modelDetail(variables.requested_model),
      });
    },
  });
}

/**
 * 更新模型-供应商映射 Mutation Hook
 */
export function useUpdateModelProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: ModelMappingProviderUpdate;
    }) => updateModelProvider(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.modelProviders });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
    },
  });
}

/**
 * 删除模型-供应商映射 Mutation Hook
 */
export function useDeleteModelProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteModelProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.modelProviders });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
    },
  });
}
