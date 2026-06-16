import { ModelProviderPricingHistoryItem } from '@/types';

export type ProviderBillingMode =
  | 'token_flat'
  | 'token_tiered'
  | 'per_request'
  | 'per_image'
  | 'inherit_model_default';

export interface ProviderBillingFormValues {
  billing_mode: ProviderBillingMode;
  input_price: string;
  output_price: string;
  per_request_price: string;
  per_image_price: string;
  tiers: Array<{
    max_input_tokens: string;
    input_price: string;
    output_price: string;
    cached_input_price: string;
    cache_creation_input_price: string;
    cached_output_price: string;
  }>;
  cache_billing_enabled: boolean;
  cached_input_price: string;
  cache_creation_input_price: string;
  cached_output_price: string;
}

export function getPriceHistoryFormValues(
  item: ModelProviderPricingHistoryItem
): ProviderBillingFormValues {
  const billingMode = (
    item.resolved_billing_mode ||
    (item.billing_mode === 'inherit_model_default' ? 'token_flat' : item.billing_mode) ||
    'token_flat'
  ) as ProviderBillingMode;

  if (billingMode === 'per_request') {
    return {
      billing_mode: billingMode,
      input_price: '0',
      output_price: '0',
      per_request_price: String(item.resolved_per_request_price ?? item.per_request_price ?? 0),
      per_image_price: '0',
      tiers: [{ max_input_tokens: '', input_price: '0', output_price: '0', cached_input_price: '', cache_creation_input_price: '', cached_output_price: '' }],
      cache_billing_enabled: false,
      cached_input_price: '',
      cache_creation_input_price: '',
      cached_output_price: '',
    };
  }

  if (billingMode === 'per_image') {
    return {
      billing_mode: billingMode,
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: String(item.resolved_per_image_price ?? item.per_image_price ?? 0),
      tiers: [{ max_input_tokens: '', input_price: '0', output_price: '0', cached_input_price: '', cache_creation_input_price: '', cached_output_price: '' }],
      cache_billing_enabled: false,
      cached_input_price: '',
      cache_creation_input_price: '',
      cached_output_price: '',
    };
  }

  if (billingMode === 'token_tiered') {
    const tieredPricing = item.resolved_tiered_pricing ?? item.tiered_pricing;
    return {
      billing_mode: billingMode,
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: '0',
      tiers:
        tieredPricing && tieredPricing.length > 0
          ? tieredPricing.map((tier) => ({
              max_input_tokens:
                tier.max_input_tokens === null || tier.max_input_tokens === undefined
                  ? ''
                  : String(tier.max_input_tokens),
              input_price: String(tier.input_price ?? 0),
              output_price: String(tier.output_price ?? 0),
              cached_input_price:
                tier.cached_input_price === null || tier.cached_input_price === undefined
                  ? ''
                  : String(tier.cached_input_price),
              cache_creation_input_price:
                tier.cache_creation_input_price === null || tier.cache_creation_input_price === undefined
                  ? ''
                  : String(tier.cache_creation_input_price),
              cached_output_price:
                tier.cached_output_price === null || tier.cached_output_price === undefined
                  ? ''
                  : String(tier.cached_output_price),
            }))
          : [{ max_input_tokens: '', input_price: '0', output_price: '0', cached_input_price: '', cache_creation_input_price: '', cached_output_price: '' }],
      cache_billing_enabled: !!item.resolved_cache_billing_enabled,
      cached_input_price: '',
      cache_creation_input_price: '',
      cached_output_price: '',
    };
  }

  return {
    billing_mode: 'token_flat',
    input_price: String(item.resolved_input_price ?? item.input_price ?? 0),
    output_price: String(item.resolved_output_price ?? item.output_price ?? 0),
    per_request_price: '0',
    per_image_price: '0',
    tiers: [{ max_input_tokens: '', input_price: '0', output_price: '0', cached_input_price: '', cache_creation_input_price: '', cached_output_price: '' }],
    cache_billing_enabled: !!item.resolved_cache_billing_enabled,
    cached_input_price:
      item.resolved_cached_input_price === null || item.resolved_cached_input_price === undefined
        ? ''
        : String(item.resolved_cached_input_price),
    cache_creation_input_price:
      item.resolved_cache_creation_input_price === null || item.resolved_cache_creation_input_price === undefined
        ? ''
        : String(item.resolved_cache_creation_input_price),
    cached_output_price:
      item.resolved_cached_output_price === null || item.resolved_cached_output_price === undefined
        ? ''
        : String(item.resolved_cached_output_price),
  };
}
