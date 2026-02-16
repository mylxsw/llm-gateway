/**
 * Reusable billing/pricing fields for model-provider forms.
 */

'use client';

import React from 'react';
import { FieldValues, Path, UseFormRegister } from 'react-hook-form';
import { Loader2, MousePointerClick } from 'lucide-react';
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
import type { ModelType } from '@/types';

export type BillingMode = 'token_flat' | 'token_tiered' | 'per_request' | 'per_image';

interface TierInputValue {
  max_input_tokens: string;
  input_price: string;
  output_price: string;
}

type BillingFormValues = FieldValues & {
  input_price: string;
  output_price: string;
  per_request_price: string;
  per_image_price: string;
  tiers: TierInputValue[];
};

interface ModelProviderBillingFieldsProps<TFormValues extends BillingFormValues> {
  t: (key: string) => string;
  billingMode: BillingMode;
  setBillingMode: (mode: BillingMode) => void;
  register: UseFormRegister<TFormValues>;
  tierFields: Array<{ id: string }>;
  appendTier: (value: TierInputValue) => void;
  removeTier: (index: number) => void;
  historyLoading?: boolean;
  onLoadHistory?: () => void;
  showHistoryButton?: boolean;
  modelType?: ModelType;
}

export function ModelProviderBillingFields<TFormValues extends BillingFormValues>({
  t,
  billingMode,
  setBillingMode,
  register,
  tierFields,
  appendTier,
  removeTier,
  historyLoading = false,
  onLoadHistory,
  showHistoryButton = false,
  modelType,
}: ModelProviderBillingFieldsProps<TFormValues>) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{t('providerForm.billing')}</div>
        {showHistoryButton ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onLoadHistory}
            disabled={historyLoading}
            title={t('providerForm.loadHistoryAction')}
          >
            {historyLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <MousePointerClick className="h-4 w-4" />
            )}
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t('providerForm.billingMode')}</Label>
          <Select value={billingMode} onValueChange={(value) => setBillingMode(value as BillingMode)}>
            <SelectTrigger>
              <SelectValue placeholder={t('providerForm.billingModePlaceholder')} />
            </SelectTrigger>
            <SelectContent>
              {modelType !== 'images' && (
                <SelectItem value="per_request">
                  {t('providerForm.billingModePerRequest')}
                </SelectItem>
              )}
              {(modelType === 'images' || modelType === undefined) && (
                <SelectItem value="per_image">
                  {t('providerForm.billingModePerImage')}
                </SelectItem>
              )}
              <SelectItem value="token_flat">
                {t('providerForm.billingModeTokenFlat')}
              </SelectItem>
              {modelType !== 'images' && (
                <SelectItem value="token_tiered">
                  {t('providerForm.billingModeTokenTiered')}
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        </div>
      </div>

      {billingMode === 'per_request' ? (
        <div className="space-y-2">
          <Label htmlFor="per_request_price">
            {t('providerForm.pricePerRequest')}
          </Label>
          <Input
            id="per_request_price"
            type="number"
            min={0}
            step="0.0001"
            {...register('per_request_price' as Path<TFormValues>)}
          />
        </div>
      ) : billingMode === 'per_image' ? (
        <div className="space-y-2">
          <Label htmlFor="per_image_price">
            {t('providerForm.pricePerImage')}
          </Label>
          <Input
            id="per_image_price"
            type="number"
            min={0}
            step="0.0001"
            {...register('per_image_price' as Path<TFormValues>)}
          />
        </div>
      ) : billingMode === 'token_tiered' ? (
        <div className="space-y-3">
          <div className="text-xs text-muted-foreground">
            {t('providerForm.tieredHint')}
          </div>
          <div className="space-y-2">
            {tierFields.map((field, idx) => (
              <div key={field.id} className="grid grid-cols-7 gap-2 items-end">
                <div className="col-span-2 space-y-1">
                  <Label>{t('providerForm.maxInputTokens')}</Label>
                  <Input
                    type="number"
                    min={1}
                    placeholder={t('providerForm.tierMaxPlaceholder')}
                    {...register(`tiers.${idx}.max_input_tokens` as Path<TFormValues>)}
                  />
                </div>
                <div className="col-span-2 space-y-1">
                  <Label>{t('providerForm.tierInputPrice')}</Label>
                  <Input
                    type="number"
                    min={0}
                    step="0.0001"
                    placeholder={t('providerForm.tierInputPlaceholder')}
                    {...register(`tiers.${idx}.input_price` as Path<TFormValues>)}
                  />
                </div>
                <div className="col-span-2 space-y-1">
                  <Label>{t('providerForm.tierOutputPrice')}</Label>
                  <Input
                    type="number"
                    min={0}
                    step="0.0001"
                    placeholder={t('providerForm.tierOutputPlaceholder')}
                    {...register(`tiers.${idx}.output_price` as Path<TFormValues>)}
                  />
                </div>
                <div className="col-span-1 flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => removeTier(idx)}
                    disabled={tierFields.length <= 1}
                  >
                    {t('providerForm.removeTier')}
                  </Button>
                </div>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                appendTier({ max_input_tokens: '', input_price: '', output_price: '' })
              }
            >
              {t('providerForm.addTier')}
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="input_price">{t('providerForm.inputPrice')}</Label>
              <Input
                id="input_price"
                type="number"
                min={0}
                step="0.0001"
                {...register('input_price' as Path<TFormValues>)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="output_price">{t('providerForm.outputPrice')}</Label>
              <Input
                id="output_price"
                type="number"
                min={0}
                step="0.0001"
                {...register('output_price' as Path<TFormValues>)}
              />
            </div>
          </div>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        {t('providerForm.billingHint')}
      </p>
    </div>
  );
}
