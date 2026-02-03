/**
 * Query string helpers for list state persistence.
 */

export function parseNumberParam(
  value: string | null,
  options?: { min?: number; max?: number }
): number | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  const num = Number(value);
  if (!Number.isFinite(num)) return undefined;
  if (options?.min !== undefined && num < options.min) return undefined;
  if (options?.max !== undefined && num > options.max) return undefined;
  return num;
}

export function parseStringParam(value: string | null): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

export function parseBooleanParam(value: string | null): boolean | undefined {
  if (value === 'true') return true;
  if (value === 'false') return false;
  return undefined;
}

export function setParam(
  params: URLSearchParams,
  key: string,
  value: string | number | boolean | null | undefined
) {
  if (value === undefined || value === null || value === '') {
    params.delete(key);
    return;
  }
  params.set(key, String(value));
}

export function normalizeReturnTo(raw: string | null, fallback = '/'): string {
  if (!raw) return fallback;
  if (raw.startsWith('/') && !raw.startsWith('//')) return raw;
  return fallback;
}
