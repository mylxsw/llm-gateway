/**
 * Log Playground Page
 */

'use client';

import React, { Suspense, useMemo } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ErrorState, LoadingSpinner } from '@/components/common';
import { useLogDetail } from '@/lib/hooks';
import { normalizeReturnTo } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { LogPlayground } from '@/components/playground/LogPlayground';

export default function PlaygroundPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <PlaygroundContent />
    </Suspense>
  );
}

function PlaygroundContent() {
  const t = useTranslations('logs');
  const searchParams = useSearchParams();
  const logId = Number(searchParams.get('id'));
  const returnTo = useMemo(
    () => normalizeReturnTo(searchParams.get('returnTo'), '/logs'),
    [searchParams]
  );

  const { data: log, isLoading, isError, refetch } = useLogDetail(logId);

  if (!Number.isFinite(logId)) {
    return (
      <ErrorState
        message={t('detail.invalidLogId')}
        onRetry={() => {
          window.location.href = returnTo;
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
          <Link href={returnTo}>
            <Button variant="ghost" size="icon" aria-label={t('detail.backToLogs')}>
              <ArrowLeft className="h-4 w-4" suppressHydrationWarning />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{t('playground.title')}</h1>
            <p className="mt-1 text-muted-foreground">
              {t('playground.subtitle', { id: log.id })}
            </p>
          </div>
        </div>
      </div>

      <LogPlayground log={log} />
    </div>
  );
}
