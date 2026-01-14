/**
 * Log Query Related React Query Hooks
 * Provides data fetching and caching management
 */

import { useQuery } from '@tanstack/react-query';
import { getLogs, getLogDetail } from '@/lib/api';
import { LogQueryParams } from '@/types';

/** Query Keys */
const QUERY_KEYS = {
  all: ['logs'] as const,
  list: (params?: LogQueryParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
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