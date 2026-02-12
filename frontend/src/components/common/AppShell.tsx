/**
 * App Shell
 * Handles global layout with conditional rendering for auth routes.
 */

'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import { Github } from 'lucide-react';
import { Sidebar } from '@/components/common/Sidebar';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { LanguageSwitcher } from '@/components/common/LanguageSwitcher';
import { Button } from '@/components/ui/button';
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
          <Button
            asChild
            type="button"
            variant="outline"
            size="icon"
            className="rounded-full shadow-sm"
          >
            <a
              href="https://github.com/mylxsw/llm-gateway"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub Repository"
              title="GitHub Repository"
            >
              <Github />
            </a>
          </Button>
        </div>
      )}
    </>
  );
}
