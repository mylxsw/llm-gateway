/**
 * Provider Management Page
 * Provides provider list display and CRUD operations
 */

'use client';

import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Plus, Download, Upload } from 'lucide-react';
import { ProviderFilters, ProviderFiltersState, ProviderForm, ProviderList } from '@/components/providers';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
} from '@/lib/hooks';
import { exportProviders, importProviders, getProviderModels } from '@/lib/api';
import { Provider, ProviderCreate, ProviderUpdate, ProtocolType } from '@/types';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';

/**
 * Provider Management Page Component
 */
export default function ProvidersPage() {
  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

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

  // Filter state
  const [filters, setFilters] = useState<ProviderFiltersState>({
    name: '',
    protocol: 'all',
    is_active: 'all',
  });

  // Data query
  const { data, isLoading, isError, refetch } = useProviders({
    page,
    page_size: pageSize,
    name: filters.name || undefined,
    protocol: filters.protocol === 'all' ? undefined : (filters.protocol as ProtocolType),
    is_active: filters.is_active === 'all' ? undefined : filters.is_active === 'active',
  });

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
        const message = result.error?.message || 'Failed to fetch models';
        setModelError(message);
        return;
      }
      setModelList(result.models || []);
    } catch (error) {
      console.error('Fetch models failed:', error);
      const message =
        error instanceof Error ? error.message : 'Failed to fetch models';
      setModelError(message);
    } finally {
      setModelLoading(false);
    }
  };

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
      const result = await importProviders(json as ProviderCreate[]);
      alert(`Import complete.\nSuccess: ${result.success}\nSkipped: ${result.skipped}`);
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
          <h1 className="text-2xl font-bold">Provider Management</h1>
          <p className="mt-1 text-muted-foreground">
            Manage upstream AI provider configurations
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
            Add Provider
          </Button>
        </div>
      </div>
      {/* Filters */}
      <ProviderFilters filters={filters} onFilterChange={setFilters} />
      {/* Data List */}
      <Card>
        <CardHeader>
          <CardTitle>Provider List</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="Failed to load provider list"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message="No providers found"
              actionText="Add Provider"
              onAction={handleCreate}
            />
          )}
          
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <ProviderList
                providers={data.items}
                onEdit={handleEdit}
                onFetchModels={handleFetchModels}
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
        title="Delete Provider"
        description={`Are you sure you want to delete provider "${deletingProvider?.name}"? It cannot be deleted if referenced by models.`}
        confirmText="Delete"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />

      <Dialog open={modelDialogOpen} onOpenChange={setModelDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Upstream Models</DialogTitle>
            <DialogDescription>
              {selectedProvider
                ? `Provider: ${selectedProvider.name} (${getProviderProtocolLabel(selectedProvider.protocol, protocolConfigs)})`
                : 'No provider selected'}
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
                  No models returned from upstream.
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
    </div>
  );
}
