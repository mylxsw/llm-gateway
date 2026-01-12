/**
 * Home Page
 * Displays system overview and quick access shortcuts
 */

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Server, Layers, Key, FileText, ArrowRight } from 'lucide-react';

/** Feature Card Data */
const features = [
  {
    title: 'Provider Management',
    description: 'Manage upstream AI providers, configure base URLs and API keys',
    href: '/providers',
    icon: Server,
  },
  {
    title: 'Model Management',
    description: 'Configure model mapping rules, support multiple providers for the same model',
    href: '/models',
    icon: Layers,
  },
  {
    title: 'API Key Management',
    description: 'Manage system API Keys for clients to access proxy interfaces',
    href: '/api-keys',
    icon: Key,
  },
  {
    title: 'Request Logs',
    description: 'View all proxy request logs, supports multi-condition filtering',
    href: '/logs',
    icon: FileText,
  },
];

/**
 * Home Page Component
 */
export default function HomePage() {
  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold">LLM Gateway Admin Panel</h1>
        <p className="mt-1 text-muted-foreground">
          Model Routing & Proxy Service Management System
        </p>
      </div>

      {/* Feature Access Cards */}
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
                        <Icon className="h-5 w-5 text-primary" suppressHydrationWarning />
                      </div>
                      <CardTitle className="text-lg">{feature.title}</CardTitle>
                    </div>
                    <ArrowRight className="h-5 w-5 text-muted-foreground" suppressHydrationWarning />
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

      {/* System Description */}
      <Card>
        <CardHeader>
          <CardTitle>System Description</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            LLM Gateway is a model routing and proxy service that supports OpenAI and Anthropic protocol request proxying.
          </p>
          <ul className="list-inside list-disc space-y-2">
            <li>
              <strong>Transparent Proxy:</strong>
              Compatible with OpenAI/Anthropic client invocation methods, only modifies the &apos;model&apos; field
            </li>
            <li>
              <strong>Rule Engine:</strong>
              Supports provider matching based on headers, body, Token usage, etc.
            </li>
            <li>
              <strong>Round Robin Strategy:</strong>
              Performs round-robin load balancing among multiple providers
            </li>
            <li>
              <strong>Automatic Retry:</strong>
              Supports automatic failure retry and provider failover
            </li>
            <li>
              <strong>Complete Logging:</strong>
              Records detailed information for all requests, supports multi-condition queries
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
