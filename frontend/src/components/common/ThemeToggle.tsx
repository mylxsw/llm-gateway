/**
 * Theme Toggle Button
 * Fixed corner toggle for light/dark theme.
 */

'use client';

import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/components/common/ThemeProvider';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  inline?: boolean;
  className?: string;
}

export function ThemeToggle({ inline = false, className }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const isDark = theme === 'dark';
  const label = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  const button = (
    <Button
      type="button"
      variant="outline"
      size="icon"
      aria-label={label}
      title={label}
      onClick={toggleTheme}
      className={cn('rounded-full shadow-sm', className)}
    >
      {isDark ? <Sun /> : <Moon />}
    </Button>
  );

  if (inline) return button;

  return <div className="fixed bottom-4 right-4 z-50">{button}</div>;
}
