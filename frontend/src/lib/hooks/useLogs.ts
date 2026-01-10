/**
 * 日志查询相关 React Query Hooks
 * 提供数据获取和缓存管理
 */

import { useQuery } from '@tanstack/react-query';
import { getLogs, getLogDetail } from '@/lib/api';
import { LogQueryParams } from '@/types';

/** 查询键常量 */
const QUERY_KEYS = {
  all: ['logs'] as const,
  list: (params?: LogQueryParams) => [...QUERY_KEYS.all, 'list', params] as const,
  detail: (id: number) => [...QUERY_KEYS.all, 'detail', id] as const,
};

/**
 * 获取日志列表 Hook
 * 支持多条件筛选、分页、排序
 */
export function useLogs(params?: LogQueryParams) {
  return useQuery({
    queryKey: QUERY_KEYS.list(params),
    queryFn: () => getLogs(params),
    // 日志数据变化较快，设置较短的缓存时间
    staleTime: 30 * 1000, // 30秒
  });
}

/**
 * 获取日志详情 Hook
 */
export function useLogDetail(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => getLogDetail(id),
    enabled: id > 0,
  });
}
