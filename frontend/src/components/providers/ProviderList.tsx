/**
 * Provider List Component
 * Displays provider data table with action buttons
 */

'use client';

import React from 'react';
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
import { Sparkles, Pencil, Trash2 } from 'lucide-react';
import { Provider } from '@/types';
import { formatDateTime, truncate, getActiveStatus } from '@/lib/utils';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';

interface ProviderListProps {
  /** Provider list data */
  providers: Provider[];
  /** Used supplier model names grouped by provider id */
  usedModelNamesByProvider: Record<number, string[]>;
  /** Edit callback */
  onEdit: (provider: Provider) => void;
  /** Fetch models callback */
  onFetchModels: (provider: Provider) => void;
  /** Open used models dialog callback */
  onOpenUsedModels: (provider: Provider) => void;
  /** Delete callback */
  onDelete: (provider: Provider) => void;
}

/**
 * Provider List Component
 */
export function ProviderList({
  providers,
  usedModelNamesByProvider,
  onEdit,
  onFetchModels,
  onOpenUsedModels,
  onDelete,
}: ProviderListProps) {
  const t = useTranslations('providers');
  const { configs: protocolConfigs } = useProviderProtocolConfigs();
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[60px]">{t('list.columns.id')}</TableHead>
          <TableHead>{t('list.columns.name')}</TableHead>
          <TableHead>{t('list.columns.baseUrl')}</TableHead>
          <TableHead>{t('list.columns.protocol')}</TableHead>
          <TableHead>{t('list.columns.usedModels')}</TableHead>
          <TableHead>{t('list.columns.status')}</TableHead>
          <TableHead>{t('list.columns.updatedAt')}</TableHead>
          <TableHead className="text-right">{t('list.columns.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {providers.map((provider) => {
          const status = getActiveStatus(provider.is_active);
          const statusText = provider.is_active
            ? t('filters.status.active')
            : t('filters.status.inactive');
          const usedModelCount = usedModelNamesByProvider[provider.id]?.length ?? 0;
          return (
            <TableRow key={provider.id}>
              <TableCell className="font-mono text-sm">
                {provider.id}
              </TableCell>
              <TableCell className="font-medium">{provider.name}</TableCell>
              <TableCell className="max-w-[200px]">
                <span title={provider.base_url}>
                  {truncate(provider.base_url, 30)}
                </span>
              </TableCell>
              <TableCell>
                <Badge variant="outline">
                  {getProviderProtocolLabel(provider.protocol, protocolConfigs)}
                </Badge>
              </TableCell>
              <TableCell>
                {usedModelCount > 0 ? (
                  <Button
                    variant="ghost"
                    className="h-auto p-0"
                    onClick={() => onOpenUsedModels(provider)}
                    title={t('list.actions.viewModelList')}
                  >
                    <Badge
                      variant="secondary"
                      className="cursor-pointer hover:bg-secondary/80"
                    >
                      {usedModelCount}
                    </Badge>
                  </Button>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell>
                <Badge className={status.className}>{statusText}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(provider.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onFetchModels(provider)}
                    title={t('list.actions.fetchModels')}
                  >
                    <Sparkles className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(provider)}
                    title={t('list.actions.edit')}
                  >
                    <Pencil className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(provider)}
                    title={t('list.actions.delete')}
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
