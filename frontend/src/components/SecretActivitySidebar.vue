<template>
  <!-- Message list pane (Right side: Tabs) -->
  <section class="flex h-full min-h-0 w-full lg:w-1/2 shrink-0 flex-col lg:border-l border-outline-gray-1 bg-surface-base">
    <!-- Header and Tabs -->
    <div class="flex flex-col shrink-0 border-b border-outline-gray-1 px-6 py-4 gap-3 bg-surface-base">
      <TabButtons
        v-model="activeTabLabel"
        :options="tabsList"
      />
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="p-0">
      <div v-if="activeTabLabel === 'Activity'">
        <div class="px-6 py-5">
          <div class="w-full pt-1">
            <div class="flex items-center justify-between mb-6 pb-2.5 border-b border-outline-gray-1">
              <h2 class="text-base font-bold text-ink-gray-9">Activity</h2>
              <Button variant="ghost" icon="lucide-refresh-cw" size="sm" @click="activity.reload()" title="Refresh Activity" />
            </div>

            <div v-if="activity.loading" class="space-y-4">
              <div v-for="i in 3" :key="i" class="h-14 bg-surface-gray-2 border border-outline-gray-1 rounded-xl animate-pulse" />
            </div>

            <div v-else-if="activityList.length" class="relative space-y-6 before:absolute before:top-2 before:bottom-2 before:left-2.5 before:w-px before:bg-outline-gray-2 py-1">
              <div v-for="item in activityList" :key="item.name" class="relative flex items-start gap-3.5">
                <div class="w-5 h-5 flex items-center justify-center shrink-0 relative text-ink-gray-5 bg-surface-base mt-0.5">
                  <span :class="['lucide-' + (actionIcons[item.action] || 'activity'), 'w-4 h-4']" aria-hidden="true" />
                </div>
                <div class="min-w-0 flex-1 flex flex-col gap-1.5">
                  <div class="flex items-start justify-between w-full gap-4">
                    <div class="text-sm leading-relaxed text-ink-gray-8">
                      <span class="font-bold text-ink-gray-9">{{ item.user }}</span>
                      <span class="text-ink-gray-6 ml-1"> {{ getActionMainText(item) }}</span>
                    </div>
                    <span class="ml-auto text-xs text-ink-gray-4 shrink-0 whitespace-nowrap text-right pt-0.5">{{ formatRelativeTime(item.timestamp) }}</span>
                  </div>

                  <div v-if="hasActivityDetails(item)" class="mt-1.5 p-3 rounded-lg bg-surface-gray-2 border border-outline-gray-1 text-sm text-ink-gray-8 leading-relaxed w-full font-normal shadow-2xs">
                    {{ getActivityDetailText(item) }}
                  </div>
                </div>
              </div>
            </div>

            <EmptyState v-else icon="activity" title="No activity recorded" />
          </div>
        </div>
      </div>
      <div v-if="activeTabLabel === 'Sharing'">
        <div class="px-6 py-5">
          <div class="space-y-5 w-full">
            <div class="flex items-center justify-between border-b border-outline-gray-1 pb-3 shrink-0">
              <h3 class="text-base font-semibold text-ink-gray-9">Sharing Settings</h3>
              <Button
                v-if="isOwnerOrAdmin"
                variant="solid"
                size="sm"
                class="shadow-sm font-semibold"
                iconLeft="lucide-user-plus"
                label="Share Secret"
                @click="openShareDialog"
              />
            </div>

            <div v-if="!isOwnerOrAdmin" class="p-4 bg-surface-gray-2 border border-outline-gray-1 rounded-xl text-sm leading-relaxed text-ink-gray-7 font-medium shadow-sm flex items-start gap-3">
              <div class="w-9 h-9 rounded-full bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0 text-ink-gray-7">
                <span class="lucide-share-2 w-4.5 h-4.5" aria-hidden="true" />
              </div>
              <div>
                <p class="font-bold text-ink-gray-9 leading-normal">Shared Secret Access</p>
                <p class="mt-1 text-ink-gray-6 font-normal">
                  This secret was shared with you by <strong class="text-ink-gray-8">{{ secretData.shared_by || secretData.owner }}</strong>. You have <strong class="text-ink-gray-8">{{ secretData.permission_level || secretData.user_permission || 'View Only' }}</strong> rights on this secret.
                </p>
              </div>
            </div>

            <div v-else class="space-y-4">
              <div class="text-xs font-bold text-ink-gray-5 uppercase tracking-wider pl-0.5">Active Shares</div>
              <div v-if="activeSharesList.length" class="space-y-3">
                <div
                  v-for="item in activeSharesList"
                  :key="item.name"
                  class="flex items-center justify-between p-3.5 bg-surface-elevation-1 border border-outline-gray-1 rounded-xl shadow-sm hover:border-outline-gray-3 transition-colors"
                >
                  <div class="flex items-center gap-3.5 min-w-0">
                    <div class="w-9 h-9 rounded-full bg-surface-gray-2 border border-outline-gray-1 shadow-2xs flex items-center justify-center shrink-0">
                      <span
                        :class="['lucide-' + (item.share_type === 'UserGroup' || item.user_count > 1 ? 'users' : (item.share_type === 'Role' ? 'shield' : 'user')), 'w-4.5 h-4.5 text-ink-gray-5']"
                        aria-hidden="true"
                      />
                    </div>
                    <div class="min-w-0">
                      <div class="flex items-center gap-1.5 min-w-0">
                        <p class="text-sm font-semibold text-ink-gray-9 truncate leading-snug">
                          {{ item.share_type === 'User' ? item.user : (item.share_type === 'UserGroup' ? item.user : item.frappe_role) }}
                        </p>
                        <Button
                          v-if="item.share_type === 'Role'"
                          variant="ghost"
                          size="sm"
                          class="!h-6 !px-1.5 text-xs text-ink-blue-link hover:underline shrink-0"
                          title="View role members"
                          @click="openRoleUsersModal(item.frappe_role, item)"
                        >
                          View Members
                        </Button>
                        <Button
                          v-else-if="item.share_type === 'UserGroup' || item.user_count > 1"
                          variant="ghost"
                          size="sm"
                          class="!h-6 !px-1.5 text-xs text-ink-blue-link hover:underline shrink-0"
                          title="View shared users"
                          @click="openUserGroupModal(item)"
                        >
                          View Members
                        </Button>
                      </div>
                      <p class="text-xs text-ink-gray-4 mt-1 font-medium flex items-center gap-1.5 leading-none">
                        <span>{{ item.share_type }}</span>
                        <span class="w-1 h-1 rounded-full bg-surface-gray-4" />
                        <span v-if="item.expires_on">Expires {{ formatTime(item.expires_on) }}</span>
                        <span v-else>Never expires</span>
                      </p>
                    </div>
                  </div>

                  <div class="flex items-center gap-3 shrink-0">
                    <Dropdown
                      v-if="canEditShare(item) && item.share_type === 'User' && !(item.user_count > 1)"
                      :options="[
                        { label: 'View Only', onClick: () => handleUpdateSharePermission(item.name, 'View Only') },
                        { label: 'View & Copy', onClick: () => handleUpdateSharePermission(item.name, 'View & Copy') },
                        { label: 'Edit', onClick: () => handleUpdateSharePermission(item.name, 'Edit') },
                        { label: 'Full Control', onClick: () => handleUpdateSharePermission(item.name, 'Full Control') }
                      ]"
                    >
                      <Badge
                        :theme="permissionTheme[item.permission_level] || 'gray'"
                        variant="subtle"
                        size="sm"
                        class="cursor-pointer hover:opacity-80 transition-opacity"
                        title="Click to update permission level"
                      >
                        {{ item.permission_level }} ▾
                      </Badge>
                    </Dropdown>
                    <Badge
                      v-else-if="item.share_type === 'UserGroup' || item.user_count > 1 || item.share_type === 'Role'"
                      theme="blue"
                      variant="subtle"
                      size="sm"
                      class="cursor-pointer hover:opacity-80 transition-opacity"
                      title="Manage individual member permissions"
                      @click="item.share_type === 'Role' ? openRoleUsersModal(item.frappe_role, item) : openUserGroupModal(item)"
                    >
                      Manage Access ›
                    </Badge>
                    <Badge
                      v-else
                      :theme="permissionTheme[item.permission_level] || 'gray'"
                      variant="subtle"
                      size="sm"
                    >
                      {{ item.permission_level }}
                    </Badge>

                    <Button
                      v-if="canEditShare(item)"
                      variant="ghost"
                      icon="lucide-trash-2"
                      class="!p-1.5 h-auto text-ink-gray-4 hover:!text-ink-red-3 hover:!bg-surface-red-2"
                      title="Revoke Access"
                      @click="confirmRevokeShare(item)"
                    />
                  </div>
                </div>
              </div>

              <div v-else class="p-8 bg-surface-gray-2 border border-dashed border-outline-gray-1 rounded-2xl text-center shadow-sm">
                <div class="w-10 h-10 rounded-full bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center mx-auto text-ink-gray-4 mb-3 shrink-0">
                  <span class="lucide-users w-5 h-5" aria-hidden="true" />
                </div>
                <p class="text-sm font-semibold text-ink-gray-9 leading-snug">Not Shared Yet</p>
                <p class="text-xs text-ink-gray-5 mt-1 max-w-[280px] mx-auto leading-normal font-medium">
                  This secret is private. Use the Share button to give access to other users or roles.
                </p>
              </div>

              <div v-if="revokedSharesList.length" class="mt-6 space-y-3">
                <div class="flex items-center gap-2 pl-0.5">
                  <span class="text-xs font-bold text-ink-gray-5 uppercase tracking-wider">Revoked Shares</span>
                  <Badge variant="subtle" theme="red" size="sm" class="!rounded-full font-medium">
                    {{ revokedSharesList.length }}
                  </Badge>
                </div>

                <div
                  v-for="item in revokedSharesList"
                  :key="item.name"
                  class="flex items-center justify-between p-3.5 bg-surface-gray-2 border border-outline-gray-1 rounded-xl opacity-80 hover:opacity-100 transition-opacity"
                >
                  <div class="flex items-center gap-3.5 min-w-0">
                    <div class="w-9 h-9 rounded-full bg-surface-gray-3 border border-outline-gray-1 shadow-2xs flex items-center justify-center shrink-0">
                      <span
                        :class="['lucide-' + (item.share_type === 'UserGroup' || item.user_count > 1 ? 'users' : (item.share_type === 'Role' ? 'shield' : 'user')), 'w-4.5 h-4.5 text-ink-gray-4']"
                        aria-hidden="true"
                      />
                    </div>
                    <div class="min-w-0">
                      <div class="flex items-center gap-1.5 min-w-0">
                        <p class="text-sm font-semibold text-ink-gray-7 truncate leading-snug line-through">
                          {{ item.share_type === 'User' ? item.user : (item.share_type === 'UserGroup' ? item.user : item.frappe_role) }}
                        </p>
                        <Button
                          v-if="item.share_type === 'Role'"
                          variant="ghost"
                          size="sm"
                          class="!h-6 !px-1.5 text-xs text-ink-blue-link hover:underline shrink-0"
                          title="View role members"
                          @click="openRoleUsersModal(item.frappe_role, item)"
                        >
                          View Members
                        </Button>
                        <Button
                          v-else-if="item.share_type === 'UserGroup' || item.user_count > 1"
                          variant="ghost"
                          size="sm"
                          class="!h-6 !px-1.5 text-xs text-ink-blue-link hover:underline shrink-0"
                          title="View shared users"
                          @click="openUserGroupModal(item)"
                        >
                          View Members
                        </Button>
                      </div>
                      <p class="text-xs text-ink-gray-4 mt-1 font-medium flex items-center gap-1.5 leading-none">
                        <span>{{ item.share_type }}</span>
                        <span class="w-1 h-1 rounded-full bg-surface-gray-4" />
                        <span>Revoked</span>
                      </p>
                    </div>
                  </div>

                  <div class="flex items-center gap-3 shrink-0">
                    <Badge theme="red" variant="subtle" size="sm">
                      Revoked
                    </Badge>
                    <Button
                      v-if="canEditShare(item)"
                      variant="ghost"
                      icon="lucide-trash-2"
                      class="!p-1.5 h-auto text-ink-gray-4 hover:!text-ink-red-3 hover:!bg-surface-red-2"
                      title="Delete Share Record Permanently"
                      @click="handleDeleteShareLogEntry(item)"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ScrollArea>

            <ShareItemDialog
      v-model="showShareDialog"
      :sharedName="props.name"
      sharedDoctype="Vault Secret"
      :itemTitle="secretData?.title || props.name"
      @shared="refreshSharingState"
    />

    <RevokeShareDialog
      v-model="showRevokeConfirm"
      :share="shareToRevoke"
      @revoked="refreshSharingState"
    />

    <PeopleWithAccessModal
      v-model="showRoleUsersModal"
      :roleName="selectedRoleName"
      :sharedName="props.name"
      sharedDoctype="Vault Secret"
      :item="selectedRoleItem"
      :isOwnerOrAdmin="selectedRoleItem ? canEditShare(selectedRoleItem) : isOwnerOrAdmin"
      @saved="refreshSharingState"
    />
  </section>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  Button,
  Badge,
  Dropdown,
  TabButtons,
  ScrollArea,
  toast,
} from 'frappe-ui'

