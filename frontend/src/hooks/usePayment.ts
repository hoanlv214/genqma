import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { API_BASE_URL, ApiError } from "../services/api";
import { ensureArcTestnet, getWalletProvider, shortAddress } from "../services/wallet";
import { ARC_CHAIN } from "../config/network";
import { payX402Resource, prepareX402Payment, submitX402Payment, X402PaymentError, type PreparedX402Payment } from "../services/x402";
import { createInvoice, verifyPayment } from "../services/invoices";
import { getProviderReport } from "../services/reports";
import { extractGatewayBalanceUsdc } from "../services/gatewayCrypto";
import type { PaymentStepKey, PaymentStepState } from "../types/qma";
import { normalizeTierForCache } from "../utils/format";

type Signal = Record<string, any>;
type ToastTone = "info" | "success" | "warning" | "error";
type SameAddress = (a?: string, b?: string) => boolean;
type SetCacheRevision = Dispatch<SetStateAction<number>>;

interface UsePaymentOptions {
  wallet: string;
  activeQuery: Signal;
  selectedProviderId: string;
  sellerAddress: string;
  arcGatewayUrl: string;
  sameAddress: SameAddress;
  showToast: (message: string, tone?: ToastTone) => void;
  refreshPendingInvoice: (signal: Signal, tier: "preview" | "full", providerId: string, account: string) => Promise<any>;
  rememberPendingInvoice: (invoice: any, signal: Signal, tier: "preview" | "full", providerId: string, account: string) => void;
  clearPendingInvoice: (signal: Signal, tier: "preview" | "full", providerId: string, account: string) => void;
  normalizeSignalPayload: (source?: Signal) => Signal;
  signalCacheKey: (signal: Signal, tier: "preview" | "full", providerId: string, account?: string) => string;
  setCacheRevision: SetCacheRevision;
}

