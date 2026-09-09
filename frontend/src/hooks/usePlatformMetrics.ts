import { useState } from "react";
import { getPlatformSummary } from "../services/traction";

export function usePlatformMetrics() {
  const [metrics, setMetrics] = useState({
    paid_count: 0,
    revenue_usdc: 0,
    available_usdc: 0,
  });

  const loadPlatformSummary = async () => {
    const data = await getPlatformSummary();
    setMetrics({
      paid_count: data.current_paid_count ?? data.paid_count ?? 0,
      revenue_usdc: data.revenue_usdc || 0,
      available_usdc: data.seller_gateway_balance?.available_usdc ?? data.available_usdc ?? 0,
    });
    return data;
  };

  return { metrics, loadPlatformSummary };
}
