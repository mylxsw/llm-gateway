/**
 * Log Query Related React Query Hooks
 * Provides data fetching and caching management
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getLogs, getLogDetail, getLogCostStats, retryLog, cancelLog } from '@/lib/api';
import { LogQueryParams } from '@/types';

/** Query Keys */
const QUERY_KEYS = {
  all: ['logs'] as const,
  list: (params?: LogQueryParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
  costStats: (params?: LogQueryParams) => [...QUERY_KEYS.all, 'cost-stats', params] as const,
};

/**
 * Get Log List Hook
 * Supports multi-condition filtering, pagination, sorting
 */
export function useLogs(params?: LogQueryParams) {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => getLogs(params),
    // Log data changes frequently, set shorter cache time
    staleTime: 30 * 1000, // 30 seconds
    // Discover new requests and replace in-progress rows after completion.
    refetchInterval: 2 * 1000,
    refetchIntervalInBackground: false,
  });
}

/**
 * Get Log Detail Hook
 */
export function useLogDetail(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => getLogDetail(id),
    enabled: id > 0,
  });
}

export function useLogCostStats(params?: LogQueryParams) {
  return useQuery({
    queryKey: QUERY_KEYS.costStats(params),
    queryFn: () => getLogCostStats(params),
    staleTime: 30 * 1000,
  });
}

export function useRetryLog() {
  return useMutation({
    mutationFn: (id: number) => retryLog(id),
  });
}

export function useCancelLog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cancelLog(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
    },
  });
}
