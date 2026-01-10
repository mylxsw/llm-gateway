/**
 * 表单验证工具
 */

/**
 * 验证 URL 格式
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * 验证非空字符串
 */
export function isNotEmpty(value: string | null | undefined): boolean {
  return value !== null && value !== undefined && value.trim().length > 0;
}

/**
 * 验证模型名格式（字母、数字、下划线、短横线、点）
 */
export function isValidModelName(name: string): boolean {
  return /^[a-zA-Z0-9_\-\.]+$/.test(name);
}

/**
 * 验证 API Key 名称（允许中文、字母、数字、下划线、短横线、空格）
 */
export function isValidKeyName(name: string): boolean {
  return /^[\u4e00-\u9fa5a-zA-Z0-9_\- ]+$/.test(name) && name.trim().length > 0;
}
