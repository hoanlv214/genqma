import { useEffect, useRef } from "react";
import { appKit, openAppKitModal, closeAppKitModal } from "../../config/reownAppKit";

export interface WalletAppKitModalProps {
  open: boolean;
  onClose: () => void;
  onConnected: (address: string) => void;
}

/**
 * Reown AppKit Wallet Connection Bridge.
 * Replaces the handwritten 354-line EIP-6963 modal with the official Reown AppKit ecosystem modal.
 * Supports 300+ wallets, QR mobile connections, and automatic Arc Testnet alignment.
 */
export function WalletAppKitModal({ open, onClose, onConnected }: WalletAppKitModalProps) {
  const initialAddressRef = useRef<string | null>(null);

  useEffect(() => {
    if (!open) {
      initialAddressRef.current = null;
      if (appKit.getState().open) {
        closeAppKitModal().catch(() => {});
      }
      return;
    }

    // Capture starting address to avoid false trigger if already connected
    initialAddressRef.current = appKit.getAddress() || null;

    // Trigger official Reown AppKit modal
    openAppKitModal().catch((err) => {
      console.warn("Reown AppKit open modal error:", err);
    });

    // Subscribe to connected account updates
    const unsubscribeAccount = appKit.subscribeAccount((account) => {
      if (account?.isConnected && account?.address) {
        // Trigger only if address is newly connected or modal was explicitly opened
        if (account.address !== initialAddressRef.current || !initialAddressRef.current) {
          onConnected(account.address);
          closeAppKitModal().catch(() => {});
          onClose();
        }
      }
    });

    // Subscribe to modal open/close state transitions (user dismissed modal)
    const unsubscribeState = appKit.subscribeState((state) => {
      if (!state.open && open) {
        onClose();
      }
    });

    return () => {
      unsubscribeAccount();
      unsubscribeState();
    };
  }, [open, onClose, onConnected]);

  // AppKit mounts its own web-component dialog (<appkit-modal>) to document.body
  return null;
}
