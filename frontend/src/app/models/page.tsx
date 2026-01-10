/**
 * 模型管理页面
 * 提供模型映射的列表展示和 CRUD 操作
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
 * 模型管理页面组件
 */
export default function ModelsPage() {
  // 分页状态
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // 表单对话框状态
  const [formOpen, setFormOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelMapping | null>(null);

  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingModel, setDeletingModel] = useState<ModelMapping | null>(null);

  // 数据查询
  const { data, isLoading, isError, refetch } = useModels({
    page,
    page_size: pageSize,
  });

  // Mutations
  const createMutation = useCreateModel();
  const updateMutation = useUpdateModel();
  const deleteMutation = useDeleteModel();

  // 打开新建表单
  const handleCreate = () => {
    setEditingModel(null);
    setFormOpen(true);
  };

  // 打开编辑表单
  const handleEdit = (model: ModelMapping) => {
    setEditingModel(model);
    setFormOpen(true);
  };

  // 打开删除确认
  const handleDelete = (model: ModelMapping) => {
    setDeletingModel(model);
    setDeleteDialogOpen(true);
  };

  // 提交表单
  const handleSubmit = async (formData: ModelMappingCreate | ModelMappingUpdate) => {
    try {
      if (editingModel) {
        // 更新
        await updateMutation.mutateAsync({
          requestedModel: editingModel.requested_model,
          data: formData as ModelMappingUpdate,
        });
      } else {
        // 创建
        await createMutation.mutateAsync(formData as ModelMappingCreate);
      }
      setFormOpen(false);
      setEditingModel(null);
    } catch (error) {
      console.error('保存失败:', error);
    }
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingModel) return;
    try {
      await deleteMutation.mutateAsync(deletingModel.requested_model);
      setDeleteDialogOpen(false);
      setDeletingModel(null);
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">模型管理</h1>
          <p className="mt-1 text-muted-foreground">
            配置模型映射规则和供应商
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          新增模型
        </Button>
      </div>

      {/* 数据列表 */}
      <Card>
        <CardHeader>
          <CardTitle>模型映射列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="加载模型列表失败"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message="暂无模型配置"
              actionText="新增模型"
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

      {/* 新建/编辑表单 */}
      <ModelForm
        open={formOpen}
        onOpenChange={setFormOpen}
        model={editingModel}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除模型映射"
        description={`确定要删除模型「${deletingModel?.requested_model}」吗？这将同时删除所有关联的供应商配置。`}
        confirmText="删除"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
