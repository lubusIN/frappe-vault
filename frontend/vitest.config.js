import path from 'path'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    include: ['src/__tests__/**/*.test.js'],
    environment: 'jsdom',
    globals: true,
  },
  resolve: {
    alias: [
      { find: 'frappe-ui/experimental', replacement: path.resolve(__dirname, 'src/__tests__/__mocks__/frappe-ui.js') },
      { find: 'frappe-ui', replacement: path.resolve(__dirname, 'src/__tests__/__mocks__/frappe-ui.js') },
      { find: '@', replacement: path.resolve(__dirname, 'src') },
    ],
  },
})
