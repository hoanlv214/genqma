import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { extractGatewayBalanceUsdc, getOnChainUsdcBalance } from "../services/gatewayCrypto";
import { getWalletSummary, getWalletPayments } from "../services/walletProfileSession";

interface UseQuickProfileOptions {
  wallet: string;
  arcGatewayUrl: string;
  showProfileModal: boolean;
  setShowProfileModal: Dispatch<SetStateAction<boolean>>;
}

export function useQuickProfile({
  wallet,
  arcGatewayUrl,
  showProfileModal,
  setShowProfileModal,
}: UseQuickProfileOptions) {
  const [profileChainUsdc, setProfileChainUsdc] = useState("n/a");
  const [profileGatewayUsdc, setProfileGatewayUsdc] = useState("n/a");
  const [profileReportsCount, setProfileReportsCount] = useState(0);
  const [profileTotalSpent, setProfileTotalSpent] = useState("0.00 USDC");
  const [profilePurchasedSymbols, setProfilePurchasedSymbols] = useState<string[]>([]);
  const [profileVerifiedPayments, setProfileVerifiedPayments] = useState<any[]>([]);
  const [profileVerifiedPaymentsPage, setProfileVerifiedPaymentsPage] = useState(1);
  const [profileVerifiedPaymentsTotalPages, setProfileVerifiedPaymentsTotalPages] = useState(1);
  const [profilePaymentsLoading, setProfilePaymentsLoading] = useState(false);
  const [profilePaymentsError, setProfilePaymentsError] = useState("");

  const openQuickProfileModal = () => {
    setProfileVerifiedPaymentsPage(1);
    setProfileChainUsdc("loading...");
    setProfileGatewayUsdc("loading...");
    setProfileReportsCount(0);
    setProfileTotalSpent("loading...");
    setProfilePurchasedSymbols([]);
    setProfileVerifiedPayments([]);
    setProfilePaymentsError("");
    setShowProfileModal(true);
  };

  const loadQuickProfileData = async () => {
    if (!wallet) return;
    const account = wallet;
    const page = profileVerifiedPaymentsPage;
    setProfilePaymentsLoading(true);
    setProfilePaymentsError("");

    const cleanGatewayUrl = arcGatewayUrl.replace(/\/$/, "");
    if (cleanGatewayUrl) {
      try {
        const statusResp = await fetch(`${cleanGatewayUrl}/api/wallet-status/${account}`);
        if (statusResp.ok) {
          const statusData = await statusResp.json();
          const chainBal = getOnChainUsdcBalance(statusData);
          setProfileChainUsdc(chainBal ? `${Number(chainBal).toFixed(6)} USDC` : "0.000000 USDC");
        } else {
          setProfileChainUsdc("n/a");
        }
      } catch (err) {
        console.warn("Failed to load quick profile wallet status", err);
        setProfileChainUsdc("n/a");
      }

      try {
        const balResp = await fetch(`${cleanGatewayUrl}/api/balance/${account}`);
        if (balResp.ok) {
          const balData = await balResp.json();
          const formattedGatewayBal = extractGatewayBalanceUsdc(balData) ?? 0;
          setProfileGatewayUsdc(`${formattedGatewayBal.toFixed(6)} USDC`);
        } else {
          setProfileGatewayUsdc("n/a");
        }
      } catch (err) {
        console.warn("Failed to load quick profile gateway balance", err);
        setProfileGatewayUsdc("n/a");
      }
    } else {
      setProfileChainUsdc("n/a");
      setProfileGatewayUsdc("n/a");
    }

    try {
      const summaryData = await getWalletSummary(account);
      setProfileReportsCount(summaryData.current_payments ?? summaryData.payments ?? 0);
      setProfileTotalSpent(`${Number(summaryData.spent_usdc || 0).toFixed(3)} USDC`);
      setProfilePurchasedSymbols(Array.isArray(summaryData.purchased_symbols) ? summaryData.purchased_symbols : []);
    } catch (err) {
      console.warn("Failed to load quick profile summary", err);
    }

    try {
      const paymentsData = await getWalletPayments(account, page, 10);
      const rows = paymentsData.recent_payments || paymentsData.payments || [];
      const pageMeta = paymentsData.recent_payments_page || paymentsData.meta || {};
      setProfileVerifiedPayments(Array.isArray(rows) ? rows : []);
      setProfileVerifiedPaymentsTotalPages(Number(pageMeta.total_pages || pageMeta.pages || 1));
    } catch (err) {
      console.warn("Failed to load quick profile payments", err);
      setProfileVerifiedPayments([]);
      setProfilePaymentsError("Could not load verified payments.");
    } finally {
      setProfilePaymentsLoading(false);
    }
  };

  useEffect(() => {
    if (showProfileModal) {
      loadQuickProfileData();
    }
  }, [showProfileModal, profileVerifiedPaymentsPage]);

  return {
    profileChainUsdc,
    profileGatewayUsdc,
    profileReportsCount,
    profileTotalSpent,
    profilePurchasedSymbols,
    profileVerifiedPayments,
    profileVerifiedPaymentsPage,
    profileVerifiedPaymentsTotalPages,
    profilePaymentsLoading,
    profilePaymentsError,
    setProfileVerifiedPaymentsPage,
    loadQuickProfileData,
    openQuickProfileModal,
  };
}
