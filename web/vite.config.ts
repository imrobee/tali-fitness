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
    // Vite refuses unknown host names; these are the Compose service names the
    // screenshot container uses. IP addresses (the iPhone) are always allowed.
    allowedHosts: ['web', 'web-demo'],
    // Forward /api and /auth to the API so the browser sees a single origin: no CORS,
    // and the session cookie belongs to the page's own host (docs/AUTH_SPEC.md 5).
    // The demo stack points this at its own API (docker-compose.yml, profile "demo").
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://api:8000',
      '/auth': process.env.API_PROXY_TARGET ?? 'http://api:8000',
    },
  },
  test: {
    // Pure functions run in Node; component tests opt into jsdom per file.
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
