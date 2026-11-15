import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backend = process.env.FAKE_DECISION_DEV_BACKEND || 'http://127.0.0.1:8790'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../backend/fake_decision/web/dist',
    emptyOutDir: true,
    sourcemap: false,
    target: 'es2022',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true, ws: true },
      '/v1': { target: backend, changeOrigin: true },
      '/v1beta': { target: backend, changeOrigin: true },
      '/healthz': { target: backend, changeOrigin: true },
      '/robots.txt': { target: backend, changeOrigin: true },
    },
  },
})
