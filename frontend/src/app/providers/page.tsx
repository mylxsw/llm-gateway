/**
 * 供应商管理页面
 * 提供供应商的列表展示和 CRUD 操作
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus } from 'lucide-react';
import { ProviderForm, ProviderList } from '@/components/providers';
import { Pagination, ConfirmDialog, LoadingSpinner, ErrorState, EmptyState } from '@/components/common';
import {
  useProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
} from '@/lib/hooks';
import { Provider, ProviderCreate, ProviderUpdate } from '@/types';

/**
 * 供应商管理页面组件
 */
export default function ProvidersPage() {
  // 分页状态
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // 表单对话框状态
  const [formOpen, setFormOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);

  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingProvider, setDeletingProvider] = useState<Provider | null>(null);

  // 数据查询
  const { data, isLoading, isError, refetch } = useProviders({
    page,
    page_size: pageSize,
  });

  // Mutations
  const createMutation = useCreateProvider();
  const updateMutation = useUpdateProvider();
  const deleteMutation = useDeleteProvider();

  // 打开新建表单
  const handleCreate = () => {
    setEditingProvider(null);
    setFormOpen(true);
  };

  // 打开编辑表单
  const handleEdit = (provider: Provider) => {
    setEditingProvider(provider);
    setFormOpen(true);
  };

  // 打开删除确认
  const handleDelete = (provider: Provider) => {
    setDeletingProvider(provider);
    setDeleteDialogOpen(true);
  };

  // 提交表单
  const handleSubmit = async (formData: ProviderCreate | ProviderUpdate) => {
    try {
      if (editingProvider) {
        // 更新
        await updateMutation.mutateAsync({
          id: editingProvider.id,
          data: formData as ProviderUpdate,
        });
      } else {
        // 创建
        await createMutation.mutateAsync(formData as ProviderCreate);
      }
      setFormOpen(false);
      setEditingProvider(null);
    } catch (error) {
      console.error('保存失败:', error);
    }
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingProvider) return;
    try {
      await deleteMutation.mutateAsync(deletingProvider.id);
      setDeleteDialogOpen(false);
      setDeletingProvider(null);
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">供应商管理</h1>
          <p className="mt-1 text-muted-foreground">
            管理上游 AI 供应商配置
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          新增供应商
        </Button>
      </div>

      {/* 数据列表 */}
      <Card>
        <CardHeader>
          <CardTitle>供应商列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="加载供应商列表失败"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message="暂无供应商"
              actionText="新增供应商"
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

      {/* 新建/编辑表单 */}
      <ProviderForm
        open={formOpen}
        onOpenChange={setFormOpen}
        provider={editingProvider}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除供应商"
        description={`确定要删除供应商「${deletingProvider?.name}」吗？如果该供应商被模型引用，将无法删除。`}
        confirmText="删除"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
