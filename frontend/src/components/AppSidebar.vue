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

        <div class="flex-1 overflow-y-auto overflow-x-hidden px-2 -mx-2">
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
              :class="[
                { 'notifications-btn-trigger': item.isNotification },
                item.isActive ? '!bg-surface-elevation-3 !text-ink-gray-8 !shadow-sm' : ''
              ]"
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

          <div v-show="!isSidebarCollapsed" class="w-full flex-1"><Tree v-if="folderTree.length" :nodes="folderTree" node-key="name" class="w-full">
            <template #item="{ node, expanded, toggle, hasChildren }">
              <router-link
                :to="`/secrets?folder=${encodeURIComponent(node.name)}`"
                class="flex h-7 min-w-0 flex-1 items-center rounded pl-0.5 pr-1.5 transition-colors focus:outline-none focus-visible:ring-0"
                :class="
                  checkActive(`/secrets?folder=${encodeURIComponent(node.name)}`)
                    ? 'bg-surface-elevation-3 text-ink-gray-8 shadow-sm'
                    : 'text-ink-gray-6 hover:bg-surface-gray-2'
                "
              >
                <!-- Prefix Icon -->
                <Icon
                  :name="node.icon || 'folder'"
                  class="size-4 shrink-0 mr-2 text-ink-gray-5"
                />

                <!-- Label -->
                <span class="truncate text-[13px] flex-1">{{ node.label }}</span>

                <!-- Suffix Actions (Arrow on right!) -->
                <div class="flex items-center gap-0.5 opacity-0 group-hover/row:opacity-100 transition-opacity ml-auto" @click.prevent.stop>
                  <!-- Dropdown for options -->
                  <Dropdown v-if="getFolderOptions(node).length > 0" :options="getFolderOptions(node)">
                    <template #default="{ open }">
                      <Button
                        variant="ghost"
                        icon="lucide-more-horizontal"
                        class="size-5 !p-0.5 text-ink-gray-6"
                        :class="{ 'bg-surface-gray-3': open }"
                      />
                    </template>
                  </Dropdown>
                  <!-- Expand/Collapse toggle -->
                  <Button
                    v-if="hasChildren"
                    variant="ghost"
                    :icon="expanded ? 'chevron-down' : 'chevron-right'"
                    class="size-5 !p-0.5 text-ink-gray-5"
                    @click.prevent.stop="toggle"
                  />
                </div>
              </router-link>
            </template>
          </Tree>
          <div v-else class="px-2 py-1.5 text-xs text-ink-gray-5">
            No folders yet.
          </div></div>

          <div v-show="isSidebarCollapsed" class="flex flex-col gap-0.5 w-full">
            <template v-for="folder in folderTree" :key="folder.name">
              <Popover v-if="folder.children && folder.children.length > 0" trigger="hover" placement="right-start">
                <template #target>
                  <SidebarItem
                    :label="folder.folder_name"
                    :to="`/secrets?folder=${encodeURIComponent(folder.name)}`"
                    :isActive="isFolderOrDescendantActive(folder)"
                    class="vault-sidebar-item cursor-pointer"
                  >
                    <template #prefix>
                      <div class="flex items-center justify-center w-4 h-4 shrink-0">
                        <Icon
                          :name="folder.icon || 'folder'"
                          class="w-4 h-4 shrink-0 text-ink-gray-5"
                        />
                      </div>
                    </template>
                  </SidebarItem>
                </template>
                <template #body>
                  <div class="bg-surface-gray-1 border border-outline-gray-2 shadow-xl rounded-lg py-1.5 w-56 ml-2 z-50">
                    <div class="px-3 py-1.5 text-[11px] font-semibold text-ink-gray-4 uppercase tracking-wider mb-1">
                      {{ folder.folder_name }}
                    </div>
                    <div class="max-h-[300px] overflow-y-auto">
                      <router-link
                        v-for="child in getAllDescendants(folder)"
                        :key="child.name"
                        :to="`/secrets?folder=${encodeURIComponent(child.name)}`"
                        class="flex items-center px-3 py-1.5 text-[13px] hover:bg-surface-gray-2 text-ink-gray-7 hover:text-ink-gray-9 transition-colors cursor-pointer"
                        :class="{ 'font-semibold text-ink-gray-9 bg-surface-gray-2': checkActive(`/secrets?folder=${encodeURIComponent(child.name)}`) }"
                        :style="{ paddingLeft: `${12 + (child.level * 16)}px` }"
                      >
                        <Icon :name="child.icon || 'folder'" class="w-4 h-4 mr-2 text-ink-gray-5 shrink-0" />
                        <span class="truncate">{{ child.folder_name }}</span>
                      </router-link>
                    </div>
                  </div>
                </template>
              </Popover>
              <SidebarItem
                v-else
                :label="folder.folder_name"
                :to="`/secrets?folder=${encodeURIComponent(folder.name)}`"
                :isActive="isFolderOrDescendantActive(folder)"
                class="vault-sidebar-item cursor-pointer"
              >
                <template #prefix>
                  <div class="flex items-center justify-center w-4 h-4 shrink-0">
                    <Icon
                      :name="folder.icon || 'folder'"
                      class="w-4 h-4 shrink-0 text-ink-gray-5"
                    />
                  </div>
                </template>
              </SidebarItem>
            </template>
          </div>
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
              <label class="block text-xs text-ink-gray-5 mb-1.5 font-medium">Parent Folder (Optional)</label>
              <Autocomplete
                v-model="newFolderParent"
                :options="folderOptions"
                placeholder="Select parent folder..."
                :disabled="isSubfolderMode"
              >
                <template #item-prefix="{ option }">
                  <div :style="{ paddingLeft: (option.level * 1.5) + 'rem' }" class="flex items-center">
                    <Icon name="corner-down-right" class="w-4 h-4 mr-2 text-ink-gray-4 shrink-0" v-if="option.level > 0" />
                    <Icon name="folder" class="w-4 h-4 mr-2 text-ink-gray-5 shrink-0" v-else />
                  </div>
                </template>
              </Autocomplete>
            </div>
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
              <label class="block text-xs text-ink-gray-5 mb-1.5 font-medium">Parent Folder (Optional)</label>
              <Autocomplete
                v-model="editFolderParent"
                :options="folderOptions.filter(o => o.value !== folderToEdit?.name)"
                placeholder="Select parent folder..."
              >
                <template #item-prefix="{ option }">
                  <div :style="{ paddingLeft: (option.level * 1.5) + 'rem' }" class="flex items-center">
                    <Icon name="corner-down-right" class="w-4 h-4 mr-2 text-ink-gray-4 shrink-0" v-if="option.level > 0" />
                    <Icon name="folder" class="w-4 h-4 mr-2 text-ink-gray-5 shrink-0" v-else />
                  </div>
                </template>
              </Autocomplete>
            </div>
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

              <!-- Subfolder Actions -->
              <div class="space-y-3 mt-4" v-if="folderToDelete?.children?.length > 0">
                <p class="text-sm font-medium text-ink-gray-9">What to do with subfolders?</p>
                <FormControl
                  type="select"
                  v-model="deleteSubfolderAction"
                  :options="[
                    { label: folderToDelete.parent_vault_folder ? 'Move to Parent Level' : 'Move to Root Level', value: 'move_up' },
                    { label: 'Move to specific folder...', value: 'move_to' },
                    { label: 'Delete all subfolders', value: 'delete_all' }
                  ]"
                />

                <div v-if="deleteSubfolderAction === 'move_to'" class="mt-2">
                  <Autocomplete
                    v-model="deleteTargetFolder"
                    :options="folderOptions.filter(o => o.value !== folderToDelete?.name && !o.value.startsWith(folderToDelete?.name))"
                    placeholder="Select target folder..."
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
import { ref, computed, reactive, h, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, FeatherIcon, Tooltip, Dialog, Dropdown, FormControl, Checkbox, Sidebar, SidebarItem, Tree, Autocomplete, SidebarHeader, SidebarCollapseToggle, createResource, toast, Popover } from 'frappe-ui'
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
const deleteSubfolderAction = ref('move_up')
const deleteTargetFolder = ref(null)

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


