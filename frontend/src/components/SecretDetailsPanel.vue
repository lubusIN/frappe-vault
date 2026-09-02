<template>
  <article class="space-y-2">
    <div class="flex items-center justify-between cursor-pointer select-none group" @click="detailsOpen = !detailsOpen">
      <h3 class="text-xs font-semibold text-ink-gray-5 uppercase tracking-wider group-hover:text-ink-gray-7 transition-colors">Secret Data</h3>
      <FeatherIcon name="chevron-down" class="w-4 h-4 text-ink-gray-4 transition-transform duration-200" :class="{ '-rotate-90': !detailsOpen }" />
    </div>
    <div v-show="detailsOpen" class="space-y-4 pt-2">
      <!-- EDIT VIEW FORM -->
      <div v-if="isEditing" class="space-y-4 pt-1 px-6">
        <!-- Title -->
        <div class="flex items-center justify-between gap-3 text-sm">
          <label class="w-28 shrink-0 text-ink-gray-5 font-normal">Title <span class="text-ink-red-3">*</span></label>
          <div class="flex-1 min-w-0">
            <TextInput v-model="editForm.title" placeholder="Secret Title" class="w-full text-sm" />
          </div>
        </div>

        <!-- Type select -->
        <div class="flex items-center justify-between gap-3 text-sm">
          <label class="w-28 shrink-0 text-ink-gray-5 font-normal">Type</label>
          <div class="flex-1 min-w-0">
            <FormControl v-model="editForm.secret_type" type="select" :options="secretTypeOptions" class="w-full text-sm cursor-pointer" />
          </div>
        </div>

        <!-- Folder select -->
        <div class="flex items-center justify-between gap-3 text-sm">
          <label class="w-28 shrink-0 text-ink-gray-5 font-normal">Folder</label>
          <div class="flex-1 min-w-0">
            <Autocomplete
              v-model="selectedFolder"
              :options="folderOptions"
              placeholder="Select a folder..."
              class="w-full text-sm cursor-pointer"
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
        </div>

        <div class="w-full border-t border-outline-gray-1 my-2" />

        <!-- Dynamic type inputs -->
        <div class="space-y-3">
          <template v-for="field in secretFieldsConfig[editForm.secret_type] || []" :key="field.name">
            <!-- Textarea -->
            <div v-if="field.type === 'textarea'" class="pt-1">
              <FormControl type="textarea" :label="field.label" v-model="editForm[field.name]" :rows="5" :placeholder="field.placeholder" class="w-full text-xs" :class="field.mono ? 'font-mono' : ''" />
            </div>

            <!-- File Attachment Edit Input -->
            <div v-else-if="field.type === 'file'" class="space-y-2 pt-1">
              <label class="block text-xs font-semibold text-ink-gray-5 uppercase tracking-wider">{{ field.label }}</label>

              <!-- List of Attached Files in Edit Mode -->
              <div v-if="editAttachmentList.length > 0" class="space-y-2">
                <div
                  v-for="(fileUrl, fIdx) in editAttachmentList"
                  :key="fileUrl + fIdx"
                  class="p-2.5 rounded-xl border border-outline-gray-1 bg-surface-gray-2 flex items-center justify-between shadow-2xs"
                >
                  <div class="flex items-center gap-3 overflow-hidden min-w-0">
                    <img
                      v-if="isImageUrl(fileUrl)"
                      :src="fileUrl"
                      class="w-10 h-10 object-cover rounded-lg shrink-0 border border-outline-gray-1 bg-surface-base cursor-pointer"
                      @click="openImagePreview(fileUrl)"
                    />
                    <div v-else class="w-10 h-10 rounded-lg bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0 cursor-pointer" @click="openFileUrl(fileUrl)">
                      <FeatherIcon name="file-text" class="w-5 h-5 text-ink-gray-7" />
                    </div>
                    <div class="min-w-0 cursor-pointer" @click="isImageUrl(fileUrl) ? openImagePreview(fileUrl) : openFileUrl(fileUrl)">
                      <p class="text-xs font-semibold text-ink-gray-9 truncate hover:text-ink-blue-link transition-colors">{{ getFileName(fileUrl) }}</p>
                      <p class="text-[11px] text-ink-gray-5 font-mono truncate">{{ fileUrl }}</p>
                    </div>
                  </div>
                  <Button variant="ghost" icon="lucide-x" class="!p-1 h-auto text-ink-gray-4 hover:!text-ink-red-3 hover:!bg-surface-red-2" @click="removeEditAttachment(fIdx)" />
                </div>
              </div>

              <!-- Upload Drag & Drop Trigger -->
              <div
                class="relative border-2 border-dashed border-outline-gray-2 rounded-xl p-4 text-center hover:border-ink-gray-6 transition-colors cursor-pointer bg-surface-gray-1"
                @click="triggerEditFileInput(field.name)"
              >
                <FormControl
                  type="file"
                  :id="'edit_file_input_' + field.name"
                  class="hidden"
                  multiple
                  accept="*/*"
                  @change="handleEditFileUpload($event, field.name)"
                />
                <div class="flex flex-col items-center gap-1">
                  <FeatherIcon name="paperclip" class="w-6 h-6 text-ink-gray-5" />
                  <span class="text-xs font-semibold text-ink-gray-8">
                    {{ uploadingEditFiles ? 'Uploading files...' : (editAttachmentList.length > 0 ? '+ Add More Files' : 'Click or drag files here to upload') }}
                  </span>
                  <span class="text-[10px] text-ink-gray-5">Supports Images, PDFs, Zip, Documents (Select multiple files)</span>
                </div>
              </div>
            </div>

            <!-- Text / Password / URL -->
            <div v-else class="flex items-center justify-between gap-3 text-sm">
              <label class="w-28 shrink-0 text-ink-gray-5 font-normal">{{ field.label }}</label>
              <div class="flex-1 min-w-0 relative">
                <TextInput :type="field.type === 'password' && !editRevealedFields[field.name] ? 'password' : 'text'" v-model="editForm[field.name]" :placeholder="field.placeholder" class="w-full text-sm" :class="[field.mono ? 'font-mono' : '', field.type === 'password' ? 'pr-9' : '']" />
                <Button v-if="field.type === 'password'" variant="ghost" :icon="editRevealedFields[field.name] ? 'lucide-eye-off' : 'lucide-eye'" class="absolute right-1 top-1 !p-1.5 h-auto text-ink-gray-4 hover:text-ink-gray-9 focus:outline-none" @click="toggleField(field.name, true)" />
              </div>
            </div>
          </template>
        </div>

        <!-- Notes input -->
        <div class="pt-2">
          <FormControl type="textarea" label="Notes" v-model="editForm.notes" :rows="3" placeholder="Enter notes..." class="w-full text-sm" />
        </div>

        <!-- Edit Action Buttons -->
        <div class="flex items-center justify-end gap-2 pt-4 border-t border-outline-gray-1">
          <Button variant="outline" size="sm" @click="isEditing = false">Cancel</Button>
          <Button variant="solid" size="sm" @click="handleSave" :loading="updateResource.loading" class="font-semibold shadow-2xs">Save Changes</Button>
        </div>
      </div>

      <!-- READ ONLY VIEW -->
      <div v-else class="space-y-2.5 py-1">
        <!-- Secret Type -->
        <div class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Secret Type</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">{{ secretData.secret_type }}</span>
        </div>

        <!-- Folder -->
        <div class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Folder</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">
            {{ getFolderName(secretData.folder) || '—' }}
          </span>
        </div>

        <!-- Dynamic Fields Array -->
        <template v-for="field in secretFieldsConfig[secretData.secret_type] || []" :key="field.name">
          <!-- File Attachment View Mode -->
          <div v-if="field.type === 'file'" class="pt-3 space-y-3">
            <div class="flex items-center justify-between">
              <span class="block text-xs font-semibold text-ink-gray-5 uppercase tracking-wider">{{ field.label }}</span>
              <span v-if="parseAttachments(secretData[field.name]).length > 0" class="text-xs font-medium text-ink-gray-5">
                {{ parseAttachments(secretData[field.name]).length }} {{ parseAttachments(secretData[field.name]).length === 1 ? 'file' : 'files' }}
              </span>
            </div>

            <div v-if="parseAttachments(secretData[field.name]).length > 0" class="space-y-2 max-h-96 overflow-y-auto pr-1">
              <div
                v-for="(fileUrl, aIdx) in parseAttachments(secretData[field.name])"
                :key="fileUrl + aIdx"
                class="bg-surface-gray-2 border border-outline-gray-1 rounded-xl p-3 flex items-center justify-between gap-3 hover:border-outline-gray-2 transition-colors shadow-2xs"
              >
                <div class="flex items-center gap-3 overflow-hidden min-w-0 cursor-pointer" @click="isImageUrl(fileUrl) && !imageLoadErrorMap[fileUrl] ? openImagePreview(fileUrl) : openFileUrl(fileUrl)">
                  <img
                    v-if="isImageUrl(fileUrl) && !imageLoadErrorMap[fileUrl]"
                    :src="fileUrl"
                    class="w-10 h-10 object-cover rounded-lg shrink-0 border border-outline-gray-1 bg-surface-base hover:opacity-90 transition-opacity"
                    @error="imageLoadErrorMap[fileUrl] = true"
                  />
                  <div v-else class="w-10 h-10 rounded-lg bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0">
                    <FeatherIcon name="file-text" class="w-5 h-5 text-ink-gray-7" />
                  </div>
                  <div class="min-w-0">
                    <p class="text-xs font-semibold text-ink-gray-9 truncate hover:text-ink-blue-link transition-colors">{{ getFileName(fileUrl) }}</p>
                    <p class="text-[11px] text-ink-gray-5 font-mono truncate">{{ fileUrl }}</p>
                  </div>
                </div>

                <div class="flex items-center gap-1.5 shrink-0">
                  <Button
                    v-if="isImageUrl(fileUrl) && !imageLoadErrorMap[fileUrl]"
                    variant="subtle"
                    size="xs"
                    icon="eye"
                    label="Preview"
                    class="font-medium text-xs shadow-2xs"
                    @click="openImagePreview(fileUrl)"
                  />

                  <a
                    v-if="canCopy"
                    :href="fileUrl"
                    target="_blank"
                    download
                    class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-surface-base border border-outline-gray-2 text-ink-gray-8 hover:bg-surface-gray-1 transition-colors shadow-2xs"
                  >
                    <FeatherIcon name="download" class="w-3.5 h-3.5 text-ink-gray-6" /> Download
                  </a>
                </div>
              </div>
            </div>

            <div v-else class="text-xs text-ink-gray-4 italic py-1">No files attached.</div>
          </div>

          <div v-else-if="hasFieldValue(field.name)" :class="field.type === 'textarea' ? 'pt-2' : 'flex items-center justify-between py-1 text-sm'">
            <span v-if="field.type === 'textarea'" class="block text-xs font-semibold text-ink-gray-5 uppercase tracking-wider mb-1.5">{{ field.label }}</span>
            <span v-else class="w-28 shrink-0 text-ink-gray-5 font-normal">{{ field.label }}</span>

            <!-- Textarea Content -->
            <div v-if="field.type === 'textarea'" class="relative bg-surface-gray-2 border border-outline-gray-1 rounded-xl p-3 group shadow-inner">
              <pre class="text-xs font-mono text-ink-gray-8 overflow-x-auto max-h-36 whitespace-pre select-all leading-normal">{{ secretData[field.name] }}</pre>
              <Button v-if="canCopy" variant="ghost" :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'" :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-7'" class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-surface-base border border-outline-gray-1 shadow-2xs text-xs font-medium h-auto !py-1 !px-2 rounded-md" label="Copy" @click="copyFieldData(field.name)" />
            </div>

            <!-- URL Link -->
            <div v-else-if="field.isLink" class="min-w-0 flex-1 flex items-center justify-end gap-1.5 overflow-hidden">
              <a :href="secretData[field.name]" target="_blank" class="min-w-0 font-medium text-ink-blue-link hover:underline truncate inline-flex items-center justify-end gap-1">
                <span class="truncate">{{ secretData[field.name] }}</span>
                <FeatherIcon name="external-link" class="w-3.5 h-3.5 shrink-0 text-ink-blue-link" />
              </a>
              <Button
                v-if="canCopy"
                variant="ghost"
                :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'"
                :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-4 hover:text-ink-gray-9'"
                class="!p-1 h-auto focus:outline-none shrink-0"
                :title="'Copy ' + field.label"
                @click="copyFieldData(field.name)"
              />
            </div>

            <!-- Password/Hidden Field -->
            <div v-else-if="field.type === 'password'" class="min-w-0 flex-1 flex items-center justify-end gap-2">
              <span class="font-mono tracking-wider font-medium text-ink-gray-9 truncate">
                {{ revealedFields[field.name] ? decryptedData?.[field.name] : (field.name === 'card_number' ? '•••• •••• •••• ••••' : (field.name === 'card_cvv' ? '•••' : '••••••••••••')) }}
              </span>
              <div class="flex items-center gap-0.5 shrink-0">
                <Button v-if="field.name === 'totp_secret' && secretData.has_totp" variant="subtle" theme="blue" icon="lucide-clock" class="!p-1.5 h-auto text-ink-blue-5 hover:text-ink-blue-6 focus:outline-none" title="Get TOTP Code" @click="$emit('open-totp')" />
                <Button variant="ghost" :icon="revealedFields[field.name] ? 'lucide-eye-off' : 'lucide-eye'" class="!p-1 h-auto text-ink-gray-4 hover:text-ink-gray-9 focus:outline-none" :title="'Reveal ' + field.label" @click="toggleField(field.name)" />
                <Button v-if="canCopy" variant="ghost" :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'" :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-4 hover:text-ink-gray-9'" class="!p-1 h-auto focus:outline-none" :title="'Copy ' + field.label" @click="copyFieldData(field.name)" />
              </div>
            </div>

            <!-- Standard Text Field -->
            <div v-else class="min-w-0 flex-1 flex items-center justify-end gap-1.5 overflow-hidden">
              <span class="min-w-0 font-medium text-ink-gray-9 truncate" :class="field.mono ? 'font-mono' : ''">
                {{ field.name === 'db_host' ? secretData.db_host + (secretData.db_port ? ':' + secretData.db_port : '') : secretData[field.name] }}
              </span>
              <Button
                v-if="canCopy"
                variant="ghost"
                :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'"
                :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-4 hover:text-ink-gray-9'"
                class="!p-1 h-auto focus:outline-none shrink-0"
                :title="'Copy ' + field.label"
                @click="copyFieldData(field.name)"
              />
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Image Lightbox Modal / Popover Preview -->
    <Dialog v-model="previewModalOpen" :options="{ size: 'xl', title: 'Image Preview' }">
      <template #body-content>
        <div class="flex flex-col items-center gap-4 py-2">
          <div class="relative w-full max-h-[75vh] flex items-center justify-center bg-surface-gray-7 rounded-2xl overflow-hidden p-2">
            <img :src="previewImageUrl" class="max-w-full max-h-[70vh] object-contain rounded-lg" />
          </div>
          <div class="w-full flex items-center justify-between px-1">
            <span class="text-xs font-mono text-ink-gray-7 truncate max-w-xs">{{ getFileName(previewImageUrl) }}</span>
            <div class="flex items-center gap-2">
              <a :href="previewImageUrl" target="_blank" download class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-base border border-outline-gray-2 text-ink-gray-9 hover:bg-surface-gray-1 transition-colors shadow-2xs">
                <FeatherIcon name="download" class="w-4 h-4 text-ink-gray-7" /> Download
              </a>
              <a :href="previewImageUrl" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-base border border-outline-gray-2 text-ink-gray-9 hover:bg-surface-gray-1 transition-colors shadow-2xs">
                <FeatherIcon name="external-link" class="w-4 h-4 text-ink-gray-7" /> Open Original
              </a>
            </div>
          </div>
        </div>
      </template>
    </Dialog>
  </article>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import {
  Button,
  FeatherIcon,
  TextInput,
  FormControl,
  Dialog,
  toast,
  Autocomplete
} from 'frappe-ui'
import { Icon } from 'frappe-ui/icons'

