<template>
  <Dialog
    v-model="isOpen"
    :size="'5xl'"
    @close="activeSettingsPage = ''"
  >
    <template #body>
      <div class="flex h-[calc(100vh_-_8rem)] bg-surface-gray-1">
        <div class="flex flex-col m-1 rounded-l-lg w-56 shrink-0 bg-surface-gray-1 overflow-y-auto">
          <template v-for="(tab, i) in tabs" :key="tab.label">
            <div v-if="i !== 0" class="mx-1 mb-0.5 mt-[5px]" />
            <div class="h-7.5 px-2 py-[7px] my-[3px] flex gap-1.5 text-xs-medium text-ink-gray-5 sticky top-0 z-10 bg-surface-gray-1">
              <span>{{ tab.label }}</span>
            </div>
            <nav class="space-y-[3px] px-1">
              <SidebarItem
                v-for="item in tab.items"
                :key="item.label"
                :label="item.label"
                :active="activeTab?.label === item.label"
                class="w-full cursor-pointer"
                :class="activeTab?.label !== item.label && 'hover:!bg-surface-gray-3'"
                @click="activeTab = item"
              >
                <template #prefix>
                  <component :is="item.icon" class="size-4 text-ink-gray-7" v-if="typeof item.icon === 'object'" />
                  <span v-else-if="typeof item.icon === 'string' && item.icon.startsWith('lucide-')" :class="[item.icon, 'size-4 text-ink-gray-7']" />
                  <FeatherIcon v-else :name="item.icon" class="size-4 text-ink-gray-7" />
                </template>
              </SidebarItem>
            </nav>
          </template>
        </div>
        <div class="flex flex-col flex-1 overflow-y-auto bg-surface-elevation-2 rounded-r-lg">
          <component :is="activeTab.component" v-if="activeTab" @navigateTo="(tabLabel) => openTab(tabLabel)" />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, markRaw } from 'vue'
import { Dialog, SidebarItem, FeatherIcon } from 'frappe-ui'
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
        label: 'Preferences',
        icon: 'lucide-sliders',
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

function openTab(tabLabel) {
  for (const section of tabs.value) {
    const tab = section.items.find(item => item.label === tabLabel)
    if (tab) {
      activeTab.value = tab
      return
    }
  }
}

const activeTab = ref(tabs.value[0].items[0])
</script>
