/**
 * Log Detail Page
 * Displays full information of a single log
 */

'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { LogDetail } from '@/components/logs';
import { LoadingSpinner, ErrorState } from '@/components/common';
import { useLogDetail } from '@/lib/hooks';
import { useTranslations } from 'next-intl';

export default function LogDetailPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <LogDetailContent />
    </Suspense>
  );
}

function LogDetailContent() {
  const t = useTranslations('logs');
  const searchParams = useSearchParams();
  const logId = Number(searchParams.get('id'));

  const { data: log, isLoading, isError, refetch } = useLogDetail(logId);

  if (!Number.isFinite(logId)) {
    return (
      <ErrorState
        message={t('detail.invalidLogId')}
        onRetry={() => {
          window.location.href = '/logs';
        }}
      />
    );
  }

  if (isLoading) return <LoadingSpinner />;

  if (isError || !log) {
    return (
      <ErrorState
        message={t('detail.loadFailed')}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-4">
          <Link href="/logs">
            <Button variant="ghost" size="icon" aria-label={t('detail.backToLogs')}>
              <ArrowLeft className="h-4 w-4" suppressHydrationWarning />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{t('detail.title')}</h1>
            <p className="mt-1 text-muted-foreground">{t('detail.logId', { id: log.id })}</p>
          </div>
        </div>
      </div>

      <LogDetail log={log} />
    </div>
  );
}
