/**
 * Provider Form Component
 * Used for creating and editing providers
 */

'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslations } from 'next-intl';
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
import {
  getProviderProtocolConfig,
  useProviderProtocolConfigs,
} from '@/lib/providerProtocols';

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
  api_key: string;
  is_active: boolean;
  proxy_enabled: boolean;
  proxy_url: string;
}

const DEFAULT_PARAMETER_OPTIONS = [
  { value: 'temperature', label: 'temperature' },
  { value: 'top_p', label: 'top_p' },
  { value: 'top_k', label: 'top_k' },
  { value: 'max_tokens', label: 'max_tokens' },
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
  const t = useTranslations('providers');
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
      api_key: '',
      is_active: true,
      proxy_enabled: false,
      proxy_url: '',
    },
  });

  // Watch form values
  const protocol = watch('protocol');
  const baseUrl = watch('base_url');
  const isActive = watch('is_active');
  const proxyEnabled = watch('proxy_enabled');
  const { configs: protocolConfigs } = useProviderProtocolConfigs();
  const protocolConfig = getProviderProtocolConfig(protocol, protocolConfigs);
  
  // Extra headers state
  const [extraHeaders, setExtraHeaders] = useState<{ key: string; value: string }[]>([]);
  const [defaultParameters, setDefaultParameters] = useState<
    { key: string; value: string }[]
  >([]);
  const lastAutoBaseUrl = useRef<string | null>(null);

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

  const addDefaultParameter = () => {
    setDefaultParameters([
      ...defaultParameters,
      { key: DEFAULT_PARAMETER_OPTIONS[0].value, value: '' },
    ]);
  };

  const removeDefaultParameter = (index: number) => {
    const nextParams = [...defaultParameters];
    nextParams.splice(index, 1);
    setDefaultParameters(nextParams);
  };

  const updateDefaultParameter = (
    index: number,
    field: 'key' | 'value',
    value: string
  ) => {
    const nextParams = [...defaultParameters];
    nextParams[index][field] = value;
    setDefaultParameters(nextParams);
  };

  const formatParameterValue = (value: unknown) => {
    if (typeof value === 'string') {
      return value;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  };

  const parseParameterValue = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return value;
    if (/^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(trimmed)) {
      const num = Number(trimmed);
      if (!Number.isNaN(num)) {
        return num;
      }
    }
    return value;
  };

  // Fill form data in edit mode
  useEffect(() => {
    if (provider) {
      reset({
        name: provider.name,
        base_url: provider.base_url,
        protocol: provider.protocol,
        api_key: '', // API Key not echoed
        is_active: provider.is_active,
        proxy_enabled: provider.proxy_enabled ?? false,
        proxy_url: '',
      });
      lastAutoBaseUrl.current =
        getProviderProtocolConfig(provider.protocol, protocolConfigs)?.base_url ?? null;
      
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

      if (provider.provider_options?.default_parameters) {
        const allowedKeys = new Set(
          DEFAULT_PARAMETER_OPTIONS.map((option) => option.value)
        );
        setDefaultParameters(
          Object.entries(provider.provider_options.default_parameters)
            .filter(([key]) => allowedKeys.has(key))
            .map(([key, value]) => ({
              key,
              value: formatParameterValue(value),
            }))
        );
      } else {
        setDefaultParameters([]);
      }
    } else {
      reset({
        name: '',
        base_url: '',
        protocol: 'openai',
        api_key: '',
        is_active: true,
        proxy_enabled: false,
        proxy_url: '',
      });
      lastAutoBaseUrl.current = getProviderProtocolConfig('openai', protocolConfigs)?.base_url ?? null;
      setExtraHeaders([]);
      setDefaultParameters(
        protocol === 'anthropic'
          ? [{ key: 'max_tokens', value: '4096' }]
          : []
      );
    }
  }, [provider, reset]);

  useEffect(() => {
    if (provider) return;
    if (defaultParameters.length > 0) return;
    if (protocol !== 'anthropic') return;
    setDefaultParameters([{ key: 'max_tokens', value: '4096' }]);
  }, [provider, protocol, defaultParameters.length]);

  useEffect(() => {
    if (!protocolConfig) return;
    const nextBaseUrl = protocolConfig.base_url;
    const shouldAutoFill =
      !baseUrl || (lastAutoBaseUrl.current && baseUrl === lastAutoBaseUrl.current);

    if (shouldAutoFill && baseUrl !== nextBaseUrl) {
      setValue('base_url', nextBaseUrl, { shouldDirty: true });
    }

    lastAutoBaseUrl.current = nextBaseUrl;
  }, [baseUrl, protocolConfig, setValue]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    // Handle extra headers
    const headers: Record<string, string> = {};
    extraHeaders.forEach(({ key, value }) => {
      if (key && value) {
        headers[key] = value;
      }
    });

    const params: Record<string, unknown> = {};
    defaultParameters.forEach(({ key, value }) => {
      if (key && value) {
        const parsed = parseParameterValue(value);
        if (typeof parsed === 'number' && !Number.isNaN(parsed)) {
          params[key] = parsed;
        }
      }
    });

    // Filter out empty strings
    const submitData: ProviderCreate | ProviderUpdate = {
      name: data.name,
      base_url: data.base_url,
      protocol: data.protocol,
      is_active: data.is_active,
      extra_headers: Object.keys(headers).length > 0 ? headers : undefined,
      provider_options:
        Object.keys(params).length > 0
          ? { default_parameters: params }
          : undefined,
      proxy_enabled: data.proxy_enabled,
    };
    
    // Only submit API Key if filled
    if (data.api_key) {
      submitData.api_key = data.api_key;
    }
    if (data.proxy_url) {
      submitData.proxy_url = data.proxy_url;
    }
    
    onSubmit(submitData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? t('form.title.edit') : t('form.title.new')}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="name">
              {t('form.name.label')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              placeholder={t('form.name.placeholder')}
              {...register('name', {
                required: t('form.name.required'),
                validate: (v) => isNotEmpty(v) || t('form.name.empty'),
              })}
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          {/* Protocol Type */}
          <div className="space-y-2">
            <Label>
              {t('form.protocol.label')} <span className="text-destructive">*</span>
            </Label>
            <Select
              value={protocol}
              onValueChange={(value: ProtocolType) => setValue('protocol', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder={t('form.protocol.placeholder')} />
              </SelectTrigger>
              <SelectContent>
                {protocolConfigs.map((option) => (
                  <SelectItem key={option.protocol} value={option.protocol}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Base URL */}
          <div className="space-y-2">
            <Label htmlFor="base_url">
              {t('form.baseUrl.label')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="base_url"
              placeholder={protocolConfig?.base_url || 'https://api.openai.com'}
              {...register('base_url', {
                required: t('form.baseUrl.required'),
                validate: (v) => isValidUrl(v) || t('form.baseUrl.invalid'),
              })}
            />
            {errors.base_url && (
              <p className="text-sm text-destructive">{errors.base_url.message}</p>
            )}
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <Label htmlFor="api_key">
              {t('form.apiKey.label')}{' '}
              {!isEdit && <span className="text-muted-foreground">{t('form.apiKey.optional')}</span>}
            </Label>
            <Input
              id="api_key"
              type="password"
              placeholder={
                isEdit ? t('form.apiKey.placeholderEdit') : t('form.apiKey.placeholderNew')
              }
              {...register('api_key')}
            />
          </div>

          {/* Extra Headers */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{t('form.extraHeaders.label')}</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addHeader}
                className="h-8 px-2"
              >
                <Plus className="mr-1 h-3 w-3" suppressHydrationWarning />
                {t('form.extraHeaders.add')}
              </Button>
            </div>
            
            {extraHeaders.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {t('form.extraHeaders.empty')}
              </p>
            )}

            <div className="space-y-2 max-h-[200px] overflow-y-auto">
              {extraHeaders.map((header, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    placeholder={t('form.extraHeaders.keyPlaceholder')}
                    value={header.key}
                    onChange={(e) => updateHeader(index, 'key', e.target.value)}
                    className="flex-1"
                  />
                  <Input
                    placeholder={t('form.extraHeaders.valuePlaceholder')}
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

          {/* Default Parameters */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{t('form.defaultParams.label')}</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addDefaultParameter}
                className="h-8 px-2"
              >
                <Plus className="mr-1 h-3 w-3" suppressHydrationWarning />
                {t('form.defaultParams.add')}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('form.defaultParams.helpApply')}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('form.defaultParams.helpNumeric')}
            </p>

            {defaultParameters.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {t('form.defaultParams.empty')}
              </p>
            )}

            <div className="space-y-2 max-h-[200px] overflow-y-auto">
              {defaultParameters.map((param, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Select
                    value={param.key}
                    onValueChange={(value: string) =>
                      updateDefaultParameter(index, 'key', value)
                    }
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder={t('form.defaultParams.selectKey')} />
                    </SelectTrigger>
                    <SelectContent>
                      {DEFAULT_PARAMETER_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    placeholder={t('form.defaultParams.valuePlaceholder')}
                    value={param.value}
                    onChange={(e) =>
                      updateDefaultParameter(index, 'value', e.target.value)
                    }
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeDefaultParameter(index)}
                    className="h-9 w-9 text-destructive hover:text-destructive/90"
                  >
                    <Trash2 className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {/* Proxy Configuration */}
          <div className="space-y-3 rounded-md border border-border p-3">
            <div className="flex items-center justify-between">
              <Label htmlFor="proxy_enabled">{t('form.proxy.label')}</Label>
              <Switch
                id="proxy_enabled"
                checked={proxyEnabled}
                onCheckedChange={(checked) => setValue('proxy_enabled', checked)}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t('form.proxy.help')}
            </p>

            {proxyEnabled && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="proxy_url">{t('form.proxy.urlLabel')}</Label>
                  <Input
                    id="proxy_url"
                    placeholder={
                      isEdit ? t('form.proxy.urlPlaceholderEdit') : t('form.proxy.urlPlaceholderNew')
                    }
                    {...register('proxy_url')}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Status */}
          <div className="flex items-center justify-between">
            <Label htmlFor="is_active">{t('form.status.label')}</Label>
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
              {t('form.actions.cancel')}
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? t('form.actions.saving') : t('form.actions.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