import EmptyState from '../components/EmptyState.vue'
import ShareItemDialog from '../components/ShareItemDialog.vue'
import RevokeShareDialog from '../components/RevokeShareDialog.vue'
import PeopleWithAccessModal from '../components/PeopleWithAccessModal.vue'

import { actionIcons, permissionTheme, formatRelativeTime, formatTime } from '../composables/constants'
import { getActionMainText, hasActivityDetails, getActivityDetailText } from '../utils/activity'
import {
  useSecretActivity,
  useSecretShares,
  useVaultStats,
  useUpdateSharePermission,
  useBulkDeleteShares
} from '../composables/vault'

const props = defineProps({
  name: { type: String, required: true },
  secretData: { type: Object, default: () => ({}) },
})

const activeTabLabel = ref('Sharing')

const activity = useSecretActivity(props.name)
const sharesResource = useSecretShares(props.name)
const bulkDeleteSharesResource = useBulkDeleteShares()
const updateSharePermResource = useUpdateSharePermission()
const stats = useVaultStats()

const activityList = computed(() => activity.data || [])
const sharesList = computed(() => sharesResource.data || [])
const activeSharesList = computed(() => sharesList.value.filter(s => !s.is_revoked))
const revokedSharesList = computed(() => sharesList.value.filter(s => s.is_revoked))

