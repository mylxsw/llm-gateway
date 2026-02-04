/**
 * Home Page
 * Displays system overview and quick access shortcuts
 */

'use client';

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Server, Layers, Key, FileText, ArrowRight } from "lucide-react";
import { HomeCostStats } from "@/components/home/HomeCostStats";

/**
 * Home Page Component
 */
export default function HomePage() {
  const t = useTranslations("home");

  const features = [
    {
      title: t("cards.providersTitle"),
      description: t("cards.providersDescription"),
      href: "/providers",
      icon: Server,
    },
    {
      title: t("cards.modelsTitle"),
      description: t("cards.modelsDescription"),
      href: "/models",
      icon: Layers,
    },
    {
      title: t("cards.apiKeysTitle"),
      description: t("cards.apiKeysDescription"),
      href: "/api-keys",
      icon: Key,
    },
    {
      title: t("cards.logsTitle"),
      description: t("cards.logsDescription"),
      href: "/logs",
      icon: FileText,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("description")}</p>
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
                        <Icon
                          className="h-5 w-5 text-primary"
                          suppressHydrationWarning
                        />
                      </div>
                      <CardTitle className="text-lg">{feature.title}</CardTitle>
                    </div>
                    <ArrowRight
                      className="h-5 w-5 text-muted-foreground"
                      suppressHydrationWarning
                    />
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
