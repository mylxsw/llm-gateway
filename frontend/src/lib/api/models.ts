/**
 * Model Mapping API
 * Corresponds to backend /api/admin/models and /api/admin/model-providers routes
 */

import { get, post, put, del } from './client';
import {
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  ModelListParams,
  ModelProviderListParams,
  ModelExport,
  ModelStats,
  ModelProviderStats,
  ModelMatchRequest,
  ModelMatchProvider,
  PaginatedResponse,
} from '@/types';

const MODELS_URL = '/api/admin/models';
const MODEL_PROVIDERS_URL = '/api/admin/model-providers';
const MODEL_STATS_URL = '/api/admin/models/stats';
const MODEL_PROVIDER_STATS_URL = '/api/admin/models/provider-stats';

// ============ Model Mapping CRUD ============

/**
 * Get Model Mapping List
 * @param params - Query parameters
 */
export async function getModels(
  params?: ModelListParams
): Promise<PaginatedResponse<ModelMapping>> {
  return get<PaginatedResponse<ModelMapping>>(MODELS_URL, params as Record<string, unknown>);
}

/**
 * Get Single Model Mapping Details (including provider configurations)
 * @param requestedModel - Requested model name
 */
export async function getModel(requestedModel: string): Promise<ModelMapping> {
  return get<ModelMapping>(`${MODELS_URL}/${encodeURIComponent(requestedModel)}`);
}

/**
 * Create Model Mapping
 * @param data - Creation data
 */
export async function createModel(data: ModelMappingCreate): Promise<ModelMapping> {
  return post<ModelMapping>(MODELS_URL, data);
}

/**
 * Update Model Mapping
 * @param requestedModel - Requested model name
 * @param data - Update data
 */
export async function updateModel(
  requestedModel: string,
  data: ModelMappingUpdate
): Promise<ModelMapping> {
  return put<ModelMapping>(`${MODELS_URL}/${encodeURIComponent(requestedModel)}`, data);
}

/**
 * Delete Model Mapping (Cascades delete associated provider configurations)
 * @param requestedModel - Requested model name
 */
export async function deleteModel(requestedModel: string): Promise<void> {
  return del<void>(`${MODELS_URL}/${encodeURIComponent(requestedModel)}`);
}

// ============ Model-Provider Mapping CRUD ============

/**
 * Get Model-Provider Mapping List
 * @param params - Query parameters
 */
export async function getModelProviders(
  params?: ModelProviderListParams
): Promise<{ items: ModelMappingProvider[]; total: number }> {
  return get<{ items: ModelMappingProvider[]; total: number }>(
    MODEL_PROVIDERS_URL,
    params as Record<string, unknown>
  );
}

/**
 * Create Model-Provider Mapping
 * @param data - Creation data
 */
export async function createModelProvider(
  data: ModelMappingProviderCreate
): Promise<ModelMappingProvider> {
  return post<ModelMappingProvider>(MODEL_PROVIDERS_URL, data);
}

/**
 * Update Model-Provider Mapping
 * @param id - Mapping ID
 * @param data - Update data
 */
export async function updateModelProvider(
  id: number,
  data: ModelMappingProviderUpdate
): Promise<ModelMappingProvider> {
  return put<ModelMappingProvider>(`${MODEL_PROVIDERS_URL}/${id}`, data);
}

/**
 * Delete Model-Provider Mapping
 * @param id - Mapping ID
 */
export async function deleteModelProvider(id: number): Promise<void> {
  return del<void>(`${MODEL_PROVIDERS_URL}/${id}`);
}

/**
 * Export Models
 */
export async function exportModels(): Promise<ModelExport[]> {
  return get<ModelExport[]>(`${MODELS_URL}/export`);
}

/**
 * Import Models
 * @param data - List of models to import
 */
export async function importModels(
  data: ModelExport[]
): Promise<{ success: number; skipped: number; errors: string[] }> {
  return post<{success: number; skipped: number; errors: string[]}>(`${MODELS_URL}/import`, data);
}

export async function getModelStats(
  params?: { requested_model?: string }
): Promise<ModelStats[]> {
  return get<ModelStats[]>(MODEL_STATS_URL, params as Record<string, unknown>);
}

export async function getModelProviderStats(
  params?: { requested_model?: string }
): Promise<ModelProviderStats[]> {
  return get<ModelProviderStats[]>(MODEL_PROVIDER_STATS_URL, params as Record<string, unknown>);
}

export async function matchModelProviders(
  requestedModel: string,
  data: ModelMatchRequest
): Promise<ModelMatchProvider[]> {
  return post<ModelMatchProvider[]>(
    `${MODELS_URL}/${encodeURIComponent(requestedModel)}/match`,
    data
  );
}
