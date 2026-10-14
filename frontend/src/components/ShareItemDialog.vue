<template>
  <Dialog
    :modelValue="modelValue"
    :options="{
      title: dialogTitle,
      size: 'lg',
    }"
    @update:modelValue="val => emit('update:modelValue', val)"
  >
    <template #body-content>
      <div class="flex flex-col gap-4 py-1">
        <!-- Target Type Selection: TabButtons -->
        <div class="space-y-1.5">
          <label class="block text-p-sm-medium text-ink-gray-7">Share With</label>
          <TabButtons
            v-model="newShareType"
            :options="[
              { label: 'User(s)', value: 'User', class: 'flex-1 !justify-center', onClick: () => { selectedUserEmails = [] } },
              { label: 'Role(s)', value: 'Role', class: 'flex-1 !justify-center', onClick: () => { selectedRoles = [] } }
            ]"
            class="w-full !flex"
          />
        </div>

        <!-- User Selection: MultiSelect Component -->
        <div v-if="newShareType === 'User'" class="space-y-1.5">
          <label class="block text-p-sm-medium text-ink-gray-7">Select Users</label>
          <MultiSelect
            v-model="selectedUserEmails"
            :options="userMembers"
            placeholder="Select users to share with…"
            class="w-full"
          >
            <template #prefix>
              <div v-if="visibleSelectedUsers.length" class="flex -space-x-1.5 overflow-hidden">
                <Avatar
                  v-for="u in visibleSelectedUsers"
                  :key="u.value"
                  :image="u.image"
                  :label="u.label"
                  size="sm"
                  class="ring-2 ring-surface-base"
                />
                <span
                  v-if="overflowUserCount > 0"
                  class="z-10 grid size-6 place-items-center rounded-full bg-surface-gray-3 text-p-xs-medium text-ink-gray-7 ring-2 ring-surface-base"
                >
                  +{{ overflowUserCount }}
                </span>
              </div>
              <FeatherIcon v-else name="users" class="w-4 h-4 text-ink-gray-5" />
            </template>

            <template #summary="{ selectedOptions, summary }">
              <template v-if="selectedOptions.length">
                {{ selectedOptions.map((o) => o.label).join(', ') }}
              </template>
              <template v-else>{{ summary }}</template>
            </template>

            <template #item-prefix="{ item }">
              <Avatar :image="item.image" :label="item.label" size="sm" />
            </template>

            <template #item-label="{ item }">
              <div class="min-w-0 flex items-center justify-between w-full">
                <div class="truncate font-medium text-ink-gray-9 text-xs">{{ item.label }}</div>
                <div class="truncate text-[11px] text-ink-gray-5 font-mono ml-2">{{ item.value }}</div>
              </div>
            </template>
          </MultiSelect>
        </div>

        <!-- Role Selection: MultiSelect Component -->
        <div v-else class="space-y-1.5">
          <label class="block text-p-sm-medium text-ink-gray-7">Select Roles</label>
          <MultiSelect
            v-model="selectedRoles"
            :options="roleMembers"
            placeholder="Select roles to share with…"
            class="w-full"
          >
            <template #prefix>
              <div v-if="visibleSelectedRoles.length" class="flex -space-x-1.5">
                <span
                  v-for="r in visibleSelectedRoles"
                  :key="r.value"
                  class="z-10 inline-flex items-center justify-center px-1.5 py-0.5 rounded bg-surface-blue-2 text-ink-blue-link text-xs font-medium border border-outline-blue-1"
                >
                  {{ r.label }}
                </span>
                <span
                  v-if="overflowRoleCount > 0"
                  class="z-10 grid size-5 place-items-center rounded-full bg-surface-gray-3 text-p-xs-medium text-ink-gray-7"
                >
                  +{{ overflowRoleCount }}
                </span>
              </div>
              <FeatherIcon v-else name="shield" class="w-4 h-4 text-ink-gray-5" />
            </template>

            <template #summary="{ selectedOptions, summary }">
              <template v-if="selectedOptions.length">
                {{ selectedOptions.map((o) => o.label).join(', ') }}
              </template>
              <template v-else>{{ summary }}</template>
            </template>

            <template #item-label="{ item }">
              <div class="min-w-0 flex items-center justify-between w-full">
                <div class="truncate font-medium text-ink-gray-9 text-xs">{{ item.label }}</div>
              </div>
            </template>
          </MultiSelect>
        </div>

        <!-- Permission Level Selection -->
        <FormControl
          label="Permission Level"
          type="select"
          v-model="newSharePermission"
          :options="[
            { label: 'View Only', value: 'View Only' },
            { label: 'View & Copy', value: 'View & Copy' },
            { label: 'Edit', value: 'Edit' },
            { label: 'Full Control', value: 'Full Control' }
          ]"
        />

        <!-- Optional Expiration Date -->
        <FormControl
          label="Expires On (Optional)"
          type="datetime-local"
          v-model="newShareExpiresOn"
        />

        <!-- Apply to Subfolders Checkbox -->
        <div v-if="sharedDoctype === 'Vault Folder' && hasChildFolders" class="pt-2">
          <div class="flex items-center gap-2">
            <Checkbox
              v-model="newShareCascade"
              label="Apply to all subfolders"
            />
          </div>
          <p class="text-[11px] text-ink-gray-5 mt-1 ml-6 leading-tight">
            If checked, recipients will automatically get access to any subfolders inside this folder.
          </p>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2 px-4 pb-4">
        <Button variant="ghost" label="Cancel" @click="emit('update:modelValue', false)" class="text-ink-gray-7 focus:outline-none" />
        <Button
          variant="solid"
          label="Share"
          :loading="isSharing"
          :disabled="newShareType === 'User' ? selectedUserEmails.length === 0 : selectedRoles.length === 0"
          @click="handleShare"
          class="font-semibold shadow-sm focus:outline-none"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, Button, Avatar, FeatherIcon, FormControl, MultiSelect, TabButtons, Checkbox, toast } from 'frappe-ui'
