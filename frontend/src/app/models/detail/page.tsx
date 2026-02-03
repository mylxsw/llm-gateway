/**
 * Model Detail Page
 * Displays model mapping details and provider configurations
 */

'use client';

import React, { Suspense, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowLeft, Plus, Pencil, Trash2 } from 'lucide-react';
import { ModelProviderForm, ModelMatchDialog, ModelTestDialog } from '@/components/models';
import { ConfirmDialog, LoadingSpinner, ErrorState } from '@/components/common';
import {
  useModel,
  useModelStats,
  useModelProviderStats,
  useProviders,
  useCreateModelProvider,
  useUpdateModelProvider,
  useDeleteModelProvider,
} from '@/lib/hooks';
import {
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  ModelProviderStats,
  ModelType,
  SelectionStrategy,
} from '@/types';
import { formatDateTime, getActiveStatus, formatDuration, normalizeReturnTo } from '@/lib/utils';
import { ProtocolType } from '@/types/provider';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';

function protocolLabel(
  protocol: ProtocolType,
  configs: ReturnType<typeof useProviderProtocolConfigs>['configs']
) {
  return getProviderProtocolLabel(protocol, configs);
}

function roundUpTo4Decimals(value: number) {
  const factor = 10000;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function formatUsdCeil4(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  const num = Number(value);
  if (Number.isNaN(num)) return '-';
  return `$${roundUpTo4Decimals(num).toFixed(4)}`;
}

function formatPrice(value: number | null | undefined) {
  return formatUsdCeil4(value);
}

function isAllZero(values: number[]) {
  return values.every((v) => v === 0);
}

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return `${(value * 100).toFixed(1)}%`;
}

function resolveInheritedPrice(
  override: number | null | undefined,
  fallback: number | null | undefined
) {
  if (override !== null && override !== undefined) return override;
  if (fallback !== null && fallback !== undefined) return fallback;
  return 0;
}

export default function ModelDetailPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <ModelDetailContent />
    </Suspense>
  );
}

