import { useEffect, useMemo, useState } from "react";
import { getProviderStats, claimCreatorEarnings } from "../services/providers";
import { submitWithdrawal } from "../services/invoices";
import { ensureArcTestnet, getWalletProvider } from "../services/wallet";
import {
  buildCreatorClaimMessage,
  buildGatewayWithdrawIntent,
  buildGatewayWithdrawTypedData,
  encodeGatewayMintCalldata,
  randomHexNonce,
  utf8ToHex,
} from "../services/gatewayCrypto";
import type { Provider } from "../types/qma";

const WITHDRAW_FEE_RESERVE_USDC = 0.0035;

type ToastTone = "info" | "success" | "warning" | "error";
type SameAddress = (a?: string, b?: string) => boolean;
type LoadQuickProfileData = () => Promise<void>;
type WaitForTxReceipt = (hash: string) => Promise<any>;
type SaveLocalAction = (type: string, amount: string, hash: string) => void;

interface UseProviderEarningsOptions {
  wallet: string;
  ownedProviders: Provider[];
  sameAddress: SameAddress;
  creatorClaimConfig: any;
  paymentNetworkName: string;
  gatewayContractAddress: string;
  gatewayMinterAddress: string;
  arcUsdcAddress: string;
  withdrawMode: string;
  loadQuickProfileData: LoadQuickProfileData;
  waitForTxReceipt: WaitForTxReceipt;
  saveLocalAction: SaveLocalAction;
  showToast: (message: string, tone?: ToastTone) => void;
}

