/**
 * Model Mapping List Component
 * Displays model mapping data table
 */

'use client';

import React from 'react';
import Link from 'next/link';
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
import { Eye, Pencil, Trash2 } from 'lucide-react';
import { ModelMapping } from '@/types';
import { formatDateTime, getActiveStatus } from '@/lib/utils';

interface ModelListProps {
  /** Model mapping list data */
  models: ModelMapping[];
  /** Edit callback */
  onEdit: (model: ModelMapping) => void;
  /** Delete callback */
  onDelete: (model: ModelMapping) => void;
}

/**
 * Model Mapping List Component
 */
export function ModelList({
  models,
  onEdit,
  onDelete,
}: ModelListProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Requested Model Name</TableHead>
          <TableHead>Strategy</TableHead>
          <TableHead>Provider Count</TableHead>
          <TableHead>Matching Rules</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Updated At</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map((model) => {
          const status = getActiveStatus(model.is_active);
          return (
            <TableRow key={model.requested_model}>
              <TableCell className="font-medium font-mono">
                {model.requested_model}
              </TableCell>
              <TableCell>
                <Badge variant="outline">{model.strategy}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{model.provider_count || 0}</Badge>
              </TableCell>
              <TableCell>
                {model.matching_rules ? (
                  <Badge variant="outline" className="text-blue-600">
                    Configured
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </TableCell>
              <TableCell>
                <Badge className={status.className}>{status.text}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatDateTime(model.updated_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Link href={`/models/${encodeURIComponent(model.requested_model)}`}>
                    <Button variant="ghost" size="icon" title="View Details">
                      <Eye className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(model)}
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(model)}
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