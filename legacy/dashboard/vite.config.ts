import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so `dist/` can be served from any static sub-path.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 900,
  },
});
