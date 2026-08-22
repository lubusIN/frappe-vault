/**
 * Composables for Frappe Vault data fetching.
 */
import { createResource } from 'frappe-ui'
import { ref } from 'vue'

export const mobileSidebarOpened = ref(false)
export const isSidebarCollapsed = ref(localStorage.getItem('isSidebarCollapsed') === 'true')

// --- Secrets ---
export function useSecrets(initialFilters = {}) {
  return createResource({
    url: 'frappe_vault.api.secrets.list',
    params: initialFilters,
    auto: false,
  })
}

export function useSecret(name) {
  return createResource({
    url: 'frappe_vault.api.secrets.get',
    params: { name },
    auto: !!name,
  })
}

export function useDecryptSecret() {
  return createResource({
    url: 'frappe_vault.api.secrets.decrypt',
    makeParams: ({ name }) => ({ name }),
  })
}

export function useGetTotp() {
  return createResource({
    url: 'frappe_vault.api.secrets.get_totp',
    makeParams: ({ name }) => ({ name }),
  })
}

export function useCreateSecret() {
  return createResource({
    url: 'frappe_vault.api.secrets.create',
  })
}

export function useUpdateSecret() {
  return createResource({
    url: 'frappe_vault.api.secrets.update',
  })
}

export function useDeleteSecret() {
  return createResource({
    url: 'frappe_vault.api.secrets.delete',
  })
}

export function useRotateNow() {
  return createResource({
    url: 'frappe_vault.api.secrets.rotate_now',
  })
}

export function useClearZipPassphrase() {
  return createResource({
    url: 'frappe_vault.api.secrets.clear_zip_passphrase',
  })
}

export function useBulkDeleteSecrets() {
  return createResource({
    url: 'frappe_vault.api.secrets.bulk_delete',
  })
}

export function useToggleBookmark() {
  return createResource({
    url: 'frappe_vault.api.secrets.toggle_bookmark',
  })
}

export function useVaultStats() {
  return createResource({
    url: 'frappe_vault.api.secrets.stats',
    auto: true,
    cache: 'vault-stats',
  })
}

// --- Folders ---
export function useFolders() {
  return createResource({
    url: 'frappe_vault.api.folders.get_all',
    auto: true,
    cache: 'vault-folders',
  })
}

export function useFolderSecrets() {
  return createResource({
    url: 'frappe_vault.api.folders.get_folder_secrets',
    makeParams: ({ folder_name }) => ({ folder_name, limit: 1 }),
  })
}

export function useCreateFolder() {
  return createResource({
    url: 'frappe_vault.api.folders.create',
  })
}

export function useDeleteFolder() {
  return createResource({
    url: 'frappe_vault.api.folders.delete',
  })
}

export function useUpdateFolder() {
  return createResource({
    url: 'frappe_vault.api.folders.update',
  })
}

// --- Sharing ---
export function useShareSecret() {
  return createResource({
    url: 'frappe_vault.api.sharing.share',
  })
}

export function useUnshare() {
  return createResource({
    url: 'frappe_vault.api.sharing.unshare',
  })
}

export function useSharedWithMe() {
  return createResource({
    url: 'frappe_vault.api.sharing.shared_with_me',
    auto: true,
    cache: 'vault-shared',
  })
}

export function useShareOptions() {
  return createResource({
    url: 'frappe_vault.api.sharing.get_share_options',
    auto: true,
    cache: 'vault-share-options',
  })
}

export function useSecretShares(secretName) {
  return createResource({
    url: 'frappe_vault.api.sharing.get_shares',
    params: { secret_name: secretName },
    auto: !!secretName,
  })
}

export function useFolderShares() {
  return createResource({
    url: 'frappe_vault.api.sharing.get_shares',
  })
}

export function useBulkDeleteShares() {
  return createResource({
    url: 'frappe_vault.api.sharing.bulk_delete_shares',
  })
}

export function useUpdateSharePermission() {
  return createResource({
    url: 'frappe_vault.api.sharing.update_share_permission',
  })
}

export function useRoleUsers() {
  return createResource({
    url: 'frappe_vault.api.sharing.get_role_users',
  })
}

export function useSaveRoleMemberPermission() {
  return createResource({
    url: 'frappe_vault.api.sharing.save_role_member_permission',
  })
}

export function useCreateOneTimeLink() {
  return createResource({
    url: 'frappe_vault.api.sharing.create_one_time_link',
  })
}

export function useConsumeOneTimeLink() {
  return createResource({
    url: 'frappe_vault.api.sharing.consume_link',
  })
}



export function useCheckStrength() {
  return createResource({
    url: 'frappe_vault.api.generator.check_strength',
  })
}

export function useCheckBreach() {
  return createResource({
    url: 'frappe_vault.api.generator.check_breach',
  })
}

// --- Security ---
export function useSecurityScore() {
  return createResource({
    url: 'frappe_vault.services.security_service.calculate_security_score',
    auto: true,
    cache: 'vault-security-score',
  })
}

// --- Audit ---
export function useAuditLogs(initialParams = {}) {
  return createResource({
    url: 'frappe_vault.api.audit.get_logs',
    params: initialParams,
    auto: true,
  })
}

export function useSecretActivity(secretName) {
  return createResource({
    url: 'frappe_vault.api.audit.get_secret_activity',
    params: { secret_name: secretName },
    auto: !!secretName,
  })
}

// --- Demo Data ---
export function useGenerateDemoData() {
  return createResource({
    url: 'frappe_vault.api.demo.generate_demo_data',
  })
}

export function useClearDemoData() {
  return createResource({
    url: 'frappe_vault.api.demo.clear_demo_data',
  })
}

// --- Field Metadata ---
export function useFilterableFields(doctype = 'Vault Secret') {
  return createResource({
    url: 'frappe_vault.api.fields.get_filterable_fields',
    params: { doctype },
    auto: true,
    cache: ['vault-filterable-fields', doctype],
  })
}

export function useSortOptions(doctype = 'Vault Secret') {
  return createResource({
    url: 'frappe_vault.api.fields.get_sort_options',
    params: { doctype },
    auto: true,
    cache: ['vault-sort-options', doctype],
  })
}

// --- Notifications ---
export function useNotifications(limit = 20) {
  return createResource({
    url: 'frappe_vault.api.notifications.get_notifications',
    params: { limit },
    auto: true,
  })
}

export function useMarkNotificationRead() {
  return createResource({
    url: 'frappe_vault.api.notifications.mark_read',
  })
}

export function useMarkAllNotificationsRead() {
  return createResource({
    url: 'frappe_vault.api.notifications.mark_all_read',
  })
}

// --- Dashboard ---
export function useVaultDashboard() {
  return createResource({
    url: 'frappe_vault.api.dashboard.get_vault_dashboard',
    auto: false,
  })
}
