/**
 * Bulk upgrade dialog for provider model mappings.
 */

'use client';

import React, { useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { useFieldArray, useForm } from 'react-hook-form';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { BillingDisplay, ModelProviderBillingFields } from '@/components/models';
import {
  ModelMappingProvider,
  ModelProviderBulkUpgradeRequest,
  Provider,
} from '@/types';

interface ProviderModelBulkUpgradeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: Provider | null;
  currentModelName: string | null;
  mappings: ModelMappingProvider[];
  loading?: boolean;
  onSubmit: (data: ModelProviderBulkUpgradeRequest) => void;
}

interface FormData {
  new_target_model_name: string;
  billing_mode: 'token_flat' | 'token_tiered' | 'per_request' | 'per_image';
  input_price: string;
  output_price: string;
  per_request_price: string;
  per_image_price: string;
  tiers: Array<{ max_input_tokens: string; input_price: string; output_price: string }>;
}

function buildDefaultPricing(mapping?: ModelMappingProvider | null): Omit<FormData, 'new_target_model_name'> {
  if (!mapping) {
    return {
      billing_mode: 'token_flat',
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: '0',
      tiers: [{ max_input_tokens: '32768', input_price: '0', output_price: '0' }],
    };
  }

  const billingMode = (mapping.billing_mode || 'token_flat') as FormData['billing_mode'];

  if (billingMode === 'per_request') {
    return {
      billing_mode: billingMode,
      input_price: '0',
      output_price: '0',
      per_request_price: String(mapping.per_request_price ?? 0),
      per_image_price: '0',
      tiers: [{ max_input_tokens: '32768', input_price: '0', output_price: '0' }],
    };
  }

  if (billingMode === 'per_image') {
    return {
      billing_mode: billingMode,
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: String(mapping.per_image_price ?? 0),
      tiers: [{ max_input_tokens: '32768', input_price: '0', output_price: '0' }],
    };
  }

  if (billingMode === 'token_tiered') {
    const tiers =
      mapping.tiered_pricing && mapping.tiered_pricing.length > 0
        ? mapping.tiered_pricing.map((tier) => ({
            max_input_tokens:
              tier.max_input_tokens === null || tier.max_input_tokens === undefined
                ? ''
                : String(tier.max_input_tokens),
            input_price: String(tier.input_price ?? 0),
            output_price: String(tier.output_price ?? 0),
          }))
        : [{ max_input_tokens: '', input_price: '0', output_price: '0' }];

    return {
      billing_mode: billingMode,
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: '0',
      tiers,
    };
  }

  return {
    billing_mode: 'token_flat',
    input_price: String(mapping.input_price ?? 0),
    output_price: String(mapping.output_price ?? 0),
    per_request_price: '0',
    per_image_price: '0',
    tiers: [{ max_input_tokens: '32768', input_price: '0', output_price: '0' }],
  };
}

export function ProviderModelBulkUpgradeDialog({
  open,
  onOpenChange,
  provider,
  currentModelName,
  mappings,
  loading = false,
  onSubmit,
}: ProviderModelBulkUpgradeDialogProps) {
  const t = useTranslations('providers');
  const tModels = useTranslations('models');
  const tCommon = useTranslations('common');

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    control,
  } = useForm<FormData>({
    defaultValues: {
      new_target_model_name: '',
      billing_mode: 'token_flat',
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: '0',
      tiers: [{ max_input_tokens: '32768', input_price: '0', output_price: '0' }],
    },
  });

  const { fields: tierFields, append: appendTier, remove: removeTier } = useFieldArray({
    control,
    name: 'tiers',
  });

  const billingMode = watch('billing_mode');

  useEffect(() => {
    if (!open) {
      return;
    }
    const pricingDefaults = buildDefaultPricing(mappings[0]);
    reset({
      new_target_model_name: currentModelName ?? '',
      ...pricingDefaults,
    });
  }, [currentModelName, mappings, open, reset]);

  const submit = (data: FormData) => {
    if (!provider || !currentModelName) {
      return;
    }

    const payload: ModelProviderBulkUpgradeRequest = {
      provider_id: provider.id,
      current_target_model_name: currentModelName,
      new_target_model_name: data.new_target_model_name.trim(),
      billing_mode: data.billing_mode,
      input_price: null,
      output_price: null,
      per_request_price: null,
      per_image_price: null,
      tiered_pricing: null,
    };

    if (data.billing_mode === 'per_request') {
      payload.per_request_price = Number(data.per_request_price.trim() || '0');
    } else if (data.billing_mode === 'per_image') {
      payload.per_image_price = Number(data.per_image_price.trim() || '0');
    } else if (data.billing_mode === 'token_tiered') {
      payload.tiered_pricing = (data.tiers || []).map((tier) => ({
        max_input_tokens: tier.max_input_tokens.trim() ? Number(tier.max_input_tokens.trim()) : null,
        input_price: Number(tier.input_price.trim() || '0'),
        output_price: Number(tier.output_price.trim() || '0'),
      }));
    } else {
      payload.input_price = Number(data.input_price.trim() || '0');
      payload.output_price = Number(data.output_price.trim() || '0');
    }

    onSubmit(payload);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[900px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('usedModels.upgrade.title')}</DialogTitle>
          <DialogDescription>
            {provider
              ? t('usedModels.upgrade.description', {
                  provider: provider.name,
                  model: currentModelName || '-',
                })
              : t('usedModels.noProviderSelected')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('usedModels.upgrade.columns.requestedModel')}</TableHead>
                  <TableHead>{t('usedModels.upgrade.columns.currentModel')}</TableHead>
                  <TableHead>{t('usedModels.upgrade.columns.currentBilling')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.map((mapping) => (
                  <TableRow key={mapping.id}>
                    <TableCell>
                      <code className="text-xs">{mapping.requested_model}</code>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs">{mapping.target_model_name}</code>
                    </TableCell>
                    <TableCell className="text-xs">
                      <BillingDisplay
                        billingMode={mapping.billing_mode}
                        inputPrice={mapping.input_price}
                        outputPrice={mapping.output_price}
                        perRequestPrice={mapping.per_request_price}
                        perImagePrice={mapping.per_image_price}
                        tieredPricing={mapping.tiered_pricing}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit(submit)}>
            <div className="space-y-2">
              <Label htmlFor="new_target_model_name">
                {t('usedModels.upgrade.newModelLabel')}
              </Label>
              <Input
                id="new_target_model_name"
                placeholder={t('usedModels.upgrade.newModelPlaceholder')}
                {...register('new_target_model_name', {
                  required: tModels('providerForm.targetModelRequired'),
                })}
              />
            </div>

            <ModelProviderBillingFields
              t={tModels}
              billingMode={billingMode}
              setBillingMode={(value) => setValue('billing_mode', value)}
              register={register}
              tierFields={tierFields}
              appendTier={appendTier}
              removeTier={removeTier}
            />

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
                {loading
                  ? tCommon('saving')
                  : t('usedModels.upgrade.confirm')}
              </Button>
            </DialogFooter>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}
