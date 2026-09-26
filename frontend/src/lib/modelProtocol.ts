/**
 * Model type / provider protocol compatibility.
 *
 * Mirrors `is_model_type_protocol_compatible` in
 * `backend/app/common/provider_protocols.py`. The backend is the source of
 * truth and rejects an incompatible binding on save; this copy exists so the
 * UI can avoid offering the invalid combination in the first place.
 */

import type { ModelType } from '@/types/model';
import type { ProtocolType } from '@/types/provider';

/**
 * Model type that must be served by the Jev protocol. The model type and the
 * protocol deliberately share the name: a Jev model is exactly a model served
 * over the Jev protocol.
 */
export const JEV_MODEL_TYPE = 'jev';
export const JEV_PROTOCOL = 'jev';

/** Providers whose protocol resolves to Jev, keyed by frontend protocol name. */
function isJevProtocol(protocol: ProtocolType | null | undefined): boolean {
  return (protocol ?? '').toLowerCase().trim() === JEV_PROTOCOL;
}

function normalizeModelType(modelType: ModelType | null | undefined): string {
  return (modelType ?? 'chat').toLowerCase().trim();
}

/**
 * Whether a model of `modelType` may be served by a `protocol` provider.
 *
 * Jev has no conversion path to or from the chat-oriented protocols, so a Jev
 * model must be bound to a Jev provider and a Jev provider must only serve Jev
 * models. Every other combination stays unconstrained.
 */
export function isModelTypeProtocolCompatible(
  modelType: ModelType | null | undefined,
  protocol: ProtocolType | null | undefined,
): boolean {
  return (normalizeModelType(modelType) === JEV_MODEL_TYPE) === isJevProtocol(protocol);
}

/** Filter a provider list down to the ones that can serve `modelType`. */
export function filterProvidersForModelType<T extends { protocol: ProtocolType }>(
  providers: T[],
  modelType: ModelType | null | undefined,
): T[] {
  return providers.filter((provider) =>
    isModelTypeProtocolCompatible(modelType, provider.protocol),
  );
}
