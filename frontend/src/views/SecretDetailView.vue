<template>

  <div class="h-full w-full bg-surface-base text-ink-gray-9 flex flex-col">
    <!-- Split header using PageHeaderBase -->
            <PageHeaderBase class="flex h-12 border-b border-outline-gray-1 bg-surface-base shrink-0">
      <!-- Details Main Header (Left/Middle) -->
      <div :class="[showActivitySidebar ? 'hidden lg:flex' : 'flex', 'min-w-0 flex-1 items-center justify-between gap-3 px-3 lg:px-5 bg-surface-base']">
        <div class="flex min-w-0 items-center gap-2">
          <Button variant="ghost" icon="lucide-arrow-left" @click="router.push('/secrets')" />
          <div v-if="secretData" :class="`size-6 rounded-full flex items-center justify-center shrink-0 shadow-sm border border-outline-gray-1 ${typeMeta[secretData.secret_type || 'Other']?.bg}`">
            <FeatherIcon :name="typeMeta[secretData.secret_type || 'Other']?.icon || 'key'" class="w-3.5 h-3.5 text-ink-gray-7" />
          </div>
          <PageHeaderTitle v-if="secretData">{{ secretData.title }}</PageHeaderTitle>
          <div v-if="secretData" class="text-sm text-ink-gray-5 font-mono ml-2 cursor-copy hover:text-ink-gray-8" @click="copyToClipboard(secretData.name)" title="Copy ID">
            {{ secretData.name }}
          </div>
        </div>

        <div class="flex items-center gap-1 shrink-0">
          <Button v-if="canEdit" variant="ghost" :icon="isEditing ? 'lucide-eye' : 'lucide-edit'" :label="isEditing ? 'View' : 'Edit'" @click="toggleEditMode" />
          <Button v-if="canDelete" variant="ghost" icon="lucide-trash-2" theme="red" title="Delete" @click="showDeleteDialog = true" />
          <Button variant="ghost" :icon="showActivitySidebar ? 'lucide-panel-right-close' : 'lucide-panel-right'" title="Toggle Activity" @click="showActivitySidebar = !showActivitySidebar" />
        </div>
      </div>

      <!-- Activity Sidebar Header (Right) -->
      <div v-show="showActivitySidebar" class="flex w-full lg:w-1/2 shrink-0 items-center justify-between lg:border-l border-outline-gray-1 px-3 lg:px-4 bg-surface-base">
        <div class="flex items-center gap-2">
          <Button class="lg:hidden" variant="ghost" icon="lucide-arrow-left" @click="showActivitySidebar = false" />
          <PageHeaderTitle>Sharing & Activity</PageHeaderTitle>
        </div>
      </div>
    </PageHeaderBase>

    <div v-if="secretData" class="flex min-h-0 flex-1">
      <!-- Reading pane (Left side: Details) -->
      <section :class="[showActivitySidebar ? 'hidden lg:flex' : 'flex', 'h-full min-h-0 min-w-0 flex-1 flex-col bg-surface-gray-2/20']">


        <ScrollArea class="min-h-0 flex-1">
          <div class="space-y-6 px-5 py-6">

            <SecretDetailsPanel
              ref="dataPanelRef"
              :name="props.name"
              :secret-data="secretData || {}"
              :can-edit="canEdit"
              :can-copy="canCopy"
              :can-reveal="canReveal"
              @open-totp="showTotpDialog = true"
              @open-rotate="openRotateDialog"
              @saved="handleSecretSaved"
            />

            <SecretInfoPanel :secret-data="secretData || {}" />

          </div>
        </ScrollArea>
      </section>

      <!-- Message list pane (Right side: Tabs) -->
      <SecretActivitySidebar
        v-show="showActivitySidebar"
        :name="props.name"
        :secret-data="secretData || {}"
      />
    </div>

    <!-- Empty Loading State -->
    <div v-else class="flex-1 flex items-center justify-center bg-surface-base">
      <div class="h-8 w-8 border-2 border-ink-blue-3 border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Delete Confirmation Dialog -->
    <Dialog
      v-model="showDeleteDialog"
      :options="{
        title: 'Delete Secret',
        size: 'sm',
      }"
    >
      <template #body-content>
        <div class="space-y-3">
          <p class="text-sm text-ink-gray-6 mt-1 leading-normal">
            Are you sure you want to permanently delete <strong>{{ secretData?.title }}</strong>? This action cannot be undone.
          </p>
          <ErrorMessage v-if="deleteError" :message="deleteError" />
        </div>
      </template>
      <template #actions>
        <div class="flex items-center justify-end gap-2 px-4 pb-4">
          <Button variant="outline" @click="showDeleteDialog = false" class="text-ink-gray-7 hover:bg-surface-gray-2">
            Cancel
          </Button>
          <Button variant="solid" theme="red" @click="confirmDelete" :loading="deleteResource.loading" class="font-semibold shadow-sm px-4">
            Delete
          </Button>
        </div>
      </template>
    </Dialog>

    <!-- Rotate Now Dialog -->
    <Dialog
      v-model="showRotateDialog"
      :options="{
        title: 'Rotate ' + (secretData?.title || 'Secret'),
        size: 'sm',
      }"
    >
      <template #body-content>
        <div class="space-y-3">
          <p class="text-sm text-ink-gray-6 leading-normal">
            Generate a new password now. Everyone with access is notified, and can read the new value
            here on this page.
          </p>
          <p v-if="secretData?.apply_rotation_to_target" class="text-sm text-ink-gray-6 leading-normal">
            The password will also be changed on the live
            <strong>{{ secretData?.database_type || 'database' }}</strong> at
            <strong>{{ secretData?.db_host }}</strong>. Anything still connecting with the old password
            &mdash; applications, config files, connection strings &mdash; will start failing until it is
            updated. If the server refuses the change, nothing here is modified either.
          </p>
          <p v-else class="text-sm text-ink-gray-6 leading-normal">
            The current password is replaced in Vault only &mdash; it is <strong>not</strong> changed on the
            target system, you must apply it there yourself.
          </p>
          <ErrorMessage v-if="rotateError" :message="rotateError" />
        </div>
      </template>
      <template #actions>
        <div class="flex items-center justify-end gap-2 px-4 pb-4">
          <Button variant="outline" @click="showRotateDialog = false" class="text-ink-gray-7 hover:bg-surface-gray-2">
            Cancel
          </Button>
          <Button variant="solid" @click="handleRotateNow" :loading="rotateNowResource.loading" class="font-semibold shadow-sm px-4">
            Rotate
          </Button>
        </div>
      </template>
    </Dialog>

    <!-- TOTP Dialog -->
    <TotpDialog
      v-model="showTotpDialog"
      :secretName="props.name"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Button,
  FeatherIcon,
  Dialog,
  ErrorMessage,
  toast,
  PageHeaderBase,
  PageHeaderTitle,
  ScrollArea,
} from 'frappe-ui'
import { useSecret, useDeleteSecret, useVaultStats, useRotateNow } from '../composables/vault'
import { useClipboard } from '../composables/clipboard'
import SecretActivitySidebar from '../components/SecretActivitySidebar.vue'
import SecretDetailsPanel from '../components/SecretDetailsPanel.vue'
import SecretInfoPanel from '../components/SecretInfoPanel.vue'
import TotpDialog from '../components/TotpDialog.vue'
import { typeMeta } from '../composables/constants'

