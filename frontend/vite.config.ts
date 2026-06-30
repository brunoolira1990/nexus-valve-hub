import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "0.0.0.0",
    allowedHosts: [
      'erp.nexusvalvulas.com.br',
      '192.168.5.132',
      '201.93.248.240'
    ],
    port: 5173,
    hmr: {
      overlay: false,
      host: process.env.VITE_HMR_HOST || undefined,
      clientPort: process.env.VITE_HMR_CLIENT_PORT
        ? Number(process.env.VITE_HMR_CLIENT_PORT)
        : undefined,
    },
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: false,
      },
      "/media": {
        target: proxyTarget,
        changeOrigin: false,
      },
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
}));
