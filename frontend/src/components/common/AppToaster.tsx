/**
 * Global toast viewport (Sonner)
 * Shows notifications at top-right with 3s auto-dismiss and manual close.
 */

'use client';

import React from 'react';
import { Toaster } from 'sonner';
import { useTheme } from '@/components/common/ThemeProvider';

export function AppToaster() {
  const { theme } = useTheme();

  return (
    <Toaster
      position="top-right"
      theme={theme}
      closeButton
      richColors
      toastOptions={{ duration: 3000 }}
    />
  );
}
