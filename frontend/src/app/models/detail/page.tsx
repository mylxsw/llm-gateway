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
import { ModelProviderForm } from '@/components/models';
import { JsonViewer, ConfirmDialog, LoadingSpinner, ErrorState } from '@/components/common';
import {
  useModel,
  useProviders,
  useCreateModelProvider,
  useUpdateModelProvider,
  useDeleteModelProvider,
} from '@/lib/hooks';
import {
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
} from '@/types';
import { formatDateTime, getActiveStatus, formatUsd } from '@/lib/utils';
import { ProtocolType } from '@/types/provider';

function protocolLabel(protocol: ProtocolType) {
  switch (protocol) {
    case 'openai':
      return 'OpenAI';
    case 'anthropic':
      return 'Anthropic';
  }
}

function formatPrice(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  return formatUsd(value);
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

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingMapping, setDeletingMapping] = useState<ModelMappingProvider | null>(null);

  const { data: model, isLoading, isError, refetch } = useModel(requestedModel);
  const { data: providersData } = useProviders();
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
    } catch (error) {
      console.error('Save failed:', error);
      alert('Save failed, please check input or retry');
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingMapping) return;
    try {
      await deleteMutation.mutateAsync(deletingMapping.id);
      setDeleteDialogOpen(false);
      setDeletingMapping(null);
      refetch();
    } catch (error) {
      console.error('Delete failed:', error);
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
              <p className="text-sm text-muted-foreground">Status</p>
              <Badge className={status.className}>{status.text}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Updated At</p>
              <p className="text-sm">{formatDateTime(model.updated_at)}</p>
            </div>
            <div className="md:col-span-2">
              <p className="text-sm text-muted-foreground">Pricing (USD / 1M tokens)</p>
              <p className="text-sm">
                In: <span className="font-mono">{formatPrice(model.input_price)}</span>
                <span className="mx-2 text-muted-foreground">/</span>
                Out: <span className="font-mono">{formatPrice(model.output_price)}</span>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {model.matching_rules && (
        <Card>
          <CardHeader>
            <CardTitle>Matching Rules</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={model.matching_rules} />
          </CardContent>
        </Card>
      )}

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
          <Button onClick={handleAddProvider} size="sm">
            <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
            Add Provider
          </Button>
        </CardHeader>
        <CardContent>
          {model.providers && model.providers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Target Model</TableHead>
                  <TableHead>Price Override</TableHead>
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
                              {protocolLabel(protocol)}
                            </Badge>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="text-sm">{mapping.target_model_name}</code>
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className="font-mono">In: {formatPrice(mapping.input_price)}</span>
                        <span className="mx-2 text-muted-foreground">/</span>
                        <span className="font-mono">Out: {formatPrice(mapping.output_price)}</span>
                      </TableCell>
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

      <ModelProviderForm
        open={formOpen}
        onOpenChange={setFormOpen}
        requestedModel={requestedModel}
        providers={providersData?.items || []}
        defaultPrices={{ input_price: model.input_price ?? null, output_price: model.output_price ?? null }}
        mapping={editingMapping}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
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
