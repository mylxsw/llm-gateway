/**
 * Model Mapping Related Type Definitions
 * Corresponds to backend model_mappings and model_mapping_providers tables
 */

import { RuleSet } from './common';
import { ProtocolType } from './provider';

/** Selection Strategy Type */
export type SelectionStrategy = 'round_robin' | 'cost_first';

/** Model Mapping Entity */
export interface ModelMapping {
  requested_model: string;            // Primary Key
  strategy: SelectionStrategy;        // Selection strategy
  matching_rules?: RuleSet | null;    // Model level rules
  capabilities?: Record<string, unknown>; // Capabilities description
  is_active: boolean;
  // Pricing (USD per 1,000,000 tokens)
  input_price?: number | null;
  output_price?: number | null;
  provider_count?: number;            // Associated provider count
  providers?: ModelMappingProvider[]; // Detail contains provider list
  created_at: string;
  updated_at: string;
}

/** Model-Provider Mapping Entity */
export interface ModelMappingProvider {
  id: number;
  requested_model: string;
  provider_id: number;
  provider_name: string;              // Obtained via join
  provider_protocol?: ProtocolType | null; // Obtained via join
  target_model_name: string;          // Target model name for this provider
  provider_rules?: RuleSet | null;    // Provider level rules
  // Provider override pricing (USD per 1,000,000 tokens)
  input_price?: number | null;
  output_price?: number | null;
  // Billing mode: token_flat / token_tiered / per_request
  billing_mode?: 'token_flat' | 'token_tiered' | 'per_request' | null;
  // Per-request fixed price (USD), used when billing_mode == per_request
  per_request_price?: number | null;
  // Tiered pricing config, used when billing_mode == token_tiered
  tiered_pricing?: Array<{
    max_input_tokens?: number | null;
    input_price: number;
    output_price: number;
  }> | null;
  priority: number;
  weight: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Create Model Mapping Request */
export interface ModelMappingCreate {
  requested_model: string;
  strategy?: SelectionStrategy;
  matching_rules?: RuleSet;
  capabilities?: Record<string, unknown>;
  is_active?: boolean;
  input_price?: number | null;
  output_price?: number | null;
}

/** Update Model Mapping Request */
export interface ModelMappingUpdate {
  strategy?: SelectionStrategy;
  matching_rules?: RuleSet | null;
  capabilities?: Record<string, unknown>;
  is_active?: boolean;
  input_price?: number | null;
  output_price?: number | null;
}

/** Create Model-Provider Mapping Request */
export interface ModelMappingProviderCreate {
  requested_model: string;
  provider_id: number;
  target_model_name: string;
  provider_rules?: RuleSet;
  input_price?: number | null;
  output_price?: number | null;
  billing_mode?: 'token_flat' | 'token_tiered' | 'per_request';
  per_request_price?: number | null;
  tiered_pricing?: Array<{
    max_input_tokens?: number | null;
    input_price: number;
    output_price: number;
  }> | null;
  priority?: number;
  weight?: number;
  is_active?: boolean;
}

/** Update Model-Provider Mapping Request */
export interface ModelMappingProviderUpdate {
  target_model_name?: string;
  provider_rules?: RuleSet | null;
  input_price?: number | null;
  output_price?: number | null;
  billing_mode?: 'token_flat' | 'token_tiered' | 'per_request' | null;
  per_request_price?: number | null;
  tiered_pricing?: Array<{
    max_input_tokens?: number | null;
    input_price: number;
    output_price: number;
  }> | null;
  priority?: number;
  weight?: number;
  is_active?: boolean;
}

/** Model Mapping List Query Params */
export interface ModelListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

/** Model-Provider Mapping List Query Params */
export interface ModelProviderListParams {
  requested_model?: string;
  provider_id?: number;
  is_active?: boolean;
}

/** Model Provider Export Entity */
export interface ModelProviderExport {
  provider_name: string;
  target_model_name: string;
  provider_rules?: RuleSet | null;
  input_price?: number | null;
  output_price?: number | null;
  billing_mode?: 'token_flat' | 'token_tiered' | 'per_request' | null;
  per_request_price?: number | null;
  tiered_pricing?: Array<{
    max_input_tokens?: number | null;
    input_price: number;
    output_price: number;
  }> | null;
  priority?: number;
  weight?: number;
  is_active?: boolean;
}

/** Model Export Entity */
export interface ModelExport extends ModelMappingCreate {
  providers?: ModelProviderExport[];
}
