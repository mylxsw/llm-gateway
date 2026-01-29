/**
 * Model Mapping List Component
 * Displays model mapping data table
 */

'use client';

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
import { Pencil, Play, Server, Trash2 } from 'lucide-react';
import { ModelMapping, ModelStats } from '@/types';
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
}: ModelListProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Requested Model Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Strategy</TableHead>
          <TableHead>Provider Count</TableHead>
          <TableHead>
            <div className="flex flex-col">
              <span>Avg Response (7d)</span>
              <span className="text-xs text-muted-foreground">Avg First Token (7d)</span>
            </div>
          </TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map((model) => {
          const status = getActiveStatus(model.is_active);
          const stats = statsByModel?.[model.requested_model];
          return (
            <TableRow key={model.requested_model}>
              <TableCell className="font-medium font-mono">
                {model.requested_model}
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{model.model_type ?? 'chat'}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant="outline">
                  {model.strategy === 'cost_first'
                    ? 'Cost First'
                    : model.strategy === 'priority'
                      ? 'Priority'
                      : 'Round Robin'}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge variant="secondary">{model.provider_count || 0}</Badge>
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
                <Badge className={status.className}>{status.text}</Badge>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Link
                    href={`/models/detail?model=${encodeURIComponent(model.requested_model)}`}
                  >
                    <Button variant="ghost" size="icon" title="View Details">
                      <Server className="h-4 w-4" suppressHydrationWarning />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onTest(model)}
                    title="Test Model"
                  >
                    <Play className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(model)}
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" suppressHydrationWarning />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(model)}
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
