import type { QmaRoute } from "../../app/routes";

interface NotFoundPageProps {
  onNavigate: (route: QmaRoute) => void;
}

export function NotFoundPage({ onNavigate }: NotFoundPageProps) {
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

        /* Ambient glowing background blobs */
        .notfound-glow-1 {
          position: absolute;
          width: 450px;
          height: 450px;
          background: radial-gradient(circle, rgba(147, 51, 234, 0.15) 0%, rgba(0, 0, 0, 0) 70%);
          top: 15%;
          left: 10%;
          border-radius: 50%;
          filter: blur(40px);
          animation: floatBlob 8s infinite alternate ease-in-out;
        }

        .notfound-glow-2 {
          position: absolute;
          width: 450px;
          height: 450px;
          background: radial-gradient(circle, rgba(59, 130, 246, 0.12) 0%, rgba(0, 0, 0, 0) 70%);
          bottom: 15%;
          right: 10%;
          border-radius: 50%;
          filter: blur(40px);
          animation: floatBlob 10s infinite alternate-reverse ease-in-out;
        }

        @keyframes floatBlob {
          0% { transform: translateY(0px) scale(1); }
          100% { transform: translateY(30px) scale(1.1); }
        }

        /* Abstract cyber grid backdrop */
        .notfound-grid {
          position: absolute;
          inset: 0;
          background-image: 
            linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
          background-size: 40px 40px;
          background-position: center;
          mask-image: radial-gradient(circle at center, black 40%, transparent 80%);
          pointer-events: none;
        }

        .notfound-card {
          background: rgba(15, 10, 25, 0.45);
          backdrop-filter: blur(16px) saturate(180%);
          -webkit-backdrop-filter: blur(16px) saturate(180%);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 24px;
          padding: 50px 40px;
          max-width: 480px;
          width: 100%;
          text-align: center;
          box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
          position: relative;
          z-index: 10;
        }

        .notfound-card::before {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: 24px;
          padding: 1px;
          background: linear-gradient(135deg, rgba(147, 51, 234, 0.3) 0%, rgba(59, 130, 246, 0.1) 100%);
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }

        .notfound-404 {
          font-size: 110px;
          font-weight: 900;
          line-height: 0.9;
          margin: 0;
          background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          filter: drop-shadow(0 0 15px rgba(168, 85, 247, 0.35));
          letter-spacing: -3px;
        }

        .notfound-title {
          font-size: 22px;
          font-weight: 700;
          margin: 24px 0 12px 0;
          color: #f3f4f6;
          letter-spacing: -0.5px;
        }

        .notfound-desc {
          font-size: 14px;
          color: #9ca3af;
          line-height: 1.6;
          margin: 0 0 32px 0;
        }

        .notfound-btn {
          background: linear-gradient(135deg, #9333ea 0%, #2563eb 100%);
          color: #fff;
          font-size: 14px;
          font-weight: 600;
          padding: 14px 28px;
          border: none;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.25s ease;
          box-shadow: 0 8px 20px rgba(147, 51, 234, 0.3);
          display: inline-flex;
          align-items: center;
          gap: 8px;
          text-decoration: none;
        }

        .notfound-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 12px 28px rgba(147, 51, 234, 0.45);
          filter: brightness(1.1);
        }

        .notfound-btn:active {
          transform: translateY(0);
        }
      `}</style>
      
      <div className="notfound-glow-1" />
      <div className="notfound-glow-2" />
      <div className="notfound-grid" />

      <div className="notfound-card">
        <h1 className="notfound-404">404</h1>
        <h2 className="notfound-title">Lost in the Quantum Stream</h2>
        <p className="notfound-desc">
          The quantitative report or terminal address you are looking for has been liquidated, expired, or does not exist in our index database.
        </p>
        <button className="notfound-btn" onClick={() => onNavigate("landing")}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          Return to Command Center
        </button>
      </div>
    </div>
  );
}
