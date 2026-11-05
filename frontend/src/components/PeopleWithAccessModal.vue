<template>
  <Dialog
    :modelValue="modelValue"
    :title="dialogTitle"
    size="lg"
    @update:modelValue="val => emit('update:modelValue', val)"
  >
    <template #default>
      <div class="flex flex-col gap-4 py-1">
        <!-- Read-Only Banner for Revoked Shares -->
        <div v-if="isShareRevoked" class="flex items-center gap-2.5 p-3 rounded-xl bg-surface-gray-2 border border-outline-gray-1 text-ink-gray-9 font-medium text-xs">
          <span class="lucide-alert-circle w-4 h-4 text-ink-gray-7 shrink-0" aria-hidden="true" />
          <span>This share has been revoked. Member access details are read-only.</span>
        </div>

        <TextInput
          v-model="searchQuery"
          type="text"
          placeholder="Search members by name or email…"
          iconLeft="lucide-search"
          class="w-full"
        />

        <div class="space-y-4">
          <!-- Active Members Section (Hidden when share is revoked and 0 active members) -->
          <div v-if="!isShareRevoked || activeMembers.length">
            <div class="flex items-center gap-2 mb-2">
              <h4 class="text-xs font-bold text-ink-gray-5 uppercase tracking-wider">
                Active Members
              </h4>
              <Badge variant="subtle" theme="gray" size="sm" class="!rounded-full font-medium">
                {{ activeMembers.length }}
              </Badge>
            </div>

            <div v-if="roleUsersResource.loading" class="py-6 flex flex-col items-center justify-center space-y-2">
              <span class="lucide-loader w-5 h-5 animate-spin text-ink-gray-5" aria-hidden="true" />
              <span class="text-xs text-ink-gray-5">Loading members...</span>
            </div>

            <div v-else-if="activeMembers.length" class="flex flex-col max-h-56 overflow-y-auto divide-y divide-outline-gray-1 bg-surface-base border border-outline-gray-1 rounded-xl">
              <!-- Header Row -->
              <div class="flex items-center justify-between gap-3 px-2.5 py-2 bg-surface-gray-2 text-xs font-semibold text-ink-gray-6 border-b border-outline-gray-1 sticky top-0 z-10">
                <span class="flex-1">User</span>
                <div class="flex items-center gap-3 shrink-0">
                  <span class="w-36 text-left">Permission</span>
                  <span class="w-7"></span>
                </div>
              </div>

              <div
                v-for="u in activeMembers"
                :key="u.user"
                class="flex items-center justify-between gap-3 p-2.5 hover:bg-surface-gray-1 transition-colors"
              >
                <div class="flex items-center gap-3 min-w-0 flex-1">
                  <Avatar :label="u.full_name || u.user" size="md" />
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-ink-gray-9 truncate">
                      {{ u.full_name || u.user }}
                    </div>
                    <div class="truncate text-xs text-ink-gray-5">
                      {{ u.user }}
                    </div>
                  </div>
                </div>

                <!-- Permission Level Selector -->
                <FormControl
                  v-if="isOwnerOrAdmin && !isShareRevoked && u.can_edit !== false"
                  type="select"
                  :modelValue="getUserPermissionLevel(u)"
                  :options="[
                    { label: 'View Only', value: 'View Only' },
                    { label: 'View & Copy', value: 'View & Copy' },
                    { label: 'Edit', value: 'Edit' },
                    { label: 'Full Control', value: 'Full Control' }
                  ]"
                  class="!w-36 text-xs shrink-0"
                  @update:modelValue="(val) => handleUpdateUserPermission(u, val)"
                  @change="(val) => handleUpdateUserPermission(u, val)"
                />
                <Badge
                  v-else
                  :theme="revokedUserIds.has(u.user) ? 'red' : 'gray'"
                  variant="subtle"
                  size="sm"
                  class="!w-36 flex items-center justify-center shrink-0"
                >
                  {{ revokedUserIds.has(u.user) ? 'Revoked' : getUserPermissionLevel(u) }}
                </Badge>

                <!-- Three-Dot Menu -->
                <Dropdown
                  v-if="isOwnerOrAdmin && !isShareRevoked && u.can_edit !== false"
                  :options="[
                    {
                      label: 'Revoke Access',
                      icon: 'lucide-user-minus',
                      theme: 'red',
                      onClick: () => handleRevokeMember(u)
                    }
                  ]"
                >
                  <template #default="{ open }">
                    <Button variant="ghost" icon="lucide-more-vertical" class="!p-1.5 text-ink-gray-5 hover:text-ink-gray-9 focus:outline-none" />
                  </template>
                </Dropdown>
                <span v-else class="w-7"></span>
              </div>
            </div>
            <p v-else class="text-xs text-ink-gray-5 italic py-4 text-center">No active members.</p>
          </div>

          <!-- Revoked / Removed Members Section -->
          <div v-if="revokedMembers.length">
            <div class="flex items-center gap-2 mb-2">
              <h4 class="text-xs font-bold text-ink-gray-5 uppercase tracking-wider">
                Revoked Members
              </h4>
              <Badge variant="subtle" theme="red" size="sm" class="!rounded-full font-medium">
                {{ revokedMembers.length }}
              </Badge>
            </div>

            <div class="flex flex-col max-h-56 overflow-y-auto divide-y divide-outline-gray-1 bg-surface-gray-2 border border-outline-gray-1 rounded-xl">
              <div
                v-for="u in revokedMembers"
                :key="u.user"
                class="flex items-center justify-between gap-3 p-2.5 hover:bg-surface-gray-1 transition-colors"
              >
                <div class="flex items-center gap-3 min-w-0 flex-1">
                  <Avatar :label="u.full_name || u.user" size="md" class="opacity-60" />
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-ink-gray-7 truncate flex items-center gap-2">
                      <span>{{ u.full_name || u.user }}</span>
                      <Badge variant="subtle" theme="red" size="sm">Revoked</Badge>
                    </div>
                    <div class="truncate text-xs text-ink-gray-5">
                      {{ u.user }}
                    </div>
                  </div>
                </div>

                <Button
                  v-if="isOwnerOrAdmin && !isShareRevoked && u.can_edit !== false"
                  variant="ghost"
                  size="sm"
                  label="Re-grant"
                  class="text-ink-blue-link hover:underline shrink-0"
                  @click="handleRegrantMember(u)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2 px-4 pb-4">
        <Button variant="ghost" :label="isShareRevoked ? 'Close' : 'Cancel'" @click="emit('update:modelValue', false)" class="text-ink-gray-7 focus:outline-none" />
        <Button
          v-if="isOwnerOrAdmin && !isShareRevoked"
          variant="solid"
          theme="gray"
          label="Save Changes"
          :loading="isSaving"
          @click="handleSaveChanges"
          class="px-4 font-semibold shadow-sm focus:outline-none"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, TextInput, Badge, Avatar, FormControl, Dropdown, Button, toast } from 'frappe-ui'
