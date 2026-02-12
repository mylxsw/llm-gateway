/**
 * Provider Management Page
 * Provides provider list display and CRUD operations
 */

'use client';

import React, { useState, useRef, useCallback, useEffect, useMemo, Suspense } from 'react';
import { useTranslations } from 'next-intl';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, Download, Upload, ExternalLink } from 'lucide-react';
import { ProviderFilters, ProviderFiltersState, ProviderForm, ProviderList } from '@/components/providers';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useProviders,
  useModelProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
} from '@/lib/hooks';
import { exportProviders, importProviders, getProviderModels } from '@/lib/api';
import { Provider, ProviderCreate, ProviderUpdate, ProtocolType } from '@/types';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';
import { useRouter, useSearchParams } from 'next/navigation';
import { parseNumberParam, parseStringParam, setParam } from '@/lib/utils';

/**
 * Provider Management Page Component
 */
export default function ProvidersPage() {
  return (
    <Suspense fallback={null}>
      <ProvidersContent />
    </Suspense>
  );
}

function ProvidersContent() {
  const t = useTranslations('providers');
  const router = useRouter();
  const searchParams = useSearchParams();

  const buildStateFromParams = useCallback(() => {
    const parsedPage = parseNumberParam(searchParams.get('page'), { min: 1 }) ?? 1;
    const parsedPageSize = parseNumberParam(searchParams.get('page_size'), { min: 1 }) ?? 20;
    const parsedFilters: ProviderFiltersState = {
      name: parseStringParam(searchParams.get('name')) ?? '',
      protocol: (parseStringParam(searchParams.get('protocol')) as ProtocolType | 'all') ?? 'all',
      is_active: parseStringParam(searchParams.get('is_active')) ?? 'all',
    };
    return { parsedPage, parsedPageSize, parsedFilters };
  }, [searchParams]);
  // Pagination state
  const [page, setPage] = useState(() => buildStateFromParams().parsedPage);
  const [pageSize, setPageSize] = useState(() => buildStateFromParams().parsedPageSize);

  // Form dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingProvider, setDeletingProvider] = useState<Provider | null>(null);

  // Provider model list dialog state
  const [modelDialogOpen, setModelDialogOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [modelList, setModelList] = useState<string[]>([]);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const [usedModelsDialogOpen, setUsedModelsDialogOpen] = useState(false);
  const [usedModelsProvider, setUsedModelsProvider] = useState<Provider | null>(null);

  // Filter state
  const [filters, setFilters] = useState<ProviderFiltersState>(
    () => buildStateFromParams().parsedFilters
  );

  const areFiltersEqual = useCallback((a: ProviderFiltersState, b: ProviderFiltersState) => (
    a.name === b.name && a.protocol === b.protocol && a.is_active === b.is_active
  ), []);

  useEffect(() => {
    const { parsedPage, parsedPageSize, parsedFilters } = buildStateFromParams();
    setPage((prev) => (prev === parsedPage ? prev : parsedPage));
    setPageSize((prev) => (prev === parsedPageSize ? prev : parsedPageSize));
    setFilters((prev) => (areFiltersEqual(prev, parsedFilters) ? prev : parsedFilters));
  }, [areFiltersEqual, buildStateFromParams]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (page !== 1) setParam(params, 'page', page);
    if (pageSize !== 20) setParam(params, 'page_size', pageSize);
    setParam(params, 'name', filters.name);
    if (filters.protocol && filters.protocol !== 'all') {
      setParam(params, 'protocol', filters.protocol);
    }
    if (filters.is_active && filters.is_active !== 'all') {
      setParam(params, 'is_active', filters.is_active);
    }
    return params.toString();
  }, [filters, page, pageSize]);

  useEffect(() => {
    const currentQuery = searchParams.toString();
    if (queryString === currentQuery) return;
    const nextUrl = queryString ? `/providers?${queryString}` : '/providers';
    router.replace(nextUrl, { scroll: false });
  }, [queryString, router, searchParams]);

  // Data query
  const { data, isLoading, isError, refetch } = useProviders({
    page,
    page_size: pageSize,
    name: filters.name || undefined,
    protocol: filters.protocol === 'all' ? undefined : (filters.protocol as ProtocolType),
    is_active: filters.is_active === 'all' ? undefined : filters.is_active === 'active',
  });
  const { data: modelProviderMappings } = useModelProviders();

  const usedModelNamesByProvider = useMemo(() => {
    const grouped = new Map<number, Set<string>>();
    for (const mapping of modelProviderMappings?.items ?? []) {
      const normalizedModelName = mapping.target_model_name.trim();
      if (!normalizedModelName) continue;
      if (!grouped.has(mapping.provider_id)) {
        grouped.set(mapping.provider_id, new Set<string>());
      }
      grouped.get(mapping.provider_id)?.add(normalizedModelName);
    }
    return Object.fromEntries(
      Array.from(grouped.entries(), ([providerId, modelNames]) => [
        providerId,
        Array.from(modelNames).sort((a, b) => a.localeCompare(b)),
      ])
    );
  }, [modelProviderMappings?.items]);

  // Mutations
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const deleteMutation = useDeleteProvider();
  const { configs: protocolConfigs } = useProviderProtocolConfigs();

  // File Input Ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Open create form
  const handleCreate = () => {
    setEditingProvider(null);
    setFormOpen(true);
  };

  // Open edit form
  const handleEdit = (provider: Provider) => {
    setEditingProvider(provider);
    setFormOpen(true);
  };

  // Open delete confirmation
  const handleDelete = (provider: Provider) => {
    setDeletingProvider(provider);
    setDeleteDialogOpen(true);
  };

  const handleFetchModels = async (provider: Provider) => {
    setSelectedProvider(provider);
    setModelDialogOpen(true);
    setModelLoading(true);
    setModelError(null);
    setModelList([]);
    try {
      const result = await getProviderModels(provider.id);
      if (!result.success) {
        const message = result.error?.message || t('errors.fetchModelsFailed');
        setModelError(message);
        return;
      }
      setModelList(result.models || []);
    } catch (error) {
      console.error('Fetch models failed:', error);
      const message =
        error instanceof Error ? error.message : t('errors.fetchModelsFailed');
      setModelError(message);
    } finally {
      setModelLoading(false);
    }
  };

  const handleOpenUsedModels = (provider: Provider) => {
    setUsedModelsProvider(provider);
    setUsedModelsDialogOpen(true);
  };

  const usedModelList = usedModelsProvider
    ? usedModelNamesByProvider[usedModelsProvider.id] ?? []
    : [];

  // Submit form
  const handleSubmit = async (formData: ProviderCreate | ProviderUpdate) => {
    try {
      if (editingProvider) {
        // Update
        await updateMutation.mutateAsync({
          id: editingProvider.id,
          data: formData as ProviderUpdate,
        });
      } else {
        // Create
        await createMutation.mutateAsync(formData as ProviderCreate);
      }
      setFormOpen(false);
      setEditingProvider(null);
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (!deletingProvider) return;
    try {
      await deleteMutation.mutateAsync(deletingProvider.id);
      setDeleteDialogOpen(false);
      setDeletingProvider(null);
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  // Export
  const handleExport = async () => {
    try {
      const data = await exportProviders();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `providers_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert(t('alerts.exportFailed'));
    }
  };

  // Import
  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const json = JSON.parse(text) as unknown;
      if (!Array.isArray(json)) {
        throw new Error(t('alerts.importInvalidFile'));
      }
      const result = await importProviders(json as ProviderCreate[]);
      alert(
        t('alerts.importComplete', {
          success: result.success,
          skipped: result.skipped,
        })
      );
      refetch();
    } catch (error) {
      console.error('Import failed:', error);
      const message =
        error instanceof Error ? error.message : t('alerts.importFailedUnknown');
      alert(t('alerts.importFailedWithMessage', { message }));
    }
    // Reset input
    event.target.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Page Title and Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('page.title')}</h1>
          <p className="mt-1 text-muted-foreground">
            {t('page.subtitle')}
          </p>
        </div>
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept=".json"
            onChange={handleFileChange}
          />
          <Button variant="outline" onClick={handleImportClick}>
            <Upload className="mr-2 h-4 w-4" />
            {t('page.import')}
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            {t('page.export')}
          </Button>
          <Button onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
            {t('page.addProvider')}
          </Button>
        </div>
      </div>
      {/* Filters */}
      <ProviderFilters filters={filters} onFilterChange={setFilters} />
      {/* Data List */}
      <Card>
        <CardHeader>
          <CardTitle>{t('page.providerList')}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message={t('page.loadError')}
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message={t('page.empty')}
              actionText={t('page.addProvider')}
              onAction={handleCreate}
            />
          )}
          
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <ProviderList
                providers={data.items}
                usedModelNamesByProvider={usedModelNamesByProvider}
                onEdit={handleEdit}
                onFetchModels={handleFetchModels}
                onOpenUsedModels={handleOpenUsedModels}
                onDelete={handleDelete}
              />
              <Pagination
                page={page}
                pageSize={pageSize}
                total={data.total}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            </>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Form */}
      <ProviderForm
        open={formOpen}
        onOpenChange={setFormOpen}
        provider={editingProvider}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title={t('delete.title')}
        description={t('delete.description', { name: deletingProvider?.name ?? '' })}
        confirmText={t('delete.confirm')}
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />

      <Dialog open={modelDialogOpen} onOpenChange={setModelDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('models.title')}</DialogTitle>
            <DialogDescription>
              {selectedProvider
                ? t('models.description', {
                    name: selectedProvider.name,
                    protocol: getProviderProtocolLabel(selectedProvider.protocol, protocolConfigs),
                  })
                : t('models.noProviderSelected')}
            </DialogDescription>
          </DialogHeader>
          {modelLoading && <LoadingSpinner />}
          {!modelLoading && modelError && (
            <div className="text-sm text-destructive">{modelError}</div>
          )}
          {!modelLoading && !modelError && (
            <div className="max-h-[360px] overflow-auto rounded-md border p-3">
              {modelList.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  {t('models.empty')}
                </div>
              ) : (
                <ul className="space-y-1 text-sm">
                  {modelList.map((model) => (
                    <li key={model} className="font-mono">
                      {model}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={usedModelsDialogOpen} onOpenChange={setUsedModelsDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('usedModels.title')}</DialogTitle>
            <DialogDescription>
              {usedModelsProvider
                ? t('usedModels.description', { name: usedModelsProvider.name })
                : t('usedModels.noProviderSelected')}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[360px] overflow-auto rounded-md border p-3">
            {usedModelList.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                {t('usedModels.empty')}
              </div>
            ) : (
              <ol className="space-y-2 text-sm">
                {usedModelList.map((modelName, index) => (
                  <li
                    key={modelName}
                    className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="w-5 text-xs text-muted-foreground">{index + 1}.</span>
                      <span className="truncate font-mono" title={modelName}>
                        {modelName}
                      </span>
                    </div>
                    <Link
                      href={`/models?target_model_name=${encodeURIComponent(modelName)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 whitespace-nowrap text-primary hover:underline"
                      title={t('list.actions.viewModelList')}
                    >
                      <span>{t('list.actions.viewModelList')}</span>
                      <ExternalLink className="h-3.5 w-3.5" suppressHydrationWarning />
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
