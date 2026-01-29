/**
 * Model Match Dialog
 * Simulates provider matching for a given model.
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useMatchModelProviders } from '@/lib/hooks';
import { getProviderProtocolLabel, useProviderProtocolConfigs } from '@/lib/providerProtocols';
import { getApiErrorMessage } from '@/lib/api/error';
import { ModelMatchProvider } from '@/types';

interface ModelMatchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  requestedModel: string;
}

function parseHeadersInput(input: string): Record<string, string> {
  const trimmed = input.trim();
  if (!trimmed) return {};

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return Object.fromEntries(
        Object.entries(parsed).map(([key, value]) => [String(key), String(value ?? '')])
      );
    }
  } catch {
    // Fall through to line parsing.
  }

  const headers: Record<string, string> = {};
  const lines = trimmed.split('\n').map((line) => line.trim()).filter(Boolean);
  for (const line of lines) {
    const index = line.indexOf(':');
    if (index <= 0) {
      throw new Error('invalid_headers');
    }
    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim();
    if (!key) {
      throw new Error('invalid_headers');
    }
    headers[key] = value;
  }
  return headers;
}

function formatUsdCeil4(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  const num = Number(value);
  if (Number.isNaN(num)) return '-';
  return `$${num.toFixed(4)}`;
}

export function ModelMatchDialog({
  open,
  onOpenChange,
  requestedModel,
}: ModelMatchDialogProps) {
  const [inputTokens, setInputTokens] = useState('1000');
  const [headersInput, setHeadersInput] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [matchResults, setMatchResults] = useState<ModelMatchProvider[]>([]);
  const [matchError, setMatchError] = useState<string | null>(null);

  const matchMutation = useMatchModelProviders();
  const { configs: protocolConfigs } = useProviderProtocolConfigs();

  const handleMatch = async () => {
    const tokensValue = Number(inputTokens);
    if (!Number.isFinite(tokensValue) || tokensValue < 0) {
      setMatchError('Please enter a valid input token count.');
      return;
    }

    let headers: Record<string, string> = {};
    try {
      headers = parseHeadersInput(headersInput);
    } catch {
      setMatchError('Invalid headers format. Use JSON or key: value per line.');
      return;
    }

    setMatchError(null);
    try {
      const result = await matchMutation.mutateAsync({
        requestedModel,
        data: {
          input_tokens: tokensValue,
          headers,
          api_key: apiKey.trim() || undefined,
        },
      });
      setMatchResults(result);
    } catch (error) {
      setMatchResults([]);
      setMatchError(getApiErrorMessage(error, 'Match failed'));
    }
  };

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      setMatchError(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[720px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Test Provider Matching</DialogTitle>
          <DialogDescription>
            Enter test inputs and run matching to preview the provider order.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="match-input-tokens">Input Tokens</Label>
            <Input
              id="match-input-tokens"
              type="number"
              min={0}
              step={1}
              value={inputTokens}
              onChange={(event) => setInputTokens(event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="match-headers">Headers</Label>
            <Textarea
              id="match-headers"
              rows={4}
              placeholder={`{\n  \"x-priority\": \"high\"\n}`}
              value={headersInput}
              onChange={(event) => setHeadersInput(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Use JSON or key: value per line.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="match-api-key">API Key</Label>
            <Input
              id="match-api-key"
              type="password"
              autoComplete="off"
              placeholder="lgw-xxxxxxxxxxxx"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </div>
        </div>

        {matchError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {matchError}
          </div>
        ) : null}

        <div className="space-y-2">
          <p className="text-sm font-medium">Results</p>
          {matchResults.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Order</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Target Model</TableHead>
                  <TableHead>Protocol</TableHead>
                  <TableHead>Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {matchResults.map((item, index) => (
                  <TableRow key={`${item.provider_id}-${item.target_model_name}`}>
                    <TableCell className="font-mono">{index + 1}</TableCell>
                    <TableCell>{item.provider_name}</TableCell>
                    <TableCell>
                      <code className="text-sm">{item.target_model_name}</code>
                    </TableCell>
                    <TableCell className="text-sm">
                      {getProviderProtocolLabel(item.protocol, protocolConfigs)}
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="font-mono">
                        {formatUsdCeil4(item.estimated_cost)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No matches yet.</p>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
          >
            Close
          </Button>
          <Button
            type="button"
            onClick={handleMatch}
            disabled={matchMutation.isPending}
          >
            Test
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
