/**
 * Model Mapping Related React Query Hooks
 * Provides data fetching, caching and state management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  getModels,
  getModel,
  createModel,
  updateModel,
  deleteModel,
  getModelProviders,
  createModelProvider,
  updateModelProvider,
  deleteModelProvider,
  getModelStats,
  getModelProviderStats,
} from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api/error';
import {
  ModelMapping,
  ModelMappingCreate,
  ModelMappingUpdate,
  ModelMappingProvider,
  ModelMappingProviderCreate,
  ModelMappingProviderUpdate,
  ModelListParams,
  ModelProviderListParams,
} from '@/types';

/** Query Keys */
const QUERY_KEYS = {
  models: ['models'] as const,
  modelList: (params?: ModelListParams) => [...QUERY_KEYS.models, 'list', params] as const,
  modelDetail: (requestedModel: string) => [...QUERY_KEYS.models, 'detail', requestedModel] as const,
  modelProviders: ['model-providers'] as const,
  modelProviderList: (params?: ModelProviderListParams) =>
    [...QUERY_KEYS.modelProviders, 'list', params] as const,
  modelStats: (params?: { requested_model?: string }) =>
    [...QUERY_KEYS.models, 'stats', params] as const,
  modelProviderStats: (params?: { requested_model?: string }) =>
    [...QUERY_KEYS.models, 'provider-stats', params] as const,
};

// ============ Model Mapping Hooks ============

/**
 * Get Model Mapping List Hook
 */
export function useModels(params?: ModelListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.modelList(params),
    queryFn: () => getModels(params),
  });
}

/**
 * Get Single Model Mapping Detail Hook (Includes Provider Config)
 */
export function useModel(requestedModel: string) {
  return useQuery({
    queryKey: QUERY_KEYS.modelDetail(requestedModel),
    queryFn: () => getModel(requestedModel),
    enabled: !!requestedModel, // Only query when requestedModel is valid
  });
}

export function useModelStats(params?: { requested_model?: string }) {
  return useQuery({
    queryKey: QUERY_KEYS.modelStats(params),
    queryFn: () => getModelStats(params),
    staleTime: 30 * 1000,
  });
}

export function useModelProviderStats(params?: { requested_model?: string }) {
  return useQuery({
    queryKey: QUERY_KEYS.modelProviderStats(params),
    queryFn: () => getModelProviderStats(params),
    staleTime: 30 * 1000,
  });
}

/**
 * Create Model Mapping Mutation Hook
 */
export function useCreateModel() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ModelMappingCreate) => createModel(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      toast.success('Created successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Create failed'));
    },
  });
}

/**
 * Update Model Mapping Mutation Hook
 */
export function useUpdateModel() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({
      requestedModel,
      data,
    }: {
      requestedModel: string;
      data: ModelMappingUpdate;
    }) => updateModel(requestedModel, data),
    onSuccess: (_: ModelMapping, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.modelDetail(variables.requestedModel),
      });
      toast.success('Saved successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Save failed'));
    },
  });
}

/**
 * Delete Model Mapping Mutation Hook
 */
export function useDeleteModel() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (requestedModel: string) => deleteModel(requestedModel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      toast.success('Deleted successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Delete failed'));
    },
  });
}

// ============ Model-Provider Mapping Hooks ============

/**
 * Get Model-Provider Mapping List Hook
 */
export function useModelProviders(params?: ModelProviderListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.modelProviderList(params),
    queryFn: () => getModelProviders(params),
  });
}

/**
 * Create Model-Provider Mapping Mutation Hook
 */
export function useCreateModelProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ModelMappingProviderCreate) => createModelProvider(data),
    onSuccess: (_: ModelMappingProvider, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.modelProviders });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      // Refresh model detail
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.modelDetail(variables.requested_model),
      });
      toast.success('Created successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Create failed'));
    },
  });
}

/**
 * Update Model-Provider Mapping Mutation Hook
 */
export function useUpdateModelProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: ModelMappingProviderUpdate;
    }) => updateModelProvider(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.modelProviders });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      toast.success('Saved successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Save failed'));
    },
  });
}

/**
 * Delete Model-Provider Mapping Mutation Hook
 */
export function useDeleteModelProvider() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: number) => deleteModelProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.modelProviders });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.models });
      toast.success('Deleted successfully');
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, 'Delete failed'));
    },
  });
}
