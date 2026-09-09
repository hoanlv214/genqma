import { formatUsdc } from "../../utils/format";
import { shortAddress } from "../../services/wallet";
import { Loader } from "../ui/Loader";

interface ProviderEarningsModalProps {
  open: boolean;
  onClose: () => void;
  wallet: string;
  ownedProviders: any[];
  creatorClaimConfig: any;
  state: any; // Return type of useProviderEarnings
}

export function ProviderEarningsModal({
  open,
  onClose,
  wallet,
  ownedProviders,
  creatorClaimConfig,
  state,
}: ProviderEarningsModalProps) {
  if (!open) return null;

  const {
    providerEarningsLoading,
    providerEarningsError,
    providerEarningsStats,
    selectedProviderEarningsIds,
    creatorClaimSubmitting,
    providerWithdrawSubmitting,
    selectedProviderEarningsStats,
    providerEarningsTotals,
    providerGatewayWithdrawMax,
    providerWithdrawDisplayAmount,
    toggleProviderEarningsSelection,
    refreshProviderEarningsModal,
    submitCreatorClaim,
    submitProviderGatewayWithdraw,
  } = state;

  return (
    <div className="modal-backdrop open premium-earnings-backdrop" style={{ display: "flex" }}>
      <div
        className="premium-earnings-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="creator-earnings-title"
      >
        <div className="premium-earnings-header">
          <div className="premium-earnings-title-group">
            <div className="modal-title" id="creator-earnings-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="sparkle-icon"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"></path><path d="M20 3v4"></path><path d="M22 5h-4"></path><path d="M4 17v2"></path><path d="M5 18H3"></path></svg>
              Creator Earnings
            </div>
            <div className="modal-subtitle">Provider-owner revenue, direct Gateway split balances, and claimable QMA ledger earnings.</div>
          </div>
          <div className="premium-earnings-header-right">
            <img src="/premium_crypto_wallet.png" alt="Wallet Illustration" className="premium-wallet-img" />
            <button className="icon-button close-btn" type="button" title="Close" onClick={onClose}>x</button>
          </div>
        </div>
        <div className="premium-earnings-body">
          <div className="premium-stats-grid">
            <div className="premium-stat-card">
              <div className="stat-label">OWNER WALLET</div>
              <div className="stat-value" title={wallet}>{wallet ? shortAddress(wallet) : "n/a"} <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></div>
              <div className="stat-card-glow line-purple"></div>
            </div>
            <div className="premium-stat-card">
              <div className="stat-icon"><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg></div>
              <div className="stat-label">PROVIDERS</div>
              <div className="stat-value">{selectedProviderEarningsStats.length}/{providerEarningsStats.length || ownedProviders.length}</div>
              <div className="stat-sub success-text">Active</div>
            </div>
            <div className="premium-stat-card">
              <div className="stat-icon"><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 8v8"></path><path d="M8 12h8"></path></svg></div>
              <div className="stat-label">CLAIMABLE LEDGER</div>
              <div className="stat-value">{formatUsdc(providerEarningsTotals.totalClaimable, 6)}</div>
              <div className="stat-sub success-text">Ready to claim</div>
            </div>
            <div className="premium-stat-card">
              <div className="stat-icon"><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line></svg></div>
              <div className="stat-label">WITHDRAWABLE GATEWAY</div>
              <div className="stat-value">{formatUsdc(providerEarningsTotals.gatewayAvailable, 6)}</div>
              <div className="stat-sub success-text">Available to withdraw</div>
            </div>
          </div>


          {providerEarningsLoading && !providerEarningsStats.length ? <Loader label="Loading creator earnings..." compact size="sm" /> : (
            <div className="premium-providers-list">
              {providerEarningsStats.length ? providerEarningsStats.map((item: any) => {
                const selected = selectedProviderEarningsIds.includes(item.provider_id);
                const availableAmount = item.withdrawal_mode === "direct_gateway_split" ? (item.creator_gateway_balance?.available_usdc || 0) : item.creator_claimable_usdc;

                return (
                  <div className={`premium-provider-card ${selected ? "selected" : ""}`} key={item.provider_id}>
                    <div className="premium-provider-header">
                      <label className="premium-checkbox-label">
                        <input type="checkbox" checked={selected} onChange={() => toggleProviderEarningsSelection(item.provider_id)} disabled={creatorClaimSubmitting || providerWithdrawSubmitting} />
                        <span className="premium-checkbox"></span>
                      </label>

                      <div className="premium-provider-icon">
                        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                      </div>

                      <div className="premium-provider-info">
                        <h3>{item.provider_name || item.provider_id}</h3>
                        <div className="provider-subtitle">{item.provider_id}{item.revenue_wallet ? ` / ${shortAddress(item.revenue_wallet)}` : ""}</div>
                        <div className="provider-badges">
                          <span className="badge badge-success">Active</span>
                          <span className="badge badge-purple">Memory Provider</span>
                        </div>
                      </div>

                      <div className="premium-provider-amount">
                        <div className="amount-value">{formatUsdc(availableAmount, 6)}</div>
                        <div className="amount-label">{item.withdrawal_mode === "direct_gateway_split" ? "Gateway Balance" : "Claimable Ledger"}</div>
                      </div>

                    </div>
                  </div>
                );
              }) : (
                <div className="empty-state-card">
                  <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" strokeWidth="1" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5, marginBottom: 16 }}><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
                  <div className="empty-title">No providers found</div>
                  <div className="empty-subtitle">Deploy a provider and earn USDC to see it here.</div>
                </div>
              )}
            </div>
          )}

          <div className="premium-withdraw-actions">
            <button className="premium-btn btn-outline" type="button" onClick={refreshProviderEarningsModal} disabled={providerEarningsLoading || creatorClaimSubmitting || providerWithdrawSubmitting}>
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
              Refresh
            </button>

            <div className="actions-right">
              {providerEarningsTotals.hasDirectSplit && (
                <button className="premium-btn btn-primary" type="button" onClick={submitProviderGatewayWithdraw} disabled={providerWithdrawSubmitting || providerGatewayWithdrawMax <= 0}>
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                  {providerWithdrawSubmitting ? "Withdrawing..." : `Withdraw ${providerWithdrawDisplayAmount.toFixed(6)} USDC`}
                </button>
              )}

              <button className="premium-btn btn-primary" type="button" onClick={submitCreatorClaim} disabled={providerEarningsLoading || creatorClaimSubmitting || providerWithdrawSubmitting || !creatorClaimConfig?.configured || providerEarningsTotals.totalClaimable <= 0}>
                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                {creatorClaimSubmitting ? "Claiming..." : `Claim ${providerEarningsTotals.totalClaimable.toFixed(6)} USDC`}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
