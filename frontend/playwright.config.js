import { defineConfig, devices } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const ADMIN_AUTH_FILE = path.join(__dirname, 'e2e/.auth/admin.json')

const rawBaseUrl = process.env.BASE_URL || 'http://localhost:8000'
const siteOrigin = rawBaseUrl.replace(/\/vault\/?$/, '').replace(/\/$/, '')

export default defineConfig({
  testDir: './e2e',
  timeout: 30 * 1000,
  expect: {
    timeout: 8000,
  },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { open: 'never' }], ['list']],
  use: {
    baseURL: siteOrigin,
    ignoreHTTPSErrors: true,
    actionTimeout: 10000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: {
      slowMo: Number(process.env.SLOW_MO || 0),
    },
  },
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.js/,
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: ADMIN_AUTH_FILE,
      },
      dependencies: ['setup'],
    },
    {
      name: 'Mobile Chrome',
      use: {
        ...devices['Pixel 5'],
        storageState: ADMIN_AUTH_FILE,
      },
      dependencies: ['setup'],
    },
  ],
})
