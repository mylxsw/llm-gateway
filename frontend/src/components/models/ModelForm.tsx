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
      model_type: 'chat',
      is_active: true,
      input_price: '',
      output_price: '',
    },
  });

  const isActive = watch('is_active');
  const modelType = watch('model_type');
  const strategy = watch('strategy');
  const supportsBilling = modelType === 'chat' || modelType === 'embedding';

  useEffect(() => {
    if (!supportsBilling && strategy === 'cost_first') {
      setValue('strategy', 'round_robin');
    }
  }, [supportsBilling, strategy, setValue]);

  // Fill form data in edit mode
  useEffect(() => {
    if (model) {
      reset({
        requested_model: model.requested_model,
        strategy: model.strategy,
        model_type: model.model_type ?? 'chat',
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
        model_type: 'chat',
        is_active: true,
        input_price: '',
        output_price: '',
      });
    }
  }, [model, reset]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    const resolvedStrategy = supportsBilling ? data.strategy : 'round_robin';
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
      const inputPrice = data.input_price.trim();
      const outputPrice = data.output_price.trim();
      submitData.input_price = inputPrice ? Number(inputPrice) : null;
      submitData.output_price = outputPrice ? Number(outputPrice) : null;
    } else {
      submitData.input_price = null;
      submitData.output_price = null;
    }

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
              placeholder="e.g.: gpt-4, claude-3-opus, coding/kimi"
              disabled={isEdit}
              {...register('requested_model', {
                required: !isEdit ? 'Requested model name is required' : false,
                validate: !isEdit
                  ? (v) =>
                      isValidModelName(v) ||
                      'Model name can only contain letters, numbers, underscores, hyphens, dots, and slashes'
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

          

          {/* Model Type */}
          <div className="space-y-2">
            <Label>Model Type</Label>
            <Controller
              name="model_type"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select model type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="chat">Chat</SelectItem>
                    <SelectItem value="speech">Speech</SelectItem>
                    <SelectItem value="transcription">Transcription</SelectItem>
                    <SelectItem value="embedding">Embedding</SelectItem>
                    <SelectItem value="images">Images</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {/* Pricing */}
          {supportsBilling && (
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
          )}

          {/* Strategy */}
          <div className="space-y-3">
            <Label>Selection Strategy</Label>
            <Controller
              name="strategy"
              control={control}
              render={({ field }) => (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
                          <span className="font-semibold text-base">Round Robin</span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground pl-8">
                        Evenly distribute requests across all available providers
                      </p>
                      <div className="pl-8 pt-1">
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs">
                          <span>⚖️</span>
                          <span>Load Balancing</span>
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
                          <span className="font-semibold text-base">Cost First</span>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground pl-8">
                        Prioritize providers with the lowest estimated cost
                      </p>
                      <div className="pl-8 pt-1">
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs">
                          <span>📊</span>
                          <span>Cost Optimization</span>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              )}
            />
            <p className="text-xs text-muted-foreground">
              💡 Choose how the gateway selects providers for this model
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
