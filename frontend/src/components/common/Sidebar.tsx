/**
 * 侧边栏导航组件
 * 提供全局导航菜单
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

/** 导航菜单项定义 */
const navItems = [
  {
    title: '首页',
    href: '/',
    icon: Home,
  },
  {
    title: '供应商管理',
    href: '/providers',
    icon: Server,
  },
  {
    title: '模型管理',
    href: '/models',
    icon: Layers,
  },
  {
    title: 'API Key 管理',
    href: '/api-keys',
    icon: Key,
  },
  {
    title: '请求日志',
    href: '/logs',
    icon: FileText,
  },
];

/**
 * 侧边栏导航组件
 */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex w-64 flex-col border-r bg-white">
      {/* Logo 和标题 */}
      <div className="flex h-16 items-center border-b px-6">
        <Settings className="h-6 w-6 text-primary" />
        <span className="ml-3 text-lg font-semibold">LLM Gateway</span>
      </div>

      {/* 导航菜单 */}
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

      {/* 底部信息 */}
      <div className="border-t px-6 py-4">
        <p className="text-xs text-muted-foreground">
          LLM Gateway v1.0.0
        </p>
      </div>
    </div>
  );
}
