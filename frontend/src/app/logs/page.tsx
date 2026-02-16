/**
 * Request Log Page
 * Provides log list display and multi-condition filtering
 */

'use client';

import React, { useState, useCallback, useEffect, useMemo, Suspense } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LogFilters, LogList, LogTimeline } from '@/components/logs';
import { Pagination, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import { useApiKeys, useLogs, useLogCostStats, useModels, useProviders } from '@/lib/hooks';
import { LogQueryParams, RequestLog } from '@/types';
import { RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslations } from 'next-intl';
import { useRouter, useSearchParams } from 'next/navigation';
import { parseBooleanParam, parseNumberParam, parseStringParam, setParam } from '@/lib/utils';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

/** Default Filter Parameters */
const DEFAULT_FILTERS: LogQueryParams = {
  page: 1,
  page_size: 20,
  sort_by: 'request_time',
  sort_order: 'desc',
};

const DAY_MS = 24 * 60 * 60 * 1000;

function resolveBucket(
  start?: string,
  end?: string,
  bars = 60
): { bucket: 'minute' | 'hour' | 'day'; bucketMinutes?: number } {
  if (!start || !end) return { bucket: 'hour' };
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs <= startMs) {
    return { bucket: 'hour' };
  }
  const rangeMs = endMs - startMs;
  if (rangeMs <= 7 * DAY_MS) {
    return { bucket: 'minute', bucketMinutes: 1 };
  }
  const binMs = rangeMs / Math.max(1, bars);
  if (binMs < DAY_MS) return { bucket: 'hour' };
  return { bucket: 'day' };
}

type TimelinePreset = 'custom' | '1h' | '3h' | '6h' | '12h' | '24h' | '1w';

const TIMELINE_PRESETS: Array<{ value: TimelinePreset; minutes?: number }> = [
  { value: 'custom' },
  { value: '1h', minutes: 60 },
  { value: '3h', minutes: 180 },
  { value: '6h', minutes: 360 },
  { value: '12h', minutes: 720 },
  { value: '24h', minutes: 1440 },
  { value: '1w', minutes: 10080 },
];

/**
 * Request Log Page Component
 */
export default function LogsPage() {
  return (
    <Suspense fallback={null}>
      <LogsContent />
    </Suspense>
  );
}

