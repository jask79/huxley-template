import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { viteSingleFile } from "vite-plugin-singlefile"
import tailwindcss from "@tailwindcss/vite"

 
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3456',
        changeOrigin: true,
      },
      '/config': {
        target: 'http://localhost:3456',
        changeOrigin: true,
      },
      '/restart': {
        target: 'http://localhost:3456',
        changeOrigin: true,
      },
      '/logs': {
        target: 'http://localhost:3456',
        changeOrigin: true,
      },
      '/update': {
        target: 'http://localhost:3456',
        changeOrigin: true,
      },
    },
  },
})
