/**
 * API Key 管理页面
 * 提供 API Key 的列表展示和 CRUD 操作
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
 * API Key 管理页面组件
 */
export default function ApiKeysPage() {
  // 分页状态
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // 表单对话框状态
  const [formOpen, setFormOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [createdKey, setCreatedKey] = useState<ApiKey | null>(null);

  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingKey, setDeletingKey] = useState<ApiKey | null>(null);

  // 数据查询
  const { data, isLoading, isError, refetch } = useApiKeys({
    page,
    page_size: pageSize,
  });

  // Mutations
  const createMutation = useCreateApiKey();
  const updateMutation = useUpdateApiKey();
  const deleteMutation = useDeleteApiKey();

  // 打开新建表单
  const handleCreate = () => {
    setEditingKey(null);
    setCreatedKey(null);
    setFormOpen(true);
  };

  // 打开编辑表单
  const handleEdit = (apiKey: ApiKey) => {
    setEditingKey(apiKey);
    setCreatedKey(null);
    setFormOpen(true);
  };

  // 打开删除确认
  const handleDelete = (apiKey: ApiKey) => {
    setDeletingKey(apiKey);
    setDeleteDialogOpen(true);
  };

  // 提交表单
  const handleSubmit = async (formData: ApiKeyCreate | ApiKeyUpdate) => {
    try {
      if (editingKey) {
        // 更新
        await updateMutation.mutateAsync({
          id: editingKey.id,
          data: formData as ApiKeyUpdate,
        });
        setFormOpen(false);
        setEditingKey(null);
      } else {
        // 创建 - 显示新建的 key
        const newKey = await createMutation.mutateAsync(formData as ApiKeyCreate);
        setCreatedKey(newKey);
      }
    } catch (error) {
      console.error('保存失败:', error);
    }
  };

  // 关闭表单
  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setFormOpen(false);
      setEditingKey(null);
      setCreatedKey(null);
    }
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingKey) return;
    try {
      await deleteMutation.mutateAsync(deletingKey.id);
      setDeleteDialogOpen(false);
      setDeletingKey(null);
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">API Key 管理</h1>
          <p className="mt-1 text-muted-foreground">
            管理用于访问代理接口的 API Key
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          新建 API Key
        </Button>
      </div>

      {/* 数据列表 */}
      <Card>
        <CardHeader>
          <CardTitle>API Key 列表</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <LoadingSpinner />}
          
          {isError && (
            <ErrorState
              message="加载 API Key 列表失败"
              onRetry={() => refetch()}
            />
          )}
          
          {!isLoading && !isError && data?.items.length === 0 && (
            <EmptyState
              message="暂无 API Key"
              actionText="新建 API Key"
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

      {/* 新建/编辑表单 */}
      <ApiKeyForm
        open={formOpen}
        onOpenChange={handleCloseForm}
        apiKey={editingKey}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
        createdKey={createdKey}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除 API Key"
        description={`确定要删除 API Key「${deletingKey?.key_name}」吗？删除后使用该 Key 的客户端将无法访问。`}
        confirmText="删除"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
