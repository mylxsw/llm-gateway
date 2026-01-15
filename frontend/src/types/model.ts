/**
 * Model Mapping Related Type Definitions
 * Corresponds to backend model_mappings and model_mapping_providers tables
 */

import { RuleSet } from './common';
import { ProtocolType } from './provider';

/** Model Mapping Entity */
export interface ModelMapping {
  requested_model: string;            // Primary Key
  strategy: string;                   // Strategy, default round_robin
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
  priority: number;
  weight: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Create Model Mapping Request */
export interface ModelMappingCreate {
  requested_model: string;
  strategy?: string;
  matching_rules?: RuleSet;
  capabilities?: Record<string, unknown>;
  is_active?: boolean;
  input_price?: number | null;
  output_price?: number | null;
}

/** Update Model Mapping Request */
export interface ModelMappingUpdate {
  strategy?: string;
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
  priority?: number;
  weight?: number;
  is_active?: boolean;
}

/** Model Export Entity */
export interface ModelExport extends ModelMappingCreate {
  providers?: ModelProviderExport[];
}
