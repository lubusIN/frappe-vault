<template>
  <SettingsDialog
    v-model:open="isOpen"
    v-model:tab="activeTabLabel"
    size="5xl"
    class="relative"
    @close="activeSettingsPage = ''"
  >
    <SettingsSidebar>
      <!-- Mobile Close Bar -->
      <div class="flex items-center justify-between px-2 pt-1 pb-1 sm:hidden border-b border-outline-gray-1 mb-1">
        <span class="font-semibold text-sm text-ink-gray-9">Settings</span>
        <Button variant="ghost" class="size-7 !p-1 text-ink-gray-6 hover:text-ink-gray-9" @click="isOpen = false">
          <span class="lucide-x size-4" aria-hidden="true" />
        </Button>
      </div>

      <SettingsNavGroup
        v-for="group in tabs"
        :key="group.label"
        :label="group.label"
      >
        <SettingsNavItem
          v-for="item in group.items"
          :key="item.label"
          :value="item.label"
          class="cursor-pointer"
        >
          <template #prefix>
            <component :is="item.icon" class="size-4 text-ink-gray-7" v-if="typeof item.icon === 'object'" />
            <span v-else-if="typeof item.icon === 'string'" :class="[item.icon.startsWith('lucide-') ? item.icon : 'lucide-' + item.icon, 'size-4 text-ink-gray-7']" aria-hidden="true" />
          </template>
          {{ item.label }}
        </SettingsNavItem>
      </SettingsNavGroup>
    </SettingsSidebar>

    <SettingsContent class="relative min-w-0">
      <!-- Close button on desktop -->
      <div class="hidden sm:block absolute top-3 right-3 z-30">
        <Button
          variant="ghost"
          class="size-7 !p-1 text-ink-gray-6 hover:text-ink-gray-9 hover:bg-surface-gray-3 rounded-md transition-colors"
          @click="isOpen = false"
        >
          <span class="lucide-x size-4" aria-hidden="true" />
        </Button>
      </div>

      <SettingsPanel
        v-for="item in allItems"
        :key="item.label"
        :value="item.label"
        class="overflow-y-auto bg-surface-elevation-2 rounded-b-lg sm:rounded-b-none sm:rounded-r-lg w-full"
      >
        <component
          :is="item.component"
          @navigateTo="(tabLabel) => openTab(tabLabel)"
        />
      </SettingsPanel>
    </SettingsContent>
  </SettingsDialog>
</template>

<script setup>
import { computed, ref, markRaw, watch } from 'vue'
import {
  SettingsDialog,
  SettingsSidebar,
  SettingsNavGroup,
  SettingsNavItem,
  SettingsContent,
  SettingsPanel,
  Button,
} from 'frappe-ui'
import ProfileSettings from './Settings/Profile/ProfileSettings.vue'
import PreferencesSettings from './Settings/Preferences/PreferencesSettings.vue'
import EmailAccountList from './Settings/Email/EmailAccountList.vue'
import EmailTemplateList from './Settings/Email/EmailTemplateList.vue'
import UsersSettings from './Settings/Users.vue'
import InviteUsers from './Settings/InviteUsers.vue'

// Tracks which page was open before the modal closes (used by @close handler)
const activeSettingsPage = ref('')

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

const activeTabLabel = ref('Profile')

const tabs = computed(() => {
  const allTabs = [
    {
      label: 'User Configuration',
      items: [
        {
          label: 'Profile',
          icon: 'lucide-user',
          component: markRaw(ProfileSettings),
        },
        {
          label: 'Appearance',
          icon: 'lucide-palette',
          component: markRaw(PreferencesSettings),
        }
      ]
    },
    {
      label: 'User Management',
      items: [
        {
          label: 'Users',
          icon: 'lucide-users',
          component: markRaw(UsersSettings),
        },
        {
          label: 'Invite User',
          icon: 'lucide-user-plus',
          component: markRaw(InviteUsers),
        }
      ]
    },
    {
      label: 'Email',
      items: [
        {
          label: 'Accounts',
          icon: 'lucide-mail',
          component: markRaw(EmailAccountList),
        },
        {
          label: 'Templates',
          icon: 'lucide-layout-template',
          component: markRaw(EmailTemplateList),
        }
      ]
    }
  ]

  const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name || ''
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  const isAdmin = user === 'Administrator' || roles.includes('Vault Admin')

  if (!isAdmin) {
    return allTabs.filter(tab => tab.label === 'User Configuration')
  }

  return allTabs
})

const allItems = computed(() => {
  return tabs.value.flatMap(group => group.items)
})

watch(tabs, (newTabs) => {
  const exists = newTabs.some(g => g.items.some(i => i.label === activeTabLabel.value))
  if (!exists) {
    activeTabLabel.value = newTabs[0]?.items[0]?.label || 'Profile'
  }
}, { immediate: true })

function openTab(tabLabel) {
  for (const group of tabs.value) {
    const item = group.items.find(i =>
      i.label === tabLabel ||
      i.label.toLowerCase() === tabLabel.toLowerCase() ||
      tabLabel.toLowerCase().includes(i.label.toLowerCase()) ||
      i.label.toLowerCase().includes(tabLabel.toLowerCase())
    )
    if (item) {
      activeTabLabel.value = item.label
      return
    }
  }
}
</script>