const tabsList = computed(() => [
  { label: 'Sharing', value: 'Sharing' },
  { label: 'Activity', value: 'Activity' },
])

onMounted(() => {
  if (props.name) {
    activity.submit({ secret_name: props.name })
    sharesResource.fetch({ secret_name: props.name })
  }
  window.addEventListener('vault-secret-updated', handleVaultSecretUpdated)
})

watch(() => props.name, (n) => {
  if (n) {
    activity.submit({ secret_name: n })
    sharesResource.fetch({ secret_name: n })
  }
})

onUnmounted(() => {
  window.removeEventListener('vault-secret-updated', handleVaultSecretUpdated)
})

// Current User & Permissions
const currentSessionUser = computed(() => {
  if (window.frappe?.boot?.user) {
    if (typeof window.frappe.boot.user === 'object') {
      return window.frappe.boot.user.name || 'Guest'
    }
    return window.frappe.boot.user
  }
  if (window.frappe?.session?.user) return window.frappe.session.user
  if (window.frappe?.user?.name) return window.frappe.user.name
  return 'Guest'
})

const isOwnerOrAdmin = computed(() => {
  if (stats.data?.is_admin) return true
  if (currentSessionUser.value === 'Administrator') return true
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  if (roles.includes('Vault Admin')) return true
  return props.secretData.owner === currentSessionUser.value || props.secretData.user_permission === 'Full Control'
})

