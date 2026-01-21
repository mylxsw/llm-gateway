/**
 * Provider Related Type Definitions
 * Corresponds to backend service_providers table
 */

/** Protocol Type */
export type ProtocolType = 'openai' | 'anthropic';

/** Provider Entity */
export interface Provider {
  id: number;
  name: string;
  base_url: string;
  protocol: ProtocolType;
  api_key?: string;          // Sanitized display
  extra_headers?: Record<string, string>;
  proxy_enabled?: boolean;
  proxy_url?: string; // Sanitized display
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Create Provider Request */
export interface ProviderCreate {
  name: string;
  base_url: string;
  protocol: ProtocolType;
  api_key?: string;
  extra_headers?: Record<string, string>;
  proxy_enabled?: boolean;
  proxy_url?: string;
  is_active?: boolean;
}

/** Update Provider Request */
export interface ProviderUpdate {
  name?: string;
  base_url?: string;
  protocol?: ProtocolType;
  api_key?: string;
  extra_headers?: Record<string, string>;
  proxy_enabled?: boolean;
  proxy_url?: string;
  is_active?: boolean;
}

/** Provider List Query Params */
export interface ProviderListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
  name?: string;
  protocol?: string;
}

/** Provider Export Entity (includes API key) */
export type ProviderExport = ProviderCreate;
