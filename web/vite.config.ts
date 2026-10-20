import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // The dev server runs in Docker: listen on all interfaces so the Mac and
    // the iPhone (via the Mac's LAN IP) can reach it.
    host: true,
    port: 5173,
    // Forward /api to the api service so the browser sees a single origin
    // (no CORS setup needed). "api" is the Compose service name.
    proxy: { '/api': 'http://api:8000' },
  },
  test: {
    // Slice 1 only tests pure functions; jsdom arrives with component tests.
    environment: 'node',
  },
})
