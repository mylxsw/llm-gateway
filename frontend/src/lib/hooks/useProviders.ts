/**
 * Provider Related React Query Hooks
 * Provides data fetching, caching and state management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  getProviders,
  getProvider,
  createProvider,
  updateProvider,
  deleteProvider,
} from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api/error';
import {
  Provider,
  ProviderCreate,
  ProviderUpdate,
  ProviderListParams,
} from '@/types';

/** Query Keys */
const QUERY_KEYS = {
  all: ['providers'] as const,
  list: (params?: ProviderListParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
};

/**
 * Get Provider List Hook
 * @param params - Query parameters
 */
export function useProviders(params?: ProviderListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => getProviders(params),
  });
}

/**
 * Get Single Provider Detail Hook
 * @param id - Provider ID
 */
export function useProvider(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => getProvider(id),
    enabled: id > 0, // Only query when ID is valid
  });
}

/**
 * Create Provider Mutation Hook
 */
export function useCreateProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ProviderCreate) => createProvider(data),
    onSuccess: () => {
      // Refresh list cache on success
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      toast.success('Created successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Create failed'));
    },
  });
}

/**
 * Update Provider Mutation Hook
 */
export function useUpdateProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ProviderUpdate }) =>
      updateProvider(id, data),
    onSuccess: (updatedProvider: Provider) => {
      // Refresh list and detail cache on success
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      queryClient.setQueryData(
        QUERY_KEYS.detail(updatedProvider.id),
        updatedProvider
      );
      toast.success('Saved successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Save failed'));
    },
  });
}

/**
 * Delete Provider Mutation Hook
 */
export function useDeleteProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteProvider(id),
    onSuccess: () => {
      // Refresh list cache on success
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      toast.success('Deleted successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Delete failed'));
    },
  });
}
