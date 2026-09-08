import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Separate app from platform/. Dev server on :5173; it calls the population API
// on :8787 cross-origin (CORS is enabled on the Express API). No proxy needed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
