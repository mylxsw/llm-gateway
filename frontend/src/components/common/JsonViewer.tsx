/**
 * JSON Viewer Component
 * Used to display formatted JSON data, supports collapse and copy.
 */

'use client';

import React, { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Copy, Check, ChevronDown, ChevronRight, WrapText } from 'lucide-react';
import { copyToClipboard, cn } from '@/lib/utils';

interface JsonViewerProps {
  /** JSON Data */
  data: unknown;
  /** Whether expanded by default */
  defaultExpanded?: boolean;
  /** Max height */
  maxHeight?: string;
  /** Custom class name */
  className?: string;
}

/**
 * JSON Viewer Component
 * Formats and displays JSON data
 */
export function JsonViewer({
  data,
  defaultExpanded = true,
  maxHeight = '400px',
  className,
}: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [wrapLines, setWrapLines] = useState(false);

  const normalizedData = useMemo(() => {
    if (typeof data !== 'string') return data;
    const trimmed = data.trim();
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))
    ) {
      try {
        return JSON.parse(trimmed);
      } catch {
        return data;
      }
    }
    return data;
  }, [data]);

  // Format JSON string
  const jsonString = (() => {
    try {
      return JSON.stringify(normalizedData, null, 2) ?? String(normalizedData);
    } catch {
      return String(normalizedData);
    }
  })();

  type TokenType = 'key' | 'string' | 'number' | 'boolean' | 'null' | 'plain';

  const tokens = useMemo(() => {
    const tokenRegex = /"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
    const parsedTokens: Array<{ text: string; type: TokenType }> = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = tokenRegex.exec(jsonString)) !== null) {
      if (match.index > lastIndex) {
        parsedTokens.push({
          text: jsonString.slice(lastIndex, match.index),
          type: 'plain',
        });
      }

      const value = match[0];
      let type: TokenType = 'plain';

      if (value.startsWith('"')) {
        const after = jsonString.slice(match.index + value.length);
        const isKey = /^\s*:/.test(after);
        type = isKey ? 'key' : 'string';
      } else if (value === 'true' || value === 'false') {
        type = 'boolean';
      } else if (value === 'null') {
        type = 'null';
      } else {
        type = 'number';
      }

      parsedTokens.push({ text: value, type });
      lastIndex = match.index + value.length;
    }

    if (lastIndex < jsonString.length) {
      parsedTokens.push({
        text: jsonString.slice(lastIndex),
        type: 'plain',
      });
    }

    return parsedTokens;
  }, [jsonString]);

  const tokenClassName = (type: TokenType) => {
    switch (type) {
      case 'key':
        return 'text-sky-600';
      case 'string':
        return 'text-emerald-600';
      case 'number':
        return 'text-amber-600';
      case 'boolean':
        return 'text-rose-600';
      case 'null':
        return 'text-teal-600';
      default:
        return 'text-foreground';
    }
  };

  // Copy to clipboard
  const handleCopy = async () => {
    const success = await copyToClipboard(jsonString);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={cn('relative rounded-md border bg-muted/50', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" suppressHydrationWarning />
          ) : (
            <ChevronRight className="h-4 w-4" suppressHydrationWarning />
          )}
          <span>{expanded ? 'Collapse' : 'Expand'}</span>
        </button>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setWrapLines((value) => !value)}
            className="h-7 gap-1 px-2"
          >
            <WrapText className="h-3.5 w-3.5" suppressHydrationWarning />
            <span>{wrapLines ? 'No wrap' : 'Wrap'}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="h-7 gap-1 px-2"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-green-500" suppressHydrationWarning />
                <span className="text-green-500">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" suppressHydrationWarning />
                <span>Copy</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* JSON Content */}
      {expanded && (
        <pre
          className={cn(
            'overflow-auto p-3 text-sm font-mono',
            wrapLines ? 'whitespace-pre-wrap break-words' : 'whitespace-pre'
          )}
          style={{ maxHeight }}
        >
          <code>
            {tokens.map((token, index) => (
              <span key={`${token.type}-${index}`} className={tokenClassName(token.type)}>
                {token.text}
              </span>
            ))}
          </code>
        </pre>
      )}
    </div>
  );
}
