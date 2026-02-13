/**
 * Model Test Dialog
 * Simulates a chat request for a model and returns latency + content.
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useModel, useTestModel } from '@/lib/hooks';
import { getApiErrorMessage } from '@/lib/api/error';
import { formatDuration } from '@/lib/utils';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';
import { ModelTestResponse, ProtocolType } from '@/types';

interface ModelTestDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  requestedModel: string;
}

export function ModelTestDialog({
  open,
  onOpenChange,
  requestedModel,
}: ModelTestDialogProps) {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');
  const [protocol, setProtocol] = useState<ProtocolType | ''>('');
  const [stream, setStream] = useState(false);
  const [result, setResult] = useState<ModelTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: model } = useModel(requestedModel);
  const { configs: protocolConfigs } = useProviderProtocolConfigs();
  const testMutation = useTestModel();

  const availableProtocols = useMemo(() => {
    const hasProviders = (model?.providers?.length ?? 0) > 0;
    if (!hasProviders) {
      return [];
    }
    const supported: ProtocolType[] = [
      'openai',
      'openai_responses',
      'anthropic',
    ];
    if (protocolConfigs.length === 0) {
      return supported;
    }
    const configured = new Set(protocolConfigs.map((config) => config.protocol));
    return supported.filter((protocol) => configured.has(protocol));
  }, [model?.providers, protocolConfigs]);

  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResult(null);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError(null);
      if (availableProtocols.length > 0) {
        if (!protocol || !availableProtocols.includes(protocol)) {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setProtocol(availableProtocols[0]);
        }
      } else if (protocol) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setProtocol('');
      }
    }
  }, [open, protocol, availableProtocols]);

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      setResult(null);
      setError(null);
    }
  };

  const handleTest = async () => {
    if (!protocol) {
      setError(t('testDialog.protocolRequired'));
      return;
    }
    setError(null);
    setResult(null);
    try {
      const response = await testMutation.mutateAsync({
        requestedModel,
        data: {
          protocol,
          stream,
        },
      });
      setResult(response);
    } catch (err) {
      setError(getApiErrorMessage(err, t('testDialog.testFailed')));
    }
  };

  const responseText = result?.content ?? '';

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('testDialog.title')}</DialogTitle>
          <DialogDescription>
            {t('testDialog.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label>{t('testDialog.protocol')}</Label>
            <Select
              value={protocol}
              onValueChange={(value) => setProtocol(value as ProtocolType)}
              disabled={availableProtocols.length === 0}
            >
              <SelectTrigger>
                <SelectValue
                  placeholder={
                    availableProtocols.length === 0
                      ? t('testDialog.noProtocols')
                      : t('testDialog.selectProtocol')
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {availableProtocols.map((item) => (
                  <SelectItem key={item} value={item}>
                    {getProviderProtocolLabel(item, protocolConfigs)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {availableProtocols.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                {t('testDialog.addProvidersHint')}
              </p>
            ) : null}
          </div>

          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <div>
              <Label htmlFor="model-test-stream" className="text-sm">
                {t('testDialog.stream')}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t('testDialog.streamHint')}
              </p>
            </div>
            <Switch
              id="model-test-stream"
              checked={stream}
              onCheckedChange={setStream}
            />
          </div>
        </div>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('testDialog.provider')}</span>
            <span className="font-mono">
              {result?.provider_name ?? '-'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('testDialog.targetModel')}</span>
            <span className="font-mono">
              {result?.target_model ?? '-'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('testDialog.latency')}</span>
            <span className="font-mono">
              {formatDuration(result?.total_time_ms ?? null)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('testDialog.firstToken')}</span>
            <span className="font-mono">
              {formatDuration(result?.first_byte_delay_ms ?? null)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('testDialog.status')}</span>
            <span className="font-mono">
              {result?.response_status ?? '-'}
            </span>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">{t('testDialog.response')}</p>
          <Textarea
            rows={8}
            value={responseText}
            readOnly
            placeholder={t('testDialog.noResponse')}
            className="font-mono"
          />
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
          >
            {tCommon('close')}
          </Button>
          <Button
            type="button"
            onClick={handleTest}
            disabled={testMutation.isPending || availableProtocols.length === 0}
          >
            {tCommon('test')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
