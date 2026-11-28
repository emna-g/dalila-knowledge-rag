import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'

// En développement (npm run dev) : l'API de Dalila tourne à côté (uvicorn frontend.serveur:app, port 8000).
// En production : `npm run build` -> dist/, servi par frontend/serveur.py à la même adresse que l'API.
const API = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { '/carte': API, '/sante': API, '/dalila': API, '/admin/api': API },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    // deux pages : la carte (/) et l'administration (/admin/)
    rollupOptions: { input: { carte: resolve(__dirname, 'index.html'), admin: resolve(__dirname, 'admin/index.html') } },
  },
})
