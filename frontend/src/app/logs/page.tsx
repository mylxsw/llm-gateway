/**
 * Request Log Page
 * Provides log list display and multi-condition filtering
 */

'use client';

import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LogFilters, LogList } from '@/components/logs';
import { Pagination, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import { useLogs, useProviders } from '@/lib/hooks';
import { LogQueryParams } from '@/types';

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

  // Execute Search
  const handleSearch = useCallback(() => {
    // Reset page to 1
    setFilters((prev) => ({ ...prev, page: 1 }));
    refetch();
  }, [refetch]);

  // Reset Filters
  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
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
    setFilters((prev) => ({ ...prev, ...newFilters, page: 1 })); // Reset to page 1 on filter change
  }, []);

  // View Log Detail
  const handleViewLog = useCallback((log: any) => {
    // Navigate to log detail page
    window.location.href = `/logs/${log.id}`;
  }, []);

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold">Request Logs</h1>
        <p className="mt-1 text-muted-foreground">
          View proxy request logs, supports multi-condition filtering
        </p>
      </div>

      {/* Filters */}
      <LogFilters
        filters={filters}
        onFilterChange={handleFilterChange}
        providers={providersData?.items || []}
      />

      {/* Data List */}
      <Card>
        <CardHeader>
          <CardTitle>Log List</CardTitle>
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