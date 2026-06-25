/**
 * Prompt View Component
 *
 * Parses an LLM request body (OpenAI or Anthropic format) and renders the
 * conversation in a friendly, chat-like layout: system prompt, messages with
 * role badges, inline tool calls / tool results, the list of tool/function
 * definitions, and the request parameters.
 *
 * Message text is rendered as plain text (whitespace preserved); only tool
 * schemas use the JSON viewer.
 */

"use client";

import React, { useMemo, useState } from "react";
import {
  AlertCircle,
  Bot,
  ChevronDown,
  ChevronRight,
  Settings2,
  Terminal,
  User,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { JsonViewer } from "@/components/common";
import { useTranslations } from "next-intl";

// ---------------------------------------------------------------------------
// Unified display model
// ---------------------------------------------------------------------------

type PromptRole = "system" | "user" | "assistant" | "tool";

type PromptPart =
  | { kind: "text"; text: string }
  | { kind: "image"; url: string }
  | { kind: "tool_call"; id?: string; name: string; argsText: string }
  | { kind: "tool_result"; toolCallId?: string; text: string; isError?: boolean };

interface PromptMessage {
  role: PromptRole;
  parts: PromptPart[];
}

interface PromptToolDef {
  name: string;
  description?: string;
  schema?: unknown;
}

interface PromptParam {
  key: string;
  value: string;
}

interface PromptModel {
  system: string | null;
  messages: PromptMessage[];
  tools: PromptToolDef[];
  params: PromptParam[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRecord = Record<string, any>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isObject(value: unknown): value is AnyRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Lightweight guard: true only when body looks like a chat request. */
export function hasPromptContent(
  body: unknown,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _protocol?: string,
): boolean {
  return isObject(body) && Array.isArray(body.messages);
}

/** Pretty-print a value as JSON, falling back to String() on failure. */
function prettyJson(value: unknown): string {
  if (typeof value === "string") {
    // Tool-call arguments often arrive as a JSON string; re-indent if possible.
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** Detect the request protocol, preferring the explicit hint. */
function detectProtocol(body: AnyRecord, protocol?: string): "openai" | "anthropic" {
  const hint = protocol?.toLowerCase();
  if (hint === "anthropic") return "anthropic";
  if (hint === "openai") return "openai";

  // Fall back to body shape.
  if (typeof body.system === "string" || Array.isArray(body.system)) {
    return "anthropic";
  }
  if (Array.isArray(body.tools)) {
    const first = body.tools[0];
    if (isObject(first) && (first.input_schema || (!first.function && first.name))) {
      return "anthropic";
    }
  }
  return "openai";
}

/** Flatten an Anthropic-style text/system value into a string. */
function flattenAnthropicText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value
      .map((part) => {
        if (typeof part === "string") return part;
        if (isObject(part) && typeof part.text === "string") return part.text;
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (isObject(value) && typeof value.text === "string") return value.text;
  return "";
}

// ---------------------------------------------------------------------------
// Normalizers
// ---------------------------------------------------------------------------

const RESERVED_PARAM_KEYS = new Set(["messages", "system", "tools", "tool_choice"]);

function extractParams(body: AnyRecord): PromptParam[] {
  const params: PromptParam[] = [];
  for (const [key, value] of Object.entries(body)) {
    if (RESERVED_PARAM_KEYS.has(key)) continue;
    if (
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      params.push({ key, value: String(value) });
    }
  }
  return params;
}

function normalizeOpenAI(body: AnyRecord): PromptModel {
  let system: string | null = null;
  const messages: PromptMessage[] = [];

  for (const raw of body.messages as unknown[]) {
    if (!isObject(raw)) continue;
    const role = String(raw.role || "");

    if (role === "system") {
      const text = flattenAnthropicText(raw.content);
      system = system ? `${system}\n${text}` : text;
      continue;
    }

    const parts: PromptPart[] = [];

    if (role === "tool") {
      parts.push({
        kind: "tool_result",
        toolCallId: typeof raw.tool_call_id === "string" ? raw.tool_call_id : undefined,
        text: flattenAnthropicText(raw.content),
      });
    } else {
      // text content
      if (typeof raw.content === "string") {
        if (raw.content) parts.push({ kind: "text", text: raw.content });
      } else if (Array.isArray(raw.content)) {
        for (const part of raw.content) {
          if (!isObject(part)) continue;
          if (part.type === "text" && typeof part.text === "string") {
            parts.push({ kind: "text", text: part.text });
          } else if (part.type === "image_url") {
            const url = isObject(part.image_url) ? String(part.image_url.url || "") : "";
            parts.push({ kind: "image", url });
          }
        }
      }

      // assistant tool calls
      if (Array.isArray(raw.tool_calls)) {
        for (const call of raw.tool_calls) {
          if (!isObject(call)) continue;
          const fn = isObject(call.function) ? call.function : {};
          parts.push({
            kind: "tool_call",
            id: typeof call.id === "string" ? call.id : undefined,
            name: String(fn.name || ""),
            argsText: prettyJson(fn.arguments ?? {}),
          });
        }
      }
    }

    messages.push({ role: normalizeRole(role), parts });
  }

  const tools: PromptToolDef[] = [];
  if (Array.isArray(body.tools)) {
    for (const tool of body.tools) {
      if (!isObject(tool)) continue;
      const fn = isObject(tool.function) ? tool.function : tool;
      tools.push({
        name: String(fn.name || ""),
        description: typeof fn.description === "string" ? fn.description : undefined,
        schema: fn.parameters,
      });
    }
  }

  return { system, messages, tools, params: extractParams(body) };
}

function normalizeAnthropic(body: AnyRecord): PromptModel {
  const system = body.system != null ? flattenAnthropicText(body.system) : null;
  const messages: PromptMessage[] = [];

  for (const raw of body.messages as unknown[]) {
    if (!isObject(raw)) continue;
    const role = String(raw.role || "");
    const parts: PromptPart[] = [];

    if (typeof raw.content === "string") {
      if (raw.content) parts.push({ kind: "text", text: raw.content });
    } else if (Array.isArray(raw.content)) {
      for (const part of raw.content) {
        if (!isObject(part)) continue;
        switch (part.type) {
          case "text":
            if (typeof part.text === "string") {
              parts.push({ kind: "text", text: part.text });
            }
            break;
          case "tool_use":
            parts.push({
              kind: "tool_call",
              id: typeof part.id === "string" ? part.id : undefined,
              name: String(part.name || ""),
              argsText: prettyJson(part.input ?? {}),
            });
            break;
          case "tool_result":
            parts.push({
              kind: "tool_result",
              toolCallId:
                typeof part.tool_use_id === "string" ? part.tool_use_id : undefined,
              text: flattenAnthropicText(part.content),
              isError: part.is_error === true,
            });
            break;
          case "image":
            parts.push({ kind: "image", url: anthropicImageUrl(part) });
            break;
          default:
            break;
        }
      }
    }

    messages.push({ role: normalizeRole(role), parts });
  }

  const tools: PromptToolDef[] = [];
  if (Array.isArray(body.tools)) {
    for (const tool of body.tools) {
      if (!isObject(tool)) continue;
      tools.push({
        name: String(tool.name || ""),
        description: typeof tool.description === "string" ? tool.description : undefined,
        schema: tool.input_schema,
      });
    }
  }

  return { system, messages, tools, params: extractParams(body) };
}

function anthropicImageUrl(part: AnyRecord): string {
  const source = isObject(part.source) ? part.source : {};
  if (typeof source.url === "string") return source.url;
  if (typeof source.media_type === "string") return `[${source.media_type}]`;
  return "";
}

function normalizeRole(role: string): PromptRole {
  if (role === "system" || role === "user" || role === "assistant" || role === "tool") {
    return role;
  }
  return "user";
}

/** Normalize either protocol into a unified model. Returns null on bad input. */
export function parsePromptRequest(
  body: unknown,
  protocol?: string,
): PromptModel | null {
  if (!hasPromptContent(body, protocol) || !isObject(body)) return null;
  try {
    const proto = detectProtocol(body, protocol);
    return proto === "anthropic" ? normalizeAnthropic(body) : normalizeOpenAI(body);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Presentation
// ---------------------------------------------------------------------------

const ROLE_META: Record<
  PromptRole,
  { icon: LucideIcon; variant: BadgeProps["variant"] }
> = {
  system: { icon: Settings2, variant: "outline" },
  user: { icon: User, variant: "secondary" },
  assistant: { icon: Bot, variant: "default" },
  tool: { icon: Wrench, variant: "warning" },
};

function SectionLabel({
  icon: Icon,
  children,
}: {
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-sm font-medium">
      <Icon className="h-4 w-4 text-muted-foreground" suppressHydrationWarning />
      <span>{children}</span>
    </div>
  );
}

function PreText({ text }: { text: string }) {
  return (
    <p className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
      {text}
    </p>
  );
}

function SystemSection({ text }: { text: string }) {
  const t = useTranslations("logs");
  return (
    <div className="space-y-2">
      <SectionLabel icon={Settings2}>{t("detail.prompt.system")}</SectionLabel>
      <div className="rounded-lg border bg-muted/30 p-3">
        <PreText text={text} />
      </div>
    </div>
  );
}

function ParametersSection({ params }: { params: PromptParam[] }) {
  const t = useTranslations("logs");
  if (params.length === 0) return null;
  return (
    <div className="space-y-2">
      <SectionLabel icon={Terminal}>{t("detail.prompt.parameters")}</SectionLabel>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border bg-muted/30 p-3 sm:grid-cols-3 lg:grid-cols-4">
        {params.map((param) => (
          <div key={param.key} className="flex items-center justify-between gap-2 text-xs">
            <span className="truncate text-muted-foreground">{param.key}</span>
            <span className="truncate font-mono font-medium" title={param.value}>
              {param.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ToolCallBlock({ part }: { part: Extract<PromptPart, { kind: "tool_call" }> }) {
  const t = useTranslations("logs");
  return (
    <div className="rounded-md border border-dashed bg-background p-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="gap-1 font-mono">
          <Wrench className="h-3 w-3" suppressHydrationWarning />
          {t("detail.prompt.toolCall")}
        </Badge>
        <code className="font-mono text-xs font-semibold">{part.name}</code>
        {part.id && (
          <span className="font-mono text-[10px] text-muted-foreground">{part.id}</span>
        )}
      </div>
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-muted/40 p-2 font-mono text-xs">
        {part.argsText}
      </pre>
    </div>
  );
}

function ToolResultBlock({
  part,
}: {
  part: Extract<PromptPart, { kind: "tool_result" }>;
}) {
  const t = useTranslations("logs");
  return (
    <div
      className={`rounded-md border bg-background p-2 ${
        part.isError ? "border-red-300 dark:border-red-900" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={part.isError ? "error" : "outline"} className="font-mono">
          {t("detail.prompt.toolResult")}
        </Badge>
        {part.toolCallId && (
          <span className="font-mono text-[10px] text-muted-foreground">
            {part.toolCallId}
          </span>
        )}
      </div>
      {part.text && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-muted/40 p-2 font-mono text-xs">
          {part.text}
        </pre>
      )}
    </div>
  );
}

function MessagePart({ part }: { part: PromptPart }) {
  const t = useTranslations("logs");
  switch (part.kind) {
    case "text":
      return <PreText text={part.text} />;
    case "image":
      return (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">{t("detail.prompt.image")}</Badge>
          {part.url && <code className="truncate font-mono">{part.url}</code>}
        </div>
      );
    case "tool_call":
      return <ToolCallBlock part={part} />;
    case "tool_result":
      return <ToolResultBlock part={part} />;
    default:
      return null;
  }
}

function MessageCard({ message }: { message: PromptMessage }) {
  const t = useTranslations("logs");
  const meta = ROLE_META[message.role];
  const Icon = meta.icon;
  return (
    <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted-foreground" suppressHydrationWarning />
        <Badge variant={meta.variant}>{t(`detail.prompt.role.${message.role}`)}</Badge>
      </div>
      {message.parts.length > 0 ? (
        <div className="space-y-2">
          {message.parts.map((part, index) => (
            <MessagePart key={index} part={part} />
          ))}
        </div>
      ) : (
        <p className="text-xs italic text-muted-foreground">—</p>
      )}
    </div>
  );
}

function ToolDefinitionItem({ tool }: { tool: PromptToolDef }) {
  const t = useTranslations("logs");
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-md border bg-background">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/40"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" suppressHydrationWarning />
        ) : (
          <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" suppressHydrationWarning />
        )}
        <div className="min-w-0 flex-1">
          <code className="font-mono text-xs font-semibold">{tool.name}</code>
          {tool.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
              {tool.description}
            </p>
          )}
        </div>
      </button>
      {expanded && (
        <div className="border-t p-3">
          {tool.description && (
            <p className="mb-3 whitespace-pre-wrap break-words text-xs text-muted-foreground">
              {tool.description}
            </p>
          )}
          {tool.schema != null ? (
            <JsonViewer
              data={tool.schema}
              defaultRawView
              defaultWrapLines
              maxHeight="40vh"
            />
          ) : (
            <p className="text-xs italic text-muted-foreground">
              {t("detail.prompt.schema")}: —
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ToolsSection({ tools }: { tools: PromptToolDef[] }) {
  const t = useTranslations("logs");
  const [expanded, setExpanded] = useState(true);
  if (tools.length === 0) return null;
  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-sm font-medium"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" suppressHydrationWarning />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" suppressHydrationWarning />
        )}
        <Wrench className="h-4 w-4 text-muted-foreground" suppressHydrationWarning />
        <span>{t("detail.prompt.tools")}</span>
        <Badge variant="secondary">{t("detail.prompt.toolsCount", { count: tools.length })}</Badge>
      </button>
      {expanded && (
        <div className="space-y-2">
          {tools.map((tool, index) => (
            <ToolDefinitionItem key={`${tool.name}-${index}`} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}

interface PromptViewProps {
  body: unknown;
  protocol?: string;
}

export function PromptView({ body, protocol }: PromptViewProps) {
  const t = useTranslations("logs");
  const model = useMemo(() => parsePromptRequest(body, protocol), [body, protocol]);

  if (!model) {
    return (
      <div className="flex items-center gap-2 rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
        <AlertCircle className="h-4 w-4" suppressHydrationWarning />
        <span>{t("detail.prompt.empty")}</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {model.system && <SystemSection text={model.system} />}

      <ParametersSection params={model.params} />

      <div className="space-y-2">
        <SectionLabel icon={Bot}>{t("detail.prompt.messages")}</SectionLabel>
        <div className="space-y-3">
          {model.messages.map((message, index) => (
            <MessageCard key={index} message={message} />
          ))}
        </div>
      </div>

      <ToolsSection tools={model.tools} />
    </div>
  );
}
