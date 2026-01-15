/**
 * Home Cost Stats
 * Shows aggregated cost stats on the home page.
 */

'use client';

import React, { useMemo } from 'react';
import { CostStats } from '@/components/logs';
import { useLogCostStats } from '@/lib/hooks';
import { LogQueryParams } from '@/types';
import { toast } from 'sonner';

const DEFAULT_RANGE_DAYS = 7;

export function HomeCostStats() {
  const params = useMemo<LogQueryParams>(() => {
    const end = new Date();
    const start = new Date(end.getTime() - DEFAULT_RANGE_DAYS * 24 * 60 * 60 * 1000);
    return {
      start_time: start.toISOString(),
      end_time: end.toISOString(),
    };
  }, []);

  const { data, isLoading, isFetching, refetch } = useLogCostStats(params);

  return (
    <CostStats
      stats={data}
      loading={isLoading}
      refreshing={isFetching}
      onRefresh={async () => {
        try {
          await refetch();
          toast.success('Refreshed');
        } catch {
          toast.error('Refresh failed');
        }
      }}
    />
  );
}
