import type { ReactNode } from "react";

export interface FundArcWalletModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function FundArcWalletModal({ open, onClose, children }: FundArcWalletModalProps) {
  if (!open) return null;
  return (
    <div className="modal-backdrop open flex" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="wallet-profile-modal funding-modal" role="dialog" aria-modal="true" aria-labelledby="fund-arc-title">
        {children}
      </div>
    </div>
  );
}
