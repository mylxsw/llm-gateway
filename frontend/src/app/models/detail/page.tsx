/**
 * Model Detail Page
 * Displays model mapping details and provider configurations
 */

'use client';

import React, { Suspense, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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
import { ModelProviderForm, ModelMatchDialog } from '@/components/models';
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
} from '@/types';
import { formatDateTime, getActiveStatus, formatDuration } from '@/lib/utils';
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

function formatUsdOrFree(value: number) {
  return value === 0 ? 'free' : formatUsdCeil4(value);
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

function formatBilling(
  mapping: ModelMappingProvider,
  fallbackPrices?: { input_price?: number | null; output_price?: number | null }
) {
  const mode = mapping.billing_mode ?? 'token_flat';
  if (mode === 'per_request') {
    if (mapping.per_request_price === null || mapping.per_request_price === undefined) {
      return 'Per request: -';
    }
    if (mapping.per_request_price === 0) return 'free';
    return `Per request: ${formatUsdCeil4(mapping.per_request_price)}`;
  }
  if (mode === 'token_tiered') {
    const tiers = mapping.tiered_pricing ?? [];
    if (!tiers.length) return 'Tiered: -';
    if (isAllZero(tiers.flatMap((t) => [t.input_price, t.output_price]))) return 'free';
    const preview = tiers
      .slice(0, 2)
      .map((t) => {
        const max =
          t.max_input_tokens === null || t.max_input_tokens === undefined
            ? '∞'
            : String(t.max_input_tokens);
        return `≤${max}: ${formatUsdOrFree(t.input_price)}/${formatUsdOrFree(t.output_price)}`;
      })
      .join(', ');
    return `Tiered: ${preview}${tiers.length > 2 ? ` (+${tiers.length - 2})` : ''}`;
  }
  // token_flat (default)
  const effectiveInput = resolveInheritedPrice(mapping.input_price, fallbackPrices?.input_price);
  const effectiveOutput = resolveInheritedPrice(mapping.output_price, fallbackPrices?.output_price);
  if (effectiveInput === 0 && effectiveOutput === 0) return 'free';
  return `Token: ${formatUsdOrFree(effectiveInput)}/${formatUsdOrFree(effectiveOutput)} (per 1M)`;
}

export default function ModelDetailPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <ModelDetailContent />
    </Suspense>
  );
}

function ModelDetailContent() {
  const searchParams = useSearchParams();
  const requestedModelParam = searchParams.get('model');
  const requestedModel = requestedModelParam ? decodeURIComponent(requestedModelParam) : '';

  const [formOpen, setFormOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<ModelMappingProvider | null>(null);
  const [matchDialogOpen, setMatchDialogOpen] = useState(false);

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

  if (!requestedModel) {
    return (
      <ErrorState
        message="Missing model parameter"
        onRetry={() => {
          window.location.href = '/models';
        }}
      />
    );
  }

  if (isLoading) return <LoadingSpinner />;

  if (isError || !model) {
    return (
      <ErrorState
        message="Failed to load model details"
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
        <Link href="/models">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" suppressHydrationWarning />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold font-mono">{model.requested_model}</h1>
          <p className="mt-1 text-muted-foreground">Model Mapping Details</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">Requested Model Name</p>
              <code className="text-sm">{model.requested_model}</code>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Strategy</p>
              <Badge variant="outline">{model.strategy}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Model Type</p>
              <Badge variant="secondary">{modelType}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <Badge className={status.className}>{status.text}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Updated At</p>
              <p className="text-sm">{formatDateTime(model.updated_at)}</p>
            </div>
            {supportsBilling && (
              <div className="md:col-span-2">
                <p className="text-sm text-muted-foreground">Pricing (USD / 1M tokens)</p>
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
          <CardTitle>Usage Stats (Last 7 Days)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">Avg Response Time</p>
              <p className="text-sm">{formatDuration(modelStats?.avg_response_time_ms ?? null)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Avg First Token (Stream)</p>
              <p className="text-sm">
                {formatDuration(modelStats?.avg_first_byte_time_ms ?? null)}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Success Rate</p>
              <p className="text-sm">{formatRate(modelStats?.success_rate)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Failure Rate</p>
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
          <CardTitle>Provider Configuration</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMatchDialogOpen(true)}
            >
              Test
            </Button>
            <Button onClick={handleAddProvider} size="sm">
              <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
              Add Provider
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {model.providers && model.providers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Target Model</TableHead>
                  {supportsBilling && <TableHead>Billing</TableHead>}
                  <TableHead>Priority</TableHead>
                  <TableHead>Weight</TableHead>
                  <TableHead>Rules</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
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
                              title={`Protocol: ${protocol}`}
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
                            Configured
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={mappingStatus.className}>
                          {mappingStatus.text}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleEditMapping(mapping)}
                            title="Edit"
                          >
                            <Pencil className="h-4 w-4" suppressHydrationWarning />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteMapping(mapping)}
                            title="Delete"
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
              No providers configured, click button above to add
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Provider Stats (Last 7 Days)</CardTitle>
        </CardHeader>
        <CardContent>
          {providerStats.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Target Model</TableHead>
                  <TableHead>Avg Response</TableHead>
                  <TableHead>Avg First Token</TableHead>
                  <TableHead>Success</TableHead>
                  <TableHead>Failure</TableHead>
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
              No stats available for the last 7 days
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

      <ModelMatchDialog
        open={matchDialogOpen}
        onOpenChange={setMatchDialogOpen}
        requestedModel={requestedModel}
      />

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete Provider Configuration"
        description={`Are you sure you want to delete configuration for provider "${deletingMapping?.provider_name}"?`}
        confirmText="Delete"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
