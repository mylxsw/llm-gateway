/**
 * 供应商相关 React Query Hooks
 * 提供数据获取、缓存和状态管理
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getProviders,
  getProvider,
  createProvider,
  updateProvider,
  deleteProvider,
} from '@/lib/api';
import {
  Provider,
  ProviderCreate,
  ProviderUpdate,
  ProviderListParams,
} from '@/types';

/** 查询键常量 */
const QUERY_KEYS = {
  all: ['providers'] as const,
  list: (params?: ProviderListParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
};

/**
 * 获取供应商列表 Hook
 * @param params - 查询参数
 */
export function useProviders(params?: ProviderListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => getProviders(params),
  });
}

/**
 * 获取单个供应商详情 Hook
 * @param id - 供应商 ID
 */
export function useProvider(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => getProvider(id),
    enabled: id > 0, // 仅当 id 有效时执行查询
  });
}

/**
 * 创建供应商 Mutation Hook
 */
export function useCreateProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ProviderCreate) => createProvider(data),
    onSuccess: () => {
      // 创建成功后，刷新列表缓存
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
    },
  });
}

/**
 * 更新供应商 Mutation Hook
 */
export function useUpdateProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProviderUpdate }) =>
      updateProvider(id, data),
    onSuccess: (updatedProvider: Provider) => {
      // 更新成功后，刷新列表和详情缓存
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      queryClient.setQueryData(
        QUERY_KEYS.detail(updatedProvider.id),
        updatedProvider
      );
    },
  });
}

/**
 * 删除供应商 Mutation Hook
 */
export function useDeleteProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteProvider(id),
    onSuccess: () => {
      // 删除成功后，刷新列表缓存
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
    },
  });
}
