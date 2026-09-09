import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { listProviders } from "../services/providers";
import type { Provider } from "../types/qma";

interface UseProvidersOptions {
  activeQuery: Record<string, any>;
  setActiveQuery: Dispatch<SetStateAction<Record<string, any>>>;
}

const DEFAULT_PROVIDERS: Provider[] = [
  {
    provider_id: "funding_memory",
    provider_name: "Funding Memory (MEXC Futures)",
    category: "crypto_funding",
    description: "MEXC futures funding anomaly memory",
    owner_wallet: "0x23e7c029a287a83d80b2e084e008211658dda11d",
    ui_schema: {
      fields: [
        { key: "fundingRate", label: "Funding Rate", type: "number", default: -0.0025 },
        { key: "marketCap", label: "Market Cap ($)", type: "number", default: 10000000 },
        { key: "circRatio", label: "Circulating Ratio", type: "number", default: 0.65 },
        { key: "fromATH", label: "Distance from ATH (%)", type: "number", default: -50 },
        { key: "volume24h", label: "24h Volume ($)", type: "number", default: 2000000 },
      ],
    },
  },
  {
    provider_id: "oi_memory",
    provider_name: "OI Memory (MEXC Open Interest)",
    category: "crypto_funding",
    description: "MEXC open interest crowding memory",
    owner_wallet: "0x23e7c029a287a83d80b2e084e008211658dda11d",
    ui_schema: {
      fields: [
        { key: "openInterest", label: "Open Interest ($)", type: "number", default: 5000000 },
        { key: "marketCap", label: "Market Cap ($)", type: "number", default: 10000000 },
        { key: "circRatio", label: "Circulating Ratio", type: "number", default: 0.65 },
        { key: "fromATH", label: "Distance from ATH (%)", type: "number", default: -50 },
        { key: "volume24h", label: "24h Volume ($)", type: "number", default: 2000000 },
      ],
    },
  },
];

export function useProviders({ activeQuery, setActiveQuery }: UseProvidersOptions) {
  const [selectedProviderId, setSelectedProviderId] = useState("funding_memory");
  const [providers, setProviders] = useState<Provider[]>(DEFAULT_PROVIDERS);

  const loadProviders = async () => {
    try {
      const data = await listProviders();
      setProviders((data.providers as unknown as Provider[]) || []);
    } catch (err) {
      console.warn("Failed to load providers list", err);
    }
  };

  useEffect(() => {
    loadProviders();
  }, []);

  const handleProviderChange = (providerId: string) => {
    setSelectedProviderId(providerId);
    const target = providers.find((provider) => provider.provider_id === providerId);
    if (target?.ui_schema?.fields) {
      const fieldsQuery: Record<string, any> = { symbol: activeQuery.symbol || "HYPE" };
      target.ui_schema.fields.forEach((field) => {
        fieldsQuery[field.key] = field.default !== undefined ? field.default : "";
      });
      setActiveQuery(fieldsQuery);
    }
  };

  return {
    providers,
    selectedProviderId,
    setSelectedProviderId,
    loadProviders,
    handleProviderChange,
  };
}
