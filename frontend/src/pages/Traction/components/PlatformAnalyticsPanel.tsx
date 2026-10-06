import { useEffect, useState } from "react";
import { Loader } from "@/components/Loader";
import { getPlatformSummary, getPlatformPayments, getPlatformPayers } from "@/services/traction";
import { shortAddress } from "@/services/wallet";
import { formatDateTime, formatUsdc, gatewayStatusBadge, tierLabel } from "@/utils/format";

type PlatformData = Record<string, any>;

function renderSettlementRef(event: any) {
  const txHash = event?.transaction_hash || event?.tx_hash || event?.settlement_tx_hash;
  const settlementId = event?.settlement_id;
  const isFinalStatus = ["completed", "confirmed"].includes(String(event?.gateway_status || "").toLowerCase());

  if (event?.explorer_url && txHash) {
    return (
      <a className="tx-link" href={event.explorer_url} target="_blank" rel="noreferrer" title={`Settlement: ${settlementId || ""}`}>
        {shortAddress(txHash)}
      </a>
    );
  }
  if (txHash) {
    return (
      <a className="tx-link" href={`https://testnet.arcscan.app/tx/${txHash}`} target="_blank" rel="noreferrer" title={`Settlement: ${settlementId || ""}`}>
        {shortAddress(txHash)}
      </a>
    );
  }
  if (settlementId) {
    return (
      <>
        <span className="mono-td" title={`Settlement ID: ${settlementId}`}>{shortAddress(settlementId)}</span>
        <div className={`settlement-status-note ${isFinalStatus ? "is-final" : "is-pending"}`}>
          {isFinalStatus ? "Arcscan tx unavailable" : "Arcscan tx pending"}
        </div>
      </>
    );
  }
  return <span className="text-[var(--t3)]">n/a</span>;
}

