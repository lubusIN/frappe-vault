<template>
  <div class="flex flex-col h-full bg-surface-elevation-2 rounded-r-lg">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-outline-gray-2">
      <div class="flex items-center gap-3">
        <Button
          variant="ghost"
          icon="lucide-arrow-left"
          @click="$emit('back')"
        />
        <h2 class="text-xl font-semibold text-ink-gray-9">
          {{ templateId ? 'Edit Template' : 'New Template' }}
        </h2>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <span class="text-sm text-ink-gray-7">Enabled</span>
          <Switch v-model="template.doc.vault_enabled" />
        </div>
        <Button
          variant="solid"
          label="Save"
          :loading="isSaving"
          @click="saveTemplate"
        />
      </div>
    </div>

    <!-- Form Content -->
    <div class="flex-1 overflow-y-auto px-6 py-6">
      <div class="max-w-3xl flex flex-col gap-8">
        
        <!-- Basic Info -->
        <div class="flex flex-col gap-5">
          <div class="flex gap-4">
            <div class="flex-1">
              <label class="block text-sm font-medium text-ink-gray-7 mb-1">Name *</label>
              <TextInput
                v-model="template.doc.name"
                :disabled="!!templateId"
                placeholder="e.g. Payment Reminder"
                :class="{ 'border-red-500': showValidations && !template.doc.name }"
              />
              <p v-if="showValidations && !template.doc.name" class="text-xs text-red-500 mt-1">Name is required</p>
            </div>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-ink-gray-7 mb-1">Subject *</label>
            <TextInput
              v-model="template.doc.subject"
              placeholder="e.g. You have been invited to join {{ title }}"
              :class="{ 'border-red-500': showValidations && !template.doc.subject }"
            />
            <p v-if="showValidations && !template.doc.subject" class="text-xs text-red-500 mt-1">Subject is required</p>
          </div>
        </div>
        
        <!-- Options -->
        <div class="flex items-center gap-2 mt-2">
          <Checkbox v-model="template.doc.vault_is_default" />
          <span class="text-sm text-ink-gray-7">Set as default template for Vault Invitations</span>
        </div>

        <!-- Content Settings -->
        <div class="flex flex-col gap-4">
          <div>
            <label class="block text-sm font-medium text-ink-gray-7 mb-1">Content Type</label>
            <Select
              v-model="contentType"
              :options="[
                { label: 'Rich Text', value: 'Rich Text' },
                { label: 'HTML', value: 'HTML' }
              ]"
            />
          </div>
          
          <div v-if="contentType === 'Rich Text'">
            <label class="block text-sm font-medium text-ink-gray-7 mb-1">Content *</label>
            <TextEditor
              :content="template.doc.response"
              @change="val => template.doc.response = val"
              :fixedMenu="true"
            />
          </div>
          <div v-else>
            <label class="block text-sm font-medium text-ink-gray-7 mb-1">HTML Content *</label>
            <textarea
              v-model="template.doc.response_html"
              class="w-full min-h-[300px] p-3 text-sm font-mono border rounded-lg border-outline-gray-2 focus:border-outline-gray-4 focus:ring-0 outline-none"
              placeholder="Enter HTML here..."
            ></textarea>
          </div>
        </div>
        
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { Button, TextInput, Select, TextEditor, Checkbox, Switch, createResource, toast } from 'frappe-ui'

const props = defineProps({
  templateId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['back', 'saved'])

const isSaving = ref(false)
const showValidations = ref(false)

const contentType = ref('Rich Text')

const template = reactive({
  doc: {
    doctype: 'Email Template',
    name: '',
    subject: '',
    response: '',
    response_html: '',
    use_html: 0,
    vault_enabled: 1,
    vault_is_default: 0
  }
})

onMounted(async () => {
  if (props.templateId) {
    const docRes = createResource({
      url: 'frappe.client.get',
      makeParams() {
        return {
          doctype: 'Email Template',
          name: props.templateId
        }
      }
    })
    const doc = await docRes.fetch()
    Object.assign(template.doc, doc)
    
    // Set boolean equivalents for UI components
    template.doc.vault_enabled = !!template.doc.vault_enabled
    template.doc.vault_is_default = !!template.doc.vault_is_default
    contentType.value = template.doc.use_html ? 'HTML' : 'Rich Text'
  }
})

watch(contentType, (newVal) => {
  template.doc.use_html = newVal === 'HTML' ? 1 : 0
})

async function saveTemplate() {
  showValidations.value = true
  
  if (!template.doc.name || !template.doc.subject) {
    toast.error('Please fill in all required fields.')
    return
  }

  isSaving.value = true
  try {
    const docToSave = {
      ...template.doc,
      vault_enabled: template.doc.vault_enabled ? 1 : 0,
      vault_is_default: template.doc.vault_is_default ? 1 : 0
    }

    const saveRes = createResource({
      url: props.templateId ? 'frappe.client.save' : 'frappe.client.insert',
      makeParams() {
        return {
          doc: JSON.stringify(docToSave)
        }
      }
    })
    await saveRes.fetch()
    toast.success(`Template ${props.templateId ? 'updated' : 'created'} successfully!`)
    emit('saved')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to save template.')
  } finally {
    isSaving.value = false
  }
}
</script>
