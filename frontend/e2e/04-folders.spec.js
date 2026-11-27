import { test, expect } from '@playwright/test'

test.describe('Folders & Nested Folder Hierarchy', () => {
  let rootFolder = null
  let subFolder = null
  let nestedSecret = null
  let csrf = null

  test.afterEach(async ({ page }) => {
    if (!csrf) return
    if (nestedSecret) {
      await page.request.post('/api/method/frappe_vault.api.secrets.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: nestedSecret },
      })
      nestedSecret = null
    }
    if (subFolder) {
      await page.request.post('/api/method/frappe_vault.api.folders.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: subFolder, delete_secrets: true },
      })
      subFolder = null
    }
    if (rootFolder) {
      await page.request.post('/api/method/frappe_vault.api.folders.delete', {
        headers: { 'X-Frappe-CSRF-Token': csrf },
        data: { name: rootFolder, delete_secrets: true },
      })
      rootFolder = null
    }
  })

  test('creates nested folders, places secret inside, and renders in sidebar & secrets view', async ({ page }) => {
    await page.goto('/vault/secrets')
    csrf = await page.evaluate(() => window.csrf_token || window.frappe?.csrf_token)

    const stamp = Date.now()
    const rootName = `E2E Root ${stamp}`
    const subName = `E2E Sub ${stamp}`
    const secretTitle = `E2E Nested Secret ${stamp}`

    // 1. Create root folder
    const r1 = await page.request.post('/api/method/frappe_vault.api.folders.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: { folder_name: rootName, is_group: 1 },
    })
    expect(r1.ok()).toBeTruthy()
    rootFolder = (await r1.json()).message?.name

    // 2. Create nested subfolder inside root
    const r2 = await page.request.post('/api/method/frappe_vault.api.folders.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: { folder_name: subName, parent_vault_folder: rootFolder },
    })
    expect(r2.ok()).toBeTruthy()
    subFolder = (await r2.json()).message?.name

    // 3. Create secret inside subfolder
    const s1 = await page.request.post('/api/method/frappe_vault.api.secrets.create', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: { title: secretTitle, secret_type: 'Password', password: 'NestedPass!2026', folder: subFolder },
    })
    expect(s1.ok()).toBeTruthy()
    nestedSecret = (await s1.json()).message?.name

    // 4. Reload /vault/secrets and verify root folder & secret appear in UI
    await page.reload()
    await expect(page.getByText(rootName).first()).toBeVisible()
    await expect(page.getByText(secretTitle).first()).toBeVisible()

    // 5. Reparent subfolder to root level (null parent)
    const reparent = await page.request.post('/api/method/frappe_vault.api.folders.update', {
      headers: { 'X-Frappe-CSRF-Token': csrf },
      data: { name: subFolder, parent_vault_folder: '' },
    })
    expect(reparent.ok()).toBeTruthy()

    await page.reload()
    await expect(page.getByText(subName).first()).toBeVisible()
  })
})
