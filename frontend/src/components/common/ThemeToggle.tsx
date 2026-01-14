/**
 * Theme Toggle Button
 * Fixed corner toggle for light/dark theme.
 */

'use client';

import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/components/common/ThemeProvider';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const isDark = theme === 'dark';
  const label = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <Button
        type="button"
        variant="outline"
        size="icon"
        aria-label={label}
        title={label}
        onClick={toggleTheme}
        className="rounded-full shadow-sm"
      >
        {isDark ? <Sun /> : <Moon />}
      </Button>
    </div>
  );
}
