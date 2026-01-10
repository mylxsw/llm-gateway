/**
 * 供应商列表组件
 * 展示供应商数据表格，包含操作按钮
 */

'use client';

import React from 'react';
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
import { Pencil, Trash2 } from 'lucide-react';
import { Provider } from '@/types';
import { formatDateTime, truncate, getActiveStatus } from '@/lib/utils';

interface ProviderListProps {
  /** 供应商列表数据 */
  providers: Provider[];
  /** 编辑回调 */
  onEdit: (provider: Provider) => void;
  /** 删除回调 */
  onDelete: (provider: Provider) => void;
}

/**
 * 供应商列表组件
 */
export function ProviderList({
  providers,
  onEdit,
  onDelete,
}: ProviderListProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[60px]">ID</TableHead>
          <TableHead>名称</TableHead>
          <TableHead>接口地址</TableHead>
          <TableHead>协议</TableHead>
          <TableHead>API 类型</TableHead>
          <TableHead>状态</TableHead>
          <TableHead>更新时间</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {providers.map((provider) => {
          const status = getActiveStatus(provider.is_active);
          return (
            <TableRow key={provider.id}>
              <TableCell className="font-mono text-sm">
                {provider.id}
              </TableCell>
              <TableCell className="font-medium">{provider.name}</TableCell>
              <TableCell className="max-w-[200px]">
                <span title={provider.base_url}>
                  {truncate(provider.base_url, 30)}
                </span>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{provider.protocol}</Badge>
              </TableCell>
              <TableCell>{provider.api_type}</TableCell>
              <TableCell>
                <Badge className={status.className}>{status.text}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(provider.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(provider)}
                    title="编辑"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(provider)}
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