const newFolderParent = ref(null)
const isSubfolderMode = ref(false)
const editFolderParent = ref(null)

const folderOptions = computed(() => {
  const options = []
  const traverse = (nodes, level = 0) => {
    for (const node of nodes) {
      options.push({ label: node.folder_name, value: node.name, level })
      if (node.children?.length) {
        traverse(node.children, level + 1)
      }
    }
  }
  traverse(folderTree.value)
  return options
})

function openCreateFolderDialog(parent = null) {
  newFolderName.value = ''
  newFolderIcon.value = ''
  newFolderParent.value = parent ? { label: parent.folder_name, value: parent.name } : null
  isSubfolderMode.value = !!parent
  showCreateFolderDialog.value = true
}

async function handleCreateFolder() {
  if (!newFolderName.value.trim()) return
  try {
    await createFolderResource.submit({
      folder_name: newFolderName.value.trim(),
      icon: newFolderIcon.value || 'folder',
      parent_vault_folder: newFolderParent.value?.value || null,
      is_group: 0
    })
    showCreateFolderDialog.value = false
    foldersResource.reload()
    stats.reload()
  } catch (err) {
  }
}


function isFolderOrDescendantActive(folder) {
  if (checkActive(`/secrets?folder=${encodeURIComponent(folder.name)}`)) return true
  if (folder.children) {
    for (const child of folder.children) {
      if (isFolderOrDescendantActive(child)) return true
    }
  }
  return false
}

