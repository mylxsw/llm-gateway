/**
 * Common Type Definitions
 * Includes base types like pagination, error response, etc.
 */

/** Pagination Response Structure */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** API Error Response Structure */
export interface ApiError {
  error: {
    message: string;
    type: string;
    code: string;
    details?: Record<string, unknown>;
  };
}

/** Pagination Query Params */
export interface PaginationParams {
  page?: number;
  page_size?: number;
}

/** Sort Params */
export interface SortParams {
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/** Rule Operator Type */
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

/** Single Rule Definition */
export interface Rule {
  field: string;
  operator: RuleOperator;
  value: unknown;
}

/** Rule Set Definition */
export interface RuleSet {
  rules: Rule[];
  logic?: 'AND' | 'OR';
}