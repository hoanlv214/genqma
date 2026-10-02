import type { ReactNode } from "react";

export interface FundArcWalletModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function FundArcWalletModal({ open, onClose, children }: FundArcWalletModalProps) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150 modal-backdrop open"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="w-full max-w-[880px] h-[660px] max-h-[calc(100vh-32px)] bg-[#090a12] border border-white/[0.08] rounded-2xl shadow-2xl shadow-black/80 overflow-hidden flex flex-col relative wallet-profile-modal funding-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="fund-arc-title"
      >
        {children}
      </div>
    </div>
  );
}
