/**
 * 根布局组件
 * 配置全局字体、样式和 Provider
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/common/Sidebar";
import { AuthGate } from "@/components/auth";

// 配置无衬线字体
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

// 配置等宽字体
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// 页面元数据
export const metadata: Metadata = {
  title: "LLM Gateway 管理面板",
  description: "模型路由与代理服务管理面板",
};

/**
 * 根布局组件
 * 包含侧边栏导航和主内容区域
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Providers>
          <AuthGate />
          <div className="flex min-h-screen">
            {/* 侧边栏导航 */}
            <Sidebar />
            {/* 主内容区域 */}
            <main className="flex-1 overflow-auto bg-gray-50 p-6">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
