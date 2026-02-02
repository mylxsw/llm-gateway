'use client';

import React, { useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslations } from 'next-intl';
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
  target_model_name?: string;
  model_type?: ModelType | 'all';
  strategy?: SelectionStrategy | 'all';
  is_active?: string; // 'all' | 'active' | 'inactive'
}

interface ModelFiltersProps {
  filters: ModelFiltersState;
  onFilterChange: (filters: ModelFiltersState) => void;
}

export function ModelFilters({ filters, onFilterChange }: ModelFiltersProps) {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');

  const defaultValues = useMemo(
    () => ({
      requested_model: filters.requested_model,
      target_model_name: filters.target_model_name,
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
      target_model_name: '',
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
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-2">
            <Label>{t('filters.modelName')}</Label>
            <Input
              placeholder={t('filters.fuzzyMatch')}
              {...register('requested_model')}
            />
          </div>

          <div className="space-y-2">
            <Label>{t('filters.supplierModelName')}</Label>
            <Input
              placeholder={t('filters.targetModelName')}
              {...register('target_model_name')}
            />
          </div>

          <div className="space-y-2">
            <Label>{t('filters.type')}</Label>
            <Select
              value={watch('model_type')}
              onValueChange={(value) => setValue('model_type', value as ModelType | 'all')}
            >
              <SelectTrigger>
                <SelectValue placeholder={tCommon('all')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tCommon('all')}</SelectItem>
                <SelectItem value="chat">{t('filters.chat')}</SelectItem>
                <SelectItem value="speech">{t('filters.speech')}</SelectItem>
                <SelectItem value="transcription">{t('filters.transcription')}</SelectItem>
                <SelectItem value="embedding">{t('filters.embedding')}</SelectItem>
                <SelectItem value="images">{t('filters.images')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>{t('filters.strategy')}</Label>
            <Select
              value={watch('strategy')}
              onValueChange={(value) => setValue('strategy', value as SelectionStrategy | 'all')}
            >
              <SelectTrigger>
                <SelectValue placeholder={tCommon('all')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tCommon('all')}</SelectItem>
                <SelectItem value="round_robin">{t('filters.roundRobin')}</SelectItem>
                <SelectItem value="cost_first">{t('filters.costFirst')}</SelectItem>
                <SelectItem value="priority">{t('filters.priority')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>{t('filters.status')}</Label>
            <Select
              value={watch('is_active')}
              onValueChange={(value) => setValue('is_active', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder={tCommon('all')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tCommon('all')}</SelectItem>
                <SelectItem value="active">{t('filters.active')}</SelectItem>
                <SelectItem value="inactive">{t('filters.inactive')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onReset}>
            <X className="mr-2 h-4 w-4" />
            {t('filters.reset')}
          </Button>
          <Button type="submit">
            <Filter className="mr-2 h-4 w-4" />
            {t('filters.filter')}
          </Button>
        </div>
      </div>
    </form>
  );
}
