/**
 * 加载状态组件
 * 用于显示数据加载中、加载失败、数据为空等状态
 */

'use client';

import React from 'react';
import { Loader2, AlertCircle, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface LoadingStateProps {
  /** 自定义类名 */
  className?: string;
}

/**
 * 加载中状态
 */
export function LoadingSpinner({ className }: LoadingStateProps) {
  return (
    <div className={cn('flex items-center justify-center py-8', className)}>
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

interface ErrorStateProps extends LoadingStateProps {
  /** 错误消息 */
  message?: string;
  /** 重试回调 */
  onRetry?: () => void;
}

/**
 * 错误状态
 */
export function ErrorState({
  className,
  message = '加载失败，请稍后重试',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-8', className)}>
      <AlertCircle className="h-10 w-10 text-destructive" />
      <p className="mt-2 text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          重试
        </Button>
      )}
    </div>
  );
}

interface EmptyStateProps extends LoadingStateProps {
  /** 空状态提示 */
  message?: string;
  /** 操作按钮文本 */
  actionText?: string;
  /** 操作回调 */
  onAction?: () => void;
}

/**
 * 空数据状态
 */
export function EmptyState({
  className,
  message = '暂无数据',
  actionText,
  onAction,
}: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-8', className)}>
      <Inbox className="h-10 w-10 text-muted-foreground" />
      <p className="mt-2 text-sm text-muted-foreground">{message}</p>
      {actionText && onAction && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </div>
  );
}
