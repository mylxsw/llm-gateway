/**
 * Log Detail Component
 * Displays detailed information of a request log, including request/response body, headers, etc.
 */

"use client";

import React, { useMemo, useState } from "react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertCircle,
  ArrowRight,
  Check,
  Clock,
  Columns,
  Copy,
  Play,
  Rows,
  Server,
  Shield,
  Terminal,
  Waves,
} from "lucide-react";
import { RequestLogDetail } from "@/types";
import {
  copyToClipboard,
  formatDateTime,
  formatDuration,
  formatUsd,
} from "@/lib/utils";
import { JsonViewer } from "@/components/common/JsonViewer";
import {
  StreamJsonViewer,
  isStreamPayload,
} from "@/components/common/StreamJsonViewer";
import { useTranslations } from "next-intl";

interface LogDetailProps {
  /** Log data */
  log: RequestLogDetail | null;
}

/**
 * Log Detail Component
 */
export function LogDetail({ log }: LogDetailProps) {
  const t = useTranslations("logs");
  const [activeTab, setActiveTab] = useState<
    "request" | "response" | "headers"
  >("request");
  const [layout, setLayout] = useState<"vertical" | "horizontal">("vertical");
  const [traceCopied, setTraceCopied] = useState(false);
  const [curlCopied, setCurlCopied] = useState(false);

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

  const handleCopyAsCurl = async () => {
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
    setCurlCopied(true);
    setTimeout(() => setCurlCopied(false), 1500);
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
              {(log.request_path || log.upstream_url) && (
                <div
                  className={
                    layout === "horizontal" && log.converted_request_body
                      ? "col-span-full"
                      : ""
                  }
                >
                  <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                    {log.request_path && (
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
                          {log.request_path}
                        </code>
                      </div>
                    )}
                    {log.request_path && log.upstream_url && (
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
                        onClick={handleCopyAsCurl}
                      >
                        {curlCopied ? (
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
    </div>
  );
}
