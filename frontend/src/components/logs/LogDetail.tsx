/**
 * Log Detail Component
 * Displays detailed information of a request log, including request/response body, headers, etc.
 */

"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertCircle,
  ArrowRight,
  Bug,
  Check,
  Clock,
  Columns,
  Copy,
  Loader2,
  Play,
  RotateCcw,
  Rows,
  Server,
  Shield,
  Terminal,
  WrapText,
  Waves,
} from "lucide-react";
import { RequestLogDetail } from "@/types";
import {
  copyToClipboard,
  formatDateTime,
  formatDuration,
  formatUsd,
} from "@/lib/utils";
import { ConfirmDialog, JsonViewer } from "@/components/common";
import {
  StreamJsonViewer,
  isStreamPayload,
} from "@/components/common/StreamJsonViewer";
import { useTranslations } from "next-intl";
import { getStoredAdminToken } from "@/lib/api/client";

interface LogDetailProps {
  /** Log data */
  log: RequestLogDetail | null;
}

interface DebugSection {
  title: string;
  language: "json" | "text";
  content: unknown;
}

const RETRY_TIMEOUT_MS = 5 * 60 * 1000;

const MAX_DEBUG_FIELD_LENGTH = 200;

function truncateDebugValue(value: unknown): unknown {
  if (typeof value === "string") {
    if (value.length <= MAX_DEBUG_FIELD_LENGTH) return value;
    return `${value.slice(0, MAX_DEBUG_FIELD_LENGTH)}... [truncated ${
      value.length - MAX_DEBUG_FIELD_LENGTH
    } chars]`;
  }

  if (Array.isArray(value)) {
    return value.map((item) => truncateDebugValue(item));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, truncateDebugValue(item)]),
    );
  }

  return value;
}

function renderMarkdownCodeLine(line: string, key: string) {
  if (line.startsWith("```")) {
    return (
      <div key={key}>
        <span className="text-emerald-300">{line || " "}</span>
      </div>
    );
  }

  if (line.startsWith("# ")) {
    return (
      <div key={key}>
        <span className="text-sky-300">{line || " "}</span>
      </div>
    );
  }

  if (line.startsWith("## ")) {
    return (
      <div key={key}>
        <span className="text-cyan-300">{line || " "}</span>
      </div>
    );
  }

  return (
    <div key={key}>
      <span>{line || " "}</span>
    </div>
  );
}

function resolveOriginalRequestUrl(
  requestUrl: string | undefined,
  requestPath: string | undefined,
  requestHeaders: Record<string, string> | undefined,
  clientOrigin: string | null,
) {
  if (requestUrl) return requestUrl;
  if (!requestPath) return null;

  const forwardedProto =
    requestHeaders?.["x-forwarded-proto"] || requestHeaders?.["X-Forwarded-Proto"];
  const forwardedHost =
    requestHeaders?.["x-forwarded-host"] || requestHeaders?.["X-Forwarded-Host"];
  const host = requestHeaders?.host || requestHeaders?.Host;
  const origin = requestHeaders?.origin || requestHeaders?.Origin;

  const baseUrl =
    (forwardedProto && forwardedHost && `${forwardedProto}://${forwardedHost}`) ||
    (host && `${forwardedProto || "http"}://${host}`) ||
    origin ||
    clientOrigin;

  if (!baseUrl) return requestPath;

  try {
    return new URL(requestPath, baseUrl).toString();
  } catch {
    return requestPath;
  }
}

/**
 * Log Detail Component
 */
