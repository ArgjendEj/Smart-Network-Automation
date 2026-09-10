import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // listen on IPv4 + IPv6 (fixes localhost -> ::1 only)
    port: 5173,
    strictPort: true,
    proxy: {
      // use 127.0.0.1 (not "localhost") so Node doesn't resolve to ::1 and miss uvicorn
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
