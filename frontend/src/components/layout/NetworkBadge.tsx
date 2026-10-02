import { useState, useRef, useEffect } from "react";
import { ARC_CHAIN, IS_TESTNET, NETWORK_MODE } from "../../config/network";
import { cn } from "../../utils/cn";
import "./GlobalHeader.css";

export interface NetworkBadgeProps {
  className?: string;
  showDetailsOnClick?: boolean;
}

export function NetworkBadge({ className = "", showDetailsOnClick = true }: NetworkBadgeProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const isTest = IS_TESTNET;

  return (
    <div
      ref={containerRef}
      className={cn("network-badge network-badge-wrapper relative inline-flex items-center", className)}
    >
      <button
        type="button"
        className={cn(
          "network-badge__btn network-badge-btn inline-flex items-center gap-[7px] py-[5px] px-3 rounded-full border font-mono text-[11px] font-semibold tracking-wide transition-all duration-200 outline-none select-none",
          isTest
            ? "network-badge__btn--testnet bg-sky-500/10 border-sky-500/30 text-sky-200 hover:bg-sky-500/20 hover:border-sky-500/50"
            : "network-badge__btn--mainnet bg-emerald-500/10 border-emerald-500/30 text-emerald-200 hover:bg-emerald-500/20 hover:border-emerald-500/50",
          showDetailsOnClick ? "cursor-pointer" : "cursor-default"
        )}
        onClick={() => showDetailsOnClick && setOpen(!open)}
        title={`${ARC_CHAIN.name} (Chain ID: ${ARC_CHAIN.chainId}) — Click for details`}
      >
        <span
          className={cn(
            "network-badge__dot w-[7px] h-[7px] rounded-full inline-block shrink-0 transition-shadow duration-200",
            isTest
              ? "network-badge__dot--testnet bg-sky-400 shadow-[0_0_8px_#38bdf8]"
              : "network-badge__dot--mainnet bg-emerald-400 shadow-[0_0_8px_#10b981]"
          )}
        />
        <span className="network-badge__name">{ARC_CHAIN.name}</span>
        {showDetailsOnClick && (
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            width="12"
            height="12"
            className={cn(
              "network-badge__chevron opacity-65 transition-transform duration-200",
              open && "network-badge__chevron--open rotate-180"
            )}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        )}
      </button>

      {/* Network Details Popover */}
      {open && (
        <div
          className="network-badge__popover network-badge-popover absolute top-[calc(100%+8px)] right-0 w-[280px] bg-surface-1 border border-bdr rounded-xl p-4 shadow-[0_16px_40px_rgba(0,0,0,0.65)] z-[1100] backdrop-blur-xl"
        >
          <div className="network-badge__popover-header flex justify-between items-center mb-3 pb-2 border-b border-bdr">
            <span className="network-badge__popover-title text-[11px] uppercase tracking-wider text-t3 font-bold">
              Network Profile
            </span>
            <span
              className={cn(
                "network-badge__popover-badge text-[10px] font-mono px-2 py-0.5 rounded border font-bold",
                isTest
                  ? "network-badge__popover-badge--testnet bg-sky-500/10 text-sky-400 border-sky-500/30"
                  : "network-badge__popover-badge--mainnet bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
              )}
            >
              {NETWORK_MODE.toUpperCase()}
            </span>
          </div>

          <div className="network-badge__popover-body flex flex-col gap-2 text-[11.5px]">
            <div className="network-badge__popover-row flex justify-between">
              <span className="network-badge__popover-label text-t3">Chain ID</span>
              <span className="network-badge__popover-value font-mono text-t1 font-semibold">
                {ARC_CHAIN.chainId}
              </span>
            </div>
            <div className="network-badge__popover-row flex justify-between">
              <span className="network-badge__popover-label text-t3">Native Gas</span>
              <span className="network-badge__popover-value text-sky-400 font-semibold font-mono">
                USDC (~$0.01)
              </span>
            </div>
            <div className="network-badge__popover-row flex justify-between">
              <span className="network-badge__popover-label text-t3">Block Finality</span>
              <span className="network-badge__popover-value text-emerald-400 font-semibold font-mono">
                &lt; 500ms
              </span>
            </div>
          </div>

          <div className="network-badge__popover-footer mt-3 pt-2.5 border-t border-bdr">
            <a
              href={ARC_CHAIN.explorerUrl}
              target="_blank"
              rel="noreferrer"
              className="network-badge__popover-link flex items-center justify-center gap-1.5 w-full py-1.5 px-3 rounded-md bg-surface-2 border border-bdr text-sky-400 text-[11px] font-semibold no-underline hover:bg-surface-3 hover:border-sky-500/40 hover:text-sky-300 transition-all"
            >
              <span>View Explorer on Arcscan</span>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="12" height="12">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
