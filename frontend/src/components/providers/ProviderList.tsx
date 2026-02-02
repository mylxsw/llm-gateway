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
  /** Edit callback */
  onEdit: (provider: Provider) => void;
  /** Fetch models callback */
  onFetchModels: (provider: Provider) => void;
  /** Delete callback */
  onDelete: (provider: Provider) => void;
}

/**
 * Provider List Component
 */
export function ProviderList({
  providers,
  onEdit,
  onFetchModels,
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
          <TableHead>{t('list.columns.status')}</TableHead>
          <TableHead>{t('list.columns.updatedAt')}</TableHead>
          <TableHead className="text-right">{t('list.columns.actions')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {providers.map((provider) => {
          const status = getActiveStatus(provider.is_active);
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
                <Badge className={status.className}>{status.text}</Badge>
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
