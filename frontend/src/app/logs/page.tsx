/**
 * Request Log Page
 * Provides log list display and multi-condition filtering
 */

'use client';

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LogFilters, LogList } from '@/components/logs';
import { Pagination, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import { useApiKeys, useLogs, useModels, useProviders } from '@/lib/hooks';
import { LogQueryParams, RequestLog } from '@/types';
import { RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

/** Default Filter Parameters */
const DEFAULT_FILTERS: LogQueryParams = {
  page: 1,
  page_size: 20,
  sort_by: 'request_time',
  sort_order: 'desc',
};

/**
 * Request Log Page Component
 */
export default function LogsPage() {
  // Filter parameters state
  const [filters, setFilters] = useState<LogQueryParams>(DEFAULT_FILTERS);

  // Data query
  const { data, isLoading, isError, refetch } = useLogs(filters);
  const { data: providersData } = useProviders({ is_active: true });
  const { data: modelsData } = useModels({ is_active: true, page: 1, page_size: 1000 });
  const { data: apiKeysData } = useApiKeys({ is_active: true, page: 1, page_size: 1000 });

  const areLogQueryParamsEqual = useCallback((a: LogQueryParams, b: LogQueryParams) => {
    const keys: Array<keyof LogQueryParams> = [
      'start_time',
      'end_time',
      'requested_model',
      'target_model',
      'provider_id',
      'status_min',
      'status_max',
      'has_error',
      'api_key_id',
      'api_key_name',
      'retry_count_min',
      'retry_count_max',
      'input_tokens_min',
      'input_tokens_max',
      'total_time_min',
      'total_time_max',
      'page',
      'page_size',
      'sort_by',
      'sort_order',
    ];

    return keys.every((key) => Object.is(a[key], b[key]));
  }, []);

  // Page Change
  const handlePageChange = useCallback((page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  }, []);

  // Page Size Change
  const handlePageSizeChange = useCallback((pageSize: number) => {
    setFilters((prev) => ({ ...prev, page_size: pageSize, page: 1 }));
  }, []);

  // Handle filter change from LogFilters component
  const handleFilterChange = useCallback((newFilters: Partial<LogQueryParams>) => {
    setFilters((prev) => {
      const next = { ...prev, ...newFilters, page: 1 };
      if (areLogQueryParamsEqual(prev, next)) {
        void refetch();
        return prev;
      }
      return next;
    }); // Reset to page 1 on filter change
  }, [areLogQueryParamsEqual, refetch]);

  // View Log Detail
  const handleViewLog = useCallback((log: RequestLog) => {
    window.location.href = `/logs/detail?id=${encodeURIComponent(String(log.id))}`;
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold">Logs</h1>
        <p className="mt-1 text-muted-foreground">
          View proxy request logs, supports multi-condition filtering
        </p>
      </div>

      {/* Filters */}
      <LogFilters
        filters={filters}
        onFilterChange={handleFilterChange}
        providers={providersData?.items || []}
        models={modelsData?.items || []}
        apiKeys={apiKeysData?.items || []}
      />

      {/* Data List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Log List</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8"
            aria-label="Refresh"
            onClick={async () => {
              try {
                await refetch();
                toast.success('Refreshed');
              } catch {
                toast.error('Refresh failed');
              }
            }}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`}
              suppressHydrationWarning
            />
          </Button>
          
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="Failed to load log list"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState message="No matching log records found" />
          )}
          
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <LogList logs={data.items} onView={handleViewLog} />
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
