/**
 * API Key Form Component
 * Used for creating and editing API Keys
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Copy, Check, AlertCircle } from 'lucide-react';
import { ApiKey, ApiKeyCreate, ApiKeyUpdate } from '@/types';
import { isValidKeyName, copyToClipboard } from '@/lib/utils';

interface ApiKeyFormProps {
  /** Whether dialog is open */
  open: boolean;
  /** Dialog close callback */
  onOpenChange: (open: boolean) => void;
  /** API Key data for edit mode */
  apiKey?: ApiKey | null;
  /** Submit callback */
  onSubmit: (data: ApiKeyCreate | ApiKeyUpdate) => void;
  /** Loading state */
  loading?: boolean;
  /** Newly created API Key (for displaying full key value) */
  createdKey?: ApiKey | null;
}

/** Form Field Definition */
interface FormData {
  key_name: string;
  is_active: boolean;
}

/**
 * API Key Form Component
 */
export function ApiKeyForm({
  open,
  onOpenChange,
  apiKey,
  onSubmit,
  loading = false,
  createdKey,
}: ApiKeyFormProps) {
  // Check if edit mode
  const isEdit = !!apiKey;
  const [copied, setCopied] = useState(false);
  
  // Form control
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      key_name: '',
      is_active: true,
    },
  });

  const isActive = watch('is_active');

  // Fill form data in edit mode
  useEffect(() => {
    if (apiKey) {
      reset({
        key_name: apiKey.key_name,
        is_active: apiKey.is_active,
      });
    } else {
      reset({
        key_name: '',
        is_active: true,
      });
    }
    setCopied(false);
  }, [apiKey, reset, open]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    if (isEdit) {
      onSubmit({
        key_name: data.key_name,
        is_active: data.is_active,
      });
    } else {
      onSubmit({
        key_name: data.key_name,
      });
    }
  };

  // Copy API Key
  const handleCopy = async () => {
    if (createdKey?.key_value) {
      const success = await copyToClipboard(createdKey.key_value);
      if (success) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    }
  };

  // Display newly created Key
  if (createdKey) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>API Key Created Successfully</DialogTitle>
            <DialogDescription>
              Please copy and save the following API Key immediately. You will not be able to see the full key again after closing.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="flex items-center gap-2 rounded-md border bg-muted/50 p-3">
              <AlertCircle className="h-5 w-5 text-yellow-500" />
              <span className="text-sm text-muted-foreground">
                This is the only time the full Key will be displayed
              </span>
            </div>
            
            <div className="space-y-2">
              <Label>API Key Name</Label>
              <Input value={createdKey.key_name} disabled />
            </div>
            
            <div className="space-y-2">
              <Label>API Key</Label>
              <div className="flex gap-2">
                <Input
                  value={createdKey.key_value}
                  readOnly
                  className="font-mono text-sm"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>
              I have copied and saved it
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit API Key' : 'New API Key'}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="key_name">
              Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="key_name"
              placeholder="Enter API Key name, e.g.: Production"
              {...register('key_name', {
                required: 'Name is required',
                validate: (v) => isValidKeyName(v) || 'Invalid name format',
              })}
            />
            {errors.key_name && (
              <p className="text-sm text-destructive">{errors.key_name.message}</p>
            )}
          </div>

          {/* Status */}
          {isEdit && (
            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">Enabled Status</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={(checked) => setValue('is_active', checked)}
              />
            </div>
          )}

          {!isEdit && (
            <p className="text-sm text-muted-foreground">
              API Key will be automatically generated by the system, please save it immediately after creation
            </p>
          )}

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
              {loading ? 'Saving...' : isEdit ? 'Save' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}