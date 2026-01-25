import { useProviderProtocols } from '@/lib/hooks';
import { ProviderProtocolConfig, ProtocolType } from '@/types/provider';

export function useProviderProtocolConfigs(options?: { enabled?: boolean }) {
  const { data, ...rest } = useProviderProtocols(options);
  return {
    configs: data ?? [],
    ...rest,
  };
}

export function getProviderProtocolConfig(
  protocol: ProtocolType | undefined,
  configs: ProviderProtocolConfig[]
) {
  if (!protocol) return undefined;
  return configs.find((config) => config.protocol === protocol);
}

export function getProviderProtocolLabel(
  protocol: ProtocolType | undefined,
  configs: ProviderProtocolConfig[]
) {
  return getProviderProtocolConfig(protocol, configs)?.label ?? protocol ?? '';
}