import { useRoleUsers, useSaveRoleMemberPermission } from '../composables/vault'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  roleName: { type: String, default: '' },
  sharedName: { type: String, required: true },
  sharedDoctype: { type: String, default: 'Vault Secret' },
  item: { type: Object, default: null },
  isOwnerOrAdmin: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const dialogTitle = computed(() => {
  return props.roleName ? `People with ${props.roleName} Role` : 'People with Access'
})

const isShareRevoked = computed(() => Boolean(props.item?.is_revoked))

const searchQuery = ref('')
const revokedUserIds = ref(new Set())
const userPermissionOverrides = ref({})
const originalRevokedUserIds = ref(new Set())
const originalUserPermissionOverrides = ref({})
const isSaving = ref(false)

const roleUsersResource = useRoleUsers()
const saveRoleMemberPermResource = useSaveRoleMemberPermission()

const roleUsersList = computed(() => roleUsersResource.data || [])

const filteredRoleUsersList = computed(() => {
  if (!searchQuery.value.trim()) return roleUsersList.value
  const q = searchQuery.value.toLowerCase().trim()
  return roleUsersList.value.filter(u =>
    (u.full_name && u.full_name.toLowerCase().includes(q)) ||
    (u.user && u.user.toLowerCase().includes(q))
  )
})

