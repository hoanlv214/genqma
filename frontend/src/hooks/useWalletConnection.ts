import { useEffect, useMemo } from "react";
import { clearAllWalletProfileSessions, clearWalletProfileSession } from "../services/walletProfileSession";
import { useWalletStore } from "../state/walletStore";
import type { Provider } from "../types/qma";

type ToastTone = "info" | "success" | "warning" | "error";

interface UseWalletConnectionOptions {
  providers: Provider[];
  selectedProviderId: string;
  adminAddress: string;
  sellerAddress: string;
  showToast: (message: string, tone?: ToastTone) => void;
}

export function useWalletConnection({
  providers,
  selectedProviderId,
  adminAddress,
  sellerAddress,
  showToast,
}: UseWalletConnectionOptions) {
  const { address: wallet, setAddress, disconnect: disconnectWallet } = useWalletStore();

  useEffect(() => {
    // Silently check if the browser wallet is already connected/authorized
    if (window.ethereum?.request) {
      window.ethereum
        .request({ method: "eth_accounts" })
        .then((accounts: any) => {
          if (Array.isArray(accounts) && accounts[0]) {
            setAddress(String(accounts[0]).toLowerCase());
          }
        })
        .catch(() => {
          // Silent fallback: keep existing localStorage address
        });
    }

    const handleAccountsChanged = (accounts: any) => {
      const next = accounts && accounts[0] ? String(accounts[0]).toLowerCase() : "";
      if (next !== wallet?.toLowerCase()) {
        clearAllWalletProfileSessions();
        setAddress(next);
      }
    };

    if (window.ethereum?.on) {
      window.ethereum.on("accountsChanged", handleAccountsChanged);
    }

    return () => {
      if (window.ethereum?.removeListener) {
        window.ethereum.removeListener("accountsChanged", handleAccountsChanged);
      }
    };
  }, [setAddress, wallet]);

  const sameAddress = (a?: string, b?: string) => {
    return Boolean(a && b && String(a).toLowerCase() === String(b).toLowerCase());
  };

  const ownedProviders = useMemo(() => {
    if (!wallet) return [];
    return providers.filter((provider) =>
      [provider.owner_wallet, provider.revenue_wallet]
        .filter(Boolean)
        .some((address) => sameAddress(address, wallet))
    );
  }, [providers, wallet]);

  const activeProvider = useMemo(() => {
    return providers.find((provider) => provider.provider_id === selectedProviderId);
  }, [providers, selectedProviderId]);

  const walletRole = useMemo(() => {
    const normalized = wallet.toLowerCase();
    if (!normalized) return { label: "Buyer", className: "role-buyer" };
    if (adminAddress && normalized === adminAddress.toLowerCase()) return { label: "Admin", className: "role-admin" };
    if (sellerAddress && normalized === sellerAddress.toLowerCase()) return { label: "Treasury", className: "role-treasury" };
    const ownedProvider = ownedProviders[0];
    if (ownedProvider) return { label: "Provider", className: "role-creator" };
    return { label: "Buyer", className: "role-buyer" };
  }, [adminAddress, ownedProviders, sellerAddress, wallet]);

  const connect = async () => {
    if (!window.ethereum?.request) {
      showToast("EVM wallet provider required.", "error");
      return;
    }
    try {
      const accounts = (await window.ethereum.request({ method: "eth_requestAccounts" })) as any;
      const next = accounts && accounts[0] ? String(accounts[0]).toLowerCase() : "";
      setAddress(next);
      if (next) {
        showToast("Wallet connected.", "success");
      }
    } catch (err: any) {
      showToast(err.message || "Connection failed", "error");
    }
  };

  const disconnect = () => {
    if (wallet) clearWalletProfileSession(wallet);
    disconnectWallet();
    showToast("Wallet disconnected. Private profile session cleared.", "info");
  };

  return {
    wallet,
    connect,
    disconnect,
    sameAddress,
    walletRole,
    ownedProviders,
    activeProvider,
  };
}
