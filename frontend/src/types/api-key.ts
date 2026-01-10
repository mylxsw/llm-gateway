/**
 * API Key 相关类型定义
 * 对应后端 api_keys 表
 */

/** API Key 实体 */
export interface ApiKey {
  id: number;
  key_name: string;
  key_value: string;          // 列表中脱敏显示，创建时完整返回
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
}

/** 创建 API Key 请求 */
export interface ApiKeyCreate {
  key_name: string;
}

/** 更新 API Key 请求 */
export interface ApiKeyUpdate {
  key_name?: string;
  is_active?: boolean;
}

/** API Key 列表查询参数 */
export interface ApiKeyListParams {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}
