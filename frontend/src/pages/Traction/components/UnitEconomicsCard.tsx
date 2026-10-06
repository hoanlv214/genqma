import React from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { formatUsdc } from "@/utils/format";
import type { TractionSummary } from "@/services/traction";

interface UnitEconomicsCardProps {
  summary?: TractionSummary | null;
}

export function UnitEconomicsCard({ summary }: UnitEconomicsCardProps) {
  return (
    <Card className="mb-8 rounded-2xl border-bdr bg-surface-1/90 backdrop-blur-md shadow-card overflow-hidden">
      <CardHeader className="p-6 sm:p-7 pb-4 sm:pb-5 border-b-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-success shadow-[0_0_8px_var(--green)]" />
          <span className="font-mono text-xs font-bold text-success tracking-[0.14em] uppercase block">
            Protocol Economics
          </span>
        </div>
        <CardTitle className="text-xl sm:text-2xl font-bold text-t1 tracking-tight">
          Unit Economics &amp; Revenue Split
        </CardTitle>
        <CardDescription className="text-xs sm:text-sm text-t2 leading-relaxed max-w-3xl mt-1">
          Every mechanism below is a live code path, not a projection: the per-query marketplace split, the treasury
          sweep, and the GenLayer-verified performance tiers. The footer strip reads the real settlement ledger.
        </CardDescription>
      </CardHeader>

      <CardContent className="p-6 sm:p-7 pt-0 sm:pt-0">
        {/* 3 Live Mechanism Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
          {/* Mechanism 1 */}
          <div className="bg-surface-2/80 hover:bg-surface-2 border border-accent/25 hover:border-accent/45 rounded-xl p-4 sm:p-5 flex flex-col justify-between transition-colors shadow-sm">
            <div>
              <div className="flex justify-between items-center gap-2 mb-2.5">
                <span className="text-xs font-bold text-accent font-sans">
                  1. Marketplace Split
                </span>
                <Badge variant="dim" size="sm">
                  80% to creators
                </Badge>
              </div>
              <p className="text-xs text-t2 leading-relaxed mb-4">
                On every x402 query the creator receives 80% of the payment. GenLayer-verified win-rate tiers raise it
                to 85, 87.5, or 90%. The platform keeps the remainder as the only marketplace fee.
              </p>
            </div>
            <div className="text-xs font-mono text-t2 bg-surface-1/90 border border-bdr/60 px-3 py-2 rounded-lg flex items-center justify-between">
              <span>Preview 0.002</span>
              <span className="text-t1 font-semibold">Full 0.005 USDC</span>
            </div>
          </div>

          {/* Mechanism 2 */}
          <div className="bg-surface-2/80 hover:bg-surface-2 border border-accent/25 hover:border-accent/45 rounded-xl p-4 sm:p-5 flex flex-col justify-between transition-colors shadow-sm">
            <div>
              <div className="flex justify-between items-center gap-2 mb-2.5">
                <span className="text-xs font-bold text-accent font-sans">
                  2. Treasury Yield
                </span>
                <Badge variant="dim" size="sm">
                  5.0% target APY
                </Badge>
              </div>
              <p className="text-xs text-t2 leading-relaxed mb-4">
                Idle platform USDC sweeps into the USYC ERC-4626 vault on Arc, with just-in-time redemption for
                payables. Earn Kit Morpho vaults are verified on-chain before any deposit is allowed.
              </p>
            </div>
            <div className="text-xs font-mono text-t2 bg-surface-1/90 border border-bdr/60 px-3 py-2 rounded-lg flex items-center justify-between">
              <span>Sweep + redeem on-chain</span>
              <span className="text-accent font-semibold">Euthyna-sealed</span>
            </div>
          </div>

          {/* Mechanism 3 */}
          <div className="bg-surface-2/80 hover:bg-surface-2 border border-accent/25 hover:border-accent/45 rounded-xl p-4 sm:p-5 flex flex-col justify-between transition-colors shadow-sm">
            <div>
              <div className="flex justify-between items-center gap-2 mb-2.5">
                <span className="text-xs font-bold text-accent font-sans">
                  3. Verified Performance Tiers
                </span>
                <Badge variant="dim" size="sm">
                  85 / 87.5 / 90%
                </Badge>
              </div>
              <p className="text-xs text-t2 leading-relaxed mb-4">
                GenLayer validators confirm provider win rates on settled reports. Verified accuracy moves the creator
                share tier automatically; unverified providers stay at the 80% base share.
              </p>
            </div>
            <div className="text-xs font-mono text-t2 bg-surface-1/90 border border-bdr/60 px-3 py-2 rounded-lg flex items-center justify-between">
              <span className="text-t2">SLA verified by</span>
              <span className="text-accent font-semibold">GenLayer Shield</span>
            </div>
          </div>
        </div>

        {/* Live Ledger Facts Strip */}
        <div className="bg-gradient-to-r from-success/10 via-surface-2/50 to-accent/10 border border-success/30 rounded-xl p-4 sm:p-5 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 sm:gap-6 shadow-sm">
          <div className="space-y-1 max-w-xl">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <strong className="text-sm sm:text-base font-semibold text-t1 tracking-tight">
                Live Ledger Facts
              </strong>
            </div>
            <p className="text-xs text-t2 leading-relaxed">
              Constants: creator share 80% base · full report 0.005 USDC · USYC target APY 5.0%. Everything else in
              this strip is read from the settlement ledger at request time.
            </p>
          </div>
          <div className="flex flex-wrap sm:flex-nowrap gap-5 sm:gap-6 items-center w-full lg:w-auto pt-3 lg:pt-0 border-t border-bdr/40 lg:border-t-0">
            <div className="text-left sm:text-right">
              <span className="text-2xs text-t3 uppercase block font-mono tracking-wider mb-0.5">Unique payers</span>
              <strong className="text-sm sm:text-base text-t1 font-mono font-bold tabular-nums">
                {summary ? summary.unique_payers.toLocaleString("en-US") : "—"}
              </strong>
            </div>
            <div className="h-8 w-px bg-bdr/60 hidden sm:block" />
            <div className="text-left sm:text-right">
              <span className="text-2xs text-t3 uppercase block font-mono tracking-wider mb-0.5">Settled volume</span>
              <strong className="text-sm sm:text-base text-success font-mono font-bold tabular-nums">
                {summary ? formatUsdc(summary.settled_volume_usdc) : "—"}
              </strong>
            </div>
            <div className="h-8 w-px bg-bdr/60 hidden sm:block" />
            <div className="text-left sm:text-right">
              <span className="text-2xs text-t3 uppercase block font-mono tracking-wider mb-0.5">Average report</span>
              <strong className="text-sm sm:text-base text-accent font-mono font-bold tabular-nums">
                {summary ? formatUsdc(summary.average_paid_report_usdc) : "—"}
              </strong>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default UnitEconomicsCard;
