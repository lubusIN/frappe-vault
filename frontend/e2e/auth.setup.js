import { test as setup, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'
import { ADMIN_AUTH_FILE } from '../playwright.config.js'

setup('authenticate as vault admin', async ({ request }) => {
  const usr = process.env.ADMIN_USER || 'Administrator'
  const pwd = process.env.ADMIN_PASS || 'admin'

  const response = await request.post('/api/method/login', {
    data: { usr, pwd },
  })

  expect(
    response.ok(),
    `Login failed for ${usr}. Set ADMIN_USER / ADMIN_PASS env vars if using custom credentials.`
  ).toBeTruthy()

  fs.mkdirSync(path.dirname(ADMIN_AUTH_FILE), { recursive: true })
  await request.storageState({ path: ADMIN_AUTH_FILE })
})
