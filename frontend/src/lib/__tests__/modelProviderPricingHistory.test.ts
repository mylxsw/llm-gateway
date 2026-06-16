import { describe, expect, it } from 'vitest';
import { getPriceHistoryFormValues } from '../modelProviderPricingHistory';
import { ModelProviderPricingHistoryItem } from '@/types';

describe('getPriceHistoryFormValues', () => {
  it('uses resolved model billing when history item inherits model default', () => {
    const item = {
      id: 1,
      requested_model: 'gpt-4o-mini',
      provider_id: 2,
      provider_name: 'test',
      target_model_name: 'gpt-4o-mini',
      billing_mode: 'inherit_model_default',
      input_price: null,
      output_price: null,
      resolved_billing_mode: 'token_flat',
      resolved_input_price: 0.15,
      resolved_output_price: 0.6,
      resolved_cache_billing_enabled: true,
      resolved_cached_input_price: 0.05,
      resolved_cached_output_price: 0.2,
      resolved_cache_creation_input_price: 0.075,
      priority: 0,
      weight: 1,
      is_active: true,
      created_at: '2026-04-24T00:00:00Z',
      updated_at: '2026-04-24T00:00:00Z',
    } satisfies Partial<ModelProviderPricingHistoryItem> as ModelProviderPricingHistoryItem;

    expect(getPriceHistoryFormValues(item)).toEqual({
      billing_mode: 'token_flat',
      input_price: '0.15',
      output_price: '0.6',
      per_request_price: '0',
      per_image_price: '0',
      tiers: [{ max_input_tokens: '', input_price: '0', output_price: '0', cached_input_price: '', cache_creation_input_price: '', cached_output_price: '' }],
      cache_billing_enabled: true,
      cached_input_price: '0.05',
      cache_creation_input_price: '0.075',
      cached_output_price: '0.2',
    });
  });

  it('uses resolved tiered pricing when history item inherits a tiered model config', () => {
    const item = {
      id: 1,
      requested_model: 'gpt-5',
      provider_id: 2,
      provider_name: 'test',
      target_model_name: 'gpt-5',
      billing_mode: 'inherit_model_default',
      resolved_billing_mode: 'token_tiered',
      resolved_tiered_pricing: [
        {
          max_input_tokens: 1000,
          input_price: 1,
          output_price: 2,
          cached_input_price: 0.5,
          cache_creation_input_price: 0.75,
          cached_output_price: 1,
        },
      ],
      resolved_cache_billing_enabled: true,
      priority: 0,
      weight: 1,
      is_active: true,
      created_at: '2026-04-24T00:00:00Z',
      updated_at: '2026-04-24T00:00:00Z',
    } satisfies Partial<ModelProviderPricingHistoryItem> as ModelProviderPricingHistoryItem;

    expect(getPriceHistoryFormValues(item)).toEqual({
      billing_mode: 'token_tiered',
      input_price: '0',
      output_price: '0',
      per_request_price: '0',
      per_image_price: '0',
      tiers: [
        {
          max_input_tokens: '1000',
          input_price: '1',
          output_price: '2',
          cached_input_price: '0.5',
          cache_creation_input_price: '0.75',
          cached_output_price: '1',
        },
      ],
      cache_billing_enabled: true,
      cached_input_price: '',
      cache_creation_input_price: '',
      cached_output_price: '',
    });
  });
});
