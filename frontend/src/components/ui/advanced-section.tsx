'use client';

import * as React from 'react';
import { ChevronDown } from 'lucide-react';

import { cn } from '@/lib/utils';

interface AdvancedSectionProps {
  label: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
  contentClassName?: string;
}

/** A compact disclosure card shared by admin forms. */
export function AdvancedSection({
  label,
  open,
  onOpenChange,
  children,
  contentClassName,
}: AdvancedSectionProps) {
  const contentId = React.useId();

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className={cn(
          'flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium',
          'transition-colors hover:bg-muted/50 focus-visible:outline-none',
          'focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
          open && 'bg-muted/30'
        )}
        aria-expanded={open}
        aria-controls={contentId}
      >
        <span>{label}</span>
        <ChevronDown
          className={cn(
            'h-4 w-4 text-muted-foreground transition-transform',
            open && 'rotate-180'
          )}
          suppressHydrationWarning
        />
      </button>

      {open && (
        <div
          id={contentId}
          className={cn('border-t border-border p-4', contentClassName)}
        >
          {children}
        </div>
      )}
    </div>
  );
}
