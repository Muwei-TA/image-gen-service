import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8088',
      '/health': 'http://127.0.0.1:8088',
      '/auth': 'http://127.0.0.1:8088',
      '/batches': 'http://127.0.0.1:8088',
      '/jobs': 'http://127.0.0.1:8088',
      '/uploads': 'http://127.0.0.1:8088',
      '/files': 'http://127.0.0.1:8088',
    },
  },
})
