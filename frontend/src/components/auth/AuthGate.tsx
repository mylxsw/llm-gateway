/**
 * Authentication Gate
 *
 * When backend enables ADMIN_USERNAME/ADMIN_PASSWORD:
 * - Automatically pops up login dialog if not logged in
 * - Re-triggers login dialog if any API returns 401
 */

'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { getAuthStatus, login } from '@/lib/api/auth';
import { setStoredAdminToken } from '@/lib/api/client';

export function AuthGate() {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const canClose = useMemo(() => enabled === false, [enabled]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const status = await getAuthStatus();
        if (cancelled) return;
        setEnabled(status.enabled);
        if (status.enabled && !status.authenticated) {
          setOpen(true);
        }
      } catch {
        if (cancelled) return;
        // If status API fails, do not block UI forcibly
        setEnabled(false);
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('auth:required', handler);
    return () => window.removeEventListener('auth:required', handler);
  }, []);

  const handleOpenChange = (next: boolean) => {
    if (!next && !canClose) return;
    setOpen(next);
  };

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await login(username.trim(), password);
      setStoredAdminToken(res.access_token);
      setOpen(false);
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Login</DialogTitle>
          <DialogDescription>
            Username and password are required to access the admin panel.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Username</label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              disabled={loading}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Password</label>
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
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={!canClose || loading}
          >
            Cancel
          </Button>
          <Button onClick={handleLogin} disabled={loading || !username || !password}>
            {loading ? 'Logging in...' : 'Login'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}