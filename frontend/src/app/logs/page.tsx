/**
 * 请求日志页面
 * 提供日志列表展示和多条件筛选查询
 */

'use client';

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LogFilters, LogList } from '@/components/logs';
import { Pagination, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import { useLogs, useProviders } from '@/lib/hooks';
import { LogQueryParams } from '@/types';

/** 默认筛选参数 */
const DEFAULT_FILTERS: LogQueryParams = {
  page: 1,
  page_size: 20,
  sort_by: 'request_time',
  sort_order: 'desc',
};

/**
 * 请求日志页面组件
 */
export default function LogsPage() {
  // 筛选参数状态
  const [filters, setFilters] = useState<LogQueryParams>(DEFAULT_FILTERS);

  // 数据查询
  const { data, isLoading, isError, refetch } = useLogs(filters);
  const { data: providersData } = useProviders({ is_active: true });

  // 执行搜索
  const handleSearch = useCallback(() => {
    // 重置页码到第一页
    setFilters((prev) => ({ ...prev, page: 1 }));
    refetch();
  }, [refetch]);

  // 重置筛选条件
  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  // 页码改变
  const handlePageChange = useCallback((page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  }, []);

  // 每页数量改变
  const handlePageSizeChange = useCallback((pageSize: number) => {
    setFilters((prev) => ({ ...prev, page_size: pageSize, page: 1 }));
  }, []);

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold">请求日志</h1>
        <p className="mt-1 text-muted-foreground">
          查看代理请求日志，支持多条件筛选查询
        </p>
      </div>

      {/* 筛选器 */}
      <LogFilters
        filters={filters}
        onFiltersChange={setFilters}
        providers={providersData?.items || []}
        onSearch={handleSearch}
        onReset={handleReset}
      />

      {/* 数据列表 */}
      <Card>
        <CardHeader>
          <CardTitle>日志列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="加载日志列表失败"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState message="暂无符合条件的日志记录" />
          )}
          
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <LogList logs={data.items} />
              <Pagination
                page={filters.page || 1}
                pageSize={filters.page_size || 20}
                total={data.total}
                onPageChange={handlePageChange}
                onPageSizeChange={handlePageSizeChange}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
