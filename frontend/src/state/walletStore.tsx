import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { clearAllWalletProfileSessions } from "../services/walletProfileSession";

interface WalletState {
  address: string;
  setAddress: (address: string) => void;
  disconnect: () => void;
}

const WalletContext = createContext<WalletState | null>(null);

export function WalletProvider({ children }: { children: ReactNode }) {
  const [address, setAddressState] = useState(() => localStorage.getItem("qma_connected_wallet") || "");

  const value = useMemo<WalletState>(
    () => ({
      address,
      setAddress(next) {
        setAddressState(next);
        if (next) localStorage.setItem("qma_connected_wallet", next);
        else localStorage.removeItem("qma_connected_wallet");
      },
      disconnect() {
        setAddressState("");
        localStorage.removeItem("qma_connected_wallet");
        clearAllWalletProfileSessions();
      },
    }),
    [address],
  );

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}

export function useWalletStore() {
  const value = useContext(WalletContext);
  if (!value) throw new Error("useWalletStore must be used inside WalletProvider.");
  return value;
}
