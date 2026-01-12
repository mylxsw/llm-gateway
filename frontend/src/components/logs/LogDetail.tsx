/**
 * Log Detail Component
 * Displays detailed information of a request log, including request/response body, headers, etc.
 */

'use client';

import React from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Clock, Server, AlertCircle, Shield, Play } from 'lucide-react';
import { RequestLog } from '@/types';
import { formatDateTime, getStatusColor, formatDuration } from '@/lib/utils';
import { JsonViewer } from '@/components/common/JsonViewer';

interface LogDetailProps {
  /** Log data */
  log: RequestLog | null;
  /** Whether detailed view is open */
  open: boolean;
  /** Close callback */
  onOpenChange: (open: boolean) => void;
}

/**
 * Log Detail Component
 */
export function LogDetail({ log, open, onOpenChange }: LogDetailProps) {
  if (!log) return null;

  const statusColor = getStatusColor(log.response_status);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[800px] sm:max-w-[800px] p-0">
        <div className="flex h-full flex-col">
          {/* Header */}
          <div className="border-b p-6">
            <SheetHeader>
              <div className="flex items-start justify-between">
                <div>
                  <SheetTitle className="text-xl font-bold">Request Log Details</SheetTitle>
                  <SheetDescription className="mt-1 flex items-center gap-2">
                    <span className="font-mono">{log.trace_id}</span>
                  </SheetDescription>
                </div>
                <Badge className={statusColor.className}>
                  {log.response_status || 'Unknown'}
                </Badge>
              </div>
            </SheetHeader>

            {/* Basic Info */}
            <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="h-4 w-4" />
                <span>Request Time:</span>
                <span className="font-medium text-foreground">
                  {formatDateTime(log.request_time)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Server className="h-4 w-4" />
                <span>Provider:</span>
                <span className="font-medium text-foreground">
                  {log.provider_name}
                </span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Shield className="h-4 w-4" />
                <span>API Key:</span>
                <span className="font-medium text-foreground">
                  {log.api_key_name} ({log.api_key_id})
                </span>
              </div>
              <div className="flex items-center gap-2 text-muted-foreground">
                <Play className="h-4 w-4" />
                <span>Model:</span>
                <span className="font-medium text-foreground">
                  {log.requested_model} → {log.target_model}
                </span>
              </div>
            </div>

            {/* Metrics */}
            <div className="mt-4 flex gap-4 rounded-lg bg-muted/50 p-3 text-sm">
              <div>
                <span className="text-muted-foreground">Latency:</span>
                <span className="ml-1 font-medium">{log.first_byte_delay_ms}ms</span>
              </div>
              <div>
                <span className="text-muted-foreground">Total Time:</span>
                <span className="ml-1 font-medium">
                  {formatDuration(log.total_time_ms || 0)}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Input Token:</span>
                <span className="ml-1 font-medium">{log.input_tokens}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Output Token:</span>
                <span className="ml-1 font-medium">{log.output_tokens}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Retries:</span>
                <span className="ml-1 font-medium">{log.retry_count}</span>
              </div>
            </div>

            {/* Error Info */}
            {log.error_info && (
              <div className="mt-4 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <div className="break-all">{log.error_info}</div>
              </div>
            )}
          </div>

          {/* Content Area */}
          <ScrollArea className="flex-1 p-6">
            <Tabs defaultValue="request" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="request">Request Content</TabsTrigger>
                <TabsTrigger value="response">Response Content</TabsTrigger>
                <TabsTrigger value="headers">Headers Info</TabsTrigger>
              </TabsList>
              
              <TabsContent value="request" className="mt-4 space-y-4">
                <div>
                  <h4 className="mb-2 text-sm font-medium">Request Body</h4>
                  <JsonViewer data={log.request_body} />
                </div>
              </TabsContent>
              
              <TabsContent value="response" className="mt-4 space-y-4">
                <div>
                  <h4 className="mb-2 text-sm font-medium">Response Body</h4>
                  <JsonViewer data={log.response_body || {}} />
                </div>
              </TabsContent>
              
              <TabsContent value="headers" className="mt-4 space-y-4">
                <div>
                  <h4 className="mb-2 text-sm font-medium">Request Headers</h4>
                  <JsonViewer data={log.request_headers} />
                </div>
              </TabsContent>
            </Tabs>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
}