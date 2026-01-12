/**
 * JSON Viewer Component
 * Used to display formatted JSON data, supports collapse and copy.
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';
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

  const normalizedData = React.useMemo(() => {
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
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          <span>{expanded ? 'Collapse' : 'Expand'}</span>
        </button>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="h-7 gap-1 px-2"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-green-500" />
              <span className="text-green-500">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>Copy</span>
            </>
          )}
        </Button>
      </div>

      {/* JSON Content */}
      {expanded && (
        <pre
          className="overflow-auto p-3 text-sm"
          style={{ maxHeight }}
        >
          <code className="text-foreground">{jsonString}</code>
        </pre>
      )}
    </div>
  );
}