<template>
  <div class="flex h-full flex-col gap-6 p-6 text-ink-gray-8">
    <div class="flex px-2 justify-between">
      <div class="flex flex-col gap-1 w-9/12">
        <h2 class="flex gap-2 text-2xl-semibold leading-none h-5">
          Send Invites
        </h2>
        <p class="text-p-base text-ink-gray-6">
          Invite users to access Vault. Specify their roles to control access and permissions
        </p>
      </div>
      <div class="flex item-center space-x-2 w-3/12 justify-end">
        <Button
          label="Send Invites"
          variant="solid"
          :disabled="!invitees.length || userExistMessage || inviteeExistMessage"
          :loading="inviteByEmail.loading"
          @click="inviteByEmail.submit()"
        />
      </div>
    </div>
    <div class="flex-1 flex flex-col px-2 gap-8 overflow-y-auto">
      <div>
        <FormControl
          type="textarea"
          label="Invite By Email"
          placeholder="user1@example.com, user2@example.com, ..."
          :debounce="100"
          :disabled="inviteByEmail.loading"
          description="You can invite multiple users by comma separating their email addresses"
          @input="updateInvitees($event.target.value)"
        />
        <div
          v-if="userExistMessage || inviteeExistMessage"
          class="text-xs text-ink-red-6 mt-1.5"
        >
          {{ userExistMessage || inviteeExistMessage }}
        </div>
        <FormControl
          v-model="role"
          type="select"
          class="mt-4"
          label="Invite As"
          :options="roleOptions"
          :description="description"
        />
      </div>
      <template v-if="pendingInvitations.data?.length && !invitees.length">
        <div class="flex flex-col gap-4">
          <div class="flex items-center justify-between text-base-semibold">
            <div>Pending Invites</div>
          </div>
          <ul class="flex flex-col gap-1">
            <li
              v-for="user in pendingInvitations.data"
              :key="user.name"
              class="flex items-center justify-between px-2 py-1 rounded-lg bg-surface-gray-2"
            >
              <div class="text-base">
                <span class="text-ink-gray-8">
                  {{ user.email }}
                </span>
                <span class="text-ink-gray-5">
                  ({{ roleMap[user.role] }})
                </span>
              </div>
              <div>
                <Button
                  tooltip="Delete Invitation"
                  icon="lucide-x"
                  variant="ghost"
                  :loading="
                    pendingInvitations.delete.loading &&
                    pendingInvitations.delete.params.name === user.name
                  "
                  @click="pendingInvitations.delete.submit(user.name)"
                />
              </div>
            </li>
          </ul>
        </div>
      </template>
    </div>
    <ErrorMessage :message="error" />
  </div>
</template>

<script setup>
import { usersStore } from '@/stores/users'
import {
  toast,
  createListResource,
  createResource,
  FormControl,
  Button,
  ErrorMessage,
} from 'frappe-ui'
import { ref, computed } from 'vue'

const { users } = usersStore()

const invitees = ref([])
const role = ref('Vault User')
const error = ref(null)

const validateEmail = (email) => {
  return String(email)
    .toLowerCase()
    .match(
      /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/
    );
};

const userExistMessage = computed(() => {
  const inviteesSet = new Set(invitees.value)
  if (!inviteesSet.size) return null

  if (!users.data?.length) return null
  const existingEmails = users.data.map((user) => user.name)
  const existingUsersSet = new Set(existingEmails)

  const existingInvitees = inviteesSet.intersection(existingUsersSet)
  if (existingInvitees.size === 0) return null

  return `User with email ${Array.from(existingInvitees).join(', ')} already exists`
})

const inviteeExistMessage = computed(() => {
  const inviteesSet = new Set(invitees.value)
  if (!inviteesSet.size) return null

  if (!pendingInvitations.data?.length) return null
  const existingEmails = pendingInvitations.data.map((user) => user.email)
  const existingUsersSet = new Set(existingEmails)

  const existingInvitees = inviteesSet.intersection(existingUsersSet)
  if (existingInvitees.size === 0) return null

  return `User with email ${Array.from(existingInvitees).join(', ')} already invited`
})

const description = computed(() => {
  return {
    'Vault Admin': 'Can manage users, roles, and settings within the Vault.',
    'Vault User': 'Can view and use secrets they have been granted access to.',
  }[role.value]
})

const roleOptions = computed(() => {
  return [
    { value: 'Vault User', label: 'User' },
    { value: 'Vault Admin', label: 'Admin' },
  ]
})

const roleMap = {
  'Vault User': 'User',
  'Vault Admin': 'Admin',
}

const inviteByEmail = createResource({
  url: 'frappe_vault.api.user.invite_by_email',
  makeParams() {
    return {
      emails: invitees.value.join(', '),
      role: role.value,
    }
  },
  onSuccess(data) {
    role.value = 'Vault User'
    error.value = null
    invitees.value = []
    pendingInvitations.reload()

    if (data.to_invite && data.to_invite.length > 0) {
      toast.success('Invitations sent successfully!')
    }
    
    if (data.existing_members && data.existing_members.length > 0) {
      toast.error(`User(s) already exist: ${data.existing_members.join(', ')}. Please manage their roles from the Existing Users tab.`)
    }
    
    if (data.existing_invites && data.existing_invites.length > 0) {
      toast.info(`Invitations already pending for: ${data.existing_invites.join(', ')}`)
    }
  },
  onError(err) {
    error.value = err?.messages?.[0]
    toast.error(error.value)
  },
})

const pendingInvitations = createListResource({
  type: 'list',
  doctype: 'Vault Invitation',
  filters: { status: 'Pending' },
  fields: ['name', 'email', 'role'],
  pageLength: 999,
  auto: true,
})

function updateInvitees(value) {
  const emails = value
    .split(',')
    .map((email) => email.trim())
    .filter((email) => validateEmail(email))
  invitees.value = emails
}
</script>
