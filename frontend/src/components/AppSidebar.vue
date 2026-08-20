<template>
  <Sidebar
    v-model:collapsed="sidebarCollapsedComputed"
    :disable-collapse="isMobile"
    class="select-none vault-sidebar"
  >
      <div class="flex h-full flex-col p-2">
        <!-- Header -->
        <SidebarHeader
          v-if="sidebarConfig.header"
          :title="sidebarConfig.header.title"
          :subtitle="sidebarConfig.header.subtitle"
          :logo="sidebarConfig.header.logo"
          :menu-items="sidebarConfig.header.menuItems"
        />

        <div class="flex-1 overflow-y-auto overflow-x-hidden">
          <!-- Main Links Section -->
          <nav class="flex flex-col gap-0.5 mt-2">
            <SidebarItem
              v-for="item in sidebarConfig.sections[0].items"
              :key="item.label"
              :id="item.id"
              :label="item.label"
              :icon="item.icon"
              :to="item.to"
              :onClick="item.onClick"
              :isActive="item.isActive"
              class="vault-sidebar-item cursor-pointer"
              :class="{ 'notifications-btn-trigger': item.isNotification }"
            >
              <template v-if="item.count" #suffix>
                <Badge :label="String(item.count)" variant="subtle" :theme="item.isNotification && item.count > 0 ? 'red' : 'gray'" />
              </template>
            </SidebarItem>
          </nav>

          <!-- Section Divider -->
          <div class="my-2 mx-1 border-t border-outline-gray-1 opacity-60" />

          <!-- Folders Section -->
          <div class="flex flex-col gap-0.5">
            <div
              class="flex items-center select-none px-2 py-1 mb-0.5"
              :class="isSidebarCollapsed ? 'justify-center' : 'justify-between'"
            >
              <span
                v-if="!isSidebarCollapsed"
                class="text-xs font-semibold text-ink-gray-4 tracking-wider uppercase truncate vault-sidebar-section-label"
              >
                Folders
              </span>
              <Tooltip text="New Folder" placement="right">
                <Button
                  variant="ghost"
                  icon="plus"
                  class="size-7 !p-1 text-ink-gray-6 hover:text-ink-gray-9 hover:bg-surface-gray-3 shrink-0 rounded-lg transition-colors"
                  @click.prevent.stop="openCreateFolderDialog"
                />
              </Tooltip>
            </div>

          <SidebarItem
            v-for="folder in folders"
            :key="folder.name"
            :label="folder.folder_name"
            :to="`/secrets?folder=${encodeURIComponent(folder.name)}`"
            :isActive="checkActive(`/secrets?folder=${encodeURIComponent(folder.name)}`)"
            class="group vault-sidebar-item"
          >
            <template #prefix>
              <div class="flex items-center justify-center w-4 h-4">
                <Icon
                  :name="folder.icon || 'folder'"
                  class="w-4 h-4 shrink-0"
                />
              </div>
            </template>
            <template #suffix>
              <div v-if="getFolderOptions(folder).length > 0" class="opacity-0 group-hover:opacity-100 transition-opacity duration-150" @click.prevent.stop>
                <Dropdown :options="getFolderOptions(folder)">
                  <template #default="{ open }">
                    <Button
                      variant="ghost"
                      icon="lucide-more-horizontal"
                      class="!p-0.5 h-auto text-ink-gray-6"
                      :class="{ 'bg-surface-gray-3': open }"
                    />
                  </template>
                </Dropdown>
              </div>
            </template>
          </SidebarItem>
        </div>
      </div>

      <div class="mt-auto">
        <SidebarItem
          v-if="isVaultAdmin && stats.data?.has_demo_data"
          label="Clear Demo Data"
          :icon="{ render: () => h(BrushCleaningIcon, { class: 'size-4 text-ink-red-5 shrink-0' }) }"
          class="hover:bg-surface-red-2 text-ink-red-6 transition-colors cursor-pointer font-medium"
          @click="showClearDemoConfirm = true"
        >
          <template #icon>
            <BrushCleaningIcon class="size-4 text-ink-red-5 shrink-0" />
          </template>
        </SidebarItem>
        <SidebarItem
          v-else-if="isVaultAdmin && stats.data?.total_secrets === 0 && !generateDemo.loading"
          label="Load Demo Data"
          :icon="{ render: () => h(SparklesIcon, { class: 'size-4 text-ink-blue-5 shrink-0' }) }"
          class="hover:bg-surface-blue-2 text-ink-blue-3 transition-colors cursor-pointer font-medium"
          @click="handleGenerateDemo"
        >
          <template #icon>
            <SparklesIcon class="size-4 text-ink-blue-5 shrink-0" />
          </template>
        </SidebarItem>
        <SidebarCollapseToggle v-if="!isMobile" />
      </div>
    </div>

      <!-- Clear Demo Data Confirmation Dialog -->
      <Dialog
        v-model="showClearDemoConfirm"
        :options="{ title: 'Clear Demo Data', size: 'sm' }"
      >
        <template #body-content>
          <p class="text-sm text-ink-gray-7 leading-relaxed">
            Are you sure you want to remove all demo folders and secrets? Any changes made to demo secrets will be lost.
          </p>
        </template>
        <template #actions>
          <div class="flex justify-end gap-2">
            <Button variant="ghost" label="Cancel" @click="showClearDemoConfirm = false" />
            <Button
              variant="solid"
              theme="red"
              label="Clear Demo Data"
              :loading="clearDemo.loading"
              @click="handleClearDemo"
            />
          </div>
        </template>
      </Dialog>

      <!-- Dialogs (rendered inside #footer-items slot since Sidebar has no default slot) -->
      <!-- About Dialog -->
      <Dialog
        v-model="showAboutModal"
        size="sm"
        bare
      >
        <template #default="{ close }">
          <div class="bg-surface-elevation-1 rounded-2xl p-6 shadow-xl border border-outline-gray-1 text-ink-gray-9">
            <!-- App Logo and Title -->
            <div class="flex flex-col items-center justify-center pb-2">
              <img :src="sidebarConfig.header.logo" class="size-12 object-contain rounded-xl shadow-2xs" />
              <div class="mt-3 flex items-center gap-2">
                <h3 class="text-lg font-semibold text-ink-gray-9">Frappe Vault</h3>
                <span class="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full bg-surface-gray-3 border border-outline-gray-1 text-ink-gray-6">
                  v{{ vaultVersion }}
                </span>
              </div>
            </div>

            <!-- Top Divider -->
            <div class="border-t border-outline-gray-1 my-2" />

            <!-- Links List -->
            <div class="flex flex-col py-1 space-y-0.5">
              <a
                v-for="link in aboutLinks"
                :key="link.label"
                :href="link.href"
                target="_blank"
                class="flex items-center justify-between p-2 rounded-sm text-sm text-ink-gray-8 hover:bg-surface-gray-2 transition-colors"
              >
                <div class="flex items-center gap-3">
                  <component :is="link.icon" class="size-4 text-ink-gray-6 shrink-0" />
                  <span class="font-medium">{{ link.label }}</span>
                </div>
                <ArrowRightIcon class="size-4 text-ink-gray-6 shrink-0" />
              </a>
            </div>

            <!-- Bottom Divider -->
            <div class="border-t border-outline-gray-1 my-2" />

            <!-- Footer -->
            <div class="text-center text-xs pt-1">
              <a href="https://lubus.in/" target="_blank" class="font-medium text-ink-gray-5 hover:text-ink-gray-9 hover:underline transition-colors">
                \ Made by Lubus /
              </a>
            </div>
          </div>
        </template>
      </Dialog>

      <!-- Create Folder Dialog -->
      <Dialog
        v-model="showCreateFolderDialog"
        :options="{ title: 'New Folder', size: 'sm' }"
      >
        <template #body-content>
          <div class="space-y-4">
            <FormControl
              label="Folder Name"
              v-model="newFolderName"
              placeholder="e.g. Work, Personal"
              @keyup.enter="handleCreateFolder"
            />
            <div>
              <label class="block text-xs text-ink-gray-5 mb-1.5 font-medium">Folder Icon</label>
              <IconPicker v-model="newFolderIcon" placeholder="Search icons..." class="w-full" />
            </div>
          </div>
        </template>
        <template #actions>
          <div class="flex justify-end gap-2">
            <Button variant="ghost" label="Cancel" @click="showCreateFolderDialog = false" />
            <Button
              variant="solid"
              label="Create"
              :loading="createFolderResource.loading"
              :disabled="!newFolderName.trim()"
              @click="handleCreateFolder"
            />
          </div>
        </template>
      </Dialog>

      <!-- Edit Folder Dialog -->
      <Dialog
        v-model="showEditFolderDialog"
        :options="{ title: 'Edit Folder', size: 'sm' }"
      >
        <template #body-content>
          <div class="space-y-4">
            <FormControl
              label="Folder Name"
              v-model="editFolderName"
              placeholder="e.g. Work, Personal"
              @keyup.enter="handleEditFolder"
            />
            <div>
              <label class="block text-xs text-ink-gray-5 mb-1.5 font-medium">Folder Icon</label>
              <IconPicker v-model="editFolderIcon" placeholder="Search icons..." class="w-full" />
            </div>
          </div>
        </template>
        <template #actions>
          <div class="flex justify-end gap-2">
            <Button variant="ghost" label="Cancel" @click="showEditFolderDialog = false" />
            <Button
              variant="solid"
              label="Save"
              :loading="updateFolderResource.loading"
              :disabled="!editFolderName.trim()"
              @click="handleEditFolder"
            />
          </div>
        </template>
      </Dialog>

      <!-- Delete Folder Dialog -->
      <Dialog
        v-model="showDeleteFolderDialog"
        :options="{ title: 'Delete Folder', size: 'sm' }"
      >
        <template #body-content>
          <div class="space-y-3">
            <p class="text-sm text-ink-gray-7" v-if="loadingCount">Analyzing folder secrets...</p>
            <template v-else>
              <div class="space-y-3" v-if="deleteSecretsCount > 0">
                <p class="text-sm text-ink-gray-7 leading-relaxed">
                  Folder <span class="font-semibold text-ink-gray-9">"{{ folderToDelete?.folder_name }}"</span> contains <span class="font-bold text-ink-gray-9">{{ deleteSecretsCount }}</span> {{ deleteSecretsCount === 1 ? 'secret' : 'secrets' }}.
                </p>
                <div class="pt-0.5">
                  <Checkbox
                    v-model="deleteSecretsCheck"
                    label="Also delete secrets inside this folder"
                    description="If unchecked, secrets will be moved to All Secrets."
                  />
                </div>
              </div>
              <div class="space-y-2" v-else>
                <p class="text-sm text-ink-gray-7 leading-relaxed">
                  Are you sure you want to delete folder <span class="font-semibold text-ink-gray-9">"{{ folderToDelete?.folder_name }}"</span>?
                </p>
              </div>
              <div v-if="deleteFolderError" class="text-sm text-red-700 dark:text-red-300 bg-surface-red-1/40 p-2.5 rounded-lg border border-outline-red-1 font-medium leading-relaxed">
                {{ deleteFolderError }}
              </div>
            </template>
          </div>
        </template>
        <template #actions>
          <div class="flex justify-end gap-2">
            <Button variant="ghost" label="Cancel" @click="showDeleteFolderDialog = false" />
            <Button
              variant="solid"
              :theme="deleteSecretsCount > 0 && deleteSecretsCheck ? 'red' : 'gray'"
              :label="deleteSecretsCount > 0 && deleteSecretsCheck ? 'Delete Folder & Secrets' : 'Delete Folder'"
              :loading="deleteFolderResource.loading"
              :disabled="loadingCount"
              @click="handleDeleteFolder"
            />
          </div>
        </template>
      </Dialog>

      <!-- Share Folder Dialog -->
      <ShareItemDialog
        v-model="showShareFolderDialog"
        :sharedName="folderToShare?.name"
        :itemTitle="folderToShare?.folder_name"
        sharedDoctype="Vault Folder"
      />

      <!-- Manage Folder Shares Dialog -->
      <ManageFolderSharesDialog
        v-model="showManageFolderSharesDialog"
        :folderName="folderToManageShares?.name"
        :folderTitle="folderToManageShares?.folder_name"
        :isOwnerOrAdmin="isManagingFolderOwnerOrAdmin"
      />

      <!-- Settings Modal -->
      <SettingsModal v-if="showSettingsModal" v-model="showSettingsModal" />
  </Sidebar>
</template>

<script setup>
import { ref, computed, reactive, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, FeatherIcon, Tooltip, Dialog, Dropdown, FormControl, Checkbox, Sidebar, SidebarItem, SidebarHeader, SidebarCollapseToggle, createResource, toast } from 'frappe-ui'
import { IconPicker, Icon } from 'frappe-ui/icons'
import { useVaultStats, useFolders, useCreateFolder, useDeleteFolder, useUpdateFolder, useFolderSecrets, useGenerateDemoData, useClearDemoData, mobileSidebarOpened, isSidebarCollapsed } from '../composables/vault'
import {
  visible,
  notifications,
  unreadNotificationsCount,
  toggleNotificationPanel,
} from '../stores/notifications'
import NotificationsPanel from './NotificationsPanel.vue'
import ShareItemDialog from './ShareItemDialog.vue'
import ManageFolderSharesDialog from './ManageFolderSharesDialog.vue'
import SettingsModal from './SettingsModal.vue'
import LayoutDashboard from '~icons/lucide/layout-dashboard'
import HelpCircleIcon from '~icons/lucide/help-circle'
import HeartIcon from '~icons/lucide/heart'
import BugIcon from '~icons/lucide/bug'
import HeadphonesIcon from '~icons/lucide/headphones'
import ArrowRightIcon from '~icons/lucide/arrow-right'
import BrushCleaningIcon from '~icons/lucide/brush-cleaning'
import SparklesIcon from '~icons/lucide/sparkles'

const props = defineProps({
  isMobile: { type: Boolean, default: false }
})

const route = useRoute()
const router = useRouter()
const stats = useVaultStats()
const foldersResource = useFolders()
// Notifications state is managed by stores/notifications.js (visible, notifications, unreadNotificationsCount, toggleNotificationPanel)
const generateDemo = useGenerateDemoData()
const clearDemo = useClearDemoData()
const showClearDemoConfirm = ref(false)

const isVaultAdmin = computed(() => {
  const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name
  if (user === 'Administrator') return true
  const roles = window.frappe?.boot?.user?.roles || window.frappe?.user?.roles || []
  return roles.includes('Vault Admin') || roles.includes('System Manager')
})

const appsResource = createResource({
  url: 'frappe.apps.get_apps',
  cache: 'apps',
  auto: true,
  transform: (data) => {
    let _apps = [
      {
        label: 'Desk',
        icon: { render: () => h('img', { src: '/assets/frappe/images/framework.png', class: 'size-6 object-contain rounded-xs' }) },
        onClick: () => { window.location.href = '/app' }
      }
    ]
    if (Array.isArray(data)) {
      data.forEach((app) => {
        if (app.name === 'frappe_vault' || app.name === 'frappe') return
        _apps.push({
          label: app.title || app.name,
          icon: { render: () => h('img', { src: app.logo || '/assets/frappe/images/framework.png', class: 'size-6 object-contain rounded-xs' }) },
          onClick: () => { window.location.href = app.route || `/${app.name}` }
        })
      })
    }
    return _apps
  }
})

const createFolderResource = useCreateFolder()
const deleteFolderResource = useDeleteFolder()
const updateFolderResource = useUpdateFolder()
const folderSecretsResource = useFolderSecrets()

const showCreateFolderDialog = ref(false)
const newFolderName = ref('')
const newFolderIcon = ref('')

const showEditFolderDialog = ref(false)
const folderToEdit = ref(null)
const editFolderName = ref('')
const editFolderIcon = ref('')

const showDeleteFolderDialog = ref(false)
const folderToDelete = ref(null)
const deleteSecretsCount = ref(0)
const deleteSecretsCheck = ref(false)
const loadingCount = ref(false)
const deleteFolderError = ref('')

const showShareFolderDialog = ref(false)
const folderToShare = ref(null)

const showManageFolderSharesDialog = ref(false)
const folderToManageShares = ref(null)

function parseFrappeError(error) {
  if (Array.isArray(error?.messages) && error.messages.length) {
    const msg = error.messages[0]
    if (msg && !msg.includes('Traceback')) {
      return msg.replace(/<[^>]*>?/gm, '')
    }
  }
  if (error?.exc) {
    const lines = error.exc.split('\n').map(l => l.trim()).filter(Boolean)
    const last = lines[lines.length - 1]
    if (last) return last.replace(/^frappe\.\w+\.\w+:\s*/, '')
  }
  if (error?.message && !error.message.includes('Traceback')) {
    return error.message
  }
  return 'Failed to delete folder. Please try again.'
}


function openCreateFolderDialog() {
  newFolderName.value = ''
  newFolderIcon.value = ''
  showCreateFolderDialog.value = true
}

async function handleCreateFolder() {
  if (!newFolderName.value.trim()) return
  try {
    await createFolderResource.submit({
      folder_name: newFolderName.value.trim(),
      icon: newFolderIcon.value || 'folder',
    })
    showCreateFolderDialog.value = false
    foldersResource.reload()
    stats.reload()
  } catch (err) {
  }
}

function getFolderOptions(folder) {
  const options = []

  const currentUser = window.frappe?.session?.user || window.frappe?.boot?.user?.name || ''
  const isOwnerOrAdmin = folder.owner === currentUser || isAdmin.value

  if (isOwnerOrAdmin || folder.can_write) {
    options.push({
      label: 'Share',
      icon: 'lucide-share-2',
      onClick: () => {
        folderToShare.value = folder
        showShareFolderDialog.value = true
      }
    })
    options.push({
      label: 'Manage Shares',
      icon: 'lucide-users',
      onClick: () => {
        folderToManageShares.value = folder
        showManageFolderSharesDialog.value = true
      }
    })
  }

  if (folder.can_write) {
    options.push({
      label: 'Edit Folder',
      icon: 'edit-2',
      onClick: () => {
        folderToEdit.value = folder
        editFolderName.value = folder.folder_name
        editFolderIcon.value = folder.icon || ''
        showEditFolderDialog.value = true
      }
    })
    options.push({
      label: 'Delete Folder',
      icon: 'trash-2',
      onClick: () => openDeleteFolderDialog(folder)
    })
  }
  return options
}

function openDeleteFolderDialog(folder) {
  folderToDelete.value = folder
  deleteSecretsCount.value = 0
  deleteSecretsCheck.value = false
  loadingCount.value = true
  deleteFolderError.value = ''
  showDeleteFolderDialog.value = true

  folderSecretsResource.submit({ folder_name: folder.name }).then((res) => {
    deleteSecretsCount.value = res.total || 0
    loadingCount.value = false
  }).catch(() => {
    loadingCount.value = false
  })
}

async function handleEditFolder() {
  if (!editFolderName.value.trim() || !folderToEdit.value) return
  try {
    await updateFolderResource.submit({
      name: folderToEdit.value.name,
      folder_name: editFolderName.value.trim(),
      icon: editFolderIcon.value || 'folder',
    })
    showEditFolderDialog.value = false
    folderToEdit.value = null
    foldersResource.reload()
  } catch (err) {
  }
}

async function handleDeleteFolder() {
  if (!folderToDelete.value) return
  deleteFolderError.value = ''
  try {
    await deleteFolderResource.submit({
      name: folderToDelete.value.name,
      delete_secrets: deleteSecretsCount.value > 0 && deleteSecretsCheck.value ? 1 : 0,
    })

    if (route.query.folder === folderToDelete.value.name || route.name === 'SecretDetail') {
      router.push('/secrets')
    }

    showDeleteFolderDialog.value = false
    folderToDelete.value = null
    foldersResource.reload()
    stats.reload()
  } catch (err) {
    deleteFolderError.value = parseFrappeError(err)
  }
}

async function handleGenerateDemo() {
  try {
    await generateDemo.submit()
    stats.reload()
    foldersResource.reload()
    window.dispatchEvent(new CustomEvent('vault-demo-changed'))
    toast.success('Demo data generated successfully')
    if (route.name === 'SecretDetail') {
      router.push('/')
    }
  } catch (err) {
    toast.error(err.message || 'Failed to generate demo data')
  }
}

async function handleClearDemo() {
  try {
    await clearDemo.submit()
    showClearDemoConfirm.value = false
    stats.reload()
    foldersResource.reload()
    window.dispatchEvent(new CustomEvent('vault-demo-changed'))
    toast.success('Demo data cleared successfully')
    if (route.name === 'SecretDetail') {
      router.push('/')
    }
  } catch (err) {
    toast.error(err.message || 'Failed to clear demo data')
  }
}

// Persist collapsed state in localStorage via shared composable ref
const sidebarCollapsedComputed = computed({
  get: () => props.isMobile ? false : isSidebarCollapsed.value,
  set: (val) => {
    isSidebarCollapsed.value = val
    localStorage.setItem('isSidebarCollapsed', String(val))
  }
})

const showAboutModal = ref(false)
const showSettingsModal = ref(false)

const vaultVersion = computed(() => {
  return window.frappe?.boot?.versions?.frappe_vault || '1.1.0'
})

const aboutLinks = [
  { label: 'GitHub', href: 'https://github.com/lubusIN/frappe-vault', icon: HelpCircleIcon },
  { label: 'Submit Feedback', href: 'https://github.com/lubusIN/frappe-vault/issues', icon: BugIcon },
  { label: 'Buy us a coffee', href: 'https://github.com/sponsors/lubusIN', icon: HeartIcon },
  { label: 'Get in touch', href: 'https://lubus.in/contact-us/', icon: HeadphonesIcon },
]

const folders = computed(() => foldersResource.data || [])

const userName = computed(() => {
  if (window.frappe?.boot?.user) {
    if (typeof window.frappe.boot.user === 'object') {
      return window.frappe.boot.user.full_name || window.frappe.boot.user.name || 'User'
    }
    return window.frappe.boot.user
  }
  if (window.frappe?.session?.user_fullname) return window.frappe.session.user_fullname
  if (window.frappe?.user?.full_name) return window.frappe.user.full_name
  return window.frappe?.session?.user || 'User'
})

const isAdmin = computed(() => {
  if (stats.data?.is_admin) return true
  const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name || ''
  if (user === 'Administrator') return true
  const roles = window.frappe?.user_roles || window.frappe?.boot?.user?.roles || []
  return roles.includes('Vault Admin')
})

const isManagingFolderOwnerOrAdmin = computed(() => {
  if (isAdmin.value) return true
  const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name || ''
  return folderToManageShares.value?.owner === user
})

// Single reactive sidebar config
function checkActive(to) {
  if (!to) return false
  const pathStr = typeof to === 'string' ? to : to.path || ''
  if (!pathStr) return false

  if (pathStr.includes('?')) {
    const [path, queryString] = pathStr.split('?')
    if (route.path !== path) return false

    const urlParams = new URLSearchParams(queryString)
    for (const [key, value] of urlParams.entries()) {
      if (route.query[key] !== value) return false
    }
    return true
  }

  if (pathStr === '/') {
    return route.path === '/'
  }

  if (pathStr === '/secrets') {
    if (route.query.folder || route.query.category) {
      return false
    }
    return route.path === '/secrets' || route.path.startsWith('/secrets/')
  }

  return route.path === pathStr || route.path.startsWith(pathStr + '/')
}

const sidebarConfig = reactive({
  header: computed(() => ({
    title: 'Vault',
    logo: '/assets/frappe_vault/images/vault-icon.svg',
    subtitle: userName.value,
    menuItems: [
      {
        group: '',
        hideLabel: true,
        options: [
          {
            icon: 'lucide-layout-grid',
            label: 'Apps',
            submenu: appsResource.data || [
              {
                label: 'Desk',
                  icon: { render: () => h('img', { src: '/assets/frappe/images/framework.png', class: 'size-4 object-contain rounded-xs' }) },
                onClick: () => { window.location.href = '/app' }
              }
            ]
          },

          {
            icon: 'lucide-settings',
            label: 'Settings',
            onClick: () => { showSettingsModal.value = true }
          },
          {
            icon: 'lucide-info',
            label: 'About',
            onClick: () => { showAboutModal.value = true }
          }
        ]
      },
      {
        group: '',
        hideLabel: true,
        options: [
          {
            icon: 'lucide-log-out',
            label: 'Log out',
            onClick: () => { window.location.href = '/logout' }
          }
        ]
      }
    ],
  })),
  sections: computed(() => [
    {
      label: '',
      items: [
        {
          id: 'notifications-btn',
          label: 'Notifications',
          icon: 'lucide-bell',
          count: unreadNotificationsCount.value,
          isNotification: true,
          onClick: () => {
            toggleNotificationPanel()
            if (props.isMobile) {
              mobileSidebarOpened.value = false
            }
          },
          isActive: visible.value,
        },
        { label: 'Dashboard', icon: LayoutDashboard, to: '/', isActive: checkActive('/') },
        { label: 'Secrets', icon: 'lucide-key-round', to: '/secrets', count: stats.data?.total_secrets, isActive: checkActive('/secrets') },
        { label: 'Bookmarks', icon: 'lucide-bookmark', to: '/bookmarks', count: stats.data?.bookmarks, isActive: checkActive('/bookmarks') },
        {
          label: isAdmin.value ? 'Shares' : 'Shared with Me',
          icon: 'lucide-share-2',
          to: isAdmin.value ? '/shares' : '/shared',
          isActive: checkActive(isAdmin.value ? '/shares' : '/shared'),
        },
      ],
    },
    {
      label: '',
      items: [
        { isHeader: true, label: 'Folders' },
        ...folders.value.map((folder) => {
          const toUrl = `/secrets?folder=${folder.name}`
          return {
            label: folder.folder_name,
            to: toUrl,
            isActive: checkActive(toUrl),
            color: folder.color,
            folder,
          }
        }),
      ],
    },
  ]),
})
</script>
