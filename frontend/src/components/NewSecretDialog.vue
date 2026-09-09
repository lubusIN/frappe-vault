<template>
  <Dialog v-model="show" :options="{ title: 'Add Secret', size: 'lg' }">
    <template #body-content>
      <div class="space-y-4">
        <FormControl label="Title" v-model="form.title" :required="true" placeholder="e.g. Gmail, AWS Console, Passport Scan" />

        <FormControl label="Secret Type" type="select" v-model="form.secret_type" :options="SECRET_TYPES" />

        <div>
          <label class="block text-xs font-medium text-ink-gray-7 mb-1.5">Folder</label>
          <Autocomplete
            v-model="selectedFolder"
            :options="folderOptions"
            placeholder="Select a folder..."
          >
            <template #item-prefix="{ option }">
              <div :style="{ paddingLeft: (option.level * 1.5) + 'rem' }" class="flex items-center">
                <Icon name="corner-down-right" class="w-4 h-4 mr-2 text-ink-gray-4 shrink-0" v-if="option.level > 0" />
                <Icon name="folder" class="w-4 h-4 mr-2 text-ink-gray-5 shrink-0" v-else-if="option.value !== ''" />
                <div class="w-4 h-4 mr-2 shrink-0" v-else></div>
              </div>
            </template>
          </Autocomplete>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <template v-for="field in secretFieldsConfig[form.secret_type] || []" :key="field.name">
            <!-- Media Attachment Custom UI -->
            <div v-if="field.type === 'file'" class="col-span-2 space-y-2 pt-1">
              <label class="block text-sm font-medium text-ink-gray-7">Document / Media Attachments</label>

              <!-- List of Uploaded Files -->
              <div v-if="attachmentList.length > 0" class="space-y-2">
                <div
                  v-for="(fileUrl, idx) in attachmentList"
                  :key="fileUrl + idx"
                  class="p-2.5 rounded-xl border border-outline-gray-1 bg-surface-gray-2 flex items-center justify-between shadow-2xs"
                >
                  <div class="flex items-center gap-3 overflow-hidden min-w-0">
                    <img
                      v-if="isImageUrl(fileUrl)"
                      :src="fileUrl"
                      class="w-10 h-10 object-cover rounded-lg shrink-0 border border-outline-gray-1 bg-surface-base"
                    />
                    <div v-else class="w-10 h-10 rounded-lg bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0">
                      <FeatherIcon name="paperclip" class="w-5 h-5 text-ink-gray-7" />
                    </div>
                    <div class="min-w-0">
                      <p class="text-xs font-semibold text-ink-gray-9 truncate">{{ getFileName(fileUrl) }}</p>
                      <a :href="fileUrl" target="_blank" class="text-[11px] font-mono text-ink-gray-5 hover:text-blue-600 dark:hover:text-blue-400 hover:underline truncate block">{{ fileUrl }}</a>
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="xs"
                    icon="x"
                    class="!p-1 h-auto text-ink-gray-5 hover:text-ink-red-3 hover:bg-surface-gray-3 focus:outline-none"
                    title="Remove File"
                    @click.stop.prevent="removeAttachment(idx)"
                  />
                </div>
              </div>

              <!-- Multi-File Upload Dropzone Trigger -->
              <div
                class="relative border-2 border-dashed border-outline-gray-2 rounded-xl p-4 text-center hover:border-ink-gray-6 transition-colors cursor-pointer bg-surface-gray-1"
                @click="triggerFileInput('attachment')"
              >
                <FormControl
                  type="file"
                  id="file_input_attachment"
                  class="hidden"
                  multiple
                  accept="*/*"
                  @change="handleFileUpload($event)"
                />
                <div class="flex flex-col items-center gap-1">
                  <FeatherIcon name="paperclip" class="w-6 h-6 text-ink-gray-5" />
                  <span class="text-xs font-semibold text-ink-gray-8">
                    {{ uploadingFiles ? 'Uploading files...' : (attachmentList.length > 0 ? '+ Add More Files' : 'Click or drag files here to upload') }}
                  </span>
                  <span class="text-[10px] text-ink-gray-5">Supports Images, PDFs, Zip, Documents (Select multiple files)</span>
                </div>
              </div>
            </div>

            <!-- Standard Form Control -->
            <FormControl
              v-else
              :label="field.label"
              v-model="form[field.name]"
              :type="field.type === 'password' && showSecrets ? 'text' : field.type"
              :class="(field.colSpan === 2) ? 'col-span-2' : 'col-span-1'"
              :placeholder="field.placeholder"
            >
              <template #suffix v-if="field.type === 'password'">
                <Button variant="ghost" class="!p-1 h-auto text-ink-gray-5 hover:text-ink-gray-9" :icon="showSecrets ? 'lucide-eye-off' : 'lucide-eye'" @click="showSecrets = !showSecrets" />
              </template>
            </FormControl>
          </template>
        </div>

        <FormControl label="Notes" type="textarea" v-model="form.notes" :rows="3" />
      </div>
    </template>

    <template #actions>
      <Button variant="solid" @click="handleCreate" :loading="createResource.loading">Create</Button>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, FormControl, Button, FeatherIcon, toast, Autocomplete } from 'frappe-ui'
