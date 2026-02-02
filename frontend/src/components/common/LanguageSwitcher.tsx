/**
 * Language Switcher
 * Persists locale in cookie and refreshes the page.
 */

'use client';

import React from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Languages } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { locales, localeCookieName, type Locale } from '@/i18n/config';

const localeLabels: Record<Locale, string> = {
  en: 'English',
  zh: '中文',
};

interface LanguageSwitcherProps {
  collapsed?: boolean;
  compact?: boolean;
}

export function LanguageSwitcher({
  collapsed = false,
  compact = false,
}: LanguageSwitcherProps) {
  const locale = useLocale() as Locale;
  const t = useTranslations('common');
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const handleChange = (value: string) => {
    if (!locales.includes(value as Locale)) return;
    const maxAge = 60 * 60 * 24 * 365;
    document.cookie = `${localeCookieName}=${value}; path=/; max-age=${maxAge}; samesite=lax`;
    // Full page reload is required for static export mode
    window.location.reload();
  };

  const label = t('language');

  return (
    <Select value={locale} onValueChange={handleChange}>
      <SelectTrigger
        className={cn(
          'h-9 w-full rounded-full bg-background shadow-sm',
          collapsed ? 'px-2 text-xs' : 'px-3',
          compact && 'w-[120px] px-2 text-xs'
        )}
        aria-label={label}
        title={label}
      >
        <span className="flex items-center gap-2 truncate">
          <Languages className="h-4 w-4 text-muted-foreground" suppressHydrationWarning />
          <SelectValue placeholder={t('selectLanguage')} />
        </span>
      </SelectTrigger>
      <SelectContent>
        {locales.map((loc) => (
          <SelectItem key={loc} value={loc}>
            {localeLabels[loc]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
