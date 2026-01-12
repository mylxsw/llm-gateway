/**
 * Model Management Page
 * Provides model mapping list display and CRUD operations
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus } from 'lucide-react';
import { ModelForm, ModelList } from '@/components/models';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useModels,
  useCreateModel,
  useUpdateModel,
  useDeleteModel,
} from '@/lib/hooks';
import { ModelMapping, ModelMappingCreate, ModelMappingUpdate } from '@/types';

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

  // Data query
  const { data, isLoading, isError, refetch } = useModels({
    page,
    page_size: pageSize,
  });

  // Mutations
  const createMutation = useCreateModel();
  const updateMutation = useUpdateModel();
  const deleteMutation = useDeleteModel();

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
    } catch (error) {
      console.error('Save failed:', error);
    }
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (!deletingModel) return;
    try {
      await deleteMutation.mutateAsync(deletingModel.requested_model);
      setDeleteDialogOpen(false);
      setDeletingModel(null);
    } catch (error) {
      console.error('Delete failed:', error);
    }
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
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add Model
        </Button>
      </div>

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
    </div>
  );
}