function ModelDetailContent() {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');
  const searchParams = useSearchParams();
  const requestedModelParam = searchParams.get('model');
  const requestedModel = requestedModelParam ? decodeURIComponent(requestedModelParam) : '';
  const returnTo = useMemo(
    () => normalizeReturnTo(searchParams.get('returnTo'), '/models'),
    [searchParams]
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<ModelMappingProvider | null>(null);
  const [matchDialogOpen, setMatchDialogOpen] = useState(false);
  const [testDialogOpen, setTestDialogOpen] = useState(false);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingMapping, setDeletingMapping] = useState<ModelMappingProvider | null>(null);

  const { data: model, isLoading, isError, refetch } = useModel(requestedModel);
  const { data: modelStatsData } = useModelStats({ requested_model: requestedModel });
  const { data: providerStatsData } = useModelProviderStats({ requested_model: requestedModel });
  const { data: providersData } = useProviders();
  const { configs: protocolConfigs } = useProviderProtocolConfigs();
  const providersById = useMemo(() => {
    const entries = providersData?.items?.map((p) => [p.id, p] as const) ?? [];
    return new Map(entries);
  }, [providersData?.items]);

  const createMutation = useCreateModelProvider();
  const updateMutation = useUpdateModelProvider();
  const deleteMutation = useDeleteModelProvider();

  const handleAddProvider = () => {
    setEditingMapping(null);
    setFormOpen(true);
  };

  const handleEditMapping = (mapping: ModelMappingProvider) => {
    setEditingMapping(mapping);
    setFormOpen(true);
  };

  const handleDeleteMapping = (mapping: ModelMappingProvider) => {
    setDeletingMapping(mapping);
    setDeleteDialogOpen(true);
  };

  const handleSubmit = async (
    formData: ModelMappingProviderCreate | ModelMappingProviderUpdate
  ) => {
    try {
      if (editingMapping) {
        await updateMutation.mutateAsync({
          id: editingMapping.id,
          data: formData as ModelMappingProviderUpdate,
        });
      } else {
        await createMutation.mutateAsync(formData as ModelMappingProviderCreate);
      }
      setFormOpen(false);
      setEditingMapping(null);
      refetch();
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingMapping) return;
    try {
      await deleteMutation.mutateAsync(deletingMapping.id);
      setDeleteDialogOpen(false);
      setDeletingMapping(null);
      refetch();
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  const getStrategyLabel = (strategy: SelectionStrategy) => {
    switch (strategy) {
      case 'cost_first':
        return t('list.strategy.costFirst');
      case 'priority':
        return t('list.strategy.priority');
      case 'round_robin':
      default:
        return t('list.strategy.roundRobin');
    }
  };

  const getModelTypeLabel = (type?: ModelType | null) => {
    switch (type) {
      case 'speech':
        return t('filters.speech');
      case 'transcription':
        return t('filters.transcription');
      case 'embedding':
        return t('filters.embedding');
      case 'images':
        return t('filters.images');
      case 'chat':
      default:
        return t('filters.chat');
    }
  };

  const formatUsdOrFree = (value: number) => {
    return value === 0 ? t('detail.billingDisplay.free') : formatUsdCeil4(value);
  };

  const formatBilling = (
    mapping: ModelMappingProvider,
    fallbackPrices?: { input_price?: number | null; output_price?: number | null }
  ) => {
    const mode = mapping.billing_mode ?? 'token_flat';
    if (mode === 'per_request') {
      if (mapping.per_request_price === null || mapping.per_request_price === undefined) {
        return t('detail.billingDisplay.perRequestEmpty');
      }
      if (mapping.per_request_price === 0) return t('detail.billingDisplay.free');
      return t('detail.billingDisplay.perRequest', {
        price: formatUsdCeil4(mapping.per_request_price),
      });
    }
    if (mode === 'token_tiered') {
      const tiers = mapping.tiered_pricing ?? [];
      if (!tiers.length) return t('detail.billingDisplay.tieredEmpty');
      if (isAllZero(tiers.flatMap((tier) => [tier.input_price, tier.output_price]))) {
        return t('detail.billingDisplay.free');
      }
      const preview = tiers
        .slice(0, 2)
        .map((tier) => {
          const max =
            tier.max_input_tokens === null || tier.max_input_tokens === undefined
              ? '∞'
              : String(tier.max_input_tokens);
          return t('detail.billingDisplay.tieredEntry', {
            max,
            input: formatUsdOrFree(tier.input_price),
            output: formatUsdOrFree(tier.output_price),
          });
        })
        .join(', ');
      const more =
        tiers.length > 2
          ? t('detail.billingDisplay.tieredPreviewMore', { count: tiers.length - 2 })
          : '';
      return t('detail.billingDisplay.tieredPreview', { preview, more });
    }
    // token_flat (default)
    const effectiveInput = resolveInheritedPrice(mapping.input_price, fallbackPrices?.input_price);
    const effectiveOutput = resolveInheritedPrice(mapping.output_price, fallbackPrices?.output_price);
    if (effectiveInput === 0 && effectiveOutput === 0) return t('detail.billingDisplay.free');
    return t('detail.billingDisplay.tokenFlat', {
      input: formatUsdOrFree(effectiveInput),
      output: formatUsdOrFree(effectiveOutput),
    });
  };

  if (!requestedModel) {
    return (
      <ErrorState
        message={t('detail.missingModelParam')}
        onRetry={() => {
          window.location.href = returnTo;
        }}
      />
    );
  }

  if (isLoading) return <LoadingSpinner />;

  if (isError || !model) {
    return (
      <ErrorState
        message={t('detail.loadFailed')}
        onRetry={() => refetch()}
      />
    );
  }

  const status = getActiveStatus(model.is_active);
  const modelType = model.model_type ?? 'chat';
  const supportsBilling = modelType === 'chat' || modelType === 'embedding';
  const modelStats = modelStatsData?.find((stat) => stat.requested_model === requestedModel);
  const providerStats = providerStatsData ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href={returnTo}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" suppressHydrationWarning />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold font-mono">{model.requested_model}</h1>
          <p className="mt-1 text-muted-foreground">{t('detail.title')}</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('detail.basicInfo')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">
                {t('detail.requestedModelName')}
              </p>
              <code className="text-sm">{model.requested_model}</code>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.strategy')}</p>
              <Badge variant="outline">{getStrategyLabel(model.strategy)}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.modelType')}</p>
              <Badge variant="secondary">{getModelTypeLabel(modelType)}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.status')}</p>
              <Badge className={status.className}>
                {model.is_active ? t('filters.active') : t('filters.inactive')}
              </Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.updatedAt')}</p>
              <p className="text-sm">{formatDateTime(model.updated_at)}</p>
            </div>
            {supportsBilling && (
              <div className="md:col-span-2">
                <p className="text-sm text-muted-foreground">{t('detail.pricing')}</p>
                <p className="text-sm">
                  <span className="font-mono">{formatPrice(model.input_price)}</span>
                  <span className="mx-2 text-muted-foreground">/</span>
                  <span className="font-mono">{formatPrice(model.output_price)}</span>
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('detail.usageStats')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.avgResponseTime')}</p>
              <p className="text-sm">{formatDuration(modelStats?.avg_response_time_ms ?? null)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                {t('detail.avgFirstTokenStream')}
              </p>
              <p className="text-sm">
                {formatDuration(modelStats?.avg_first_byte_time_ms ?? null)}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.successRate')}</p>
              <p className="text-sm">{formatRate(modelStats?.success_rate)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('detail.failureRate')}</p>
              <p className="text-sm">{formatRate(modelStats?.failure_rate)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* {model.capabilities && (
        <Card>
          <CardHeader>
            <CardTitle>Capabilities</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={model.capabilities} />
          </CardContent>
        </Card>
      )} */}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{t('detail.providerConfig')}</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTestDialogOpen(true)}
            >
              {t('actions.modelTest')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMatchDialogOpen(true)}
            >
              {t('actions.matchTest')}
            </Button>
            <Button onClick={handleAddProvider} size="sm">
              <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
              {t('actions.addProvider')}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {model.providers && model.providers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('detail.provider')}</TableHead>
                  <TableHead>{t('detail.targetModel')}</TableHead>
                  {supportsBilling && <TableHead>{t('detail.billing')}</TableHead>}
                  <TableHead>{t('detail.priority')}</TableHead>
                  <TableHead>{t('detail.weight')}</TableHead>
                  <TableHead>{t('detail.rules')}</TableHead>
                  <TableHead>{t('detail.status')}</TableHead>
                  <TableHead className="text-right">{t('detail.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {model.providers.map((mapping) => {
                  const mappingStatus = getActiveStatus(mapping.is_active);
                  const protocol =
                    mapping.provider_protocol ??
                    providersById.get(mapping.provider_id)?.protocol;
                  return (
                    <TableRow key={mapping.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <span>{mapping.provider_name}</span>
                          {protocol ? (
                            <Badge
                              variant="outline"
                              className="font-normal text-muted-foreground border-muted-foreground/30"
                              title={t('detail.protocolTitle', { protocol })}
                            >
                              {protocolLabel(protocol, protocolConfigs)}
                            </Badge>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="text-sm">{mapping.target_model_name}</code>
                      </TableCell>
                      {supportsBilling && (
                        <TableCell className="text-sm">
                          <span className="font-mono">
                            {formatBilling(mapping, {
                              input_price: model.input_price,
                              output_price: model.output_price,
                            })}
                          </span>
                        </TableCell>
                      )}
                      <TableCell>{mapping.priority}</TableCell>
                      <TableCell>{mapping.weight}</TableCell>
                      <TableCell>
                        {mapping.provider_rules ? (
                          <Badge variant="outline" className="text-blue-600">
                            {t('detail.configured')}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={mappingStatus.className}>
                          {mapping.is_active ? t('filters.active') : t('filters.inactive')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleEditMapping(mapping)}
                            title={tCommon('edit')}
                          >
                            <Pencil className="h-4 w-4" suppressHydrationWarning />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteMapping(mapping)}
                            title={tCommon('delete')}
                          >
                            <Trash2
                              className="h-4 w-4 text-destructive"
                              suppressHydrationWarning
                            />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="py-8 text-center text-muted-foreground">
              {t('detail.noProviders')}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('detail.providerStats')}</CardTitle>
        </CardHeader>
        <CardContent>
          {providerStats.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('detail.provider')}</TableHead>
                  <TableHead>{t('detail.targetModel')}</TableHead>
                  <TableHead>{t('detail.avgResponse')}</TableHead>
                  <TableHead>{t('detail.avgFirstToken')}</TableHead>
                  <TableHead>{t('detail.success')}</TableHead>
                  <TableHead>{t('detail.failure')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {providerStats.map((stat: ModelProviderStats) => (
                  <TableRow key={`${stat.provider_name}-${stat.target_model}`}>
                    <TableCell className="font-medium">{stat.provider_name}</TableCell>
                    <TableCell>
                      <code className="text-sm">{stat.target_model}</code>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDuration(stat.avg_response_time_ms ?? null)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDuration(stat.avg_first_byte_time_ms ?? null)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatRate(stat.success_rate)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatRate(stat.failure_rate)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="py-8 text-center text-muted-foreground">
              {t('detail.noStats')}
            </p>
          )}
        </CardContent>
      </Card>

      <ModelProviderForm
        open={formOpen}
        onOpenChange={setFormOpen}
        requestedModel={requestedModel}
        providers={providersData?.items || []}
        defaultPrices={{ input_price: model.input_price ?? null, output_price: model.output_price ?? null }}
        mapping={editingMapping}
        modelType={modelType}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      <ModelTestDialog
        open={testDialogOpen}
        onOpenChange={setTestDialogOpen}
        requestedModel={requestedModel}
      />

      <ModelMatchDialog
        open={matchDialogOpen}
        onOpenChange={setMatchDialogOpen}
        requestedModel={requestedModel}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title={t('detail.deleteProviderConfigTitle')}
        description={t('detail.deleteProviderConfigDescription', {
          name: deletingMapping?.provider_name ?? '',
        })}
        confirmText={tCommon('delete')}
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
