/**
 * API Key List Component
 * Displays API Key data table
 */

'use client';

import React, { useState } from 'react';
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
import { Pencil, Trash2, Copy, Check, Eye, EyeOff, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { ApiKey } from '@/types';
import { formatDateTime, getActiveStatus } from '@/lib/utils';
import { getRawKeyValue } from '@/lib/api/api-keys';

interface ApiKeyListProps {
  /** API Key list data */
  apiKeys: ApiKey[];
  /** Edit callback */
  onEdit: (apiKey: ApiKey) => void;
  /** Delete callback */
  onDelete: (apiKey: ApiKey) => void;
}

/**
 * API Key List Component
 */
export function ApiKeyList({
  apiKeys,
  onEdit,
  onDelete,
}: ApiKeyListProps) {
  // Store copy state, visibility state, loading state, and raw key values
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [visibleId, setVisibleId] = useState<number | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [rawKeyValues, setRawKeyValues] = useState<Record<number, string>>({});

  // Fetch raw key value from backend
  const fetchRawKeyValue = async (id: number): Promise<string | null> => {
    if (rawKeyValues[id]) {
      return rawKeyValues[id];
    }
    setLoadingId(id);
    try {
      const keyValue = await getRawKeyValue(id);
      setRawKeyValues(prev => ({ ...prev, [id]: keyValue }));
      return keyValue;
    } catch {
      toast.error('Failed to fetch API Key');
      return null;
    } finally {
      setLoadingId(null);
    }
  };

  // Copy API Key
  const handleCopy = async (apiKey: ApiKey) => {
    const keyValue = await fetchRawKeyValue(apiKey.id);
    if (keyValue) {
      try {
        await navigator.clipboard.writeText(keyValue);
        setCopiedId(apiKey.id);
        toast.success('API Key copied to clipboard');
        setTimeout(() => setCopiedId(null), 2000);
      } catch {
        toast.error('Failed to copy to clipboard');
      }
    }
  };

  // Toggle visibility
  const toggleVisible = async (id: number) => {
    if (visibleId === id) {
      setVisibleId(null);
    } else {
      await fetchRawKeyValue(id);
      setVisibleId(id);
    }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[60px]">ID</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>API Key</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created At</TableHead>
          <TableHead>Last Used</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {apiKeys.map((apiKey) => {
          const status = getActiveStatus(apiKey.is_active);
          const isVisible = visibleId === apiKey.id;
          const isCopied = copiedId === apiKey.id;
          const isLoading = loadingId === apiKey.id;
          const rawKeyValue = rawKeyValues[apiKey.id];

          return (
            <TableRow key={apiKey.id}>
              <TableCell className="font-mono text-sm">
                {apiKey.id}
              </TableCell>
              <TableCell className="font-medium">{apiKey.key_name}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono">
                    {isVisible && rawKeyValue ? rawKeyValue : apiKey.key_value}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => toggleVisible(apiKey.id)}
                    title={isVisible ? 'Hide' : 'Show'}
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" suppressHydrationWarning />
                    ) : isVisible ? (
                      <EyeOff className="h-3.5 w-3.5" suppressHydrationWarning />
                    ) : (
                      <Eye className="h-3.5 w-3.5" suppressHydrationWarning />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => handleCopy(apiKey)}
                    title="Copy"
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" suppressHydrationWarning />
                    ) : isCopied ? (
                      <Check className="h-3.5 w-3.5 text-green-500" suppressHydrationWarning />
                    ) : (
                      <Copy className="h-3.5 w-3.5" suppressHydrationWarning />
                    )}
                  </Button>
                </div>
              </TableCell>
              <TableCell>
                <Badge className={status.className}>{status.text}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(apiKey.created_at)}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(apiKey.last_used_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(apiKey)}
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(apiKey)}
                    title="Delete"
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
