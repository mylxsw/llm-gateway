/**
 * Model-Provider Mapping Form Component
 * Used for configuring providers for a model
 */

'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { useForm, Controller } from 'react-hook-form';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { RuleBuilder } from '@/components/common';
import {
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
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
  input_price: string;
  output_price: string;
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
  onSubmit,
  loading = false,
}: ModelProviderFormProps) {
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
      input_price: '',
      output_price: '',
      priority: 0,
      weight: 1,
      is_active: true,
    },
  });

  const providerId = watch('provider_id');
  const isActive = watch('is_active');

  // Fill form data in edit mode
  useEffect(() => {
    if (mapping) {
      reset({
        provider_id: String(mapping.provider_id),
        target_model_name: mapping.target_model_name,
        provider_rules: mapping.provider_rules || null,
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
        priority: mapping.priority,
        weight: mapping.weight,
        is_active: mapping.is_active,
      });
    } else {
      reset({
        provider_id: '',
        target_model_name: '',
        provider_rules: null,
        input_price:
          defaultPrices?.input_price === null || defaultPrices?.input_price === undefined
            ? '0'
            : String(defaultPrices.input_price),
        output_price:
          defaultPrices?.output_price === null || defaultPrices?.output_price === undefined
            ? '0'
            : String(defaultPrices.output_price),
        priority: 0,
        weight: 1,
        is_active: true,
      });
    }
  }, [defaultPrices?.input_price, defaultPrices?.output_price, mapping, reset]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    const inputPrice = data.input_price.trim();
    const outputPrice = data.output_price.trim();
    if (isEdit) {
      // Update mode
      const submitData: ModelMappingProviderUpdate = {
        target_model_name: data.target_model_name,
        input_price: inputPrice ? Number(inputPrice) : null,
        output_price: outputPrice ? Number(outputPrice) : null,
        priority: data.priority,
        weight: data.weight,
        is_active: data.is_active,
      };
      
      submitData.provider_rules = data.provider_rules || undefined;
      
      onSubmit(submitData);
    } else {
      // Create mode
      const submitData: ModelMappingProviderCreate = {
        requested_model: requestedModel,
        provider_id: Number(data.provider_id),
        target_model_name: data.target_model_name,
        input_price: inputPrice ? Number(inputPrice) : null,
        output_price: outputPrice ? Number(outputPrice) : null,
        priority: data.priority,
        weight: data.weight,
        is_active: data.is_active,
      };
      
      submitData.provider_rules = data.provider_rules || undefined;
      
      onSubmit(submitData);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit Provider Configuration' : 'Add Provider Configuration'}
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Requested Model Name (Read Only) */}
          <div className="space-y-2">
            <Label>Requested Model Name</Label>
            <Input value={requestedModel} disabled />
          </div>

          {/* Provider Selection */}
          <div className="space-y-2">
            <Label>
              Provider <span className="text-destructive">*</span>
            </Label>
            {providers.length === 0 && !isEdit ? (
              <div className="text-sm text-muted-foreground p-2 border rounded-md bg-muted/50">
                No available providers, please
                <Link href="/providers" className="text-primary hover:underline mx-1">
                  create a provider
                </Link>
                first.
              </div>
            ) : (
              <Select
                value={providerId}
                onValueChange={(value) => setValue('provider_id', value)}
                disabled={isEdit}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((provider) => (
                    <SelectItem key={provider.id} value={String(provider.id)}>
                      {provider.name} ({provider.protocol})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {!providerId && !isEdit && providers.length > 0 && (
              <p className="text-sm text-destructive">Please select a provider</p>
            )}
          </div>

          {/* Target Model Name */}
          <div className="space-y-2">
            <Label htmlFor="target_model_name">
              Target Model Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="target_model_name"
              placeholder="Actual model name used by this provider, e.g. gpt-4-0613"
              {...register('target_model_name', {
                required: 'Target model name is required',
              })}
            />
            {errors.target_model_name && (
              <p className="text-sm text-destructive">
                {errors.target_model_name.message}
              </p>
            )}
          </div>

          {/* Pricing Override */}
          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="mb-2 text-sm font-medium">Price Override (USD / 1,000,000 tokens)</div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="input_price">Input Price</Label>
                <Input
                  id="input_price"
                  type="number"
                  min={0}
                  step="0.0001"
                  {...register('input_price')}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="output_price">Output Price</Label>
                <Input
                  id="output_price"
                  type="number"
                  min={0}
                  step="0.0001"
                  {...register('output_price')}
                />
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Used when this request routes to the selected provider; empty means unconfigured.
            </p>
          </div>

          {/* Priority and Weight */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="priority">Priority</Label>
              <Input
                id="priority"
                type="number"
                min={0}
                {...register('priority', { valueAsNumber: true })}
              />
              <p className="text-sm text-muted-foreground">Lower value means higher priority</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="weight">Weight</Label>
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
            <Label>Provider Level Rules</Label>
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
            <Label htmlFor="is_active">Enabled Status</Label>
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
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading || (!isEdit && !providerId)}
            >
              {loading ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
