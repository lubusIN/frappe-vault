<template>
  <div class="flex flex-col h-full p-4 rounded-r-lg">
    <!-- List View -->
    <template v-if="currentView === 'list'">
      <div class="flex items-center justify-between px-4 py-3">
        <div>
          <h2 class="text-xl font-semibold text-ink-gray-9 mb-1">Email Templates</h2>
          <p class="text-sm text-ink-gray-5">Manage your email templates for outgoing emails.</p>
        </div>
        <Button
          variant="solid"
          icon-left="lucide-plus"
          label="New"
          @click="addTemplate"
        />
      </div>

      <div class="flex-1 overflow-y-auto px-4 mt-6">
        <!-- Empty State -->
        <div
          v-if="!templates.loading && (!templates.data || templates.data.length === 0)"
          class="flex flex-col items-center justify-center h-full text-center"
        >
          <div class="flex flex-col items-center justify-center py-20">
            <FeatherIcon name="mail" class="w-12 h-12 text-ink-gray-4 mb-4" />
            <h3 class="text-lg font-medium text-ink-gray-9 mb-1">No Email Templates Found</h3>
            <p class="text-sm text-ink-gray-5 mb-4">Add one to get started.</p>
          </div>
        </div>

        <!-- Templates List -->
        <div v-else-if="templates.data && templates.data.length > 0" class="flex flex-col gap-4">
          <div
            v-for="template in templates.data"
            :key="template.name"
            class="flex items-center justify-between p-4 border border-outline-gray-2 rounded-lg hover:bg-surface-gray-2 transition-colors cursor-pointer"
            @click="editTemplate(template.name)"
          >
            <div class="flex items-center gap-3">
              <div class="flex items-center justify-center w-10 h-10 rounded-full bg-surface-gray-3">
                <span class="lucide-layout-template w-5 h-5 text-ink-gray-6" />
              </div>
              <div class="flex flex-col">
                <span class="text-sm font-medium text-ink-gray-9">{{ template.name }}</span>
                <span class="text-xs text-ink-gray-5">{{ template.subject }}</span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Badge v-if="template.vault_enabled" theme="green">Enabled</Badge>
              <Badge v-else theme="gray">Disabled</Badge>
              <Badge v-if="template.vault_is_default" theme="blue">Default</Badge>
              <div @click.stop>
                <Dropdown
                  :options="[
                    {
                      label: 'Remove',
                      icon: 'lucide-trash-2',
                      onClick: () => deleteTemplate(template.name)
                    }
                  ]"
                  :button="{
                    icon: 'more-horizontal',
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
      <EmailTemplateForm
        :templateId="selectedTemplateId"
        @back="currentView = 'list'"
        @saved="onTemplateSaved"
      />
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, FeatherIcon, Badge, Dropdown, createListResource, call, toast } from 'frappe-ui'
import EmailTemplateForm from './EmailTemplateForm.vue'

// list | form
const currentView = ref('list')
const selectedTemplateId = ref(null)

const templates = createListResource({
  doctype: 'Email Template',
  fields: ['name', 'subject', 'vault_enabled', 'vault_is_default'],
  limit: 100,
  auto: true
})

function addTemplate() {
  selectedTemplateId.value = null
  currentView.value = 'form'
}

function editTemplate(id) {
  selectedTemplateId.value = id
  currentView.value = 'form'
}

function onTemplateSaved() {
  currentView.value = 'list'
  templates.reload()
}

async function deleteTemplate(id) {
  const confirmed = await new Promise(resolve => {
    if (window.frappe?.ui?.confirm) {
      window.frappe.ui.confirm(
        'Are you sure you want to remove this email template?',
        () => resolve(true),
        () => resolve(false)
      )
    } else {
      resolve(window.confirm('Are you sure you want to remove this email template?'))
    }
  })
  if (!confirmed) return

  try {
    await call('frappe.client.delete', { doctype: 'Email Template', name: id })
    toast.success('Template removed successfully!')
    templates.reload()
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to remove template.')
  }
}
</script>
