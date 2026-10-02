import React from "react";
import { LandingHeader } from "@/components/layout/LandingHeader";
import type { QmaRoute } from "@/app/routes";
import { cn } from "@/utils/cn";

export interface LandingLayoutProps {
  children: React.ReactNode;
  onNavigate?: (route: QmaRoute) => void;
  className?: string;
}

export function LandingLayout({
  children,
  onNavigate = () => {},
  className,
}: LandingLayoutProps) {
  return (
    <div className={cn("min-h-screen landing-page bg-bg-1 text-t1 flex flex-col font-sans", className)}>
      <LandingHeader onNavigate={onNavigate} />
      <main className="flex-1 w-full">
        {children}
      </main>
    </div>
  );
}

export default LandingLayout;
