import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, 'BACKEND_URL')
  return {
    server: {
      proxy: { '/speech': env.BACKEND_URL || 'http://127.0.0.1:8000' },
    },
    plugins: [
      react(),
      babel({ presets: [reactCompilerPreset()] }),
    ],
  }
})
