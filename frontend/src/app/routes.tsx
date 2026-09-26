export type QmaRoute = "landing" | "app" | "profile" | "marketplace" | "traction" | "docs" | "connect" | "swap" | "not_found";

export function routeFromPath(pathname: string): QmaRoute {
  const clean = pathname.replace(/\/$/, "");
  if (clean === "" || clean === "/index.html") return "landing";
  if (clean === "/app_demo" || clean === "/demo") return "app";
  if (clean === "/app") return "app";
  if (clean === "/profile" || clean.startsWith("/profile/") || clean.startsWith("/user")) return "profile";
  if (clean === "/marketplace" || clean.startsWith("/marketplace/")) return "marketplace";
  if (clean === "/traction" || clean.startsWith("/traction/") || clean === "/ledger" || clean.startsWith("/ledger/")) return "traction";
  if (clean === "/swap" || clean.startsWith("/swap/") || clean === "/fx" || clean.startsWith("/fx/") || clean === "/bridge" || clean.startsWith("/bridge/")) return "swap";
  if (clean === "/docs" || clean.startsWith("/docs/")) return "docs";
  if (clean === "/connect") return "connect";
  return "not_found";
}

export function pathForRoute(route: QmaRoute): string {
  if (route === "profile") return "/profile";
  if (route === "marketplace") return "/marketplace";
  if (route === "traction") return "/traction";
  if (route === "swap") return "/swap";
  if (route === "docs") return "/docs";
  if (route === "connect") return "/connect";
  if (route === "app") return "/app";
  if (route === "landing") return "/";
  return "/404";
}