export function useProviderEarnings({
  wallet,
  ownedProviders,
  sameAddress,
  creatorClaimConfig,
  paymentNetworkName,
  gatewayContractAddress,
  gatewayMinterAddress,
  arcUsdcAddress,
  withdrawMode,
  loadQuickProfileData,
  waitForTxReceipt,
  saveLocalAction,
  showToast,
}: UseProviderEarningsOptions) {
  const [showProviderEarningsModal, setShowProviderEarningsModal] = useState(false);
  const [providerEarningsLoading, setProviderEarningsLoading] = useState(false);
  const [providerEarningsError, setProviderEarningsError] = useState("");
  const [providerEarningsStats, setProviderEarningsStats] = useState<any[]>([]);
  const [selectedProviderEarningsIds, setSelectedProviderEarningsIds] = useState<string[]>([]);
  const [creatorClaimSubmitting, setCreatorClaimSubmitting] = useState(false);
  const [providerWithdrawAmount, setProviderWithdrawAmount] = useState("");
  const [providerWithdrawSubmitting, setProviderWithdrawSubmitting] = useState(false);

  const fetchProviderEarningsStats = async () => {
    const stats = await Promise.all(ownedProviders.map(async (provider) => {
      try {
        const data = await getProviderStats(provider.provider_id);
        return data.stats || data;
      } catch (err) {
        console.warn(`Provider stats unavailable for ${provider.provider_id}`, err);
        return {
          provider_id: provider.provider_id,
          provider_name: provider.provider_name || provider.provider_id,
          revenue_wallet: provider.revenue_wallet,
          creator_claimable_usdc: 0,
          creator_earned_usdc: 0,
          revenue_usdc: 0,
          creator_share_bps: provider.revenue_share_bps || 0,
          withdrawal_mode: "unavailable",
          split_note: "Stats endpoint is unavailable for this provider.",
        };
      }
    }));
    return stats;
  };

  const providerIdsFromStats = (stats: any[]) => stats.map((item) => item.provider_id).filter(Boolean).sort();

  const syncProviderEarningsSelection = (stats: any[], mode: "all" | "preserve" = "preserve") => {
    const nextIds = providerIdsFromStats(stats);
    setSelectedProviderEarningsIds((current) => {
      if (mode === "all") return nextIds;
      const valid = new Set(nextIds);
      const kept = current.filter((providerId) => valid.has(providerId));
      return kept.length ? kept : nextIds;
    });
  };

  const toggleProviderEarningsSelection = (providerId: string) => {
    setSelectedProviderEarningsIds((current) => {
      if (current.includes(providerId)) return current.filter((item) => item !== providerId);
      return [...current, providerId].sort();
    });
  };

  const refreshProviderEarningsModal = async () => {
    setProviderEarningsLoading(true);
    setProviderEarningsError("");
    try {
      const stats = await fetchProviderEarningsStats();
      setProviderEarningsStats(stats);
      syncProviderEarningsSelection(stats);
    } catch (err: any) {
      setProviderEarningsError(err?.message || "Could not refresh creator earnings.");
    } finally {
      setProviderEarningsLoading(false);
    }
  };

  const openProviderEarningsModal = async () => {
    if (!wallet) {
      showToast("Connect your creator wallet first.", "warning");
      return;
    }
    if (!ownedProviders.length) {
      showToast("This wallet is not registered as a provider owner.", "warning");
      return;
    }
    setShowProviderEarningsModal(true);
    setProviderEarningsLoading(true);
    setProviderEarningsError("");
    try {
      const stats = await fetchProviderEarningsStats();
      setProviderEarningsStats(stats);
      syncProviderEarningsSelection(stats, "all");
    } catch (err: any) {
      setProviderEarningsError(err?.message || "Could not load creator earnings.");
    } finally {
      setProviderEarningsLoading(false);
    }
  };

  const submitCreatorClaim = async () => {
    if (!wallet) {
      showToast("Connect your creator wallet first.", "warning");
      return;
    }
    const selectedStats = providerEarningsStats.filter((item) => selectedProviderEarningsIds.includes(item.provider_id));
    if (!selectedStats.length) {
      setProviderEarningsError("Select at least one provider to claim.");
      return;
    }
    const claimableStats = selectedStats.filter((item) => Number(item.creator_claimable_usdc || 0) > 0);
    const providerIds = claimableStats.map((item) => item.provider_id).filter(Boolean).sort();
    const totalClaimable = claimableStats.reduce((sum, item) => sum + Number(item.creator_claimable_usdc || 0), 0);
    if (!providerIds.length) {
      setProviderEarningsError("Selected providers have no creator ledger earnings to claim.");
      return;
    }
    if (totalClaimable <= 0) {
      setProviderEarningsError("No creator ledger earnings are available to claim.");
      return;
    }
    if (!creatorClaimConfig?.configured) {
      setProviderEarningsError(creatorClaimConfig?.error || "Creator claim payout executor is not configured yet.");
      return;
    }
    const provider = getWalletProvider();
    if (!provider?.request) {
      setProviderEarningsError("EVM wallet provider required for claim signature.");
      return;
    }
    setCreatorClaimSubmitting(true);
    setProviderEarningsError("");
    try {
      const nonce = randomHexNonce();
      const issuedAt = Math.floor(Date.now() / 1000);
      const message = buildCreatorClaimMessage({
        claimant: wallet,
        providerIds,
        amountUsdc: totalClaimable,
        nonce,
        issuedAt,
        network: paymentNetworkName,
      });
      showToast("Sign the creator claim intent in your wallet.", "info");
      const signature = await provider.request<string>({ method: "personal_sign", params: [utf8ToHex(message), wallet] });
      const data = await claimCreatorEarnings({ claimant_address: wallet, provider_ids: providerIds, amount_usdc: totalClaimable.toFixed(6), nonce, issued_at: issuedAt, signature });
      const claim = data.claim || {};
      const txHash = claim.transaction_hash || claim.tx_hash;
      if (txHash) saveLocalAction("creator_claim", Number(claim.amount_usdc || totalClaimable).toFixed(6), txHash);
      showToast(`Creator claim paid: ${Number(claim.amount_usdc || totalClaimable).toFixed(6)} USDC`, "success");
      await refreshProviderEarningsModal();
    } catch (err: any) {
      console.warn("Creator claim failed", err);
      setProviderEarningsError(err?.message || "Creator claim failed.");
      showToast(err?.message || "Creator claim failed.", "error");
    } finally {
      setCreatorClaimSubmitting(false);
    }
  };

  const selectedProviderEarningsStats = useMemo(() => {
    const selectedIds = new Set(selectedProviderEarningsIds);
    return providerEarningsStats.filter((item) => selectedIds.has(item.provider_id));
  }, [providerEarningsStats, selectedProviderEarningsIds]);

  const allProviderEarningsSelected = providerEarningsStats.length > 0 && selectedProviderEarningsStats.length === providerEarningsStats.length;

  const providerEarningsTotals = useMemo(() => {
    const scopedStats = selectedProviderEarningsStats;
    const totalClaimable = scopedStats.reduce((sum, item) => sum + Number(item.creator_claimable_usdc || 0), 0);
    const totalDirectSettled = scopedStats.reduce((sum, item) => item.withdrawal_mode === "direct_gateway_split" ? sum + Number(item.creator_earned_usdc || 0) : sum, 0);
    const gatewayBalancesByWallet = new Map<string, any>();
    scopedStats.filter((item) => item.withdrawal_mode === "direct_gateway_split" && item.creator_gateway_balance).forEach((item) => {
      const balance = item.creator_gateway_balance;
      const balanceAddress = balance.address || item.revenue_wallet || wallet || item.provider_id;
      gatewayBalancesByWallet.set(String(balanceAddress).toLowerCase(), { ...balance, withdraw_address: balanceAddress });
    });
    const gatewayBalances = Array.from(gatewayBalancesByWallet.values());
    const withdrawableGatewayBalances = gatewayBalances.filter((item) => sameAddress(item.withdraw_address || item.address, wallet));
    const externalGatewayAvailable = gatewayBalances.filter((item) => !sameAddress(item.withdraw_address || item.address, wallet)).reduce((sum, item) => sum + Number(item.available_usdc || 0), 0);
    const gatewayAvailable = withdrawableGatewayBalances.reduce((sum, item) => sum + Number(item.available_usdc || 0), 0);
    const gatewayPending = withdrawableGatewayBalances.reduce((sum, item) => sum + Number(item.pending_batch_usdc || 0), 0);
    const hasDirectSplit = scopedStats.some((item) => item.withdrawal_mode === "direct_gateway_split");
    return { totalClaimable, totalDirectSettled, gatewayAvailable, gatewayPending, hasDirectSplit, externalGatewayAvailable, hasExternalGatewayBalance: externalGatewayAvailable > 0 };
  }, [selectedProviderEarningsStats, wallet]);

  const providerGatewayWithdrawMax = useMemo(() => Math.max(0, providerEarningsTotals.gatewayAvailable - WITHDRAW_FEE_RESERVE_USDC), [providerEarningsTotals.gatewayAvailable]);
  const providerWithdrawDisplayAmount = useMemo(() => {
    const amount = Number(providerWithdrawAmount);
    return Number.isFinite(amount) && amount > 0 ? amount : providerGatewayWithdrawMax;
  }, [providerGatewayWithdrawMax, providerWithdrawAmount]);

  useEffect(() => {
    if (!showProviderEarningsModal) {
      setProviderWithdrawAmount("");
      return;
    }
    const suggested = providerGatewayWithdrawMax > 0 ? providerGatewayWithdrawMax.toFixed(6) : "";
    setProviderWithdrawAmount((current) => {
      const currentNumber = Number(current);
      if (!current || !Number.isFinite(currentNumber) || currentNumber > providerGatewayWithdrawMax) return suggested;
      return current;
    });
  }, [showProviderEarningsModal, providerGatewayWithdrawMax]);

  const submitProviderGatewayWithdraw = async () => {
    if (!wallet) return setProviderEarningsError("Connect your creator wallet first.");
    if (!providerEarningsTotals.hasDirectSplit) return setProviderEarningsError("No direct Gateway split provider is available for this wallet.");
    if (!gatewayContractAddress) return setProviderEarningsError("Circle Gateway contract address is unknown. Refresh config and try again.");
    if (providerEarningsTotals.hasExternalGatewayBalance && providerEarningsTotals.gatewayAvailable <= 0) return setProviderEarningsError("Connect the provider revenue wallet to withdraw its direct Gateway balance.");
    const amount = Number(providerWithdrawAmount);
    if (!Number.isFinite(amount) || amount <= 0 || amount > providerGatewayWithdrawMax) return setProviderEarningsError(`Enter an amount between 0 and ${providerGatewayWithdrawMax.toFixed(6)} USDC.`);
    const provider = getWalletProvider();
    if (!provider?.request) return setProviderEarningsError("EVM wallet provider required for Gateway withdrawal.");

    const useRelayer = ["platform_relayed", "relayed", "gasless"].includes(String(withdrawMode || "").toLowerCase());
    setProviderWithdrawSubmitting(true);
    setProviderEarningsError("");
    try {
      if (!useRelayer) await ensureArcTestnet();
      const burnIntent = buildGatewayWithdrawIntent(amount, { gatewayContractAddress, gatewayMinterAddress, arcUsdcAddress, wallet });
      showToast("Sign the Gateway withdrawal intent in your wallet.", "info");
      const signature = await provider.request<string>({ method: "eth_signTypedData_v4", params: [wallet, JSON.stringify(buildGatewayWithdrawTypedData(burnIntent))] });
      const submitResult = await submitWithdrawal({ burnIntent, signature });
      if (submitResult.relayed) {
        const txHash = submitResult.mintTxHash || submitResult.transaction_hash;
        if (!txHash) throw new Error("Relayer completed but did not return a mint transaction hash.");
        saveLocalAction("withdraw", amount.toFixed(6), txHash);
        showToast(`Gateway withdrawal relayed: ${amount.toFixed(6)} USDC`, "success");
      } else {
        if (!submitResult.attestation || !submitResult.signature) throw new Error("Circle Gateway did not return a mint attestation. Withdrawal transaction was not sent.");
        const txHash = await provider.request<string>({ method: "eth_sendTransaction", params: [{ from: wallet, to: gatewayMinterAddress, data: encodeGatewayMintCalldata(submitResult.attestation, submitResult.signature), gas: "0x493e0" }] });
        await waitForTxReceipt(txHash);
        saveLocalAction("withdraw", amount.toFixed(6), txHash);
        showToast(`Gateway withdrawal completed: ${amount.toFixed(6)} USDC`, "success");
      }
      await Promise.all([
        refreshProviderEarningsModal(),
        loadQuickProfileData().catch((err) => console.warn("Quick profile refresh after withdraw failed", err)),
      ]);
    } catch (err: any) {
      console.warn("Gateway withdrawal failed", err);
      setProviderEarningsError(err?.message || "Gateway withdrawal failed.");
      showToast(err?.message || "Gateway withdrawal failed.", "error");
    } finally {
      setProviderWithdrawSubmitting(false);
    }
  };

  return {
    showProviderEarningsModal,
    setShowProviderEarningsModal,
    providerEarningsLoading,
    providerEarningsError,
    providerEarningsStats,
    selectedProviderEarningsIds,
    creatorClaimSubmitting,
    providerWithdrawSubmitting,
    selectedProviderEarningsStats,
    allProviderEarningsSelected,
    providerEarningsTotals,
    providerGatewayWithdrawMax,
    providerWithdrawDisplayAmount,
    fetchProviderEarningsStats,
    providerIdsFromStats,
    syncProviderEarningsSelection,
    toggleProviderEarningsSelection,
    openProviderEarningsModal,
    refreshProviderEarningsModal,
    submitCreatorClaim,
    submitProviderGatewayWithdraw,
  };
}
