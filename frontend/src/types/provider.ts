/**
 * 供应商相关类型定义
 * 对应后端 service_providers 表
 */

/** 协议类型 */
export type ProtocolType = 'openai' | 'anthropic';

/** 供应商实体 */
export interface Provider {
  id: number;
  name: string;
  base_url: string;
  protocol: ProtocolType;
  api_type: string;
  api_key?: string;          // 脱敏显示
  extra_headers?: Record<string, string>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建供应商请求 */
export interface ProviderCreate {
  name: string;
  base_url: string;
  protocol: ProtocolType;
  api_type: string;
  api_key?: string;
  extra_headers?: Record<string, string>;
  is_active?: boolean;
}

/** 更新供应商请求 */
export interface ProviderUpdate {
  name?: string;
  base_url?: string;
  protocol?: ProtocolType;
  api_type?: string;
  api_key?: string;
  extra_headers?: Record<string, string>;
  is_active?: boolean;
}

/** 供应商列表查询参数 */
export interface ProviderListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}
