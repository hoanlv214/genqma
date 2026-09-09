import { useEffect, useRef, useState } from "react";
import { quotePrice } from "../services/invoices";

interface UseQuoteOptions {
  activeQuery: Record<string, any>;
  selectedProviderId: string;
}

export function useQuote({ activeQuery, selectedProviderId }: UseQuoteOptions) {
  const [quotedPrices, setQuotedPrices] = useState<Record<string, number>>({});
  const quoteTimer = useRef<any>(null);

  const scheduleQuoteRefresh = () => {
    clearTimeout(quoteTimer.current);
    quoteTimer.current = setTimeout(async () => {
      try {
        const tiers = ["preview", "full"];
        const results = await Promise.all(
          tiers.map(async (tier) => {
            try {
              const resData = await quotePrice({
                ...activeQuery,
                provider_id: selectedProviderId,
                tier,
              });
              return [tier, Number(resData.amount_usdc)];
            } catch {
              return [tier, null];
            }
          })
        );
        const nextQuotes: Record<string, number> = {};
        results.forEach(([tier, value]) => {
          if (tier && value !== null) nextQuotes[tier as string] = value as number;
        });
        setQuotedPrices(nextQuotes);
      } catch (err) {
        console.warn("Quote refresh failed", err);
      }
    }, 400);
  };

  useEffect(() => {
    if (activeQuery?.symbol) {
      scheduleQuoteRefresh();
    }
  }, [activeQuery, selectedProviderId]);

  return {
    quotedPrices,
    quoteTimer,
    scheduleQuoteRefresh,
  };
}
