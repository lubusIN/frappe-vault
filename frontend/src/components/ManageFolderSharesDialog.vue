<template>
  <Dialog
    :modelValue="modelValue"
    :title="dialogTitle"
    size="lg"
    @update:modelValue="val => emit('update:modelValue', val)"
  >
    <template #default>
      <div class="flex flex-col gap-3 py-1 min-h-[180px]">
        <!-- Loading State -->
        <div v-if="loading" class="flex flex-col items-center justify-center py-12 gap-3">
          <div class="w-8 h-8 border-2 border-outline-gray-2 border-t-ink-gray-7 rounded-full animate-spin" />
          <p class="text-sm text-ink-gray-5 font-medium">Loading shares…</p>
        </div>

        <!-- Active Shares -->
        <template v-else-if="activeShares.length">
          <div class="flex items-center gap-2 pl-0.5 mb-1">
            <span class="text-xs font-bold text-ink-gray-5 uppercase tracking-wider">Active Shares</span>
            <Badge variant="subtle" theme="green" size="sm" class="!rounded-full font-medium">
              {{ activeShares.length }}
            </Badge>
          </div>

          <div
            v-for="item in activeShares"
            :key="item.name"
            class="flex items-center justify-between p-3.5 bg-surface-white border border-outline-gray-1 rounded-xl shadow-2xs hover:shadow-xs transition-shadow"
          >
            <!-- Left: Icon + Info -->
            <div class="flex items-center gap-3.5 min-w-0">
              <div class="w-9 h-9 rounded-full bg-surface-gray-2 border border-outline-gray-1 shadow-2xs flex items-center justify-center shrink-0">
                <span
                  :class="['lucide-' + (item.share_type === 'Role' ? 'shield' : (item.user_count > 1 ? 'users' : 'user')), 'w-4.5 h-4.5 text-ink-gray-5']"
                  aria-hidden="true"
                />
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-ink-gray-9 truncate leading-snug">
                  {{ item.share_type === 'User' ? (item.full_name || item.user) : (item.share_type === 'Role' ? item.frappe_role : item.user) }}
                </p>
                <p class="text-xs text-ink-gray-5 mt-0.5 font-medium flex items-center gap-1.5 leading-none">
                  <span>{{ item.share_type }}</span>
                  <span class="w-1 h-1 rounded-full bg-surface-gray-4" />
                  <span>by {{ item.shared_by_name || item.shared_by }}</span>
                </p>
              </div>
            </div>

            <!-- Right: Permission + Revoke -->
            <div class="flex items-center gap-3 shrink-0">
              <Badge
                :theme="permissionTheme[item.permission_level] || 'gray'"
                variant="subtle"
                size="sm"
              >
                {{ item.permission_level }}
              </Badge>

              <Button
                v-if="canRevoke(item)"
                variant="ghost"
                icon="lucide-trash-2"
                class="!p-1.5 h-auto text-ink-gray-4 hover:!text-ink-red-3 hover:!bg-surface-red-2"
                title="Revoke Access"
                :loading="revokingShare === item.name"
                @click="handleRevoke(item)"
              />
            </div>
          </div>
        </template>

        <!-- Empty State -->
        <div v-else class="p-8 bg-surface-gray-2 border border-dashed border-outline-gray-1 rounded-2xl text-center shadow-sm">
          <div class="w-10 h-10 rounded-full bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center mx-auto text-ink-gray-4 mb-3 shrink-0">
            <span class="lucide-users w-5 h-5" aria-hidden="true" />
          </div>
          <p class="text-sm font-semibold text-ink-gray-9 leading-snug">Not Shared Yet</p>
          <p class="text-xs text-ink-gray-5 mt-1 max-w-[280px] mx-auto leading-normal font-medium">
            This folder is private. Use the Share button to give access to other users or roles.
          </p>
        </div>

        <!-- Revoked Shares -->
        <template v-if="revokedShares.length">
          <div class="flex items-center gap-2 pl-0.5 mt-4 mb-1">
            <span class="text-xs font-bold text-ink-gray-5 uppercase tracking-wider">Revoked</span>
            <Badge variant="subtle" theme="red" size="sm" class="!rounded-full font-medium">
              {{ revokedShares.length }}
            </Badge>
          </div>

          <div
            v-for="item in revokedShares"
            :key="item.name"
            class="flex items-center justify-between p-3.5 bg-surface-gray-2 border border-outline-gray-1 rounded-xl opacity-70"
          >
            <div class="flex items-center gap-3.5 min-w-0">
              <div class="w-9 h-9 rounded-full bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0">
                <span
                  :class="['lucide-' + (item.share_type === 'Role' ? 'shield' : 'user'), 'w-4.5 h-4.5 text-ink-gray-4']"
                  aria-hidden="true"
                />
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-ink-gray-7 truncate leading-snug line-through">
                  {{ item.share_type === 'User' ? (item.full_name || item.user) : item.frappe_role }}
                </p>
                <p class="text-xs text-ink-gray-4 mt-0.5 font-medium">
                  Revoked by {{ item.revoked_by || 'unknown' }}
                </p>
              </div>
            </div>
            <Badge theme="red" variant="subtle" size="sm">Revoked</Badge>
          </div>
        </template>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, Button, Badge, toast } from 'frappe-ui'
import { useFolderShares, useUnshare } from '../composables/vault'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  folderName: { type: String, default: '' },
  folderTitle: { type: String, default: '' },
  isOwnerOrAdmin: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'updated'])

const dialogTitle = computed(() => {
  return props.folderTitle ? `Manage Shares — "${props.folderTitle}"` : 'Manage Folder Shares'
})

const permissionTheme = {
  'View Only': 'gray',
  'View & Copy': 'blue',
  'Edit': 'orange',
  'Full Control': 'green',
}

const sharesResource = useFolderShares()
const unshareResource = useUnshare()
const loading = ref(false)
const revokingShare = ref(null)

const allShares = computed(() => sharesResource.data || [])
const activeShares = computed(() => allShares.value.filter(s => !s.is_revoked))
const revokedShares = computed(() => allShares.value.filter(s => s.is_revoked))

const currentUser = computed(() => window.frappe?.session?.user || window.frappe?.boot?.user?.name || '')

function canRevoke(item) {
  // The sharer can always revoke. The owner/admin can also revoke any share.
  return props.isOwnerOrAdmin || item.shared_by === currentUser.value
}

watch(() => props.modelValue, async (isOpen) => {
  if (isOpen && props.folderName) {
    loading.value = true
    try {
      await sharesResource.submit({
        secret_name: props.folderName,
        shared_doctype: 'Vault Folder',
      })
    } finally {
      loading.value = false
    }
  }
})

async function handleRevoke(item) {
  revokingShare.value = item.name
  try {
    await unshareResource.submit({ share_name: item.name })
    toast.success('Access revoked successfully')
    // Reload shares
    await sharesResource.submit({
      secret_name: props.folderName,
      shared_doctype: 'Vault Folder',
    })
    emit('updated')
  } catch (err) {
    toast.error('Failed to revoke access')
  } finally {
    revokingShare.value = null
  }
}
</script>
