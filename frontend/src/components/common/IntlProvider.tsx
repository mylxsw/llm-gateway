/**
 * Client-side Internationalization Provider
 * Handles locale switching for static export mode
 */

'use client';

import React, { useEffect, useState } from 'react';
import { NextIntlClientProvider } from 'next-intl';
import { locales, defaultLocale, localeCookieName, type Locale } from '@/i18n/config';

// Import all messages statically for static export
import enMessages from '../../../messages/en.json';
import zhMessages from '../../../messages/zh.json';

const messagesMap: Record<Locale, typeof enMessages> = {
  en: enMessages,
  zh: zhMessages,
};

function getStoredLocale(): Locale {
  if (typeof window === 'undefined') return defaultLocale;

  const cookieMatch = document.cookie.match(new RegExp(`${localeCookieName}=([^;]+)`));
  const stored = cookieMatch?.[1];

  if (stored && locales.includes(stored as Locale)) {
    return stored as Locale;
  }
  return defaultLocale;
}

interface IntlProviderProps {
  children: React.ReactNode;
}

export function IntlProvider({ children }: IntlProviderProps) {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setLocale(getStoredLocale());
    setMounted(true);

    // Listen for locale changes
    const handleLocaleChange = () => {
      setLocale(getStoredLocale());
    };

    window.addEventListener('locale-change', handleLocaleChange);
    return () => window.removeEventListener('locale-change', handleLocaleChange);
  }, []);

  // Update html lang attribute
  useEffect(() => {
    if (mounted) {
      document.documentElement.lang = locale;
    }
  }, [locale, mounted]);

  const messages = messagesMap[locale];

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

// Export a function to change locale (to be used by LanguageSwitcher)
export function setLocale(newLocale: Locale) {
  if (!locales.includes(newLocale)) return;

  const maxAge = 60 * 60 * 24 * 365;
  document.cookie = `${localeCookieName}=${newLocale}; path=/; max-age=${maxAge}; samesite=lax`;

  // Dispatch event to notify IntlProvider
  window.dispatchEvent(new Event('locale-change'));
}
