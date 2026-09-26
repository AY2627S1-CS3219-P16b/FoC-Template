import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: true,
    // Supplier paths are listed first: Vite matches keys in order, and both
    // services share the /api prefix.
    proxy: {
      '/api/v1/suppliers': 'http://localhost:8001',
      '/api/v1/places': 'http://localhost:8001',
      '/api/v1/supplier-changes': 'http://localhost:8001',
      '/api': 'http://localhost:8000'
    }
  }
});
