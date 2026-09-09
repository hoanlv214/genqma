import type { ReactNode } from "react";

interface FundArcWalletModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function FundArcWalletModal({ open, onClose, children }: FundArcWalletModalProps) {
  if (!open) return null;
  return (
    <div className="modal-backdrop open" style={{ display: "flex" }}>
      <div className="wallet-profile-modal funding-modal" role="dialog" aria-modal="true" aria-labelledby="fund-arc-title">
        {children}
      </div>
    </div>
  );
}