function LogsContent() {
  const t = useTranslations('logs');
  const tTimeline = useTranslations('logs.timeline');
  const router = useRouter();
  const searchParams = useSearchParams();
  const buildFiltersFromParams = useCallback((): LogQueryParams => {
    const parsed: LogQueryParams = {
      page: parseNumberParam(searchParams.get('page'), { min: 1 }) ?? DEFAULT_FILTERS.page,
      page_size:
        parseNumberParam(searchParams.get('page_size'), { min: 1 }) ?? DEFAULT_FILTERS.page_size,
      sort_by: parseStringParam(searchParams.get('sort_by')) ?? DEFAULT_FILTERS.sort_by,
      sort_order:
        (parseStringParam(searchParams.get('sort_order')) as LogQueryParams['sort_order']) ??
        DEFAULT_FILTERS.sort_order,
      start_time: parseStringParam(searchParams.get('start_time')),
      end_time: parseStringParam(searchParams.get('end_time')),
      requested_model: parseStringParam(searchParams.get('requested_model')),
      target_model: parseStringParam(searchParams.get('target_model')),
      provider_id: parseNumberParam(searchParams.get('provider_id'), { min: 1 }),
      status_min: parseNumberParam(searchParams.get('status_min')),
      status_max: parseNumberParam(searchParams.get('status_max')),
      has_error: parseBooleanParam(searchParams.get('has_error')),
      api_key_id: parseNumberParam(searchParams.get('api_key_id'), { min: 1 }),
      api_key_name: parseStringParam(searchParams.get('api_key_name')),
      retry_count_min: parseNumberParam(searchParams.get('retry_count_min')),
      retry_count_max: parseNumberParam(searchParams.get('retry_count_max')),
      input_tokens_min: parseNumberParam(searchParams.get('input_tokens_min')),
      input_tokens_max: parseNumberParam(searchParams.get('input_tokens_max')),
      total_time_min: parseNumberParam(searchParams.get('total_time_min')),
      total_time_max: parseNumberParam(searchParams.get('total_time_max')),
    };

    return parsed;
  }, [searchParams]);

  // Filter parameters state
  const [filters, setFilters] = useState<LogQueryParams>(() => buildFiltersFromParams());

  // Initialize timeline preset from URL or default to '24h'
  const [timelinePreset, setTimelinePreset] = useState<TimelinePreset>(() => {
    const urlPreset = parseStringParam(searchParams.get('preset')) as TimelinePreset | undefined;
    if (urlPreset && TIMELINE_PRESETS.some((p) => p.value === urlPreset)) return urlPreset;
    // If URL has explicit time params, it's custom; otherwise default to 24h
    if (parseStringParam(searchParams.get('start_time')) || parseStringParam(searchParams.get('end_time'))) {
      return 'custom';
    }
    return '24h';
  });

  // Build the resolved filter params: inject timeline when using presets (server handles time calc)
  const resolvedFilters = useMemo<LogQueryParams>(() => {
    if (filters.start_time || filters.end_time) {
      return filters;
    }
    if (timelinePreset !== 'custom') {
      return { ...filters, timeline: timelinePreset as LogQueryParams['timeline'] };
    }
    return filters;
  }, [filters, timelinePreset]);

  // Display-only time range for LogTimeline chart rendering.
  // In preset mode, filters have no start/end but the chart needs concrete
  // boundaries to lay out bars. This does NOT affect API queries.
  const displayTimeRange = useMemo(() => {
    if (filters.start_time && filters.end_time) {
      return { start: filters.start_time, end: filters.end_time };
    }
    if (timelinePreset !== 'custom') {
      const match = TIMELINE_PRESETS.find((p) => p.value === timelinePreset);
      const minutes = match?.minutes ?? 1440;
      const now = new Date();
      return {
        start: new Date(now.getTime() - minutes * 60 * 1000).toISOString(),
        end: now.toISOString(),
      };
    }
    return { start: undefined, end: undefined };
  }, [filters.start_time, filters.end_time, timelinePreset]);

  // Data query
  const { data, isLoading, isError, refetch } = useLogs(resolvedFilters);
  const { data: providersData } = useProviders({ is_active: true, page: 1, page_size: 1000 });
  const { data: modelsData } = useModels({ is_active: true, page: 1, page_size: 1000 });
  const { data: apiKeysData } = useApiKeys({ is_active: true, page: 1, page_size: 1000 });
  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);
  const { bucket: timelineBucket, bucketMinutes } = useMemo(
    () => resolveBucket(displayTimeRange.start, displayTimeRange.end, 60),
    [displayTimeRange.start, displayTimeRange.end]
  );
  const timelineParams = useMemo<LogQueryParams>(
    () => ({
      start_time: resolvedFilters.start_time,
      end_time: resolvedFilters.end_time,
      timeline: resolvedFilters.timeline,
      requested_model: resolvedFilters.requested_model,
      provider_id: resolvedFilters.provider_id,
      api_key_id: resolvedFilters.api_key_id,
      api_key_name: resolvedFilters.api_key_name,
      tz_offset_minutes: tzOffsetMinutes,
      bucket: timelineBucket,
      bucket_minutes: bucketMinutes,
      group_by: 'request_model',
    }),
    [
      resolvedFilters.api_key_id,
      resolvedFilters.api_key_name,
      resolvedFilters.end_time,
      resolvedFilters.provider_id,
      resolvedFilters.requested_model,
      resolvedFilters.start_time,
      resolvedFilters.timeline,
      bucketMinutes,
      timelineBucket,
      tzOffsetMinutes,
    ]
  );
  const {
    data: timelineStats,
    isLoading: timelineLoading,
    isFetching: timelineFetching,
    refetch: refetchTimeline,
  } = useLogCostStats(timelineParams);

  // Sync timelinePreset when filters change (e.g. user submits custom time via LogFilters)
  useEffect(() => {
    // When filters have no explicit time, keep current preset
    if (!filters.start_time && !filters.end_time) return;
    const startMs = new Date(filters.start_time!).getTime();
    const endMs = new Date(filters.end_time!).getTime();
    if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs <= startMs) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTimelinePreset('custom');
      return;
    }
    const now = Date.now();
    const diffToNow = Math.abs(endMs - now);
    const durationMinutes = Math.round((endMs - startMs) / (60 * 1000));
    const matched = TIMELINE_PRESETS.find(
      (preset) =>
        preset.minutes !== undefined &&
        Math.abs((preset.minutes ?? 0) - durationMinutes) <= 1 &&
        diffToNow <= 2 * 60 * 1000
    );
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTimelinePreset(matched?.value ?? 'custom');
  }, [filters.end_time, filters.start_time]);

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

  useEffect(() => {
    const nextFilters = buildFiltersFromParams();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilters((prev) => (areLogQueryParamsEqual(prev, nextFilters) ? prev : nextFilters));
  }, [areLogQueryParamsEqual, buildFiltersFromParams]);

  const filtersQuery = useMemo(() => {
    const params = new URLSearchParams();
    if ((filters.page ?? DEFAULT_FILTERS.page) !== DEFAULT_FILTERS.page) {
      setParam(params, 'page', filters.page);
    }
    if ((filters.page_size ?? DEFAULT_FILTERS.page_size) !== DEFAULT_FILTERS.page_size) {
      setParam(params, 'page_size', filters.page_size);
    }
    if ((filters.sort_by ?? DEFAULT_FILTERS.sort_by) !== DEFAULT_FILTERS.sort_by) {
      setParam(params, 'sort_by', filters.sort_by);
    }
    if ((filters.sort_order ?? DEFAULT_FILTERS.sort_order) !== DEFAULT_FILTERS.sort_order) {
      setParam(params, 'sort_order', filters.sort_order);
    }
    // Only write start/end to URL when explicitly set (custom mode)
    setParam(params, 'start_time', filters.start_time);
    setParam(params, 'end_time', filters.end_time);
    // Persist the preset so page refresh restores the same preset
    if (timelinePreset !== '24h') {
      setParam(params, 'preset', timelinePreset);
    }
    setParam(params, 'requested_model', filters.requested_model);
    setParam(params, 'target_model', filters.target_model);
    setParam(params, 'provider_id', filters.provider_id);
    setParam(params, 'status_min', filters.status_min);
    setParam(params, 'status_max', filters.status_max);
    setParam(params, 'has_error', filters.has_error);
    setParam(params, 'api_key_id', filters.api_key_id);
    setParam(params, 'api_key_name', filters.api_key_name);
    setParam(params, 'retry_count_min', filters.retry_count_min);
    setParam(params, 'retry_count_max', filters.retry_count_max);
    setParam(params, 'input_tokens_min', filters.input_tokens_min);
    setParam(params, 'input_tokens_max', filters.input_tokens_max);
    setParam(params, 'total_time_min', filters.total_time_min);
    setParam(params, 'total_time_max', filters.total_time_max);
    return params.toString();
  }, [filters, timelinePreset]);

  useEffect(() => {
    const currentQuery = searchParams.toString();
    if (filtersQuery === currentQuery) return;
    const nextUrl = filtersQuery ? `/logs?${filtersQuery}` : '/logs';
    router.replace(nextUrl, { scroll: false });
  }, [filtersQuery, router, searchParams]);

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
    const returnTo = filtersQuery ? `/logs?${filtersQuery}` : '/logs';
    router.push(
      `/logs/detail?id=${encodeURIComponent(String(log.id))}&returnTo=${encodeURIComponent(returnTo)}`
    );
  }, [filtersQuery, router]);

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold">{t('title')}</h1>
        <p className="mt-1 text-muted-foreground">
          {t('description')}
        </p>
      </div>

      {/* Timeline */}
      <LogTimeline
        stats={timelineStats}
        loading={timelineLoading}
        refreshing={timelineFetching}
        bucket={timelineBucket}
        bucketMinutes={bucketMinutes}
        maxBars={60}
        selectedStart={displayTimeRange.start}
        selectedEnd={displayTimeRange.end}
        onRangeChange={(range) => {
          if (range) {
            handleFilterChange({ start_time: range.start_time, end_time: range.end_time });
            return;
          }
          // Clear selection → restore default preset, remove explicit times
          setTimelinePreset('24h');
          handleFilterChange({ start_time: undefined, end_time: undefined });
        }}
        onRefresh={refetchTimeline}
        headerActions={
          <Select
            value={timelinePreset}
            onValueChange={(value) => {
              const preset = value as TimelinePreset;
              setTimelinePreset(preset);
              if (preset === 'custom') return;
              // Clear explicit times; timeline preset will be sent to backend
              handleFilterChange({ start_time: undefined, end_time: undefined });
            }}
          >
            <SelectTrigger className="h-8 w-[180px]">
              <SelectValue placeholder={tTimeline('rangeSelect')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="custom">{tTimeline('rangeCustom')}</SelectItem>
              <SelectItem value="1h">{tTimeline('range1h')}</SelectItem>
              <SelectItem value="3h">{tTimeline('range3h')}</SelectItem>
              <SelectItem value="6h">{tTimeline('range6h')}</SelectItem>
              <SelectItem value="12h">{tTimeline('range12h')}</SelectItem>
              <SelectItem value="24h">{tTimeline('range24h')}</SelectItem>
              <SelectItem value="1w">{tTimeline('range1w')}</SelectItem>
            </SelectContent>
          </Select>
        }
      />

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
          <CardTitle>{t('list.title')}</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8"
            aria-label={t('actions.refresh')}
            onClick={async () => {
              try {
                await refetch();
                toast.success(t('toasts.refreshSuccess'));
              } catch {
                toast.error(t('toasts.refreshFailed'));
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
              message={t('list.loadFailed')}
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState message={t('list.empty')} />
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
