import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import type { ProxyOptions } from 'vite'

// backend: uvicorn fastapi_server.app:app --port 8000 (из project/backend)
// Префикс /api снимаем, чтобы фронтенд и backend были на одном origin (без CORS).
const proxy: Record<string, ProxyOptions> = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
})
