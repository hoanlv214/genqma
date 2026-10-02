import { UnifiedFundsModal, type UnifiedFundsModalProps } from "./UnifiedFundsModal";

export type UnifiedDepositModalProps = Omit<UnifiedFundsModalProps, "defaultTab">;

export function UnifiedDepositModal(props: UnifiedDepositModalProps) {
  return <UnifiedFundsModal {...props} defaultTab="deposit" />;
}