import { Icon } from 'frappe-ui/icons'
import { SECRET_TYPES } from '../composables/constants'
import { secretFieldsConfig } from '../composables/secretFields'
import { useFolders, useCreateSecret } from '../composables/vault'
import { cleanUrl, parseAttachments, isImageUrl, getFileName } from '../utils/attachments'
import { validateTotpSecret } from '../utils/secretForm'

const props = defineProps({
  modelValue: Boolean,
  initialFolder: String,
})
const emit = defineEmits(['update:modelValue', 'created'])

const show = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const createResource = useCreateSecret()
const foldersResource = useFolders()

const folderOptions = computed(() => {
  const opts = [{ label: 'None', value: '', level: 0 }]
  const folders = foldersResource.data || []

  // Build a tree structure so we can traverse it and get correct visual ordering
  const tree = []
  const map = {}
  folders.forEach(f => {
    map[f.name] = { ...f, children: [] }
  })

  folders.forEach(f => {
    if (f.parent_vault_folder && map[f.parent_vault_folder]) {
      map[f.parent_vault_folder].children.push(map[f.name])
    } else {
      tree.push(map[f.name])
    }
  })

  const traverse = (nodes, level = 0) => {
    for (const node of nodes) {
      if (node.can_write) {
        opts.push({ label: node.folder_name, value: node.name, level })
      }
      if (node.children?.length) {
        traverse(node.children, level + 1)
      }
    }
  }

  traverse(tree)
  return opts
})

const defaultForm = () => ({
  title: '', secret_type: 'Password', folder: props.initialFolder || '', url: '', username: '', email: '',
  password: '', totp_secret: '', api_key: '', api_secret: '', ssh_private_key: '', attachment: '', notes: '', card_holder: '', card_number: '',
  card_expiry: '', card_cvv: '', db_host: '', db_port: '', db_name: '', db_password: '',
})

const form = ref(defaultForm())
const selectedFolder = ref(null)

watch(() => form.value.folder, (newFolder) => {
  if (typeof newFolder === 'string') {
    selectedFolder.value = folderOptions.value.find(o => o.value === newFolder) || { label: 'None', value: '' }
  }
})

watch(selectedFolder, (newVal) => {
  if (newVal) {
    form.value.folder = newVal.value
  }
})
const attachmentList = ref([])
const showSecrets = ref(false)
const uploadingFiles = ref(false)

watch(show, (v) => {
  if (v) {
    form.value = defaultForm()
    attachmentList.value = []
    showSecrets.value = false
  }
})

function removeAttachment(index) {
  attachmentList.value.splice(index, 1)
  syncAttachmentForm()
}

function syncAttachmentForm() {
  if (attachmentList.value.length === 0) {
    form.value.attachment = ''
  } else if (attachmentList.value.length === 1) {
    form.value.attachment = attachmentList.value[0]
  } else {
    form.value.attachment = JSON.stringify(attachmentList.value)
  }
}

async function handleFileUpload(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return

  uploadingFiles.value = true
  try {
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('is_private', 1)

      const response = await fetch('/api/method/frappe_vault.api.secrets.upload_file', {
        method: 'POST',
        headers: {
          'X-Frappe-CSRF-Token': window.csrf_token || ''
        },
        body: formData
      })
      const data = await response.json()
      if (response.ok && data.message && data.message.file_url) {
        attachmentList.value.push(data.message.file_url)
      } else {
        toast.error(data.message || 'File upload failed')
      }
    }
    syncAttachmentForm()
  } catch (err) {
    toast.error(err.message || 'File upload failed')
  } finally {
    uploadingFiles.value = false
  }
}

function triggerFileInput(fieldname) {
  const el = document.getElementById('file_input_' + fieldname)
  if (el) {
    if (el.tagName === 'INPUT') el.click()
    else {
      const input = el.querySelector('input[type="file"]')
      if (input) input.click()
    }
  }
}

async function handleCreate() {
  if (['Password', 'API Key'].includes(form.value.secret_type) && form.value.totp_secret) {
    const validation = validateTotpSecret(form.value.totp_secret)
    if (!validation.ok) {
      toast.error(validation.message)
      return
    }
  }

  try {
    const result = await createResource.submit(form.value)
    window.dispatchEvent(new CustomEvent('vault-secret-updated', { detail: { name: result?.name } }))
    emit('created', result)
  } catch (err) {
    if (err.messages?.length) {
      err.messages.forEach(msg => toast.error(msg))
    } else {
      toast.error(err.message || 'Failed to create secret')
    }
  }
}
</script>
