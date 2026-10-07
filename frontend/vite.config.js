import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During development, requests to /api go to the FastAPI server on port 8000,
// so the browser sees one origin and we avoid CORS problems.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