export function usePayment({
  wallet,
  activeQuery,
  selectedProviderId,
  sellerAddress,
  arcGatewayUrl,
  sameAddress,
  showToast,
  refreshPendingInvoice,
  rememberPendingInvoice,
  clearPendingInvoice,
  normalizeSignalPayload,
  signalCacheKey,
  setCacheRevision,
}: UsePaymentOptions) {
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [currentInvoice, setCurrentInvoice] = useState<any>(null);
  const [paymentStep, setPaymentStep] = useState<PaymentStepKey>("wallet");
  const [paymentStepStatus, setPaymentStepStatus] = useState<Record<PaymentStepKey, { status: PaymentStepState; label: string; detail?: string }>>({
    wallet: { status: "waiting", label: "Waiting" },
    gateway: { status: "waiting", label: "Waiting" },
    settlement: { status: "waiting", label: "Waiting" },
    genlayer: { status: "waiting", label: "Waiting" },
    report: { status: "waiting", label: "Waiting" },
  });
  const [genlayerReceipt, setGenlayerReceipt] = useState<any>(null);
  const [payStatusText, setPayStatusText] = useState("");
  const [payErrorText, setPayErrorText] = useState("");
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [paySubmitting, setPaySubmitting] = useState(false);
  const [paymentDetails, setPaymentDetails] = useState({
    buyerGatewayBalance: "",
    settlementId: "",
    sellerAvailable: "",
    sellerPending: "",
    txHash: "",
    explorerUrl: "",
    genlayerTxHash: "",
    genlayerExplorerUrl: "",
  });
  const [reportDetailsOpen, setReportDetailsOpen] = useState(true);
  const [showDepositModal, setShowDepositModal] = useState(false);
  const [depositAmountInput, setDepositAmountInput] = useState("0.005");
  const [gatewayDepositLoading, setGatewayDepositLoading] = useState(false);
  const [gatewayDepositStatus, setGatewayDepositStatus] = useState("");
  const [unlockedReport, setUnlockedReport] = useState<any>(null);
  const [reportCollapsed, setReportCollapsed] = useState(true);

  const recommendationTierPrice = (pick: any, tier: string, pricing: Record<string, number>) => {
    const baseKey = `${pick.provider_id || "funding_memory"}_${tier}`;
    return pricing[baseKey] || (tier === "preview" ? 0.002 : 0.005);
  };

  const recommendationTier = (pick: any): "preview" | "full" => {
    const tier = String(pick?.tier || pick?.suggested_tier || "").toLowerCase();
    return tier === "full" ? "full" : "preview";
  };

  const openPaywall = async (
    tier: "preview" | "full",
    event?: FormEvent,
    targetQuery?: Signal,
    targetProviderId?: string,
  ) => {
    if (event) event.preventDefault();
    if (!wallet) {
      showToast("Please connect your wallet first.", "warning");
      return;
    }

    const effectiveQuery = targetQuery || activeQuery;
    const effectiveProviderId = targetProviderId || selectedProviderId;

    setPaywallOpen(true);
    setPaymentSuccess(false);
    setPaySubmitting(false);
    setPayErrorText("");
    setUnlockedReport(null);
    setPaymentDetails({
      buyerGatewayBalance: "",
      settlementId: "",
      sellerAvailable: "",
      sellerPending: "",
      txHash: "",
      explorerUrl: "",
      genlayerTxHash: "",
      genlayerExplorerUrl: "",
    });
    setPaymentStep("wallet");
    setPaymentStepStatus({
      wallet: { status: "active", label: "Checking" },
      gateway: { status: "waiting", label: "Waiting" },
      settlement: { status: "waiting", label: "Waiting" },
      genlayer: { status: "waiting", label: "Waiting" },
      report: { status: "waiting", label: "Waiting" },
    });

    try {
      const provider = getWalletProvider();
      if (!provider) throw new Error("Wallet not found.");
      const chainId = await provider.request<string>({ method: "eth_chainId" });
      if (String(chainId).toLowerCase() !== ARC_CHAIN.chainIdHex.toLowerCase()) {
        setPayStatusText(`Switching network to ${ARC_CHAIN.name}...`);
        await ensureArcTestnet(provider);
      }

      setPaymentStepStatus((prev) => ({
        ...prev,
        wallet: { status: "completed", label: "Connected" },
        gateway: { status: "active", label: "Checking" },
      }));
      setPaymentStep("gateway");
      setPayStatusText("Checking pending invoice state...");
      let invoiceData = await refreshPendingInvoice(effectiveQuery, tier, effectiveProviderId, wallet);
      if (invoiceData?.access_status === "expired" || invoiceData?.access_status === "disputed") {
        clearPendingInvoice(effectiveQuery, tier, effectiveProviderId, wallet);
        invoiceData = null;
      }
      if (invoiceData?.status === "paid" && invoiceData.access_token) {
        const fullInvoice = {
          ...invoiceData,
          query: invoiceData.query || effectiveQuery,
          symbol: invoiceData.symbol || effectiveQuery.symbol || (invoiceData.payment_requirement as any)?.symbol,
          evidence_url: invoiceData.evidence_url || invoiceData.query?.evidence_url || effectiveQuery?.evidence_url,
          exchange: invoiceData.exchange || invoiceData.query?.exchange || effectiveQuery?.exchange,
        };
        setCurrentInvoice(fullInvoice);
        if (invoiceData.genlayer) {
          setGenlayerReceipt(invoiceData.genlayer);
        }
        const glTxHash = invoiceData.genlayer?.transaction_hash;
        const glExplorerUrl = glTxHash
          ? `https://explorer-studio-dev.genlayer.com/transactions/${glTxHash}`
          : "";
        setPaymentDetails((prev) => ({
          ...prev,
          settlementId: invoiceData.settlement_id || prev.settlementId,
          txHash: glTxHash || invoiceData.transaction_hash || prev.txHash,
          explorerUrl: glExplorerUrl || invoiceData.explorer_url || prev.explorerUrl,
          genlayerTxHash: glTxHash || "",
          genlayerExplorerUrl: glExplorerUrl,
        }));
        sessionStorage.setItem(`qma_accessToken_${invoiceData.invoice_id}`, invoiceData.access_token);
        setPaymentStepStatus((prev) => ({
          ...prev,
          gateway: { status: "completed", label: "Funded" },
          settlement: { status: "completed", label: "Accepted" },
          genlayer: { status: "completed", label: "SLA Verified" },
          report: { status: "active", label: "Opening" },
        }));
        setPayStatusText("Recovered paid invoice. Opening report...");
        await fetchReportContent(invoiceData.invoice_id, invoiceData.access_token, fullInvoice, effectiveQuery, effectiveProviderId);
        clearPendingInvoice(effectiveQuery, tier, effectiveProviderId, wallet);
        return;
      }

      if (!invoiceData) {
        setPayStatusText("Creating payment invoice...");
        invoiceData = await createInvoice({
          ...effectiveQuery,
          symbol: String(effectiveQuery.symbol || ""),
          provider_id: effectiveProviderId,
          tier,
          buyer_wallet_address: wallet,
        });
      } else {
        showToast(`Resumed invoice ${shortAddress(invoiceData.invoice_id)} from its recorded payment state.`, "info");
      }
      const fullInvoice = {
        ...invoiceData,
        query: invoiceData.query || effectiveQuery,
        symbol: invoiceData.symbol || effectiveQuery.symbol || (invoiceData.payment_requirement as any)?.symbol,
        evidence_url: invoiceData.evidence_url || invoiceData.query?.evidence_url || effectiveQuery?.evidence_url,
        exchange: invoiceData.exchange || invoiceData.query?.exchange || effectiveQuery?.exchange,
      };
      setCurrentInvoice(fullInvoice);
      rememberPendingInvoice(fullInvoice, effectiveQuery, tier, effectiveProviderId, wallet);

      setPayStatusText("Reading Gateway Balance...");
      let gatewayBase = arcGatewayUrl.replace(/\/$/, "");
      if (!gatewayBase && invoiceData.arc_gateway_url) {
        try { gatewayBase = new URL(invoiceData.arc_gateway_url).origin; } catch { gatewayBase = ""; }
      }
      if (!gatewayBase) throw new Error("Arc Gateway URL not configured. Retry or refresh.");
      const balResp = await fetch(`${gatewayBase}/api/balance/${wallet}`);
      if (!balResp.ok) throw new Error("Could not check Gateway Balance");
      const balData = await balResp.json();
      const gatewayBal = extractGatewayBalanceUsdc(balData) ?? 0;
      setPaymentDetails((prev) => ({ ...prev, buyerGatewayBalance: `${gatewayBal.toFixed(6)} USDC` }));

      const invoiceCost = Number(invoiceData.amount);
      if (gatewayBal < invoiceCost) {
        setPayStatusText(`Top Up required: need ${invoiceCost.toFixed(6)} USDC, have ${gatewayBal.toFixed(6)} USDC`);
        setPaymentStepStatus((prev) => ({ ...prev, gateway: { status: "failed", label: "Top Up Needed" } }));
        setPaymentStep("gateway");
        setDepositAmountInput(Math.max(invoiceCost, 0.005).toFixed(6));
        setShowDepositModal(true);
        return;
      }

      if (invoiceData.status === "verification_pending" && invoiceData.settlement_id) {
        if (invoiceData.genlayer) {
          setGenlayerReceipt(invoiceData.genlayer);
        }
        const glTxHash = invoiceData.genlayer?.transaction_hash;
        const glExplorerUrl = glTxHash
          ? `https://explorer-studio-dev.genlayer.com/transactions/${glTxHash}`
          : "";
        setPaymentDetails((prev) => ({
          ...prev,
          settlementId: invoiceData.settlement_id,
          txHash: glTxHash || invoiceData.transaction_hash || prev.txHash,
          explorerUrl: glExplorerUrl || invoiceData.explorer_url || prev.explorerUrl,
          genlayerTxHash: glTxHash || "",
          genlayerExplorerUrl: glExplorerUrl,
        }));
        setPaymentStepStatus((prev) => ({
          ...prev,
          gateway: { status: "completed", label: "Funded" },
          settlement: { status: "completed", label: "Settled" },
          genlayer: { status: "waiting", label: "Retry available" },
        }));
        setPaymentStep("genlayer");
        setPayStatusText("Payment is already settled. Retry GenLayer verification without signing or paying again.");
      } else {
        setPaymentStepStatus((prev) => ({
          ...prev,
          gateway: { status: "completed", label: "Funded" },
          settlement: { status: "active", label: "Sign Settlement" },
        }));
        setPaymentStep("settlement");
        setPayStatusText("Gateway funds confirmed. Ready for settlement signature.");
      }
    } catch (err: any) {
      setPayErrorText(err.message || "Failed to initialize payment.");
      setPaymentStepStatus((prev) => ({ ...prev, wallet: { status: "failed", label: "Failed" } }));
    }
  };

  const waitForTxReceipt = async (hash: string) => {
    const provider = getWalletProvider();
    if (!provider) return;
    for (let i = 0; i < 45; i++) {
      try {
        const rec = await provider.request<any>({ method: "eth_getTransactionReceipt", params: [hash] });
        if (rec) {
          if (rec.status !== "0x1") throw new Error("Transaction reverted.");
          return rec;
        }
      } catch (err: any) {
        // Ignore network errors or RPC rate limits (429) during polling, just wait and retry.
        console.warn("RPC error while waiting for receipt, retrying...", err);
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
    throw new Error("Receipt timeout");
  };

  const saveLocalAction = (type: string, amount: string, hash: string) => {
    try {
      const key = `qma_wallet_events_${wallet.toLowerCase()}`;
      const events = JSON.parse(localStorage.getItem(key) || "[]");
      events.unshift({
        type,
        amount_usdc: amount,
        tx_hash: hash,
        explorer_url: `https://testnet.arcscan.app/tx/${hash}`,
        at: Date.now(),
      });
      localStorage.setItem(key, JSON.stringify(events.slice(0, 50)));
    } catch (err) {
      console.warn("Failed to write local event log", err);
    }
  };

  const handleDepositToGateway = async (
    options: { standalone?: boolean } = {},
  ): Promise<boolean> => {
    if (!wallet) {
      showToast("Please connect your wallet first.", "warning");
      return false;
    }
    const amount = Number(depositAmountInput);
    if (!Number.isFinite(amount) || amount <= 0) {
      showToast("Invalid deposit amount.", "warning");
      return false;
    }

    const invoice = options.standalone ? null : currentInvoice;
    const setDepositProgress = (message: string) => {
      setPayStatusText(message);
      setGatewayDepositStatus(message);
    };
    setDepositProgress("Preparing gateway deposit transaction...");
    setGatewayDepositLoading(true);
    try {
      let gwBase = arcGatewayUrl.replace(/\/$/, "");
      if (!gwBase && invoice?.arc_gateway_url) {
        try { gwBase = new URL(invoice.arc_gateway_url).origin; } catch { gwBase = ""; }
      }
      if (!gwBase) throw new Error("Arc Gateway URL not configured. Retry or refresh.");

      await ensureArcTestnet();

      let startingGatewayBalance = 0;
      const startingBalanceResp = await fetch(`${gwBase}/api/balance/${wallet}`).catch(() => null);
      if (startingBalanceResp?.ok) {
        startingGatewayBalance = extractGatewayBalanceUsdc(await startingBalanceResp.json()) ?? 0;
      }

      const walletStatusResp = await fetch(`${gwBase}/api/wallet-status/${wallet}`);
      const statusData = walletStatusResp.ok ? await walletStatusResp.json() : null;
      const walletBalance = Number(statusData?.usdc?.formatted ?? statusData?.usdcBalance?.formatted);
      if (Number.isFinite(walletBalance) && amount > walletBalance) {
        throw new Error(`Insufficient Arc USDC. Available: ${walletBalance.toFixed(6)} USDC.`);
      }
      const approveDefault = statusData?.defaultApproveUsdc ?? 10;
      const approveAmount = Math.max(approveDefault, amount).toFixed(6);
      const calldataUrl = `${gwBase}/api/deposit-calldata/${wallet}?amount=${amount.toFixed(6)}&approveAmount=${approveAmount}`;
      const calldataResp = await fetch(calldataUrl);
      const data = await calldataResp.json();
      if (!calldataResp.ok) throw new Error(data.error || "Deposit calldata failed");

      const provider = getWalletProvider();
      if (!provider) throw new Error("No wallet injection found.");
      const allowance = Number(statusData?.allowance?.formatted || 0);
      if (allowance < amount) {
        setDepositProgress("Requesting USDC allowance approval in wallet...");
        const appTxHash = await provider.request<string>({ method: "eth_sendTransaction", params: [data.approveTx] });
        setDepositProgress("Waiting for allowance transaction receipt...");
        await waitForTxReceipt(appTxHash);
        saveLocalAction("approve", approveAmount, appTxHash);
      }

      setDepositProgress("Confirm Gateway deposit in your wallet...");
      const depTxHash = await provider.request<string>({ method: "eth_sendTransaction", params: [data.depositTx] });
      setDepositProgress("Waiting for deposit transaction confirmation...");
      await waitForTxReceipt(depTxHash);
      saveLocalAction("deposit", amount.toFixed(6), depTxHash);

      setDepositProgress("Updating gateway balances...");
      const targetBalance = invoice
        ? Math.max(startingGatewayBalance, Number(invoice.amount))
        : startingGatewayBalance + amount;
      let balanceUpdated = false;
      let updatedGatewayBalance = startingGatewayBalance;
      for (let i = 0; i < 30; i++) {
        const check = await fetch(`${gwBase}/api/balance/${wallet}`);
        if (check.ok) {
          const res = await check.json();
          updatedGatewayBalance = extractGatewayBalanceUsdc(res) ?? 0;
          if (updatedGatewayBalance + 0.000001 >= targetBalance) {
            balanceUpdated = true;
            break;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      if (!balanceUpdated) throw new Error("Circle Gateway did not settle balance update in time.");
      setPaymentDetails((prev) => ({ ...prev, buyerGatewayBalance: `${updatedGatewayBalance.toFixed(6)} USDC` }));
      setShowDepositModal(false);
      if (invoice) {
        setPaymentStepStatus((prev) => ({
          ...prev,
          gateway: { status: "completed", label: "Funded" },
          settlement: { status: "active", label: "Sign Settlement" },
        }));
        setPaymentStep("settlement");
        setDepositProgress("Circle deposit successful. Ready to sign settlement.");
      } else {
        setDepositProgress(`Deposited ${amount.toFixed(6)} USDC to Circle Gateway.`);
        showToast(`Gateway deposit confirmed: ${amount.toFixed(6)} USDC.`, "success");
      }
      return true;
    } catch (err: any) {
      showToast(err.message || "Gateway deposit failed.", "error");
      setDepositProgress(err.message || "Deposit failed. Retry.");
      return false;
    } finally {
      setGatewayDepositLoading(false);
    }
  };

  const signAndSettleX402 = async () => {
    if (!currentInvoice || !wallet || paySubmitting) return;
    let settlementId = String(currentInvoice.settlement_id || "");
    setPaySubmitting(true);
    setPayErrorText("");
    setPayStatusText("Requesting EIP-712 payment authorization signature...");
    setPaymentStep("settlement");
    setPaymentStepStatus((prev) => ({ ...prev, settlement: { status: "active", label: "Signing" } }));

    try {
      const splitLegs = Array.isArray(currentInvoice.split_legs) ? currentInvoice.split_legs : [];
      const hasPriorSplitProgress = splitLegs.some((leg: any) => leg.status === "paid" || leg.status === "processing" || leg.settlement_id);
      if (hasPriorSplitProgress) {
        const reconciled = await refreshPendingInvoice(activeQuery, normalizeTierForCache(currentInvoice.tier), currentInvoice.provider_id || selectedProviderId, wallet);
        const processingLeg = (reconciled?.split_legs || []).find((leg: any) => leg.status === "processing");
        if (processingLeg) {
          throw new Error(`The ${processingLeg.role || processingLeg.leg_id} settlement is still being reconciled. Check invoice status before retrying.`);
        }
      }
      const selfRecipientLeg = splitLegs.find((leg: any) => sameAddress(wallet, leg.pay_to));
      if (selfRecipientLeg) {
        throw new Error(`Connected wallet is the ${selfRecipientLeg.role || selfRecipientLeg.leg_id} split recipient (${selfRecipientLeg.pay_to}). Use a separate buyer wallet from the provider or treasury wallet.`);
      }
      const invoiceRecipient = String(currentInvoice.wallet_address || sellerAddress || "");
      if (!splitLegs.length && sameAddress(wallet, invoiceRecipient)) {
        throw new Error(`Connected wallet is the seller wallet (${invoiceRecipient}). Use a separate buyer wallet for report purchases.`);
      }

      const splitSettlements: any[] = splitLegs
        .filter((leg: any) => leg.status === "paid" && leg.settlement_id && leg.sidecar_receipt)
        .map((leg: any) => ({
          leg_id: leg.leg_id,
          settlement_id: leg.settlement_id,
          pay_to: leg.pay_to,
          amount_raw: String(leg.amount_raw),
          sidecar_receipt: leg.sidecar_receipt,
          payer_address: leg.payer_address,
          gateway_status: leg.gateway_status,
        }));
      let paidAmountUsdc: number | undefined;

      if (splitLegs.length) {
        let workingSplitLegs = splitLegs;
        const paidLegIds = new Set(splitSettlements.map((item) => item.leg_id));
        const pendingLegs = splitLegs.filter((leg: any) => !paidLegIds.has(leg.leg_id) && leg.status !== "paid");
        const preparedLegs: Array<{ leg: any; prepared: PreparedX402Payment }> = [];
        for (const leg of pendingLegs) {
          setPayStatusText(`Signing ${leg.role || leg.leg_id} split leg...`);
          preparedLegs.push({ leg, prepared: await prepareX402Payment(leg.resource, wallet) });
        }
        const settlementResults = await Promise.allSettled(
          preparedLegs.map(({ prepared }) => submitX402Payment(prepared)),
        );
        const failedLegs: Array<{ leg: any; reason: unknown }> = [];
        settlementResults.forEach((result, index) => {
          const leg = preparedLegs[index].leg;
          if (result.status === "rejected") {
            failedLegs.push({ leg, reason: result.reason });
            return;
          }
          const paidLeg = result.value;
          const legSettlementId = paidLeg.settlement_id || paidLeg.settlementId;
          if (!legSettlementId || !paidLeg.sidecar_receipt) throw new Error(`Split leg ${leg.leg_id} did not return a settlement receipt.`);
          splitSettlements.push({
            leg_id: paidLeg.leg_id || leg.leg_id,
            settlement_id: legSettlementId,
            pay_to: paidLeg.pay_to || leg.pay_to,
            amount_raw: String(paidLeg.amount_raw || leg.amount_raw),
            sidecar_receipt: paidLeg.sidecar_receipt,
            payer_address: paidLeg.payer,
            gateway_status: paidLeg.gateway_status,
          });
          workingSplitLegs = workingSplitLegs.map((item: any) => item.leg_id === (paidLeg.leg_id || leg.leg_id)
            ? { ...item, status: "paid", settlement_id: legSettlementId, sidecar_receipt: paidLeg.sidecar_receipt, payer_address: paidLeg.payer || item.payer_address, gateway_status: paidLeg.gateway_status || item.gateway_status }
            : item);
          const updatedInvoice = { ...currentInvoice, split_legs: workingSplitLegs };
          setCurrentInvoice(updatedInvoice);
          rememberPendingInvoice(updatedInvoice, activeQuery, normalizeTierForCache(updatedInvoice.tier), updatedInvoice.provider_id || selectedProviderId, wallet);
          saveLocalAction("x402_split_leg", String(paidLeg.amount_usdc || leg.amount_usdc || currentInvoice.amount), legSettlementId);
        });
        if (failedLegs.length) {
          // Reconcile before retrying. A timeout can mean Circle settled and
          // the response was lost; signing a new authorization would risk a
          // second payment. The cached invoice is already persisted, so this
          // status request is safe and can recover any leg recorded by QMA.
          const invoiceQuery = currentInvoice?.query || activeQuery;
          const invoiceProviderId = currentInvoice?.provider_id || selectedProviderId;
          const reconciled = await refreshPendingInvoice(invoiceQuery, normalizeTierForCache(currentInvoice.tier), invoiceProviderId, wallet);
          const reconciledLegs = Array.isArray(reconciled?.split_legs) ? reconciled.split_legs : [];
          for (const reconciledLeg of reconciledLegs) {
            if (reconciledLeg.status !== "paid" || !reconciledLeg.settlement_id || !reconciledLeg.sidecar_receipt) continue;
            const alreadyIncluded = splitSettlements.some((item) => item.leg_id === reconciledLeg.leg_id);
            if (!alreadyIncluded) {
              splitSettlements.push({
                leg_id: reconciledLeg.leg_id,
                settlement_id: reconciledLeg.settlement_id,
                pay_to: reconciledLeg.pay_to,
                amount_raw: String(reconciledLeg.amount_raw),
                payer_address: reconciledLeg.payer_address,
                gateway_status: reconciledLeg.gateway_status,
                sidecar_receipt: reconciledLeg.sidecar_receipt,
              });
            }
          }
          workingSplitLegs = workingSplitLegs.map((item: any) => reconciledLegs.find((candidate: any) => candidate.leg_id === item.leg_id) || item);
          const updatedInvoice = {
            ...(reconciled || currentInvoice),
            split_legs: workingSplitLegs,
            query: invoiceQuery,
            symbol: currentInvoice?.symbol || (currentInvoice?.payment_requirement as any)?.symbol,
          };
          setCurrentInvoice(updatedInvoice);
          rememberPendingInvoice(updatedInvoice, invoiceQuery, normalizeTierForCache(updatedInvoice.tier), invoiceProviderId, wallet);
          const unresolved = failedLegs.filter(({ leg }) => {
            const reconciledLeg = workingSplitLegs.find((item: any) => item.leg_id === leg.leg_id);
            return !(reconciledLeg?.status === "paid" && reconciledLeg.settlement_id && reconciledLeg.sidecar_receipt);
          });
          if (unresolved.length) {
            const uncertain = failedLegs.some(({ reason }) => reason instanceof X402PaymentError && reason.outcomeUncertain);
            throw new Error(uncertain
              ? "Settlement outcome is uncertain. Payment state was checked; retry only after the invoice status is known."
              : `Could not settle ${unresolved.map(({ leg }) => leg.role || leg.leg_id).join(", ")} split leg. Retry the remaining leg.`);
          }
        }
      } else {
        if (currentInvoice.settlement_id) {
          settlementId = currentInvoice.settlement_id;
          paidAmountUsdc = Number(currentInvoice.amount);
        } else {
          const paidData = await payX402Resource(currentInvoice.arc_gateway_url, wallet);
          settlementId = paidData.settlement_id || paidData.settlementId;
          paidAmountUsdc = Number(paidData.amount_usdc || currentInvoice.amount);
          if (!settlementId) throw new Error("Arc Gateway did not return a settlement id.");
          saveLocalAction("x402_settlement", String(paidAmountUsdc || currentInvoice.amount), settlementId);
        }
      }

      setPaymentStep("genlayer");
      setPaymentStepStatus((prev) => ({
        ...prev,
        settlement: { status: "completed", label: "Settled" },
        genlayer: { status: "active", label: "Consensus SLA" },
        report: { status: "waiting", label: "Waiting" },
      }));
      setPayStatusText("Settlement confirmed. Verifying the bound report with the GenLayer Intelligent Contract...");
      showToast("Settlement confirmed. Verifying the bound report with the GenLayer Intelligent Contract...", "info");

      let verifyData: any = await verifyPayment(currentInvoice.invoice_id, {
        invoice_secret: currentInvoice.invoice_secret,
        payer_address: wallet,
        ...(settlementId ? { settlement_id: settlementId, amount_usdc: paidAmountUsdc } : {}),
        ...(splitSettlements.length ? { split_settlements: splitSettlements } : {}),
      });

      let glReceipt = verifyData.genlayer;
      setGenlayerReceipt(glReceipt);

      // Rejection blocks access. Refund is a separate Arc payout state and
      // must never be inferred from the GenLayer verdict alone.
      if (verifyData.status === "verification_rejected" || glReceipt?.verdict === "INVALID") {
        setPaymentStepStatus((prev) => ({
          ...prev,
          genlayer: { status: "failed", label: "SLA Violated" },
          report: { status: "failed", label: "Access Blocked" },
        }));
        setPayStatusText("");
        setPayErrorText(
          `GenLayer validators rejected this report: ${glReceipt?.reasoning || "The report did not match authoritative evidence"}. Access is blocked and no report was issued. ${verifyData.status === "refunded" || verifyData.arc_settlement?.status === "confirmed"
            ? "The full payment has been refunded to the settlement payer."
            : "The full refund is being processed on Arc; completion will be shown only after Circle confirms it."
          }`
        );
        showToast("GenLayer Shield rejected the report. Access remains blocked.", "error");
        clearPendingInvoice(activeQuery, normalizeTierForCache(currentInvoice.tier), currentInvoice.provider_id || selectedProviderId, wallet);
        return;
      }

      // If GenLayer verification is still pending on-chain, poll until finalized
      if (
        !verifyData?.access_token &&
        (verifyData?.status === "verification_pending" ||
          glReceipt?.status === "VERIFICATION_PENDING" ||
          glReceipt?.verdict === "PENDING")
      ) {
        setPaymentStep("genlayer");
        setPaymentStepStatus((prev) => ({
          ...prev,
          settlement: { status: "completed", label: "Settled" },
          genlayer: { status: "active", label: "Consensus SLA" },
          report: { status: "waiting", label: "Waiting" },
        }));
        setPayStatusText("Settlement confirmed. GenLayer multi-validator consensus is finalizing on-chain...");
        showToast("GenLayer consensus in progress. Awaiting validator finalization...", "info");

        const maxPollAttempts = 15;
        for (let attempt = 1; attempt <= maxPollAttempts; attempt++) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
          try {
            const pollData: any = await verifyPayment(currentInvoice.invoice_id, {
              invoice_secret: currentInvoice.invoice_secret,
              payer_address: wallet,
              ...(settlementId ? { settlement_id: settlementId, amount_usdc: paidAmountUsdc } : {}),
              ...(splitSettlements.length ? { split_settlements: splitSettlements } : {}),
            });

            if (pollData) {
              verifyData = pollData;
              if (pollData.genlayer) {
                glReceipt = pollData.genlayer;
                setGenlayerReceipt(glReceipt);
              }

              if (pollData.status === "verification_rejected" || glReceipt?.verdict === "INVALID") {
                setPaymentStepStatus((prev) => ({
                  ...prev,
                  genlayer: { status: "failed", label: "SLA Violated" },
                  report: { status: "failed", label: "Access Blocked" },
                }));
                setPayStatusText("");
                setPayErrorText(`GenLayer validators rejected this report: ${glReceipt?.reasoning || "Failed validation"}. Access blocked.`);
                showToast("GenLayer Shield rejected the report.", "error");
                clearPendingInvoice(activeQuery, normalizeTierForCache(currentInvoice.tier), currentInvoice.provider_id || selectedProviderId, wallet);
                return;
              }

              if (pollData.access_token) {
                break;
              }
            }
          } catch (pollErr: any) {
            if (pollErr instanceof ApiError && pollErr.status === 503) {
              continue;
            }
            console.warn("GenLayer poll attempt failed:", pollErr);
          }
        }
      }

      if (!verifyData?.access_token) {
        if (
          verifyData?.status === "verification_pending" ||
          glReceipt?.status === "VERIFICATION_PENDING" ||
          glReceipt?.verdict === "PENDING"
        ) {
          const pendingInvoice = {
            ...currentInvoice,
            status: "verification_pending",
            settlement_id: settlementId,
          };
          setCurrentInvoice(pendingInvoice);
          rememberPendingInvoice(
            pendingInvoice,
            activeQuery,
            normalizeTierForCache(pendingInvoice.tier),
            pendingInvoice.provider_id || selectedProviderId,
            wallet,
          );
          setPaymentStep("genlayer");
          setPaymentStepStatus((prev) => ({
            ...prev,
            settlement: { status: "completed", label: "Settled" },
            genlayer: { status: "waiting", label: "In Progress" },
            report: { status: "waiting", label: "Locked" },
          }));
          setPayStatusText("");
          setPayErrorText("Settlement confirmed on Arc! GenLayer validator consensus is still finalizing. Click 'Unlock Report' to complete verification without any new payment. If validators ultimately reject the report, the full payment is refunded automatically.");
          return;
        }
        throw new Error("QMA verification did not return an access token.");
      }

      setPaymentStepStatus((prev) => ({
        ...prev,
        settlement: { status: "completed", label: "Settled" },
        genlayer: { status: "completed", label: "SLA Verified" },
        report: { status: "completed", label: "Unlocked" },
      }));

      // Refresh buyer gateway balance to reflect the new post-settlement balance
      try {
        let gwBase = arcGatewayUrl.replace(/\/$/, "");
        if (!gwBase && currentInvoice?.arc_gateway_url) {
          try { gwBase = new URL(currentInvoice.arc_gateway_url).origin; } catch { gwBase = ""; }
        }
        if (gwBase && wallet) {
          const balResp = await fetch(`${gwBase}/api/balance/${wallet}`);
          if (balResp.ok) {
            const balData = await balResp.json();
            const newBal = extractGatewayBalanceUsdc(balData);
            if (newBal != null) {
              setPaymentDetails((prev) => ({ ...prev, buyerGatewayBalance: `${newBal.toFixed(6)} USDC` }));
            }
          }
        }
      } catch (balErr) {
        console.warn("Failed to refresh balance after settlement", balErr);
      }

      const glTxHash = glReceipt?.transaction_hash;
      const glExplorerUrl = glTxHash
        ? `https://explorer-studio-dev.genlayer.com/transactions/${glTxHash}`
        : "";

      setPaymentDetails((prev) => ({
        ...prev,
        settlementId: verifyData.settlement_id || settlementId || splitSettlements.map((item: any) => item.settlement_id).join(", "),
        sellerAvailable: verifyData.seller_gateway_available_usdc != null ? `${Number(verifyData.seller_gateway_available_usdc).toFixed(6)} USDC` : prev.sellerAvailable,
        sellerPending: verifyData.seller_gateway_pending_batch_usdc != null ? `${Number(verifyData.seller_gateway_pending_batch_usdc).toFixed(6)} USDC` : prev.sellerPending,
        txHash: glTxHash || verifyData.transaction_hash || prev.txHash,
        explorerUrl: glExplorerUrl || verifyData.explorer_url || prev.explorerUrl,
        genlayerTxHash: glTxHash || "",
        genlayerExplorerUrl: glExplorerUrl,
      }));
      setPayStatusText(
        glTxHash
          ? `GenLayer finalized VALID verdict (Tx: ${shortAddress(glTxHash)}). Report unlocked.`
          : "GenLayer returned a finalized VALID verdict for this report hash. Report unlocked."
      );
      setPaymentSuccess(true);
      if (glTxHash) {
        showToast(`GenLayer SLA Verified! Tx: ${shortAddress(glTxHash)}`, "success");
      } else {
        showToast("GenLayer SLA Verified! Report unlocked.", "success");
      }
      sessionStorage.setItem(`qma_accessToken_${currentInvoice.invoice_id}`, verifyData.access_token);
      const invoiceQuery = currentInvoice?.query || activeQuery;
      const invoiceProviderId = currentInvoice?.provider_id || selectedProviderId;
      await fetchReportContent(
        currentInvoice.invoice_id,
        verifyData.access_token,
        currentInvoice,
        invoiceQuery,
        invoiceProviderId,
      );
      clearPendingInvoice(invoiceQuery, normalizeTierForCache(currentInvoice.tier), invoiceProviderId, wallet);
    } catch (err: any) {
      if (
        (err instanceof ApiError && err.status === 503 && settlementId) ||
        (settlementId && err?.message && err.message.includes("access token"))
      ) {
        const pendingInvoice = {
          ...currentInvoice,
          status: "verification_pending",
          settlement_id: settlementId,
        };
        setCurrentInvoice(pendingInvoice);
        rememberPendingInvoice(
          pendingInvoice,
          activeQuery,
          normalizeTierForCache(pendingInvoice.tier),
          pendingInvoice.provider_id || selectedProviderId,
          wallet,
        );
        setPaymentStep("genlayer");
        setPaymentStepStatus((prev) => ({
          ...prev,
          settlement: { status: "completed", label: "Settled" },
          genlayer: { status: "waiting", label: "Retry available" },
          report: { status: "waiting", label: "Locked" },
        }));
        setPayErrorText("Payment is settled, but GenLayer has not returned a finalized verdict yet. Retry verification; no new signature or payment is required.");
        return;
      }
      setPayErrorText(err.message || "Settlement signature cancelled or failed.");
      setPaymentStepStatus((prev) => ({ ...prev, settlement: { status: "failed", label: "Failed" } }));
    } finally {
      setPaySubmitting(false);
    }
  };

  const fetchReportContent = async (
    invoiceId: string,
    accessToken: string,
    invoiceOverride?: any,
    queryOverride?: Signal,
    providerOverride?: string,
  ) => {
    try {
      const invoiceForReport = invoiceOverride || currentInvoice;
      const baseQuery = queryOverride || invoiceForReport?.query || activeQuery;
      const invoiceSymbol = invoiceForReport?.symbol || invoiceForReport?.payment_requirement?.symbol;
      const reportQuery = {
        ...baseQuery,
        ...(invoiceSymbol ? { symbol: invoiceSymbol } : {}),
      };
      const providerForReport = invoiceForReport?.provider_id || providerOverride || selectedProviderId;
      const reportData = await getProviderReport({
        providerId: providerForReport,
        tier: invoiceForReport?.tier === "preview" ? "preview" : "full",
        invoiceId,
        accessToken,
        query: reportQuery as any,
      });

      const normalizedReportQuery = normalizeSignalPayload(reportQuery);
      const reportTier = normalizeTierForCache(invoiceForReport.tier);
      const cachedReportData = {
        ...reportData,
        invoice: reportData.invoice || invoiceForReport,
        provider_id: reportData.provider_id || providerForReport,
        tier: reportData.tier || reportTier,
        query: reportData.query || normalizedReportQuery,
      };
      setUnlockedReport(cachedReportData);
      setReportCollapsed(false);
      const key = signalCacheKey(normalizedReportQuery, reportTier, providerForReport);
      localStorage.setItem(key, JSON.stringify({
        saved_at: Date.now(),
        signal: normalizedReportQuery,
        tier: reportTier,
        provider_id: providerForReport,
        payer_address: wallet,
        invoice: invoiceForReport,
        report: cachedReportData,
      }));
      setCacheRevision((value) => value + 1);
    } catch (err: any) {
      showToast("Failed to load report contents: " + err.message, "error");
    }
  };

  const handleOpenUnlockedReport = () => {
    setPaywallOpen(false);
    setReportCollapsed(false);
  };

  return {
    paywallOpen,
    setPaywallOpen,
    currentInvoice,
    setCurrentInvoice,
    paymentStep,
    paymentStepStatus,
    payStatusText,
    payErrorText,
    paymentSuccess,
    paySubmitting,
    paymentDetails,
    reportDetailsOpen,
    setReportDetailsOpen,
    showDepositModal,
    setShowDepositModal,
    depositAmountInput,
    setDepositAmountInput,
    gatewayDepositLoading,
    gatewayDepositStatus,
    setGatewayDepositStatus,
    unlockedReport,
    setUnlockedReport,
    reportCollapsed,
    setReportCollapsed,
    openPaywall,
    signAndSettleX402,
    handleDepositToGateway,
    waitForTxReceipt,
    fetchReportContent,
    handleOpenUnlockedReport,
    recommendationTierPrice,
    recommendationTier,
    saveLocalAction,
    genlayerReceipt,
  };
}