const props = defineProps({
  name: {
    type: String,
    required: true,
  }
})

const router = useRouter()
const clipboard = useClipboard()

const showActivitySidebar = ref(window.innerWidth >= 1024)
const showTotpDialog = ref(false)

function handleResize() {
  if (window.innerWidth >= 1024) {
    showActivitySidebar.value = true
  } else {
    showActivitySidebar.value = false
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  window.addEventListener('vault-secret-updated', handleVaultSecretUpdated)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('vault-secret-updated', handleVaultSecretUpdated)
})

watch(() => props.name, (name) => {
  if (!name) return
  secret.submit({ name })
  showTotpDialog.value = false
})

const dataPanelRef = ref(null)
const isEditing = computed(() => dataPanelRef.value?.isEditing)

function toggleEditMode() {
  dataPanelRef.value?.toggleEditMode()
}

function handleSecretSaved() {
  secret.submit({ name: props.name })
}

function handleVaultSecretUpdated(event) {
  const updatedName = event?.detail?.name
  if (!updatedName || updatedName === props.name) {
    secret.submit({ name: props.name })
  }
}

function copyToClipboard(text) {
  if (!text) return
  clipboard.copy(text)
  toast.success('Copied to clipboard')
}

// --- Resources ---
const secret = useSecret(props.name)
const deleteResource = useDeleteSecret()
const rotateNowResource = useRotateNow()
const stats = useVaultStats()

