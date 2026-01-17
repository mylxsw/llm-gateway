/**
 * Model Mapping Form Component
 * Used for creating and editing model mappings
 */

'use client';

import React, { useEffect } from 'react';
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
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RuleBuilder } from '@/components/common';
import {
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  RuleSet,
  SelectionStrategy
} from '@/types';
import { isValidModelName } from '@/lib/utils';

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
  matching_rules: RuleSet | null;
  is_active: boolean;
  input_price: string;
  output_price: string;
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
      matching_rules: null,
      is_active: true,
      input_price: '',
      output_price: '',
    },
  });

  const isActive = watch('is_active');

  // Fill form data in edit mode
  useEffect(() => {
    if (model) {
      reset({
        requested_model: model.requested_model,
        strategy: model.strategy,
        matching_rules: model.matching_rules || null,
        is_active: model.is_active,
        input_price:
          model.input_price === null || model.input_price === undefined
            ? ''
            : String(model.input_price),
        output_price:
          model.output_price === null || model.output_price === undefined
            ? ''
            : String(model.output_price),
      });
    } else {
      reset({
        requested_model: '',
        strategy: 'round_robin',
        matching_rules: null,
        is_active: true,
        input_price: '',
        output_price: '',
      });
    }
  }, [model, reset]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    const submitData: ModelMappingCreate | ModelMappingUpdate = {
      strategy: data.strategy,
      is_active: data.is_active,
    };
    
    // requested_model required on creation
    if (!isEdit) {
      (submitData as ModelMappingCreate).requested_model = data.requested_model;
    }
    
    // Assign rules directly
    submitData.matching_rules = data.matching_rules || undefined;

    // Preserve existing capabilities on edit (field hidden in UI)
    if (isEdit && model?.capabilities) {
      submitData.capabilities = model.capabilities;
    }

    const inputPrice = data.input_price.trim();
    const outputPrice = data.output_price.trim();
    submitData.input_price = inputPrice ? Number(inputPrice) : null;
    submitData.output_price = outputPrice ? Number(outputPrice) : null;
    
    onSubmit(submitData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Model Mapping' : 'New Model Mapping'}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Requested Model Name */}
          <div className="space-y-2">
            <Label htmlFor="requested_model">
              Requested Model Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="requested_model"
              placeholder="e.g.: gpt-4, claude-3-opus"
              disabled={isEdit}
              {...register('requested_model', {
                required: !isEdit ? 'Requested model name is required' : false,
                validate: !isEdit
                  ? (v) => isValidModelName(v) || 'Model name can only contain letters, numbers, underscores, hyphens, and dots'
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
                Model name is the primary key and cannot be modified
              </p>
            )}
          </div>

          

          {/* Pricing */}
          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="mb-2 text-sm font-medium">Pricing (USD / 1M tokens)</div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="input_price">Input Price</Label>
                <Input
                  id="input_price"
                  type="number"
                  min={0}
                  step="0.0001"
                  placeholder="e.g. 5"
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
                  placeholder="e.g. 15"
                  {...register('output_price')}
                />
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Used as model fallback price when no provider override exists; empty means unconfigured.
            </p>
          </div>

          {/* Matching Rules */}
          <div className="space-y-2">
            <Label>Matching Rules (Beta)</Label>
            <Controller
              name="matching_rules"
              control={control}
              render={({ field }) => (
                <RuleBuilder
                  value={field.value || undefined}
                  onChange={field.onChange}
                />
              )}
            />
          </div>

          {/* Strategy */}
          <div className="space-y-2">
            <Label htmlFor="strategy">Selection Strategy</Label>
            <Controller
              name="strategy"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                >
                  <SelectTrigger id="strategy">
                    <SelectValue placeholder="Select strategy" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="round_robin">
                      <div className="flex flex-col">
                        <span className="font-medium">Round Robin</span>
                        <span className="text-xs text-muted-foreground">
                          Distribute requests evenly across providers
                        </span>
                      </div>
                    </SelectItem>
                    <SelectItem value="cost_first">
                      <div className="flex flex-col">
                        <span className="font-medium">Cost First</span>
                        <span className="text-xs text-muted-foreground">
                          Prioritize lowest-cost providers based on input tokens
                        </span>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
            <p className="text-sm text-muted-foreground">
              Round Robin: Evenly distributes requests. Cost First: Selects provider with lowest estimated cost.
            </p>
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
            <Button type="submit" disabled={loading}>
              {loading ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
