import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  fetchOwnerAgentWallet,
  type AgentWalletDetails,
} from "../services/agentWallet";
import { useWalletStore } from "./walletStore";

interface AgentWalletState {
  agentWallet: AgentWalletDetails | null;
  loading: boolean;
  error: string;
  refresh: (options?: { silent?: boolean }) => Promise<AgentWalletDetails | null>;
}

const AgentWalletContext = createContext<AgentWalletState | null>(null);

export function AgentWalletProvider({
  children,
  enabled = true,
}: {
  children: ReactNode;
  enabled?: boolean;
}) {
  const { address: ownerWallet } = useWalletStore();
  const [agentWallet, setAgentWallet] = useState<AgentWalletDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestVersion = useRef(0);

  const refresh = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!enabled || !ownerWallet) {
      requestVersion.current += 1;
      setAgentWallet(null);
      setLoading(false);
      setError("");
      return null;
    }

    const version = ++requestVersion.current;
    if (!silent) setLoading(true);

    try {
      const nextWallet = await fetchOwnerAgentWallet(ownerWallet);
      if (version === requestVersion.current) {
        setAgentWallet(nextWallet);
        setError("");
      }
      return nextWallet;
    } catch (err) {
      if (version === requestVersion.current) {
        setError(err instanceof Error ? err.message : "Agent Wallet data is unavailable.");
      }
      return null;
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [enabled, ownerWallet]);

  useEffect(() => {
    setAgentWallet(null);
    setError("");

    if (!enabled || !ownerWallet) {
      requestVersion.current += 1;
      setLoading(false);
      return;
    }

    void refresh();
    const interval = window.setInterval(() => {
      void refresh({ silent: true });
    }, 15_000);

    return () => {
      requestVersion.current += 1;
      window.clearInterval(interval);
    };
  }, [enabled, ownerWallet, refresh]);

  const value = useMemo<AgentWalletState>(
    () => ({ agentWallet, loading, error, refresh }),
    [agentWallet, error, loading, refresh],
  );

  return <AgentWalletContext.Provider value={value}>{children}</AgentWalletContext.Provider>;
}

export function useAgentWalletStore() {
  const value = useContext(AgentWalletContext);
  if (!value) throw new Error("useAgentWalletStore must be used inside AgentWalletProvider.");
  return value;
}
