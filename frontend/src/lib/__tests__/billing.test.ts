import { describe, it, expect } from 'vitest';
import { getBillingModesForModelType, buildBillingSubmitData } from '../billing';

describe('getBillingModesForModelType', () => {
  it('chat model has token_flat, token_tiered, per_request but not per_image', () => {
    const modes = getBillingModesForModelType('chat');
    expect(modes).toContain('token_flat');
    expect(modes).toContain('token_tiered');
    expect(modes).toContain('per_request');
    expect(modes).not.toContain('per_image');
  });

  it('embedding model has same modes as chat', () => {
    const modes = getBillingModesForModelType('embedding');
    expect(modes).toContain('token_flat');
    expect(modes).toContain('token_tiered');
    expect(modes).toContain('per_request');
    expect(modes).not.toContain('per_image');
  });

  it('images model has per_image and token_flat only', () => {
    const modes = getBillingModesForModelType('images');
    expect(modes).toContain('per_image');
    expect(modes).toContain('token_flat');
    expect(modes).not.toContain('per_request');
    expect(modes).not.toContain('token_tiered');
  });

  it('undefined model type returns all modes', () => {
    const modes = getBillingModesForModelType(undefined);
    expect(modes).toContain('per_request');
    expect(modes).toContain('per_image');
    expect(modes).toContain('token_flat');
    expect(modes).toContain('token_tiered');
  });

  it('speech model type returns all modes (not a billing type)', () => {
    const modes = getBillingModesForModelType('speech');
    expect(modes).toContain('per_request');
    expect(modes).toContain('per_image');
    expect(modes).toContain('token_flat');
    expect(modes).toContain('token_tiered');
  });
});

describe('buildBillingSubmitData', () => {
  const baseValues = {
    billing_mode: 'token_flat' as const,
    input_price: '5.0',
    output_price: '15.0',
    per_request_price: '0.05',
    per_image_price: '0.04',
    tiers: [{ max_input_tokens: '32768', input_price: '1.0', output_price: '2.0' }],
  };

  it('non-billing model type returns all nulls', () => {
    const result = buildBillingSubmitData(baseValues, false);
    expect(result.billing_mode).toBeNull();
    expect(result.input_price).toBeNull();
    expect(result.output_price).toBeNull();
    expect(result.per_request_price).toBeNull();
    expect(result.per_image_price).toBeNull();
    expect(result.tiered_pricing).toBeNull();
  });

  it('token_flat sets input/output price and nullifies others', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'token_flat' },
      true,
    );
    expect(result.billing_mode).toBe('token_flat');
    expect(result.input_price).toBe(5.0);
    expect(result.output_price).toBe(15.0);
    expect(result.per_request_price).toBeNull();
    expect(result.per_image_price).toBeNull();
    expect(result.tiered_pricing).toBeNull();
  });

  it('per_request sets per_request_price and nullifies others', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'per_request' },
      true,
    );
    expect(result.billing_mode).toBe('per_request');
    expect(result.per_request_price).toBe(0.05);
    expect(result.per_image_price).toBeNull();
    expect(result.input_price).toBeNull();
    expect(result.output_price).toBeNull();
    expect(result.tiered_pricing).toBeNull();
  });

  it('per_image sets per_image_price and nullifies others', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'per_image' },
      true,
    );
    expect(result.billing_mode).toBe('per_image');
    expect(result.per_image_price).toBe(0.04);
    expect(result.per_request_price).toBeNull();
    expect(result.input_price).toBeNull();
    expect(result.output_price).toBeNull();
    expect(result.tiered_pricing).toBeNull();
  });

  it('token_tiered builds tiered_pricing and nullifies others', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'token_tiered' },
      true,
    );
    expect(result.billing_mode).toBe('token_tiered');
    expect(result.tiered_pricing).toEqual([
      { max_input_tokens: 32768, input_price: 1.0, output_price: 2.0 },
    ]);
    expect(result.per_request_price).toBeNull();
    expect(result.per_image_price).toBeNull();
    expect(result.input_price).toBeNull();
    expect(result.output_price).toBeNull();
  });

  it('token_tiered with empty max_input_tokens sets null', () => {
    const result = buildBillingSubmitData(
      {
        ...baseValues,
        billing_mode: 'token_tiered',
        tiers: [{ max_input_tokens: '', input_price: '3.0', output_price: '4.0' }],
      },
      true,
    );
    expect(result.tiered_pricing).toEqual([
      { max_input_tokens: null, input_price: 3.0, output_price: 4.0 },
    ]);
  });

  it('token_flat with empty input_price defaults to 0', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'token_flat', input_price: '', output_price: '' },
      true,
    );
    expect(result.input_price).toBe(0);
    expect(result.output_price).toBe(0);
  });

  it('per_request with empty price defaults to 0', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'per_request', per_request_price: '' },
      true,
    );
    expect(result.per_request_price).toBe(0);
  });

  it('per_image with empty price defaults to 0', () => {
    const result = buildBillingSubmitData(
      { ...baseValues, billing_mode: 'per_image', per_image_price: '' },
      true,
    );
    expect(result.per_image_price).toBe(0);
  });
});
