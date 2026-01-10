/**
 * HTTP 客户端封装
 * 基于 axios 实现，提供统一的错误处理和请求拦截
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import { ApiError } from '@/types';

/** API 基础地址，可通过环境变量配置 */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

/**
 * 创建 axios 实例
 * 配置基础 URL 和默认请求头
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30秒超时
});

/**
 * 请求拦截器
 * 可在此处添加认证 token 等
 */
apiClient.interceptors.request.use(
  (config) => {
    // 可在此处添加 Authorization header
    // const token = localStorage.getItem('admin_token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器
 * 统一处理错误响应
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    // 提取错误信息
    if (error.response?.data?.error) {
      const apiError = error.response.data.error;
      return Promise.reject(new Error(apiError.message || '请求失败'));
    }
    return Promise.reject(new Error(error.message || '网络错误'));
  }
);

/**
 * 通用 GET 请求
 * @param url - 请求路径
 * @param params - 查询参数
 * @param config - 额外配置
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
 * 通用 POST 请求
 * @param url - 请求路径
 * @param data - 请求体
 * @param config - 额外配置
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
 * 通用 PUT 请求
 * @param url - 请求路径
 * @param data - 请求体
 * @param config - 额外配置
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
 * 通用 DELETE 请求
 * @param url - 请求路径
 * @param config - 额外配置
 */
export async function del<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response = await apiClient.delete<T>(url, config);
  return response.data;
}

export default apiClient;
