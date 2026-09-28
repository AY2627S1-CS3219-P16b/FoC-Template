import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: false,
    // Supplier paths are listed first: Vite matches keys in order, and both
    // services share the /api prefix.
    proxy: {
      '/api/v1/suppliers': process.env.SUPPLIER_API_PROXY_TARGET || 'http://localhost:8001',
      '/api/v1/places': process.env.SUPPLIER_API_PROXY_TARGET || 'http://localhost:8001',
      '/api/v1/supplier-changes': process.env.SUPPLIER_API_PROXY_TARGET || 'http://localhost:8001',
      '/api': process.env.USER_API_PROXY_TARGET || 'http://localhost:8000'
    }
  }
});
