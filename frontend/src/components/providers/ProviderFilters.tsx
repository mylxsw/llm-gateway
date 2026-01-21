'use client';

import React, { useEffect, useMemo } from 'react';
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
import { Filter, X } from 'lucide-react';
import { ProtocolType } from '@/types';

export interface ProviderFiltersState {
  name?: string;
  protocol?: ProtocolType | 'all';
  is_active?: string; // 'all' | 'active' | 'inactive'
}

interface ProviderFiltersProps {
  filters: ProviderFiltersState;
  onFilterChange: (filters: ProviderFiltersState) => void;
}

export function ProviderFilters({ filters, onFilterChange }: ProviderFiltersProps) {
  const defaultValues = useMemo(
    () => ({
      name: filters.name,
      protocol: filters.protocol || 'all',
      is_active: filters.is_active || 'all',
    }),
    [filters]
  );

  const { register, handleSubmit, reset, setValue, watch } = useForm<ProviderFiltersState>({
    defaultValues,
  });

  useEffect(() => {
    reset(defaultValues);
  }, [defaultValues, reset]);

  const onReset = () => {
    const cleared: ProviderFiltersState = {
      name: '',
      protocol: 'all',
      is_active: 'all',
    };
    reset(cleared);
    onFilterChange(cleared);
  };

  const onSubmit = (data: ProviderFiltersState) => {
    onFilterChange(data);
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="mb-6 rounded-lg border bg-card p-4 shadow-sm"
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-2">
            <Label>Provider Name</Label>
            <Input
              placeholder="Fuzzy match"
              {...register('name')}
            />
          </div>

          <div className="space-y-2">
            <Label>Protocol</Label>
            <Select
              value={watch('protocol')}
              onValueChange={(value) => setValue('protocol', value as ProtocolType | 'all')}
            >
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="anthropic">Anthropic</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Status</Label>
            <Select
              value={watch('is_active')}
              onValueChange={(value) => setValue('is_active', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex justify-end gap-2">
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
