/**
 * HTTP Client Wrapper
 * Implemented based on axios, providing unified error handling and request interception.
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import { ApiError } from '@/types';
import { getApiErrorMessage } from './error';

/** API base URL, configurable via environment variables */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Create axios instance
 * Configure base URL and default headers
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds timeout
});

const ADMIN_TOKEN_STORAGE_KEY = 'lgw_admin_token';

/**
 * Request Interceptor
 * Add authentication token here
 */
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response Interceptor
 * Unified error response handling
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const statusCode = error.response?.status;
    const url = error.config?.url || '';
    const statusText = error.response?.statusText;

    if (typeof window !== 'undefined' && statusCode === 401 && !url.includes('/api/auth/')) {
      window.dispatchEvent(new CustomEvent('auth:required'));
    }

    const httpFallback =
      typeof statusCode === 'number'
        ? `HTTP ${statusCode}${statusText ? ` ${statusText}` : ''}`
        : error.message || 'Network error';

    const message = getApiErrorMessage(error, httpFallback);
    return Promise.reject(new Error(message));
  }
);

export function getStoredAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
}

export function setStoredAdminToken(token: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
}

export function clearStoredAdminToken() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
}

/**
 * Generic GET Request
 * @param url - Request path
 * @param params - Query parameters
 * @param config - Extra configuration
 */
export async function get<T>(
  url: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.get<T>(url, { ...config, params });
  return response.data;
}

/**
 * Generic POST Request
 * @param url - Request path
 * @param data - Request body
 * @param config - Extra configuration
 */
export async function post<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.post<T>(url, data, config);
  return response.data;
}

/**
 * Generic PUT Request
 * @param url - Request path
 * @param data - Request body
 * @param config - Extra configuration
 */
export async function put<T>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.put<T>(url, data, config);
  return response.data;
}

/**
 * Generic DELETE Request
 * @param url - Request path
 * @param config - Extra configuration
 */
export async function del<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.delete<T>(url, config);
  return response.data;
}

export default apiClient;
