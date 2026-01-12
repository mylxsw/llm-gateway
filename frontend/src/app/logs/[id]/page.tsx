/**
 * Log Detail Page
 * Displays full information of a single log
 */

'use client';

import React, { useState } from 'react';
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
  const logId = Number(params.id);
  const [detailOpen, setDetailOpen] = useState(true);

  // Data query
  const { data: log, isLoading, isError, refetch } = useLogDetail(logId);

  // Handle sheet open change
  const handleDetailOpenChange = (open: boolean) => {
    setDetailOpen(open);
    if (!open) {
      // Navigate back to logs list if detail view is closed
      window.location.href = '/logs';
    }
  };

  if (isLoading) {
    return <LoadingSpinner />;
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
      <div className="flex items-center gap-4">
        <Link href="/logs">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Log Details</h1>
          <p className="mt-1 text-muted-foreground">
            Log ID: {log.id}
          </p>
        </div>
      </div>

      {/* Log Detail Content (Rendered as a Sheet) */}
      <LogDetail log={log} open={detailOpen} onOpenChange={handleDetailOpenChange} />
      
      {/* Fallback content if Sheet is closed (though navigation usually happens) */}
      {!detailOpen && (
        <div className="flex justify-center p-8">
          <Button onClick={() => setDetailOpen(true)}>Open Details</Button>
        </div>
      )}
    </div>
  );
}