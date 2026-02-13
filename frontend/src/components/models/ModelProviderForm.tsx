/**
 * Model-Provider Mapping Form Component
 * Used for configuring providers for a model
 */

'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useTranslations } from 'next-intl';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
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
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { RuleBuilder } from '@/components/common';
import { BillingDisplay } from '@/components/models/BillingDisplay';
import { ModelProviderBillingFields } from '@/components/models/ModelProviderBillingFields';
import { toast } from 'sonner';
import { getModelProviderPricingHistory } from '@/lib/api';
import { useProviderModels } from '@/lib/hooks';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';
import {
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  ModelProviderPricingHistoryItem,
  ModelType,
  Provider,
  RuleSet,
} from '@/types';

interface ModelProviderFormProps {
  /** Whether dialog is open */
  open: boolean;
  /** Dialog close callback */
  onOpenChange: (open: boolean) => void;
  /** Current requested model name */
  requestedModel: string;
  /** Available provider list */
  providers: Provider[];
  /** Default prices from model fallback (for create mode prefill) */
  defaultPrices?: { input_price?: number | null; output_price?: number | null };
  /** Mapping data for edit mode */
  mapping?: ModelMappingProvider | null;
  /** Parent model type */
  modelType: ModelType;
  /** Submit callback */
  onSubmit: (data: ModelMappingProviderCreate | ModelMappingProviderUpdate) => void;
  /** Loading state */
  loading?: boolean;
}

/** Form Field Definition */
interface FormData {
  provider_id: string;
  target_model_name: string;
  provider_rules: RuleSet | null;
  billing_mode: 'token_flat' | 'token_tiered' | 'per_request';
  // token_flat
  input_price: string;
  output_price: string;
  // per_request
  per_request_price: string;
  // token_tiered
  tiers: Array<{ max_input_tokens: string; input_price: string; output_price: string }>;
  priority: number;
  weight: number;
  is_active: boolean;
}

/**
 * Model-Provider Mapping Form Component
 */
