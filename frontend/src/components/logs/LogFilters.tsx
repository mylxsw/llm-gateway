/**
 * Log Filter Component
 * Provides multi-condition filtering for log queries
 */

'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { CalendarIcon, Filter, X } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { LogQueryParams } from '@/types';

interface LogFiltersProps {
  /** Current filter values */
  filters: Partial<LogQueryParams>;
  /** Filter change callback */
  onFilterChange: (filters: Partial<LogQueryParams>) => void;
  /** Providers list (for dropdown) */
  providers: Array<{ id: number; name: string }>;
}

/**
 * Log Filter Component
 */
export function LogFilters({
  filters,
  onFilterChange,
  providers,
}: LogFiltersProps) {
  const { register, handleSubmit, reset, setValue, watch } = useForm<Partial<LogQueryParams>>({
    defaultValues: filters,
  });

  const startTime = watch('start_time');
  const endTime = watch('end_time');
  const hasError = watch('has_error');

  const onReset = () => {
    reset({
      page: 1,
      page_size: filters.page_size,
    });
    onFilterChange({});
  };

  const onSubmit = (data: Partial<LogQueryParams>) => {
    // Remove empty values
    const cleanData = Object.fromEntries(
      Object.entries(data).filter(([_, v]) => v !== undefined && v !== '')
    );
    onFilterChange(cleanData);
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mb-6 rounded-lg border bg-card p-4 shadow-sm"
    >
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Date Range */}
        <div className="flex gap-2">
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  'w-full justify-start text-left font-normal',
                  !startTime && 'text-muted-foreground'
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {startTime ? (
                  format(new Date(startTime), 'yyyy-MM-dd')
                ) : (
                  <span>Start Date</span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={startTime ? new Date(startTime) : undefined}
                onSelect={(date) => 
                  setValue('start_time', date ? date.toISOString() : undefined)
                }
                initialFocus
              />
            </PopoverContent>
          </Popover>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  'w-full justify-start text-left font-normal',
                  !endTime && 'text-muted-foreground'
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {endTime ? (
                  format(new Date(endTime), 'yyyy-MM-dd')
                ) : (
                  <span>End Date</span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={endTime ? new Date(endTime) : undefined}
                onSelect={(date) =>
                  setValue('end_time', date ? date.toISOString() : undefined)
                }
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        {/* Model */}
        <Input
          placeholder="Model Name (Requested/Target)"
          {...register('requested_model')}
        />

        {/* Trace ID */}
        <Input
          placeholder="Trace ID"
          {...register('trace_id')} // NOTE: Backend needs support or fuzzy search
        />

        {/* Provider */}
        <Select
          onValueChange={(value) => 
            setValue('provider_id', value === 'all' ? undefined : Number(value))
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select Provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Providers</SelectItem>
            {providers.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Status */}
        <Select
          onValueChange={(value) => {
            if (value === 'error') {
              setValue('has_error', true);
            } else if (value === 'success') {
              setValue('has_error', false);
            } else {
              setValue('has_error', undefined);
            }
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Request Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="success">Success</SelectItem>
            <SelectItem value="error">Failed</SelectItem>
          </SelectContent>
        </Select>
        
        {/* Buttons */}
        <div className="flex gap-2 lg:col-span-3 lg:justify-end">
          <Button type="button" variant="outline" onClick={onReset}>
            <X className="mr-2 h-4 w-4" />
            Reset
          </Button>
          <Button type="submit">
            <Filter className="mr-2 h-4 w-4" />
            Filter
          </Button>
        </div>
      </div>
    </form>
  );
}