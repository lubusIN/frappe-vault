<template>
  <div class="flex flex-col h-full p-4 rounded-r-lg">
    <!-- List View -->
    <template v-if="currentView === 'list'">
      <div class="flex items-center justify-between px-4 py-3">
        <div>
          <h2 class="text-xl font-semibold text-ink-gray-9 mb-1">Email Accounts</h2>
          <p class="text-sm text-ink-gray-5">Manage your email accounts for incoming and outgoing emails.</p>
        </div>
        <Button
          variant="solid"
          icon-left="lucide-plus"
          label="Add Account"
          @click="addAccount"
        />
      </div>

      <div class="flex-1 overflow-y-auto px-4 mt-6">
        <!-- Empty State -->
        <div
          v-if="!accounts.loading && (!accounts.data || accounts.data.length === 0)"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <div class="flex flex-col items-center justify-center py-20">
            <span class="lucide-mail w-12 h-12 text-ink-gray-4 mb-4" aria-hidden="true" />
            <h3 class="text-lg font-medium text-ink-gray-9 mb-1">No Email Accounts Found</h3>
            <p class="text-sm text-ink-gray-5 mb-4">Add one to get started.</p>
          </div>
        </div>

        <!-- Accounts List -->
        <div v-else-if="accounts.data && accounts.data.length > 0" class="flex flex-col gap-4">
          <div
            v-for="account in accounts.data"
            :key="account.name"
            class="flex items-center justify-between p-4 border border-outline-gray-2 rounded-lg hover:bg-surface-gray-2 transition-colors cursor-pointer"
            @click="editAccount(account.name)"
          >
            <div class="flex items-center gap-3">
              <div class="flex items-center justify-center w-10 h-10 rounded-full bg-surface-gray-3">
                <span class="lucide-mail w-5 h-5 text-ink-gray-6" aria-hidden="true" />
              </div>
              <div class="flex flex-col">
                <span class="text-sm font-medium text-ink-gray-9">{{ account.email_account_name || account.email_id }}</span>
                <span class="text-xs text-ink-gray-5">{{ account.email_id }}</span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Badge v-if="account.enable_incoming" theme="green">Incoming</Badge>
              <Badge v-if="account.enable_outgoing" theme="blue">Outgoing</Badge>
              <div @click.stop>
                <Dropdown
                  :options="[
                    {
                      label: 'Remove',
                      icon: 'lucide-trash-2',
                      onClick: () => deleteAccount(account.name)
                    }
                  ]"
                  :button="{
                    icon: 'lucide-more-horizontal',
                    variant: 'ghost'
                  }"
                  placement="bottom-end"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Form View -->
    <template v-else-if="currentView === 'form'">
      <EmailAccountForm
        :accountId="selectedAccountId"
        @back="currentView = 'list'"
        @saved="onAccountSaved"
      />
    </template>

    <!-- Confirm Delete Dialog -->
    <Dialog
      v-model="confirmDeleteDialog.show"
      title="Remove Email Account"
      size="sm"
    >
      <template #default>
        <p class="text-sm text-ink-gray-7">Are you sure you want to remove this email account?</p>
      </template>
      <template #actions>
        <div class="flex justify-end gap-2">
          <Button variant="ghost" label="Cancel" @click="confirmDeleteDialog.show = false" />
          <Button variant="solid" theme="red" label="Delete" @click="confirmDeleteAccount" />
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, Badge, Dropdown, Dialog, createListResource, call, toast } from 'frappe-ui'
import EmailAccountForm from './EmailAccountForm.vue'

// list | providers | form
const currentView = ref('list')
const selectedAccountId = ref(null)

const accounts = createListResource({
  doctype: 'Email Account',
  fields: ['name', 'email_account_name', 'email_id', 'enable_incoming', 'enable_outgoing'],
  limit: 100,
  auto: true
})

function addAccount() {
  selectedAccountId.value = null
  currentView.value = 'form'
}

function editAccount(name) {
  selectedAccountId.value = name
  currentView.value = 'form'
}

function onAccountSaved() {
  accounts.reload()
  currentView.value = 'list'
}

const confirmDeleteDialog = ref({
  show: false,
  accountName: null
})

function deleteAccount(name) {
  confirmDeleteDialog.value = { show: true, accountName: name }
}

async function confirmDeleteAccount() {
  const name = confirmDeleteDialog.value.accountName
  if (!name) return

  confirmDeleteDialog.value.show = false

  try {
    await call('frappe.client.delete', { doctype: 'Email Account', name })
    toast.success('Account removed successfully!')
    accounts.reload()
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to remove account.')
  }
}
</script>
