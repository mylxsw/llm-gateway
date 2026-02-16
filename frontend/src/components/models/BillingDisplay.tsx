/**
 * Billing Display Component
 * Unified billing summary text for model-provider mappings.
 */

'use client';

import React from 'react';
import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';

type BillingMode = 'token_flat' | 'token_tiered' | 'per_request' | 'per_image' | null | undefined;

interface BillingTier {
  max_input_tokens?: number | null;
  input_price: number;
  output_price: number;
}

interface BillingDisplayProps {
  billingMode?: BillingMode;
  inputPrice?: number | null;
  outputPrice?: number | null;
  perRequestPrice?: number | null;
  perImagePrice?: number | null;
  tieredPricing?: BillingTier[] | null;
  fallbackInputPrice?: number | null;
  fallbackOutputPrice?: number | null;
  className?: string;
}

function roundUpTo4Decimals(value: number) {
  const factor = 10000;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function formatUsdCeil4(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  const num = Number(value);
  if (Number.isNaN(num)) return '-';
  return `$${roundUpTo4Decimals(num).toFixed(4)}`;
}

function resolveInheritedPrice(
  override: number | null | undefined,
  fallback: number | null | undefined
) {
  if (override !== null && override !== undefined) return override;
  if (fallback !== null && fallback !== undefined) return fallback;
  return 0;
}

function isAllZero(values: number[]) {
  return values.every((v) => v === 0);
}

export function BillingDisplay({
  billingMode,
  inputPrice,
  outputPrice,
  perRequestPrice,
  perImagePrice,
  tieredPricing,
  fallbackInputPrice,
  fallbackOutputPrice,
  className,
}: BillingDisplayProps) {
  const t = useTranslations('models');

  const formatUsdOrFree = (value: number) =>
    value === 0 ? t('detail.billingDisplay.free') : formatUsdCeil4(value);

  const mode = billingMode ?? 'token_flat';

  let text = '';
  if (mode === 'per_request') {
    if (perRequestPrice === null || perRequestPrice === undefined) {
      text = t('detail.billingDisplay.perRequestEmpty');
    } else if (perRequestPrice === 0) {
      text = t('detail.billingDisplay.free');
    } else {
      text = t('detail.billingDisplay.perRequest', {
        price: formatUsdCeil4(perRequestPrice),
      });
    }
  } else if (mode === 'per_image') {
    if (perImagePrice === null || perImagePrice === undefined) {
      text = t('detail.billingDisplay.perImageEmpty');
    } else if (perImagePrice === 0) {
      text = t('detail.billingDisplay.free');
    } else {
      text = t('detail.billingDisplay.perImage', {
        price: formatUsdCeil4(perImagePrice),
      });
    }
  } else if (mode === 'token_tiered') {
    const tiers = tieredPricing ?? [];
    if (!tiers.length) {
      text = t('detail.billingDisplay.tieredEmpty');
    } else if (isAllZero(tiers.flatMap((tier) => [tier.input_price, tier.output_price]))) {
      text = t('detail.billingDisplay.free');
    } else {
      const preview = tiers
        .slice(0, 2)
        .map((tier) => {
          const max =
            tier.max_input_tokens === null || tier.max_input_tokens === undefined
              ? '∞'
              : String(tier.max_input_tokens);
          return t('detail.billingDisplay.tieredEntry', {
            max,
            input: formatUsdOrFree(tier.input_price),
            output: formatUsdOrFree(tier.output_price),
          });
        })
        .join(', ');
      const more =
        tiers.length > 2
          ? t('detail.billingDisplay.tieredPreviewMore', { count: tiers.length - 2 })
          : '';
      text = t('detail.billingDisplay.tieredPreview', { preview, more });
    }
  } else {
    const effectiveInput = resolveInheritedPrice(inputPrice, fallbackInputPrice);
    const effectiveOutput = resolveInheritedPrice(outputPrice, fallbackOutputPrice);
    if (effectiveInput === 0 && effectiveOutput === 0) {
      text = t('detail.billingDisplay.free');
    } else {
      text = t('detail.billingDisplay.tokenFlat', {
        input: formatUsdOrFree(effectiveInput),
        output: formatUsdOrFree(effectiveOutput),
      });
    }
  }

  return <span className={cn('font-mono', className)}>{text}</span>;
}

