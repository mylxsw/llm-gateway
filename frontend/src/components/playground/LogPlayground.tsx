'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { executeLogPlaygroundRequest } from '@/lib/api';
import { useProviderProtocolConfigs } from '@/lib/providerProtocols';
import { getApiErrorMessage } from '@/lib/api/error';
import { formatDuration } from '@/lib/utils';
import { JsonViewer, StreamJsonViewer } from '@/components/common';
import { LogPlaygroundExecuteResponse, RequestLogDetail } from '@/types';
import {
  Braces,
  ChevronDown,
  ChevronRight,
  Loader2,
  Pencil,
  Play,
} from 'lucide-react';

type JsonPath = Array<string | number>;
type EditorMode = 'json' | 'text';

interface LogPlaygroundProps {
  log: RequestLogDetail;
}

type FieldEditorState = {
  path: JsonPath;
  label: string;
  value: unknown;
} | null;

const FALLBACK_PROTOCOLS = [
  { protocol: 'openai', label: 'OpenAI', implementation: 'openai' },
  { protocol: 'openai_responses', label: 'OpenAI Responses', implementation: 'openai_responses' },
  { protocol: 'anthropic', label: 'Anthropic', implementation: 'anthropic' },
  { protocol: 'gemini', label: 'Google Gemini', implementation: 'gemini' },
];

const DEFAULT_EXPANDED_JSON_DEPTH = 4;

function cloneJsonValue<T>(value: T): T {
  if (value === undefined) {
    return value;
  }
  return JSON.parse(JSON.stringify(value)) as T;
}

function getImplementationProtocol(protocol: string, configs: Array<{ protocol: string; implementation: string }>) {
  return configs.find((item) => item.protocol === protocol)?.implementation ?? protocol;
}

function deriveRequestPath(
  protocol: string,
  requestBody: unknown,
  originalProtocol?: string,
  originalPath?: string,
  configs: Array<{ protocol: string; implementation: string }> = []
) {
  if (protocol === originalProtocol && originalPath) {
    return originalPath;
  }

  const implementation = getImplementationProtocol(protocol, configs);
  if (implementation === 'anthropic') {
    return '/v1/messages';
  }
  if (implementation === 'openai_responses') {
    return '/v1/responses';
  }
  if (implementation === 'gemini') {
    const model =
      requestBody && typeof requestBody === 'object' && !Array.isArray(requestBody)
        ? (requestBody as Record<string, unknown>).model
        : undefined;
    const stream =
      requestBody && typeof requestBody === 'object' && !Array.isArray(requestBody)
        ? Boolean((requestBody as Record<string, unknown>).stream)
        : false;
    if (typeof model === 'string' && model.trim()) {
      return `/v1beta/models/${model}:${stream ? 'streamGenerateContent?alt=sse' : 'generateContent'}`;
    }
    return '/v1beta/models/{model}:generateContent';
  }
  return '/v1/chat/completions';
}

function isStreamingRequest(
  protocol: string,
  requestPath: string,
  requestBody: unknown,
  configs: Array<{ protocol: string; implementation: string }>
) {
  const implementation = getImplementationProtocol(protocol, configs);
  if (implementation === 'gemini') {
    return requestPath.includes('streamGenerateContent') || requestPath.includes('alt=sse');
  }
  return (
    !!requestBody &&
    typeof requestBody === 'object' &&
    !Array.isArray(requestBody) &&
    Boolean((requestBody as Record<string, unknown>).stream)
  );
}

function summarizeValue(value: unknown) {
  if (typeof value === 'string') {
    return value.length > 80 ? `${value.slice(0, 80)}...` : value;
  }
  if (Array.isArray(value)) {
    return `Array(${value.length})`;
  }
  if (value && typeof value === 'object') {
    return `Object(${Object.keys(value as Record<string, unknown>).length})`;
  }
  if (value === null) {
    return 'null';
  }
  return String(value);
}

function getValueType(value: unknown) {
  if (Array.isArray(value)) return 'array';
  if (value === null) return 'null';
  return typeof value;
}

