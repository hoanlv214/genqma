// src/lib/theme.ts
import { useCallback, useEffect, useState } from "react";

export type ThemeDef = {
  id: string;
  label: string;
  /** 4 màu xem trước trong nút chọn: nền, bề mặt, accent, success */
  swatch: [string, string, string, string];
};

/** Thêm theme mới: thêm 1 dòng ở đây + 1 khối [data-theme] trong themes.css */
export const THEMES: ThemeDef[] = [
  { id: "treasury",    label: "Treasury (v2)", swatch: ["#09090b", "#111827", "#6366f1", "#10b981"] },
  { id: "indigo-sky",  label: "Indigo Sky",    swatch: ["#0b1020", "#151d3f", "#6366f1", "#34d399"] },
  { id: "emerald",     label: "Emerald",       swatch: ["#08110f", "#10211d", "#10b981", "#34d399"] },
  { id: "paper-light", label: "Paper Light",   swatch: ["#faf9f5", "#ffffff", "#4f46e5", "#059669"] },
];

export const DEFAULT_THEME = "treasury";
const STORAGE_KEY = "qma-theme";

const isValid = (id: string | null): id is string =>
  !!id && THEMES.some((t) => t.id === id);

/** Thứ tự ưu tiên: ?theme=… trên URL > localStorage > mặc định */
export function resolveInitialTheme(): string {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("theme");
    if (isValid(fromUrl)) return fromUrl;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isValid(stored)) return stored;
  } catch {
    /* localStorage bị chặn: dùng mặc định */
  }
  return DEFAULT_THEME;
}

export function applyTheme(id: string, persist = true) {
  document.documentElement.setAttribute("data-theme", id);
  if (persist) {
    try { localStorage.setItem(STORAGE_KEY, id); } catch { /* ignore */ }
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<string>(() =>
    document.documentElement.getAttribute("data-theme") ?? resolveInitialTheme()
  );

  useEffect(() => { applyTheme(theme); }, [theme]);

  const setTheme = useCallback((id: string) => {
    if (isValid(id)) setThemeState(id);
  }, []);

  const cycle = useCallback(() => {
    const i = THEMES.findIndex((t) => t.id === theme);
    setThemeState(THEMES[(i + 1) % THEMES.length].id);
  }, [theme]);

  return { theme, setTheme, cycle, themes: THEMES };
}
