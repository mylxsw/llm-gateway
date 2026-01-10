/**
 * 模型映射相关类型定义
 * 对应后端 model_mappings 和 model_mapping_providers 表
 */

import { RuleSet } from './common';

/** 模型映射实体 */
export interface ModelMapping {
  requested_model: string;            // 主键
  strategy: string;                   // 策略，默认 round_robin
  matching_rules?: RuleSet | null;    // 模型级规则
  capabilities?: Record<string, unknown>; // 功能描述
  is_active: boolean;
  provider_count?: number;            // 关联的供应商数量
  providers?: ModelMappingProvider[]; // 详情中包含供应商列表
  created_at: string;
  updated_at: string;
}

/** 模型-供应商映射实体 */
export interface ModelMappingProvider {
  id: number;
  requested_model: string;
  provider_id: number;
  provider_name: string;              // 关联查询获得
  target_model_name: string;          // 该供应商对应的目标模型名
  provider_rules?: RuleSet | null;    // 供应商级规则
  priority: number;
  weight: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建模型映射请求 */
export interface ModelMappingCreate {
  requested_model: string;
  strategy?: string;
  matching_rules?: RuleSet;
  capabilities?: Record<string, unknown>;
  is_active?: boolean;
}

/** 更新模型映射请求 */
export interface ModelMappingUpdate {
  strategy?: string;
  matching_rules?: RuleSet | null;
  capabilities?: Record<string, unknown>;
  is_active?: boolean;
}

/** 创建模型-供应商映射请求 */
export interface ModelMappingProviderCreate {
  requested_model: string;
  provider_id: number;
  target_model_name: string;
  provider_rules?: RuleSet;
  priority?: number;
  weight?: number;
  is_active?: boolean;
}

/** 更新模型-供应商映射请求 */
export interface ModelMappingProviderUpdate {
  target_model_name?: string;
  provider_rules?: RuleSet | null;
  priority?: number;
  weight?: number;
  is_active?: boolean;
}

/** 模型映射列表查询参数 */
export interface ModelListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

/** 模型-供应商映射列表查询参数 */
export interface ModelProviderListParams {
  requested_model?: string;
  provider_id?: number;
  is_active?: boolean;
}
