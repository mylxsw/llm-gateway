/**
 * Loading State Component
 * Used to display loading, error, and empty data states.
 */

'use client';

import React from 'react';
import { Loader2, AlertCircle, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';

interface LoadingStateProps {
  /** Custom class name */
  className?: string;
}

/**
 * Loading Spinner
 */
export function LoadingSpinner({ className }: LoadingStateProps) {
  return (
    <div className={cn('flex items-center justify-center py-8', className)}>
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" suppressHydrationWarning />
    </div>
  );
}

interface ErrorStateProps extends LoadingStateProps {
  /** Error message */
  message?: string;
  /** Retry callback */
  onRetry?: () => void;
}

/**
 * Error State
 */
export function ErrorState({
  className,
  message,
  onRetry,
}: ErrorStateProps) {
  const t = useTranslations('common');
  const resolvedMessage = message ?? t('loadFailed');
  return (
    <div className={cn('flex flex-col items-center justify-center py-8', className)}>
      <AlertCircle className="h-10 w-10 text-destructive" suppressHydrationWarning />
      <p className="mt-2 text-sm text-muted-foreground">{resolvedMessage}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          {t('retry')}
        </Button>
      )}
    </div>
  );
}

interface EmptyStateProps extends LoadingStateProps {
  /** Empty state message */
  message?: string;
  /** Action button text */
  actionText?: string;
  /** Action callback */
  onAction?: () => void;
}

/**
 * Empty Data State
 */
export function EmptyState({
  className,
  message,
  actionText,
  onAction,
}: EmptyStateProps) {
  const t = useTranslations('common');
  const resolvedMessage = message ?? t('noDataAvailable');
  return (
    <div className={cn('flex flex-col items-center justify-center py-8', className)}>
      <Inbox className="h-10 w-10 text-muted-foreground" suppressHydrationWarning />
      <p className="mt-2 text-sm text-muted-foreground">{resolvedMessage}</p>
      {actionText && onAction && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </div>
  );
}
