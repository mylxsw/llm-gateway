/**
 * Utility Functions Collection
 * Includes common functions like class name merging, formatting, etc.
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

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
  
  const date = new Date(dateString);
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
  
  return date.toLocaleString('en-US', dateOptions);
}

/**
 * Format milliseconds to readable duration
 * @param ms - milliseconds
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  
  if (ms < 1000) {
    return `${ms}ms`;
  } else if (ms < 60000) {
    return `${(ms / 1000).toFixed(2)}s`;
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
  return num.toLocaleString('en-US');
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
  if (status === null || status === undefined) return 'text-gray-500';
  if (status >= 200 && status < 300) return 'text-green-600';
  if (status >= 400 && status < 500) return 'text-yellow-600';
  if (status >= 500) return 'text-red-600';
  return 'text-gray-500';
}

/**
 * Get display text and color for boolean active status
 */
export function getActiveStatus(isActive: boolean): {
  text: string;
  className: string;
} {
  return isActive
    ? { text: 'Active', className: 'bg-green-100 text-green-800' }
    : { text: 'Inactive', className: 'bg-gray-100 text-gray-800' };
}