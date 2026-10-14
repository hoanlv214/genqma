import React from "react";
import { AlertTriangle, CheckCircle, ShieldAlert, Cpu, Scale, FileCheck } from "lucide-react";
import type { QmaRoute } from "@/app/routes";
import { LegalLayout } from "./LegalLayout";

export interface TermsPageProps {
  onNavigate?: (route: QmaRoute) => void;
}

const TOC_ITEMS = [
  { id: "acceptance", label: "Acceptance & Eligibility" },
  { id: "protocol-nature", label: "Non-Custodial Protocol" },
  { id: "no-financial-advice", label: "No Financial Advice" },
  { id: "agent-operations", label: "Autonomous Agent Operations" },
  { id: "blockchain-risks", label: "Blockchain & Protocol Risks" },
  { id: "prohibited-activities", label: "Prohibited Uses" },
  { id: "ip-licenses", label: "Intellectual Property" },
  { id: "warranties-disclaimer", label: "Disclaimer of Warranties" },
  { id: "liability-limitation", label: "Limitation of Liability" },
  { id: "indemnification", label: "Indemnification" },
  { id: "governing-law", label: "Governing Law & Disputes" },
  { id: "contact", label: "Contact & Notices" },
];

export function TermsPage({ onNavigate = () => {} }: TermsPageProps) {
  return (
    <LegalLayout
      activeRoute="terms"
      onNavigate={onNavigate}
      title="Terms of Service"
      subtitle="Standard legal agreement and protocol rules governing your access to and interaction with QMA Network's autonomous execution router and intelligence platform."
      lastUpdated="March 2026"
      tableOfContents={TOC_ITEMS}
    >
      {/* 1. Acceptance & Eligibility */}
      <section id="acceptance" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">01</span>
          Acceptance of Terms &amp; Eligibility
        </h2>
        <p>
          These Terms of Service (&ldquo;Terms&rdquo;) constitute a binding legal agreement between you (&ldquo;User&rdquo;, &ldquo;you&rdquo;) and <strong>QMA Network</strong> (&ldquo;QMA&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;). By accessing our website, connecting a cryptographic wallet, utilizing our execution router, or calling our API endpoints, you explicitly acknowledge that you have read, understood, and agreed to be bound by these Terms.
        </p>
        <p>
          You represent and warrant that:
        </p>
        <ul>
          <li>You are at least 18 years of age (or the age of legal majority in your jurisdiction).</li>
          <li>You possess full legal capacity to enter into binding agreements.</li>
          <li>You are not a citizen, resident, or entity located in any jurisdiction subject to comprehensive sanctions enforced by the United States Office of Foreign Assets Control (OFAC), the European Union, the United Nations, or the United Kingdom.</li>
          <li>Your use of QMA complies with all applicable local, national, and international laws and regulations.</li>
        </ul>
      </section>

      {/* 2. Non-Custodial Protocol */}
      <section id="protocol-nature" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">02</span>
          Non-Custodial Protocol Architecture
        </h2>
        <p>
          QMA provides decentralized, non-custodial software tools and execution infrastructure. 
        </p>
        <div className="legal-callout">
          <div className="legal-callout-title">
            <CheckCircle size={16} />
            Self-Sovereign Asset Control
          </div>
          <p style={{ margin: 0 }}>
            At no point does QMA take custody, possession, escrow, or fiduciary control of your digital assets, tokens, private keys, or wallet credentials. All transactions are constructed client-side or validated deterministically and must be signed cryptographically by your authorized wallet.
          </p>
        </div>
        <p>
          You are solely and exclusively responsible for the security of your private keys, seed phrases, and wallet configurations. If you lose access to your private credentials, QMA cannot restore your access or recover your funds.
        </p>
      </section>

      {/* 3. No Financial Advice */}
      <section id="no-financial-advice" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">03</span>
          No Financial, Legal, or Investment Advice
        </h2>
        <div className="legal-callout legal-callout-warning">
          <div className="legal-callout-title">
            <AlertTriangle size={16} />
            Strict Disclaimer
          </div>
          <p style={{ margin: 0 }}>
            Nothing contained in QMA software, documentation, user interfaces, or AI-generated outputs constitutes financial, investment, legal, tax, or regulatory advice.
          </p>
        </div>
        <p>
          QMA provides algorithmic market data aggregation, historical analogs, deterministic execution routing, and automated tool-use parameters for technological efficiency only. 
        </p>
        <p>
          Past historical performance, liquidity depth calculations, and AI-assisted recommendations do not guarantee future results. You should evaluate all risks and consult with qualified independent professional advisors before engaging in digital asset transactions.
        </p>
      </section>

      {/* 4. Autonomous Agent Operations */}
      <section id="agent-operations" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">04</span>
          Autonomous Agent Operations &amp; Spend Guards
        </h2>
        <p>
          QMA incorporates multi-agent reasoning systems that assist in finding optimal routing paths, checking liquidity constraints, and validating settlement conditions.
        </p>
        <ul>
          <li>
            <strong>Deterministic Guardrails:</strong> While agents utilize advanced Large Language Models (including Claude 3.5 Sonnet and Haiku) for reasoning and intent parsing, all proposed actions are subject to strict programmatic spend limit guards, slippage boundaries, and circuit breakers before execution.
          </li>
          <li>
            <strong>User Confirmation:</strong> Unless you have explicitly configured an autonomous delegate or gasless session lease with predefined budget caps, every transaction requires explicit signing from your connected wallet.
          </li>
          <li>
            <strong>Simulation Caveats:</strong> Pre-execution simulations are estimates based on the blockchain state at the time of calculation. Actual block inclusion, gas costs, and execution routes may fluctuate due to dynamic on-chain conditions.
          </li>
        </ul>
      </section>

      {/* 5. Blockchain & Protocol Risks */}
      <section id="blockchain-risks" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">05</span>
          Assumption of Blockchain &amp; Smart Contract Risks
        </h2>
        <p>
          By interacting with QMA, you acknowledge and willingly assume all inherent risks associated with cryptographic systems, decentralized networks, and smart contract execution:
        </p>
        <ul>
          <li><strong>Smart Contract Vulnerabilities:</strong> Third-party smart contracts (such as Uniswap V2 pools, lending markets, or token bridges) may contain undetected bugs, exploits, or structural failures.</li>
          <li><strong>Network Congestion &amp; Slippage:</strong> High network traffic, MEV frontrunning, and sudden liquidity shortages may cause transactions to experience slippage or revert, incurring non-refundable network gas fees.</li>
          <li><strong>Stablecoin &amp; Peg Volatility:</strong> Synthetic tokens, wrapped assets, and fiat-backed stablecoins (such as USDC and EURC) carry independent counterparty and peg stability risks.</li>
          <li><strong>Irreversibility of Transactions:</strong> Blockchain state changes are permanent. Transactions confirmed on-chain cannot be cancelled, modified, or refunded by QMA.</li>
        </ul>
      </section>

      {/* 6. Prohibited Activities */}
      <section id="prohibited-activities" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">06</span>
          Prohibited Activities
        </h2>
        <p>You agree not to use the QMA platform or API to:</p>
        <ul>
          <li>Violate any applicable international, federal, state, or local law, statute, or ordinance.</li>
          <li>Engage in or facilitate money laundering, terrorist financing, or proliferation of weapons of mass destruction.</li>
          <li>Evade international financial sanctions or transact on behalf of designated restricted entities.</li>
          <li>Conduct market manipulation, spoofing, wash trading, or predatory MEV exploitation that undermines network integrity.</li>
          <li>Attempt to reverse-engineer, exploit, spam, overload, or compromise QMA backend infrastructure, nodes, or agent coordination services.</li>
        </ul>
      </section>

      {/* 7. Intellectual Property */}
      <section id="ip-licenses" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">07</span>
          Intellectual Property &amp; Open Source
        </h2>
        <p>
          All proprietary algorithms, user interface designs, visual brand assets, logos, and documentation related to QMA Network are the intellectual property of QMA Foundation.
        </p>
        <p>
          Open-source repositories and SDK modules published by QMA are licensed under the applicable open-source licenses specified within their respective code repositories (such as MIT or Apache 2.0). Nothing in these Terms restricts your rights under those open-source licenses.
        </p>
      </section>

      {/* 8. Disclaimer of Warranties */}
      <section id="warranties-disclaimer" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">08</span>
          Disclaimer of Warranties
        </h2>
        <p>
          QMA PLATFORM, INTERFACES, APIS, AND AUTONOMOUS ROUTING SYSTEMS ARE PROVIDED STRICTLY ON AN <strong>&ldquo;AS IS&rdquo;</strong> AND <strong>&ldquo;AS AVAILABLE&rdquo;</strong> BASIS, WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED.
        </p>
        <p>
          TO THE MAXIMUM EXTENT PERMITTED BY LAW, QMA DISCLAIMS ALL WARRANTIES, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, SECURE, OR FREE FROM HARMFUL CODE.
        </p>
      </section>

      {/* 9. Limitation of Liability */}
      <section id="liability-limitation" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">09</span>
          Limitation of Liability
        </h2>
        <p>
          IN NO EVENT SHALL QMA NETWORK, ITS FOUNDERS, CONTRIBUTORS, DIRECTORS, OR PARTNERS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS, DATA, USE, GOODWILL, OR DIGITAL ASSETS, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF THE PROTOCOL.
        </p>
        <p>
          IN JURISDICTIONS THAT DO NOT PERMIT THE EXCLUSION OR LIMITATION OF CERTAIN DAMAGES, OUR AGGREGATE LIABILITY SHALL BE LIMITED TO THE FULLEST EXTENT PERMISSIBLE BY APPLICABLE LAW, NOT TO EXCEED ONE HUNDRED UNITED STATES DOLLARS ($100.00 USD).
        </p>
      </section>

      {/* 10. Indemnification */}
      <section id="indemnification" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">10</span>
          Indemnification
        </h2>
        <p>
          You agree to defend, indemnify, and hold harmless QMA Network, its contributors, and affiliates from and against any claims, liabilities, damages, losses, and reasonable legal expenses arising out of or related to your breach of these Terms, your violation of applicable laws, or your misuse of the platform.
        </p>
      </section>

      {/* 11. Governing Law & Disputes */}
      <section id="governing-law" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">11</span>
          Governing Law &amp; Dispute Resolution
        </h2>
        <p>
          These Terms and any dispute arising out of your use of QMA shall be governed by and construed in accordance with standard international commercial law principles and the laws of the British Virgin Islands, without regard to conflict of law rules.
        </p>
        <p>
          Any dispute, controversy, or claim shall first be submitted to good-faith informal negotiation for at least thirty (30) days prior to initiating formal binding arbitration under the rules of the International Chamber of Commerce (ICC).
        </p>
      </section>

      {/* 12. Contact */}
      <section id="contact" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">12</span>
          Contact &amp; Official Inquiries
        </h2>
        <p>
          For questions, formal notices, or compliance inquiries regarding these Terms of Service, please contact our legal desk:
        </p>
        <div className="legal-contact-card">
          <h4>QMA Network Legal Counsel</h4>
          <p style={{ margin: 0, color: "var(--t2)" }}>
            Official communication channel for regulatory, compliance, and governance notices:
          </p>
          <a href="mailto:legal@qma.network" className="legal-contact-email">
            legal@qma.network
          </a>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--t3)" }}>
            QMA Foundation &bull; Decentralized Autonomous Technology Governance
          </p>
        </div>
      </section>
    </LegalLayout>
  );
}

export default TermsPage;
