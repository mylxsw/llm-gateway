/**
 * Utility Functions Collection
 * Includes common functions like class name merging, formatting, etc.
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Normalize backend UTC timestamps for browser parsing.
 *
 * Backend contract is UTC for storage/transfer. If a timestamp string is missing an explicit
 * timezone offset (e.g. `2026-01-15T12:00:00`), treat it as UTC and append `Z`.
 */
export function normalizeUtcDateString(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;

  // Already has timezone info.
  if (/[zZ]$/.test(trimmed) || /[+-]\d{2}:?\d{2}$/.test(trimmed)) return trimmed;

  // ISO-like without offset: treat as UTC.
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(trimmed)) {
    return `${trimmed}Z`;
  }

  // SQLite-like `YYYY-MM-DD HH:mm:ss(.sss)` without offset: treat as UTC.
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(trimmed)) {
    return `${trimmed.replace(' ', 'T')}Z`;
  }

  return trimmed;
}

/**
 * Merge Tailwind CSS class names
 * Uses clsx for conditional classes and twMerge for handling conflicts
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format Date Time
 * @param dateString - ISO 8601 date string
 * @param options - Formatting options
 */
export function formatDateTime(
  dateString: string | null | undefined,
  options?: {
    showTime?: boolean;
    showSeconds?: boolean;
  }
): string {
  if (!dateString) return '-';
  
  const date = new Date(normalizeUtcDateString(dateString));
  if (Number.isNaN(date.getTime())) return '-';
  const { showTime = true, showSeconds = false } = options || {};
  
  const dateOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  };
  
  if (showTime) {
    dateOptions.hour = '2-digit';
    dateOptions.minute = '2-digit';
    if (showSeconds) {
      dateOptions.second = '2-digit';
    }
  }
  
  // Use the user's current locale + timezone (browser runtime defaults).
  return date.toLocaleString(undefined, dateOptions);
}

/**
 * Format milliseconds to readable duration
 * @param ms - milliseconds
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  
  if (ms < 1000) {
    return `${Number(ms.toFixed(2))}ms`;
  } else if (ms < 60000) {
    return `${Number((ms / 1000).toFixed(2))}s`;
  } else {
    const minutes = Math.floor(ms / 60000);
    const seconds = ((ms % 60000) / 1000).toFixed(0);
    return `${minutes}m ${seconds}s`;
  }
}

/**
 * Format number with thousand separators
 */
export function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '-';
  return num.toLocaleString(undefined);
}

/**
 * Format USD cost with 4 decimals
 */
export function formatUsd(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return '$0.0000';
  const num = Number(cost);
  if (Number.isNaN(num)) return '$0.0000';
  return `$${num.toFixed(4)}`;
}

/**
 * Format USD cost with 2 decimals
 */
export function formatUsdCompact(cost: number | null | undefined): string {
  if (cost === null || cost === undefined) return '$0.00';
  const num = Number(cost);
  if (Number.isNaN(num)) return '$0.00';
  return `$${num.toFixed(2)}`;
}

/**
 * Truncate string
 * @param str - Original string
 * @param maxLength - Maximum length
 */
export function truncate(
  str: string | null | undefined,
  maxLength: number = 50
): string {
  if (!str) return '-';
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength)}...`;
}

/**
 * Copy text to clipboard
 * @param text - Text to copy
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get color class name for status code
 */
export function getStatusColor(status: number | null | undefined): string {
  if (status === null || status === undefined) return 'text-muted-foreground';
  if (status >= 200 && status < 300) return 'text-green-600 dark:text-green-400';
  if (status >= 400 && status < 500) return 'text-yellow-600 dark:text-yellow-400';
  if (status >= 500) return 'text-red-600 dark:text-red-400';
  return 'text-muted-foreground';
}

/**
 * Get display text and color for boolean active status
 */
export function getActiveStatus(isActive: boolean): {
  text: string;
  className: string;
} {
  return isActive
    ? { text: 'Active', className: 'border-transparent bg-green-500/15 text-green-700 dark:text-green-300' }
    : { text: 'Inactive', className: 'bg-muted text-muted-foreground' };
}
