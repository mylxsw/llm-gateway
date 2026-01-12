/**
 * Root Layout Component
 * Configures global fonts, styles, and Providers
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/common/Sidebar";
import { AuthGate } from "@/components/auth";

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
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          <AuthGate />
          <div className="flex min-h-screen">
            {/* Sidebar Navigation */}
            <Sidebar />
            {/* Main Content Area */}
            <main className="flex-1 overflow-auto bg-gray-50 p-6">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}