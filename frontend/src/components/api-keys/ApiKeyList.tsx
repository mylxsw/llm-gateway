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
import { Pencil, Trash2, Copy, Check, Eye, EyeOff } from 'lucide-react';
import { ApiKey } from '@/types';
import { formatDateTime, getActiveStatus, copyToClipboard } from '@/lib/utils';

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
  // Store copy state and visibility state
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [visibleId, setVisibleId] = useState<number | null>(null);

  // Copy API Key
  const handleCopy = async (apiKey: ApiKey) => {
    const success = await copyToClipboard(apiKey.key_value);
    if (success) {
      setCopiedId(apiKey.id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  // Toggle visibility
  const toggleVisible = (id: number) => {
    setVisibleId(visibleId === id ? null : id);
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
          
          return (
            <TableRow key={apiKey.id}>
              <TableCell className="font-mono text-sm">
                {apiKey.id}
              </TableCell>
              <TableCell className="font-medium">{apiKey.key_name}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono">
                    {isVisible ? apiKey.key_value : apiKey.key_value.replace(/./g, '•')}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => toggleVisible(apiKey.id)}
                    title={isVisible ? 'Hide' : 'Show'}
                  >
                    {isVisible ? (
                      <EyeOff className="h-3.5 w-3.5" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => handleCopy(apiKey)}
                    title="Copy"
                  >
                    {isCopied ? (
                      <Check className="h-3.5 w-3.5 text-green-500" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
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
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(apiKey)}
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
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