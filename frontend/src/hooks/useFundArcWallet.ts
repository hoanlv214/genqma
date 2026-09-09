import { useState, useEffect, useCallback } from "react";
import { getInjectedWallet, shortAddress } from "../services/wallet";
import { extractGatewayBalanceUsdc, getOnChainUsdcBalance } from "../services/gatewayCrypto";

interface UseFundArcWalletOptions {
  wallet: string;
  arcGatewayUrl: string;
}

export function useFundArcWallet({ wallet, arcGatewayUrl }: UseFundArcWalletOptions) {
  const [fundReadinessStatus, setFundReadinessStatus] = useState("Checking");
  const [fundReadinessTone, setFundReadinessTone] = useState("");
  const [fundWalletStatus, setFundWalletStatus] = useState("Not connected");
  const [fundProviderStatus, setFundProviderStatus] = useState("n/a");
  const [fundChainStatus, setFundChainStatus] = useState("n/a");
  const [fundWalletUsdc, setFundWalletUsdc] = useState("n/a");
  const [fundGatewayBalance, setFundGatewayBalance] = useState("n/a");
  const [fundRequiredAmount, setFundRequiredAmount] = useState("n/a");
  const [fundNextStep, setFundNextStep] = useState("Connect wallet first");
  const [fundPrimaryAction, setFundPrimaryAction] = useState({ action: "connect", label: "Connect wallet first" });
  const [fundShowAdvanced, setFundShowAdvanced] = useState(false);

  const refreshFundingReadiness = useCallback(async () => {
    const required = 0.005;
    const requiredLabel = `${required.toFixed(3)} USDC`;
    setFundRequiredAmount(requiredLabel);

    if (!wallet) {
      setFundReadinessStatus("Wallet needed");
      setFundReadinessTone("warn");
      setFundWalletStatus("Not connected");
      setFundProviderStatus("n/a");
      setFundChainStatus("n/a");
      setFundWalletUsdc("n/a");
      setFundGatewayBalance("n/a");
      setFundNextStep("Connect wallet first");
      setFundPrimaryAction({ action: "connect", label: "Connect wallet first" });
      return;
    }

    setFundWalletStatus(shortAddress(wallet));

    let provider = null;
    let chainIdHex = "";
    let isArc = false;
    let chainLabel = "n/a";
    let providerLabel = "Injected Wallet";
    let error: any = null;

    try {
      provider = getInjectedWallet();
      if (provider) {
        const pAny = provider as any;
        if (pAny.isMetaMask) providerLabel = "MetaMask";
        else if (pAny.isRabby) providerLabel = "Rabby";
        else if (pAny.isOKX || pAny.isOKExWallet) providerLabel = "OKX Wallet";
        setFundProviderStatus(providerLabel);

        const rawChainId = await provider.request<string>({ method: "eth_chainId" });
        chainIdHex = String(rawChainId).toLowerCase();
        isArc = chainIdHex === "0x4cef52";
        chainLabel = isArc ? "Arc Testnet" : `Other Network (${chainIdHex})`;
        setFundChainStatus(chainLabel);
      }
    } catch (err) {
      error = err;
      setFundChainStatus("Chain detection failed");
    }

    if (error || !provider) {
      setFundReadinessStatus("Check failed");
      setFundReadinessTone("warn");
      setFundNextStep("Funding status is unavailable. Retry or continue to payment.");
      setFundPrimaryAction({ action: "refresh", label: "Retry readiness check" });
      return;
    }

    if (!isArc) {
      setFundReadinessStatus("Wrong chain");
      setFundReadinessTone("warn");
      setFundNextStep("Add or switch to Arc Testnet. Your wallet will show the network details for approval.");
      setFundPrimaryAction({ action: "switch", label: "Add / Switch Arc Testnet" });
      return;
    }

    try {
      const cleanGatewayUrl = (arcGatewayUrl || "").replace(/\/$/, "");
      const [statusResp, balResp] = await Promise.all([
        fetch(`${cleanGatewayUrl}/api/wallet-status/${wallet}`).catch(() => null),
        fetch(`${cleanGatewayUrl}/api/balance/${wallet}`).catch(() => null),
      ]);

      let walletBal = 0;
      if (statusResp?.ok) {
        const statusData = await statusResp.json();
        const chainBal = getOnChainUsdcBalance(statusData);
        walletBal = chainBal ? Number(chainBal) : 0;
        setFundWalletUsdc(`${walletBal.toFixed(3)} USDC`);
      } else {
        setFundWalletUsdc("n/a");
      }

      let gatewayBal = 0;
      if (balResp?.ok) {
        const balData = await balResp.json();
        gatewayBal = extractGatewayBalanceUsdc(balData) ?? 0;
        setFundGatewayBalance(`${gatewayBal.toFixed(3)} USDC`);
      } else {
        setFundGatewayBalance("n/a");
      }

      if (gatewayBal >= required) {
        setFundReadinessStatus("Ready");
        setFundReadinessTone("ready");
        setFundNextStep("Gateway balance is ready for the selected report.");
        setFundPrimaryAction({ action: "close", label: "Continue to payment" });
      } else if (walletBal + gatewayBal >= required) {
        setFundReadinessStatus("Gateway low");
        setFundReadinessTone("warn");
        setFundNextStep("Continue to payment; QMA will prompt Gateway Deposit");
        setFundPrimaryAction({ action: "close", label: "Continue to payment" });
      } else {
        setFundReadinessStatus("Funding needed");
        setFundReadinessTone("warn");
        setFundNextStep("Use Faucet or CCTP/App Kit, then retry. Arc uses USDC for gas and payment funding.");
        setFundPrimaryAction({ action: "faucet", label: "Open Circle Faucet" });
      }
    } catch (err) {
      setFundReadinessStatus("Check failed");
      setFundReadinessTone("warn");
      setFundNextStep("Funding status is unavailable. Retry or continue to payment.");
      setFundPrimaryAction({ action: "refresh", label: "Retry readiness check" });
    }
  }, [wallet, arcGatewayUrl]);

  useEffect(() => {
    refreshFundingReadiness();
  }, [refreshFundingReadiness]);

  return {
    fundReadinessStatus,
    fundReadinessTone,
    fundWalletStatus,
    fundProviderStatus,
    fundChainStatus,
    fundWalletUsdc,
    fundGatewayBalance,
    fundRequiredAmount,
    fundNextStep,
    fundPrimaryAction,
    fundShowAdvanced,
    setFundShowAdvanced,
    refreshFundingReadiness,
  };
}
