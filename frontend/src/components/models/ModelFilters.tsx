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
import { ModelType, SelectionStrategy } from '@/types';

export interface ModelFiltersState {
  requested_model?: string;
  model_type?: ModelType | 'all';
  strategy?: SelectionStrategy | 'all';
  is_active?: string; // 'all' | 'active' | 'inactive'
}

interface ModelFiltersProps {
  filters: ModelFiltersState;
  onFilterChange: (filters: ModelFiltersState) => void;
}

export function ModelFilters({ filters, onFilterChange }: ModelFiltersProps) {
  const defaultValues = useMemo(
    () => ({
      requested_model: filters.requested_model,
      model_type: filters.model_type || 'all',
      strategy: filters.strategy || 'all',
      is_active: filters.is_active || 'all',
    }),
    [filters]
  );

  const { register, handleSubmit, reset, setValue, watch } = useForm<ModelFiltersState>({
    defaultValues,
  });

  useEffect(() => {
    reset(defaultValues);
  }, [defaultValues, reset]);

  const onReset = () => {
    const cleared: ModelFiltersState = {
      requested_model: '',
      model_type: 'all',
      strategy: 'all',
      is_active: 'all',
    };
    reset(cleared);
    onFilterChange(cleared);
  };

  const onSubmit = (data: ModelFiltersState) => {
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
            <Label>Model Name</Label>
            <Input
              placeholder="Fuzzy match"
              {...register('requested_model')}
            />
          </div>

          <div className="space-y-2">
            <Label>Type</Label>
            <Select
              value={watch('model_type')}
              onValueChange={(value) => setValue('model_type', value as ModelType | 'all')}
            >
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="chat">Chat</SelectItem>
                <SelectItem value="speech">Speech</SelectItem>
                <SelectItem value="transcription">Transcription</SelectItem>
                <SelectItem value="embedding">Embedding</SelectItem>
                <SelectItem value="images">Images</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Strategy</Label>
            <Select
              value={watch('strategy')}
              onValueChange={(value) => setValue('strategy', value as SelectionStrategy | 'all')}
            >
              <SelectTrigger>
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="round_robin">Round Robin</SelectItem>
                <SelectItem value="cost_first">Cost First</SelectItem>
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
