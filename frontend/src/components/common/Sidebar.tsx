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
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

/** Navigation Items Definition */
const navItems = [
  {
    title: 'Home',
    href: '/',
    icon: Home,
  },
  {
    title: 'Providers',
    href: '/providers',
    icon: Server,
  },
  {
    title: 'Models',
    href: '/models',
    icon: Layers,
  },
  {
    title: 'API Keys',
    href: '/api-keys',
    icon: Key,
  },
  {
    title: 'Logs',
    href: '/logs',
    icon: FileText,
  },
];

/**
 * Sidebar Navigation Component
 */
export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

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
            Squirrel
          </span>
        </div>

        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
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

          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.title : undefined}
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
                {item.title}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className={cn('border-t border-border py-4', collapsed ? 'px-4' : 'px-6')}>
        <p
          className={cn(
            'overflow-hidden whitespace-nowrap text-xs text-muted-foreground transition-[max-width,opacity] duration-200',
            collapsed ? 'max-w-0 opacity-0' : 'max-w-[200px] opacity-100'
          )}
        >
          Squirrel LLM Gateway v1.0.0
        </p>
      </div>
    </div>
  );
}