import { useShareOptions, useShareSecret, useFolders } from '../composables/vault'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  sharedName: { type: String, required: true },
  sharedDoctype: { type: String, default: 'Vault Secret' },
  itemTitle: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'shared'])

const dialogTitle = computed(() => {
  return props.itemTitle ? `Share "${props.itemTitle}"` : 'Share Item'
})

const newShareType = ref('User')
const selectedUserEmails = ref([])
const selectedRoles = ref([])
const newSharePermission = ref('View Only')
const newShareExpiresOn = ref('')
const newShareCascade = ref(true)
const isSharing = ref(false)

const shareOptionsResource = useShareOptions()
const shareResource = useShareSecret()
const foldersResource = useFolders()

const hasChildFolders = computed(() => {
  if (props.sharedDoctype !== 'Vault Folder' || !foldersResource.data) return false
  return foldersResource.data.some(f => f.parent_vault_folder === props.sharedName)
})

const shareOptions = computed(() => shareOptionsResource.data || { users: [], roles: [] })

const userMembers = computed(() => {
  return (shareOptions.value.users || []).map((u) => ({
    label: u.label || u.value,
    value: u.value,
    image: u.image || null,
  }))
})

const roleMembers = computed(() => {
  return (shareOptions.value.roles || []).map((r) => ({
    label: r.label || r.value,
    value: r.value,
  }))
})

const visibleSelectedUsers = computed(() => {
  const selected = userMembers.value.filter((u) => selectedUserEmails.value.includes(u.value))
  return selected.slice(0, 3)
})

const overflowUserCount = computed(() => {
  return Math.max(0, selectedUserEmails.value.length - 3)
})

const visibleSelectedRoles = computed(() => {
  const selected = roleMembers.value.filter((r) => selectedRoles.value.includes(r.value))
  return selected.slice(0, 2)
})

const overflowRoleCount = computed(() => {
  return Math.max(0, selectedRoles.value.length - 2)
})

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    selectedUserEmails.value = []
    selectedRoles.value = []
    newSharePermission.value = 'View Only'
    newShareExpiresOn.value = ''
    newShareCascade.value = true
    if (!shareOptionsResource.data) {
      shareOptionsResource.fetch()
    }
    if (props.sharedDoctype === 'Vault Folder' && !foldersResource.data) {
      foldersResource.fetch()
    }
  }
})

async function handleShare() {
  if (!props.sharedName) {
    toast.error('Please select an item to share')
    return
  }

  isSharing.value = true
  try {
    if (newShareType.value === 'User') {
      for (const email of selectedUserEmails.value) {
        await shareResource.submit({
          shared_name: props.sharedName,
          shared_doctype: props.sharedDoctype,
          share_type: 'User',
          user: email,
          permission_level: newSharePermission.value,
          expires_on: newShareExpiresOn.value || undefined,
          cascade_permissions: newShareCascade.value ? 1 : 0,
        })
      }
    } else {
      for (const role of selectedRoles.value) {
        await shareResource.submit({
          shared_name: props.sharedName,
          shared_doctype: props.sharedDoctype,
          share_type: 'Role',
          frappe_role: role,
          permission_level: newSharePermission.value,
          expires_on: newShareExpiresOn.value || undefined,
          cascade_permissions: newShareCascade.value ? 1 : 0,
        })
      }
    }

    toast.success('Successfully shared!')
    emit('update:modelValue', false)
    emit('shared')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to share')
  } finally {
    isSharing.value = false
  }
}
</script>
