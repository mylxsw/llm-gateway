/**
 * Authentication Gate
 *
 * When backend enables ADMIN_USERNAME/ADMIN_PASSWORD:
 * - Redirects to login page if not logged in
 * - Re-triggers login redirect if any API returns 401
 */

'use client';

import React, { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getAuthStatus } from '@/lib/api/auth';

const LOGIN_PATH = '/login';

function getReturnTo(): string {
  if (typeof window === 'undefined') return '/';
  return `${window.location.pathname}${window.location.search}`;
}

export function AuthGate() {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const status = await getAuthStatus();
        if (cancelled) return;
        if (status.enabled && !status.authenticated && pathname !== LOGIN_PATH) {
          const returnTo = encodeURIComponent(getReturnTo());
          router.replace(`${LOGIN_PATH}?returnTo=${returnTo}`);
        }
      } catch {
        // If status API fails, do not block UI forcibly
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  useEffect(() => {
    const handler = () => {
      if (pathname === LOGIN_PATH) return;
      const returnTo = encodeURIComponent(getReturnTo());
      router.replace(`${LOGIN_PATH}?returnTo=${returnTo}`);
    };
    window.addEventListener('auth:required', handler);
    return () => window.removeEventListener('auth:required', handler);
  }, [pathname, router]);

  return null;
}
