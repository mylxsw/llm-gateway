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
import { Eye, ArrowRight, Waves } from 'lucide-react';
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
          <TableHead>请求时间</TableHead>
          <TableHead>模型映射</TableHead>
          <TableHead>供应商</TableHead>
          <TableHead>状态/重试</TableHead>
          <TableHead>延迟/总时</TableHead>
          <TableHead>输入/输出 Token</TableHead>
          <TableHead>Token消耗/Stream</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log) => (
          <TableRow key={log.id}>
            <TableCell className="whitespace-nowrap text-muted-foreground">
              {formatDateTime(log.request_time, { showSeconds: true })}
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <code className="text-sm">{log.requested_model || '-'}</code>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <code className="text-sm">{log.target_model || '-'}</code>
              </div>
            </TableCell>
            <TableCell>{log.provider_name || '-'}</TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                {log.response_status ? (
                  <span className={getStatusColor(log.response_status)}>
                    {log.response_status}
                  </span>
                ) : (
                  '-'
                )}
                <span className="text-muted-foreground">/</span>
                {log.retry_count > 0 ? (
                  <Badge variant="warning">{log.retry_count}</Badge>
                ) : (
                  <span className="text-muted-foreground">0</span>
                )}
              </div>
            </TableCell>
            <TableCell className="text-muted-foreground">
              <div className="flex flex-col text-xs">
                <span>{formatDuration(log.first_byte_delay_ms)}</span>
                <span className="text-muted-foreground/70">
                  {formatDuration(log.total_time_ms)}
                </span>
              </div>
            </TableCell>
            <TableCell className="font-mono text-sm">
              <div className="flex items-center gap-1">
                <span>{formatNumber(log.input_tokens)}</span>
                <span className="text-muted-foreground">/</span>
                <span>{formatNumber(log.output_tokens)}</span>
              </div>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <span className="font-mono text-sm">
                  {formatNumber(
                    (log.input_tokens || 0) + (log.output_tokens || 0)
                  )}
                </span>
                <span className="text-muted-foreground">/</span>
                {log.is_stream ? (
                  <span title="流式请求">
                    <Waves className="h-4 w-4 text-blue-500" />
                  </span>
                ) : (
                  <span className="text-muted-foreground text-xs">-</span>
                )}
              </div>
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
