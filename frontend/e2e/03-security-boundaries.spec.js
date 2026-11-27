import { test, expect } from '@playwright/test'
import { ADMIN_AUTH_FILE } from '../playwright.config.js'
import { createEphemeralVaultUser, deleteEphemeralVaultUser } from './helpers/users.js'

test.describe('API Security Boundaries (Guest Context)', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('blocks unauthenticated access to protected Vault endpoints', async ({ request }) => {
    const endpoints = [
      { method: 'get', url: '/api/method/frappe_vault.api.secrets.list' },
      { method: 'post', url: '/api/method/frappe_vault.api.demo.clear_demo_data' },
      {
        method: 'post',
        url: '/api/resource/Vault Share',
        data: { share_type: 'User', shared_doctype: 'Vault Secret', shared_name: 'VS-0001' },
      },
      {
        method: 'post',
        url: '/api/resource/Vault One Time Link',
        data: { secret: 'VS-0001', max_views: 10 },
      },
    ]

    for (const ep of endpoints) {
      const res = ep.method === 'get'
        ? await request.get(ep.url)
        : await request.post(ep.url, { data: ep.data })

      expect(res.status(), `${ep.method.toUpperCase()} ${ep.url} should be blocked`).toBeGreaterThanOrEqual(400)
    }
  })
})

test.describe('v1.2.2 Security & Permission Boundaries (Vault User)', () => {
  let adminUnsharedSecret = null
  let adminSharedSecret = null
  let testUser = null

  test.beforeAll(async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const page = await adminCtx.newPage()
    await page.goto('/vault')
    const csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    // 1. Create ephemeral test Vault User owned by this test run
    testUser = await createEphemeralVaultUser(adminCtx, csrf, 'sec')

    // 2. Create an unshared Admin secret (attacker must not read or link)
    const s1 = await adminCtx.request.post('/api/method/frappe_vault.api.secrets.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: {
        title: `E2E Admin Private ${Date.now()}`,
        secret_type: 'Password',
        password: 'AdminOnlySecret!99',
      },
    })
    expect(s1.ok()).toBeTruthy()
    adminUnsharedSecret = (await s1.json()).message?.name

    // 3. Create a shared Admin secret with TOTP (shared as View Only)
    const s2 = await adminCtx.request.post('/api/method/frappe_vault.api.secrets.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: {
        title: `E2E Shared TOTP ${Date.now()}`,
        secret_type: 'Password',
        username: 'shared@example.com',
        password: 'SharedPassword!99',
        totp_secret: 'JBSWY3DPEHPK3PXP',
      },
    })
    expect(s2.ok()).toBeTruthy()
    adminSharedSecret = (await s2.json()).message?.name

    const shareRes = await adminCtx.request.post('/api/method/frappe_vault.api.sharing.share', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: {
        shared_name: adminSharedSecret,
        shared_doctype: 'Vault Secret',
        share_type: 'User',
        user: testUser.email,
        permission_level: 'View Only',
      },
    })
    expect(shareRes.ok()).toBeTruthy()

    await adminCtx.close()
  })

  test.afterAll(async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const page = await adminCtx.newPage()
    await page.goto('/vault')
    const csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    if (adminUnsharedSecret) {
      await adminCtx.request.post('/api/method/frappe_vault.api.secrets.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: adminUnsharedSecret },
      })
    }
    if (adminSharedSecret) {
      await adminCtx.request.post('/api/method/frappe_vault.api.secrets.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: adminSharedSecret },
      })
    }
    await deleteEphemeralVaultUser(adminCtx, csrf, testUser)
    await adminCtx.close()
  })

  test('blocks REST privilege escalation, demo clear, and masks TOTP seed in UI for View Only user', async ({ browser }) => {
    const userCtx = await browser.newContext({ storageState: { cookies: [], origins: [] } })
    const loginRes = await userCtx.request.post('/api/method/login', {
      data: { usr: testUser.email, pwd: testUser.password },
    })
    expect(loginRes.ok(), 'Vault User login failed').toBeTruthy()

    const page = await userCtx.newPage()
    await page.goto(`/vault/secrets/${adminSharedSecret}`)
    const userCsrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    // --- UI Check 1: View Only hides TOTP Reveal/Copy buttons, keeps Clock button ---
    await expect(page.getByText('TOTP Secret (2FA)')).toBeVisible()
    await expect(page.getByTitle('Get TOTP Code')).toBeVisible()
    await expect(page.getByTitle('Reveal TOTP Secret (2FA)')).toHaveCount(0)
    await expect(page.getByTitle('Copy TOTP Secret (2FA)')).toHaveCount(0)

    // --- UI Check 2: Revealing Password keeps TOTP Secret (2FA) row visible ---
    await page.getByTitle('Reveal Password').click()
    await expect(page.getByText('SharedPassword!99')).toBeVisible()
    await expect(page.getByText('TOTP Secret (2FA)')).toBeVisible()

    // --- API Security Check 1: Direct POST /api/resource/Vault Share blocked ---
    const selfShare = await userCtx.request.post('/api/resource/Vault Share', {
      headers: { 'X-Frappe-CSRF-Token': userCsrf },
      data: {
        share_type: 'User',
        user: testUser.email,
        shared_doctype: 'Vault Secret',
        shared_name: adminUnsharedSecret,
        permission_level: 'Full Control',
      },
    })
    expect(selfShare.status()).toBe(403)

    // --- API Security Check 2: Direct POST /api/resource/Vault One Time Link blocked ---
    const otlHack = await userCtx.request.post('/api/resource/Vault One Time Link', {
      headers: { 'X-Frappe-CSRF-Token': userCsrf },
      data: { secret: adminUnsharedSecret, max_views: 100 },
    })
    expect(otlHack.status()).toBe(403)

    // --- API Security Check 3: clear_demo_data blocked for Vault User ---
    const demoClear = await userCtx.request.post('/api/method/frappe_vault.api.demo.clear_demo_data', {
      headers: { 'X-Frappe-CSRF-Token': userCsrf },
    })
    expect(demoClear.status()).toBe(403)

    // --- API Security Check 4: cleanup_old_logs blocked for Vault User ---
    const logCleanup = await userCtx.request.post(
      '/api/method/frappe_vault.background_jobs.log_cleanup.cleanup_old_logs',
      { headers: { 'X-Frappe-CSRF-Token': userCsrf } }
    )
    expect(logCleanup.status()).toBe(403)

    // --- API Security Check 5: Decrypt returns totp_secret: null for View Only ---
    const decryptRes = await userCtx.request.post('/api/method/frappe_vault.api.secrets.decrypt', {
      headers: { 'X-Frappe-CSRF-Token': userCsrf },
      data: { name: adminSharedSecret },
    })
    expect(decryptRes.ok()).toBeTruthy()
    const decryptBody = await decryptRes.json()
    expect(decryptBody.message?.decrypted?.totp_secret).toBeNull()

    await userCtx.close()
  })
})
