import { test, expect } from '@playwright/test'
import { ADMIN_AUTH_FILE } from '../playwright.config.js'
import { createEphemeralVaultUser, deleteEphemeralVaultUser } from './helpers/users.js'

test.describe('Admin vs Standard User Role Isolation', () => {
  let testUser = null

  test.beforeAll(async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const page = await adminCtx.newPage()
    await page.goto('/vault')
    const csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)
    testUser = await createEphemeralVaultUser(adminCtx, csrf, 'role_iso')
    await adminCtx.close()
  })

  test.afterAll(async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const page = await adminCtx.newPage()
    await page.goto('/vault')
    const csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)
    await deleteEphemeralVaultUser(adminCtx, csrf, testUser)
    await adminCtx.close()
  })

  test('Vault Admin can access Manage Shares and Audit Log routes', async ({ page }) => {
    await page.goto('/vault/shares')
    await expect(page).toHaveURL(/\/vault\/shares/)

    await page.goto('/vault/audit')
    await expect(page).toHaveURL(/\/vault\/audit/)
  })

  test('Standard Vault User is redirected away from admin-only routes', async ({ browser }) => {
    const userCtx = await browser.newContext({ storageState: { cookies: [], origins: [] } })
    const loginRes = await userCtx.request.post('/api/method/login', {
      data: { usr: testUser.email, pwd: testUser.password },
    })
    expect(loginRes.ok()).toBeTruthy()

    const page = await userCtx.newPage()
    await page.goto('/vault/shares')
    await expect(page).not.toHaveURL(/\/vault\/shares/)

    await page.goto('/vault/audit')
    await expect(page).not.toHaveURL(/\/vault\/audit/)

    await userCtx.close()
  })
})
