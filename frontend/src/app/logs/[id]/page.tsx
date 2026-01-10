/**
 * 日志详情页面
 * 展示单条日志的完整信息
 */

'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { LogDetail } from '@/components/logs';
import { LoadingSpinner, ErrorState } from '@/components/common';
import { useLogDetail } from '@/lib/hooks';

/**
 * 日志详情页面组件
 */
export default function LogDetailPage() {
  const params = useParams();
  const logId = Number(params.id);

  // 数据查询
  const { data: log, isLoading, isError, refetch } = useLogDetail(logId);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (isError || !log) {
    return (
      <ErrorState
        message="加载日志详情失败"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* 返回按钮和标题 */}
      <div className="flex items-center gap-4">
        <Link href="/logs">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">日志详情</h1>
          <p className="mt-1 text-muted-foreground">
            日志 ID: {log.id}
          </p>
        </div>
      </div>

      {/* 日志详情内容 */}
      <LogDetail log={log} />
    </div>
  );
}
