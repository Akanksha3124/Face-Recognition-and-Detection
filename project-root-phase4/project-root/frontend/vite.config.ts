import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Phase 1: skeleton config only. Proxy to the backend is added
// once real API calls exist (Phase 5).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
