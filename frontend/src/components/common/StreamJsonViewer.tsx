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

type TokenType = 'key' | 'string' | 'number' | 'boolean' | 'null' | 'plain';

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

const summarizeJsonValue = (value: unknown): string => {
  if (value === null || value === undefined) return String(value);
  if (Array.isArray(value)) return `Array(${value.length})`;
  if (typeof value === 'object') {
    const blockedKeys = new Set(['model', 'id', 'created', 'object']);
    const isIgnoredValue = (val: unknown) => val === null || val === 0 || val === '';
    const entries = Object.entries(value as Record<string, unknown>).filter(
      ([key, val]) => !blockedKeys.has(key) && !isIgnoredValue(val)
    );
    if (entries.length === 0) return '{}';

    const maxParts = 12;
    const maxDepth = 4;
    const parts: string[] = [];
    const seen = new WeakSet<object>();

    const pushPart = (text: string) => {
      if (parts.length < maxParts) parts.push(text);
    };

    const formatValue = (val: unknown) => {
      if (val === null) return 'null';
      if (Array.isArray(val)) return `Array(${val.length})`;
      if (typeof val === 'object') return '{…}';
      if (typeof val === 'string') {
        const snippet = val.length > 32 ? `${val.slice(0, 32)}…` : val;
        return `"${snippet}"`;
      }
      return String(val);
    };

    const walk = (val: unknown, path: string, depth: number) => {
      if (parts.length >= maxParts) return;
      if (val === undefined || isIgnoredValue(val)) return;
      if (depth > maxDepth) {
        pushPart(`${path}: {…}`);
        return;
      }

      if (Array.isArray(val)) {
        if (val.length === 0) {
          pushPart(`${path}: []`);
          return;
        }
        val.forEach((item, index) => {
          if (parts.length >= maxParts) return;
          walk(item, `${path}[${index}]`, depth + 1);
        });
        return;
      }

      if (typeof val === 'object') {
        if (seen.has(val as object)) {
          pushPart(`${path}: {…}`);
          return;
        }
        seen.add(val as object);
        const objectEntries = Object.entries(val as Record<string, unknown>).filter(
          ([key, child]) => !blockedKeys.has(key) && !isIgnoredValue(child)
        );
        if (objectEntries.length === 0) {
          pushPart(`${path}: {}`);
          return;
        }
        objectEntries.forEach(([key, child]) => {
          if (parts.length >= maxParts) return;
          walk(child, `${path}.${key}`, depth + 1);
        });
        return;
      }

      pushPart(`${path}: ${formatValue(val)}`);
    };

    entries.forEach(([key, val]) => {
      if (parts.length >= maxParts) return;
      if (Array.isArray(val)) {
        walk(val, key, 1);
        return;
      }
      if (typeof val === 'object') {
        walk(val, key, 1);
        return;
      }
      pushPart(`${key}: ${formatValue(val)}`);
    });

    const suffix = parts.length >= maxParts ? ' …' : '';
    return parts.join(', ') + suffix;
  }
  if (typeof value === 'string') {
    return value.length > 64 ? `${value.slice(0, 64)}…` : value;
  }
  return String(value);
};

const tokenizeJsonString = (jsonString: string): Array<{ text: string; type: TokenType }> => {
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
};

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

/**
 * Stream JSON Viewer Component
 */
export function StreamJsonViewer({ data, maxHeight = '400px', className }: StreamJsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [wrapLines, setWrapLines] = useState(false);
  const [useRawView, setUseRawView] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const [expandedLines, setExpandedLines] = useState<Record<number, boolean>>({});

  const rawText = useMemo(() => {
    if (typeof data === 'string') return data;
    try {
      return JSON.stringify(data, null, 2) ?? String(data);
    } catch {
      return String(data);
    }
  }, [data]);

  const lines = useMemo(() => parseStreamLines(rawText), [rawText]);
  const rawTokens = useMemo(() => tokenizeJsonString(rawText), [rawText]);

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
              <code>
                {rawTokens.length > 0
                  ? rawTokens.map((token, index) => (
                      <span
                        key={`${token.type}-${index}`}
                        className={tokenClassName(token.type)}
                      >
                        {token.text}
                      </span>
                    ))
                  : rawText || ' '}
              </code>
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
                    {line.kind === 'json' ? (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedLines((prev) => ({
                              ...prev,
                              [line.index]: !prev[line.index],
                            }))
                          }
                          className="mb-1 flex w-full items-center gap-2 text-left text-xs text-muted-foreground hover:text-foreground"
                        >
                          {expandedLines[line.index] ? (
                            <ChevronDown className="h-3.5 w-3.5" suppressHydrationWarning />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5" suppressHydrationWarning />
                          )}
                          <span className="font-mono">Line {line.index + 1}</span>
                          {line.isDataLine && <span className="rounded bg-muted px-1">data</span>}
                          {!expandedLines[line.index] && (
                            <span className="truncate text-xs text-foreground/80">
                              {summarizeJsonValue(line.value)}
                            </span>
                          )}
                        </button>
                        {expandedLines[line.index] && (
                          <ReactJsonView
                            value={line.value as Record<string, unknown> | unknown[]}
                            style={isDark ? darkTheme : lightTheme}
                          />
                        )}
                      </>
                    ) : (
                      <>
                        <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-mono">Line {line.index + 1}</span>
                          {line.isDataLine && <span className="rounded bg-muted px-1">data</span>}
                        </div>
                        <pre className="whitespace-pre-wrap break-words text-xs font-mono text-muted-foreground">
                          {line.kind === 'done' ? '[DONE]' : line.raw}
                        </pre>
                      </>
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
