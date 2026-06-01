import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env from project root (one level up) so frontend picks up root .env
  const rootEnv = loadEnv(mode, resolve(__dirname, '..'))
  // Merge into process.env so import.meta.env and process.env access these
  process.env = { ...process.env, ...rootEnv }

  return {
    plugins: [vue()],
  }
})
