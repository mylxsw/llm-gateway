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
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';

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
    title: 'Request Logs',
    href: '/logs',
    icon: FileText,
  },
];

/**
 * Sidebar Navigation Component
 */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex w-64 flex-col border-r bg-white">
      {/* Logo and Title */}
      <div className="flex h-16 items-center border-b px-6">
        <Settings className="h-6 w-6 text-primary" />
        <span className="ml-3 text-lg font-semibold">LLM Gateway</span>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              )}
            >
              <Icon className="h-5 w-5" />
              {item.title}
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="border-t px-6 py-4">
        <p className="text-xs text-muted-foreground">
          LLM Gateway v1.0.0
        </p>
      </div>
    </div>
  );
}