/**
 * 日志详情组件
 * 展示单条日志的完整信息
 */

'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { JsonViewer } from '@/components/common/JsonViewer';
import { RequestLogDetail } from '@/types';
import {
  formatDateTime,
  formatDuration,
  formatNumber,
  getStatusColor,
} from '@/lib/utils';

interface LogDetailProps {
  /** 日志详情数据 */
  log: RequestLogDetail;
}

/**
 * 日志详情组件
 */
export function LogDetail({ log }: LogDetailProps): React.ReactElement {
  return (
    <div className="space-y-6">
      {/* 基本信息 */}
      <Card>
        <CardHeader>
          <CardTitle>基本信息</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">日志 ID</p>
              <p className="font-mono">{String(log.id)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">请求时间</p>
              <p>{formatDateTime(log.request_time, { showSeconds: true })}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Trace ID</p>
              <p className="font-mono text-sm">{log.trace_id || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">状态码</p>
              <p className={getStatusColor(log.response_status)}>
                {log.response_status != null ? String(log.response_status) : '-'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Key 信息 */}
      <Card>
        <CardHeader>
          <CardTitle>API Key 信息</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">API Key ID</p>
              <p>{log.api_key_id != null ? String(log.api_key_id) : '-'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">API Key 名称</p>
              <p>{log.api_key_name || '-'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 模型与供应商 */}
      <Card>
        <CardHeader>
          <CardTitle>模型与供应商</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">请求模型</p>
              <code className="text-sm">{log.requested_model || '-'}</code>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">目标模型</p>
              <code className="text-sm">{log.target_model || '-'}</code>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">供应商 ID</p>
              <p>{log.provider_id != null ? String(log.provider_id) : '-'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">供应商名称</p>
              <p>{log.provider_name || '-'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 性能指标 */}
      <Card>
        <CardHeader>
          <CardTitle>性能指标</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <div>
              <p className="text-sm text-muted-foreground">重试次数</p>
              {log.retry_count > 0 ? (
                <Badge variant="warning">{log.retry_count}</Badge>
              ) : (
                <p>0</p>
              )}
            </div>
            <div>
              <p className="text-sm text-muted-foreground">首字节延迟</p>
              <p>{formatDuration(log.first_byte_delay_ms)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">总耗时</p>
              <p>{formatDuration(log.total_time_ms)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">输入 Token</p>
              <p className="font-mono">{formatNumber(log.input_tokens)}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">输出 Token</p>
              <p className="font-mono">{formatNumber(log.output_tokens)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 请求头 */}
      {log.request_headers && (
        <Card>
          <CardHeader>
            <CardTitle>请求头（已脱敏）</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={log.request_headers} />
          </CardContent>
        </Card>
      )}

      {/* 请求体 */}
      {log.request_body && (
        <Card>
          <CardHeader>
            <CardTitle>请求体</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={log.request_body} />
          </CardContent>
        </Card>
      )}

      {/* 响应体 */}
      {log.response_body && (
        <Card>
          <CardHeader>
            <CardTitle>响应体</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={log.response_body} maxHeight="500px" />
          </CardContent>
        </Card>
      )}

      {/* 错误信息 */}
      {log.error_info && (
        <Card>
          <CardHeader>
            <CardTitle className="text-destructive">错误信息</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-md bg-destructive/10 p-4 text-sm text-destructive">
              {log.error_info}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
