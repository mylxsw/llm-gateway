'use client';

import { Activity, CheckCircle2, Gauge, XCircle } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { LogCostStatsResponse } from '@/types';
import { formatDuration, formatNumber } from '@/lib/utils';

interface HomeCallStatsProps {
  stats: LogCostStatsResponse;
}

function formatRate(rate: number) {
  return `${(Math.max(0, Math.min(1, rate)) * 100).toFixed(1)}%`;
}

export function HomeCallStats({ stats }: HomeCallStatsProps) {
  const t = useTranslations('home.dashboard');
  const { summary, model_call_stats: modelStats } = stats;
  const successRate = Math.max(0, Math.min(1, summary.success_rate));

  const metrics = [
    {
      label: t('totalCalls'),
      value: formatNumber(summary.request_count),
      icon: Activity,
      className: 'text-sky-600 dark:text-sky-400',
    },
    {
      label: t('successfulCalls'),
      value: formatNumber(summary.success_count),
      icon: CheckCircle2,
      className: 'text-emerald-600 dark:text-emerald-400',
    },
    {
      label: t('failedCalls'),
      value: formatNumber(summary.failure_count),
      icon: XCircle,
      className: 'text-rose-600 dark:text-rose-400',
    },
    {
      label: t('overallSuccessRate'),
      value: formatRate(successRate),
      icon: Gauge,
      className: 'text-violet-600 dark:text-violet-400',
      rate: successRate,
    },
  ];

  return (
    <section className="space-y-4" aria-labelledby="call-health-title">
      <div>
        <h2 id="call-health-title" className="text-base font-semibold">
          {t('title')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('description')}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div
              key={metric.label}
              className="relative overflow-hidden rounded-lg border bg-card px-4 py-3 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-medium text-muted-foreground">
                    {metric.label}
                  </div>
                  <div className="mt-2 font-mono text-2xl font-semibold tabular-nums">
                    {metric.value}
                  </div>
                </div>
                <Icon className={`h-5 w-5 ${metric.className}`} aria-hidden="true" />
              </div>
              {metric.rate !== undefined ? (
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-violet-500 transition-[width]"
                    style={{ width: `${metric.rate * 100}%` }}
                  />
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <Card className="shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{t('modelStatsTitle')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('latencyHint')}</p>
        </CardHeader>
        <CardContent>
          {modelStats.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {t('noData')}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('provider')}</TableHead>
                  <TableHead>{t('model')}</TableHead>
                  <TableHead className="text-right">{t('totalCalls')}</TableHead>
                  <TableHead className="text-right">{t('successfulCalls')}</TableHead>
                  <TableHead className="text-right">{t('failedCalls')}</TableHead>
                  <TableHead className="text-right">{t('successRate')}</TableHead>
                  <TableHead className="text-right">{t('averageLatency')}</TableHead>
                  <TableHead className="text-right">{t('maximumLatency')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {modelStats.map((item) => (
                  <TableRow key={`${item.provider_name}:${item.model_name}`}>
                    <TableCell className="font-medium">{item.provider_name}</TableCell>
                    <TableCell className="max-w-[260px] font-mono text-xs">
                      <span className="block truncate" title={item.model_name}>
                        {item.model_name}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatNumber(item.request_count)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-emerald-600 dark:text-emerald-400">
                      {formatNumber(item.success_count)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums text-rose-600 dark:text-rose-400">
                      {formatNumber(item.failure_count)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatRate(item.success_rate)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatDuration(item.avg_first_byte_time_ms)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatDuration(item.max_first_byte_time_ms)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
