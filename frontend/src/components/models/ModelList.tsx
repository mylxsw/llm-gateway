/**
 * 模型映射列表组件
 * 展示模型映射数据表格
 */

'use client';

import React from 'react';
import Link from 'next/link';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Eye, Pencil, Trash2 } from 'lucide-react';
import { ModelMapping } from '@/types';
import { formatDateTime, getActiveStatus } from '@/lib/utils';

interface ModelListProps {
  /** 模型映射列表数据 */
  models: ModelMapping[];
  /** 编辑回调 */
  onEdit: (model: ModelMapping) => void;
  /** 删除回调 */
  onDelete: (model: ModelMapping) => void;
}

/**
 * 模型映射列表组件
 */
export function ModelList({
  models,
  onEdit,
  onDelete,
}: ModelListProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>请求模型名</TableHead>
          <TableHead>策略</TableHead>
          <TableHead>供应商数量</TableHead>
          <TableHead>匹配规则</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>更新时间</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map((model) => {
          const status = getActiveStatus(model.is_active);
          return (
            <TableRow key={model.requested_model}>
              <TableCell className="font-medium font-mono">
                {model.requested_model}
              </TableCell>
              <TableCell>
                <Badge variant="outline">{model.strategy}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{model.provider_count || 0}</Badge>
              </TableCell>
              <TableCell>
                {model.matching_rules ? (
                  <Badge variant="outline" className="text-blue-600">
                    已配置
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell>
                <Badge className={status.className}>{status.text}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(model.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Link href={`/models/${encodeURIComponent(model.requested_model)}`}>
                    <Button variant="ghost" size="icon" title="查看详情">
                      <Eye className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(model)}
                    title="编辑"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(model)}
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
  );
}
