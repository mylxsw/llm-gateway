/**
 * 首页
 * 显示系统概览和快捷入口
 */

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Server, Layers, Key, FileText, ArrowRight } from 'lucide-react';

/** 功能卡片数据 */
const features = [
  {
    title: '供应商管理',
    description: '管理上游 AI 供应商，配置接口地址和 API Key',
    href: '/providers',
    icon: Server,
  },
  {
    title: '模型管理',
    description: '配置模型映射规则，支持同一模型对接多个供应商',
    href: '/models',
    icon: Layers,
  },
  {
    title: 'API Key 管理',
    description: '管理系统 API Key，用于客户端访问代理接口',
    href: '/api-keys',
    icon: Key,
  },
  {
    title: '请求日志',
    description: '查看所有代理请求日志，支持多条件筛选查询',
    href: '/logs',
    icon: FileText,
  },
];

/**
 * 首页组件
 */
export default function HomePage() {
  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold">LLM Gateway 管理面板</h1>
        <p className="mt-1 text-muted-foreground">
          模型路由与代理服务管理系统
        </p>
      </div>

      {/* 功能入口卡片 */}
      <div className="grid gap-6 md:grid-cols-2">
        {features.map((feature) => {
          const Icon = feature.icon;
          return (
            <Link key={feature.href} href={feature.href}>
              <Card className="h-full transition-shadow hover:shadow-md">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <Icon className="h-5 w-5 text-primary" />
                      </div>
                      <CardTitle className="text-lg">{feature.title}</CardTitle>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground" />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* 系统说明 */}
      <Card>
        <CardHeader>
          <CardTitle>系统说明</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            LLM Gateway 是一个模型路由与代理服务，支持 OpenAI 和 Anthropic 协议的请求代理。
          </p>
          <ul className="list-inside list-disc space-y-2">
            <li>
              <strong>透明代理：</strong>
              兼容 OpenAI/Anthropic 客户端调用方式，仅修改 model 字段
            </li>
            <li>
              <strong>规则引擎：</strong>
              支持基于请求头、请求体、Token 用量等条件进行供应商匹配
            </li>
            <li>
              <strong>轮询策略：</strong>
              在多个供应商之间进行轮询负载均衡
            </li>
            <li>
              <strong>自动重试：</strong>
              支持故障自动重试和供应商切换
            </li>
            <li>
              <strong>完整日志：</strong>
              记录所有请求的详细信息，支持多条件查询
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
