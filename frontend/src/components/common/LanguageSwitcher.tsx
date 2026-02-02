/**
 * Language Switcher
 * Icon button with dropdown for language selection
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
} from '@/components/ui/select';
import { locales, type Locale } from '@/i18n/config';
import { setLocale } from './IntlProvider';

const localeLabels: Record<Locale, string> = {
  en: 'English',
  zh: '中文',
};

export function LanguageSwitcher() {
  const locale = useLocale() as Locale;
  const t = useTranslations('common');
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const handleChange = (value: string) => {
    if (!locales.includes(value as Locale)) return;
    setLocale(value as Locale);
  };

  const label = t('language');

  return (
    <Select value={locale} onValueChange={handleChange}>
      <SelectTrigger
        className="h-9 w-9 rounded-full bg-background border shadow-sm justify-center [&>svg:last-child]:hidden"
        aria-label={label}
        title={label}
      >
        <Languages className="h-4 w-4" />
      </SelectTrigger>
      <SelectContent align="end">
        {locales.map((loc) => (
          <SelectItem key={loc} value={loc}>
            {localeLabels[loc]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
