/**
 * Loading State Component
 * Used to display loading, error, and empty data states.
 */

'use client';

import React from 'react';
import { Loader2, AlertCircle, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
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
  message = 'Failed to load, please try again later',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-8', className)}>
      <AlertCircle className="h-10 w-10 text-destructive" />
      <p className="mt-2 text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          Retry
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
  message = 'No data available',
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