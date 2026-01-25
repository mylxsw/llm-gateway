/**
 * Log Filter Component
 * Provides multi-condition filtering for log queries
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ChevronDown, ChevronUp, Filter, X } from 'lucide-react';
import { LogQueryParams } from '@/types';
import { normalizeUtcDateString } from '@/lib/utils';

interface LogFiltersProps {
  /** Current filter values */
  filters: LogQueryParams;
  /** Filter change callback */
  onFilterChange: (filters: Partial<LogQueryParams>) => void;
  /** Providers list (for dropdown) */
  providers: Array<{ id: number; name: string }>;
  /** Models list (for dropdown) */
  models: Array<{ requested_model: string }>;
  /** API keys list (for dropdown) */
  apiKeys: Array<{ id: number; key_name: string }>;
}

const FILTER_KEYS: Array<keyof LogQueryParams> = [
  'start_time',
  'end_time',
  'requested_model',
  'target_model',
  'provider_id',
  'has_error',
  'status_min',
  'status_max',
  'api_key_id',
  'api_key_name',
  'retry_count_min',
  'retry_count_max',
  'input_tokens_min',
  'input_tokens_max',
  'total_time_min',
  'total_time_max',
];

function pad2(v: number) {
  return String(v).padStart(2, '0');
}

function isoToLocalDateTimeInputValue(value?: string) {
  if (!value) return undefined;
  const d = new Date(normalizeUtcDateString(value));
  if (Number.isNaN(d.getTime())) return undefined;
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(
    d.getHours()
  )}:${pad2(d.getMinutes())}`;
}

function localDateTimeInputValueToIso(value?: string) {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;

  const match = /^(\d{4})-(\d{2})-(\d{2})[T\\s](\d{2}):(\d{2})(?::(\d{2}))?$/.exec(trimmed);
  if (!match) return undefined;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = match[6] ? Number(match[6]) : 0;

  const local = new Date(year, month - 1, day, hour, minute, second, 0);
  if (Number.isNaN(local.getTime())) return undefined;
  return local.toISOString();
}

/**
 * Log Filter Component
 */
export function LogFilters({
  filters,
  onFilterChange,
  providers,
  models,
  apiKeys,
}: LogFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const defaultValues = useMemo<Partial<LogQueryParams>>(
    () => ({
      start_time: isoToLocalDateTimeInputValue(filters.start_time),
      end_time: isoToLocalDateTimeInputValue(filters.end_time),
      requested_model: filters.requested_model,
      target_model: filters.target_model,
      provider_id: filters.provider_id,
      has_error: filters.has_error,
      status_min: filters.status_min,
      status_max: filters.status_max,
      api_key_id: filters.api_key_id,
      api_key_name: filters.api_key_name,
      retry_count_min: filters.retry_count_min,
      retry_count_max: filters.retry_count_max,
      input_tokens_min: filters.input_tokens_min,
      input_tokens_max: filters.input_tokens_max,
      total_time_min: filters.total_time_min,
      total_time_max: filters.total_time_max,
    }),
    [
      filters.api_key_id,
      filters.api_key_name,
      filters.end_time,
      filters.has_error,
      filters.input_tokens_max,
      filters.input_tokens_min,
      filters.provider_id,
      filters.requested_model,
      filters.retry_count_max,
      filters.retry_count_min,
      filters.start_time,
      filters.status_max,
      filters.status_min,
      filters.target_model,
      filters.total_time_max,
      filters.total_time_min,
    ]
  );

  const { register, handleSubmit, reset, setValue, watch } = useForm<
    Partial<LogQueryParams>
  >({
    defaultValues,
  });

  useEffect(() => {
    reset(defaultValues);
  }, [defaultValues, reset]);

  const onReset = () => {
    const cleared: Partial<LogQueryParams> = {
      page: 1,
      page_size: filters.page_size ?? 20,
    };
    for (const key of FILTER_KEYS) cleared[key] = undefined;
    reset(cleared);
    onFilterChange(cleared);
  };

  const onSubmit = (data: Partial<LogQueryParams>) => {
    const normalized: Partial<LogQueryParams> = {
      page: 1,
      page_size: filters.page_size ?? 20,
    };

    for (const key of FILTER_KEYS) {
      const value = data[key];
      if (value === '') {
        normalized[key] = undefined;
        continue;
      }
      if (typeof value === 'number' && Number.isNaN(value)) {
        normalized[key] = undefined;
        continue;
      }
      if (key === 'start_time' || key === 'end_time') {
        (normalized as Record<keyof LogQueryParams, unknown>)[key] =
          localDateTimeInputValueToIso(value as string | undefined);
      } else {
        (normalized as Record<keyof LogQueryParams, unknown>)[key] = value;
      }
    }

    onFilterChange(normalized);
  };

  const providerValue =
    watch('provider_id') === undefined ? 'all' : String(watch('provider_id'));

  const modelValue =
    watch('requested_model') === undefined ? 'all' : String(watch('requested_model'));

  const apiKeyValue =
    watch('api_key_id') === undefined ? 'all' : String(watch('api_key_id'));

  const errorValue =
    watch('has_error') === undefined
      ? 'all'
      : watch('has_error')
        ? 'true'
        : 'false';

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mb-6 rounded-lg border bg-card p-4 shadow-sm"
    >
      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-2">
            <Label>Start Time</Label>
            <Input type="datetime-local" {...register('start_time')} />
          </div>

          <div className="space-y-2">
            <Label>End Time</Label>
            <Input type="datetime-local" {...register('end_time')} />
          </div>

          <div className="space-y-2">
            <Label>Model</Label>
            <Select
              value={modelValue}
              onValueChange={(value) =>
                setValue('requested_model', value === 'all' ? undefined : value, { shouldDirty: true })
              }
            >
              <SelectTrigger className="w-full min-w-0">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {models.map((m) => (
                  <SelectItem key={m.requested_model} value={m.requested_model}>
                    {m.requested_model}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>API Key</Label>
            <Select
              value={apiKeyValue}
              onValueChange={(value) =>
                setValue('api_key_id', value === 'all' ? undefined : Number(value), { shouldDirty: true })
              }
            >
              <SelectTrigger className="w-full min-w-0">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {apiKeys.map((k) => (
                  <SelectItem key={k.id} value={String(k.id)}>
                    {k.key_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>Provider</Label>
            <Select
              value={providerValue}
              onValueChange={(value) =>
                setValue(
                  'provider_id',
                  value === 'all' ? undefined : Number(value),
                  { shouldDirty: true }
                )
              }
            >
              <SelectTrigger className="w-full min-w-0">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {providers.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Has Error</Label>
            <Select
              value={errorValue}
              onValueChange={(value) =>
                setValue(
                  'has_error',
                  value === 'all' ? undefined : value === 'true',
                  { shouldDirty: true }
                )
              }
            >
              <SelectTrigger className="w-full min-w-0">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="true">Has Error</SelectItem>
                <SelectItem value="false">No Error</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-end justify-end gap-2">
            <Button type="button" variant="outline" onClick={onReset}>
              <X className="mr-2 h-4 w-4" suppressHydrationWarning />
              Reset
            </Button>
            <Button type="submit">
              <Filter className="mr-2 h-4 w-4" suppressHydrationWarning />
              Filter
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0"
              aria-label="Toggle advanced filters"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? (
                <ChevronUp className="h-4 w-4" suppressHydrationWarning />
              ) : (
                <ChevronDown className="h-4 w-4" suppressHydrationWarning />
              )}
            </Button>
          </div>
        </div>

        {showAdvanced && (
          <div className="space-y-4 border-t pt-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label>Status Code Range</Label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    placeholder="Min"
                    className="min-w-0 flex-1"
                    {...register('status_min', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                  <Input
                    type="number"
                    placeholder="Max"
                    className="min-w-0 flex-1"
                    {...register('status_max', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Retry Count Range</Label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    min={0}
                    placeholder="Min"
                    className="min-w-0 flex-1"
                    {...register('retry_count_min', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                  <Input
                    type="number"
                    min={0}
                    placeholder="Max"
                    className="min-w-0 flex-1"
                    {...register('retry_count_max', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>API Key Name</Label>
                <Input
                  placeholder="Fuzzy match"
                  {...register('api_key_name')}
                />
              </div>

              <div className="space-y-2">
                <Label>Input Tokens Range</Label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    placeholder="Min"
                    className="min-w-0 flex-1"
                    {...register('input_tokens_min', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                  <Input
                    type="number"
                    placeholder="Max"
                    className="min-w-0 flex-1"
                    {...register('input_tokens_max', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label>Target Model</Label>
                <Input
                  placeholder="Fuzzy match"
                  {...register('target_model')}
                />
              </div>
              <div className="space-y-2">
                <Label>Total Duration Range (ms)</Label>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    placeholder="Min"
                    className="min-w-0 flex-1"
                    {...register('total_time_min', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                  <Input
                    type="number"
                    placeholder="Max"
                    className="min-w-0 flex-1"
                    {...register('total_time_max', {
                      setValueAs: (v) =>
                        v === '' ? undefined : Number(v),
                    })}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </form>
  );
}
