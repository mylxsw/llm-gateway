/**
 * API Key Management Page
 * Provides API Key list display and CRUD operations
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus } from 'lucide-react';
import { ApiKeyForm, ApiKeyList } from '@/components/api-keys';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useApiKeys,
  useCreateApiKey,
  useUpdateApiKey,
  useDeleteApiKey,
} from '@/lib/hooks';
import { ApiKey, ApiKeyCreate, ApiKeyUpdate } from '@/types';

/**
 * API Key Management Page Component
 */
export default function ApiKeysPage() {
  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Form dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [createdKey, setCreatedKey] = useState<ApiKey | null>(null);

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingKey, setDeletingKey] = useState<ApiKey | null>(null);

  // Data query
  const { data, isLoading, isError, refetch } = useApiKeys({
    page,
    page_size: pageSize,
  });

  // Mutations
  const createMutation = useCreateApiKey();
  const updateMutation = useUpdateApiKey();
  const deleteMutation = useDeleteApiKey();

  // Open create form
  const handleCreate = () => {
    setEditingKey(null);
    setCreatedKey(null);
    setFormOpen(true);
  };

  // Open edit form
  const handleEdit = (apiKey: ApiKey) => {
    setEditingKey(apiKey);
    setCreatedKey(null);
    setFormOpen(true);
  };

  // Open delete confirmation
  const handleDelete = (apiKey: ApiKey) => {
    setDeletingKey(apiKey);
    setDeleteDialogOpen(true);
  };

  // Submit form
  const handleSubmit = async (formData: ApiKeyCreate | ApiKeyUpdate) => {
    try {
      if (editingKey) {
        // Update
        await updateMutation.mutateAsync({
          id: editingKey.id,
          data: formData as ApiKeyUpdate,
        });
        setFormOpen(false);
        setEditingKey(null);
      } else {
        // Create - Show created key
        const newKey = await createMutation.mutateAsync(formData as ApiKeyCreate);
        setCreatedKey(newKey);
      }
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  // Close form
  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setFormOpen(false);
      setEditingKey(null);
      setCreatedKey(null);
    }
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (!deletingKey) return;
    try {
      await deleteMutation.mutateAsync(deletingKey.id);
      setDeleteDialogOpen(false);
      setDeletingKey(null);
    } catch {
      // Errors are surfaced via mutation onError toast
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Title and Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Key Management</h1>
          <p className="mt-1 text-muted-foreground">
            Manage API Keys used for accessing proxy interfaces
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" suppressHydrationWarning />
          New API Key
        </Button>
      </div>

      {/* Data List */}
      <Card>
        <CardHeader>
          <CardTitle>API Key List</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="Failed to load API Key list"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message="No API Keys found"
              actionText="New API Key"
              onAction={handleCreate}
            />
          )}
          
          {!isLoading && !isError && data && data.items.length > 0 && (
            <>
              <ApiKeyList
                apiKeys={data.items}
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
      <ApiKeyForm
        open={formOpen}
        onOpenChange={handleCloseForm}
        apiKey={editingKey}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
        createdKey={createdKey}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete API Key"
        description={`Are you sure you want to delete API Key "${deletingKey?.key_name}"? Clients using this key will no longer be able to access the service.`}
        confirmText="Delete"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
