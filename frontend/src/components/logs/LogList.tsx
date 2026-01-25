/**
 * Log List Component
 * Displays log data table
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
  Eye, 
  ArrowRight,
  Waves,
} from 'lucide-react';
import { RequestLog } from '@/types';
import { formatDateTime, getStatusColor, formatUsd } from '@/lib/utils';

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
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[180px]">Time</TableHead>
          <TableHead>Provider</TableHead>
          <TableHead>Model Mapping</TableHead>
          <TableHead>In/Out Token</TableHead>
          <TableHead>Cost</TableHead>
          <TableHead>Status/Retry</TableHead>
          <TableHead className="text-right">Action</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log) => {
          const statusColor = getStatusColor(log.response_status);
          
          return (
            <TableRow key={log.id} className="group">
              <TableCell className="font-mono text-xs text-muted-foreground">
                <div>{formatDateTime(log.request_time)}</div>
                <div className="mt-1 truncate opacity-0 transition-opacity group-hover:opacity-100" title={log.trace_id}>
                  {log.trace_id?.slice(0, 8)}...
                </div>
              </TableCell>
              <TableCell>{log.provider_name}</TableCell>
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
                    {log.is_stream && (
                      <span title="Stream Request" className="ml-1">
                        <Waves className="h-3 w-3 text-blue-500" suppressHydrationWarning />
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {log.api_key_name}
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <div className="flex flex-col text-xs">
                  <span>In: {log.input_tokens || 0}</span>
                  <span className="text-muted-foreground">Out: {log.output_tokens || 0}</span>
                </div>
              </TableCell>
              <TableCell
                className="font-mono text-xs"
                title={`Input: ${formatUsd(log.input_cost)}\nOutput: ${formatUsd(log.output_cost)}`}
              >
                {formatUsd(log.total_cost)}
              </TableCell>
              <TableCell>
                <div className="flex flex-col items-start gap-1">
                  <Badge variant="outline" className={statusColor}>
                    {log.response_status || 'Unknown'}
                  </Badge>
                  {log.retry_count > 0 && (
                    <span className="text-xs text-orange-500">
                      Retry: {log.retry_count}
                    </span>
                  )}
                </div>
              </TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onView(log)}
                  title="View Details"
                >
                  <Eye className="h-4 w-4" suppressHydrationWarning />
                </Button>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
