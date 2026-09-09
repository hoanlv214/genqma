interface DepositModalProps {
  open: boolean;
  onClose: () => void;
  depositAmountInput: string;
  onDepositAmountChange: (value: string) => void;
  exactCost: number;
  payStatusText: string;
  onDeposit: () => void;
}

export function DepositModal({
  open,
  onClose,
  depositAmountInput,
  onDepositAmountChange,
  exactCost,
  payStatusText,
  onDeposit,
}: DepositModalProps) {
  if (!open) return null;

  return (
    <div className="modal-backdrop open">
      <div className="modal-panel withdraw-modal" style={{ width: 420 }}>
        <div className="modal-header">
          <span className="modal-title">Deposit USDC to Circle Gateway</span>
          <button type="button" className="icon-button" onClick={onClose}>
            x
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ fontSize: "0.78rem", color: "var(--t2)" }}>
            Your Circle Gateway balance is insufficient for this purchase. Choose an amount to deposit.
          </p>
          <label>
            <span className="withdraw-label">Deposit amount (USDC)</span>
            <input
              type="number"
              className="withdraw-input"
              value={depositAmountInput}
              onChange={(event) => onDepositAmountChange(event.target.value)}
            />
          </label>
          <div className="deposit-quick-row">
            <button type="button" className="deposit-quick-btn" onClick={() => onDepositAmountChange(exactCost.toFixed(6))}>
              Exact Cost
            </button>
            <button type="button" className="deposit-quick-btn" onClick={() => onDepositAmountChange("0.005")}>
              0.005 USDC
            </button>
            <button type="button" className="deposit-quick-btn" onClick={() => onDepositAmountChange("0.1")}>
              0.10 USDC
            </button>
          </div>

          {payStatusText && (
            <p style={{ fontSize: "0.76rem", color: "var(--t2)", marginTop: 6 }}>{payStatusText}</p>
          )}

          <div className="withdraw-actions" style={{ marginTop: 12 }}>
            <button type="button" className="submit-btn" onClick={onDeposit}>
              Deposit
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
