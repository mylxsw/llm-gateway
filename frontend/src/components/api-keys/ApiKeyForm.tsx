/**
 * API Key Form Component
 * Used for creating and editing API Keys
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useForm, useWatch } from 'react-hook-form';
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
import { Copy, Check, AlertCircle, ShieldAlert } from 'lucide-react';
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
  record_details: boolean;
  is_mcp_admin: boolean;
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
  const t = useTranslations('apiKeys');

  // Check if edit mode
  const isEdit = !!apiKey;
  const [copied, setCopied] = useState(false);
  // Confirmation gate for granting MCP admin (requires typing the key name).
  const [grantConfirmOpen, setGrantConfirmOpen] = useState(false);
  const [grantConfirmText, setGrantConfirmText] = useState('');
  
  // Form control
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      key_name: '',
      is_active: true,
      record_details: true,
      is_mcp_admin: false,
    },
  });

  const isActive = useWatch({ control, name: 'is_active' });
  const recordDetails = useWatch({ control, name: 'record_details' });
  const isMcpAdmin = useWatch({ control, name: 'is_mcp_admin' });

  // Fill form data in edit mode
  useEffect(() => {
    if (apiKey) {
      reset({
        key_name: apiKey.key_name,
        is_active: apiKey.is_active,
        record_details: apiKey.record_details,
        is_mcp_admin: apiKey.is_mcp_admin,
      });
    } else {
      reset({
        key_name: '',
        is_active: true,
        record_details: true,
        is_mcp_admin: false,
      });
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCopied(false);
  }, [apiKey, reset, open]);

  // Submit form
  const onFormSubmit = (data: FormData) => {
    if (isEdit) {
      onSubmit({
        key_name: data.key_name,
        is_active: data.is_active,
        record_details: data.record_details,
        is_mcp_admin: data.is_mcp_admin,
      });
    } else {
      onSubmit({
        key_name: data.key_name,
        record_details: data.record_details,
      });
    }
  };

  // Toggle MCP admin. Turning it ON opens a confirmation dialog (type the key
  // name to confirm); turning it OFF applies immediately.
  const handleMcpAdminToggle = (checked: boolean) => {
    if (checked) {
      setGrantConfirmText('');
      setGrantConfirmOpen(true);
    } else {
      setValue('is_mcp_admin', false);
    }
  };

  const confirmGrantMcpAdmin = () => {
    setValue('is_mcp_admin', true);
    setGrantConfirmOpen(false);
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
            <DialogTitle>{t('success.title')}</DialogTitle>
            <DialogDescription>
              {t('success.description')}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4">
            <div className="flex items-center gap-2 rounded-md border bg-muted/50 p-3">
              <AlertCircle className="h-5 w-5 text-yellow-500" suppressHydrationWarning />
              <span className="text-sm text-muted-foreground">
                {t('success.notice')}
              </span>
            </div>
            
            <div className="space-y-2">
              <Label>{t('form.keyNameLabel')}</Label>
              <Input value={createdKey.key_name} disabled />
            </div>
            
            <div className="space-y-2">
              <Label>{t('form.keyLabel')}</Label>
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
                    <Check className="h-4 w-4 text-green-500" suppressHydrationWarning />
                  ) : (
                    <Copy className="h-4 w-4" suppressHydrationWarning />
                  )}
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>
              {t('success.confirmSaved')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>{isEdit ? t('form.editTitle') : t('form.newTitle')}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="key_name">
              {t('form.nameLabel')} <span className="text-destructive">*</span>
            </Label>
            <Input
              id="key_name"
              placeholder={t('form.namePlaceholder')}
              {...register('key_name', {
                required: t('form.nameRequired'),
                validate: (v) => isValidKeyName(v) || t('form.nameInvalid'),
              })}
            />
            {errors.key_name && (
              <p className="text-sm text-destructive">{errors.key_name.message}</p>
            )}
          </div>

          {/* Status */}
          {isEdit && (
            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">{t('form.enabledStatusLabel')}</Label>
              <Switch
                id="is_active"
                checked={isActive}
                onCheckedChange={(checked) => setValue('is_active', checked)}
              />
            </div>
          )}

          {/* Record request detail payload */}
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-1">
              <Label htmlFor="record_details">{t('form.recordDetailsLabel')}</Label>
              <p className="text-xs text-muted-foreground">
                {t('form.recordDetailsHint')}
              </p>
            </div>
            <Switch
              id="record_details"
              checked={recordDetails}
              onCheckedChange={(checked) => setValue('record_details', checked)}
            />
          </div>

          {/* MCP admin capability (edit mode only) */}
          {isEdit && (
            <div className="space-y-2 rounded-md border border-destructive/40 bg-destructive/5 p-3">
              <div className="flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <Label htmlFor="is_mcp_admin" className="flex items-center gap-1.5 text-destructive">
                    <ShieldAlert className="h-4 w-4" suppressHydrationWarning />
                    {t('form.mcpAdminLabel')}
                  </Label>
                </div>
                <Switch
                  id="is_mcp_admin"
                  checked={isMcpAdmin}
                  onCheckedChange={handleMcpAdminToggle}
                />
              </div>
              <p className="text-xs text-destructive">
                {t('form.mcpAdminWarning')}
              </p>
            </div>
          )}

          {!isEdit && (
            <p className="text-sm text-muted-foreground">
              {t('form.autoGenerateHint')}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              {t('actions.cancel')}
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? t('actions.saving') : isEdit ? t('actions.save') : t('actions.create')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    {/* Grant MCP admin confirmation (type key name to confirm) */}
    <Dialog open={grantConfirmOpen} onOpenChange={setGrantConfirmOpen}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <ShieldAlert className="h-5 w-5" suppressHydrationWarning />
            {t('form.mcpAdminConfirmTitle')}
          </DialogTitle>
          <DialogDescription>{t('form.mcpAdminConfirmDescription')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="mcp_confirm">
            {t('form.mcpAdminConfirmPrompt', { name: apiKey?.key_name ?? '' })}
          </Label>
          <Input
            id="mcp_confirm"
            value={grantConfirmText}
            onChange={(e) => setGrantConfirmText(e.target.value)}
            placeholder={apiKey?.key_name ?? ''}
            autoComplete="off"
          />
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setGrantConfirmOpen(false)}
          >
            {t('actions.cancel')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={grantConfirmText !== (apiKey?.key_name ?? '')}
            onClick={confirmGrantMcpAdmin}
          >
            {t('form.mcpAdminConfirmButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}
