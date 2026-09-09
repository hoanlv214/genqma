import { getInjectedWallet, ensureArcTestnet } from "../../services/wallet";

interface FundArcWalletModalContentProps {
  fundReadinessTone: string;
  fundReadinessStatus: string;
  fundGatewayBalance: string;
  fundRequiredAmount: string;
  wallet: string;
  fundWalletStatus: string;
  fundProviderStatus: string;
  fundChainStatus: string;
  fundWalletUsdc: string;
  fundPrimaryAction: { action: string; label?: string };
  fundNextStep: string;
  fundShowAdvanced: boolean;
  setFundShowAdvanced: (value: boolean | ((current: boolean) => boolean)) => void;
  setShowFundArcModal: (open: boolean) => void;
  connect: () => void | Promise<void>;
  refreshFundingReadiness: () => void | Promise<void>;
}

export function FundArcWalletModalContent({
  fundReadinessTone, fundReadinessStatus, fundGatewayBalance, fundRequiredAmount, wallet, fundWalletStatus, fundProviderStatus, fundChainStatus, fundWalletUsdc, fundPrimaryAction, fundNextStep, fundShowAdvanced, setFundShowAdvanced, setShowFundArcModal, connect, refreshFundingReadiness,
}: FundArcWalletModalContentProps) {
  return (
    <>
      <div className="funding-modal-header">
        <div>
          <div className="modal-title" id="fund-arc-title">Fund Arc Wallet</div>
          <div className="modal-subtitle">
            {fundReadinessTone === "ready" ? "Gateway balance covers this report." : "Top up your Gateway balance to unlock this report."}
          </div>
        </div>
      </div>
      <div className="funding-body funding-modal-body">
        <section className="funding-section">
          <div className="funding-balance-head">
            <span className="funding-item-label">Gateway balance</span>
            <span className={`funding-status-pill ${fundReadinessTone}`}>
              {fundReadinessTone === "ready" ? "✓ " : ""}{fundReadinessTone === "ready" ? "Ready" : fundReadinessStatus}
            </span>
          </div>
          <div className="funding-balance-values">
            <strong>{fundGatewayBalance}</strong>
            <span>needs {fundRequiredAmount}</span>
          </div>
          <div className={`funding-progress ${fundReadinessTone}`}>
            <span style={{ width: fundGatewayBalance !== "n/a" && fundRequiredAmount !== "n/a" ? `${Math.min((Number.parseFloat(fundGatewayBalance) / Number.parseFloat(fundRequiredAmount)) * 100, 100)}%` : "0%" }} />
          </div>
        </section>
        <div className="funding-wallet-identity">
          <span className="funding-wallet-icon">◈</span>
          <div>
            <strong title={wallet}>{fundWalletStatus}</strong>
            <span>{fundProviderStatus} · {fundChainStatus}</span>
          </div>
          <strong className="funding-wallet-usdc">{fundWalletUsdc}</strong>
        </div>
        <section className="funding-section">
          {fundReadinessTone === "ready" || fundPrimaryAction.action === "close" ? (
            <div className="funding-ready-actions">
              <button type="button" className="funding-continue-btn" onClick={() => setShowFundArcModal(false)}>
                Continue to payment
              </button>
            </div>
          ) : (
            <>
              <div className="funding-section-title">Funding options</div>
              <div className="funding-route-grid">
                <a className="funding-route-card" href="https://faucet.circle.com/" target="_blank" rel="noopener noreferrer">
                  <span className="funding-option-icon">↯</span><span><strong>Circle Faucet</strong><small>Free Arc Testnet USDC for demos and testing.</small></span>
                </a>
                <a className="funding-route-card" href="https://developers.circle.com/" target="_blank" rel="noopener noreferrer">
                  <span className="funding-option-icon">⇄</span><span><strong>Bridge via CCTP</strong><small>Move USDC from another chain into Arc.</small></span>
                </a>
                <div className="funding-route-card funding-route-card-highlight">
                  <span className="funding-option-icon">＋</span><span><strong>Deposit to Gateway</strong><small>Move Arc USDC into your Gateway balance.</small></span>
                </div>
              </div>
              <div className="funding-next-step"><span className="funding-item-label">Next step</span><strong className="funding-item-value">{fundNextStep}</strong><div className="funding-primary-action">
                {fundPrimaryAction.action === "connect" && (
                  <button type="button" className="funding-action-btn" onClick={connect}>
                    Connect wallet first
                  </button>
                )}
                {fundPrimaryAction.action === "switch" && (
                  <button type="button" className="funding-action-btn" onClick={async () => {
                    try {
                      await ensureArcTestnet();
                      refreshFundingReadiness();
                    } catch (err) {
                      console.error("Failed to switch/add Arc Testnet network:", err);
                    }
                  }}>
                    Switch Network
                  </button>
                )}
                {fundPrimaryAction.action === "refresh" && (
                  <button type="button" className="funding-action-btn" onClick={refreshFundingReadiness}>
                    Retry check
                  </button>
                )}
                {fundPrimaryAction.action === "faucet" && (
                  <a className="funding-action-btn" href="https://faucet.circle.com/" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", textAlign: "center", display: "inline-block" }}>
                    Open Circle Faucet
                  </a>
                )}
                {fundPrimaryAction.action === "close" && (
                  <button type="button" className="funding-action-btn" onClick={() => setShowFundArcModal(false)}>
                    Close
                  </button>
                )}
              </div></div>
            </>
          )}
          <div className="funding-network-details">
            <span className="funding-network-title">Arc Testnet network details</span>
            <div className="funding-network-row">
              <strong className="funding-network-label">Chain ID</strong>
              <code>5042002 / 0x4cef52</code>
            </div>
            <div className="funding-network-row">
              <strong className="funding-network-label">RPC URL</strong>
              <code>https://rpc.testnet.arc.network</code>
            </div>
            <div className="funding-network-row">
              <strong className="funding-network-label">Currency</strong>
              <code>USDC</code>
            </div>
            <div className="funding-network-row">
              <strong className="funding-network-label">Explorer</strong>
              <code>https://testnet.arcscan.app</code>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
