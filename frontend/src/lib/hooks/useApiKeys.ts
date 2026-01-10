/**
 * API Key 相关 React Query Hooks
 * 提供数据获取、缓存和状态管理
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getApiKeys,
  getApiKey,
  createApiKey,
  updateApiKey,
  deleteApiKey,
} from '@/lib/api';
import {
  ApiKey,
  ApiKeyCreate,
  ApiKeyUpdate,
  ApiKeyListParams,
} from '@/types';

/** 查询键常量 */
const QUERY_KEYS = {
  all: ['api-keys'] as const,
  list: (params?: ApiKeyListParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
};

/**
 * 获取 API Key 列表 Hook
 */
export function useApiKeys(params?: ApiKeyListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => getApiKeys(params),
  });
}

/**
 * 获取单个 API Key 详情 Hook
 */
export function useApiKey(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => getApiKey(id),
    enabled: id > 0,
  });
}

/**
 * 创建 API Key Mutation Hook
 * 注意：创建成功后会返回完整的 key_value（仅此一次）
 */
export function useCreateApiKey() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ApiKeyCreate) => createApiKey(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
    },
  });
}

/**
 * 更新 API Key Mutation Hook
 */
export function useUpdateApiKey() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiKeyUpdate }) =>
      updateApiKey(id, data),
    onSuccess: (updatedKey: ApiKey) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      queryClient.setQueryData(QUERY_KEYS.detail(updatedKey.id), updatedKey);
    },
  });
}

/**
 * 删除 API Key Mutation Hook
 */
export function useDeleteApiKey() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
    },
  });
}
