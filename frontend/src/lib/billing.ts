/**
 * Billing utility functions for model type-specific billing mode filtering
 * and billing submit data construction.
 */

export type BillingMode = 'token_flat' | 'token_tiered' | 'per_request' | 'per_image';

/**
 * Returns the allowed billing modes for a given model type.
 * - chat / embedding: token_flat, token_tiered, per_request
 * - images: per_image, token_flat
 * - undefined (no model type): all modes (for backwards compat)
 */
export function getBillingModesForModelType(modelType?: string): BillingMode[] {
  if (modelType === 'images') {
    return ['per_image', 'token_flat'];
  }
  if (modelType === 'chat' || modelType === 'embedding') {
    return ['per_request', 'token_flat', 'token_tiered'];
  }
  // No model type specified → show all (e.g. in bulk upgrade dialog)
  return ['per_request', 'per_image', 'token_flat', 'token_tiered'];
}

export interface BillingSubmitData {
  billing_mode: BillingMode | null;
  input_price: number | null;
  output_price: number | null;
  per_request_price: number | null;
  per_image_price: number | null;
  tiered_pricing: Array<{
    max_input_tokens: number | null;
    input_price: number;
    output_price: number;
    cached_input_price?: number | null;
    cached_output_price?: number | null;
  }> | null;
  cache_billing_enabled: boolean | null;
  cached_input_price: number | null;
  cached_output_price: number | null;
}

interface BillingFormValues {
  billing_mode: BillingMode;
  input_price: string;
  output_price: string;
  per_request_price: string;
  per_image_price: string;
  tiers: Array<{ max_input_tokens: string; input_price: string; output_price: string; cached_input_price: string; cached_output_price: string }>;
  cache_billing_enabled: boolean;
  cached_input_price: string;
  cached_output_price: string;
}

/**
 * Builds billing submit data from form values.
 * Returns null-ed fields for billing modes that don't apply.
 */
export function buildBillingSubmitData(
  values: BillingFormValues,
  supportsBilling: boolean,
): BillingSubmitData {
  if (!supportsBilling) {
    return {
      billing_mode: null,
      input_price: null,
      output_price: null,
      per_request_price: null,
      per_image_price: null,
      tiered_pricing: null,
      cache_billing_enabled: null,
      cached_input_price: null,
      cached_output_price: null,
    };
  }

  const mode = values.billing_mode;

  if (mode === 'per_request') {
    const perReq = values.per_request_price.trim();
    return {
      billing_mode: mode,
      per_request_price: perReq ? Number(perReq) : 0,
      per_image_price: null,
      input_price: null,
      output_price: null,
      tiered_pricing: null,
      cache_billing_enabled: null,
      cached_input_price: null,
      cached_output_price: null,
    };
  }

  if (mode === 'per_image') {
    const perImg = values.per_image_price.trim();
    return {
      billing_mode: mode,
      per_image_price: perImg ? Number(perImg) : 0,
      per_request_price: null,
      input_price: null,
      output_price: null,
      tiered_pricing: null,
      cache_billing_enabled: null,
      cached_input_price: null,
      cached_output_price: null,
    };
  }

  if (mode === 'token_tiered') {
    return {
      billing_mode: mode,
      tiered_pricing: (values.tiers || []).map((t) => {
        const maxStr = t.max_input_tokens.trim();
        return {
          max_input_tokens: maxStr === '' ? null : Number(maxStr),
          input_price: Number(t.input_price || '0'),
          output_price: Number(t.output_price || '0'),
          cached_input_price: values.cache_billing_enabled && t.cached_input_price.trim()
            ? Number(t.cached_input_price) : null,
          cached_output_price: values.cache_billing_enabled && t.cached_output_price.trim()
            ? Number(t.cached_output_price) : null,
        };
      }),
      per_request_price: null,
      per_image_price: null,
      input_price: null,
      output_price: null,
      cache_billing_enabled: values.cache_billing_enabled || null,
      cached_input_price: null,
      cached_output_price: null,
    };
  }

  // token_flat
  const inputPrice = values.input_price.trim();
  const outputPrice = values.output_price.trim();
  return {
    billing_mode: mode,
    input_price: inputPrice ? Number(inputPrice) : 0,
    output_price: outputPrice ? Number(outputPrice) : 0,
    per_request_price: null,
    per_image_price: null,
    tiered_pricing: null,
    cache_billing_enabled: values.cache_billing_enabled || null,
    cached_input_price: values.cache_billing_enabled && values.cached_input_price.trim()
      ? Number(values.cached_input_price) : null,
    cached_output_price: values.cache_billing_enabled && values.cached_output_price.trim()
      ? Number(values.cached_output_price) : null,
  };
}
