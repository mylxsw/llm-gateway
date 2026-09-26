import { describe, expect, it } from 'vitest';

import {
  filterProvidersForModelType,
  isModelTypeProtocolCompatible,
} from '../modelProtocol';
import type { ModelType } from '@/types/model';

describe('isModelTypeProtocolCompatible', () => {
  it('pairs a jev model with a jev provider', () => {
    expect(isModelTypeProtocolCompatible('jev', 'jev')).toBe(true);
  });

  it.each(['openai', 'openai_responses', 'anthropic', 'gemini', 'deepseek'])(
    'rejects a jev model on the %s protocol',
    (protocol) => {
      expect(isModelTypeProtocolCompatible('jev', protocol)).toBe(false);
    },
  );

  it.each(['chat', 'embedding', 'images', 'speech', 'transcription'] as ModelType[])(
    'rejects a %s model on a jev provider',
    (modelType) => {
      expect(isModelTypeProtocolCompatible(modelType, 'jev')).toBe(false);
    },
  );

  it('leaves every non-jev combination unconstrained', () => {
    expect(isModelTypeProtocolCompatible('chat', 'openai')).toBe(true);
    expect(isModelTypeProtocolCompatible('embedding', 'anthropic')).toBe(true);
    expect(isModelTypeProtocolCompatible('images', 'gemini')).toBe(true);
  });

  it('defaults a missing model type to chat', () => {
    expect(isModelTypeProtocolCompatible(undefined, 'openai')).toBe(true);
    expect(isModelTypeProtocolCompatible(undefined, 'jev')).toBe(false);
    expect(isModelTypeProtocolCompatible(null, 'jev')).toBe(false);
  });

  it('normalizes case and padding', () => {
    expect(isModelTypeProtocolCompatible('JEV' as ModelType, '  jev ')).toBe(true);
    expect(isModelTypeProtocolCompatible('jev', 'JEV')).toBe(true);
  });

  it('treats an unknown protocol as non-jev', () => {
    expect(isModelTypeProtocolCompatible('jev', 'bogus')).toBe(false);
    expect(isModelTypeProtocolCompatible('chat', 'bogus')).toBe(true);
    expect(isModelTypeProtocolCompatible('jev', '')).toBe(false);
  });
});

describe('filterProvidersForModelType', () => {
  const providers = [
    { id: 1, name: 'openai-prod', protocol: 'openai' },
    { id: 2, name: 'typesafe', protocol: 'jev' },
    { id: 3, name: 'claude', protocol: 'anthropic' },
  ];

  it('keeps only jev providers for a jev model', () => {
    expect(filterProvidersForModelType(providers, 'jev').map((p) => p.id)).toEqual([2]);
  });

  it('drops jev providers for a chat model', () => {
    expect(filterProvidersForModelType(providers, 'chat').map((p) => p.id)).toEqual([
      1, 3,
    ]);
  });

  it('returns an empty list when nothing matches', () => {
    const onlyChat = [{ id: 1, name: 'openai-prod', protocol: 'openai' }];
    expect(filterProvidersForModelType(onlyChat, 'jev')).toEqual([]);
  });

  it('does not mutate the input', () => {
    const input = [...providers];
    filterProvidersForModelType(input, 'jev');
    expect(input).toHaveLength(3);
  });
});
