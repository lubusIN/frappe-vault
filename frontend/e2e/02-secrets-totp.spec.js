import { test, expect } from '@playwright/test'

test.describe('Secret Lifecycle & TOTP UI', () => {
  let createdSecretName = null
  let csrfToken = null

  test.beforeEach(async ({ page }) => {
    await page.goto('/vault')
    csrfToken = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)
    expect(csrfToken).toBeTruthy()

    const res = await page.request.post('/api/method/frappe_vault.api.secrets.create', {
      headers: {
        'X-Frappe-CSRF-Token': csrfToken,
      },
      data: {
        title: `E2E TOTP Test ${Date.now()}`,
        secret_type: 'Password',
        username: 'e2e@example.com',
        password: 'E2E#Password!2026',
        totp_secret: 'JBSWY3DPEHPK3PXP',
      },
    })
    expect(res.ok(), `Create secret failed with status ${res.status()}`).toBeTruthy()
    const body = await res.json()
    createdSecretName = body.message?.name
    expect(createdSecretName).toBeTruthy()
  })

  test.afterEach(async ({ page }) => {
    if (createdSecretName && csrfToken) {
      await page.request.post('/api/method/frappe_vault.api.secrets.delete', {
        headers: {
          'X-Frappe-CSRF-Token': csrfToken,
        },
        data: { name: createdSecretName },
      })
      createdSecretName = null
    }
  })

  test('revealing password preserves TOTP field and generates 6-digit code', async ({ page }) => {
    await page.goto(`/vault/secrets/${createdSecretName}`)

    // TOTP row should be visible
    await expect(page.getByText('TOTP Secret (2FA)')).toBeVisible()

    // Click Reveal Password button
    await page.getByTitle('Reveal Password').click()
    await expect(page.getByText('E2E#Password!2026')).toBeVisible()

    // TOTP row must remain visible after decrypting password
    await expect(page.getByText('TOTP Secret (2FA)')).toBeVisible()

    // Open TOTP code modal via clock icon
    await page.getByTitle('Get TOTP Code').click()
    await expect(page.getByText(/^\d{3}\s\d{3}$/)).toBeVisible()
  })
})
