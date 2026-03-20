/**
 * JSON Viewer Component
 * Used to display formatted JSON data, supports collapse and copy.
 */

"use client";

import React, { useEffect, useMemo, useState } from "react";
import ReactJsonView from "@uiw/react-json-view";
import { darkTheme } from "@uiw/react-json-view/dark";
import { lightTheme } from "@uiw/react-json-view/light";
import { Button } from "@/components/ui/button";
import {
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  WrapText,
  Braces,
} from "lucide-react";
import { copyToClipboard, cn } from "@/lib/utils";

interface JsonViewerProps {
  /** JSON Data */
  data: unknown;
  /** Whether expanded by default */
  defaultExpanded?: boolean;
  /** Max height */
  maxHeight?: string;
  /** Custom class name */
  className?: string;
  /** Extra action buttons rendered at the start of the toolbar right section */
  extraActions?: React.ReactNode;
  /** Controlled wrap state */
  wrapLines?: boolean;
  /** Controlled wrap change callback */
  onWrapLinesChange?: (value: boolean) => void;
  /** Whether to show the built-in wrap toggle */
  showWrapToggle?: boolean;
}

/**
 * JSON Viewer Component
 * Formats and displays JSON data
 */
export function JsonViewer({
  data,
  defaultExpanded = true,
  maxHeight = "400px",
  className,
  extraActions,
  wrapLines: controlledWrapLines,
  onWrapLinesChange,
  showWrapToggle = true,
}: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [internalWrapLines, setInternalWrapLines] = useState(false);
  const [useRawView, setUseRawView] = useState(false);
  const [isDark, setIsDark] = useState(false);
  const wrapLines = controlledWrapLines ?? internalWrapLines;

  const parsedJson = useMemo(() => {
    if (typeof data !== "string") {
      const isJsonValue =
        data === null || ["object", "number", "boolean"].includes(typeof data);
      return { isValid: isJsonValue, value: data };
    }
    const trimmed = data.trim();
    if (!trimmed) return { isValid: false, value: data };
    try {
      return { isValid: true, value: JSON.parse(trimmed) };
    } catch {
      return { isValid: false, value: data };
    }
  }, [data]);

  const isValidJson =
    parsedJson.isValid &&
    typeof parsedJson.value === "object" &&
    parsedJson.value !== null;
  const jsonValue = parsedJson.value;
  const showJsonView = isValidJson && !useRawView;

  useEffect(() => {
    const updateTheme = () => {
      setIsDark(document.documentElement.classList.contains("dark"));
    };

    updateTheme();

    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  // Format JSON string for copy fallback
  const jsonString = (() => {
    if (isValidJson) {
      try {
        return JSON.stringify(jsonValue, null, 2) ?? String(jsonValue);
      } catch {
        return String(jsonValue);
      }
    }
    if (typeof jsonValue === "string") {
      return jsonValue;
    }
    try {
      return JSON.stringify(jsonValue, null, 2) ?? String(jsonValue);
    } catch {
      return String(jsonValue);
    }
  })();

  type TokenType = "key" | "string" | "number" | "boolean" | "null" | "plain";

  const tokens = useMemo(() => {
    if (showJsonView) return [];
    const tokenRegex =
      /"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
    const parsedTokens: Array<{ text: string; type: TokenType }> = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = tokenRegex.exec(jsonString)) !== null) {
      if (match.index > lastIndex) {
        parsedTokens.push({
          text: jsonString.slice(lastIndex, match.index),
          type: "plain",
        });
      }

      const value = match[0];
      let type: TokenType = "plain";

      if (value.startsWith('"')) {
        const after = jsonString.slice(match.index + value.length);
        const isKey = /^\s*:/.test(after);
        type = isKey ? "key" : "string";
      } else if (value === "true" || value === "false") {
        type = "boolean";
      } else if (value === "null") {
        type = "null";
      } else {
        type = "number";
      }

      parsedTokens.push({ text: value, type });
      lastIndex = match.index + value.length;
    }

    if (lastIndex < jsonString.length) {
      parsedTokens.push({
        text: jsonString.slice(lastIndex),
        type: "plain",
      });
    }

    return parsedTokens;
  }, [showJsonView, jsonString]);

  const tokenClassName = (type: TokenType) => {
    switch (type) {
      case "key":
        return "text-sky-600";
      case "string":
        return "text-emerald-600";
      case "number":
        return "text-amber-600";
      case "boolean":
        return "text-rose-600";
      case "null":
        return "text-teal-600";
      default:
        return "text-foreground";
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

  const handleWrapToggle = () => {
    const nextValue = !wrapLines;
    if (onWrapLinesChange) {
      onWrapLinesChange(nextValue);
      return;
    }
    setInternalWrapLines(nextValue);
  };

  return (
    <div className={cn("relative min-w-0 max-w-full rounded-md border bg-muted/50", className)}>
      {/* Toolbar */}
      <div className="flex min-w-0 items-center justify-between border-b px-3 py-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" suppressHydrationWarning />
          ) : (
            <ChevronRight className="h-4 w-4" suppressHydrationWarning />
          )}
          <span>{expanded ? "Collapse" : "Expand"}</span>
        </button>
        <div className="flex min-w-0 items-center gap-2">
          {extraActions}
          {showWrapToggle && !showJsonView && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleWrapToggle}
              className="h-7 gap-1 px-2"
            >
              <WrapText className="h-3.5 w-3.5" suppressHydrationWarning />
              <span>{wrapLines ? "No wrap" : "Wrap"}</span>
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
                <Check
                  className="h-3.5 w-3.5 text-green-500"
                  suppressHydrationWarning
                />
                <span className="text-green-500">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" suppressHydrationWarning />
                <span>Copy</span>
              </>
            )}
          </Button>
          {isValidJson && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setUseRawView((value) => !value)}
              className="h-7 gap-1 px-2"
            >
              <Braces className="h-3.5 w-3.5" suppressHydrationWarning />
              <span>{useRawView ? "JSON" : "Raw"}</span>
            </Button>
          )}
        </div>
      </div>

      {/* JSON Content */}
      {expanded && (
        <>
          {showJsonView ? (
            <div
              className="min-w-0 max-w-full overflow-auto p-3 text-sm"
              style={{ maxHeight }}
            >
              <ReactJsonView
                value={jsonValue as Record<string, unknown> | unknown[]}
                style={isDark ? darkTheme : lightTheme}
              />
            </div>
          ) : (
            <pre
              className={cn(
                "max-w-full overflow-x-auto overflow-y-auto p-3 text-sm font-mono",
                wrapLines
                  ? "whitespace-pre-wrap break-words"
                  : "whitespace-pre",
              )}
              style={{ maxHeight }}
            >
              <code className={cn("block max-w-full", wrapLines ? "min-w-0" : "min-w-max")}>
                {tokens.map((token, index) => (
                  <span
                    key={`${token.type}-${index}`}
                    className={tokenClassName(token.type)}
                  >
                    {token.text}
                  </span>
                ))}
              </code>
            </pre>
          )}
        </>
      )}
    </div>
  );
}
