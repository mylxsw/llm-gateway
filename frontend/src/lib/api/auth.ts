/**
 * Auth Related API
 */

import { get, post } from './client';

export interface AuthStatusResponse {
  enabled: boolean;
  authenticated: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export async function getAuthStatus(): Promise<AuthStatusResponse> {
  return get<AuthStatusResponse>('/api/auth/status');
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return post<LoginResponse>('/api/auth/login', { username, password });
}

export async function logout(): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>('/api/auth/logout');
}
