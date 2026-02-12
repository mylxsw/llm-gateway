/**
 * Log Timeline Component
 * Displays request volume trend with success/error counts and supports range selection.
 */

"use client";

import React, { useCallback, useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/common";
import { LogCostStatsResponse } from "@/types";
import { formatDateTime, formatNumber, normalizeUtcDateString } from "@/lib/utils";
import { RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

const DAY_MS = 24 * 60 * 60 * 1000;
const HOUR_MS = 60 * 60 * 1000;

type BucketUnit = "minute" | "hour" | "day";

type TimelinePoint = {
  label: string;
  success_count: number;
  error_count: number;
  startMs: number;
  endMs: number;
};

interface LogTimelineProps {
  stats?: LogCostStatsResponse;
  loading?: boolean;
  refreshing?: boolean;
  bucket?: BucketUnit;
  bucketMinutes?: number;
  maxBars?: number;
  selectedStart?: string;
  selectedEnd?: string;
  onRangeChange?: (range: { start_time: string; end_time: string } | null) => void;
  onRefresh?: () => void;
  headerActions?: React.ReactNode;
}

function parseBucketToDate(bucket: string) {
  const trimmed = bucket.trim();
  if (!trimmed) return null;
  const normalized = normalizeUtcDateString(trimmed);
  const direct = new Date(normalized);
  if (!Number.isNaN(direct.getTime())) return direct;

  const matchHour = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):00/.exec(trimmed);
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

function formatBucketLabel(date: Date, unit: BucketUnit) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  if (unit === "day") return `${y}-${m}-${d}`;
  const hh = String(date.getHours()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:00`;
}

function formatRangeLabel(start: Date, end: Date, binMs: number) {
  const endInclusive = new Date(end.getTime() - 1);
  const showTime = binMs < DAY_MS;
  const startLabel = formatDateTime(start.toISOString(), {
    showTime,
    showSeconds: false,
  });
  const endLabel = formatDateTime(endInclusive.toISOString(), {
    showTime,
    showSeconds: false,
  });
  if (startLabel === "-" || endLabel === "-") {
    return showTime ? formatBucketLabel(start, "hour") : formatBucketLabel(start, "day");
  }
  if (startLabel === endLabel) return startLabel;
  return `${startLabel} ~ ${endLabel}`;
}

function buildTimelinePoints(
  trend: LogCostStatsResponse["trend"],
  unit: BucketUnit,
  rangeStart?: string,
  rangeEnd?: string,
  barsCount = 60,
  bucketMinutes?: number,
): TimelinePoint[] {
  if (!rangeStart || !rangeEnd) return [];
  const rangeStartMs = new Date(normalizeUtcDateString(rangeStart)).getTime();
  const rangeEndMs = new Date(normalizeUtcDateString(rangeEnd)).getTime();
  if (
    Number.isNaN(rangeStartMs) ||
    Number.isNaN(rangeEndMs) ||
    rangeEndMs <= rangeStartMs
  ) {
    return [];
  }

  const parsed = trend
    .map((p) => {
      const date = parseBucketToDate(String(p.bucket));
      return date
        ? {
            t: date,
            success: Number(p.success_count) || 0,
            error: Number(p.error_count) || 0,
          }
        : null;
    })
    .filter((x): x is { t: Date; success: number; error: number } =>
      Boolean(x),
    )
    .sort((a, b) => a.t.getTime() - b.t.getTime());

  const unitMs =
    unit === "day"
      ? DAY_MS
      : unit === "hour"
        ? HOUR_MS
        : Math.max(1, Math.round((bucketMinutes ?? 1) * 60 * 1000));
  const rangeMs = Math.max(0, rangeEndMs - rangeStartMs);
  const bars = Math.max(1, barsCount);
  const bucketMs = Math.max(1, rangeMs / bars);

  const points: TimelinePoint[] = Array.from({ length: bars }).map((_, idx) => {
    const startMs = rangeStartMs + idx * bucketMs;
    const endMs = Math.min(rangeEndMs, startMs + bucketMs);
    return {
      label: formatRangeLabel(new Date(startMs), new Date(endMs), bucketMs),
      success_count: 0,
      error_count: 0,
      startMs,
      endMs,
    };
  });

  if (parsed.length === 0 || rangeMs <= 0) return points;

  for (const item of parsed) {
    const bucketStart = item.t.getTime();
    const bucketEnd = bucketStart + unitMs;
    const overlapStart = Math.max(bucketStart, rangeStartMs);
    const overlapEnd = Math.min(bucketEnd, rangeEndMs);
    if (overlapEnd <= overlapStart) continue;

    let startIdx = Math.floor((overlapStart - rangeStartMs) / bucketMs);
    let endIdx = Math.floor((overlapEnd - rangeStartMs) / bucketMs);
    startIdx = Math.max(0, Math.min(bars - 1, startIdx));
    endIdx = Math.max(0, Math.min(bars - 1, endIdx));

    for (let idx = startIdx; idx <= endIdx; idx += 1) {
      const segmentStart = rangeStartMs + idx * bucketMs;
      const segmentEnd = segmentStart + bucketMs;
      const segOverlapStart = Math.max(overlapStart, segmentStart);
      const segOverlapEnd = Math.min(overlapEnd, segmentEnd);
      if (segOverlapEnd <= segOverlapStart) continue;
      const ratio = (segOverlapEnd - segOverlapStart) / unitMs;
      const target = points[idx];
      target.success_count += item.success * ratio;
      target.error_count += item.error * ratio;
    }
  }

  return points;
}

function formatLocalRangeLabel(start?: string, end?: string) {
  if (!start || !end) return null;
  const startLabel = formatDateTime(start, { showSeconds: false });
  const endLabel = formatDateTime(end, { showSeconds: false });
  if (startLabel === "-" || endLabel === "-") return null;
  return `${startLabel} ~ ${endLabel}`;
}

export function LogTimeline({
  stats,
  loading,
  refreshing,
  bucket = "day",
  bucketMinutes,
  maxBars = 60,
  selectedStart,
  selectedEnd,
  onRangeChange,
  onRefresh,
  headerActions,
}: LogTimelineProps) {
  const t = useTranslations("logs.timeline");
  const data = useMemo(
    () =>
      buildTimelinePoints(
        stats?.trend ?? [],
        bucket,
        selectedStart,
        selectedEnd,
        maxBars,
        bucketMinutes,
      ),
    [bucket, bucketMinutes, maxBars, selectedEnd, selectedStart, stats?.trend],
  );

  const handleBarClick = useCallback(
    (payload?: TimelinePoint) => {
      if (!payload) return;
      const startIso = new Date(payload.startMs).toISOString();
      const endIso = new Date(Math.max(payload.startMs, payload.endMs - 1)).toISOString();
        onRangeChange?.({ start_time: startIso, end_time: endIso });
    },
    [onRangeChange],
  );

  const rangeLabel = useMemo(
    () => formatLocalRangeLabel(selectedStart, selectedEnd),
    [selectedEnd, selectedStart],
  );

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <CardTitle>{t("title")}</CardTitle>
          <div className="mt-1 text-sm text-muted-foreground">
            {rangeLabel ?? t("hint")}
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {headerActions ? <div className="min-w-0">{headerActions}</div> : null}
          {onRefresh ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8"
              aria-label={t("refresh")}
              onClick={onRefresh}
              disabled={refreshing}
            >
              <RefreshCw
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                suppressHydrationWarning
              />
            </Button>
          ) : null}
          {rangeLabel ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8"
              onClick={() => onRangeChange?.(null)}
            >
              {t("clear")}
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="h-[240px]">
        {loading ? (
          <LoadingSpinner />
        ) : data.length === 0 ? (
          <div className="text-sm text-muted-foreground">{t("empty")}</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="label"
                tick={false}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
                height={8}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                width={36}
                allowDecimals={false}
              />
              <Tooltip
                cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
                content={({ active, payload }) => {
                  if (!active || !payload || payload.length === 0) return null;
                  const point = payload[0]?.payload as TimelinePoint;
                  return (
                    <div className="rounded-md border bg-background p-2 text-xs shadow-md">
                      <div className="font-medium text-foreground">
                        {point.label}
                      </div>
                      <div className="mt-1 flex items-center justify-between gap-3 text-muted-foreground">
                        <span>{t("success")}</span>
                        <span className="font-mono">
                          {formatNumber(Math.round(point.success_count))}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between gap-3 text-muted-foreground">
                        <span>{t("error")}</span>
                        <span className="font-mono">
                          {formatNumber(Math.round(point.error_count))}
                        </span>
                      </div>
                    </div>
                  );
                }}
              />
              <Bar
                dataKey="success_count"
                stackId="total"
                fill="hsl(160 70% 45%)"
                radius={[2, 2, 0, 0]}
                onClick={(entry) => handleBarClick(entry?.payload as TimelinePoint)}
              />
              <Bar
                dataKey="error_count"
                stackId="total"
                fill="hsl(0 75% 55%)"
                radius={[2, 2, 0, 0]}
                onClick={(entry) => handleBarClick(entry?.payload as TimelinePoint)}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
