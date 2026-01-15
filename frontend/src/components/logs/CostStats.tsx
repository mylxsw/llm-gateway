/**
 * Cost Stats Component
 * Displays aggregated cost summary and simple charts for the current filter set
 */

'use client';

import React, { useEffect, useMemo, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingSpinner } from '@/components/common';
import { LogCostStatsResponse } from '@/types';
import { formatNumber, formatUsd } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { Maximize2, RefreshCw } from 'lucide-react';

interface CostStatsProps {
  stats?: LogCostStatsResponse;
  loading?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  headerActions?: React.ReactNode;
  headerExtras?: React.ReactNode;
  rangeLabel?: string;
  rangeDays?: number;
  rangeStart?: string;
  rangeEnd?: string;
  bucket?: 'hour' | 'day';
  maxBars?: number;
}

type Segment = {
  label: string;
  colorClassName: string;
  getValue: (p: LogCostStatsResponse['trend'][number]) => number;
  formatValue: (v: number) => string;
};

const DAY_MS = 24 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

function formatCompactNumber(value: number) {
  if (!Number.isFinite(value)) return '0';
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(Math.round(value));
}

function parseBucketToLocalDate(bucket: string) {
  const trimmed = bucket.trim();
  const matchHour = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):00$/.exec(trimmed);
  if (matchHour) {
    const year = Number(matchHour[1]);
    const month = Number(matchHour[2]);
    const day = Number(matchHour[3]);
    const hour = Number(matchHour[4]);
    return new Date(year, month - 1, day, hour, 0, 0, 0);
  }

  const matchDay = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (matchDay) {
    const year = Number(matchDay[1]);
    const month = Number(matchDay[2]);
    const day = Number(matchDay[3]);
    return new Date(year, month - 1, day, 0, 0, 0, 0);
  }

  return null;
}

function formatBucketLabel(date: Date, unit: 'hour' | 'day') {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  if (unit === 'day') return `${y}-${m}-${d}`;
  const hh = String(date.getHours()).padStart(2, '0');
  return `${y}-${m}-${d} ${hh}:00`;
}

function formatBucketRangeLabel(start: Date, end: Date, unit: 'hour' | 'day', step: number) {
  if (unit === 'day' && step === 1) return formatBucketLabel(start, 'day');
  if (unit === 'hour' && step === 1) return formatBucketLabel(start, 'hour');
  const endInclusive = new Date(end.getTime() - 1);
  return `${formatBucketLabel(start, unit)} ~ ${formatBucketLabel(endInclusive, unit)}`;
}

function floorToUnit(date: Date, unit: 'hour' | 'day') {
  const d = new Date(date);
  if (unit === 'day') d.setHours(0, 0, 0, 0);
  else d.setMinutes(0, 0, 0);
  return d;
}

function ceilToUnitExclusive(date: Date, unit: 'hour' | 'day') {
  const floored = floorToUnit(date, unit);
  if (floored.getTime() === date.getTime()) return floored;
  const bumped = new Date(floored);
  bumped.setTime(bumped.getTime() + (unit === 'day' ? DAY_MS : HOUR_MS));
  return bumped;
}

function computeStep(rangeMs: number, unit: 'hour' | 'day', maxBars: number) {
  const unitMs = unit === 'day' ? DAY_MS : HOUR_MS;
  const raw = rangeMs / Math.max(1, maxBars) / unitMs;
  return Math.max(1, Math.ceil(raw));
}

function stepLabel(unit: 'hour' | 'day', step: number) {
  if (unit === 'day') return step === 1 ? 'Day' : `${step}d`;
  return step === 1 ? 'Hour' : `${step}h`;
}

