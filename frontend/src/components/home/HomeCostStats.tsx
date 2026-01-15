/**
 * Home Cost Stats
 * Shows aggregated cost stats on the home page.
 */

'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CostStats } from '@/components/logs';
import { useLogCostStats } from '@/lib/hooks';
import { LogQueryParams } from '@/types';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

type RangePreset = '24h' | '7d' | '30d' | '90d' | '365d' | 'custom';

const STORAGE_KEY = 'home_cost_stats_range_v1';
const DEFAULT_PRESET: RangePreset = '7d';
const DAY_MS = 24 * 60 * 60 * 1000;

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
  const [{ preset, customStart, customEnd }, setRangeState] = useState(getDefaultRangeState);
  const [refreshToken, setRefreshToken] = useState(0);
  const restoredRef = useRef(false);

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

  const params = useMemo<LogQueryParams>(() => {
    const refreshBump = refreshToken * 0;
    const endAnchor = new Date();

    if (preset === 'custom') {
      const start = parseDateInputValue(customStart);
      const end = parseDateInputValue(customEnd);
      if (!start || !end) return {};
      const startAt = startOfDay(start);
      const endAt = new Date(endOfDay(end).getTime() + refreshBump);
      return { start_time: startAt.toISOString(), end_time: endAt.toISOString() };
    }

    if (preset === '24h') {
      const start = new Date(endAnchor.getTime() - DAY_MS + refreshBump);
      return { start_time: start.toISOString(), end_time: endAnchor.toISOString() };
    }

    const days = preset === '7d' ? 7 : preset === '30d' ? 30 : preset === '90d' ? 90 : 365;
    const start = new Date(endAnchor.getTime() - days * DAY_MS + refreshBump);
    return { start_time: start.toISOString(), end_time: endAnchor.toISOString() };
  }, [preset, customStart, customEnd, refreshToken]);

  const { data, isLoading, isFetching, refetch } = useLogCostStats(params);

  return (
    <CostStats
      stats={data}
      loading={isLoading}
      refreshing={isFetching}
      toolbar={
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <Label className="text-xs text-muted-foreground">Range</Label>
            <Select
              value={preset}
              onValueChange={(v) => setRangeState((s) => ({ ...s, preset: v as RangePreset }))}
            >
              <SelectTrigger className="h-8 w-[150px]">
                <SelectValue placeholder="Select range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">Last 24 hours</SelectItem>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="90d">Last 90 days</SelectItem>
                <SelectItem value="365d">Last 365 days</SelectItem>
                <SelectItem value="custom">Custom…</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {preset === 'custom' ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className="flex items-center gap-2">
                <Input
                  className="h-8 w-[140px]"
                  type="date"
                  value={customStart}
                  aria-label="Start date"
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
                  aria-label="End date"
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
          ) : null}
        </div>
      }
      onRefresh={() => {
        if (preset === 'custom') {
          void refetch();
          return;
        }
        setRefreshToken((v) => v + 1);
      }}
    />
  );
}
