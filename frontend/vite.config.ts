import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// HELIOS COMMAND dev server. The backend API base URL is provided via
// VITE_API_BASE_URL (defaults to the local backend). No secrets live here.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
  },
});
