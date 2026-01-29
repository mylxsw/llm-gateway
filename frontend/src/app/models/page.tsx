/**
 * Model Management Page
 * Provides model mapping list display and CRUD operations
 */

'use client';

import React, { useState, useRef } from 'react';
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

/**
 * Model Management Page Component
 */
export default function ModelsPage() {
  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Form dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelMapping | null>(null);

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingModel, setDeletingModel] = useState<ModelMapping | null>(null);
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [testingModel, setTestingModel] = useState<ModelMapping | null>(null);

  // Filter state
  const [filters, setFilters] = useState<ModelFiltersState>({
    requested_model: '',
    model_type: 'all',
    strategy: 'all',
    is_active: 'all',
  });

  // Data query
  const { data, isLoading, isError, refetch } = useModels({
    page,
    page_size: pageSize,
    requested_model: filters.requested_model || undefined,
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
        await createMutation.mutateAsync(formData as ModelMappingCreate);
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
      alert('Export failed');
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
        throw new Error('Invalid import file: expected a JSON array');
      }
      const result = await importModels(json as ModelExport[]);
      
      let message = `Import complete.\nSuccess: ${result.success}\nSkipped: ${result.skipped}`;
      if (result.errors && result.errors.length > 0) {
        message += `\n\nErrors:\n${result.errors.join('\n')}`;
      }
      alert(message);
      
      refetch();
    } catch (error) {
      console.error('Import failed:', error);
      const message =
        error instanceof Error ? error.message : 'Import failed due to an unknown error';
      alert(`Import failed: ${message}`);
    }
    // Reset input
    event.target.value = '';
  };

  return (
    <div className="space-y-6">
      {/* Page Title and Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Model Management</h1>
          <p className="mt-1 text-muted-foreground">
            Configure model mapping rules and providers
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
            Import
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button onClick={handleCreate}>
            <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
            Add Model
          </Button>
        </div>
      </div>
      {/* Filters */}
      <ModelFilters filters={filters} onFilterChange={setFilters} />
      {/* Data List */}
      <Card>
        <CardHeader>
          <CardTitle>Model Mapping List</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="Failed to load model list"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message="No model configurations found"
              actionText="Add Model"
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
        title="Delete Model Mapping"
        description={`Are you sure you want to delete model "${deletingModel?.requested_model}"? This will also delete all associated provider configurations.`}
        confirmText="Delete"
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
