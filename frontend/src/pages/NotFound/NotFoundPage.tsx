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
          min-height: 100vh;
          width: 100%;
          background: radial-gradient(circle at center, #0f0c1b 0%, #050209 100%);
          color: #fff;
          font-family: 'Outfit', 'Inter', sans-serif;
          position: relative;
          overflow: hidden;
          padding: 20px;
          box-sizing: border-box;
        }

        .notfound-glow {
          position: absolute;
          width: 500px;
          height: 500px;
          background: radial-gradient(circle, rgba(124, 111, 255, 0.15) 0%, rgba(0, 0, 0, 0) 70%);
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
          gap: 6px;
          padding: 6px 14px;
          border-radius: 20px;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.08);
          font-size: 13px;
          font-weight: 500;
          color: var(--accent, #7C6FFF);
          margin-bottom: 24px;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }

        .notfound-badge .dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--accent, #7C6FFF);
          box-shadow: 0 0 8px var(--accent, #7C6FFF);
        }

        .notfound-code {
          font-size: 120px;
          font-weight: 800;
          line-height: 1;
          margin: 0;
          letter-spacing: -4px;
          background: linear-gradient(180deg, #ffffff 0%, rgba(255, 255, 255, 0.3) 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          text-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }

        .notfound-title {
          font-size: 24px;
          font-weight: 600;
          margin: 16px 0 12px;
          color: #ffffff;
        }

        .notfound-desc {
          font-size: 15px;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.6);
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
          background: var(--accent, #7C6FFF);
          color: #fff;
          font-weight: 600;
          font-size: 14px;
          border: none;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: 0 4px 16px rgba(124, 111, 255, 0.3);
        }

        .notfound-btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(124, 111, 255, 0.4);
        }

        .notfound-btn-secondary {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.05);
          color: #ffffff;
          font-weight: 600;
          font-size: 14px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .notfound-btn-secondary:hover {
          background: rgba(255, 255, 255, 0.08);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .notfound-terminal-box {
          margin-top: 40px;
          padding: 16px 20px;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.4);
          border: 1px solid rgba(255, 255, 255, 0.06);
          font-family: 'JetBrains Mono', monospace;
          font-size: 12px;
          color: rgba(255, 255, 255, 0.4);
          display: flex;
          align-items: center;
          gap: 12px;
          max-width: 100%;
        }

        .notfound-terminal-box .term-prefix {
          color: var(--accent, #7C6FFF);
        }
      `}</style>

      <div className="notfound-glow"></div>

      <div className="notfound-content">
        <div className="notfound-badge">
          <span className="dot"></span>
          <span>Routing Error</span>
        </div>

        <h1 className="notfound-code">404</h1>
        <h2 className="notfound-title">Intelligence Vector Not Found</h2>
        <p className="notfound-desc">
          The requested coordinate does not exist on the Arc network topology. It may have expired or been relocated.
        </p>

        <div className="notfound-actions">
          <button className="notfound-btn-primary" onClick={() => onNavigate("landing")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            Return to Landing
          </button>
          <button className="notfound-btn-secondary" onClick={() => onNavigate("app")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
              <rect width="7" height="9" x="3" y="3" rx="1"></rect>
              <rect width="7" height="5" x="14" y="3" rx="1"></rect>
              <rect width="7" height="9" x="14" y="12" rx="1"></rect>
              <rect width="7" height="5" x="3" y="16" rx="1"></rect>
            </svg>
            Live Workspace
          </button>
        </div>

        <div className="notfound-terminal-box">
          <span className="term-prefix">$</span>
          <span>arc-trace: null pointer resolving address on active state machine</span>
        </div>
      </div>
    </div>
  );
}

export default NotFoundPage;
