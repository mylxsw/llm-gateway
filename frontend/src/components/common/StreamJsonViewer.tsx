/**
 * Stream JSON Viewer Component
 * Used to display stream responses (data: ...) in JSON view per line.
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import ReactJsonView from '@uiw/react-json-view';
import { darkTheme } from '@uiw/react-json-view/dark';
import { lightTheme } from '@uiw/react-json-view/light';
import { Button } from '@/components/ui/button';
import { Check, ChevronDown, ChevronRight, Copy, WrapText, Braces } from 'lucide-react';
import { cn, copyToClipboard } from '@/lib/utils';

interface StreamJsonViewerProps {
  /** Raw stream text */
  data: unknown;
  /** Max height */
  maxHeight?: string;
  /** Custom class name */
  className?: string;
}

type StreamLine = {
  index: number;
  raw: string;
  kind: 'json' | 'text' | 'done';
  value?: unknown;
  isDataLine: boolean;
};

const parseStreamLines = (raw: string): StreamLine[] => {
  const lines = raw.split(/\r?\n/).filter((line) => line.trim().length > 0);

  return lines.map((line, index) => {
    const match = line.match(/^\s*data:\s*(.*)$/);
    const isDataLine = Boolean(match);
    const payload = match ? match[1] : line;
    const trimmed = payload.trim();

    if (trimmed === '[DONE]') {
      return { index, raw: line, kind: 'done', isDataLine };
    }

    if (!trimmed) {
      return { index, raw: line, kind: 'text', isDataLine };
    }

    try {
      const parsed = JSON.parse(trimmed);
      return { index, raw: line, kind: 'json', value: parsed, isDataLine };
    } catch {
      return { index, raw: line, kind: 'text', isDataLine };
    }
  });
};

/**
 * Stream JSON Viewer Component
 */
export function StreamJsonViewer({ data, maxHeight = '400px', className }: StreamJsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [wrapLines, setWrapLines] = useState(false);
  const [useRawView, setUseRawView] = useState(false);
  const [isDark, setIsDark] = useState(false);

  const rawText = useMemo(() => {
    if (typeof data === 'string') return data;
    try {
      return JSON.stringify(data, null, 2) ?? String(data);
    } catch {
      return String(data);
    }
  }, [data]);

  const lines = useMemo(() => parseStreamLines(rawText), [rawText]);

  useEffect(() => {
    const updateTheme = () => {
      setIsDark(document.documentElement.classList.contains('dark'));
    };

    updateTheme();

    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

    return () => observer.disconnect();
  }, []);

  const handleCopy = async () => {
    const success = await copyToClipboard(rawText);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={cn('relative rounded-md border bg-muted/50', className)}>
      <div className="flex items-center justify-between border-b px-3 py-2">
        <button
          onClick={() => setExpanded((value) => !value)}
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
          {useRawView && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setWrapLines((value) => !value)}
              className="h-7 gap-1 px-2"
            >
              <WrapText className="h-3.5 w-3.5" suppressHydrationWarning />
              <span>{wrapLines ? 'No wrap' : 'Wrap'}</span>
            </Button>
          )}
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
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setUseRawView((value) => !value)}
            className="h-7 gap-1 px-2"
          >
            <Braces className="h-3.5 w-3.5" suppressHydrationWarning />
            <span>{useRawView ? 'JSON' : 'Raw'}</span>
          </Button>
        </div>
      </div>

      {expanded && (
        <>
          {useRawView ? (
            <pre
              className={cn(
                'overflow-auto p-3 text-sm font-mono',
                wrapLines ? 'whitespace-pre-wrap break-words' : 'whitespace-pre'
              )}
              style={{ maxHeight }}
            >
              <code>{rawText || ' '}</code>
            </pre>
          ) : (
            <div className="overflow-auto p-3 text-sm" style={{ maxHeight }}>
              <div className="space-y-3">
                {lines.length === 0 && (
                  <div className="text-xs text-muted-foreground">No stream content</div>
                )}
                {lines.map((line) => (
                  <div
                    key={`${line.kind}-${line.index}`}
                    className="rounded-md border bg-background/60 p-2"
                  >
                    <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="font-mono">Line {line.index + 1}</span>
                      {line.isDataLine && <span className="rounded bg-muted px-1">data</span>}
                    </div>
                    {line.kind === 'json' ? (
                      <ReactJsonView
                        value={line.value as Record<string, unknown> | unknown[]}
                        style={isDark ? darkTheme : lightTheme}
                      />
                    ) : (
                      <pre className="whitespace-pre-wrap break-words text-xs font-mono text-muted-foreground">
                        {line.kind === 'done' ? '[DONE]' : line.raw}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export const isStreamPayload = (value: unknown): boolean => {
  if (typeof value !== 'string') return false;
  return value.split(/\r?\n/).some((line) => /^\s*data:\s*/.test(line));
};
