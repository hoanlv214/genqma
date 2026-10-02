import { UnifiedFundsModal, type UnifiedFundsModalProps } from "./UnifiedFundsModal";

export type UnifiedWithdrawModalProps = Omit<UnifiedFundsModalProps, "defaultTab">;

export function UnifiedWithdrawModal(props: UnifiedWithdrawModalProps) {
  return <UnifiedFundsModal {...props} defaultTab="withdraw" />;
}
