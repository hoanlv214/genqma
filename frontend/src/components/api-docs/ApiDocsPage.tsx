import { ApiReferenceReact } from "@scalar/api-reference-react";
import "@scalar/api-reference-react/style.css";
import { API_BASE_URL } from "../../services/api";

export function ApiDocsPage() {
  const parts = window.location.pathname.split("/");
  const audience = parts.length > 2 && parts[2] ? parts[2] : "";

  const openApiUrl = audience ? `${API_BASE_URL}/openapi/${audience}.json` : `${API_BASE_URL}/openapi.json`;
  const tabs = [
    { id: "public", label: "Public" },
    { id: "agent", label: "Agent" },
    { id: "wallet", label: "Wallet" },
    { id: "admin", label: "Admin" },
    { id: "private", label: "Private" },
    { id: "", label: "Full" },
  ];
  const audienceDescription = {
    public: "Unauthenticated and optional-auth operations.",
    agent: "Decision, purchase, report, and autonomous-session APIs for agents.",
    wallet: "Wallet history, entitlements, reports, payments, and owner session APIs.",
    admin: "Provider review, operations, platform, and payment diagnostics.",
    private: "Operations requiring wallet, paid-access, invoice, admin, signed-payload, or worker proof.",
    full: "Complete supported external API. Gateway-only /api/internal routes remain hidden.",
  }[audience || "full"];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '10px 20px', background: '#1e1e1e', color: 'white', display: 'flex', gap: '16px', alignItems: 'center', borderBottom: '1px solid #333', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: '1.1rem' }}>QMA API Docs:</strong>
        <nav aria-label="API documentation audience" style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          {tabs.map((tab) => (
            <a
              key={tab.id || "full"}
              href={tab.id ? `/docs/${tab.id}` : "/docs"}
              aria-current={audience === tab.id ? "page" : undefined}
              style={{
                color: audience === tab.id ? '#4ade80' : '#ccc',
                textDecoration: 'none',
                fontWeight: audience === tab.id ? 'bold' : 'normal',
              }}
            >
              {tab.label}
            </a>
          ))}
        </nav>
        <span style={{ color: '#9ca3af', fontSize: '0.82rem' }}>{audienceDescription}</span>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <ApiReferenceReact configuration={{ url: openApiUrl }} />
      </div>
    </div>
  );
}
