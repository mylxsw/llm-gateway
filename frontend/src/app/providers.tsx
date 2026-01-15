/**
 * React Query Provider
 * Provides global state management for the app.
 */

'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/components/common/ThemeProvider';
import { AppToaster } from '@/components/common/AppToaster';

/**
 * Global provider component
 * Wraps React Query and other global providers.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  // Create QueryClient instance (one per client)
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Default cache time: 5 minutes
            staleTime: 5 * 60 * 1000,
            // Retry once on failure
            retry: 1,
            // Do not refetch on window focus
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        {children}
        <AppToaster />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
