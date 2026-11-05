import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    frappeui({
      frontendRoute: '/vault',
      frappeProxy: true,
      lucideIcons: true,
      jinjaBootData: true,
      buildConfig: {
        outDir: '../frappe_vault/public/frontend',
        baseUrl: '/assets/frappe_vault/frontend/',
        indexHtmlPath: '../frappe_vault/www/vault.html',
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    target: 'es2015',
    rollupOptions: {
      output: {
        manualChunks: {
          'frappe-ui': ['frappe-ui'],
        },
      },
    },
  },
  optimizeDeps: {
    include: [
      'highlight.js',
      'highlight.js/lib/core',
      'interactjs',
      'debug'
    ],
  },
})
