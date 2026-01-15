/**
 * Cost Stats Component
 * Displays aggregated cost summary and simple charts for the current filter set
 */

'use client';

import React, { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common';
import { LogCostStatsResponse } from '@/types';
import { formatNumber, formatUsd } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';

interface CostStatsProps {
  stats?: LogCostStatsResponse;
  loading?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  headerActions?: React.ReactNode;
  headerExtras?: React.ReactNode;
}

export function CostStats({
  stats,
  loading,
  onRefresh,
  refreshing,
  headerActions,
  headerExtras,
}: CostStatsProps) {
  const trendMax = useMemo(() => {
    const values = stats?.trend?.map((p) => Number(p.total_cost) || 0) ?? [];
    return Math.max(0, ...values);
  }, [stats?.trend]);

  const modelMax = useMemo(() => {
    const values = stats?.by_model?.map((p) => Number(p.total_cost) || 0) ?? [];
    return Math.max(0, ...values);
  }, [stats?.by_model]);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <CardTitle className="shrink-0">Activity</CardTitle>

        {onRefresh || headerActions || headerExtras ? (
          <div className="ml-auto flex w-full flex-col items-end gap-2 sm:w-auto">
            <div className="flex items-center justify-end gap-2">
              {onRefresh ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8"
                  aria-label="刷新"
                  onClick={onRefresh}
                  disabled={refreshing}
                >
                  <RefreshCw
                    className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
                    suppressHydrationWarning
                  />
                  <span className="ml-2">刷新</span>
                </Button>
              ) : null}

              {headerActions ? <div className="min-w-0">{headerActions}</div> : null}
            </div>

            {headerExtras ? <div className="w-full sm:w-auto">{headerExtras}</div> : null}
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <LoadingSpinner />}
        {!loading && !stats && (
          <div className="text-sm text-muted-foreground">No stats available</div>
        )}

        {!loading && stats && (
          <>
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-muted-foreground">Total</div>
                <div className="mt-1 font-mono font-medium">{formatUsd(stats.summary.total_cost)}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-muted-foreground">Input</div>
                <div className="mt-1 font-mono font-medium">{formatUsd(stats.summary.input_cost)}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-muted-foreground">Output</div>
                <div className="mt-1 font-mono font-medium">{formatUsd(stats.summary.output_cost)}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-muted-foreground">Requests</div>
                <div className="mt-1 font-mono font-medium">{formatNumber(stats.summary.request_count)}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-muted-foreground">In Tokens</div>
                <div className="mt-1 font-mono font-medium">{formatNumber(stats.summary.input_tokens)}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-muted-foreground">Out Tokens</div>
                <div className="mt-1 font-mono font-medium">{formatNumber(stats.summary.output_tokens)}</div>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border bg-muted/10 p-3">
                <div className="mb-2 text-sm font-medium">Cost Trend</div>
                <div className="flex items-end gap-1 overflow-x-auto pb-1">
                  {stats.trend.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No data</div>
                  ) : (
                    stats.trend.map((p) => {
                      const heightPct =
                        trendMax > 0 ? Math.max(2, Math.round((p.total_cost / trendMax) * 100)) : 0;
                      return (
                        <div key={p.bucket} className="flex flex-col items-center gap-1">
                          <div
                            className="w-3 rounded-sm bg-primary/70"
                            style={{ height: `${heightPct}%`, minHeight: 4, maxHeight: 96 }}
                            title={`${p.bucket}\n${formatUsd(p.total_cost)}\nRequests: ${p.request_count}`}
                          />
                          <div className="max-w-[64px] truncate text-[10px] text-muted-foreground" title={p.bucket}>
                            {p.bucket}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              <div className="rounded-lg border bg-muted/10 p-3">
                <div className="mb-2 text-sm font-medium">By Model (Top 10)</div>
                <div className="space-y-2">
                  {stats.by_model.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No data</div>
                  ) : (
                    stats.by_model.slice(0, 10).map((m) => {
                      const widthPct =
                        modelMax > 0 ? Math.max(2, Math.round((m.total_cost / modelMax) * 100)) : 0;
                      return (
                        <div key={m.requested_model} className="space-y-1">
                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="truncate" title={m.requested_model}>
                              {m.requested_model || '-'}
                            </span>
                            <span className="shrink-0 font-mono text-xs">{formatUsd(m.total_cost)}</span>
                          </div>
                          <div className="h-2 w-full rounded bg-muted">
                            <div className="h-2 rounded bg-primary/70" style={{ width: `${widthPct}%` }} />
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
