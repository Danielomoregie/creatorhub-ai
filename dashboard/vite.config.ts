import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` hot-reloads the UI and forwards /api to `creatorhub dashboard` (port 8765).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765" } },
});