export function ModelProviderForm({
  open,
  onOpenChange,
  requestedModel,
  providers,
  defaultPrices,
  mapping,
  modelType,
  onSubmit,
  loading = false,
}: ModelProviderFormProps) {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');
  const { configs: protocolConfigs } = useProviderProtocolConfigs();
  // Check if edit mode
  const isEdit = !!mapping;
  
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
      provider_id: '',
      target_model_name: '',
      provider_rules: null,
      billing_mode: 'token_flat',
      input_price: '',
      output_price: '',
      per_request_price: '',
      tiers: [{ max_input_tokens: '32768', input_price: '', output_price: '' }],
      priority: 0,
      weight: 1,
      is_active: true,
    },
  });

  const { fields: tierFields, append: appendTier, remove: removeTier } = useFieldArray({
    control,
    name: 'tiers',
  });

  const providerId = watch('provider_id');
  const isActive = watch('is_active');
  const billingMode = watch('billing_mode');
  const targetModelName = watch('target_model_name');
  const supportsBilling = modelType === 'chat' || modelType === 'embedding';
  const [providerModels, setProviderModels] = useState<string[]>([]);
  const [providerModelDialogOpen, setProviderModelDialogOpen] = useState(false);
  const [selectedProviderModel, setSelectedProviderModel] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [priceHistoryDialogOpen, setPriceHistoryDialogOpen] = useState(false);
  const [priceHistoryItems, setPriceHistoryItems] = useState<ModelProviderPricingHistoryItem[]>(
    []
  );
  const [selectedPriceHistoryId, setSelectedPriceHistoryId] = useState<number | null>(null);
  const providerModelQuery = useProviderModels(Number(providerId), { enabled: false });

  // Fill form data in edit mode
  useEffect(() => {
    if (mapping) {
      const mode = (mapping.billing_mode || 'token_flat') as
        | 'token_flat'
        | 'token_tiered'
        | 'per_request';

      reset({
        provider_id: String(mapping.provider_id),
        target_model_name: mapping.target_model_name,
        provider_rules: mapping.provider_rules || null,
        billing_mode: mode,
        input_price:
          mapping.input_price === null || mapping.input_price === undefined
            ? defaultPrices?.input_price === null || defaultPrices?.input_price === undefined
              ? '0'
              : String(defaultPrices.input_price)
            : String(mapping.input_price),
        output_price:
          mapping.output_price === null || mapping.output_price === undefined
            ? defaultPrices?.output_price === null || defaultPrices?.output_price === undefined
              ? '0'
              : String(defaultPrices.output_price)
            : String(mapping.output_price),
        per_request_price:
          mapping.per_request_price === null || mapping.per_request_price === undefined
            ? '0'
            : String(mapping.per_request_price),
        tiers:
          mapping.tiered_pricing && mapping.tiered_pricing.length > 0
            ? mapping.tiered_pricing.map((t) => ({
                max_input_tokens:
                  t.max_input_tokens === null || t.max_input_tokens === undefined
                    ? ''
                    : String(t.max_input_tokens),
                input_price: String(t.input_price),
                output_price: String(t.output_price),
              }))
            : [
                {
                  max_input_tokens: '32768',
                  input_price:
                    mapping.input_price === null || mapping.input_price === undefined
                      ? '0'
                      : String(mapping.input_price),
                  output_price:
                    mapping.output_price === null || mapping.output_price === undefined
                      ? '0'
                      : String(mapping.output_price),
                },
              ],
        priority: mapping.priority,
        weight: mapping.weight,
        is_active: mapping.is_active,
      });
    } else {
      const fallbackInputPrice =
        defaultPrices?.input_price === null || defaultPrices?.input_price === undefined
          ? '0'
          : String(defaultPrices.input_price);
      const fallbackOutputPrice =
        defaultPrices?.output_price === null || defaultPrices?.output_price === undefined
          ? '0'
          : String(defaultPrices.output_price);
      reset({
        provider_id: '',
        target_model_name: '',
        provider_rules: null,
        billing_mode: 'token_flat',
        input_price: fallbackInputPrice,
        output_price: fallbackOutputPrice,
        per_request_price: '0',
        tiers: [
          {
            max_input_tokens: '32768',
            input_price: fallbackInputPrice,
            output_price: fallbackOutputPrice,
          },
        ],
        priority: 0,
        weight: 1,
        is_active: true,
      });
    }
  }, [defaultPrices?.input_price, defaultPrices?.output_price, mapping, reset]);

  const handleOpenProviderModelDialog = async () => {
    if (!providerId) {
      toast.error(t('providerForm.selectProviderFirst'));
      return;
    }
    const result = await providerModelQuery.refetch();
    const data = result.data;
    if (!data) {
      toast.error(t('providerForm.loadProviderModelsFailed'));
      return;
    }
    if (!data.success) {
      toast.error(data.error?.message || t('providerForm.loadProviderModelsFailed'));
      return;
    }
    const models = data.models || [];
    setProviderModels(models);
    setSelectedProviderModel(models[0] || '');
    setProviderModelDialogOpen(true);
  };

  const handleConfirmProviderModel = () => {
    if (!selectedProviderModel) {
      return;
    }
    setValue('target_model_name', selectedProviderModel, {
      shouldValidate: true,
      shouldDirty: true,
    });
    setProviderModelDialogOpen(false);
  };

  const applyPriceHistory = (item: ModelProviderPricingHistoryItem) => {
    const resolvedBillingMode = (item.billing_mode || 'token_flat') as FormData['billing_mode'];
    setValue('billing_mode', resolvedBillingMode);
    if (resolvedBillingMode === 'per_request') {
      setValue('per_request_price', String(item.per_request_price ?? 0));
      return;
    }
    if (resolvedBillingMode === 'token_tiered') {
      const tiers =
        item.tiered_pricing && item.tiered_pricing.length > 0
          ? item.tiered_pricing.map((tier) => ({
              max_input_tokens:
                tier.max_input_tokens === null || tier.max_input_tokens === undefined
                  ? ''
                  : String(tier.max_input_tokens),
              input_price: String(tier.input_price ?? 0),
              output_price: String(tier.output_price ?? 0),
            }))
          : [{ max_input_tokens: '', input_price: '0', output_price: '0' }];
      setValue('tiers', tiers);
      return;
    }
    setValue('input_price', String(item.input_price ?? 0));
    setValue('output_price', String(item.output_price ?? 0));
  };

  const handleLoadPriceHistory = async () => {
    const normalizedTargetModel = targetModelName.trim();
    if (!normalizedTargetModel) {
      toast.error(t('providerForm.targetModelRequired'));
      return;
    }

    setHistoryLoading(true);
    try {
      const result = await getModelProviderPricingHistory(normalizedTargetModel);
      if (result.items.length === 0) {
        toast.info(t('providerForm.noHistoryCandidates'));
        return;
      }
      setPriceHistoryItems(result.items);
      setSelectedPriceHistoryId(result.items[0].id);
      setPriceHistoryDialogOpen(true);
    } catch {
      toast.error(t('providerForm.loadHistoryFailed'));
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleApplyPriceHistory = () => {
    if (selectedPriceHistoryId === null) {
      return;
    }
    const selected = priceHistoryItems.find((item) => item.id === selectedPriceHistoryId);
    if (!selected) {
      return;
    }
    applyPriceHistory(selected);
    setPriceHistoryDialogOpen(false);
  };

  // Submit form
  const onFormSubmit = (data: FormData) => {
    const billingMode = data.billing_mode;
    const nonBillingOverride = {
      billing_mode: 'token_flat' as const,
      input_price: 0,
      output_price: 0,
      per_request_price: null,
      tiered_pricing: null,
    };

    const buildFlatPricing = () => {
      const inputPrice = data.input_price.trim();
      const outputPrice = data.output_price.trim();
      return {
        input_price: Number(inputPrice || '0'),
        output_price: Number(outputPrice || '0'),
      };
    };

    const buildTieredPricing = () => {
      return (data.tiers || []).map((t) => {
        const inputPrice = Number((t.input_price || '0').trim() || '0');
        const outputPrice = Number((t.output_price || '0').trim() || '0');
        const maxStr = t.max_input_tokens.trim();
        const maxInputTokens = maxStr === '' ? null : Number(maxStr);
        return {
          max_input_tokens: maxInputTokens,
          input_price: inputPrice,
          output_price: outputPrice,
        };
      });
    };

    if (isEdit) {
      // Update mode
      const submitData: ModelMappingProviderUpdate = {
        target_model_name: data.target_model_name,
        priority: data.priority,
        weight: data.weight,
        is_active: data.is_active,
      };

      if (supportsBilling) {
        submitData.billing_mode = billingMode;
        if (billingMode === 'per_request') {
          const perReq = data.per_request_price.trim();
          submitData.per_request_price = perReq ? Number(perReq) : 0;
          submitData.input_price = null;
          submitData.output_price = null;
          submitData.tiered_pricing = null;
        } else if (billingMode === 'token_tiered') {
          submitData.tiered_pricing = buildTieredPricing();
          submitData.per_request_price = null;
          submitData.input_price = null;
          submitData.output_price = null;
        } else {
          const flat = buildFlatPricing();
          submitData.input_price = flat.input_price;
          submitData.output_price = flat.output_price;
          submitData.per_request_price = null;
          submitData.tiered_pricing = null;
        }
      } else {
        submitData.billing_mode = nonBillingOverride.billing_mode;
        submitData.input_price = nonBillingOverride.input_price;
        submitData.output_price = nonBillingOverride.output_price;
        submitData.per_request_price = nonBillingOverride.per_request_price;
        submitData.tiered_pricing = nonBillingOverride.tiered_pricing;
      }
      
      submitData.provider_rules = data.provider_rules || undefined;
      
      onSubmit(submitData);
    } else {
      // Create mode
      const submitData: ModelMappingProviderCreate = {
        requested_model: requestedModel,
        provider_id: Number(data.provider_id),
        target_model_name: data.target_model_name,
        priority: data.priority,
        weight: data.weight,
        is_active: data.is_active,
      };

      if (supportsBilling) {
        submitData.billing_mode = billingMode;
        if (billingMode === 'per_request') {
          const perReq = data.per_request_price.trim();
          submitData.per_request_price = perReq ? Number(perReq) : 0;
          submitData.input_price = null;
          submitData.output_price = null;
          submitData.tiered_pricing = null;
        } else if (billingMode === 'token_tiered') {
          submitData.tiered_pricing = buildTieredPricing();
          submitData.per_request_price = null;
          submitData.input_price = null;
          submitData.output_price = null;
        } else {
          const flat = buildFlatPricing();
          submitData.input_price = flat.input_price;
          submitData.output_price = flat.output_price;
          submitData.per_request_price = null;
          submitData.tiered_pricing = null;
        }
      } else {
        submitData.billing_mode = nonBillingOverride.billing_mode;
        submitData.input_price = nonBillingOverride.input_price;
        submitData.output_price = nonBillingOverride.output_price;
        submitData.per_request_price = nonBillingOverride.per_request_price;
        submitData.tiered_pricing = nonBillingOverride.tiered_pricing;
      }
      
      submitData.provider_rules = data.provider_rules || undefined;
      
      onSubmit(submitData);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t('providerForm.editTitle') : t('providerForm.newTitle')}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Requested Model Name (Read Only) */}
          <div className="space-y-2">
            <Label>{t('providerForm.requestedModel')}</Label>
            <Input value={requestedModel} disabled />
          </div>

          {/* Provider Selection */}
          <div className="space-y-2">
            <Label>
              {t('providerForm.provider')} <span className="text-destructive">*</span>
            </Label>
            {providers.length === 0 && !isEdit ? (
              <div className="text-sm text-muted-foreground p-2 border rounded-md bg-muted/50">
                {t.rich('providerForm.noProviders', {
                  link: (chunks) => (
                    <Link href="/providers" className="text-primary hover:underline mx-1">
                      {chunks}
                    </Link>
                  ),
                })}
              </div>
            ) : (
              <Select
                value={providerId}
                onValueChange={(value) => setValue('provider_id', value)}
                disabled={isEdit}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('providerForm.selectProvider')} />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.id} value={String(provider.id)}>
                      {provider.name} ({getProviderProtocolLabel(provider.protocol, protocolConfigs)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {!providerId && !isEdit && providers.length > 0 && (
              <p className="text-sm text-destructive">
                {t('providerForm.selectProviderError')}
              </p>
            )}
          </div>

          {/* Target Model Name */}
          <div className="space-y-2">
            <Label htmlFor="target_model_name">
              {t('providerForm.targetModel')} <span className="text-destructive">*</span>
            </Label>
            <div className="flex gap-2">
              <Input
                id="target_model_name"
                placeholder={t('providerForm.targetModelPlaceholder')}
                {...register('target_model_name', {
                  required: t('providerForm.targetModelRequired'),
                })}
              />
              <Button
                type="button"
                variant="outline"
                onClick={handleOpenProviderModelDialog}
                disabled={!providerId || providerModelQuery.isFetching}
              >
                {providerModelQuery.isFetching
                  ? t('providerForm.loading')
                  : t('providerForm.pickFromProvider')}
              </Button>
            </div>
            {errors.target_model_name && (
              <p className="text-sm text-destructive">
                {errors.target_model_name.message}
              </p>
            )}
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
              historyLoading={historyLoading}
              onLoadHistory={handleLoadPriceHistory}
              showHistoryButton
            />
          )}

          {/* Priority and Weight */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="priority">{t('providerForm.priority')}</Label>
              <Input
                id="priority"
                type="number"
                min={0}
                {...register('priority', { valueAsNumber: true })}
              />
              <p className="text-sm text-muted-foreground">
                {t('providerForm.priorityHint')}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="weight">{t('providerForm.weight')}</Label>
              <Input
                id="weight"
                type="number"
                min={1}
                {...register('weight', { valueAsNumber: true })}
              />
            </div>
          </div>

          {/* Provider Level Rules */}
          <div className="space-y-2">
            <Label>{t('providerForm.providerRules')}</Label>
            <Controller
              name="provider_rules"
              control={control}
              render={({ field }) => (
                <RuleBuilder
                  value={field.value || undefined}
                  onChange={field.onChange}
                />
              )}
            />
          </div>

          {/* Status */}
          <div className="flex items-center justify-between">
            <Label htmlFor="is_active">{t('providerForm.enabledStatus')}</Label>
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
            <Button
              type="submit"
              disabled={loading || (!isEdit && !providerId)}
            >
              {loading ? tCommon('saving') : tCommon('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
      <Dialog open={providerModelDialogOpen} onOpenChange={setProviderModelDialogOpen}>
        <DialogContent className="sm:max-w-[560px]">
          <DialogHeader>
            <DialogTitle>{t('providerForm.selectProviderModelTitle')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-md border p-2 max-h-64 overflow-y-auto">
              {providerModels.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t('providerForm.noProviderModels')}
                </p>
              ) : (
                <div className="space-y-1">
                  {providerModels.map((modelName) => {
                    const isSelected = modelName === selectedProviderModel;
                    return (
                      <button
                        type="button"
                        key={modelName}
                        className={`w-full text-left px-3 py-2 rounded-md border transition ${
                          isSelected
                            ? 'bg-primary/10 border-primary'
                            : 'border-transparent hover:border-border hover:bg-muted/40'
                        }`}
                        onClick={() => setSelectedProviderModel(modelName)}
                      >
                        <span className="font-mono text-sm">{modelName}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setProviderModelDialogOpen(false)}
            >
              {tCommon('cancel')}
            </Button>
            <Button
              type="button"
              onClick={handleConfirmProviderModel}
              disabled={!selectedProviderModel}
            >
              {t('providerForm.useSelectedModel')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={priceHistoryDialogOpen} onOpenChange={setPriceHistoryDialogOpen}>
        <DialogContent className="sm:max-w-[720px]">
          <DialogHeader>
            <DialogTitle>{t('providerForm.historyDialogTitle')}</DialogTitle>
            <DialogDescription>{t('providerForm.historyDialogDescription')}</DialogDescription>
          </DialogHeader>
          <div className="max-h-[360px] overflow-y-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[56px]">{t('providerForm.use')}</TableHead>
                  <TableHead>{t('providerForm.provider')}</TableHead>
                  <TableHead>{t('providerForm.targetModel')}</TableHead>
                  <TableHead>{t('providerForm.billingMode')}</TableHead>
                  <TableHead>{t('providerForm.sourceModel')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {priceHistoryItems.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedPriceHistoryId(item.id)}
                  >
                    <TableCell>
                      <input
                        type="radio"
                        name="price-history-candidate"
                        checked={selectedPriceHistoryId === item.id}
                        onChange={() => setSelectedPriceHistoryId(item.id)}
                        aria-label={item.provider_name}
                      />
                    </TableCell>
                    <TableCell>{item.provider_name}</TableCell>
                    <TableCell>
                      <code className="text-xs">{item.target_model_name}</code>
                    </TableCell>
                    <TableCell className="text-xs">
                      <BillingDisplay
                        billingMode={item.billing_mode}
                        inputPrice={item.input_price}
                        outputPrice={item.output_price}
                        perRequestPrice={item.per_request_price}
                        tieredPricing={item.tiered_pricing}
                      />
                    </TableCell>
                    <TableCell>
                      <code className="text-xs">{item.requested_model}</code>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setPriceHistoryDialogOpen(false)}
            >
              {tCommon('cancel')}
            </Button>
            <Button
              type="button"
              onClick={handleApplyPriceHistory}
              disabled={selectedPriceHistoryId === null}
            >
              {t('providerForm.useSelectedPricing')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}
