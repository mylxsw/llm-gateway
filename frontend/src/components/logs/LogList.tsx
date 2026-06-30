/**
 * Log List Component
 * Displays log data table with in-progress request support
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Eye, 
  ArrowRight,
  Waves,
  Loader2,
  XCircle,
} from 'lucide-react';
import { RequestLog } from '@/types';
import { formatDateTime, formatDuration, getStatusColor, formatUsd } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { useCancelLog } from '@/lib/hooks/useLogs';
import { ConfirmDialog } from '@/components/common';
import { toast } from 'sonner';

interface LogListProps {
  /** Log list data */
  logs: RequestLog[];
  /** View details callback */
  onView: (log: RequestLog) => void;
}

/**
 * Log List Component
 */
export function LogList({ logs, onView }: LogListProps) {
  const t = useTranslations('logs');
  const cancelMutation = useCancelLog();
  const [now, setNow] = React.useState(() => Date.now());
  const [cancelLogId, setCancelLogId] = React.useState<number | null>(null);

  const isInProgress = (log: RequestLog) => log.is_completed === false;

  React.useEffect(() => {
    if (!logs.some((log) => log.is_completed === false)) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [logs]);

  const renderResponseTime = (log: RequestLog) => {
    if (isInProgress(log)) {
      const startedAt = new Date(log.request_time).getTime();
      const elapsedMs = Number.isFinite(startedAt)
        ? Math.max(0, now - startedAt)
        : undefined;
      return (
        <div className="flex items-center gap-1 text-xs">
          <Loader2 className="h-3 w-3 animate-spin text-blue-500" suppressHydrationWarning />
          <span className="font-mono text-blue-500">
            {elapsedMs === undefined ? t('list.processing') : formatDuration(elapsedMs)}
          </span>
        </div>
      );
    }

    if (!log.is_stream) {
      return (
        <div className="font-mono text-xs">
          {formatDuration(log.total_time_ms)}
        </div>
      );
    }

    return (
      <div className="flex flex-col text-xs">
        <span className="font-mono">
          {t('list.ttfb')}: {formatDuration(log.first_byte_delay_ms)}
        </span>
        <span className="font-mono text-muted-foreground">
          {t('list.totalDuration')}: {formatDuration(log.total_time_ms)}
        </span>
      </div>
    );
  };

  const handleConfirmCancel = () => {
    if (cancelLogId === null) return;
    cancelMutation.mutate(cancelLogId, {
      onSuccess: () => {
        toast.success(t('toasts.cancelSuccess'));
        setCancelLogId(null);
      },
      onError: () => {
        toast.error(t('toasts.cancelFailed'));
      },
    });
  };

  return (
    <TooltipProvider>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[180px]">{t('list.columns.time')}</TableHead>
            <TableHead>{t('list.columns.provider')}</TableHead>
            <TableHead>{t('list.columns.modelMapping')}</TableHead>
            <TableHead>{t('list.columns.responseTime')}</TableHead>
            <TableHead>{t('list.columns.tokenInOut')}</TableHead>
            <TableHead>{t('list.columns.cost')}</TableHead>
            <TableHead>{t('list.columns.statusRetry')}</TableHead>
            <TableHead className="text-right">{t('list.columns.action')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => {
            const statusColor = getStatusColor(log.response_status);
            const inProgress = isInProgress(log);
            
            return (
              <TableRow key={log.id} className={`group ${inProgress ? 'bg-blue-50/30 dark:bg-blue-950/10' : ''}`}>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  <div>{formatDateTime(log.request_time)}</div>
                  <div className="mt-1 truncate opacity-0 transition-opacity group-hover:opacity-100" title={log.trace_id}>
                    {log.trace_id?.slice(0, 8)}...
                  </div>
                </TableCell>
                <TableCell>{log.provider_name || "-"}</TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1 font-medium">
                      {log.requested_model}
                      {log.requested_model !== log.target_model && (
                        <>
                          <ArrowRight className="h-3 w-3 text-muted-foreground" suppressHydrationWarning />
                          <span className="text-muted-foreground">
                            {log.target_model}
                          </span>
                        </>
                      )}
                      {log.is_stream && !inProgress && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="ml-1 inline-flex cursor-help">
                              <Waves className="h-3 w-3 text-blue-500" suppressHydrationWarning />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            {t('list.streamRequest')}
                          </TooltipContent>
                        </Tooltip>
                      )}
                      {inProgress && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="ml-1 inline-flex cursor-help">
                              <Loader2 className="h-3 w-3 animate-spin text-blue-500" suppressHydrationWarning />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            {t('list.processing')}
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {log.api_key_name}
                    </div>
                    {log.user_id && (
                      <div className="text-xs text-muted-foreground">
                        {t('list.userId', { userId: log.user_id })}
                      </div>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {renderResponseTime(log)}
                </TableCell>
                <TableCell>
                  {inProgress ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : (
                    <div className="flex flex-col text-xs">
                      <span>{t('list.inTokens', { count: log.input_tokens || 0 })}</span>
                      <span className="text-muted-foreground">
                        {t('list.outTokens', { count: log.output_tokens || 0 })}
                      </span>
                    </div>
                  )}
                </TableCell>
                <TableCell
                  className="font-mono text-xs"
                  title={t('list.costTooltip', {
                    input: formatUsd(log.input_cost),
                    output: formatUsd(log.output_cost),
                  })}
                >
                  {inProgress ? '—' : formatUsd(log.total_cost)}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col items-start gap-1">
                    <Badge
                      variant="outline"
                      className={inProgress ? 'text-muted-foreground' : statusColor}
                    >
                      {inProgress ? '-' : (log.response_status ?? t('unknown'))}
                    </Badge>
                    {log.retry_count > 0 && (
                      <span className="text-xs text-orange-500">
                        {t('list.retry', { count: log.retry_count })}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    {inProgress && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setCancelLogId(log.id)}
                            disabled={cancelMutation.isPending}
                            title={t('list.cancelRequest')}
                          >
                            <XCircle className="h-4 w-4 text-red-500" suppressHydrationWarning />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {t('list.cancelRequest')}
                        </TooltipContent>
                      </Tooltip>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onView(log)}
                      title={t('list.viewDetails')}
                    >
                      <Eye className="h-4 w-4" suppressHydrationWarning />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <ConfirmDialog
        open={cancelLogId !== null}
        onOpenChange={(open) => {
          if (!open) setCancelLogId(null);
        }}
        title={t('list.cancelConfirmTitle')}
        description={t('list.cancelConfirmDescription')}
        confirmText={t('list.cancelRequest')}
        onConfirm={handleConfirmCancel}
        destructive
        loading={cancelMutation.isPending}
      />
    </TooltipProvider>
  );
}