export function LogDetail({ log }: LogDetailProps) {
  const t = useTranslations("logs");
  const tc = useTranslations("common");
  const [activeTab, setActiveTab] = useState<
    "request" | "response" | "headers"
  >("request");
  const [layout, setLayout] = useState<"vertical" | "horizontal">("vertical");
  const [traceCopied, setTraceCopied] = useState(false);
  const [originalCurlCopied, setOriginalCurlCopied] = useState(false);
  const [convertedCurlCopied, setConvertedCurlCopied] = useState(false);
  const [debugDialogOpen, setDebugDialogOpen] = useState(false);
  const [debugCopied, setDebugCopied] = useState(false);
  const [retryConfirmOpen, setRetryConfirmOpen] = useState(false);
  const [retryDialogOpen, setRetryDialogOpen] = useState(false);
  const [retryWrapLines, setRetryWrapLines] = useState(false);
  const [retryStreamContent, setRetryStreamContent] = useState("");
  const [retryLoading, setRetryLoading] = useState(false);
  const [retryIsStreamingResult, setRetryIsStreamingResult] = useState(false);
  const [retryResult, setRetryResult] = useState<{
    response_status: number;
    response_body?: unknown;
    new_log_id?: number | null;
  } | null>(null);
  const [retryErrorMessage, setRetryErrorMessage] = useState<string | null>(null);
  const [clientOrigin, setClientOrigin] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setClientOrigin(window.location.origin);
  }, []);

  const responseStatus = log?.response_status;
  const statusVariant = useMemo<BadgeProps["variant"]>(() => {
    const status = responseStatus;
    if (status === null || status === undefined) return "outline";
    if (status >= 200 && status < 300) return "success";
    if (status >= 400 && status < 500) return "warning";
    if (status >= 500) return "error";
    return "outline";
  }, [responseStatus]);

  const modelMapping = useMemo(() => {
    const requestedModel = log?.requested_model;
    const targetModel = log?.target_model;
    if (!requestedModel && !targetModel) return "-";
    if (requestedModel === targetModel) return requestedModel || "-";
    return `${requestedModel || "-"} → ${targetModel || "-"}`;
  }, [log?.requested_model, log?.target_model]);

  const originalRequestUrl = useMemo(
    () =>
      resolveOriginalRequestUrl(
        log?.request_url,
        log?.request_path,
        log?.request_headers,
        clientOrigin,
      ),
    [clientOrigin, log?.request_headers, log?.request_path, log?.request_url],
  );

  // Token usage details - only show fields with non-zero values
  const tokenUsageItems = useMemo(() => {
    const details = log?.usage_details;
    if (!details) return [];

    const labelMap: Record<string, string> = {
      cached_tokens: t("detail.tokenUsage.cachedTokens"),
      cache_creation_input_tokens: t("detail.tokenUsage.cacheCreation"),
      cache_read_input_tokens: t("detail.tokenUsage.cacheRead"),
      input_audio_tokens: t("detail.tokenUsage.inputAudio"),
      output_audio_tokens: t("detail.tokenUsage.outputAudio"),
      input_image_tokens: t("detail.tokenUsage.inputImage"),
      output_image_tokens: t("detail.tokenUsage.outputImage"),
      input_video_tokens: t("detail.tokenUsage.inputVideo"),
      output_video_tokens: t("detail.tokenUsage.outputVideo"),
      reasoning_tokens: t("detail.tokenUsage.reasoning"),
      tool_tokens: t("detail.tokenUsage.toolTokens"),
    };

    return Object.entries(labelMap)
      .filter(([key]) => {
        const value = details[key];
        return typeof value === "number" && value > 0;
      })
      .map(([key, label]) => ({
        key,
        label,
        value: details[key] as number,
      }));
  }, [log?.usage_details, t]);

  const handleCopyTraceId = async () => {
    const traceId = log?.trace_id;
    if (!traceId) return;
    const ok = await copyToClipboard(traceId);
    if (!ok) return;
    setTraceCopied(true);
    setTimeout(() => setTraceCopied(false), 1500);
  };

  const handleCopyOriginalAsCurl = async () => {
    if (!log) return;
    const method = (log.request_method || "POST").toUpperCase();
    const url = originalRequestUrl || "<URL>";
    const body = JSON.stringify(log.request_body || {}, null, 2);
    const lines = [
      `curl -X ${method} '${url}'`,
      `  -H 'Content-Type: application/json'`,
      `  -H 'Authorization: Bearer YOUR_AUTH_TOKEN'`,
      `  -d '${body.replace(/'/g, "'\\''")}'`,
    ];
    const curl = lines.join(" \\\n");
    const ok = await copyToClipboard(curl);
    if (!ok) return;
    setOriginalCurlCopied(true);
    setTimeout(() => setOriginalCurlCopied(false), 1500);
  };

  const handleCopyConvertedAsCurl = async () => {
    if (!log?.converted_request_body) return;
    const method = (log.request_method || "POST").toUpperCase();
    const url = log.upstream_url || "<URL>";
    const body = JSON.stringify(log.converted_request_body, null, 2);
    const lines = [
      `curl -X ${method} '${url}'`,
      `  -H 'Content-Type: application/json'`,
      `  -H 'Authorization: Bearer YOUR_AUTH_TOKEN'`,
      `  -d '${body.replace(/'/g, "'\\''")}'`,
    ];
    const curl = lines.join(" \\\n");
    const ok = await copyToClipboard(curl);
    if (!ok) return;
    setConvertedCurlCopied(true);
    setTimeout(() => setConvertedCurlCopied(false), 1500);
  };

  const debugSections = useMemo<DebugSection[]>(() => {
    if (!log) return [];

    return [
      {
        title: t("detail.debugSections.userRequestUrl"),
        language: "text",
        content: `${(log.request_method || "POST").toUpperCase()} ${originalRequestUrl || "-"}`,
      },
      {
        title: t("detail.debugSections.userRequestBody"),
        language: "json",
        content: truncateDebugValue(log.request_body || {}),
      },
      {
        title: t("detail.debugSections.userResponseBody"),
        language: "json",
        content: truncateDebugValue(log.response_body || {}),
      },
      {
        title: t("detail.debugSections.forwardedRequest"),
        language: "json",
        content: {
          method: (log.request_method || "POST").toUpperCase(),
          url: log.upstream_url || null,
          body: truncateDebugValue(log.converted_request_body || {}),
        },
      },
      {
        title: t("detail.debugSections.forwardedResponse"),
        language: "json",
        content: truncateDebugValue(log.upstream_response_body || {}),
      },
      {
        title: t("detail.debugSections.requestHeaders"),
        language: "json",
        content: truncateDebugValue(log.request_headers || {}),
      },
      {
        title: t("detail.debugSections.responseHeaders"),
        language: "json",
        content: truncateDebugValue(log.response_headers || {}),
      },
      {
        title: t("detail.debugSections.failure"),
        language: "json",
        content: {
          error_info: log.error_info || null,
          status: log.response_status ?? null,
          retry_count: log.retry_count ?? 0,
          trace_id: log.trace_id || null,
          provider: log.provider_name || null,
          requested_model: log.requested_model || null,
          target_model: log.target_model || null,
          request_protocol: log.request_protocol || null,
          supplier_protocol: log.supplier_protocol || null,
          request_time: log.request_time || null,
        },
      },
    ];
  }, [log, originalRequestUrl, t]);

  const debugMarkdown = useMemo(() => {
    if (!log) return "";

    return [
      `# ${t("detail.debugDialogTitle")}`,
      "",
      t("detail.debugDialogDescription"),
      "",
      ...debugSections.flatMap((section) => [
        `## ${section.title}`,
        "",
        `\`\`\`${section.language}`,
        section.language === "json"
          ? JSON.stringify(section.content, null, 2)
          : String(section.content ?? "-"),
        "```",
        "",
      ]),
    ].join("\n");
  }, [debugSections, log, t]);

  const handleCopyDebugMarkdown = async () => {
    if (!debugMarkdown) return;
    const ok = await copyToClipboard(debugMarkdown);
    if (!ok) return;
    setDebugCopied(true);
    setTimeout(() => setDebugCopied(false), 1500);
  };

  const handleRetryRequest = async () => {
    if (!log?.id) return;
    setRetryDialogOpen(true);
    setRetryWrapLines(false);
    setRetryStreamContent("");
    setRetryIsStreamingResult(Boolean(log.is_stream));
    setRetryResult(null);
    setRetryErrorMessage(null);
    setRetryLoading(true);

    try {
      const token = getStoredAdminToken();
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => {
        controller.abort();
      }, RETRY_TIMEOUT_MS);
      try {
        const response = await fetch(`/api/admin/logs/${log.id}/retry`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(errorText || t("detail.retryFailed"));
        }

        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("text/event-stream")) {
          const reader = response.body?.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          let streamedContent = "";
          if (!reader) {
            throw new Error(t("detail.retryFailed"));
          }

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            let separatorIndex = buffer.indexOf("\n\n");
            while (separatorIndex >= 0) {
              const rawEvent = buffer.slice(0, separatorIndex);
              buffer = buffer.slice(separatorIndex + 2);

              const lines = rawEvent.split(/\r?\n/);
              const eventType =
                lines.find((line) => line.startsWith("event:"))?.slice(6).trim() ||
                "message";
              const dataPayload = lines
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trim())
                .join("\n");

              if (dataPayload) {
                const payload = JSON.parse(dataPayload) as {
                  content?: string;
                  response_status?: number;
                  new_log_id?: number | null;
                };

                if (eventType === "status") {
                  setRetryResult((current) => ({
                    response_status:
                      payload.response_status ?? current?.response_status ?? 0,
                    response_body: current?.response_body,
                    new_log_id: current?.new_log_id,
                  }));
                } else if (eventType === "chunk") {
                  const chunk = payload.content || "";
                  streamedContent += chunk;
                  setRetryStreamContent(streamedContent);
                } else if (eventType === "done") {
                  setRetryResult({
                    response_status: payload.response_status ?? 0,
                    response_body: streamedContent,
                    new_log_id: payload.new_log_id ?? null,
                  });
                }
              }

              separatorIndex = buffer.indexOf("\n\n");
            }
          }
        } else {
          const result = await response.json();
          setRetryIsStreamingResult(false);
          setRetryResult(result);
        }
      } finally {
        window.clearTimeout(timeoutId);
      }
    } catch (error) {
      setRetryErrorMessage(
        error instanceof Error && error.name === "AbortError"
          ? t("detail.retryTimeout")
          : error instanceof Error
            ? error.message
            : t("detail.retryFailed"),
      );
    } finally {
      setRetryLoading(false);
    }
  };

  const handleOpenRetriedLog = () => {
    const newLogId = retryResult?.new_log_id;
    if (!newLogId || typeof window === "undefined") return;
    const currentLocation = `${window.location.pathname}${window.location.search}`;
    window.location.href =
      `/logs/detail?id=${encodeURIComponent(String(newLogId))}` +
      `&returnTo=${encodeURIComponent(currentLocation)}`;
  };

  const tabButtonClass = (tab: typeof activeTab) =>
    `inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
      activeTab === tab
        ? "bg-background text-foreground shadow-sm"
        : "text-muted-foreground hover:text-foreground"
    }`;

  const renderPayloadViewer = (payload: unknown, maxHeight: string) => {
    if (isStreamPayload(payload)) {
      return <StreamJsonViewer data={payload} maxHeight={maxHeight} />;
    }
    return <JsonViewer data={payload} maxHeight={maxHeight} />;
  };

  if (!log) return null;

  const retryUnsupported =
    !log.request_path ||
    !log.api_key_id ||
    (typeof log.request_body === "object" &&
      log.request_body !== null &&
      "_files" in log.request_body);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <CardTitle className="text-base">
                {t("detail.overview")}
              </CardTitle>
              <div className="mt-1 text-sm text-muted-foreground">
                {t("detail.overviewDescription")}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2 sm:justify-end">
              {log.is_stream && (
                <span title={t("list.streamRequest")}>
                  <Waves
                    className="h-4 w-4 text-blue-500"
                    suppressHydrationWarning
                  />
                </span>
              )}
              <Badge variant={statusVariant}>
                {log.response_status ?? t("unknown")}
              </Badge>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 rounded-lg border bg-muted/30 px-3 py-2">
            <div className="min-w-0">
              <div className="text-xs text-muted-foreground">
                {t("detail.traceId")}
              </div>
              <div className="truncate font-mono text-sm" title={log.trace_id}>
                {log.trace_id || "-"}
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1 px-2"
              onClick={handleCopyTraceId}
              disabled={!log.trace_id}
            >
              {traceCopied ? (
                <>
                  <Check
                    className="h-3.5 w-3.5 text-green-600"
                    suppressHydrationWarning
                  />
                  <span className="text-green-600">{t("detail.copied")}</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" suppressHydrationWarning />
                  <span>{t("detail.copy")}</span>
                </>
              )}
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-start gap-2">
              <Clock
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="min-w-0">
                <div className="text-muted-foreground">
                  {t("detail.requestTime")}
                </div>
                <div
                  className="truncate font-medium"
                  title={formatDateTime(log.request_time, {
                    showTime: true,
                    showSeconds: true,
                  })}
                >
                  {formatDateTime(log.request_time)}
                </div>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Server
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="min-w-0">
                <div className="text-muted-foreground">
                  {t("detail.provider")}
                </div>
                <div className="truncate font-medium" title={log.provider_name}>
                  {log.provider_name || "-"}
                </div>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Shield
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="min-w-0">
                <div className="text-muted-foreground">
                  {t("detail.apiKey")}
                </div>
                <div className="truncate font-medium" title={log.api_key_name}>
                  {log.api_key_name || "-"}
                  {log.api_key_id ? (
                    <span className="text-muted-foreground">
                      {" "}
                      ({log.api_key_id})
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Play
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="min-w-0">
                <div className="text-muted-foreground">
                  {t("detail.modelMapping")}
                </div>
                <div className="truncate font-medium" title={modelMapping}>
                  {modelMapping}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="mb-2 text-sm font-medium">
              {t("detail.metrics")}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-7">
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {t("detail.ttfb")}
                </span>
                <span className="font-medium">
                  {formatDuration(log.first_byte_delay_ms)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {t("detail.total")}
                </span>
                <span className="font-medium">
                  {formatDuration(log.total_time_ms || 0)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {t("detail.input")}
                </span>
                <span className="font-medium">{log.input_tokens ?? 0}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {t("detail.output")}
                </span>
                <span className="font-medium">{log.output_tokens ?? 0}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {t("detail.retries")}
                </span>
                <span className="font-medium">{log.retry_count ?? 0}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">
                  {t("detail.tokens")}
                </span>
                <span className="font-medium">
                  {(log.input_tokens ?? 0) + (log.output_tokens ?? 0)}
                </span>
              </div>
              <div
                className="flex items-center justify-between gap-2"
                title={t("detail.costTooltip", {
                  input: formatUsd(log.input_cost),
                  output: formatUsd(log.output_cost),
                })}
              >
                <span className="text-muted-foreground">
                  {t("detail.cost")}
                </span>
                <span className="font-medium font-mono">
                  {formatUsd(log.total_cost)}
                </span>
              </div>
            </div>
          </div>

          {tokenUsageItems.length > 0 && (
            <div className="rounded-lg border bg-muted/30 p-3">
              <div className="mb-2 text-sm font-medium">
                {t("detail.tokenUsageDetails")}
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-6">
                {tokenUsageItems.map((item) => (
                  <div
                    key={item.key}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="font-medium">
                      {item.value.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="mb-2 text-sm font-medium">
              {t("detail.requestFlow")}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <div className="inline-flex items-center rounded-md border bg-background px-2 py-1">
                <span className="text-muted-foreground">
                  {t("detail.apiKey")}
                </span>
                <span className="ml-2 font-medium">
                  {log.api_key_name || "-"}
                </span>
              </div>
              <ArrowRight
                className="h-4 w-4 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="inline-flex items-center rounded-md border bg-background px-2 py-1">
                <span className="text-muted-foreground">
                  {t("detail.provider")}
                </span>
                <span className="ml-2 font-medium">
                  {log.provider_name || "-"}
                </span>
              </div>
              <ArrowRight
                className="h-4 w-4 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="inline-flex items-center rounded-md border bg-background px-2 py-1">
                <span className="text-muted-foreground">
                  {t("detail.model")}
                </span>
                <span className="ml-2 font-medium">{modelMapping}</span>
              </div>
              <ArrowRight
                className="h-4 w-4 text-muted-foreground"
                suppressHydrationWarning
              />
              <div className="inline-flex items-center rounded-md border bg-background px-2 py-1">
                <span className="text-muted-foreground">
                  {t("detail.status")}
                </span>
                <span className="ml-2 font-medium">
                  {log.response_status ?? t("unknown")}
                </span>
              </div>
              {log.request_protocol &&
                log.supplier_protocol &&
                log.request_protocol !== log.supplier_protocol && (
                  <>
                    <ArrowRight
                      className="h-4 w-4 text-muted-foreground"
                      suppressHydrationWarning
                    />
                    <div className="inline-flex items-center rounded-md border bg-background px-2 py-1">
                      <span className="text-muted-foreground">
                        {t("detail.protocol")}
                      </span>
                      <span className="ml-2 font-medium">
                        {log.request_protocol} → {log.supplier_protocol}
                      </span>
                    </div>
                  </>
                )}
            </div>
          </div>
        </CardContent>
      </Card>

      {log.error_info && (
        <Card className="border-red-200 bg-red-50/50">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-red-700">
              <AlertCircle className="h-4 w-4" suppressHydrationWarning />
              {t("detail.error")}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="break-words font-mono text-sm text-red-700">
              {log.error_info}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <div>
            <CardTitle className="text-base">{t("detail.payload")}</CardTitle>
            <div className="mt-1 text-sm text-muted-foreground">
              {t("detail.payloadDescription")}
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setRetryConfirmOpen(true)}
              disabled={retryLoading || retryUnsupported}
              title={retryUnsupported ? t("detail.retryUnsupported") : undefined}
            >
              {retryLoading ? (
                <Loader2
                  className="h-4 w-4 animate-spin"
                  suppressHydrationWarning
                />
              ) : (
                <RotateCcw className="h-4 w-4" suppressHydrationWarning />
              )}
              <span>
                {retryLoading
                  ? t("detail.retryRunning")
                  : t("detail.retry")}
              </span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setDebugDialogOpen(true)}
            >
              <Bug className="h-4 w-4" suppressHydrationWarning />
              <span>{t("detail.debug")}</span>
            </Button>
            {(activeTab === "request" || activeTab === "response") && (
              <div className="inline-flex rounded-lg border bg-muted/30 p-1">
                <button
                  onClick={() => setLayout("vertical")}
                  className={`inline-flex items-center rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    layout === "vertical"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  title={t("detail.verticalLayout")}
                >
                  <Rows className="h-3.5 w-3.5" suppressHydrationWarning />
                </button>
                <button
                  onClick={() => setLayout("horizontal")}
                  className={`inline-flex items-center rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                    layout === "horizontal"
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  title={t("detail.horizontalLayout")}
                >
                  <Columns className="h-3.5 w-3.5" suppressHydrationWarning />
                </button>
              </div>
            )}
            <div className="inline-flex w-full rounded-lg border bg-muted/30 p-1 sm:w-auto">
              <button
                className={tabButtonClass("request")}
                onClick={() => setActiveTab("request")}
              >
                {t("detail.request")}
              </button>
              <button
                className={tabButtonClass("response")}
                onClick={() => setActiveTab("response")}
              >
                {t("detail.response")}
              </button>
              <button
                className={tabButtonClass("headers")}
                onClick={() => setActiveTab("headers")}
              >
                {t("detail.headers")}
              </button>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {activeTab === "request" && (
            <div
              className={
                layout === "horizontal" && log.converted_request_body
                  ? "grid grid-cols-1 gap-6 lg:grid-cols-2"
                  : "space-y-6"
              }
            >
              {(log.request_url || log.request_path || log.upstream_url) && (
                <div
                  className={
                    layout === "horizontal" && log.converted_request_body
                      ? "col-span-full"
                      : ""
                  }
                >
                  <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                    {originalRequestUrl && (
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-muted-foreground shrink-0">
                          {t("detail.requestUrl")}
                        </span>
                        <code className="truncate font-mono text-xs">
                          {log.request_method && (
                            <span className="font-semibold">
                              {log.request_method}{" "}
                            </span>
                          )}
                          {originalRequestUrl}
                        </code>
                      </div>
                    )}
                    {originalRequestUrl && log.upstream_url && (
                      <ArrowRight
                        className="h-4 w-4 shrink-0 text-muted-foreground"
                        suppressHydrationWarning
                      />
                    )}
                    {log.upstream_url && (
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-muted-foreground shrink-0">
                          {t("detail.upstreamUrl")}
                        </span>
                        <code className="truncate font-mono text-xs">
                          {log.request_method && (
                            <span className="font-semibold">
                              {log.request_method}{" "}
                            </span>
                          )}
                          {log.upstream_url}
                        </code>
                      </div>
                    )}
                  </div>
                </div>
              )}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">
                    {t("detail.originalRequest")}
                  </div>
                  {log.request_protocol && (
                    <Badge variant="outline" className="font-mono text-xs">
                      {log.request_protocol}
                    </Badge>
                  )}
                </div>
                <JsonViewer
                  data={log.request_body}
                  maxHeight={layout === "horizontal" ? "65vh" : "45vh"}
                  extraActions={
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1 px-2"
                      onClick={handleCopyOriginalAsCurl}
                    >
                      {originalCurlCopied ? (
                        <>
                          <Check
                            className="h-3.5 w-3.5 text-green-600"
                            suppressHydrationWarning
                          />
                          <span className="text-green-600">
                            {t("detail.copied")}
                          </span>
                        </>
                      ) : (
                        <>
                          <Terminal
                            className="h-3.5 w-3.5"
                            suppressHydrationWarning
                          />
                          <span>{t("detail.copyAsCurl")}</span>
                        </>
                      )}
                    </Button>
                  }
                />
              </div>

              {log.converted_request_body && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">
                      {t("detail.convertedRequest")}
                    </div>
                    {log.supplier_protocol && (
                      <Badge variant="outline" className="font-mono text-xs">
                        {log.supplier_protocol}
                      </Badge>
                    )}
                  </div>
                  <JsonViewer
                    data={log.converted_request_body}
                    maxHeight={layout === "horizontal" ? "65vh" : "45vh"}
                    extraActions={
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1 px-2"
                        onClick={handleCopyConvertedAsCurl}
                      >
                        {convertedCurlCopied ? (
                          <>
                            <Check
                              className="h-3.5 w-3.5 text-green-600"
                              suppressHydrationWarning
                            />
                            <span className="text-green-600">
                              {t("detail.copied")}
                            </span>
                          </>
                        ) : (
                          <>
                            <Terminal
                              className="h-3.5 w-3.5"
                              suppressHydrationWarning
                            />
                            <span>{t("detail.copyAsCurl")}</span>
                          </>
                        )}
                      </Button>
                    }
                  />
                </div>
              )}
            </div>
          )}

          {activeTab === "response" && (
            <div
              className={
                layout === "horizontal" && log.upstream_response_body
                  ? "grid grid-cols-1 gap-6 lg:grid-cols-2"
                  : "space-y-6"
              }
            >
              {log.upstream_response_body && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">
                      {t("detail.originalResponse")}
                    </div>
                    {log.supplier_protocol && (
                      <Badge variant="outline" className="font-mono text-xs">
                        {log.supplier_protocol}
                      </Badge>
                    )}
                  </div>
                  {renderPayloadViewer(
                    log.upstream_response_body,
                    layout === "horizontal" ? "65vh" : "45vh",
                  )}
                </div>
              )}

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">
                    {t("detail.convertedResponse")}
                  </div>
                  {log.request_protocol && (
                    <Badge variant="outline" className="font-mono text-xs">
                      {log.request_protocol}
                    </Badge>
                  )}
                </div>
                {renderPayloadViewer(
                  log.response_body || {},
                  layout === "horizontal" ? "65vh" : "45vh",
                )}
              </div>
            </div>
          )}

          {activeTab === "headers" && log && (
            <div className="space-y-6">
              <div className="space-y-3">
                <h3 className="text-sm font-medium">
                  {t("detail.requestHeaders")}
                </h3>
                <JsonViewer data={log.request_headers || {}} />
              </div>
              <div className="space-y-3">
                <h3 className="text-sm font-medium">
                  {t("detail.responseHeaders")}
                </h3>
                <JsonViewer data={log.response_headers || {}} />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={debugDialogOpen} onOpenChange={setDebugDialogOpen}>
        <DialogContent className="h-[85vh] max-h-[85vh] w-[min(96vw,1100px)] max-w-none overflow-hidden p-0">
          <div className="flex h-full min-h-0 min-w-0 flex-col p-6">
            <DialogHeader className="pr-8">
              <DialogTitle>{t("detail.debugDialogTitle")}</DialogTitle>
              <DialogDescription>
                {t("detail.debugDialogDescription")}
              </DialogDescription>
            </DialogHeader>

            <div className="mt-4 flex shrink-0 items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={handleCopyDebugMarkdown}
              >
                {debugCopied ? (
                  <>
                    <Check
                      className="h-4 w-4 text-green-600"
                      suppressHydrationWarning
                    />
                    <span className="text-green-600">{t("detail.copied")}</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" suppressHydrationWarning />
                    <span>{t("detail.copy")}</span>
                  </>
                )}
              </Button>
            </div>

            <div className="mt-4 min-h-0 min-w-0 flex-1 overflow-hidden rounded-lg border bg-slate-950">
              <div className="h-full max-w-full overflow-x-auto overflow-y-auto">
                <pre className="min-h-full min-w-full max-w-full p-4 font-mono text-xs leading-6 text-slate-100 select-text">
                  <code className="block min-w-max max-w-full">
                  {debugMarkdown.split("\n").map((line, index) =>
                    renderMarkdownCodeLine(line, `${index}-${line}`),
                  )}
                  </code>
                </pre>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={retryConfirmOpen}
        onOpenChange={setRetryConfirmOpen}
        title={t("detail.retryConfirmTitle")}
        description={t("detail.retryConfirmDescription")}
        confirmText={t("detail.retryConfirmAction")}
        onConfirm={() => {
          setRetryConfirmOpen(false);
          void handleRetryRequest();
        }}
        loading={retryLoading}
      />

      <Dialog open={retryDialogOpen} onOpenChange={setRetryDialogOpen}>
        <DialogContent className="w-[min(96vw,1000px)] max-w-none overflow-hidden">
          <div className="flex min-h-0 min-w-0 flex-col">
            <DialogHeader className="pr-8">
              <DialogTitle>{t("detail.retryDialogTitle")}</DialogTitle>
              <DialogDescription>
                {t("detail.retryDialogDescription")}
              </DialogDescription>
            </DialogHeader>

            <div className="mt-4 flex items-center justify-between gap-3 text-sm">
              <div className="text-muted-foreground">
                {t("detail.retryStatus")}
              </div>
              <div className="font-medium">
                {retryResult?.response_status ?? "-"}
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">
                  {t("detail.retryResult")}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => setRetryWrapLines((value) => !value)}
                >
                  <WrapText className="h-4 w-4" suppressHydrationWarning />
                  <span>
                    {retryWrapLines
                      ? tc("jsonViewer.noWrap")
                      : tc("jsonViewer.wrap")}
                  </span>
                </Button>
              </div>
              {retryErrorMessage ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                  {retryErrorMessage}
                </div>
              ) : retryLoading ? (
                <div className="flex min-h-32 items-center justify-center rounded-lg border bg-muted/30">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2
                      className="h-4 w-4 animate-spin"
                      suppressHydrationWarning
                    />
                    <span>{t("detail.retryRunning")}</span>
                  </div>
                </div>
              ) : retryIsStreamingResult ? (
                <div className="min-w-0 max-w-full overflow-hidden rounded-lg border bg-muted/50">
                  <div
                    className="max-w-full overflow-x-auto overflow-y-auto p-3 text-sm font-mono"
                    style={{ maxHeight: "50vh" }}
                  >
                    <code
                      className={
                        retryWrapLines
                          ? "block min-w-0 whitespace-pre-wrap break-words"
                          : "block min-w-max whitespace-pre"
                      }
                    >
                      {retryStreamContent}
                    </code>
                  </div>
                </div>
              ) : (
                <JsonViewer
                  data={retryResult?.response_body ?? {}}
                  maxHeight="50vh"
                  wrapLines={retryWrapLines}
                  onWrapLinesChange={setRetryWrapLines}
                  showWrapToggle={false}
                />
              )}
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setRetryDialogOpen(false)}
              >
                {tc("close")}
              </Button>
              <Button
                onClick={handleOpenRetriedLog}
                disabled={!retryResult?.new_log_id}
              >
                {t("detail.openRetriedLog")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
