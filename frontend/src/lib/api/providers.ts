/**
 * Provider API
 * Corresponds to backend /api/admin/providers route
 */

import { get, post, put, del } from './client';
import {
  Provider,
  ProviderCreate,
  ProviderUpdate,
  ProviderListParams,
  PaginatedResponse,
} from '@/types';

const BASE_URL = '/api/admin/providers';

/**
 * Get Provider List
 * @param params - Query parameters (pagination, status filtering)
 */
export async function getProviders(
  params?: ProviderListParams
): Promise<PaginatedResponse<Provider>> {
  return get<PaginatedResponse<Provider>>(BASE_URL, params as Record<string, unknown>);
}

/**
 * Get Single Provider Details
 * @param id - Provider ID
 */
export async function getProvider(id: number): Promise<Provider> {
  return get<Provider>(`${BASE_URL}/${id}`);
}

/**
 * Create Provider
 * @param data - Creation data
 */
export async function createProvider(data: ProviderCreate): Promise<Provider> {
  return post<Provider>(BASE_URL, data);
}

/**
 * Update Provider
 * @param id - Provider ID
 * @param data - Update data
 */
export async function updateProvider(
  id: number,
  data: ProviderUpdate
): Promise<Provider> {
  return put<Provider>(`${BASE_URL}/${id}`, data);
}

/**
 * Delete Provider
 * @param id - Provider ID
 */
export async function deleteProvider(id: number): Promise<void> {
  return del<void>(`${BASE_URL}/${id}`);
}

/**
 * Export Providers
 */
export async function exportProviders(): Promise<any[]> {
  return get<any[]>(`${BASE_URL}/export`);
}

/**
 * Import Providers
 * @param data - List of providers to import
 */
export async function importProviders(data: any[]): Promise<{success: number; skipped: number}> {
  return post<{success: number; skipped: number}>(`${BASE_URL}/import`, data);
}
