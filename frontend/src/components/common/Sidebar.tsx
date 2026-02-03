/**
 * Sidebar Navigation Component
 * Provides global navigation menu
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Server,
  Layers,
  Key,
  FileText,
  Home,
  Squirrel,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { logout } from '@/lib/api/auth';
import { clearStoredAdminToken } from '@/lib/api/client';

/** Navigation Items Definition */
const navItems = [
  {
    title: 'home',
    href: '/',
    icon: Home,
  },
  {
    title: 'providers',
    href: '/providers',
    icon: Server,
  },
  {
    title: 'models',
    href: '/models',
    icon: Layers,
  },
  {
    title: 'apiKeys',
    href: '/api-keys',
    icon: Key,
  },
  {
    title: 'logs',
    href: '/logs',
    icon: FileText,
  },
];

/**
 * Sidebar Navigation Component
 */
export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations('sidebar');
  const router = useRouter();
  const [collapsed, setCollapsed] = React.useState(false);
  const [loggingOut, setLoggingOut] = React.useState(false);

  React.useEffect(() => {
    try {
      const stored = localStorage.getItem('sidebar:collapsed');
      if (stored === '1') setCollapsed(true);
      if (stored === '0') setCollapsed(false);
    } catch {}
  }, []);

  React.useEffect(() => {
    try {
      localStorage.setItem('sidebar:collapsed', collapsed ? '1' : '0');
    } catch {}
  }, [collapsed]);

  const handleLogout = async () => {
    if (loggingOut) return;
    const confirmed = window.confirm(t('logoutConfirm'));
    if (!confirmed) return;
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      // Ignore logout errors; clear local token anyway.
    } finally {
      clearStoredAdminToken();
      const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
      router.replace(`/login?returnTo=${returnTo}`);
      setLoggingOut(false);
    }
  };

  return (
    <div
      className={cn(
        'relative flex shrink-0 flex-col border-r border-border bg-card text-card-foreground transition-[width] duration-300 ease-in-out',
        collapsed ? 'w-[76px]' : 'w-64'
      )}
    >
      {/* Logo and Title */}
      <div
        className={cn(
          'relative flex h-16 items-center border-b border-border',
          collapsed ? 'justify-center px-4' : 'px-6'
        )}
      >
        <div className={cn('flex items-center', collapsed ? 'gap-0' : 'gap-3')}>
          <Squirrel
            className="h-6 w-6 text-primary"
            suppressHydrationWarning
          />
          <span
            className={cn(
              'overflow-hidden whitespace-nowrap text-lg font-semibold transition-[max-width,opacity,transform] duration-200',
              collapsed
                ? 'max-w-0 opacity-0 translate-x-1'
                : 'max-w-[160px] opacity-100 translate-x-0'
            )}
          >
            {t('appName')}
          </span>
        </div>

        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? t('expand') : t('collapse')}
          title={collapsed ? t('expand') : t('collapse')}
          className={cn(
            'absolute -right-4 top-1/2 z-20 h-8 w-8 -translate-y-1/2 rounded-full',
            'bg-background/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/80',
            'border-border transition-all hover:bg-accent hover:shadow-md active:scale-[0.98]'
          )}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" suppressHydrationWarning />
          ) : (
            <ChevronLeft className="h-4 w-4" suppressHydrationWarning />
          )}
        </Button>
      </div>

      {/* Navigation Menu */}
      <nav className={cn('flex-1 space-y-1 py-4', collapsed ? 'px-2' : 'px-3')}>
        {navItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));
          const Icon = item.icon;
          const title = t(item.title);

          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? title : undefined}
              className={cn(
                'flex items-center rounded-lg py-2 text-sm font-medium transition-colors',
                collapsed ? 'justify-center px-2' : 'gap-3 px-3',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              )}
            >
              <Icon className="h-5 w-5" suppressHydrationWarning />
              <span
                className={cn(
                  'overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform] duration-200',
                  collapsed
                    ? 'max-w-0 opacity-0 -translate-x-1'
                    : 'max-w-[180px] opacity-100 translate-x-0'
                )}
              >
                {title}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className={cn('border-t border-border py-3', collapsed ? 'px-2' : 'px-4')}>
        <div
          className={cn(
            'flex items-center justify-between gap-2',
            collapsed ? 'justify-center' : 'justify-between'
          )}
        >
          <p
            className={cn(
              'overflow-hidden whitespace-nowrap text-xs text-muted-foreground transition-[max-width,opacity] duration-200',
              collapsed ? 'max-w-0 opacity-0' : 'max-w-[200px] opacity-100'
            )}
          >
            {t('version')}
          </p>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            disabled={loggingOut}
            title={t('logout')}
            className="h-8 w-8 text-primary hover:text-primary"
          >
            <LogOut className="h-4 w-4" suppressHydrationWarning />
          </Button>
        </div>
      </div>
    </div>
  );
}
