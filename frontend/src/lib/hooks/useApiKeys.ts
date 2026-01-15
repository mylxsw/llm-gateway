/**
 * API Key Related React Query Hooks
 * Provides data fetching, caching and state management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
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

/** Query Keys */
const QUERY_KEYS = {
  all: ['api-keys'] as const,
  list: (params?: ApiKeyListParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
};

/**
 * Get API Key List Hook
 */
export function useApiKeys(params?: ApiKeyListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => getApiKeys(params),
  });
}

/**
 * Get Single API Key Detail Hook
 */
export function useApiKey(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => getApiKey(id),
    enabled: id > 0,
  });
}

/**
 * Create API Key Mutation Hook
 * Note: Returns full key_value on success (only once)
 */
export function useCreateApiKey() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ApiKeyCreate) => createApiKey(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      toast.success('Created successfully');
    },
  });
}

/**
 * Update API Key Mutation Hook
 */
export function useUpdateApiKey() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiKeyUpdate }) =>
      updateApiKey(id, data),
    onSuccess: (updatedKey: ApiKey) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      queryClient.setQueryData(QUERY_KEYS.detail(updatedKey.id), updatedKey);
      toast.success('Saved successfully');
    },
  });
}

/**
 * Delete API Key Mutation Hook
 */
export function useDeleteApiKey() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      toast.success('Deleted successfully');
    },
  });
}
