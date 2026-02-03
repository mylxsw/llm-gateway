/**
 * App Shell
 * Handles global layout with conditional rendering for auth routes.
 */

'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from '@/components/common/Sidebar';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { LanguageSwitcher } from '@/components/common/LanguageSwitcher';
import { cn } from '@/lib/utils';

const AUTH_ROUTES = new Set(['/login']);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthRoute = AUTH_ROUTES.has(pathname);

  return (
    <>
      <div className="flex min-h-screen">
        {!isAuthRoute && <Sidebar />}
        <main
          className={cn(
            'flex-1 overflow-auto',
            isAuthRoute ? '' : 'bg-muted/30 p-6'
          )}
        >
          {children}
        </main>
      </div>
      {!isAuthRoute && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeToggle inline />
        </div>
      )}
    </>
  );
}
