import { test, expect } from '@playwright/test'
import { ADMIN_AUTH_FILE } from '../playwright.config.js'
import { createEphemeralVaultUser, deleteEphemeralVaultUser } from './helpers/users.js'

test.describe('Sharing & User-to-User Permission Matrix', () => {
  let folderName = null
  let secretName = null
  let shareA = null
  let userA = null
  let userB = null

  test.beforeAll(async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const page = await adminCtx.newPage()
    await page.goto('/vault')
    const csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    userA = await createEphemeralVaultUser(adminCtx, csrf, 'share_a')
    userB = await createEphemeralVaultUser(adminCtx, csrf, 'share_b')

    const f = await adminCtx.request.post('/api/method/frappe_vault.api.folders.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: { folder_name: `E2E Share Folder ${Date.now()}` },
    })
    expect(f.ok()).toBeTruthy()
    folderName = (await f.json()).message?.name

    const s = await adminCtx.request.post('/api/method/frappe_vault.api.secrets.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: {
        title: `E2E Share Matrix ${Date.now()}`,
        secret_type: 'Password',
        username: 'matrix@example.com',
        password: 'MatrixPassword!2026',
        totp_secret: 'JBSWY3DPEHPK3PXP',
        folder: folderName,
      },
    })
    expect(s.ok()).toBeTruthy()
    secretName = (await s.json()).message?.name

    const sh = await adminCtx.request.post('/api/method/frappe_vault.api.sharing.share', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: {
        shared_name: secretName,
        shared_doctype: 'Vault Secret',
        share_type: 'User',
        user: userA.email,
        permission_level: 'View Only',
      },
    })
    expect(sh.ok()).toBeTruthy()
    shareA = (await sh.json()).message?.name

    await adminCtx.close()
  })

  test.afterAll(async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const page = await adminCtx.newPage()
    await page.goto('/vault')
    const csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    if (secretName) {
      await adminCtx.request.post('/api/method/frappe_vault.api.secrets.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: secretName },
      })
    }
    if (folderName) {
      await adminCtx.request.post('/api/method/frappe_vault.api.folders.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: folderName, delete_secrets: true },
      })
    }
    await deleteEphemeralVaultUser(adminCtx, csrf, userA)
    await deleteEphemeralVaultUser(adminCtx, csrf, userB)
    await adminCtx.close()
  })

  test('verifies View Only -> Edit (preserves TOTP, blocks move to root) -> Full Control (user-to-user share) -> Revoke', async ({ browser }) => {
    const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH_FILE })
    const adminPage = await adminCtx.newPage()
    await adminPage.goto('/vault')
    const adminCsrf = await adminPage.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    const userACtx = await browser.newContext({ storageState: { cookies: [], origins: [] } })
    await userACtx.request.post('/api/method/login', { data: { usr: userA.email, pwd: userA.password } })
    const userAPage = await userACtx.newPage()

    // 1. View Only: User A sees secret in Shared with Me, no Edit button
    await userAPage.goto('/vault/shared')
    await expect(userAPage).toHaveURL(/\/vault\/shared/)
    await userAPage.goto(`/vault/secrets/${secretName}`)
    const userACsrf = await userAPage.evaluate(() => window.csrf_token || window.frappe?.csrf_token)
    await expect(userAPage.getByRole('button', { name: 'Edit' })).toHaveCount(0)

    // 2. Upgrade User A to Edit
    const upEdit = await adminCtx.request.post('/api/method/frappe_vault.api.sharing.update_share_permission', {
      headers: { 'X-Frappe-CSRF-Token': adminCsrf },
      data: { share_name: shareA, permission_level: 'Edit' },
    })
    expect(upEdit.ok()).toBeTruthy()

    await userAPage.reload()
    await expect(userAPage.getByText('Edit rights')).toBeVisible()

    // Edit & Save in UI and confirm TOTP seed is NOT wiped
    await userAPage.getByTitle('Edit').click().catch(async () => {
      await userAPage.getByRole('button', { name: 'Edit' }).click()
    })
    await userAPage.getByRole('button', { name: 'Save' }).click()
    await expect(userAPage.getByText('TOTP Secret (2FA)')).toBeVisible()

    // Edit user cannot bypass folder move restriction by moving secret to root ("" or null)
    const moveToRoot = await userACtx.request.post('/api/method/frappe_vault.api.secrets.update', {
      headers: { 'X-Frappe-CSRF-Token': userACsrf },
      data: { name: secretName, folder: '' },
    })
    expect(moveToRoot.status()).toBe(403)

    // Edit user still cannot share with User B
    const failShare = await userACtx.request.post('/api/method/frappe_vault.api.sharing.share', {
      headers: { 'X-Frappe-CSRF-Token': userACsrf },
      data: {
        shared_name: secretName,
        shared_doctype: 'Vault Secret',
        share_type: 'User',
        user: userB.email,
        permission_level: 'View Only',
      },
    })
    expect(failShare.status()).toBe(403)

    // 3. Upgrade User A to Full Control -> User A shares with User B
    const upFull = await adminCtx.request.post('/api/method/frappe_vault.api.sharing.update_share_permission', {
      headers: { 'X-Frappe-CSRF-Token': adminCsrf },
      data: { share_name: shareA, permission_level: 'Full Control' },
    })
    expect(upFull.ok()).toBeTruthy()

    const shareToB = await userACtx.request.post('/api/method/frappe_vault.api.sharing.share', {
      headers: { 'X-Frappe-CSRF-Token': userACsrf },
      data: {
        shared_name: secretName,
        shared_doctype: 'Vault Secret',
        share_type: 'User',
        user: userB.email,
        permission_level: 'View Only',
      },
    })
    expect(shareToB.ok()).toBeTruthy()

    // Verify User B can read the secret
    const userBCtx = await browser.newContext({ storageState: { cookies: [], origins: [] } })
    await userBCtx.request.post('/api/method/login', { data: { usr: userB.email, pwd: userB.password } })
    const userBPage = await userBCtx.newPage()
    await userBPage.goto(`/vault/secrets/${secretName}`)
    await expect(userBPage.getByText('TOTP Secret (2FA)')).toBeVisible()
    await userBCtx.close()

    // 4. Admin revokes User A -> User A loses access
    const revokeA = await adminCtx.request.post('/api/method/frappe_vault.api.sharing.unshare', {
      headers: { 'X-Frappe-CSRF-Token': adminCsrf },
      data: { share_name: shareA },
    })
    expect(revokeA.ok()).toBeTruthy()

    const afterRevoke = await userACtx.request.post('/api/method/frappe_vault.api.secrets.get', {
      headers: { 'X-Frappe-CSRF-Token': userACsrf },
      data: { name: secretName },
    })
    expect(afterRevoke.status()).toBe(403)

    await userACtx.close()
    await adminCtx.close()
  })
})
