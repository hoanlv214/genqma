/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          0: "var(--bg-0, #06080f)",
          1: "var(--bg-1, #0a0d18)",
          2: "var(--bg-2, #0f1220)",
          3: "var(--bg-3, rgba(15, 18, 32, 0.7))",
        },
        surface: {
          1: "var(--surface-1, rgba(255, 255, 255, 0.02))",
          2: "var(--surface-2, rgba(255, 255, 255, 0.035))",
          3: "var(--surface-3, rgba(255, 255, 255, 0.055))",
          glass: "var(--surface-glass, rgba(13, 16, 28, 0.72))",
        },
        bdr: {
          DEFAULT: "var(--bdr, rgba(255, 255, 255, 0.06))",
          md: "var(--bdr-md, rgba(255, 255, 255, 0.10))",
          hi: "var(--bdr-hi, rgba(124, 111, 255, 0.35))",
        },
        accent: {
          DEFAULT: "var(--accent, #7C6FFF)",
          hover: "var(--accent-hover, #8f84ff)",
          strong: "var(--accent-strong, #6a5ce8)",
          dim: "var(--accent-dim, rgba(124, 111, 255, 0.12))",
          glow: "var(--accent-glow, rgba(124, 111, 255, 0.25))",
        },
        qmaGreen: {
          DEFAULT: "var(--green, #22d3a0)",
          dim: "var(--green-dim, rgba(34, 211, 160, 0.12))",
        },
        qmaRed: {
          DEFAULT: "var(--red, #f4475b)",
          dim: "var(--red-dim, rgba(244, 71, 91, 0.12))",
        },
        qmaAmber: {
          DEFAULT: "var(--amber, #f59e0b)",
          dim: "var(--amber-dim, rgba(245, 158, 11, 0.10))",
        },
        qmaPurple: {
          DEFAULT: "var(--purple, #a78bfa)",
          dim: "var(--purple-dim, rgba(167, 139, 250, 0.12))",
        },
        t1: "var(--t1, #e8eaf0)",
        t2: "var(--t2, #8d95b0)",
        t3: "var(--t3, #4a5270)",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
        serif: ["Newsreader", "Georgia", "serif"],
        display: ["Newsreader", "Georgia", "serif"],
      },
      borderRadius: {
        xs: "4px",
        sm: "6px",
        md: "10px",
        lg: "16px",
        xl: "22px",
        "2xl": "28px",
      },
      boxShadow: {
        glow: "0 0 24px rgba(124, 111, 255, 0.28)",
        "glow-green": "0 0 24px rgba(34, 211, 160, 0.25)",
        card: "0 14px 40px -10px rgba(0, 0, 0, 0.45)",
      },
      backgroundImage: {
        "brand-gradient": "var(--brand-gradient, linear-gradient(92deg, #7c5cff 0%, #a78bfa 45%, #38e8c6 100%))",
      },
    },
  },
  plugins: [],
};
