import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Isolated harness for ThingDaddy_Platform_Sample.jsx.
// Port 5273 so it runs alongside the population UI (5173).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5273,
    // the sample lives one level up (platform/); let Vite serve it
    fs: { allow: [".."] },
  },
});
