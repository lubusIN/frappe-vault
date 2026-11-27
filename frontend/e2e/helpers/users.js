import { expect } from '@playwright/test'

/**
 * Create a run-owned ephemeral Vault User so tests never mutate pre-existing accounts.
 * Returns { email, password, created: true }.
 */
export async function createEphemeralVaultUser(ctx, csrf, prefix = 'user') {
  const email = `e2e_${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}@example.com`
  const password = `E2E@${prefix}_2026!`

  const res = await ctx.request.post('/api/resource/User', {
    headers: { 'X-Frappe-CSRF-Token': csrf },
    data: {
      email,
      first_name: `E2E ${prefix}`,
      enabled: 1,
      user_type: 'System User',
      new_password: password,
      send_welcome_email: 0,
      roles: [{ role: 'Vault User' }],
    },
  })
  const body = await res.text()
  expect(res.ok(), `Failed to create ephemeral test user (${res.status()}): ${body}`).toBeTruthy()
  return { email, password, created: true }
}

/**
 * Clean up an ephemeral test user created during the test run.
 */
export async function deleteEphemeralVaultUser(ctx, csrf, userInfo) {
  if (!userInfo?.created || !userInfo?.email) return
  await ctx.request.delete(`/api/resource/User/${encodeURIComponent(userInfo.email)}`, {
    headers: { 'X-Frappe-CSRF-Token': csrf },
  })
}
