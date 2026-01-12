/**
 * Log Detail Component
 * Displays detailed information of a request log, including request/response body, headers, etc.
 */

'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Clock, Server, AlertCircle, Shield, Play } from 'lucide-react';
import { RequestLogDetail } from '@/types';
import { formatDateTime, getStatusColor, formatDuration } from '@/lib/utils';
import { JsonViewer } from '@/components/common/JsonViewer';

interface LogDetailProps {
  /** Log data */
  log: RequestLogDetail | null;
  /** Whether detailed view is open */
  open: boolean;
  /** Close callback */
  onOpenChange: (open: boolean) => void;
}

/**
 * Log Detail Component
 */
export function LogDetail({ log, open, onOpenChange }: LogDetailProps) {
  const [activeTab, setActiveTab] = useState<'request' | 'response' | 'headers'>('request');

  if (!log) return null;

  const statusColor = getStatusColor(log.response_status);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto p-0 gap-0">
        <div className="flex h-full flex-col">
          {/* Header */}
          <div className="border-b p-6">
            <DialogHeader>
              <div className="flex items-start justify-between">
                <div>
                  <DialogTitle className="text-xl font-bold">Request Log Details</DialogTitle>
                  <DialogDescription className="mt-1 flex items-center gap-2">
                    <span className="font-mono">{log.trace_id}</span>
                  </DialogDescription>
                </div>
                <Badge className={statusColor}>
                  {log.response_status || 'Unknown'}
                </Badge>
              </div>
            </DialogHeader>

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
            <div className="mt-4 flex gap-4 rounded-lg bg-muted/50 p-3 text-sm flex-wrap">
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
          <div className="flex-1 p-6">
            <div className="w-full">
              <div className="flex border-b mb-4">
                <button
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === 'request'
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => setActiveTab('request')}
                >
                  Request Content
                </button>
                <button
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === 'response'
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => setActiveTab('response')}
                >
                  Response Content
                </button>
                <button
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === 'headers'
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => setActiveTab('headers')}
                >
                  Headers Info
                </button>
              </div>
              
              {activeTab === 'request' && (
                <div className="mt-4 space-y-4">
                  <div>
                    <h4 className="mb-2 text-sm font-medium">Request Body</h4>
                    <JsonViewer data={log.request_body} />
                  </div>
                </div>
              )}
              
              {activeTab === 'response' && (
                <div className="mt-4 space-y-4">
                  <div>
                    <h4 className="mb-2 text-sm font-medium">Response Body</h4>
                    <JsonViewer data={log.response_body || {}} />
                  </div>
                </div>
              )}
              
              {activeTab === 'headers' && (
                <div className="mt-4 space-y-4">
                  <div>
                    <h4 className="mb-2 text-sm font-medium">Request Headers</h4>
                    <JsonViewer data={log.request_headers} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}