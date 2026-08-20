<template>
  <Dialog
    v-model="isOpen"
    :options="{
      title: 'Add Existing User',
    }"
  >
    <template #body-content>
      <div class="flex flex-col gap-4">
        <div class="flex items-start gap-2 p-3 bg-surface-gray-2 border border-outline-gray-3 rounded-lg text-sm text-ink-gray-7">
          <FeatherIcon name="info" class="w-4 h-4 mt-0.5 shrink-0" />
          <p>Add existing system users to this Vault. Assign them a role to grant access with their current credentials.</p>
        </div>

        <div class="flex flex-col gap-4">
          <FormControl
            v-if="userOptions.length > 0"
            type="multiselect"
            :label="`Users (${userOptions.length})`"
            v-model="selectedUser"
            :options="userOptions"
            placeholder="Search Users..."
            empty-text="No available users found"
            class="w-full"
          >
            <template #item-prefix="{ item }">
              <Avatar :image="item.image" :label="item.label" size="sm" />
            </template>
            <template #item-label="{ item }">
              <div class="min-w-0 flex justify-between">
                <div class="truncate">{{ item.label }}</div>
                <div class="truncate text-xs text-ink-gray-5">
                  {{ item.description }}
                </div>
              </div>
            </template>
          </FormControl>
          
          <div v-else class="flex flex-col gap-1.5">
            <label class="block text-xs text-ink-gray-5">Users (0)</label>
            <div class="flex flex-col items-center justify-center p-6 border border-dashed border-outline-gray-3 rounded-lg bg-surface-gray-1">
              <FeatherIcon name="users" class="w-8 h-8 text-ink-gray-4 mb-2" />
              <p class="text-sm font-medium text-ink-gray-8">No Users Found</p>
              <p class="text-xs text-ink-gray-5 text-center mt-1">
                There are no more system users available to add, or all users have already been added to this Vault.
              </p>
            </div>
          </div>

          <FormControl
            v-model="selectedRole"
            type="select"
            label="Role"
            :options="[
              { label: 'Admin', value: 'Vault Admin' },
              { label: 'User', value: 'Vault User' },
            ]"
            :description="roleDescription"
          />
        </div>
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="subtle" @click="isOpen = false">
          Cancel
        </Button>
        <Button
          label="Add"
          variant="solid"
          :disabled="!selectedUser || selectedUser.length === 0"
          :loading="addNewUser.loading"
          @click="addNewUser.submit()"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { createResource, toast } from 'frappe-ui'
import { usersStore } from '@/stores/users'
import {
  Dialog,
  Button,
  FormControl,
  FeatherIcon,
  Avatar
} from 'frappe-ui'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const { users, usersFull } = usersStore()
const selectedUser = ref([])
const selectedRole = ref('Vault User')

const addNewUser = createResource({
  url: 'frappe_vault.api.user.add_existing_users',
  makeParams: () => ({
    users: JSON.stringify(selectedUser.value.map(u => u.value || u)),
    role: selectedRole.value,
  }),
  onSuccess: () => {
    toast.success('Users Added Successfully')
    selectedUser.value = []
    isOpen.value = false
    users.reload()
  },
  onError: (e) => {
    toast.error(e?.messages?.[0] || 'Something went wrong')
  }
})

const userOptions = computed(() => {
  const existingVaultUsers = (users.data?.vaultUsers || []).map(u => u.name)
  const allAvailableUsers = usersFull.data?.allUsers || []
  return allAvailableUsers
    .filter(u => !existingVaultUsers.includes(u.name))
    .map(u => ({
      label: u.full_name,
      value: u.name,
      description: u.email,
      image: u.user_image
    }))
})

const roleDescription = computed(() => {
  if (selectedRole.value === 'Vault Admin') {
    return 'Can manage vault settings, share settings globally, and view audit logs.'
  }
  return 'Can access shared secrets, create their own secrets, and share them.'
})

watch(isOpen, (val) => {
  if (val && !usersFull.data) {
    usersFull.fetch()
  }
})
</script>
