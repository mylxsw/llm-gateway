/**
 * Model Mapping Form Component
 * Used for creating and editing model mappings
 */

'use client';

import React, { useEffect } from 'react';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  ModelType,
  SelectionStrategy
} from '@/types';
import { isValidModelName } from '@/lib/utils';
import { ModelProviderBillingFields } from '@/components/models/ModelProviderBillingFields';
import type { BillingMode } from '@/components/models/ModelProviderBillingFields';

interface ModelFormProps {
  /** Whether dialog is open */
  open: boolean;
  /** Dialog close callback */
  onOpenChange: (open: boolean) => void;
  /** Model data for edit mode */
  model?: ModelMapping | null;
  /** Submit callback */
  onSubmit: (data: ModelMappingCreate | ModelMappingUpdate) => void;
  /** Loading state */
  loading?: boolean;
}

/** Form Field Definition */
interface FormData {
  requested_model: string;
  strategy: SelectionStrategy;
  model_type: ModelType;
  is_active: boolean;
  billing_mode: BillingMode;
  input_price: string;
  output_price: string;
  per_request_price: string;
  per_image_price: string;
  tiers: Array<{ max_input_tokens: string; input_price: string; output_price: string; cached_input_price: string; cached_output_price: string }>;
  cache_billing_enabled: boolean;
  cached_input_price: string;
  cached_output_price: string;
}

/**
 * Model Mapping Form Component
 */
