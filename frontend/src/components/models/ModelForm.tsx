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
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { RuleBuilder } from '@/components/common';
import { ModelMapping, ModelMappingCreate, ModelMappingUpdate, RuleSet } from '@/types';
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
  strategy: string;
  matching_rules: RuleSet | null;
  capabilities: string;
  is_active: boolean;
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
      capabilities: '',
      is_active: true,
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
        capabilities: model.capabilities
          ? JSON.stringify(model.capabilities, null, 2)
          : '',
        is_active: model.is_active,
      });
    } else {
      reset({
        requested_model: '',
        strategy: 'round_robin',
        matching_rules: null,
        capabilities: '',
        is_active: true,
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
    
    // Parse JSON field
    if (data.capabilities.trim()) {
      try {
        submitData.capabilities = JSON.parse(data.capabilities);
      } catch {
        // Ignore parse errors
      }
    }
    
    onSubmit(submitData);
  };

  // Validate JSON format
  const validateJson = (value: string) => {
    if (!value.trim()) return true;
    try {
      JSON.parse(value);
      return true;
    } catch {
      return 'Please enter valid JSON format';
    }
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

          {/* Strategy */}
          <div className="space-y-2">
            <Label htmlFor="strategy">Select Strategy</Label>
            <Input
              id="strategy"
              value="round_robin"
              disabled
              {...register('strategy')}
            />
            <p className="text-sm text-muted-foreground">
              Currently only supports Round Robin strategy (round_robin)
            </p>
          </div>

          {/* Matching Rules */}
          <div className="space-y-2">
            <Label>Matching Rules</Label>
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

          {/* Capabilities Description */}
          <div className="space-y-2">
            <Label htmlFor="capabilities">
              Capabilities Description <span className="text-muted-foreground">(JSON, Optional)</span>
            </Label>
            <Textarea
              id="capabilities"
              placeholder='{"streaming": true, "function_calling": true}'
              rows={3}
              {...register('capabilities', {
                validate: validateJson,
              })}
            />
            {errors.capabilities && (
              <p className="text-sm text-destructive">
                {errors.capabilities.message}
              </p>
            )}
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
