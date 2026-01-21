/**
 * Form Validation Utilities
 */

/**
 * Validate URL format
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
 * Validate non-empty string
 */
export function isNotEmpty(value: string | null | undefined): boolean {
  return value !== null && value !== undefined && value.trim().length > 0;
}

/**
 * Validate model name format (letters, numbers, underscores, hyphens, dots, slashes)
 */
export function isValidModelName(name: string): boolean {
  return /^[a-zA-Z0-9_\-\.\/]+$/.test(name);
}

/**
 * Validate API Key name (allows Chinese, letters, numbers, underscores, hyphens, spaces)
 */
export function isValidKeyName(name: string): boolean {
  // Keeping chinese support in regex as user requested translation of content/UI, 
  // but functionality logic should arguably support international characters if original did.
  // However, prompts say "standard written English". 
  // I will update regex comments to reflect capabilities, but functionality remains permissive.
  return /^[\u4e00-\u9fa5a-zA-Z0-9_\- ]+$/.test(name) && name.trim().length > 0;
}
