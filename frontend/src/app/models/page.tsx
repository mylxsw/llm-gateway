/**
 * Model Management Page
 * Provides model mapping list display and CRUD operations
 */

'use client';

import React, { useState, useRef, useCallback, useEffect, useMemo, Suspense } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Download, Upload } from 'lucide-react';
import {
  ModelFilters,
  ModelFiltersState,
  ModelForm,
  ModelList,
  ModelTestDialog,
} from '@/components/models';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useModels,
  useModelStats,
  useCreateModel,
  useUpdateModel,
  useDeleteModel,
} from '@/lib/hooks';
import { exportModels, importModels } from '@/lib/api';
import {
  ModelExport,
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  ModelType,
  SelectionStrategy,
} from '@/types';
import { useRouter, useSearchParams } from 'next/navigation';
import { parseNumberParam, parseStringParam, setParam } from '@/lib/utils';

/**
 * Model Management Page Component
 */
export default function ModelsPage() {
  return (
    <Suspense fallback={null}>
      <ModelsContent />
    </Suspense>
  );
}

function ModelsContent() {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');
  const router = useRouter();
  const searchParams = useSearchParams();

  const buildStateFromParams = useCallback(() => {
    const parsedPage = parseNumberParam(searchParams.get('page'), { min: 1 }) ?? 1;
    const parsedPageSize = parseNumberParam(searchParams.get('page_size'), { min: 1 }) ?? 20;
    const parsedFilters: ModelFiltersState = {
      requested_model: parseStringParam(searchParams.get('requested_model')) ?? '',
      target_model_name: parseStringParam(searchParams.get('target_model_name')) ?? '',
      model_type: (parseStringParam(searchParams.get('model_type')) as ModelType | 'all') ?? 'all',
      strategy:
        (parseStringParam(searchParams.get('strategy')) as SelectionStrategy | 'all') ?? 'all',
      is_active: parseStringParam(searchParams.get('is_active')) ?? 'all',
    };

    return { parsedPage, parsedPageSize, parsedFilters };
  }, [searchParams]);

  // Pagination state
  const [page, setPage] = useState(() => buildStateFromParams().parsedPage);
  const [pageSize, setPageSize] = useState(() => buildStateFromParams().parsedPageSize);

  // Form dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelMapping | null>(null);

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingModel, setDeletingModel] = useState<ModelMapping | null>(null);
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [testingModel, setTestingModel] = useState<ModelMapping | null>(null);

  // Filter state
  const [filters, setFilters] = useState<ModelFiltersState>(
    () => buildStateFromParams().parsedFilters
  );

  const areFiltersEqual = useCallback((a: ModelFiltersState, b: ModelFiltersState) => (
    a.requested_model === b.requested_model &&
    a.target_model_name === b.target_model_name &&
    a.model_type === b.model_type &&
    a.strategy === b.strategy &&
    a.is_active === b.is_active
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
    setParam(params, 'requested_model', filters.requested_model);
    setParam(params, 'target_model_name', filters.target_model_name);
    if (filters.model_type && filters.model_type !== 'all') {
      setParam(params, 'model_type', filters.model_type);
    }
    if (filters.strategy && filters.strategy !== 'all') {
      setParam(params, 'strategy', filters.strategy);
    }
    if (filters.is_active && filters.is_active !== 'all') {
      setParam(params, 'is_active', filters.is_active);
    }
    return params.toString();
  }, [filters, page, pageSize]);

  const returnTo = useMemo(
    () => (queryString ? `/models?${queryString}` : '/models'),
    [queryString]
  );

  useEffect(() => {
    const currentQuery = searchParams.toString();
    if (queryString === currentQuery) return;
    const nextUrl = queryString ? `/models?${queryString}` : '/models';
    router.replace(nextUrl, { scroll: false });
  }, [queryString, router, searchParams]);

  // Data query
  const { data, isLoading, isError, refetch } = useModels({
    page,
    page_size: pageSize,
    requested_model: filters.requested_model || undefined,
    target_model_name: filters.target_model_name || undefined,
    model_type: filters.model_type === 'all' ? undefined : (filters.model_type as ModelType),
    strategy: filters.strategy === 'all' ? undefined : (filters.strategy as SelectionStrategy),
    is_active: filters.is_active === 'all' ? undefined : filters.is_active === 'active',
  });
  const { data: statsData } = useModelStats();

  // Mutations
  const createMutation = useCreateModel();
  const updateMutation = useUpdateModel();
  const deleteMutation = useDeleteModel();

  // File Input Ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Open create form
  const handleCreate = () => {
    setEditingModel(null);
    setFormOpen(true);
  };

  // Open edit form
  const handleEdit = (model: ModelMapping) => {
    setEditingModel(model);
    setFormOpen(true);
  };

  // Open delete confirmation
  const handleDelete = (model: ModelMapping) => {
    setDeletingModel(model);
    setDeleteDialogOpen(true);
  };

  const handleTest = (model: ModelMapping) => {
    setTestingModel(model);
    setTestDialogOpen(true);
  };

  // Submit form
  const handleSubmit = async (formData: ModelMappingCreate | ModelMappingUpdate) => {
    try {
      if (editingModel) {
        // Update
        await updateMutation.mutateAsync({
          requestedModel: editingModel.requested_model,
          data: formData as ModelMappingUpdate,
        });
      } else {
        // Create
        const createData = formData as ModelMappingCreate;
        await createMutation.mutateAsync(createData);
        const requestedModel = createData.requested_model;
        if (requestedModel) {
          router.push(
            `/models/detail?model=${encodeURIComponent(requestedModel)}&returnTo=${encodeURIComponent(returnTo)}`
          );
        }
      }
      setFormOpen(false);
      setEditingModel(null);
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (!deletingModel) return;
    try {
      await deleteMutation.mutateAsync(deletingModel.requested_model);
      setDeleteDialogOpen(false);
      setDeletingModel(null);
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  // Export
  const handleExport = async () => {
    try {
      const data = await exportModels();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `models_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert(t('importExport.exportFailed'));
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
        throw new Error(t('importExport.invalidFile'));
      }
      const result = await importModels(json as ModelExport[]);
      
      if (result.errors && result.errors.length > 0) {
        alert(
          t('importExport.importCompleteWithErrors', {
            success: result.success,
            skipped: result.skipped,
            errors: result.errors.join('\n'),
          })
        );
      } else {
        alert(
          t('importExport.importComplete', {
            success: result.success,
            skipped: result.skipped,
          })
        );
      }
      
      refetch();
    } catch (error) {
      console.error('Import failed:', error);
      if (error instanceof Error) {
        alert(t('importExport.importFailed', { message: error.message }));
      } else {
        alert(t('importExport.importFailedUnknown'));
      }
    }
    // Reset input
    event.target.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Page Title and Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('title')}</h1>
          <p className="mt-1 text-muted-foreground">
            {t('description')}
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
            {t('actions.import')}
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            {t('actions.export')}
          </Button>
          <Button onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
            {t('actions.addModel')}
          </Button>
        </div>
      </div>
      {/* Filters */}
      <ModelFilters filters={filters} onFilterChange={setFilters} />
      {/* Data List */}
      <Card>
        <CardHeader>
          <CardTitle>{t('list.title')}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message={t('list.loadFailed')}
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message={t('list.empty')}
              actionText={t('actions.addModel')}
              onAction={handleCreate}
            />
          )}
          
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <ModelList
                models={data.items}
                statsByModel={Object.fromEntries(
                  (statsData ?? []).map((stat) => [stat.requested_model, stat])
                )}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onTest={handleTest}
                returnTo={returnTo}
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
      <ModelForm
        open={formOpen}
        onOpenChange={setFormOpen}
        model={editingModel}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title={t('dialogs.deleteModelMappingTitle')}
        description={t('dialogs.deleteModelMappingDescription', {
          name: deletingModel?.requested_model ?? '',
        })}
        confirmText={tCommon('delete')}
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />

      <ModelTestDialog
        open={testDialogOpen}
        onOpenChange={setTestDialogOpen}
        requestedModel={testingModel?.requested_model ?? ''}
      />
    </div>
  );
}