function updateValueAtPath(source: unknown, path: JsonPath, nextValue: unknown): unknown {
  if (path.length === 0) {
    return nextValue;
  }

  const [head, ...rest] = path;
  if (Array.isArray(source)) {
    const cloned = [...source];
    cloned[head as number] = updateValueAtPath(cloned[head as number], rest, nextValue);
    return cloned;
  }

  if (source && typeof source === 'object') {
    const cloned = { ...(source as Record<string, unknown>) };
    cloned[String(head)] = updateValueAtPath(cloned[String(head)], rest, nextValue);
    return cloned;
  }

  return source;
}

function JsonNode({
  label,
  value,
  path,
  depth,
  onEdit,
}: {
  label: string;
  value: unknown;
  path: JsonPath;
  depth: number;
  onEdit: (path: JsonPath, label: string, value: unknown) => void;
}) {
  const [open, setOpen] = useState(depth <= DEFAULT_EXPANDED_JSON_DEPTH);
  const isContainer = Array.isArray(value) || (!!value && typeof value === 'object');
  const entries = Array.isArray(value)
    ? value.map((item, index) => ({ key: `[${index}]`, pathKey: index, value: item }))
    : value && typeof value === 'object'
      ? Object.entries(value as Record<string, unknown>).map(([key, item]) => ({
          key,
          pathKey: key,
          value: item,
        }))
      : [];

  return (
    <div className={depth > 0 ? 'border-l border-border/60 pl-4' : ''}>
      <div className="flex items-start gap-2 py-2">
        <button
          type="button"
          className="mt-0.5 text-muted-foreground"
          onClick={() => isContainer && setOpen((current) => !current)}
        >
          {isContainer ? (
            open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
          ) : (
            <span className="inline-block h-4 w-4" />
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium">{label}</span>
            <Badge variant="outline" className="font-mono text-[10px] uppercase tracking-wide">
              {getValueType(value)}
            </Badge>
          </div>
          <div className="mt-1 break-all font-mono text-xs text-muted-foreground">
            {summarizeValue(value)}
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 gap-1 px-2"
          onClick={() => onEdit(path, label, value)}
        >
          <Pencil className="h-3.5 w-3.5" />
          <span>Edit</span>
        </Button>
      </div>

      {isContainer && open ? (
        <div className="space-y-1 pb-2">
          {entries.length > 0 ? (
            entries.map((entry) => (
              <JsonNode
                key={`${path.join('.')}-${String(entry.pathKey)}`}
                label={entry.key}
                value={entry.value}
                path={[...path, entry.pathKey]}
                depth={depth + 1}
                onEdit={onEdit}
              />
            ))
          ) : (
            <div className="pb-2 pl-10 text-xs text-muted-foreground">empty</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function LogPlayground({ log }: LogPlaygroundProps) {
  const t = useTranslations('logs');
  const tCommon = useTranslations('common');
  const { configs } = useProviderProtocolConfigs();
  const protocolOptions = configs.length > 0 ? configs : FALLBACK_PROTOCOLS;

  const [protocol, setProtocol] = useState(log.request_protocol || 'openai');
  const [requestBody, setRequestBody] = useState<unknown>(cloneJsonValue(log.request_body || {}));
  const [requestHeaders, setRequestHeaders] = useState<Record<string, string>>(
    cloneJsonValue(log.request_headers || {})
  );
  const [editorState, setEditorState] = useState<FieldEditorState>(null);
  const [editorMode, setEditorMode] = useState<EditorMode>('json');
  const [editorValue, setEditorValue] = useState('');
  const [editorError, setEditorError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<LogPlaygroundExecuteResponse | null>(null);
  const [streamContent, setStreamContent] = useState('');
  const [isStreamResult, setIsStreamResult] = useState(Boolean(log.is_stream));
  const [requestError, setRequestError] = useState<string | null>(null);
  const [initializedLogId, setInitializedLogId] = useState<number | null>(null);

  useEffect(() => {
    if (initializedLogId === log.id) {
      return;
    }
    setInitializedLogId(log.id);
    setProtocol(log.request_protocol || 'openai');
    setRequestBody(cloneJsonValue(log.request_body || {}));
    setRequestHeaders(cloneJsonValue(log.request_headers || {}));
    setResponse(null);
    setStreamContent('');
    setIsStreamResult(Boolean(log.is_stream));
    setRequestError(null);
  }, [initializedLogId, log]);

  const requestPath = useMemo(
    () => deriveRequestPath(protocol, requestBody, log.request_protocol, log.request_path, protocolOptions),
    [log.request_path, log.request_protocol, protocol, protocolOptions, requestBody]
  );

  const isStream = useMemo(
    () => isStreamingRequest(protocol, requestPath, requestBody, protocolOptions),
    [protocol, protocolOptions, requestBody, requestPath]
  );

  const handleOpenEditor = (path: JsonPath, label: string, value: unknown) => {
    setEditorState({ path, label, value });
    if (typeof value === 'string') {
      setEditorMode('text');
      setEditorValue(value);
    } else {
      setEditorMode('json');
      setEditorValue(JSON.stringify(value, null, 2));
    }
    setEditorError(null);
  };

  const handleApplyEditor = () => {
    if (!editorState) return;
    try {
      const nextValue = editorMode === 'text' ? editorValue : JSON.parse(editorValue);
      setRequestBody((current: unknown) =>
        updateValueAtPath(current, editorState.path, nextValue)
      );
      setEditorState(null);
      setEditorError(null);
    } catch {
      setEditorError(t('playground.editorInvalidJson'));
    }
  };

  const handleRun = async () => {
    setRunning(true);
    setRequestError(null);
    setResponse(null);
    setStreamContent('');
    setIsStreamResult(isStream);

    try {
      const fetchResponse = await executeLogPlaygroundRequest(log.id, {
        protocol,
        request_path: requestPath,
        request_headers: requestHeaders,
        request_body: requestBody,
      });

      if (!fetchResponse.ok) {
        const errorText = await fetchResponse.text();
        throw new Error(errorText || t('playground.runFailed'));
      }

      const contentType = fetchResponse.headers.get('content-type') || '';
      if (contentType.includes('text/event-stream')) {
        const reader = fetchResponse.body?.getReader();
        if (!reader) {
          throw new Error(t('playground.runFailed'));
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let streamed = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let separatorIndex = buffer.indexOf('\n\n');
          while (separatorIndex >= 0) {
            const rawEvent = buffer.slice(0, separatorIndex);
            buffer = buffer.slice(separatorIndex + 2);

            const lines = rawEvent.split(/\r?\n/);
            const eventType =
              lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message';
            const dataPayload = lines
              .filter((line) => line.startsWith('data:'))
              .map((line) => line.slice(5).trim())
              .join('\n');

            if (dataPayload) {
              const payload = JSON.parse(dataPayload) as LogPlaygroundExecuteResponse & { content?: string };
              if (eventType === 'status') {
                setResponse((current: LogPlaygroundExecuteResponse | null) => ({
                  ...(current ?? {}),
                  response_status: payload.response_status,
                  trace_id: payload.trace_id,
                  provider_name: payload.provider_name,
                  target_model: payload.target_model,
                  first_byte_delay_ms: payload.first_byte_delay_ms,
                }));
              } else if (eventType === 'chunk') {
                streamed += payload.content || '';
                setStreamContent(streamed);
              } else if (eventType === 'done') {
                setResponse({
                  response_status: payload.response_status,
                  response_body: payload.response_body ?? streamed,
                  trace_id: payload.trace_id,
                  provider_name: payload.provider_name,
                  target_model: payload.target_model,
                  first_byte_delay_ms: payload.first_byte_delay_ms,
                  total_time_ms: payload.total_time_ms,
                });
              }
            }

            separatorIndex = buffer.indexOf('\n\n');
          }
        }
        return;
      }

      const result = (await fetchResponse.json()) as LogPlaygroundExecuteResponse;
      setResponse(result);
      setIsStreamResult(false);
    } catch (error) {
      setRequestError(getApiErrorMessage(error, t('playground.runFailed')));
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="min-h-[70vh]">
          <CardHeader>
            <CardTitle>{t('playground.requestTitle')}</CardTitle>
            <CardDescription>{t('playground.requestDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label>{t('playground.requestType')}</Label>
                <Select value={protocol} onValueChange={setProtocol}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {protocolOptions.map((item) => (
                      <SelectItem key={item.protocol} value={item.protocol}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-xs text-muted-foreground">{t('playground.requestPath')}</div>
                <div className="mt-1 break-all font-mono text-sm">{requestPath}</div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="font-mono text-xs">
                  {protocol}
                </Badge>
                <Badge variant={isStream ? 'default' : 'secondary'} className="text-xs">
                  {isStream ? t('playground.streamMode') : t('playground.nonStreamMode')}
                </Badge>
              </div>
            </div>

            <div className="rounded-xl border bg-background">
              <div className="flex items-center justify-between border-b px-4 py-3">
                <div>
                  <div className="text-sm font-medium">{t('playground.requestBody')}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('playground.requestBodyHint')}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  onClick={() => handleOpenEditor([], 'root', requestBody)}
                >
                  <Braces className="h-3.5 w-3.5" />
                  <span>{t('playground.editWholeJson')}</span>
                </Button>
              </div>
              <div className="max-h-[60vh] overflow-auto px-4 py-3">
                <JsonNode
                  label="root"
                  value={requestBody}
                  path={[]}
                  depth={0}
                  onEdit={handleOpenEditor}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="min-h-[70vh]">
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle>{t('playground.responseTitle')}</CardTitle>
                <CardDescription>{t('playground.responseDescription')}</CardDescription>
              </div>
              <Button type="button" onClick={handleRun} disabled={running} className="gap-2">
                {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                <span>{t('playground.run')}</span>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-xs text-muted-foreground">{t('playground.responseStatus')}</div>
                <div className="mt-1 font-mono text-sm">{response?.response_status ?? '-'}</div>
              </div>
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-xs text-muted-foreground">{t('playground.responseTargetModel')}</div>
                <div className="mt-1 break-all font-mono text-sm">{response?.target_model ?? '-'}</div>
              </div>
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-xs text-muted-foreground">{t('playground.responseProvider')}</div>
                <div className="mt-1 break-all font-mono text-sm">{response?.provider_name ?? '-'}</div>
              </div>
              <div className="rounded-lg border bg-muted/30 px-3 py-2">
                <div className="text-xs text-muted-foreground">{t('playground.responseLatency')}</div>
                <div className="mt-1 font-mono text-sm">
                  {formatDuration(response?.total_time_ms ?? null)}
                  {response?.first_byte_delay_ms ? ` / ${formatDuration(response.first_byte_delay_ms)}` : ''}
                </div>
              </div>
              <div className="rounded-lg border bg-muted/30 px-3 py-2 sm:col-span-2">
                <div className="text-xs text-muted-foreground">{t('detail.traceId')}</div>
                <div className="mt-1 break-all font-mono text-sm">{response?.trace_id ?? '-'}</div>
              </div>
            </div>

            {requestError ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {requestError}
              </div>
            ) : null}

            {running && !streamContent && !response ? (
              <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                <span>{t('playground.running')}</span>
              </div>
            ) : isStreamResult ? (
              <StreamJsonViewer
                data={streamContent || response?.response_body || ''}
                maxHeight="60vh"
              />
            ) : response ? (
              <JsonViewer data={response.response_body ?? {}} maxHeight="60vh" />
            ) : (
              <div className="flex min-h-[360px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                {t('playground.emptyResponse')}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={Boolean(editorState)} onOpenChange={(open) => !open && setEditorState(null)}>
        <DialogContent className="sm:max-w-[840px]">
          <DialogHeader>
            <DialogTitle>{t('playground.editorTitle')}</DialogTitle>
            <DialogDescription>
              {editorState ? t('playground.editorDescription', { field: editorState.label }) : ''}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2">
            <Label>{t('playground.editorContent')}</Label>
            <Textarea
              value={editorValue}
              onChange={(event) => setEditorValue(event.target.value)}
              className="min-h-[360px] font-mono text-xs leading-6"
              spellCheck={false}
            />
            <div className="text-xs text-muted-foreground">
              {editorMode === 'text' ? 'Text mode' : 'JSON mode'}
            </div>
            {editorError ? (
              <div className="text-sm text-destructive">{editorError}</div>
            ) : null}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setEditorState(null)}>
              {tCommon('cancel')}
            </Button>
            <Button type="button" onClick={handleApplyEditor}>
              {tCommon('confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
