/**
 * Model Mapping List Component
 * Displays model mapping data table
 */

'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
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
import { Pencil, Play, Server, Trash2 } from 'lucide-react';
import { ModelMapping, ModelStats, ModelType } from '@/types';
import { getActiveStatus, formatDuration } from '@/lib/utils';

interface ModelListProps {
  /** Model mapping list data */
  models: ModelMapping[];
  statsByModel?: Record<string, ModelStats>;
  /** Edit callback */
  onEdit: (model: ModelMapping) => void;
  /** Delete callback */
  onDelete: (model: ModelMapping) => void;
  /** Test callback */
  onTest: (model: ModelMapping) => void;
  /** Return URL for detail navigation */
  returnTo?: string;
}

/**
 * Model Mapping List Component
 */
export function ModelList({
  models,
  statsByModel,
  onEdit,
  onDelete,
  onTest,
  returnTo,
}: ModelListProps) {
  const t = useTranslations('models');
  const tCommon = useTranslations('common');
  const router = useRouter();

  const getStrategyLabel = (strategy: ModelMapping['strategy']) => {
    switch (strategy) {
      case 'cost_first':
        return t('list.strategy.costFirst');
      case 'priority':
        return t('list.strategy.priority');
      case 'round_robin':
      default:
        return t('list.strategy.roundRobin');
    }
  };

  const getModelTypeLabel = (type?: ModelType | null) => {
    switch (type) {
      case 'speech':
        return t('filters.speech');
      case 'transcription':
        return t('filters.transcription');
      case 'embedding':
        return t('filters.embedding');
      case 'images':
        return t('filters.images');
      case 'chat':
      default:
        return t('filters.chat');
    }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('list.columns.requestedModel')}</TableHead>
          <TableHead>{t('list.columns.type')}</TableHead>
          <TableHead>{t('list.columns.strategy')}</TableHead>
          <TableHead>{t('list.columns.providerCount')}</TableHead>
          <TableHead>
            <div className="flex flex-col">
              <span>{t('list.columns.avgResponse')}</span>
              <span className="text-xs text-muted-foreground">
                {t('list.columns.avgFirstToken')}
              </span>
            </div>
          </TableHead>
          <TableHead>{t('list.columns.status')}</TableHead>
          <TableHead className="text-right">{t('list.columns.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map((model) => {
          const stats = statsByModel?.[model.requested_model];
          const providerCount = model.provider_count ?? model.providers?.length ?? 0;
          const activeProviderCount =
            model.active_provider_count ??
            model.providers?.filter((provider) => provider.is_active).length ??
            0;

          // Determine status display
          const isPendingConfig = model.is_active && activeProviderCount === 0;
          const statusDisplay = isPendingConfig
            ? {
                text: t('filters.pendingConfig'),
                className: 'border-transparent bg-amber-500/15 text-amber-700 dark:text-amber-300 cursor-pointer hover:bg-amber-500/25',
              }
            : {
                ...getActiveStatus(model.is_active),
                text: model.is_active ? t('filters.active') : t('filters.inactive'),
              };

          const handleStatusClick = () => {
            if (isPendingConfig) {
              router.push(
                `/models/detail?model=${encodeURIComponent(model.requested_model)}${
                  returnTo ? `&returnTo=${encodeURIComponent(returnTo)}` : ''
                }`
              );
            }
          };

          return (
            <TableRow key={model.requested_model}>
              <TableCell className="font-medium font-mono">
                {model.requested_model}
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{getModelTypeLabel(model.model_type)}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant="outline">
                  {getStrategyLabel(model.strategy)}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge
                  variant="secondary"
                  title={t('list.columns.providerCountHint')}
                >
                  {activeProviderCount}/{providerCount}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                <div className="flex flex-col gap-1">
                  <span>{formatDuration(stats?.avg_response_time_ms ?? null)}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatDuration(stats?.avg_first_byte_time_ms ?? null)}
                  </span>
                </div>
              </TableCell>
              <TableCell>
                <Badge
                  className={statusDisplay.className}
                  onClick={handleStatusClick}
                >
                  {statusDisplay.text}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Link
                    href={`/models/detail?model=${encodeURIComponent(model.requested_model)}${
                      returnTo ? `&returnTo=${encodeURIComponent(returnTo)}` : ''
                    }`}
                  >
                    <Button variant="ghost" size="icon" title={t('list.viewDetails')}>
                      <Server className="h-4 w-4" suppressHydrationWarning />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onTest(model)}
                    title={t('list.testModel')}
                  >
                    <Play className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(model)}
                    title={tCommon('edit')}
                  >
                    <Pencil className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(model)}
                    title={tCommon('delete')}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" suppressHydrationWarning />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
