import { test, expect } from '@playwright/test'

test.describe('Vault Navigation & Layout', () => {
  test('loads dashboard and core sidebar routes', async ({ page }) => {
    await page.goto('/vault')
    await expect(page).toHaveTitle(/Vault|Frappe/i)
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()

    await page.goto('/vault/secrets')
    await expect(page).toHaveURL(/\/vault\/secrets/)

    await page.goto('/vault/bookmarks')
    await expect(page).toHaveURL(/\/vault\/bookmarks/)

    await page.goto('/vault/shared')
    await expect(page).toHaveURL(/\/vault\/shared/)
  })

  test('renders responsive layout on mobile viewports', async ({ page, isMobile }) => {
    await page.goto('/vault/secrets')
    await expect(page).toHaveURL(/\/vault\/secrets/)

    if (isMobile) {
      await expect(page.locator('body')).toBeVisible()
    }
  })
})
