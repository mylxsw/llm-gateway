/**
 * Provider Management Page
 * Provides provider list display and CRUD operations
 */

'use client';

import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Download, Upload } from 'lucide-react';
import { ProviderForm, ProviderList } from '@/components/providers';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
} from '@/lib/hooks';
import { exportProviders, importProviders } from '@/lib/api';
import { Provider, ProviderCreate, ProviderUpdate } from '@/types';

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

  // Data query
  const { data, isLoading, isError, refetch } = useProviders({
    page,
    page_size: pageSize,
  });

  // Mutations
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const deleteMutation = useDeleteProvider();

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
    } catch (error) {
      console.error('Save failed:', error);
    }
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (!deletingProvider) return;
    try {
      await deleteMutation.mutateAsync(deletingProvider.id);
      setDeleteDialogOpen(false);
      setDeletingProvider(null);
    } catch (error) {
      console.error('Delete failed:', error);
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
      const json = JSON.parse(text);
      const result = await importProviders(json);
      alert(`Import complete.\nSuccess: ${result.success}\nSkipped: ${result.skipped}`);
      refetch();
    } catch (error) {
      console.error('Import failed:', error);
      alert('Import failed: ' + (error as any).message);
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
    </div>
  );
}
