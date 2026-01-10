/**
 * 日志列表组件
 * 展示请求日志数据表格
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
import { Eye } from 'lucide-react';
import { RequestLog } from '@/types';
import {
  formatDateTime,
  formatDuration,
  formatNumber,
  getStatusColor,
} from '@/lib/utils';

interface LogListProps {
  /** 日志列表数据 */
  logs: RequestLog[];
}

/**
 * 日志列表组件
 */
export function LogList({ logs }: LogListProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[60px]">ID</TableHead>
          <TableHead>请求时间</TableHead>
          <TableHead>请求模型</TableHead>
          <TableHead>目标模型</TableHead>
          <TableHead>供应商</TableHead>
          <TableHead>状态码</TableHead>
          <TableHead>重试</TableHead>
          <TableHead>首字节延迟</TableHead>
          <TableHead>总耗时</TableHead>
          <TableHead>输入 Token</TableHead>
          <TableHead>输出 Token</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log) => (
          <TableRow key={log.id}>
            <TableCell className="font-mono text-sm">{log.id}</TableCell>
            <TableCell className="whitespace-nowrap text-muted-foreground">
              {formatDateTime(log.request_time, { showSeconds: true })}
            </TableCell>
            <TableCell>
              <code className="text-sm">{log.requested_model || '-'}</code>
            </TableCell>
            <TableCell>
              <code className="text-sm">{log.target_model || '-'}</code>
            </TableCell>
            <TableCell>{log.provider_name || '-'}</TableCell>
            <TableCell>
              {log.response_status ? (
                <span className={getStatusColor(log.response_status)}>
                  {log.response_status}
                </span>
              ) : (
                '-'
              )}
            </TableCell>
            <TableCell>
              {log.retry_count > 0 ? (
                <Badge variant="warning">{log.retry_count}</Badge>
              ) : (
                <span className="text-muted-foreground">0</span>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatDuration(log.first_byte_delay_ms)}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatDuration(log.total_time_ms)}
            </TableCell>
            <TableCell className="font-mono text-sm">
              {formatNumber(log.input_tokens)}
            </TableCell>
            <TableCell className="font-mono text-sm">
              {formatNumber(log.output_tokens)}
            </TableCell>
            <TableCell className="text-right">
              <Link href={`/logs/${log.id}`}>
                <Button variant="ghost" size="icon" title="查看详情">
                  <Eye className="h-4 w-4" />
                </Button>
              </Link>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
