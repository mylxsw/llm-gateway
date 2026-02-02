/**
 * Root Layout Component
 * Configures global fonts, styles, and Providers
 */

import type { Metadata } from "next";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/common/Sidebar";
import { AuthGate } from "@/components/auth";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { LanguageSwitcher } from "@/components/common/LanguageSwitcher";
import { IntlProvider } from "@/components/common/IntlProvider";

// Configure Sans-serif Font
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

// Configure Monospace Font
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Page Metadata
export const metadata: Metadata = {
  title: "LLM Gateway Admin Panel",
  description: "Model Routing & Proxy Service Admin Panel",
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
            <div className="flex min-h-screen">
              {/* Sidebar Navigation */}
              <Sidebar />
              {/* Main Content Area */}
              <main className="flex-1 overflow-auto bg-muted/30 p-6">
                {children}
              </main>
            </div>
            <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2">
              <LanguageSwitcher compact />
              <ThemeToggle inline />
            </div>
          </Providers>
        </IntlProvider>
      </body>
    </html>
  );
}
