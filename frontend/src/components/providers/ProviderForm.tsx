/**
 * Provider Form Component
 * Used for creating and editing providers
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Plus, Trash2 } from 'lucide-react';
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
import { Provider, ProviderCreate, ProviderUpdate, ProtocolType } from '@/types';
import { isValidUrl, isNotEmpty } from '@/lib/utils';

interface ProviderFormProps {
  /** Whether dialog is open */
  open: boolean;
  /** Dialog close callback */
  onOpenChange: (open: boolean) => void;
  /** Provider data for edit mode */
  provider?: Provider | null;
  /** Submit callback */
  onSubmit: (data: ProviderCreate | ProviderUpdate) => void;
  /** Loading state */
  loading?: boolean;
}

/** Form Field Definition */
interface FormData {
  name: string;
  base_url: string;
  protocol: ProtocolType;
  api_type: string;
  api_key: string;
  is_active: boolean;
}

/** Protocol Options */
const PROTOCOL_OPTIONS: { value: ProtocolType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
];

/** API Type Options */
const API_TYPE_OPTIONS = [
  { value: 'chat', label: 'Chat Completions' },
  { value: 'completion', label: 'Text Completions' },
  { value: 'embedding', label: 'Embeddings' },
];

/**
 * Provider Form Component
 */
export function ProviderForm({
  open,
  onOpenChange,
  provider,
  onSubmit,
  loading = false,
}: ProviderFormProps) {
  // Check if edit mode
  const isEdit = !!provider;
  
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
      name: '',
      base_url: '',
      protocol: 'openai',
      api_type: 'chat',
      api_key: '',
      is_active: true,
    },
  });

  // Watch form values
  const protocol = watch('protocol');
  const isActive = watch('is_active');
  
  // Extra headers state
  const [extraHeaders, setExtraHeaders] = useState<{ key: string; value: string }[]>([]);

  // Add header
  const addHeader = () => {
    setExtraHeaders([...extraHeaders, { key: '', value: '' }]);
  };

  // Remove header
  const removeHeader = (index: number) => {
    const newHeaders = [...extraHeaders];
    newHeaders.splice(index, 1);
    setExtraHeaders(newHeaders);
  };

  // Update header
  const updateHeader = (index: number, field: 'key' | 'value', value: string) => {
    const newHeaders = [...extraHeaders];
    newHeaders[index][field] = value;
    setExtraHeaders(newHeaders);
  };

  // Fill form data in edit mode
  useEffect(() => {
    if (provider) {
      reset({
        name: provider.name,
        base_url: provider.base_url,
        protocol: provider.protocol,
        api_type: provider.api_type,
        api_key: '', // API Key not echoed
        is_active: provider.is_active,
      });
      
      // Fill extra headers
      if (provider.extra_headers) {
        setExtraHeaders(
          Object.entries(provider.extra_headers).map(([key, value]) => ({
            key,
            value,
          }))
        );
      } else {
        setExtraHeaders([]);
      }
    } else {
      reset({
        name: '',
        base_url: '',
        protocol: 'openai',
        api_type: 'chat',
        api_key: '',
        is_active: true,
      });
      setExtraHeaders([]);
    }
  }, [provider, reset]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    // Handle extra headers
    const headers: Record<string, string> = {};
    extraHeaders.forEach(({ key, value }) => {
      if (key && value) {
        headers[key] = value;
      }
    });

    // Filter out empty strings
    const submitData: ProviderCreate | ProviderUpdate = {
      name: data.name,
      base_url: data.base_url,
      protocol: data.protocol,
      api_type: data.api_type,
      is_active: data.is_active,
      extra_headers: Object.keys(headers).length > 0 ? headers : undefined,
    };
    
    // Only submit API Key if filled
    if (data.api_key) {
      submitData.api_key = data.api_key;
    }
    
    onSubmit(submitData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Provider' : 'New Provider'}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="name">
              Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              placeholder="Enter provider name"
              {...register('name', {
                required: 'Name is required',
                validate: (v) => isNotEmpty(v) || 'Name cannot be empty',
              })}
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          {/* Base URL */}
          <div className="space-y-2">
            <Label htmlFor="base_url">
              Base URL <span className="text-destructive">*</span>
            </Label>
            <Input
              id="base_url"
              placeholder="https://api.openai.com"
              {...register('base_url', {
                required: 'Base URL is required',
                validate: (v) => isValidUrl(v) || 'Please enter a valid URL',
              })}
            />
            {errors.base_url && (
              <p className="text-sm text-destructive">{errors.base_url.message}</p>
            )}
          </div>

          {/* Protocol Type */}
          <div className="space-y-2">
            <Label>
              Protocol Type <span className="text-destructive">*</span>
            </Label>
            <Select
              value={protocol}
              onValueChange={(value: ProtocolType) => setValue('protocol', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select Protocol Type" />
              </SelectTrigger>
              <SelectContent>
                {PROTOCOL_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* API Type */}
          <div className="space-y-2">
            <Label htmlFor="api_type">
              API Type <span className="text-destructive">*</span>
            </Label>
            <Select
              value={watch('api_type')}
              onValueChange={(value) => setValue('api_type', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select API Type" />
              </SelectTrigger>
              <SelectContent>
                {API_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <Label htmlFor="api_key">
              API Key {!isEdit && <span className="text-muted-foreground">(Optional)</span>}
            </Label>
            <Input
              id="api_key"
              type="password"
              placeholder={isEdit ? 'Leave blank to keep unchanged' : 'Enter provider API Key'}
              {...register('api_key')}
            />
          </div>

          {/* Extra Headers */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Extra Headers</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addHeader}
                className="h-8 px-2"
              >
                <Plus className="mr-1 h-3 w-3" suppressHydrationWarning />
                Add
              </Button>
            </div>
            
            {extraHeaders.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No extra headers, click button above to add.
              </p>
            )}

            <div className="space-y-2 max-h-[200px] overflow-y-auto">
              {extraHeaders.map((header, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    placeholder="Key"
                    value={header.key}
                    onChange={(e) => updateHeader(index, 'key', e.target.value)}
                    className="flex-1"
                  />
                  <Input
                    placeholder="Value"
                    value={header.value}
                    onChange={(e) => updateHeader(index, 'value', e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeHeader(index)}
                    className="h-9 w-9 text-destructive hover:text-destructive/90"
                  >
                    <Trash2 className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                </div>
              ))}
            </div>
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
