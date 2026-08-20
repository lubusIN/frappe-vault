<template>
  <div class="flex h-full flex-col gap-6 p-6 text-ink-gray-8">
    <!-- Header -->
    <div class="flex justify-between px-2 pt-2">
      <div class="flex flex-col gap-1 w-9/12">
        <h2 class="flex gap-2 text-2xl-semibold leading-none h-5">
          Users
        </h2>
        <p class="text-p-base text-ink-gray-6">
          Manage Vault users by adding or inviting them, and assign roles to control their access and permissions
        </p>
      </div>
      <div class="flex item-center space-x-2 w-3/12 justify-end">
        <Dropdown
          :options="[
            {
              label: 'Add Existing User',
              icon: 'lucide-user-plus',
              onClick: () => (showAddExistingModal = true),
            },
            {
              label: 'Invite New User',
              icon: 'lucide-mail',
              onClick: () => emit('navigateTo', 'Invite Users'),
            }
          ]"
          :button="{
            label: 'New',
            iconLeft: 'plus',
            variant: 'solid',
          }"
          placement="right"
        />
      </div>
    </div>

    <!-- loading state -->
    <div v-if="users.loading" class="flex mt-28 justify-between w-full h-full">
      <Button
        :loading="users.loading"
        variant="ghost"
        class="w-full"
        size="2xl"
      />
    </div>

    <!-- Empty State -->
    <div v-else-if="!usersList?.length && !search" class="flex flex-col items-center justify-center flex-1 h-full gap-3">
      <FeatherIcon name="user" class="w-12 h-12 text-ink-gray-4 stroke-1" />
      <div class="flex flex-col items-center gap-1 text-center">
        <p class="text-lg font-medium text-ink-gray-8">No Users Found</p>
        <p class="text-sm text-ink-gray-5">Add one to get started.</p>
      </div>
    </div>

    <!-- Users List -->
    <div
      v-else
      class="flex flex-col overflow-hidden"
    >
      <div
        v-if="usersList?.length > 5"
        class="flex items-center gap-2 mb-4 px-2 pt-0.5"
      >
        <TextInput
          v-model="search"
          placeholder="Search User"
          class="w-full"
          :debounce="300"
        >
          <template #prefix>
            <span
              class="lucide-search h-4 w-4 text-ink-gray-6"
              aria-hidden="true"
            />
          </template>
        </TextInput>
        <Select
          v-model="currentRole"
          class="shrink-0"
          :options="[
            { label: 'All', value: 'All' },
            { label: 'Vault Admin', value: 'Vault Admin' },
            { label: 'Vault User', value: 'Vault User' },
          ]"
        />
      </div>
      <ul class="divide-y divide-outline-elevation-2 overflow-y-auto px-2">
        <template v-for="user in usersList" :key="user.name">
          <li class="flex items-center justify-between py-2">
            <div class="flex items-center">
              <Avatar
                :image="user.user_image"
                :label="user.full_name"
                size="xl"
              />
              <div class="flex flex-col ml-3">
                <div class="flex items-center text-p-base text-ink-gray-8">
                  {{ user.full_name }}
                </div>
                <div class="text-p-sm text-ink-gray-5">
                  {{ user.name }}
                </div>
              </div>
            </div>
            <div class="flex gap-2 items-center flex-row-reverse">
              <Dropdown
                :options="getMoreOptions(user)"
                :button="{
                  icon: 'more-horizontal',
                }"
                placement="right"
              />
              <Tooltip
                v-if="user.role == 'System Manager'"
                text="Cannot change role of user with System Manager access"
              >
                <Button label="Admin" icon-left="lucide-shield" />
              </Tooltip>
              <Tooltip
                v-if="user.is_pending"
                text="User has not accepted the invitation yet"
              >
                <div class="px-2 py-1 bg-surface-gray-2 rounded text-ink-gray-5 text-sm mr-2 flex items-center gap-1">
                  <FeatherIcon name="clock" class="w-3 h-3" />
                  Pending
                </div>
              </Tooltip>
              <Dropdown
                v-else-if="!user.is_pending && getDropdownOptions(user).length > 0"
                :options="getDropdownOptions(user)"
                :button="{
                  label: user.role,
                  iconRight: 'chevron-down',
                  iconLeft: user.role === 'Vault Admin' ? 'shield' : 'user',
                }"
                placement="right"
              />
            </div>
          </li>
        </template>
      </ul>
    </div>
  </div>
  <AddExistingUserModal
    v-if="showAddExistingModal"
    v-model="showAddExistingModal"
  />
</template>

<script setup>
import AddExistingUserModal from '@/components/Modals/AddExistingUserModal.vue'
import { usersStore } from '@/stores/users'
import {
  Dropdown,
  Avatar,
  TextInput,
  toast,
  call,
  Tooltip,
  Select,
  Button,
  FeatherIcon,
  createListResource
} from 'frappe-ui'
import { ref, computed } from 'vue'

const emit = defineEmits(['navigateTo'])
const { users } = usersStore()

const showAddExistingModal = ref(false)
const search = ref('')
const currentRole = ref('All')

const pendingInvitations = createListResource({
  type: 'list',
  doctype: 'Vault Invitation',
  filters: { status: 'Pending' },
  fields: ['name', 'email', 'role'],
  pageLength: 999,
  auto: true,
})

const usersList = computed(() => {
  let filteredUsers = users.data?.vaultUsers || []
  let pendingUsers = (pendingInvitations.data || []).map(inv => ({
    name: inv.name,
    email: inv.email,
    full_name: inv.email,
    role: inv.role,
    is_pending: true,
  }))

  let allList = [...filteredUsers, ...pendingUsers]

  return allList
    .filter(
      (user) =>
        (user.name || '').toLowerCase().includes(search.value.toLowerCase()) ||
        (user.full_name || '').toLowerCase().includes(search.value.toLowerCase()),
    )
    .filter((user) => {
      if (currentRole.value === 'All') return true
      return user.role === currentRole.value
    })
})

function getMoreOptions(user) {
  if (user.is_pending) {
    return [
      {
        label: 'Delete Invite',
        icon: 'trash-2',
        onClick: () => {
          pendingInvitations.delete.submit(user.name).then(() => {
            toast.success('Invitation deleted')
            pendingInvitations.reload()
          })
        }
      }
    ]
  }
  return [
    {
      label: 'Remove',
      icon: 'trash-2',
      onClick: () => removeUser(user)
    }
  ]
}

function getDropdownOptions(user) {
  return [
    {
      label: 'Vault Admin',
      icon: 'shield',
      onClick: () => updateRole(user, 'Vault Admin'),
    },
    {
      label: 'Vault User',
      icon: 'user',
      onClick: () => updateRole(user, 'Vault User'),
    },
  ]
}

function updateRole(user, newRole) {
  if (user.role === newRole) return

  call('frappe_vault.api.user.update_user_role', {
    user: user.name,
    new_role: newRole,
  })
    .then(() => {
      toast.success(`${user.full_name} has been granted ${newRole} access`)
      users.reload()
    })
    .catch((e) => {
      toast.error(e?.messages?.[0] || 'Something went wrong')
    })
}

function removeUser(user) {
  call('frappe_vault.api.user.remove_vault_roles_from_user', {
    user: user.name,
  })
    .then(() => {
      toast.success(`User ${user.full_name} has been removed`)
      users.reload()
    })
    .catch((e) => {
      toast.error(e?.messages?.[0] || 'Something went wrong')
    })
}
</script>