export function PlatformAnalyticsPanel() {
  const [platformSummary, setPlatformSummary] = useState<PlatformData | null>(null);
  const [platformPayments, setPlatformPayments] = useState<PlatformData[]>([]);
  const [platformPaymentsPage, setPlatformPaymentsPage] = useState(1);
  const [platformPaymentsTotalPages, setPlatformPaymentsTotalPages] = useState(1);
  const [platformPaymentsTotal, setPlatformPaymentsTotal] = useState(0);
  const [platformPayers, setPlatformPayers] = useState<PlatformData[]>([]);
  const [platformPayersPage, setPlatformPayersPage] = useState(1);
  const [platformPayersTotalPages, setPlatformPayersTotalPages] = useState(1);
  const [platformPayersTotal, setPlatformPayersTotal] = useState(0);
  const [platformTablesLoading, setPlatformTablesLoading] = useState(false);
  const [platformTablesError, setPlatformTablesError] = useState("");

  const loadPlatformSummaryData = async () => {
    const data = await getPlatformSummary();
    setPlatformSummary(data);
    return data;
  };

  const loadPlatformPaymentsData = async (page: number) => {
    const data = await getPlatformPayments(page, 10);
    const rows = Array.isArray(data.recent_payments) ? data.recent_payments : [];
    const meta = data.recent_payments_page || {};
    setPlatformPayments(rows);
    setPlatformPaymentsPage(Number(meta.page || page || 1));
    setPlatformPaymentsTotalPages(Number(meta.total_pages || 1));
    setPlatformPaymentsTotal(Number(meta.total || rows.length));
  };

  const loadPlatformPayersData = async (page: number) => {
    const data = await getPlatformPayers(page, 10);
    const rows = Array.isArray(data.payer_breakdown) ? data.payer_breakdown : [];
    const meta = data.payer_breakdown_page || {};
    setPlatformPayers(rows);
    setPlatformPayersPage(Number(meta.page || page || 1));
    setPlatformPayersTotalPages(Number(meta.total_pages || 1));
    setPlatformPayersTotal(Number(meta.total || rows.length));
  };

  const refreshPlatformTables = async (paymentPage = 1, payerPage = 1) => {
    setPlatformTablesLoading(true);
    setPlatformTablesError("");
    try {
      await Promise.all([
        loadPlatformSummaryData(),
        loadPlatformPaymentsData(paymentPage),
        loadPlatformPayersData(payerPage),
      ]);
    } catch (error: any) {
      console.warn("Platform analytics unavailable", error);
      setPlatformTablesError(error?.message || "Platform analytics unavailable.");
    } finally {
      setPlatformTablesLoading(false);
    }
  };

  const changePlatformPaymentsPage = async (page: number) => {
    setPlatformTablesLoading(true);
    setPlatformTablesError("");
    try {
      await loadPlatformPaymentsData(page);
    } catch (error: any) {
      setPlatformTablesError(error?.message || "Platform payments unavailable.");
    } finally {
      setPlatformTablesLoading(false);
    }
  };

  const changePlatformPayersPage = async (page: number) => {
    setPlatformTablesLoading(true);
    setPlatformTablesError("");
    try {
      await loadPlatformPayersData(page);
    } catch (error: any) {
      setPlatformTablesError(error?.message || "Platform payers unavailable.");
    } finally {
      setPlatformTablesLoading(false);
    }
  };

  useEffect(() => {
    refreshPlatformTables(1, 1);
  }, []);

  return (
    <section className="traction-panel platform-stats-section">
      <div className="traction-panel-heading">
        <div>
          <span className="eyebrow">Settlement Ledger &amp; Provenance</span>
          <h2>Platform Analytics &amp; Payment Activity</h2>
        </div>
      </div>

      {platformTablesError ? (
        <div className="traction-error mt-4" role="alert">
          {platformTablesError}
        </div>
      ) : null}

      <div className="seller-balance-grid">
        <div className="balance-tile green">
          <span className="balance-tile-label">Seller Gateway · Available</span>
          <span className="balance-tile-val">
            {platformSummary?.seller_gateway_balance?.available_usdc != null
              ? formatUsdc(platformSummary.seller_gateway_balance.available_usdc, 6)
              : "n/a"}
          </span>
          <span className="balance-tile-sub">On-chain confirmed, withdrawable</span>
        </div>
        <div className="balance-tile amber">
          <span className="balance-tile-label">Seller Gateway · Pending Batch</span>
          <span className="balance-tile-val">
            {platformSummary?.seller_gateway_balance?.pending_batch_usdc != null
              ? formatUsdc(platformSummary.seller_gateway_balance.pending_batch_usdc, 6)
              : "n/a"}
          </span>
          <span className="balance-tile-sub">Circle accepted, awaiting on-chain batch</span>
        </div>
        <div className="balance-tile neutral">
          <span className="balance-tile-label">Seller Treasury Wallet</span>
          <span className="balance-tile-val">
            {platformSummary?.seller_address ? shortAddress(platformSummary.seller_address) : "n/a"}
          </span>
          <span className="balance-tile-sub">Final destination after batch settlement</span>
        </div>
      </div>

      <div className="split-tables">
        {/* RECENT SETTLEMENTS */}
        <div className="split-table-col split-table-col--settlements">
          <div className="subsection-title">
            Recent Settlements
            {platformPaymentsTotal ? <span className="table-count">({platformPaymentsTotal})</span> : null}
          </div>
          <div className="table-scroll-x">
            <table className="traction-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Provider</th>
                  <th>Payer</th>
                  <th>Amount</th>
                  <th>Circle Status</th>
                  <th>Settlement / Arcscan Tx</th>
                </tr>
              </thead>
              <tbody>
                {platformTablesLoading && !platformPayments.length ? (
                  <tr>
                    <td colSpan={6} className="text-center p-6">
                      <Loader label="Loading payments..." compact size="sm" />
                    </td>
                  </tr>
                ) : platformPayments.length ? (
                  platformPayments.map((event, index) => (
                    <tr key={event.event_id || event.settlement_id || event.invoice_id || index}>
                      <td className="mono-td">
                        <strong className="text-t1">{event.symbol || "n/a"}</strong>
                        <div className="table-meta">{formatDateTime(event.paid_at)}</div>
                      </td>
                      <td>
                        <span className="provider-badge">{event.provider_id || "unattributed"}</span>
                      </td>
                      <td className="mono-td" title={event.payer_address || ""}>
                        {event.payer_address ? shortAddress(event.payer_address) : "n/a"}
                      </td>
                      <td className="mono-td">
                        <span className="font-semibold">{formatUsdc(event.amount_usdc)}</span>
                        <div className="table-meta">{tierLabel(event.tier_category || event.tier)}</div>
                      </td>
                      <td>{gatewayStatusBadge(event.gateway_status)}</td>
                      <td className="mono-td">{renderSettlementRef(event)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="table-empty-cell">
                      No payments recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="table-pager">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={platformPaymentsPage <= 1 || platformTablesLoading}
              onClick={() => changePlatformPaymentsPage(Math.max(1, platformPaymentsPage - 1))}
            >
              Prev
            </button>
            <span className="table-page-label">
              Page {platformPaymentsPage} / {platformPaymentsTotalPages}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={platformPaymentsPage >= platformPaymentsTotalPages || platformTablesLoading}
              onClick={() => changePlatformPaymentsPage(Math.min(platformPaymentsTotalPages, platformPaymentsPage + 1))}
            >
              Next
            </button>
          </div>
        </div>

        {/* WALLET USAGE */}
        <div className="split-table-col split-table-col--wallets">
          <div className="subsection-title">Wallet Usage</div>
          <div className="table-scroll-x">
            <table className="traction-table">
              <thead>
                <tr>
                  <th>Wallet</th>
                  <th>Providers</th>
                  <th>Signals</th>
                  <th>Spent</th>
                </tr>
              </thead>
              <tbody>
                {platformTablesLoading && !platformPayers.length ? (
                  <tr>
                    <td colSpan={4} className="text-center p-6">
                      <Loader label="Loading wallets..." compact size="sm" />
                    </td>
                  </tr>
                ) : platformPayers.length ? (
                  platformPayers.map((payer, index) => {
                    const symbols = (payer.symbols || []).slice(0, 5).join(", ") || "n/a";
                    const overflow = (payer.symbols || []).length > 5 ? ` +${payer.symbols.length - 5}` : "";
                    const providers = (payer.providers || []).join(", ") || "unattributed";
                    return (
                      <tr key={payer.payer_address || index} title={`Last paid: ${formatDateTime(payer.last_paid_at)}`}>
                        <td className="mono-td" title={payer.payer_address || ""}>
                          {payer.payer_address ? shortAddress(payer.payer_address) : "n/a"}
                        </td>
                        <td className="text-xs text-[var(--t2)]">{providers}</td>
                        <td className="mono-td">
                          {payer.payments || 0} / {symbols}
                          {overflow}
                        </td>
                        <td className="mono-td">
                          <span className="font-semibold">{formatUsdc(payer.spent_usdc)}</span>
                          <div className="table-meta">
                            P:{payer.preview_count || 0} F:{payer.full_count || 0}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={4} className="table-empty-cell">
                      No wallet activity recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="table-pager">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={platformPayersPage <= 1 || platformTablesLoading}
              onClick={() => changePlatformPayersPage(Math.max(1, platformPayersPage - 1))}
            >
              Prev
            </button>
            <span className="table-page-label">
              Page {platformPayersPage} / {platformPayersTotalPages}
              {platformPayersTotal ? ` (${platformPayersTotal})` : ""}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={platformPayersPage >= platformPayersTotalPages || platformTablesLoading}
              onClick={() => changePlatformPayersPage(Math.min(platformPayersTotalPages, platformPayersPage + 1))}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* MARKETPLACE REVENUE LEDGER */}
      <div className="creator-split-ledger">
        <div className="subsection-title mb-3">
          Marketplace Revenue Ledger
        </div>
        <div className="table-scroll-x">
          <table className="traction-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Gross</th>
                <th>Creator Earned</th>
                <th>Platform Fee</th>
                <th>Claimable</th>
              </tr>
            </thead>
            <tbody>
              {(platformSummary?.revenue_by_provider || []).length ? (
                (platformSummary?.revenue_by_provider || []).map((row: any, index: number) => {
                  const sharePct = Number(row.creator_share_bps || 0) / 100;
                  return (
                    <tr key={row.provider_id || index} title={row.split_note || "Ledger estimate only."}>
                      <td className="mono-td" title={row.owner_wallet || ""}>
                        <strong className="text-t1">
                          {row.provider_name || row.provider_id || "provider"}
                        </strong>
                        <div className="table-meta">
                          {row.owner_wallet ? shortAddress(row.owner_wallet) : "n/a"}
                        </div>
                      </td>
                      <td className="mono-td">
                        <span className="font-semibold">{formatUsdc(row.revenue_usdc)}</span>
                        <div className="table-meta">{row.payments || 0} sales</div>
                      </td>
                      <td className="mono-td">
                        <span className="text-[var(--green)] font-semibold">
                          {formatUsdc(row.creator_earned_usdc)}
                        </span>
                        <div className="table-meta">{sharePct.toFixed(1)}%</div>
                      </td>
                      <td className="mono-td text-[var(--t2)]">
                        {formatUsdc(row.platform_fee_usdc)}
                      </td>
                      <td className="mono-td">
                        <span className="font-semibold">{formatUsdc(row.creator_claimable_usdc)}</span>
                        <div className="table-meta">ledger only</div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="table-empty-cell">
                    No creator revenue recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