function TrendCard({
  title,
  href,
  points,
  segments,
  avgLabel,
  avgValue,
  totalLabel,
  totalValue,
}: {
  title: string;
  href?: string;
  points: LogCostStatsResponse['trend'];
  segments: Segment[];
  avgLabel: string;
  avgValue: string;
  totalLabel: string;
  totalValue: string;
}) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const maxTotal = useMemo(() => {
    const totals = points.map((p) =>
      segments.reduce((acc, seg) => acc + (Number(seg.getValue(p)) || 0), 0)
    );
    return Math.max(0, ...totals);
  }, [points, segments]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;

    const raf = requestAnimationFrame(() => {
      el.scrollLeft = el.scrollWidth;
    });
    return () => cancelAnimationFrame(raf);
  }, [points]);

  return (
    <div className="group relative overflow-hidden rounded-2xl border bg-gradient-to-b from-muted/10 to-background p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-foreground">{title}</div>
        </div>
        {href ? (
          <Link
            href={href}
            className="rounded-md p-1 text-muted-foreground opacity-80 transition hover:bg-muted/20 hover:text-foreground group-hover:opacity-100"
            aria-label={`Open ${title}`}
          >
            <Maximize2 className="h-4 w-4" suppressHydrationWarning />
          </Link>
        ) : null}
      </div>

      <div ref={scrollerRef} className="flex items-end gap-1 overflow-x-auto pb-2">
        {points.length === 0 ? (
          <div className="text-sm text-muted-foreground">No data</div>
        ) : (
          points.map((p) => {
            const rawValues = segments.map((seg) => Math.max(0, Number(seg.getValue(p)) || 0));
            const total = rawValues.reduce((acc, v) => acc + v, 0);
            const normalizedMax = maxTotal > 0 ? maxTotal : 1;
            const totalHeight = Math.max(
              2,
              Math.round((Math.min(total, normalizedMax) / normalizedMax) * 96)
            );

            const toolLines = [
              p.bucket,
              ...segments.map((seg, idx) => `${seg.label}: ${seg.formatValue(rawValues[idx] ?? 0)}`),
            ];

            return (
              <div key={p.bucket} className="flex flex-col items-center gap-1">
                <div
                  className="flex w-3 flex-col justify-end overflow-hidden rounded-sm bg-muted/15"
                  style={{ height: 96 }}
                  title={toolLines.join('\n')}
                >
                  {total > 0 ? (
                    <div className="flex flex-col-reverse" style={{ height: totalHeight }}>
                      {segments.map((seg, idx) => {
                        const segValue = rawValues[idx] ?? 0;
                        const height =
                          total > 0 ? Math.max(1, Math.round((segValue / total) * totalHeight)) : 0;
                        return (
                          <div
                            key={seg.label}
                            className={seg.colorClassName}
                            style={{ height }}
                          />
                        );
                      })}
                    </div>
                  ) : (
                    <div className="h-px w-full bg-muted-foreground/30" />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="mt-1 flex items-end justify-between gap-6">
        <div className="min-w-0">
          <div className="text-xs text-muted-foreground">{avgLabel}</div>
          <div className="mt-1 font-mono text-sm font-medium">{avgValue}</div>
        </div>
        <div className="min-w-0 text-right">
          <div className="text-xs text-muted-foreground">{totalLabel}</div>
          <div className="mt-1 font-mono text-sm font-medium">{totalValue}</div>
        </div>
      </div>
    </div>
  );
}

export function CostStats({
  stats,
  loading,
  onRefresh,
  refreshing,
  headerActions,
  headerExtras,
  rangeLabel = 'Selected Range',
  rangeDays = 1,
  rangeStart,
  rangeEnd,
  bucket = 'day',
  maxBars = 30,
}: CostStatsProps) {
  const modelMax = useMemo(() => {
    const values = stats?.by_model?.map((p) => Number(p.total_cost) || 0) ?? [];
    return Math.max(0, ...values);
  }, [stats?.by_model]);

  const safeRangeDays = Math.max(1, Math.round(rangeDays));

  const computedTrend = useMemo(() => {
    if (!stats) return [];
    if (!rangeStart || !rangeEnd) return stats.trend;

    const startLocal = new Date(rangeStart);
    const endLocal = new Date(rangeEnd);
    if (Number.isNaN(startLocal.getTime()) || Number.isNaN(endLocal.getTime())) return stats.trend;

    const alignedStart = floorToUnit(startLocal, bucket);
    const alignedEnd = ceilToUnitExclusive(endLocal, bucket);
    const alignedRangeMs = Math.max(0, alignedEnd.getTime() - alignedStart.getTime());
    if (alignedRangeMs <= 0) return stats.trend;

    const step = computeStep(alignedRangeMs, bucket, maxBars);
    const unitMs = bucket === 'day' ? DAY_MS : HOUR_MS;
    const bucketMs = step * unitMs;
    const bars = Math.max(1, Math.ceil(alignedRangeMs / bucketMs));

    const emptyPoints: LogCostStatsResponse['trend'] = Array.from({ length: bars }).map((_, idx) => {
      const bucketStart = new Date(alignedStart.getTime() + idx * bucketMs);
      const bucketEnd = new Date(Math.min(alignedEnd.getTime(), bucketStart.getTime() + bucketMs));
      return {
        bucket: formatBucketRangeLabel(bucketStart, bucketEnd, bucket, step),
        request_count: 0,
        total_cost: 0,
        input_cost: 0,
        output_cost: 0,
        input_tokens: 0,
        output_tokens: 0,
        error_count: 0,
        success_count: 0,
      };
    });

    const parsed = stats.trend
      .map((p) => {
        const t = parseBucketToLocalDate(p.bucket);
        return t ? { t, p } : null;
      })
      .filter((x): x is { t: Date; p: LogCostStatsResponse['trend'][number] } => Boolean(x));

    for (const { t, p } of parsed) {
      const offsetMs = t.getTime() - alignedStart.getTime();
      if (offsetMs < 0 || offsetMs >= alignedRangeMs) continue;
      const idx = Math.min(bars - 1, Math.floor(offsetMs / bucketMs));
      const target = emptyPoints[idx];
      target.request_count += Number(p.request_count) || 0;
      target.total_cost += Number(p.total_cost) || 0;
      target.input_cost += Number(p.input_cost) || 0;
      target.output_cost += Number(p.output_cost) || 0;
      target.input_tokens += Number(p.input_tokens) || 0;
      target.output_tokens += Number(p.output_tokens) || 0;
      target.error_count += Number(p.error_count) || 0;
      target.success_count += Number(p.success_count) || 0;
    }

    return emptyPoints;
  }, [stats, rangeStart, rangeEnd, bucket, maxBars]);

  const avgTrendLabel = useMemo(() => {
    if (!rangeStart || !rangeEnd) return 'Avg Day';
    const startLocal = new Date(rangeStart);
    const endLocal = new Date(rangeEnd);
    if (Number.isNaN(startLocal.getTime()) || Number.isNaN(endLocal.getTime())) return 'Avg Day';
    const alignedStart = floorToUnit(startLocal, bucket);
    const alignedEnd = ceilToUnitExclusive(endLocal, bucket);
    const alignedRangeMs = Math.max(0, alignedEnd.getTime() - alignedStart.getTime());
    const step = computeStep(alignedRangeMs, bucket, maxBars);
    return `Avg ${stepLabel(bucket, step)}`;
  }, [rangeStart, rangeEnd, bucket, maxBars]);

  const spendSegments = useMemo<Segment[]>(
    () => [
      {
        label: 'Input',
        colorClassName: 'bg-sky-500/80',
        getValue: (p) => p.input_cost,
        formatValue: (v) => formatUsd(v),
      },
      {
        label: 'Output',
        colorClassName: 'bg-emerald-400/80',
        getValue: (p) => p.output_cost,
        formatValue: (v) => formatUsd(v),
      },
    ],
    []
  );

  const tokenSegments = useMemo<Segment[]>(
    () => [
      {
        label: 'Input',
        colorClassName: 'bg-indigo-500/80',
        getValue: (p) => p.input_tokens,
        formatValue: (v) => formatCompactNumber(v),
      },
      {
        label: 'Output',
        colorClassName: 'bg-cyan-400/80',
        getValue: (p) => p.output_tokens,
        formatValue: (v) => formatCompactNumber(v),
      },
    ],
    []
  );

  const requestSegments = useMemo<Segment[]>(
    () => [
      {
        label: 'Success',
        colorClassName: 'bg-teal-400/80',
        getValue: (p) => p.success_count,
        formatValue: (v) => formatNumber(v),
      },
      {
        label: 'Error',
        colorClassName: 'bg-rose-500/80',
        getValue: (p) => p.error_count,
        formatValue: (v) => formatNumber(v),
      },
    ],
    []
  );

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
                  aria-label="Refresh"
                  onClick={onRefresh}
                  disabled={refreshing}
                >
                  <RefreshCw
                    className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`}
                    suppressHydrationWarning
                  />
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
            <div className="grid gap-4 lg:grid-cols-3">
              <TrendCard
                title="Spend"
                href="/logs"
                points={computedTrend}
                segments={spendSegments}
                avgLabel={avgTrendLabel}
                avgValue={
                  computedTrend.length > 0
                    ? formatUsd(stats.summary.total_cost / computedTrend.length)
                    : formatUsd(stats.summary.total_cost / safeRangeDays)
                }
                totalLabel={rangeLabel}
                totalValue={formatUsd(stats.summary.total_cost)}
              />

              <TrendCard
                title="Tokens"
                href="/logs"
                points={computedTrend}
                segments={tokenSegments}
                avgLabel={avgTrendLabel}
                avgValue={
                  computedTrend.length > 0
                    ? formatCompactNumber(
                        (stats.summary.input_tokens + stats.summary.output_tokens) / computedTrend.length
                      )
                    : formatCompactNumber(
                        (stats.summary.input_tokens + stats.summary.output_tokens) / safeRangeDays
                      )
                }
                totalLabel={rangeLabel}
                totalValue={formatCompactNumber(stats.summary.input_tokens + stats.summary.output_tokens)}
              />

              <TrendCard
                title="Requests"
                href="/logs"
                points={computedTrend}
                segments={requestSegments}
                avgLabel={avgTrendLabel}
                avgValue={
                  computedTrend.length > 0
                    ? formatNumber(stats.summary.request_count / computedTrend.length)
                    : formatNumber(stats.summary.request_count / safeRangeDays)
                }
                totalLabel={rangeLabel}
                totalValue={formatNumber(stats.summary.request_count)}
              />
            </div>

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

            <div className="grid gap-4">
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
