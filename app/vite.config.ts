import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api/... is sent to the FastAPI backend (make api), so no CORS problem in dev
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