import { useClipboard } from '../composables/clipboard'
import {
  useDecryptSecret,
  useUpdateSecret,
  useFolders
} from '../composables/vault'
import { secretTypeOptions } from '../composables/constants'
import { cleanUrl, parseAttachments, isImageUrl, getFileName } from '../utils/attachments'
import { validateTotpSecret } from '../utils/secretForm'

const props = defineProps({
  name: { type: String, required: true },
  secretData: { type: Object, default: () => ({}) },
  canEdit: { type: Boolean, default: false },
  canCopy: { type: Boolean, default: false },
})

const emit = defineEmits(['open-totp', 'saved'])

const detailsOpen = ref(true)
const isEditing = ref(false)

const decryptResource = useDecryptSecret()
const updateResource = useUpdateSecret()
const folders = useFolders()
const clipboard = useClipboard()

folders.submit()

const folderOptions = computed(() => {
  const opts = [{ label: 'No Folder', value: '', level: 0 }]
  const foldersData = folders.data || []

  const tree = []
  const map = {}
  foldersData.forEach(f => {
    map[f.name] = { ...f, children: [] }
  })

  foldersData.forEach(f => {
    if (f.parent_vault_folder && map[f.parent_vault_folder]) {
      map[f.parent_vault_folder].children.push(map[f.name])
    } else {
      tree.push(map[f.name])
    }
  })

  const traverse = (nodes, level = 0) => {
    for (const node of nodes) {
      if (node.can_write || node.name === props.secretData?.folder) {
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

const selectedFolder = ref(null)

watch(() => editForm.folder, (newFolder) => {
  if (typeof newFolder === 'string') {
    selectedFolder.value = folderOptions.value.find(o => o.value === newFolder) || { label: 'No Folder', value: '', level: 0 }
  }
})

watch(selectedFolder, (newVal) => {
  if (newVal) {
    editForm.folder = newVal.value
  }
})

function getFolderName(folderId) {
  if (!folderId) return ''
  const found = folders.data?.find(f => f.name === folderId)
  return found ? found.folder_name : folderId
}

import { secretFieldsConfig } from '../composables/secretFields'

const copiedField = ref(null)
const revealedFields = ref({})
const editRevealedFields = ref({})

const editForm = reactive({
  title: '',
  secret_type: 'Password',
  folder: '',
  url: '',
  username: '',
  email: '',
  notes: '',
  password: '',
  totp_secret: '',
  api_key: '',
  api_secret: '',
  card_holder: '',
  card_number: '',
  card_expiry: '',
  card_cvv: '',
  db_host: '',
  db_port: '',
  db_name: '',
  db_password: '',
  ssh_private_key: '',
  attachment: '',
})

const decryptedData = computed(() => decryptResource.data?.decrypted)

watch(() => props.name, (n) => {
  if (n) {
    revealedFields.value = {}
    editRevealedFields.value = {}
    isEditing.value = false
  }
})

function hasFieldValue(fieldName) {
  if (!props.secretData) return false
  if (decryptedData.value && decryptedData.value[fieldName] !== undefined) {
    return Boolean(decryptedData.value[fieldName])
  }
  const hasKey = 'has_' + fieldName.replace('totp_secret', 'totp')
  if (props.secretData[hasKey] !== undefined) {
    return Boolean(props.secretData[hasKey])
  }
  return Boolean(props.secretData[fieldName])
}

function copyField(value, fieldName) {
  if (!value) return
  clipboard.copy(value)
  copiedField.value = fieldName
  setTimeout(() => {
    if (copiedField.value === fieldName) {
      copiedField.value = null
    }
  }, 3000)
}

async function ensureDecrypted(actionCallback) {
  try {
    if (!decryptedData.value) {
      await decryptResource.submit({ name: props.name })
    }
    if (actionCallback) {
      await actionCallback()
    }
  } catch (err) {
    const errMsg = err.messages?.[0] || err.message || 'Failed to decrypt secret'
    toast.error(errMsg)
  }
}

async function toggleField(fieldName, isEdit = false) {
  if (isEdit) {
    editRevealedFields.value[fieldName] = !editRevealedFields.value[fieldName]
    return
  }
  if (revealedFields.value[fieldName]) {
    revealedFields.value[fieldName] = false
    return
  }
  await ensureDecrypted(() => {
    revealedFields.value[fieldName] = true
  })
}

async function copyFieldData(fieldName) {
  let val = decryptedData.value?.[fieldName] || props.secretData?.[fieldName]
  if (!val && fieldName === 'db_host' && props.secretData?.db_host) {
    val = props.secretData.db_host + (props.secretData.db_port ? ':' + props.secretData.db_port : '')
  }
  if (val) {
    copyField(val, fieldName)
  } else {
    await ensureDecrypted(() => {
      if (decryptedData.value?.[fieldName]) {
        copyField(decryptedData.value[fieldName], fieldName)
      } else {
        toast.error('Field is empty')
      }
    })
  }
}

async function toggleEditMode() {
  if (isEditing.value) {
    isEditing.value = false
    return
  }

  await ensureDecrypted(() => {
    editRevealedFields.value = {}

    const sd = props.secretData || {}
    const dd = decryptedData.value || {}

    editForm.title = sd.title || ''
    editForm.secret_type = sd.secret_type || 'Password'
    editForm.folder = sd.folder || ''
    selectedFolder.value = folderOptions.value.find(o => o.value === editForm.folder) || { label: 'No Folder', value: '', level: 0 }
    editForm.url = sd.url || ''
    editForm.username = sd.username || ''
    editForm.email = sd.email || ''
    editForm.notes = sd.notes || ''

    editForm.password = dd.password || ''
    editForm.totp_secret = dd.totp_secret || ''
    editForm.api_key = sd.api_key || ''
    editForm.api_secret = dd.api_secret || ''
    editForm.card_holder = sd.card_holder || ''
    editForm.card_number = dd.card_number || ''
    editForm.card_expiry = sd.card_expiry || ''
    editForm.card_cvv = dd.card_cvv || ''
    editForm.db_host = sd.db_host || ''
    editForm.db_port = sd.db_port || ''
    editForm.db_name = sd.db_name || ''
    editForm.db_password = dd.db_password || ''
    editForm.ssh_private_key = sd.ssh_private_key || ''

    editAttachmentList.value = parseAttachments(sd.attachment)
    syncEditAttachmentForm()

    isEditing.value = true
  })
}

const editAttachmentList = ref([])
const uploadingEditFiles = ref(false)
const previewModalOpen = ref(false)
const previewImageUrl = ref('')
const imageLoadErrorMap = reactive({})

function openImagePreview(url) {
  previewImageUrl.value = cleanUrl(url)
  previewModalOpen.value = true
}

function openFileUrl(url) {
  const cleaned = cleanUrl(url)
  if (cleaned) window.open(cleaned, '_blank')
}

function removeEditAttachment(index) {
  editAttachmentList.value.splice(index, 1)
  syncEditAttachmentForm()
}

function syncEditAttachmentForm() {
  if (editAttachmentList.value.length === 0) {
    editForm.attachment = ''
  } else if (editAttachmentList.value.length === 1) {
    editForm.attachment = editAttachmentList.value[0]
  } else {
    editForm.attachment = JSON.stringify(editAttachmentList.value)
  }
}

function triggerEditFileInput(fieldname) {
  const el = document.getElementById('edit_file_input_' + fieldname)
  if (el) {
    if (el.tagName === 'INPUT') el.click()
    else {
      const input = el.querySelector('input[type="file"]')
      if (input) input.click()
    }
  }
}

async function handleEditFileUpload(event, fieldname) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  uploadingEditFiles.value = true
  try {
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('is_private', 1)
      formData.append('doctype', 'Vault Secret')
      if (props.name) {
        formData.append('docname', props.name)
      }

      const response = await fetch('/api/method/frappe_vault.api.secrets.upload_file', {
        method: 'POST',
        headers: {
          'X-Frappe-CSRF-Token': window.csrf_token || ''
        },
        body: formData
      })
      const data = await response.json()
      if (data.message && data.message.file_url) {
        editAttachmentList.value.push(data.message.file_url)
      }
    }
    syncEditAttachmentForm()
  } catch (err) {
    toast.error(err.message || 'File upload failed')
  } finally {
    uploadingEditFiles.value = false
  }
}

async function handleSave() {
  if (!editForm.title || !editForm.title.trim()) {
    toast.error('Please enter a secret title')
    return
  }

  if (editForm.totp_secret && ['Password', 'API Key'].includes(editForm.secret_type)) {
    const validation = validateTotpSecret(editForm.totp_secret)
    if (!validation.ok) {
      toast.error(validation.message)
      return
    }
  }

  try {
    const payload = {
      title: editForm.title,
      secret_type: editForm.secret_type,
      folder: editForm.folder,
      notes: editForm.notes,
      url: editForm.url,
    }

    if (editForm.secret_type === 'Password') {
      payload.username = editForm.username
      payload.password = editForm.password
      payload.totp_secret = editForm.totp_secret
      payload.url = editForm.url
    } else if (editForm.secret_type === 'API Key') {
      payload.api_key = editForm.api_key
      payload.api_secret = editForm.api_secret
      payload.totp_secret = editForm.totp_secret
      payload.url = editForm.url
    } else if (editForm.secret_type === 'Credit Card') {
      payload.card_holder = editForm.card_holder
      payload.card_number = editForm.card_number
      payload.card_expiry = editForm.card_expiry
      payload.card_cvv = editForm.card_cvv
    } else if (editForm.secret_type === 'Database') {
      payload.db_host = editForm.db_host
      payload.db_port = editForm.db_port
      payload.db_name = editForm.db_name
      payload.username = editForm.username
      payload.db_password = editForm.db_password
    } else if (editForm.secret_type === 'SSH Key') {
      payload.username = editForm.username
      payload.ssh_private_key = editForm.ssh_private_key
    } else if (editForm.secret_type === 'Media') {
      syncEditAttachmentForm()
      payload.attachment = editForm.attachment
    }

    await updateResource.submit({
      name: props.name,
      ...payload,
    })

    isEditing.value = false
    decryptResource.submit({ name: props.name })
    window.dispatchEvent(new CustomEvent('vault-secret-updated', { detail: { name: props.name } }))
    emit('saved')
  } catch (err) {
    if (err.messages?.length) {
      err.messages.forEach(msg => toast.error(msg))
    } else {
      toast.error(err.message || 'Failed to save changes')
    }
  }
}

defineExpose({ toggleEditMode, isEditing })
</script>
