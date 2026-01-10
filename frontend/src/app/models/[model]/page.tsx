/**
 * 模型详情页面
 * 展示模型映射详情和供应商配置
 */

'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowLeft, Plus, Pencil, Trash2 } from 'lucide-react';
import { ModelProviderForm } from '@/components/models';
import { JsonViewer, ConfirmDialog, LoadingSpinner, ErrorState } from '@/components/common';
import {
  useModel,
  useProviders,
  useCreateModelProvider,
  useUpdateModelProvider,
  useDeleteModelProvider,
} from '@/lib/hooks';
import {
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
} from '@/types';
import { formatDateTime, getActiveStatus } from '@/lib/utils';

/**
 * 模型详情页面组件
 */
export default function ModelDetailPage() {
  const params = useParams();
  const router = useRouter();
  const requestedModel = decodeURIComponent(params.model as string);

  // 表单对话框状态
  const [formOpen, setFormOpen] = useState(false);
  const [editingMapping, setEditingMapping] = useState<ModelMappingProvider | null>(null);

  // 删除确认对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingMapping, setDeletingMapping] = useState<ModelMappingProvider | null>(null);

  // 数据查询
  const { data: model, isLoading, isError, refetch } = useModel(requestedModel);
  const { data: providersData } = useProviders({ is_active: true });

  // Mutations
  const createMutation = useCreateModelProvider();
  const updateMutation = useUpdateModelProvider();
  const deleteMutation = useDeleteModelProvider();

  // 打开新建表单
  const handleAddProvider = () => {
    setEditingMapping(null);
    setFormOpen(true);
  };

  // 打开编辑表单
  const handleEditMapping = (mapping: ModelMappingProvider) => {
    setEditingMapping(mapping);
    setFormOpen(true);
  };

  // 打开删除确认
  const handleDeleteMapping = (mapping: ModelMappingProvider) => {
    setDeletingMapping(mapping);
    setDeleteDialogOpen(true);
  };

  // 提交表单
  const handleSubmit = async (
    formData: ModelMappingProviderCreate | ModelMappingProviderUpdate
  ) => {
    try {
      if (editingMapping) {
        await updateMutation.mutateAsync({
          id: editingMapping.id,
          data: formData as ModelMappingProviderUpdate,
        });
      } else {
        await createMutation.mutateAsync(formData as ModelMappingProviderCreate);
      }
      setFormOpen(false);
      setEditingMapping(null);
      refetch();
    } catch (error) {
      console.error('保存失败:', error);
    }
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingMapping) return;
    try {
      await deleteMutation.mutateAsync(deletingMapping.id);
      setDeleteDialogOpen(false);
      setDeletingMapping(null);
      refetch();
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (isError || !model) {
    return (
      <ErrorState
        message="加载模型详情失败"
        onRetry={() => refetch()}
      />
    );
  }

  const status = getActiveStatus(model.is_active);

  return (
    <div className="space-y-6">
      {/* 返回按钮和标题 */}
      <div className="flex items-center gap-4">
        <Link href="/models">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold font-mono">{model.requested_model}</h1>
          <p className="mt-1 text-muted-foreground">模型映射详情</p>
        </div>
      </div>

      {/* 基本信息 */}
      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">请求模型名</p>
              <code className="text-sm">{model.requested_model}</code>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">选择策略</p>
              <Badge variant="outline">{model.strategy}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">状态</p>
              <Badge className={status.className}>{status.text}</Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">更新时间</p>
              <p className="text-sm">{formatDateTime(model.updated_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 匹配规则 */}
      {model.matching_rules && (
        <Card>
          <CardHeader>
            <CardTitle>匹配规则</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={model.matching_rules} />
          </CardContent>
        </Card>
      )}

      {/* 功能描述 */}
      {model.capabilities && (
        <Card>
          <CardHeader>
            <CardTitle>功能描述</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={model.capabilities} />
          </CardContent>
        </Card>
      )}

      {/* 供应商配置 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>供应商配置</CardTitle>
          <Button onClick={handleAddProvider} size="sm">
            <Plus className="mr-2 h-4 w-4" />
            添加供应商
          </Button>
        </CardHeader>
        <CardContent>
          {model.providers && model.providers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>供应商</TableHead>
                  <TableHead>目标模型</TableHead>
                  <TableHead>优先级</TableHead>
                  <TableHead>权重</TableHead>
                  <TableHead>规则</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {model.providers.map((mapping) => {
                  const mappingStatus = getActiveStatus(mapping.is_active);
                  return (
                    <TableRow key={mapping.id}>
                      <TableCell className="font-medium">
                        {mapping.provider_name}
                      </TableCell>
                      <TableCell>
                        <code className="text-sm">{mapping.target_model_name}</code>
                      </TableCell>
                      <TableCell>{mapping.priority}</TableCell>
                      <TableCell>{mapping.weight}</TableCell>
                      <TableCell>
                        {mapping.provider_rules ? (
                          <Badge variant="outline" className="text-blue-600">
                            已配置
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={mappingStatus.className}>
                          {mappingStatus.text}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleEditMapping(mapping)}
                            title="编辑"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteMapping(mapping)}
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="py-8 text-center text-muted-foreground">
              暂未配置供应商，点击上方按钮添加
            </p>
          )}
        </CardContent>
      </Card>

      {/* 供应商配置表单 */}
      <ModelProviderForm
        open={formOpen}
        onOpenChange={setFormOpen}
        requestedModel={requestedModel}
        providers={providersData?.items || []}
        mapping={editingMapping}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="删除供应商配置"
        description={`确定要删除供应商「${deletingMapping?.provider_name}」的配置吗？`}
        confirmText="删除"
        onConfirm={handleConfirmDelete}
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
