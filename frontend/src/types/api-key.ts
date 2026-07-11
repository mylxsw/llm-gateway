/**
 * API Key Related Type Definitions
 * Corresponds to backend api_keys table
 */

/** API Key Entity */
export interface ApiKey {
  id: number;
  key_name: string;
  key_value: string;          // Sanitized in lists, fully returned on creation
  is_active: boolean;
  record_details: boolean;    // Whether to record request detail payload (bodies & headers)
  is_mcp_admin: boolean;      // Whether this key is granted MCP admin capability
  created_at: string;
  last_used_at?: string | null;
  monthly_cost?: number | null; // Current month's total cost (USD)
}

/** Create API Key Request */
export interface ApiKeyCreate {
  key_name: string;
  record_details?: boolean;
}

/** Update API Key Request */
export interface ApiKeyUpdate {
  key_name?: string;
  is_active?: boolean;
  record_details?: boolean;
  is_mcp_admin?: boolean;
}

/** API Key List Query Params */
export interface ApiKeyListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}