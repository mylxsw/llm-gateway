/**
 * Home Page
 * Displays system overview and quick access shortcuts
 */

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Server, Layers, Key, FileText, ArrowRight } from 'lucide-react';
import { HomeCostStats } from '@/components/home/HomeCostStats';

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

      <HomeCostStats />

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
    </div>
  );
}
