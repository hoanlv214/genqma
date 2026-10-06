import { Home, LayoutDashboard } from "lucide-react";
import type { QmaRoute } from "@/app/routes";
import type { NotFoundProps } from "./NotFound.types";

export function NotFoundPage({ onNavigate = () => {} }: NotFoundProps) {
  return (
    <div className="notfound-container">
      <style>{`
        .notfound-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 100dvh;
          width: 100%;
          background: var(--bg-base);
          color: var(--t1);
          position: relative;
          overflow: hidden;
          padding: 24px;
          box-sizing: border-box;
        }

        .notfound-glow {
          position: absolute;
          width: 500px;
          height: 500px;
          background: radial-gradient(circle, rgb(var(--accent-rgb) / 0.12) 0%, rgba(0, 0, 0, 0) 70%);
          border-radius: 50%;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          pointer-events: none;
          z-index: 1;
        }

        .notfound-content {
          position: relative;
          z-index: 2;
          display: flex;
          flex-direction: column;
          align-items: center;
          max-width: 560px;
          text-align: center;
        }

        .notfound-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 20px;
          background: var(--surface-2);
          border: 1px solid var(--bdr);
          font-size: var(--text-sm);
          font-weight: 500;
          color: var(--accent);
          margin-bottom: 24px;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }

        .notfound-code {
          font-size: 120px;
          font-weight: 800;
          line-height: 1;
          margin: 0;
          letter-spacing: -4px;
          background: linear-gradient(180deg, var(--t1) 0%, rgb(var(--accent-rgb) / 0.35) 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          text-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }

        .notfound-title {
          font-size: 24px;
          font-weight: 600;
          margin: 16px 0 12px;
          color: var(--t1);
        }

        .notfound-desc {
          font-size: 15px;
          line-height: 1.6;
          color: var(--t2);
          margin: 0 0 32px;
        }

        .notfound-actions {
          display: flex;
          gap: 16px;
        }

        .notfound-btn-primary {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          border-radius: 8px;
          background: var(--accent);
          color: var(--on-accent);
          font-weight: 600;
          font-size: var(--text-base);
          border: none;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: 0 4px 16px rgb(var(--accent-rgb) / 0.3);
        }

        .notfound-btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgb(var(--accent-rgb) / 0.4);
        }

        .notfound-btn-secondary {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          border-radius: 8px;
          background: var(--surface-2);
          color: var(--t1);
          font-weight: 600;
          font-size: var(--text-base);
          border: 1px solid var(--bdr);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .notfound-btn-secondary:hover {
          background: var(--surface-3);
          border-color: var(--bdr-md);
        }
      `}</style>

      <div className="notfound-glow"></div>

      <div className="notfound-content">
        <div className="notfound-badge">
          <span>HTTP 404</span>
        </div>

        <h1 className="notfound-code">404</h1>
        <h2 className="notfound-title">Page not found</h2>
        <p className="notfound-desc">
          This page does not exist on QMA. It may have been moved or retired.
          Use the actions below to get back to the live workspace.
        </p>

        <div className="notfound-actions">
          <button className="notfound-btn-primary" onClick={() => onNavigate("landing")}>
            <Home size={16} strokeWidth={2} />
            Return to Landing
          </button>
          <button className="notfound-btn-secondary" onClick={() => onNavigate("app")}>
            <LayoutDashboard size={16} strokeWidth={2} />
            Live Workspace
          </button>
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;
