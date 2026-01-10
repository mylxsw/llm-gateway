/**
 * React Query Provider
 * 为应用提供全局状态管理
 */

'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
 * 全局 Provider 组件
 * 包装 React Query 等全局状态管理
 */
export function Providers({ children }: { children: React.ReactNode }) {
  // 创建 QueryClient 实例（每个客户端独立）
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 默认缓存时间 5 分钟
            staleTime: 5 * 60 * 1000,
            // 失败重试 1 次
            retry: 1,
            // 窗口聚焦时不自动刷新
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
