<template>
  <div class="flex flex-col h-full p-4 rounded-r-lg">
    <div class="px-4 py-3">
      <h2 class="text-xl font-semibold text-ink-gray-9 mb-1">Profile</h2>
      <p class="text-sm text-ink-gray-5">Manage your profile & login information.</p>
    </div>
    
    <div v-if="user.doc" class="flex-1 overflow-y-auto px-4 mt-6">
      <div class="flex items-center justify-between gap-4 pb-8">
        <FileUploader
          :validateFile="validateIsImageFile"
          @success="(file) => updateImage(file.file_url)"
        >
          <template #default="{ openFileSelector, error: _error, uploading }">
            <div class="flex items-center gap-4">
              <div class="group relative size-16">
                <Avatar
                  class="size-16 text-lg"
                  :image="user.doc.user_image"
                  :label="fullName"
                />
                <Tooltip
                  :hoverDelay="0"
                  placement="bottom"
                  :text="profileTooltipText"
                >
                  <div
                    class="absolute inset-0 cursor-pointer rounded-full z-10"
                    @click.stop="openFileSelector"
                  />
                  <div
                    v-if="user.doc.user_image"
                    class="absolute -top-1 -right-1 size-5 flex items-center justify-center rounded-full bg-surface-base opacity-0 transition-opacity duration-300 group-hover:opacity-100 hover:bg-surface-gray-2 outline outline-black/5 z-20 cursor-pointer"
                    @click.stop="updateImage('')"
                    @mouseenter="isHoveringRemove = true"
                    @mouseleave="isHoveringRemove = false"
                  >
                    <span class="lucide-x size-3 text-ink-gray-5" aria-hidden="true" />
                  </div>
                </Tooltip>
                <div
                  v-if="uploading"
                  class="absolute inset-0 bg-black/20 rounded-full flex items-center justify-center z-30"
                >
                  <LoadingIndicator class="size-4" />
                </div>
              </div>

              <div class="flex flex-col gap-1">
                <div v-if="!editName" class="flex items-center gap-2">
                  <span class="text-lg font-semibold text-ink-gray-9">
                    {{ fullName }}
                  </span>
                  <Button variant="ghost" class="!px-1.5 h-6" @click="editFullName">
                    <span class="lucide-edit-2 size-3.5 text-ink-gray-5" />
                  </Button>
                </div>
                <div v-else class="flex items-center gap-2">
                  <TextInput
                    id="profile-name-input"
                    v-model="fullName"
                    class="w-48"
                    @keydown.enter="save"
                    @keydown.esc.stop="editName = false"
                  />
                  <Button variant="outline" icon="lucide-check" class="h-7 w-7" @click="save" />
                </div>
                <span class="text-sm text-ink-gray-5">
                  {{ user.doc.email }}
                </span>
                <ErrorMessage v-if="_error" :message="_error" />
              </div>
            </div>
          </template>
        </FileUploader>
      </div>

      <div class="border-t border-outline-gray-2 pt-8">
        <h3 class="text-base font-semibold text-ink-gray-9 mb-6">
          Account Info & Security
        </h3>
        
        <div class="flex items-center justify-between mb-6">
          <div class="flex flex-col gap-1">
            <span class="text-sm font-medium text-ink-gray-8">
              Password
            </span>
            <span class="text-sm text-ink-gray-5">
              Change your account password for security.
            </span>
          </div>
          <Button
            label="Change Password"
            @click="showChangePasswordModal = true"
          />
        </div>
      </div>
    </div>
  </div>

  <ChangePasswordModal
    v-if="showChangePasswordModal"
    v-model="showChangePasswordModal"
  />
</template>

<script setup>
import { ref, computed, useTemplateRef, nextTick } from 'vue'
import {
  Avatar,
  TextInput,
  FileUploader,
  LoadingIndicator,
  Tooltip,
  createDocumentResource,
  Button,
  ErrorMessage,
  toast,
  call
} from 'frappe-ui'
import ChangePasswordModal from '../../Modals/ChangePasswordModal.vue'

function validateIsImageFile(file) {
  if (!file.type.startsWith('image/')) {
    return 'Only image files are allowed'
  }
  return null
}

const sessionUser = window.frappe?.boot?.user?.name || window.frappe?.session?.user || 'Administrator'
const user = createDocumentResource({ doctype: 'User', name: sessionUser })

const showChangePasswordModal = ref(false)
const isHoveringRemove = ref(false)
const editName = ref(false)

const profileTooltipText = computed(() => {
  if (isHoveringRemove.value) return 'Remove Photo'
  return user.doc.user_image ? 'Change Photo' : 'Upload Photo'
})

const fullName = computed({
  get: () => [user.doc.first_name, user.doc.last_name].filter(Boolean).join(' '),
  set: (val) => {
    const [firstName, ...lastName] = val.split(' ')
    user.doc.first_name = firstName
    user.doc.last_name = lastName.join(' ')
  },
})

function editFullName() {
  editName.value = true
  nextTick(() => {
    document.getElementById('profile-name-input')?.focus()
  })
}

const isDirty = computed(() => {
  return JSON.stringify(user.doc) !== JSON.stringify(user.originalDoc)
})

async function save() {
  if (!isDirty.value) {
    editName.value = false
    return
  }

  try {
    const res = await call('frappe_vault.api.user.update_profile', {
      first_name: user.doc.first_name,
      last_name: user.doc.last_name,
      user_image: user.doc.user_image
    })
    
    // Update originalDoc so it's no longer "dirty"
    user.originalDoc = JSON.parse(JSON.stringify(user.doc))
    editName.value = false
    toast.success('Profile updated successfully')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to update profile')
  }
}

function updateImage(fileUrl = '') {
  isHoveringRemove.value = false
  user.doc.user_image = fileUrl
  save()
}
</script>
