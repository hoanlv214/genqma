import React from "react";
import { GlobalHeader } from "@/components/layout/GlobalHeader";
import { useWalletStore } from "@/state/walletStore";
import type { QmaRoute } from "@/app/routes";
import { cn } from "@/utils/cn";

export interface MainLayoutProps {
  children: React.ReactNode;
  activePage?: QmaRoute;
  onNavigate?: (route: QmaRoute) => void;
  className?: string;
  containerClassName?: string;
  hideHeader?: boolean;
  rightControls?: React.ReactNode;
  onConnect?: () => void;
  onDisconnect?: () => void;
  userRole?: string;
  onOpenDeposit?: () => void;
  onOpenEarnings?: () => void;
  onOpenWithdrawAgent?: () => void;
  onOpenDepositAgent?: () => void;
}

export function MainLayout({
  children,
  activePage = "app",
  onNavigate = () => {},
  className,
  containerClassName,
  hideHeader = false,
  rightControls,
  onConnect,
  onDisconnect,
  userRole,
  onOpenDeposit,
  onOpenEarnings,
  onOpenWithdrawAgent,
  onOpenDepositAgent,
}: MainLayoutProps) {
  const { address, disconnect } = useWalletStore();

  return (
    <div className={cn("min-h-screen bg-bg-1 text-t1 flex flex-col font-sans", className)}>
      {!hideHeader && (
        <GlobalHeader
          activePage={activePage}
          onNavigate={onNavigate}
          walletAddress={address}
          onConnect={onConnect || (() => {})}
          onDisconnect={onDisconnect || disconnect}
          userRole={userRole}
          rightControls={rightControls}
          onOpenDeposit={onOpenDeposit}
          onOpenEarnings={onOpenEarnings}
          onOpenWithdrawAgent={onOpenWithdrawAgent}
          onOpenDepositAgent={onOpenDepositAgent}
        />
      )}
      <main className={cn("flex-1 flex flex-col w-full", containerClassName)}>
        {children}
      </main>
    </div>
  );
}

export default MainLayout;
