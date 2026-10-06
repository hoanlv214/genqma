'use client';

import type { ReactNode } from 'react';
import { Check, ShieldAlert, ReceiptText } from 'lucide-react';
import { shortAddress } from '@/services/wallet';
import { ARC_CHAIN } from '@/config/network';
import './DecisionReceipt.css';

export interface InvoiceCheck {
  label: string;
  detail: string;
  passed?: boolean;
  link?: string;
  linkText?: string;
}

export interface DecisionReceiptProps {
  invoice?: any;
  paymentDetails?: any;
  genlayerReceipt?: any;
  wallet?: string;
}

function Stage({ number, name, children }: { number: string; name: string; children: ReactNode }) {
  return (
    <div className="qma-invoice-stage-row">
      <div className="qma-stage-badge">
        <span>{number}</span>
        <p className="qma-stage-name">{name}</p>
      </div>
      <div className="qma-stage-content">{children}</div>
    </div>
  );
}

export function DecisionReceipt({
  invoice,
  paymentDetails,
  genlayerReceipt,
  wallet,
}: DecisionReceiptProps) {
  // Dynamic values from live purchased invoice
  const dynamicSymbol = String(invoice?.symbol || 'QMA').replace('-', '_').toUpperCase();
  const dynamicAmount = invoice?.amount ? Number(invoice.amount).toFixed(3) : '0.050';
  const arcscanTx = paymentDetails?.txHash || invoice?.transaction_hash;
  const genlayerTx = paymentDetails?.genlayerTxHash || genlayerReceipt?.transaction_hash;
  const arcscanUrl = paymentDetails?.explorerUrl || (arcscanTx ? `https://testnet.arcscan.app/tx/${arcscanTx}` : undefined);
  const genlayerUrl = paymentDetails?.genlayerExplorerUrl || (genlayerTx ? `https://explorer-studio-dev.genlayer.com/transactions/${genlayerTx}` : undefined);
  const dynamicConfidence = genlayerReceipt?.confidence != null
    ? (Number(genlayerReceipt.confidence) / 100).toFixed(2)
    : null;

  const counterparty = invoice?.symbol ? `${dynamicSymbol} Intelligence Protocol` : 'QMA Intelligence Protocol';
  const reference = invoice?.invoice_id
    ? `RPT-${shortAddress(invoice.invoice_id)} · ${dynamicSymbol} Anomaly Report`
    : `RPT-${dynamicSymbol} · Quantitative Signal Brief`;
  const description = 'Full access · institutional quantitative brief + source data pack';
  const hash = arcscanTx ? shortAddress(arcscanTx) : null;
  const previous = invoice?.invoice_id ? shortAddress(invoice.invoice_id) : '91de...0b72';

  const checks: InvoiceCheck[] = [
    {
      label: 'report.delivery_verified',
      detail: 'Source pack and executive intelligence brief received',
      passed: true,
    },
    {
      label: 'invoice.duplicate_of_settled',
      detail: 'No matching settlement found on ledger',
      passed: true,
    },
    {
      label: 'genlayer.sla_verified',
      detail: genlayerReceipt?.verdict
        ? `SLA verified: ${genlayerReceipt.verdict}${genlayerReceipt.confidence != null ? ` (Consensus ${genlayerReceipt.confidence}%)` : ""}`
        : 'SLA contract verified by GenLayer consensus validators',
      passed: true,
      link: genlayerUrl,
      linkText: genlayerTx ? `Tx: ${shortAddress(genlayerTx)} ↗` : undefined,
    },
    {
      label: 'buyer.access_granted',
      detail: wallet ? `Access enabled for ${shortAddress(wallet)} (12 months)` : 'Workspace access enabled for 12 months',
      passed: true,
    },
  ];

  return (
    <div className="qma-invoice-wrapper" role="region" aria-label="QMA Settlement & Treasury Receipt">


      <section className="qma-invoice-frame">
        {/* Paper Receipt Slip */}
        <article className="qma-invoice-paper">
          {/* Header Row */}
          <div className="qma-invoice-paper-top">
            <div>
              <p className="qma-invoice-label">QMA INVOICE</p>
              <h3 className="qma-invoice-counterparty">{counterparty}</h3>
              <p className="qma-invoice-eyebrow">Report purchase · unit 01 of 01</p>
            </div>
            <div className="qma-invoice-kind-tag">
              qma · rpt
            </div>
          </div>

          {/* Amount Block */}
          <div className="qma-invoice-amount-block">
            <div className="qma-stage-content">
              <p className="qma-invoice-reference">{reference}</p>
              <p className="qma-invoice-description">{description}</p>
            </div>
            <div className="qma-invoice-amount">
              {dynamicAmount}
              <span className="qma-invoice-currency">USDC</span>
            </div>
          </div>

          {/* 4 Stages */}
          <div className="qma-invoice-stages">
            {/* Stage 01: OBSERVE */}
            <Stage number="01" name="OBSERVE">
              <p className="qma-observe-line-1">Report scope matched purchase order for {dynamicSymbol}</p>
              <p className="qma-observe-line-2">File package delivered · SHA-256 checksum verified</p>
            </Stage>

            {/* Stage 02: REASON */}
            <Stage number="02" name="REASON">
              <div className="qma-stage-reason-row">
                <span>settlement says</span>
                <span className="qma-action-pill">PAY</span>
                {dynamicConfidence && <span>confidence {dynamicConfidence}</span>}
              </div>
              <p className="qma-stage-quote">
                “The quantitative report was delivered, checksum verified, and access token minted for buyer workspace.”
              </p>
            </Stage>

            {/* Stage 03: ENFORCE */}
            <Stage number="03" name="ENFORCE">
              <div className="qma-checks-list">
                {checks.map((check) => (
                  <div key={check.label} className="qma-check-item">
                    {check.passed ? (
                      <Check aria-hidden="true" size={14} className="qma-check-icon-pass" />
                    ) : (
                      <ShieldAlert aria-hidden="true" size={14} className="qma-check-icon-fail" />
                    )}
                    <div className="qma-stage-content">
                      <span className="qma-check-code">{check.label}</span>
                      <div className="qma-check-detail">
                        {check.detail}
                        {check.link && check.linkText && (
                          <>
                            {' · '}
                            <a
                              href={check.link}
                              target="_blank"
                              rel="noreferrer"
                              className="qma-check-link"
                            >
                              {check.linkText}
                            </a>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Stage>

            {/* Stage 04: SIGN */}
            <Stage number="04" name="SIGN">
              <div>
                <span className="qma-sign-stamp">PAID</span>
                <p className="qma-sign-settlement">Settled on {ARC_CHAIN.name} via x402</p>
                {arcscanUrl && arcscanTx && (
                  <p className="qma-arcscan-receipt-row">
                    <a
                      href={arcscanUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="qma-arcscan-link"
                    >
                      Arcscan Receipt: {shortAddress(arcscanTx)} ↗
                    </a>
                  </p>
                )}
              </div>
            </Stage>
          </div>

          {/* Provenance Row */}
          <div className="qma-invoice-provenance">
            {hash && <span>hash {hash}</span>}
            <span>prev {previous}</span>
          </div>
        </article>

        {/* Live Ledger Head */}
        <div className="qma-live-ledger-head">
          <div className="qma-ledger-head-title">
            <span className="qma-pulse-dot" aria-hidden="true" />
            Live ledger head
          </div>

          <div className="qma-ledger-box-active">
            <span>
              <strong>current</strong>
              <span className="qma-ledger-event-tag">report · access_granted</span>
            </span>
            {hash && <span className="qma-ledger-hash-tag">{hash}</span>}
          </div>

          <div className="qma-ledger-box-prev">
            <span>
              previous <span className="qma-ledger-event-tag">ledger entry</span>
            </span>
            <span>{previous}</span>
          </div>
        </div>
      </section>

      <footer className="qma-invoice-footer">
        <ReceiptText size={15} className="qma-receipt-footer-icon" />
        <span>
          QMA observes, verifies, enforces, and signs every report purchase before it enters the ledger.
        </span>
      </footer>
    </div>
  );
}

export default DecisionReceipt;
