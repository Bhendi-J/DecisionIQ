import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8082',
      '/finance': 'http://127.0.0.1:8082',
      '/anomaly': 'http://127.0.0.1:8082',
      '/phishing': 'http://127.0.0.1:8082',
    },
  },
});