function canEditShare(item) {
  // Users cannot edit or revoke their own direct share unless they are system admins
  if (item && item.share_type === 'User' && item.user === currentSessionUser.value) {
    if (stats.data?.is_admin || currentSessionUser.value === 'Administrator') return true
    return false
  }

  if (stats.data?.is_admin) return true
  if (currentSessionUser.value === 'Administrator') return true
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  if (roles.includes('Vault Admin') || roles.includes('System Manager')) return true
  if (props.secretData.owner === currentSessionUser.value) return true
  if (props.secretData.user_permission === 'Full Control') return true
  if (item && item.shared_by === currentSessionUser.value) return true
  return false
}



// Sharing Modals
const showShareDialog = ref(false)
const showRevokeConfirm = ref(false)
const shareToRevoke = ref(null)

const showRoleUsersModal = ref(false)
const selectedRoleName = ref('')
const selectedRoleItem = ref(null)

function openShareDialog() {
  showShareDialog.value = true
}

function confirmRevokeShare(item) {
  shareToRevoke.value = item
  showRevokeConfirm.value = true
}

function openRoleUsersModal(roleName, item) {
  if (!roleName) return
  selectedRoleName.value = roleName
  selectedRoleItem.value = item || null
  showRoleUsersModal.value = true
}

function openUserGroupModal(item) {
  selectedRoleName.value = ''
  selectedRoleItem.value = item || null
  showRoleUsersModal.value = true
}

function handleVaultSecretUpdated(event) {
  const updatedName = event?.detail?.name
  if (!updatedName || updatedName === props.name) {
    activity.reload()
  }
}

async function refreshSharingState() {
  await sharesResource.fetch({ secret_name: props.name })
  activity.reload()
}

async function handleUpdateSharePermission(shareName, permissionLevel) {
  try {
    await updateSharePermResource.submit({
      share_name: shareName,
      permission_level: permissionLevel,
    })
    toast.success(`Permission updated to ${permissionLevel}`)
    await refreshSharingState()
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to update permission')
  }
}

async function handleDeleteShareLogEntry(shareItem) {
  if (!shareItem) return
  try {
    await bulkDeleteSharesResource.submit({ share_names: [shareItem.name] })
    toast.success('Share log entry permanently deleted')
    await refreshSharingState()
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to delete share log entry')
  }
}
</script>