const activeMembers = computed(() => {
  return filteredRoleUsersList.value.filter(u => !revokedUserIds.value.has(u.user))
})

const revokedMembers = computed(() => {
  return filteredRoleUsersList.value.filter(u => revokedUserIds.value.has(u.user))
})

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    searchQuery.value = ''
    revokedUserIds.value = new Set()
    userPermissionOverrides.value = {}
    originalRevokedUserIds.value = new Set()
    originalUserPermissionOverrides.value = {}
    fetchMembers()
  }
})

watch(() => roleUsersResource.data, (data) => {
  if (data && Array.isArray(data)) {
    const rev = new Set()
    const perms = {}
    data.forEach(u => {
      if (u.is_revoked) rev.add(u.user)
      if (u.permission_level) perms[u.user] = u.permission_level
    })
    revokedUserIds.value = new Set(rev)
    userPermissionOverrides.value = { ...perms }
    originalRevokedUserIds.value = new Set(rev)
    originalUserPermissionOverrides.value = { ...perms }
  }
})

function fetchMembers() {
  let userListArg = undefined
  if (props.item?.user_list) {
    userListArg = Array.isArray(props.item.user_list)
      ? JSON.stringify(props.item.user_list)
      : props.item.user_list
  } else if (props.item?.user) {
    userListArg = JSON.stringify([props.item.user])
  }

  roleUsersResource.submit({
    role_name: props.roleName || undefined,
    shared_name: props.sharedName,
    shared_doctype: props.sharedDoctype,
    shared_by: props.item?.shared_by || undefined,
    user_list: userListArg
  })
}

function getUserPermissionLevel(userObj) {
  if (userPermissionOverrides.value && userPermissionOverrides.value[userObj.user]) {
    return userPermissionOverrides.value[userObj.user]
  }
  return userObj.permission_level || 'View Only'
}

function handleUpdateUserPermission(userObj, val) {
  const permValue = (val && typeof val === 'object' && val.value) ? val.value : (val || 'View Only')
  userPermissionOverrides.value = {
    ...userPermissionOverrides.value,
    [userObj.user]: permValue
  }
}

function handleRevokeMember(userObj) {
  const updatedSet = new Set(revokedUserIds.value)
  updatedSet.add(userObj.user)
  revokedUserIds.value = updatedSet
}

function handleRegrantMember(userObj) {
  const updatedSet = new Set(revokedUserIds.value)
  updatedSet.delete(userObj.user)
  revokedUserIds.value = updatedSet
}

async function handleSaveChanges() {
  isSaving.value = true
  try {
    const users = roleUsersList.value || []
    let changesMade = false

    for (const u of users) {
      const isRev = revokedUserIds.value.has(u.user)
      const permLevel = userPermissionOverrides.value[u.user] || u.permission_level || 'View Only'

      const originalIsRev = originalRevokedUserIds.value.has(u.user)
      const originalPermLevel = originalUserPermissionOverrides.value[u.user] || u.permission_level || 'View Only'

      if (isRev !== originalIsRev || permLevel !== originalPermLevel) {
        changesMade = true
        await saveRoleMemberPermResource.submit({
          shared_name: props.sharedName,
          shared_doctype: props.sharedDoctype,
          user: u.user,
          permission_level: permLevel,
          is_revoked: isRev,
          is_role_override: props.item?.share_type === 'Role' ? true : false,
        })
      }
    }

    if (changesMade) {
      toast.success('Member permissions saved successfully')
    }

    emit('update:modelValue', false)
    emit('saved')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to save member permissions')
  } finally {
    isSaving.value = false
  }
}
</script>
