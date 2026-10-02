import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  publicDir: "public",
  envDir: "..",
  envPrefix: ["VITE_", "QMA_"],
  server: {
    port: 5173,
    strictPort: false,
    fs: {
      allow: [".."],
    },
    proxy: {
      // Arc Gateway (port 3000) – must come BEFORE the catch-all /api rule
      "/api/balance": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
      "/api/wallet-status": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
      "/api/deposit-calldata": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
      "/api/withdraw": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
      "/qma-access": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
      // FastAPI backend (port 8000) – catch-all for all other /api/* routes
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/openapi.json": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/openapi/": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    }
  },
  preview: {
    port: 4173,
  },
});