function getAllDescendants(folder, level = 0) {
  let descendants = []
  if (folder.children) {
    folder.children.forEach(child => {
      descendants.push({ ...child, level })
      descendants = descendants.concat(getAllDescendants(child, level + 1))
    })
  }
  return descendants
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
      label: 'New Subfolder',
      icon: 'plus',
      onClick: () => openCreateFolderDialog(folder)
    })
    options.push({
      label: 'Edit Folder',
      icon: 'edit-2',
      onClick: () => {
        folderToEdit.value = folder
        editFolderName.value = folder.folder_name
        editFolderIcon.value = folder.icon || ''
        const parentOpt = folderOptions.value.find(o => o.value === folder.parent_vault_folder)
        editFolderParent.value = parentOpt || null
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
  deleteSecretsCheck.value = true
  deleteFolderError.value = ''
  deleteSecretsCount.value = 0
  loadingCount.value = true
  deleteSubfolderAction.value = 'move_up'
  deleteTargetFolder.value = null
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
      parent_vault_folder: editFolderParent.value?.value || null,
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
      subfolder_action: deleteSubfolderAction.value,
      target_folder: deleteTargetFolder.value?.value || null,
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

const folderTree = ref([])

watch(
  () => foldersResource.data,
  (allFolders) => {
    const newTree = []
    const map = {}

    const preserveMap = {}
    const scan = (nodes) => {
      for (const n of nodes) {
        preserveMap[n.name] = n.expanded
        if (n.children) scan(n.children)
      }
    }
    scan(folderTree.value)

    if (allFolders) {
      allFolders.forEach(f => {
        map[f.name] = {
          ...f,
          label: f.folder_name,
          children: [],
          expanded: preserveMap[f.name] !== undefined ? preserveMap[f.name] : true
        }
      })

      allFolders.forEach(f => {
        if (f.parent_vault_folder && map[f.parent_vault_folder]) {
          map[f.parent_vault_folder].children.push(map[f.name])
        } else {
          newTree.push(map[f.name])
        }
      })
    }
    folderTree.value = newTree
  },
  { immediate: true }
)

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
