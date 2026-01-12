/**
 * Log Detail Page
 * Displays full information of a single log
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
 * Log Detail Page Component
 */
export default function LogDetailPage() {
  const params = useParams();
  const idParam = params?.id;
  const logId = Number(Array.isArray(idParam) ? idParam[0] : idParam);

  // Data query
  const { data: log, isLoading, isError, refetch } = useLogDetail(logId);

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (!Number.isFinite(logId)) {
    return (
      <ErrorState
        message="Invalid log id"
        onRetry={() => {
          window.location.href = '/logs';
        }}
      />
    );
  }

  if (isError || !log) {
    return (
      <ErrorState
        message="Failed to load log details"
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Back Button and Title */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/logs">
            <Button variant="ghost" size="icon" aria-label="Back to logs">
              <ArrowLeft className="h-4 w-4" suppressHydrationWarning />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Log Details</h1>
            <p className="mt-1 text-muted-foreground">
              Log ID: {log.id}
            </p>
          </div>
        </div>
      </div>

      {/* Log Detail Content (Rendered as a page) */}
      <LogDetail log={log} />
    </div>
  );
}
