/**
 * 通用类型定义
 * 包含分页、错误响应等基础类型
 */

/** 分页响应结构 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** API 错误响应结构 */
export interface ApiError {
  error: {
    message: string;
    type: string;
    code: string;
    details?: Record<string, unknown>;
  };
}

/** 分页查询参数 */
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

/** 排序参数 */
export interface SortParams {
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/** 规则操作符类型 */
export type RuleOperator = 
  | 'eq' 
  | 'ne' 
  | 'gt' 
  | 'gte' 
  | 'lt' 
  | 'lte' 
  | 'contains' 
  | 'not_contains' 
  | 'regex' 
  | 'in' 
  | 'not_in' 
  | 'exists';

/** 单条规则定义 */
export interface Rule {
  field: string;
  operator: RuleOperator;
  value: unknown;
}

/** 规则集定义 */
export interface RuleSet {
  rules: Rule[];
  logic?: 'AND' | 'OR';
}
