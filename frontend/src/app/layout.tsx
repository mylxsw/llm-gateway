/**
 * Root Layout Component
 * Configures global fonts, styles, and Providers
 */

import type { Metadata } from 'next';
import Script from 'next/script';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';
import { AuthGate } from '@/components/auth';
import { IntlProvider } from '@/components/common/IntlProvider';
import { AppShell } from '@/components/common/AppShell';

// Configure Sans-serif Font
const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

// Configure Monospace Font
const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

// Page Metadata
export const metadata: Metadata = {
  title: 'LLM Gateway Admin Panel',
  description: 'Model Routing & Proxy Service Admin Panel',
};

/**
 * Root Layout Component
 * Contains sidebar navigation and main content area
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script
          id="theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `(function () {
  try {
    var key = 'theme';
    var stored = localStorage.getItem(key);
    var systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var theme = (stored === 'dark' || stored === 'light') ? stored : (systemDark ? 'dark' : 'light');
    var root = document.documentElement;
    if (theme === 'dark') root.classList.add('dark'); else root.classList.remove('dark');
    root.dataset.theme = theme;
  } catch (e) {}
})();`,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        <IntlProvider>
          <Providers>
            <AuthGate />
            <AppShell>{children}</AppShell>
          </Providers>
        </IntlProvider>
      </body>
    </html>
  );
}
