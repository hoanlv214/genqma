import React, { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  HomePage,
  OperationsPage,
  IntelligencePage,
  MarketplacePage,
  ProfilePage,
  TractionPage,
  SwapPage,
  ConnectPage,
  NotFoundPage,
} from "@/pages";
import { routeFromPath, pathForRoute, type QmaRoute } from "@/app/routes";
import { AgentWalletProvider } from "@/state/agentWalletStore";
import ThemeSwitcher from "@/components/dev/ThemeSwitcher";

const LazyApiDocsPage = lazy(() =>
  import("@/pages/ApiDocs").then((m) => ({ default: m.ApiDocsPage }))
);

export function AppRoutes() {
  const initialRoute = useMemo(() => routeFromPath(window.location.pathname), []);
  const [route, setRoute] = useState<QmaRoute>(initialRoute);

  const navigate = (next: QmaRoute) => {
    setRoute(next);
    window.history.pushState({}, "", pathForRoute(next));
  };

  useEffect(() => {
    const handlePopState = () => {
      setRoute(routeFromPath(window.location.pathname));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    document.body.classList.remove(
      "landing-body",
      "body",
      "marketplace-body",
      "profile-body",
      "traction-body",
      "operations-body",
      "notfound-body",
      "swap-body"
    );

    if (route === "landing") {
      document.body.classList.add("landing-body");
    } else if (route === "app") {
      document.body.classList.add("body");
    } else if (route === "marketplace") {
      document.body.classList.add("marketplace-body");
    } else if (route === "profile" || route === "connect") {
      document.body.classList.add("profile-body");
    } else if (route === "traction") {
      document.body.classList.add("traction-body");
    } else if (route === "operations") {
      document.body.classList.add("operations-body");
    } else if (route === "swap") {
      document.body.classList.add("swap-body");
    } else if (route === "not_found") {
      document.body.classList.add("notfound-body");
    }
  }, [route]);

  const agentWalletEnabled = ["app", "marketplace", "profile", "traction", "swap"].includes(route);

  return (
    <AgentWalletProvider enabled={agentWalletEnabled}>
      <ThemeSwitcher />
      {route === "landing" && <HomePage onNavigate={navigate} />}
      {route === "app" && <IntelligencePage onNavigate={navigate} />}
      {route === "connect" && <ConnectPage />}
      {route === "marketplace" && <MarketplacePage onNavigate={navigate} />}
      {route === "profile" && <ProfilePage onNavigate={navigate} />}
      {route === "traction" && <TractionPage onNavigate={navigate} />}
      {route === "operations" && <OperationsPage onNavigate={navigate} />}
      {route === "swap" && <SwapPage onNavigate={navigate} />}
      {route === "not_found" && <NotFoundPage onNavigate={navigate} />}
      {route === "docs" && (
        <Suspense fallback={null}>
          <LazyApiDocsPage />
        </Suspense>
      )}
    </AgentWalletProvider>
  );
}

export default AppRoutes;
