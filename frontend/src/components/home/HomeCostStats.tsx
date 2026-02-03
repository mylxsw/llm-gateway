/**
 * Home Cost Stats
 * Shows aggregated cost stats on the home page.
 */

'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CostStats } from '@/components/logs';
import { useQuery } from '@tanstack/react-query';
import { getLogCostStats } from '@/lib/api';
import { LogQueryParams } from '@/types';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { useTranslations } from 'next-intl';
import { useApiKeys } from '@/lib/hooks';

type RangePreset = '24h' | '7d' | '30d' | '90d' | '365d' | 'custom';

const STORAGE_KEY = 'home_cost_stats_range_v1';
const DEFAULT_PRESET: RangePreset = '24h';
const DAY_MS = 24 * 60 * 60 * 1000;
const MAX_TREND_BARS = 30;

function resolveBucket(rangeMs: number, maxBars: number) {
  const perBarMs = rangeMs / Math.max(1, maxBars);
  return perBarMs < DAY_MS ? 'hour' : 'day';
}

function getRangeLabel(preset: RangePreset, t: (key: string) => string) {
  switch (preset) {
    case '24h':
      return t('rangePast24Hours');
    case '7d':
      return t('rangePast7Days');
    case '30d':
      return t('rangePastMonth');
    case '90d':
      return t('rangePast90Days');
    case '365d':
      return t('rangePastYear');
    case 'custom':
      return t('rangeSelected');
    default:
      return t('rangeSelected');
  }
}

function formatDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseDateInputValue(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const monthIndex = Number(match[2]) - 1;
  const day = Number(match[3]);
  const date = new Date(year, monthIndex, day);
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
}

function endOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}

function diffDaysInclusive(start: Date, end: Date) {
  const startAt = startOfDay(start).getTime();
  const endAt = startOfDay(end).getTime();
  const days = Math.floor((endAt - startAt) / DAY_MS) + 1;
  return Math.max(1, days);
}

function getDefaultRangeState() {
  const now = new Date();
  const defaultCustomEnd = formatDateInputValue(now);
  const defaultCustomStart = formatDateInputValue(new Date(now.getTime() - 6 * DAY_MS));
  return {
    preset: DEFAULT_PRESET as RangePreset,
    customStart: defaultCustomStart,
    customEnd: defaultCustomEnd,
  };
}

function loadRangeStateFromStorage() {
  const defaults = getDefaultRangeState();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<{
      preset: RangePreset;
      customStart: string;
      customEnd: string;
    }>;
    return {
      preset: parsed.preset ?? defaults.preset,
      customStart:
        parsed.customStart && parseDateInputValue(parsed.customStart)
          ? parsed.customStart
          : defaults.customStart,
      customEnd:
        parsed.customEnd && parseDateInputValue(parsed.customEnd)
          ? parsed.customEnd
          : defaults.customEnd,
    };
  } catch {
    return defaults;
  }
}

