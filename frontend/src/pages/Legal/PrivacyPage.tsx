import React from "react";
import { AlertCircle, Lock, ShieldCheck, Cpu, Database, Mail } from "lucide-react";
import type { QmaRoute } from "@/app/routes";
import { LegalLayout } from "./LegalLayout";

export interface PrivacyPageProps {
  onNavigate?: (route: QmaRoute) => void;
}

const TOC_ITEMS = [
  { id: "overview", label: "Overview & Controller" },
  { id: "non-custodial", label: "Non-Custodial Architecture" },
  { id: "data-collected", label: "Information We Collect" },
  { id: "data-not-collected", label: "Information We Never Collect" },
  { id: "ai-inference", label: "AI & LLM Processing" },
  { id: "how-we-use", label: "How We Use Information" },
  { id: "cookies-telemetry", label: "Cookies & Storage" },
  { id: "third-parties", label: "Third-Party Services" },
  { id: "user-rights", label: "User Rights (GDPR / CCPA)" },
  { id: "security-retention", label: "Security & Retention" },
  { id: "contact", label: "Contact & Inquiries" },
];

export function PrivacyPage({ onNavigate = () => {} }: PrivacyPageProps) {
  return (
    <LegalLayout
      activeRoute="privacy"
      onNavigate={onNavigate}
      title="Privacy Policy"
      subtitle="How QMA Network processes, safeguards, and respects data across our autonomous financial intelligence and non-custodial execution infrastructure."
      lastUpdated="March 2026"
      tableOfContents={TOC_ITEMS}
    >
      {/* 1. Overview */}
      <section id="overview" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">01</span>
          Overview &amp; Data Controller
        </h2>
        <p>
          This Privacy Policy explains how <strong>QMA Network</strong> (&ldquo;QMA&rdquo;, &ldquo;we&rdquo;, &ldquo;our&rdquo;, or &ldquo;us&rdquo;) handles information collected through our web applications, API endpoints, SDKs, autonomous intelligence agents, and smart contract execution routers.
        </p>
        <p>
          We are committed to operating with radical transparency and adhering to rigorous privacy standards, including the European Union General Data Protection Regulation (GDPR) and the California Consumer Privacy Act (CCPA).
        </p>
        <div className="legal-callout">
          <div className="legal-callout-title">
            <ShieldCheck size={16} />
            Core Privacy Principle
          </div>
          <p style={{ margin: 0 }}>
            We practice strict data minimization. QMA is engineered from the ground up to operate without requiring your real-world identity, bank accounts, or personal identifiable documents.
          </p>
        </div>
      </section>

      {/* 2. Non-Custodial Architecture */}
      <section id="non-custodial" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">02</span>
          Non-Custodial Architecture
        </h2>
        <p>
          QMA is a non-custodial protocol. When you connect your self-hosted wallet (e.g., via Web3 connectors or Circle agent wallets), you retain 100% exclusive control and custody over your private keys, cryptographic credentials, and digital assets at all times.
        </p>
        <p>
          We cannot access your funds, initiate transactions without your explicit cryptographic authorization, or reverse transactions executed on decentralized blockchains.
        </p>
      </section>

      {/* 3. Information We Collect */}
      <section id="data-collected" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">03</span>
          Information We Collect
        </h2>
        <p>We collect only the minimum information necessary to maintain platform uptime, route transactions, and prevent system exploitation:</p>
        <ul>
          <li>
            <strong>Public Blockchain Information:</strong> When you connect your wallet or execute an autonomous routing task, we process public on-chain identifiers, including public wallet addresses, transaction hashes, smart contract addresses, token balances, and interaction receipts. Blockchain data is inherently public and immutable.
          </li>
          <li>
            <strong>Technical &amp; Telemetry Data:</strong> To guarantee high-throughput routing performance, our servers automatically log anonymous technical metrics such as browser type, operating system, anonymized IP addresses (hashed for fraud prevention), latency metrics, RPC query response times, and error event logs.
          </li>
          <li>
            <strong>Voluntary Correspondence:</strong> If you contact us directly for customer support, bug bounty submissions, or institutional inquiries, we collect your email address and any details provided in your inquiry.
          </li>
        </ul>
      </section>

      {/* 4. Information We Never Collect */}
      <section id="data-not-collected" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">04</span>
          Information We Explicitly Never Collect
        </h2>
        <div className="legal-callout legal-callout-warning">
          <div className="legal-callout-title">
            <AlertCircle size={16} />
            Sensitive Data Shield
          </div>
          <p style={{ margin: 0 }}>
            QMA servers, developers, and autonomous agents will NEVER prompt for, collect, or store:
          </p>
        </div>
        <ul>
          <li>Private keys, mnemonic seed phrases, or wallet recovery passwords.</li>
          <li>Government-issued identification numbers, passports, or social security numbers.</li>
          <li>Traditional banking credentials, credit card numbers, or physical billing addresses.</li>
          <li>Biometric data or personal tracking identifiers across external websites.</li>
        </ul>
      </section>

      {/* 5. AI & LLM Processing */}
      <section id="ai-inference" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">05</span>
          Artificial Intelligence &amp; LLM Processing
        </h2>
        <p>
          QMA employs cutting-edge Large Language Models (LLMs), primarily the <strong>Claude 3.5 family by Anthropic</strong>, to power autonomous agent workflows, market intent parsing, structured tool calling, and anomaly detection.
        </p>
        <ul>
          <li>
            <strong>Data Minimization in Prompts:</strong> Prompts dispatched to LLM inference pipelines contain only abstract market telemetry, public on-chain parameters, and mathematical constraints. We strictly filter out any personal data prior to model invocation.
          </li>
          <li>
            <strong>Zero Model Training:</strong> Under our enterprise API tier agreements with AI providers, data submitted via QMA inference endpoints is never used to train, retrain, or improve foundational AI models.
          </li>
          <li>
            <strong>Deterministic Validation:</strong> All AI-generated outputs (such as swap routes, liquidity splits, and invoice claims) pass through programmatic state machines and spend limit guards before any on-chain transaction can be signed.
          </li>
        </ul>
      </section>

      {/* 6. How We Use Information */}
      <section id="how-we-use" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">06</span>
          How We Use Information
        </h2>
        <p>The information we collect is utilized strictly for the following operational purposes:</p>
        <ul>
          <li>To compute optimal routing paths across decentralized exchanges and cross-currency liquidity pools.</li>
          <li>To enforce real-time spend limits, circuit breakers, and anomaly detection protocols.</li>
          <li>To display historical execution receipts, proof-of-settlement ledgers, and user wallet analytics.</li>
          <li>To diagnose network bottlenecks, prevent Distributed Denial of Service (DDoS) attacks, and maintain node infrastructure.</li>
          <li>To comply with mandatory legal requirements and sanctions enforcement.</li>
        </ul>
      </section>

      {/* 7. Cookies & Storage */}
      <section id="cookies-telemetry" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">07</span>
          Cookies &amp; Local Storage
        </h2>
        <p>
          We do not use tracking cookies or third-party marketing beacons. We use modern browser local storage (LocalStorage and SessionStorage) exclusively for essential functional purposes:
        </p>
        <ul>
          <li>Storing your theme preference (Light, Dark, or System mode).</li>
          <li>Preserving active Web3 connector session state and selected network chains.</li>
          <li>Caching verified RPC node endpoints to accelerate load times.</li>
        </ul>
      </section>

      {/* 8. Third-Party Services */}
      <section id="third-parties" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">08</span>
          Third-Party Services &amp; Networks
        </h2>
        <p>
          When you interact with QMA, your requests may communicate with decentralized infrastructure and external third-party services, each governed by their respective privacy policies:
        </p>
        <ul>
          <li><strong>Arc Network &amp; Circle Gateway:</strong> For USDC/EURC gasless settlement and cross-chain messaging.</li>
          <li><strong>RPC Node Providers:</strong> Such as Infura, Alchemy, or private validator nodes for querying blockchain states.</li>
          <li><strong>Decentralized Liquidity Pools:</strong> Uniswap V2, Xylo, Lunex, and native AMM smart contracts.</li>
        </ul>
      </section>

      {/* 9. User Rights */}
      <section id="user-rights" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">09</span>
          User Rights (GDPR &amp; CCPA Compliance)
        </h2>
        <p>Depending on your jurisdiction, you possess specific legal rights regarding your data:</p>
        <ul>
          <li><strong>Right to Know / Access:</strong> You may request confirmation of whether we hold any off-chain personal data related to you.</li>
          <li><strong>Right to Erasure / Deletion:</strong> You may request the deletion of any off-chain logs or email correspondence associated with your address.</li>
          <li><strong>On-Chain Limitation:</strong> Please note that due to the immutable nature of public distributed ledgers, data already confirmed on a blockchain cannot be modified or erased by any party.</li>
        </ul>
      </section>

      {/* 10. Security & Retention */}
      <section id="security-retention" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">10</span>
          Data Security &amp; Retention
        </h2>
        <p>
          We employ industry-standard security practices, including TLS 1.3 encryption in transit, strict access control lists (ACLs) for backend infrastructure, and automated vulnerability scanning.
        </p>
        <p>
          Off-chain server telemetry and error logs are automatically rotated and purged after 90 days unless required for active security investigations or legal compliance.
        </p>
      </section>

      {/* 11. Contact */}
      <section id="contact" className="legal-section">
        <h2 className="legal-section-h2">
          <span className="legal-section-num">11</span>
          Contact &amp; Data Protection Officer
        </h2>
        <p>
          If you have questions, feedback, or requests regarding this Privacy Policy or our data handling practices, please contact our privacy and compliance desk:
        </p>
        <div className="legal-contact-card">
          <h4>QMA Network Legal &amp; Privacy Office</h4>
          <p style={{ margin: 0, color: "var(--t2)" }}>
            For privacy inquiries, GDPR data requests, or compliance disclosures:
          </p>
          <a href="mailto:legal@qma.network" className="legal-contact-email">
            legal@qma.network
          </a>
          <p style={{ margin: 0, fontSize: "13px", color: "var(--t3)" }}>
            Physical Address: QMA Foundation, International Technology &amp; Digital Assets Governance.
          </p>
        </div>
      </section>
    </LegalLayout>
  );
}

export default PrivacyPage;