const secretData = computed(() => secret.data)

// --- Permissions ---
const currentSessionUser = computed(() => {
  if (window.frappe?.boot?.user) {
    if (typeof window.frappe.boot.user === 'object') {
      return window.frappe.boot.user.name || 'Guest'
    }
    return window.frappe.boot.user
  }
  if (window.frappe?.session?.user) {
    return window.frappe.session.user
  }
  if (window.frappe?.user?.name) {
    return window.frappe.user.name
  }
  return 'Guest'
})

const userPermission = computed(() => secretData.value?.user_permission || 'View Only')

// Decided by the server, and deliberately not inferable from roles: the admin
// bypass that grants every other permission here does not grant sight of a
// secret's values.
const canReveal = computed(() => !!secretData.value?.can_reveal)

const canEdit = computed(() => {
  // The edit form is populated from the decrypted values, so it cannot be
  // opened by someone who may not see them. Administering a secret — moving,
  // deleting, managing its shares — does not depend on this.
  if (!canReveal.value) return false
  if (stats.data?.is_admin) return true
  if (currentSessionUser.value === 'Administrator') return true
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  if (roles.includes('Vault Admin')) return true
  if (secretData.value?.owner === currentSessionUser.value) return true
  return ['Edit', 'Full Control'].includes(userPermission.value)
})

const canDelete = computed(() => {
  if (stats.data?.is_admin) return true
  if (currentSessionUser.value === 'Administrator') return true
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  if (roles.includes('Vault Admin')) return true
  if (secretData.value?.owner === currentSessionUser.value) return true
  return userPermission.value === 'Full Control'
})

const canCopy = computed(() => {
  // Copying a stored value means decrypting it first.
  if (!canReveal.value) return false
  if (stats.data?.is_admin) return true
  if (currentSessionUser.value === 'Administrator') return true
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  if (roles.includes('Vault Admin')) return true
  if (secretData.value?.owner === currentSessionUser.value) return true
  return ['View & Copy', 'Edit', 'Full Control'].includes(userPermission.value)
})

// --- Delete ---
const showDeleteDialog = ref(false)
const deleteError = ref('')

async function confirmDelete() {
  deleteError.value = ''
  try {
    await deleteResource.submit({ name: props.name })
    showDeleteDialog.value = false
    window.dispatchEvent(new CustomEvent('vault-secret-updated', { detail: { name: props.name } }))
    toast.success('Secret deleted successfully')
    router.push('/secrets')
  } catch (err) {
    deleteError.value = err.messages?.[0] || err.message || 'Failed to delete secret'
    toast.error(deleteError.value)
  }
}

// --- Rotate Now ---
const showRotateDialog = ref(false)
const rotateError = ref('')

function openRotateDialog() {
  rotateError.value = ''
  showRotateDialog.value = true
}

async function handleRotateNow() {
  rotateError.value = ''
  try {
    const result = await rotateNowResource.submit({ name: props.name })
    showRotateDialog.value = false
    toast.success(result.message || 'Password rotated')
    window.dispatchEvent(new CustomEvent('vault-secret-updated', { detail: { name: props.name } }))
  } catch (err) {
    rotateError.value = err.messages?.[0] || err.message || 'Failed to rotate password'
  }
}

</script>
