/**
 * JSON 查看器组件
 * 用于格式化显示 JSON 数据，支持折叠和复制
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';
import { copyToClipboard, cn } from '@/lib/utils';

interface JsonViewerProps {
  /** JSON 数据 */
  data: unknown;
  /** 是否默认展开 */
  defaultExpanded?: boolean;
  /** 最大高度 */
  maxHeight?: string;
  /** 自定义类名 */
  className?: string;
}

/**
 * JSON 查看器组件
 * 格式化显示 JSON 数据
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

  // 格式化 JSON 字符串
  const jsonString = (() => {
    try {
      return JSON.stringify(normalizedData, null, 2) ?? String(normalizedData);
    } catch {
      return String(normalizedData);
    }
  })();

  // 复制到剪贴板
  const handleCopy = async () => {
    const success = await copyToClipboard(jsonString);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={cn('relative rounded-md border bg-muted/50', className)}>
      {/* 工具栏 */}
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
          <span>{expanded ? '收起' : '展开'}</span>
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
              <span className="text-green-500">已复制</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>复制</span>
            </>
          )}
        </Button>
      </div>

      {/* JSON 内容 */}
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