export function ModelForm({
  open,
  onOpenChange,
  model,
  onSubmit,
  loading = false,
}: ModelFormProps) {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');

  // Check if edit mode
  const isEdit = !!model;

  // Form control
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    control,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      requested_model: '',
      strategy: 'round_robin',
      model_type: 'chat',
      is_active: true,
      billing_mode: 'token_flat' as BillingMode,
      input_price: '',
      output_price: '',
      per_request_price: '',
      per_image_price: '',
      tiers: [{ max_input_tokens: '32768', input_price: '', output_price: '', cached_input_price: '', cached_output_price: '' }],
      cache_billing_enabled: false,
      cached_input_price: '',
      cached_output_price: '',
    },
  });

  const { fields: tierFields, append: appendTier, remove: removeTier } = useFieldArray({
    control,
    name: 'tiers',
  });

  const isActive = watch('is_active');
  const modelType = watch('model_type');
  const strategy = watch('strategy');
  const billingMode = watch('billing_mode');
  const cacheBillingEnabled = watch('cache_billing_enabled');
  const supportsBilling = modelType === 'chat' || modelType === 'embedding' || modelType === 'images';

  useEffect(() => {
    if (!supportsBilling && strategy === 'cost_first') {
      setValue('strategy', 'round_robin');
    }
  }, [supportsBilling, strategy, setValue]);

  // Fill form data in edit mode
  useEffect(() => {
    if (model) {
      const mode = (model.billing_mode || 'token_flat') as BillingMode;
      reset({
        requested_model: model.requested_model,
        strategy: model.strategy,
        model_type: model.model_type ?? 'chat',
        is_active: model.is_active,
        billing_mode: mode,
        input_price:
          model.input_price === null || model.input_price === undefined
            ? ''
            : String(model.input_price),
        output_price:
          model.output_price === null || model.output_price === undefined
            ? ''
            : String(model.output_price),
        per_request_price:
          model.per_request_price === null || model.per_request_price === undefined
            ? ''
            : String(model.per_request_price),
        per_image_price:
          model.per_image_price === null || model.per_image_price === undefined
            ? ''
            : String(model.per_image_price),
        cache_billing_enabled: !!model.cache_billing_enabled,
        cached_input_price: model.cached_input_price === null || model.cached_input_price === undefined ? '' : String(model.cached_input_price),
        cached_output_price: model.cached_output_price === null || model.cached_output_price === undefined ? '' : String(model.cached_output_price),
        tiers:
          model.tiered_pricing && model.tiered_pricing.length > 0
            ? model.tiered_pricing.map((t) => ({
                max_input_tokens:
                  t.max_input_tokens === null || t.max_input_tokens === undefined
                    ? ''
                    : String(t.max_input_tokens),
                input_price: String(t.input_price),
                output_price: String(t.output_price),
                cached_input_price: t.cached_input_price === null || t.cached_input_price === undefined ? '' : String(t.cached_input_price),
                cached_output_price: t.cached_output_price === null || t.cached_output_price === undefined ? '' : String(t.cached_output_price),
              }))
            : [{ max_input_tokens: '32768', input_price: '', output_price: '', cached_input_price: '', cached_output_price: '' }],
      });
    } else {
      reset({
        requested_model: '',
        strategy: 'round_robin',
        model_type: 'chat',
        is_active: true,
        billing_mode: 'token_flat' as BillingMode,
        input_price: '',
        output_price: '',
        per_request_price: '',
        per_image_price: '',
        tiers: [{ max_input_tokens: '32768', input_price: '', output_price: '', cached_input_price: '', cached_output_price: '' }],
        cache_billing_enabled: false,
        cached_input_price: '',
        cached_output_price: '',
      });
    }
  }, [model, reset]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    const resolvedStrategy = supportsBilling
      ? data.strategy
      : data.strategy === 'cost_first'
        ? 'round_robin'
        : data.strategy;
    const submitData: ModelMappingCreate | ModelMappingUpdate = {
      strategy: resolvedStrategy,
      model_type: data.model_type,
      is_active: data.is_active,
    };

    // requested_model required on creation
    if (!isEdit) {
      (submitData as ModelMappingCreate).requested_model = data.requested_model;
    }

    // Preserve existing capabilities on edit (field hidden in UI)
    if (isEdit && model?.capabilities) {
      submitData.capabilities = model.capabilities;
    }

    if (supportsBilling) {
      const billingMode = data.billing_mode;
      submitData.billing_mode = billingMode as ModelMappingCreate['billing_mode'];
      if (billingMode === 'per_request') {
        const perReq = data.per_request_price.trim();
        submitData.per_request_price = perReq ? Number(perReq) : 0;
        submitData.per_image_price = null;
        submitData.input_price = null;
        submitData.output_price = null;
        submitData.tiered_pricing = null;
        submitData.cache_billing_enabled = null;
        submitData.cached_input_price = null;
        submitData.cached_output_price = null;
      } else if (billingMode === 'per_image') {
        const perImg = data.per_image_price.trim();
        submitData.per_image_price = perImg ? Number(perImg) : 0;
        submitData.per_request_price = null;
        submitData.input_price = null;
        submitData.output_price = null;
        submitData.tiered_pricing = null;
        submitData.cache_billing_enabled = null;
        submitData.cached_input_price = null;
        submitData.cached_output_price = null;
      } else if (billingMode === 'token_tiered') {
        submitData.tiered_pricing = (data.tiers || []).map((t) => {
          const maxStr = t.max_input_tokens.trim();
          return {
            max_input_tokens: maxStr === '' ? null : Number(maxStr),
            input_price: Number(t.input_price || '0'),
            output_price: Number(t.output_price || '0'),
            cached_input_price: data.cache_billing_enabled && t.cached_input_price.trim() ? Number(t.cached_input_price) : undefined,
            cached_output_price: data.cache_billing_enabled && t.cached_output_price.trim() ? Number(t.cached_output_price) : undefined,
          };
        });
        submitData.per_request_price = null;
        submitData.per_image_price = null;
        submitData.input_price = null;
        submitData.output_price = null;
        submitData.cache_billing_enabled = data.cache_billing_enabled || null;
        submitData.cached_input_price = null;
        submitData.cached_output_price = null;
      } else {
        // token_flat
        const inputPrice = data.input_price.trim();
        const outputPrice = data.output_price.trim();
        submitData.input_price = inputPrice ? Number(inputPrice) : 0;
        submitData.output_price = outputPrice ? Number(outputPrice) : 0;
        submitData.per_request_price = null;
        submitData.per_image_price = null;
        submitData.tiered_pricing = null;
        submitData.cache_billing_enabled = data.cache_billing_enabled || null;
        submitData.cached_input_price = data.cache_billing_enabled && data.cached_input_price.trim() ? Number(data.cached_input_price) : null;
        submitData.cached_output_price = data.cache_billing_enabled && data.cached_output_price.trim() ? Number(data.cached_output_price) : null;
      }
    } else {
      submitData.billing_mode = null;
      submitData.input_price = null;
      submitData.output_price = null;
      submitData.per_request_price = null;
      submitData.per_image_price = null;
      submitData.tiered_pricing = null;
      submitData.cache_billing_enabled = null;
      submitData.cached_input_price = null;
      submitData.cached_output_price = null;
    }

    onSubmit(submitData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t('form.editTitle') : t('form.newTitle')}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Requested Model Name */}
          <div className="space-y-2">
            <Label htmlFor="requested_model">
              {t('form.requestedModelLabel')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="requested_model"
              placeholder={t('form.requestedModelPlaceholder')}
              disabled={isEdit}
              {...register('requested_model', {
                required: !isEdit ? t('form.requestedModelRequired') : false,
                validate: !isEdit
                  ? (v) =>
                      isValidModelName(v) ||
                      t('form.requestedModelInvalid')
                  : undefined,
              })}
            />
            {errors.requested_model && (
              <p className="text-sm text-destructive">
                {errors.requested_model.message}
              </p>
            )}
            {isEdit && (
              <p className="text-sm text-muted-foreground">
                {t('form.requestedModelImmutable')}
              </p>
            )}
          </div>



          {/* Model Type */}
          <div className="space-y-2">
            <Label>{t('form.modelTypeLabel')}</Label>
            <Controller
              name="model_type"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('form.modelTypePlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="chat">{t('filters.chat')}</SelectItem>
                    <SelectItem value="speech">{t('filters.speech')}</SelectItem>
                    <SelectItem value="transcription">{t('filters.transcription')}</SelectItem>
                    <SelectItem value="embedding">{t('filters.embedding')}</SelectItem>
                    <SelectItem value="images">{t('filters.images')}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {/* Billing / Pricing */}
          {supportsBilling && (
            <ModelProviderBillingFields
              t={t}
              billingMode={billingMode}
              setBillingMode={(value) =>
                setValue('billing_mode', value as FormData['billing_mode'])
              }
              register={register}
              tierFields={tierFields}
              appendTier={appendTier}
              removeTier={removeTier}
              modelType={modelType}
              cacheBillingEnabled={cacheBillingEnabled}
              setCacheBillingEnabled={(value) => setValue('cache_billing_enabled', value)}
            />
          )}

          {/* Strategy */}
          <div className="space-y-3">
            <Label>{t('form.selectionStrategy')}</Label>
            <Controller
              name="strategy"
              control={control}
              render={({ field }) => (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {/* Round Robin Strategy */}
                  <Card
                    className={`cursor-pointer transition-all duration-200 hover:shadow-md ${
                      field.value === 'round_robin'
                        ? 'border-primary border-2 bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => field.onChange('round_robin')}
                  >
                    <div className="p-4 space-y-2">
                      <div className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          field.value === 'round_robin'
                            ? 'border-primary bg-primary'
                            : 'border-muted-foreground'
                        }`}>
                          {field.value === 'round_robin' && (
                            <div className="w-2 h-2 rounded-full bg-white"></div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">🔄</span>
                          <span className="font-semibold text-base">
                            {t('form.roundRobinTitle')}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground pl-8">
                        {t('form.roundRobinDescription')}
                      </p>
                      <div className="pl-8 pt-1">
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs">
                          <span>⚖️</span>
                          <span>{t('form.roundRobinTag')}</span>
                        </div>
                      </div>
                    </div>
                  </Card>

                  {/* Priority Strategy */}
                  <Card
                    className={`cursor-pointer transition-all duration-200 hover:shadow-md ${
                      field.value === 'priority'
                        ? 'border-primary border-2 bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => field.onChange('priority')}
                  >
                    <div className="p-4 space-y-2">
                      <div className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          field.value === 'priority'
                            ? 'border-primary bg-primary'
                            : 'border-muted-foreground'
                        }`}>
                          {field.value === 'priority' && (
                            <div className="w-2 h-2 rounded-full bg-white"></div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">🏷️</span>
                          <span className="font-semibold text-base">
                            {t('form.priorityTitle')}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground pl-8">
                        {t('form.priorityDescription')}
                      </p>
                      <div className="pl-8 pt-1">
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs">
                          <span>🎯</span>
                          <span>{t('form.priorityTag')}</span>
                        </div>
                      </div>
                    </div>
                  </Card>

                  {/* Cost First Strategy */}
                  <Card
                    className={`transition-all duration-200 ${
                      supportsBilling ? 'cursor-pointer hover:shadow-md' : 'cursor-not-allowed opacity-50'
                    } ${
                      field.value === 'cost_first'
                        ? 'border-primary border-2 bg-primary/5'
                        : supportsBilling
                          ? 'border-border hover:border-primary/50'
                          : 'border-border'
                    }`}
                    onClick={() => {
                      if (supportsBilling) {
                        field.onChange('cost_first');
                      }
                    }}
                  >
                    <div className="p-4 space-y-2">
                      <div className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          field.value === 'cost_first'
                            ? 'border-primary bg-primary'
                            : 'border-muted-foreground'
                        }`}>
                          {field.value === 'cost_first' && (
                            <div className="w-2 h-2 rounded-full bg-white"></div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">💰</span>
                          <span className="font-semibold text-base">
                            {t('form.costFirstTitle')}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground pl-8">
                        {t('form.costFirstDescription')}
                      </p>
                      <div className="pl-8 pt-1">
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs">
                          <span>📊</span>
                          <span>{t('form.costFirstTag')}</span>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              )}
            />
            <p className="text-xs text-muted-foreground">
              💡 {t('form.strategyHint')}
            </p>
          </div>

          {/* Status */}
          <div className="flex items-center justify-between">
            <Label htmlFor="is_active">{t('form.enabledStatusLabel')}</Label>
            <Switch
              id="is_active"
              checked={isActive}
              onCheckedChange={(checked) => setValue('is_active', checked)}
            />
          </div>



          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              {tCommon('cancel')}
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? tCommon('saving') : tCommon('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