export function HomeCostStats() {
  const t = useTranslations('logs.costStats');
  const tFilters = useTranslations('logs.filters');
  const [{ preset, customStart, customEnd }, setRangeState] = useState(getDefaultRangeState);
  const [statsMode, setStatsMode] = useState<'request_model' | 'provider_model'>('request_model');
  const [apiKeyId, setApiKeyId] = useState<number | undefined>(undefined);
  const restoredRef = useRef(false);

  const { data: apiKeysData } = useApiKeys({ is_active: true, page: 1, page_size: 1000 });

  useEffect(() => {
    queueMicrotask(() => {
      try {
        setRangeState(loadRangeStateFromStorage());
      } catch {
        // ignore storage failures
      }
      restoredRef.current = true;
    });
  }, []);

  useEffect(() => {
    if (!restoredRef.current) return;
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          preset,
          customStart,
          customEnd,
        })
      );
    } catch {
      // ignore storage failures
    }
  }, [preset, customStart, customEnd]);

  const customRange = useMemo(() => {
    if (preset !== 'custom') return null;
    const start = parseDateInputValue(customStart);
    const end = parseDateInputValue(customEnd);
    if (!start || !end) return null;
    const startAt = startOfDay(start);
    const endAt = endOfDay(end);
    return { startAt, endAt };
  }, [preset, customStart, customEnd]);

  const displayRange = useMemo(() => {
    const now = new Date();
    if (preset === 'custom' && customRange) {
      const bucket = resolveBucket(customRange.endAt.getTime() - customRange.startAt.getTime(), MAX_TREND_BARS);
      return {
        start_time: customRange.startAt.toISOString(),
        end_time: customRange.endAt.toISOString(),
        bucket,
      } as const;
    }

    const days =
      preset === '24h' ? 1 : preset === '7d' ? 7 : preset === '30d' ? 30 : preset === '90d' ? 90 : 365;
    const start = new Date(now.getTime() - days * DAY_MS);
    const bucket = resolveBucket(now.getTime() - start.getTime(), MAX_TREND_BARS);
    return {
      start_time: start.toISOString(),
      end_time: now.toISOString(),
      bucket,
    } as const;
  }, [preset, customRange]);

  const rangeDays = useMemo(() => {
    if (preset === 'custom') {
      const start = parseDateInputValue(customStart);
      const end = parseDateInputValue(customEnd);
      if (!start || !end) return 1;
      return diffDaysInclusive(start, end);
    }

    if (preset === '24h') return 1;
    if (preset === '7d') return 7;
    if (preset === '30d') return 30;
    if (preset === '90d') return 90;
    return 365;
  }, [preset, customStart, customEnd]);

  const rangeLabel = useMemo(() => {
    if (preset === 'custom') {
      const start = parseDateInputValue(customStart);
      const end = parseDateInputValue(customEnd);
      if (!start || !end) return getRangeLabel(preset, t);
      return `${customStart} ~ ${customEnd}`;
    }
    return getRangeLabel(preset, t);
  }, [preset, customStart, customEnd, t]);

  const queryKey = useMemo(
    () => ['logs', 'home-cost-stats', preset, customStart, customEnd, statsMode, apiKeyId] as const,
    [preset, customStart, customEnd, statsMode, apiKeyId]
  );

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey,
    enabled: preset !== 'custom' || Boolean(customRange),
    queryFn: async () => {
      const now = new Date();
      const tzOffsetMinutes = -now.getTimezoneOffset();

      if (preset === 'custom' && customRange) {
        const bucket = resolveBucket(customRange.endAt.getTime() - customRange.startAt.getTime(), MAX_TREND_BARS);
        const params: LogQueryParams = {
          start_time: customRange.startAt.toISOString(),
          end_time: customRange.endAt.toISOString(),
          tz_offset_minutes: tzOffsetMinutes,
          bucket,
          group_by: statsMode,
          api_key_id: apiKeyId,
        };
        return getLogCostStats(params);
      }

      const days =
        preset === '24h' ? 1 : preset === '7d' ? 7 : preset === '30d' ? 30 : preset === '90d' ? 90 : 365;
      const start = new Date(now.getTime() - days * DAY_MS);
      const bucket = resolveBucket(now.getTime() - start.getTime(), MAX_TREND_BARS);

      // For live ranges, omit `end_time` so the server includes the latest logs up to now.
      const params: LogQueryParams = {
        start_time: start.toISOString(),
        tz_offset_minutes: tzOffsetMinutes,
        bucket,
        group_by: statsMode,
        api_key_id: apiKeyId,
      };
      return getLogCostStats(params);
    },
    refetchInterval: preset === 'custom' ? false : 15_000,
    refetchOnWindowFocus: true,
    staleTime: 30 * 1000,
  });

  return (
    <CostStats
      stats={data}
      loading={isLoading}
      refreshing={isFetching}
      rangeLabel={rangeLabel}
      rangeDays={rangeDays}
      rangeStart={displayRange.start_time}
      rangeEnd={displayRange.end_time}
      bucket={displayRange.bucket}
      maxBars={MAX_TREND_BARS}
      modelStatsControls={
        <div className="flex items-center gap-2">
           <Select
            value={statsMode}
            onValueChange={(v) => setStatsMode(v as 'request_model' | 'provider_model')}
          >
            <SelectTrigger className="h-6 w-[130px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="request_model">{t('statsModeRequestModel')}</SelectItem>
              <SelectItem value="provider_model">{t('statsModeProviderModel')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      }
      headerActions={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Select
            value={apiKeyId === undefined ? 'all' : String(apiKeyId)}
            onValueChange={(value) => setApiKeyId(value === 'all' ? undefined : Number(value))}
          >
            <SelectTrigger className="h-8 w-[170px]">
              <SelectValue placeholder={tFilters('apiKey')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{tFilters('all')}</SelectItem>
              {(apiKeysData?.items || []).map((k) => (
                <SelectItem key={k.id} value={String(k.id)}>
                  {k.key_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={preset}
            onValueChange={(v) => setRangeState((s) => ({ ...s, preset: v as RangePreset }))}
          >
            <SelectTrigger className="h-8 w-[160px]">
              <SelectValue placeholder={t('selectTimeRange')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">{t('last24Hours')}</SelectItem>
              <SelectItem value="7d">{t('last7Days')}</SelectItem>
              <SelectItem value="30d">{t('last30Days')}</SelectItem>
              <SelectItem value="90d">{t('last90Days')}</SelectItem>
              <SelectItem value="365d">{t('last365Days')}</SelectItem>
              <SelectItem value="custom">{t('customRange')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      }
      headerExtras={
        preset === 'custom' ? (
          <div className="flex flex-col items-end gap-2 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <Input
                className="h-8 w-[140px]"
                type="date"
                value={customStart}
                aria-label={t('startDate')}
                onChange={(e) => {
                  const nextStart = e.target.value;
                  if (!nextStart) return;
                  setRangeState((s) => ({
                    ...s,
                    customStart: nextStart,
                    customEnd: nextStart > s.customEnd ? nextStart : s.customEnd,
                  }));
                }}
              />
            </div>
            <div className="flex items-center gap-2">
              <Input
                className="h-8 w-[140px]"
                type="date"
                value={customEnd}
                aria-label={t('endDate')}
                onChange={(e) => {
                  const nextEnd = e.target.value;
                  if (!nextEnd) return;
                  setRangeState((s) => ({
                    ...s,
                    customEnd: nextEnd,
                    customStart: nextEnd < s.customStart ? nextEnd : s.customStart,
                  }));
                }}
              />
            </div>
          </div>
        ) : null
      }
      onRefresh={() => {
        void refetch();
      }}
    />
  );
}
