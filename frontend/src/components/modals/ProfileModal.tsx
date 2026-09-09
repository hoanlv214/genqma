import { Loader } from "../ui/Loader";

interface ProfileModalProps {
  open: boolean;
  wallet: string;
  onClose: () => void;
  profileChainUsdc: string;
  profileGatewayUsdc: string;
  profileReportsCount: number;
  profileTotalSpent: string;
  profilePurchasedSymbols: string[];
  profilePaymentsLoading: boolean;
  profilePaymentsError: string;
  profileVerifiedPayments: any[];
  profileVerifiedPaymentsPage: number;
  profileVerifiedPaymentsTotalPages: number;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onOpenReport: (payment: any) => void;
}

export function ProfileModal({
  open,
  wallet,
  onClose,
  profileChainUsdc,
  profileGatewayUsdc,
  profileReportsCount,
  profileTotalSpent,
  profilePurchasedSymbols,
  profilePaymentsLoading,
  profilePaymentsError,
  profileVerifiedPayments,
  profileVerifiedPaymentsPage,
  profileVerifiedPaymentsTotalPages,
  onPreviousPage,
  onNextPage,
  onOpenReport,
}: ProfileModalProps) {
  if (!open) return null;

  const shortAddress = (value?: string) => {
    if (!value) return "n/a";
    return value.length > 12 ? `${value.slice(0, 6)}...${value.slice(-4)}` : value;
  };

  return (
    <div className="modal-backdrop open" style={{ display: "flex" }}>
      <div className="wallet-profile-modal quick-profile-modal" role="dialog" aria-modal="true" aria-labelledby="wallet-profile-title" style={{ display: "block" }}>
        <div className="modal-header">
          <div>
            <div className="modal-title" id="wallet-profile-title">Wallet Profile</div>
            <div className="modal-subtitle" id="wallet-profile-address">{wallet}</div>
          </div>
          <button className="icon-button" type="button" title="Close" onClick={onClose}>✕</button>
        </div>
        <div className="profile-grid">
          <div className="profile-tile"><span className="profile-label">Wallet On-chain USDC</span><span className="profile-value">{profileChainUsdc === "loading..." ? <Loader compact variant="spinner" size="xs" className="inline" /> : profileChainUsdc}</span></div>
          <div className="profile-tile"><span className="profile-label">Buyer Gateway Balance</span><span className="profile-value">{profileGatewayUsdc === "loading..." ? <Loader compact variant="spinner" size="xs" className="inline" /> : profileGatewayUsdc}</span></div>
          <div className="profile-tile"><span className="profile-label">Reports Bought</span><span className="profile-value">{profileReportsCount}</span></div>
          <div className="profile-tile"><span className="profile-label">Total Spent</span><span className="profile-value">{profileTotalSpent === "loading..." ? <Loader compact variant="spinner" size="xs" className="inline" /> : profileTotalSpent}</span></div>
        </div>
        <div className="subsection-title">Purchased Signals</div>
        <div className="token-list">
          {profilePurchasedSymbols.length === 0 ? <span className="token-chip">None yet</span> : profilePurchasedSymbols.map((symbol, index) => <span className="token-chip" key={index}>{symbol}</span>)}
        </div>
        <div className="subsection-title">Verified Web Payments</div>
        <div className="quick-profile-table-wrap">
          <table className="activity-table">
            <thead><tr><th>Signal</th><th>Amount</th><th>Status</th><th>Settlement / Tx</th><th>Report</th></tr></thead>
            <tbody>
              {profilePaymentsLoading ? <tr><td colSpan={5}><Loader label="Loading payments..." compact size="sm" className="table-loader" /></td></tr> : profilePaymentsError ? <tr><td colSpan={5} style={{ color: "var(--orange)", textAlign: "center" }}>{profilePaymentsError}</td></tr> : profileVerifiedPayments.length === 0 ? <tr><td colSpan={5} style={{ color: "var(--t3)", textAlign: "center" }}>No verified payments.</td></tr> : profileVerifiedPayments.map((payment, index) => {
                const status = payment.gateway_status || payment.status || "completed";
                const amount = payment.amount_usdc ?? payment.amount ?? payment.price_usdc;
                const txHash = payment.transaction_hash || payment.tx_hash || payment.settlement_tx_hash;
                const settlementLabel = txHash || payment.settlement_id || payment.invoice_id;
                return <tr key={payment.entitlement_id || payment.settlement_id || payment.invoice_id || index}>
                  <td>{payment.symbol || payment.query_symbol || "n/a"}</td>
                  <td className="mono-td">{amount != null ? `${Number(amount).toFixed(3)} USDC` : "-"}</td>
                  <td><span className={`pnl-badge ${status === "completed" || status === "received" ? "win" : "loss"}`}>{status}</span></td>
                  <td className="mono-td settlement-cell">{txHash ? <a className="tx-link" href={payment.explorer_url || `https://testnet.arcscan.app/tx/${txHash}`} target="_blank" rel="noopener noreferrer">{shortAddress(txHash)}</a> : settlementLabel ? <span className="settlement-ref">{shortAddress(settlementLabel)}</span> : "n/a"}</td>
                  <td>{payment.has_report || status === "completed" || status === "received" ? <button type="button" className="refresh-btn" onClick={() => onOpenReport(payment)}>Open</button> : "n/a"}</td>
                </tr>;
              })}
            </tbody>
          </table>
        </div>
        <div className="table-pager profile-pager">
          <button type="button" className="refresh-btn" disabled={profileVerifiedPaymentsPage <= 1} onClick={onPreviousPage}>Prev</button>
          <span style={{ margin: "0 10px", fontSize: "0.8rem" }}>Page {profileVerifiedPaymentsPage} / {profileVerifiedPaymentsTotalPages}</span>
          <button type="button" className="refresh-btn" disabled={profileVerifiedPaymentsPage >= profileVerifiedPaymentsTotalPages} onClick={onNextPage}>Next</button>
        </div>
      </div>
    </div>
  );
}
