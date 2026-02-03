/**
 * Login Page (Client)
 * Standalone auth page with redirect back to original route.
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Squirrel } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { getAuthStatus, login } from '@/lib/api/auth';
import { setStoredAdminToken } from '@/lib/api/client';

function normalizeReturnTo(raw: string | null): string {
  if (!raw) return '/';
  if (raw.startsWith('/') && !raw.startsWith('//')) return raw;
  return '/';
}

export function LoginClient() {
  const t = useTranslations('common.auth');
  const tSidebar = useTranslations('sidebar');
  const router = useRouter();
  const searchParams = useSearchParams();

  const [checking, setChecking] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const returnTo = useMemo(
    () => normalizeReturnTo(searchParams.get('returnTo')),
    [searchParams]
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const status = await getAuthStatus();
        if (cancelled) return;
        setAuthEnabled(status.enabled);
        if (!status.enabled || status.authenticated) {
          router.replace(returnTo);
          return;
        }
      } catch {
        if (cancelled) return;
      } finally {
        if (!cancelled) setChecking(false);
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [router, returnTo]);

  const handleLogin = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await login(username.trim(), password);
      setStoredAdminToken(res.access_token);
      router.replace(returnTo);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6 text-sm text-muted-foreground">
        {t('checking')}
      </div>
    );
  }

  if (!authEnabled) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>{t('login')}</CardTitle>
            <CardDescription>{t('authDisabled')}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => router.replace(returnTo)}>
              {t('back')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex flex-col items-center gap-3">
            <Squirrel className="h-12 w-12 text-primary" suppressHydrationWarning />
            <CardTitle className="text-xl">Squirrel LLM Gateway</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">{t('username')}</label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              disabled={loading}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">{t('password')}</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleLogin();
                }
              }}
            />
          </div>
          {error && <div className="text-sm text-red-600">{error}</div>}
          <Button
            className="w-full"
            onClick={handleLogin}
            disabled={loading || !username || !password}
          >
            {loading ? t('loggingIn') : t('login')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
