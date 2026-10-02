// src/components/dev/ThemeSwitcher.tsx
import { useEffect, useRef, useState } from "react";
import { useTheme } from "../../lib/theme";

/** Chỉ hiện ở dev, hoặc khi mở site với ?themelab=1 (để gửi người khác xem thử) */
const labEnabled = () =>
  import.meta.env.DEV ||
  new URLSearchParams(window.location.search).get("themelab") === "1";

export default function ThemeSwitcher() {
  const { theme, setTheme, cycle, themes } = useTheme();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Alt+T: đổi sang theme kế tiếp. Esc / click ngoài: đóng.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.key.toLowerCase() === "t") { e.preventDefault(); cycle(); }
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [cycle]);

  if (!labEnabled()) return null;

  const current = themes.find((t) => t.id === theme);

  return (
    <div ref={rootRef} style={{ position: "fixed", right: 16, bottom: 16, zIndex: 9999 }}>
      {open && (
        <div
          role="listbox"
          aria-label="Chọn bảng màu"
          style={{
            position: "absolute", right: 0, bottom: "calc(100% + 8px)", width: 260,
            background: "var(--surface-2)", border: "1px solid var(--bdr-strong)",
            borderRadius: 16, padding: 8, boxShadow: "var(--shadow-lg)",
          }}
        >
          {themes.map((t) => {
            const active = t.id === theme;
            return (
              <button
                key={t.id}
                role="option"
                aria-selected={active}
                onClick={() => { setTheme(t.id); setOpen(false); }}
                style={{
                  display: "flex", alignItems: "center", gap: 12, width: "100%",
                  padding: "10px 12px", borderRadius: 12, cursor: "pointer",
                  background: active ? "var(--accent-dim)" : "transparent",
                  border: `1px solid ${active ? "var(--accent)" : "transparent"}`,
                  color: "var(--t1)", fontSize: 14, textAlign: "left",
                }}
              >
                <span style={{ display: "flex", flexShrink: 0 }} aria-hidden>
                  {t.swatch.map((c, i) => (
                    <span
                      key={i}
                      style={{
                        width: 16, height: 16, background: c, marginLeft: i ? -4 : 0,
                        borderRadius: "50%", border: "1px solid var(--bdr-strong)",
                      }}
                    />
                  ))}
                </span>
                <span style={{ flex: 1 }}>{t.label}</span>
                {active && <span style={{ color: "var(--accent-text)", fontSize: 12 }}>Đang dùng</span>}
              </button>
            );
          })}
          <div style={{ padding: "8px 12px 4px", color: "var(--t3)", fontSize: 12 }}>
            Alt+T để chuyển nhanh
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        style={{
          display: "flex", alignItems: "center", gap: 8, height: 40, padding: "0 14px",
          borderRadius: 999, cursor: "pointer", fontSize: 13, fontWeight: 600,
          background: "var(--surface-2)", color: "var(--t1)",
          border: "1px solid var(--bdr-strong)", boxShadow: "var(--shadow-md)",
        }}
      >
        <span
          aria-hidden
          style={{ width: 12, height: 12, borderRadius: "50%", background: "var(--accent)" }}
        />
        {current?.label ?? "Theme"}
      </button>
    </div>
  );
}
