import { ApiReferenceReact } from "@scalar/api-reference-react";
import "@scalar/api-reference-react/style.css";
import { API_BASE_URL } from "@/services/api";
import type { ApiDocsProps } from "./ApiDocs.types";

export function ApiDocsPage(_props: ApiDocsProps) {
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
    <div className="h-screen flex flex-col">
      <div className="px-5 py-2.5 bg-[#1e1e1e] text-white flex gap-4 items-center border-b border-[#333] flex-wrap">
        <strong className="text-[1.1rem] font-bold">QMA API Docs:</strong>
        <nav aria-label="API documentation audience" className="flex gap-4 flex-wrap">
          {tabs.map((tab) => (
            <a
              key={tab.id || "full"}
              href={tab.id ? `/docs/${tab.id}` : "/docs"}
              aria-current={audience === tab.id ? "page" : undefined}
              className={audience === tab.id ? "text-green-400 font-bold no-underline" : "text-gray-300 hover:text-white no-underline"}
            >
              {tab.label}
            </a>
          ))}
        </nav>
        <span className="text-gray-400 text-[0.82rem]">{audienceDescription}</span>
      </div>
      <div className="flex-1 overflow-auto">
        <ApiReferenceReact configuration={{ url: openApiUrl }} />
      </div>
    </div>
  );
}

export default ApiDocsPage;
