/**
 * 工具函数集合
 * 包含样式合并、格式化等通用函数
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind CSS 类名
 * 使用 clsx 处理条件类名，twMerge 处理冲突
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 格式化日期时间
 * @param dateString - ISO 8601 格式的日期字符串
 * @param options - 格式化选项
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
  
  return date.toLocaleString('zh-CN', dateOptions);
}

/**
 * 格式化毫秒为可读时间
 * @param ms - 毫秒数
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
 * 格式化数字，添加千分位
 */
export function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '-';
  return num.toLocaleString('zh-CN');
}

/**
 * 截断字符串
 * @param str - 原字符串
 * @param maxLength - 最大长度
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
 * 复制文本到剪贴板
 * @param text - 要复制的文本
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
 * 获取状态码对应的颜色类名
 */
export function getStatusColor(status: number | null | undefined): string {
  if (status === null || status === undefined) return 'text-gray-500';
  if (status >= 200 && status < 300) return 'text-green-600';
  if (status >= 400 && status < 500) return 'text-yellow-600';
  if (status >= 500) return 'text-red-600';
  return 'text-gray-500';
}

/**
 * 获取布尔状态对应的显示文本和颜色
 */
export function getActiveStatus(isActive: boolean): {
  text: string;
  className: string;
} {
  return isActive
    ? { text: '启用', className: 'bg-green-100 text-green-800' }
    : { text: '禁用', className: 'bg-gray-100 text-gray-800' };
}
