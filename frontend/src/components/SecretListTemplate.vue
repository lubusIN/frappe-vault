<template>
  <div class="flex-1 flex flex-col overflow-hidden bg-surface-base">
    <!-- Header -->
    <header class="flex h-10.5 items-center justify-between border-b border-outline-gray-1 bg-surface-base px-5 py-2.5 shrink-0">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <!-- Mobile Sidebar Trigger -->
        <Button
          class="sm:hidden mr-1 shrink-0"
          variant="ghost"
          icon="lucide-menu"
          @click="mobileSidebarOpened = true"
        />

        <Breadcrumbs :items="breadcrumbs" class="min-w-0" />
      </div>
      <div class="flex items-center gap-2">
        <Button v-if="showCreateButton" variant="solid" iconLeft="lucide-plus" label="Create" @click="showNewDialog = true" />
      </div>
    </header>

    <!-- View Controls Bar -->
    <div class="view-controls-bar flex items-center justify-between gap-2 px-5 py-4 relative z-10">
      <!-- Quick Filters (Left side) -->
      <div class="flex flex-1 items-center gap-2.5 overflow-x-auto h-9">
        <TextInput
          v-model="titleQuery"
          placeholder="Title"
          class="w-44 shrink-0"
        />

        <Select
          v-model="activeFilters.secret_type"
          :options="typeFilterOptions"
          placeholder="Type"
        />

        <Select
          v-if="showFolderFilter"
          v-model="activeFilters.folder"
          :options="folderFilterOptions"
          placeholder="Folder"
        />
      </div>

      <!-- Divider -->
      <div class="-ml-2 h-[70%] border-l" />

      <!-- Controls (Right side) -->
      <div class="flex items-center gap-2">
        <!-- Refresh -->
        <Button
          :tooltip="'Refresh'"
          :icon="RefreshIcon"
          :loading="secrets.loading"
          @click="refreshSecrets()"
        />

        <!-- Filter Panel -->
        <FilterPanel
          :fields="filterableFields.data || []"
          @update="onFilterUpdate"
        />

        <!-- Sort Panel -->
        <SortPanel
          :fields="sortOptions.data || []"
          @update="onSortUpdate"
        />

        <!-- Column Panel -->
        <ColumnPanel
          :defaultColumns="defaultColumns"
          :allFields="filterableFields.data || []"
          @update="onColumnsUpdate"
        />

        <!-- Clear Filters -->
        <Button
          v-if="hasActiveFilters"
          variant="ghost"
          class="h-8 px-2 text-sm text-ink-gray-6 hover:text-ink-gray-9 focus:outline-none font-medium"
          @click="clearFilters()"
        >
          Clear
        </Button>

        <!-- More Options -->
        <Dropdown v-if="showCreateButton" :options="moreOptions">
          <template #default>
            <Button :tooltip="'More Options'" icon="lucide-more-horizontal" />
          </template>
        </Dropdown>
      </div>
    </div>

    <!-- Secret list -->
    <div class="flex-1 flex flex-col overflow-hidden relative">
      <!-- Loading state -->
      <div v-if="secrets.loading && !secrets.data" class="p-6 space-y-3">
        <div v-for="i in 5" :key="i" class="h-16 bg-surface-gray-3 rounded-lg animate-pulse" />
      </div>

      <!-- Secrets list view -->
      <template v-else-if="secretsList.length">
        <ListView
          class="flex-1 flex flex-col overflow-hidden bg-surface-base"
          :columns="columns"
          :rows="paginatedRows"
          row-key="name"
          v-model:selections="selectedSecrets"
          :options="{
            selectable: allowSelection,
            showTooltip: true,
            resizeColumn: true,
            onRowClick: (row) => router.push({ name: 'SecretDetail', params: { name: row.name } }),
          }"
        >
          <ListHeader class="sm:mx-5 mx-3 shrink-0 relative">
            <ListHeaderItem
              v-for="column in columns"
              :key="column.key"
              :item="column"
              @columnWidthUpdated="handleColumnWidthUpdated"
            />
          </ListHeader>
          <ListRows class="sm:mx-5 mx-3">
            <ListRow
              v-for="row in paginatedRows"
              :key="row.name"
              v-slot="{ column, item }"
              :row="row"
              @click="router.push({ name: 'SecretDetail', params: { name: row.name } })"
            >
              <ListRowItem :item="item" :align="column.align" class="overflow-hidden">
                <template #default>
                  <!-- Title column -->
                  <div v-if="column.key === 'title'" class="flex items-center py-1">
                    <span class="min-w-0 font-medium text-ink-gray-9 cursor-pointer text-base truncate block leading-normal">{{ item.title }}</span>
                  </div>

                  <!-- Type column -->
                  <div v-else-if="column.key === 'secret_type'" class="flex items-center text-base text-ink-gray-9">
                    <SecretTypeIcon :type="item" show-label />
                  </div>

                  <!-- Folder column -->
                  <div v-else-if="column.key === 'folder'" class="flex items-center gap-1.5 text-base text-ink-gray-9">
                    <template v-if="item">
                      <Icon :name="(row.folder_icon || getFolderIcon(item, foldersResource.data)).replace(/^lucide-/, '')" class="w-3.5 h-3.5 text-ink-gray-5 shrink-0" />
                      <span class="truncate">{{ item }}</span>
                    </template>
                    <span class="text-base text-ink-gray-4" v-else>—</span>
                  </div>

                  <!-- Strength column -->
                  <StrengthBadge v-else-if="column.key === 'password_strength' && item" :strength="item" size="sm" />
                  <span v-else-if="column.key === 'password_strength'" class="text-base text-ink-gray-4">—</span>

                  <!-- Modified column -->
                  <span v-else-if="column.key === 'modified'" class="text-base text-ink-gray-6">{{ item.formatted }}</span>

                  <!-- Actions column -->
                  <div v-else-if="column.key === '_actions'" class="flex items-center justify-end gap-1.5" @click.stop>
                    <Button
                      variant="ghost"
                      class="!p-1.5 h-auto hover:bg-surface-gray-2"
                      @click.stop="handleToggleBookmark(row)"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        class="size-4 transition-colors"
                        :class="row.is_bookmark ? 'text-red-500 fill-red-500' : 'text-ink-gray-4 fill-none stroke-current stroke-2'"
                        stroke="currentColor"
                        :fill="row.is_bookmark ? 'currentColor' : 'none'"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        aria-hidden="true"
                      >
                        <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>
                      </svg>
                    </Button>
                  </div>

                  <!-- Dynamic columns (fallback) -->
                  <span v-else class="text-base text-ink-gray-7 truncate">{{ item ?? '—' }}</span>
                </template>
              </ListRowItem>
            </ListRow>
          </ListRows>
          <ListSelectBanner v-if="allowSelection">
            <template #actions="{ unselectAll }">
              <Button
                v-if="allowDelete"
                variant="solid"
                theme="red"
                iconLeft="lucide-trash-2"
                label="Delete"
                @click="showDeleteDialog = true"
              />
            </template>
          </ListSelectBanner>
        </ListView>

        <!-- Pagination Footer -->
        <ListFooter
          v-model="pageLength"
          class="border-t border-outline-gray-1 px-5 py-2 bg-surface-base shrink-0"
          :options="{
            rowCount: paginatedRows.length,
            totalCount: totalCount,
          }"
          @loadMore="pageLength += 20"
        />
      </template>

      <!-- Empty state -->
      <EmptyState v-else :icon="emptyState.icon" :title="emptyState.title" :description="hasActiveFilters ? 'Try adjusting your filters' : emptyState.description">
        <template #actions v-if="emptyState.showDemoButton || showCreateButton">
          <div class="flex items-center gap-2">
            <Button v-if="showCreateButton" variant="solid" @click="showNewDialog = true">Create</Button>
            <Button
              v-if="emptyState.showDemoButton && isVaultAdmin && !hasActiveFilters && !stats.data?.has_demo_data"
              variant="outline"
              iconLeft="lucide-sparkles"
              label="Load Demo Data"
              :loading="generateDemo.loading"
              @click="handleGenerateDemo"
            />
          </div>
        </template>
      </EmptyState>
    </div>

    <!-- Delete Secret Dialog -->
    <Dialog
      v-model="showDeleteDialog"
      :title="'Delete Secret'"
      size="sm"
    >
      <template #default>
        <div class="space-y-3 px-4 pb-6">
          <p class="text-sm text-ink-gray-6 mt-1 leading-normal" v-if="selectedSecrets.size === 1">
            Are you sure you want to permanently delete <strong>this secret</strong>? This action cannot be undone.
          </p>
          <p class="text-sm text-ink-gray-6 mt-1 leading-normal" v-else>
            Are you sure you want to permanently delete <strong>{{ selectedSecrets.size }} secrets</strong>? This action cannot be undone.
          </p>
          <div v-if="deleteError" class="text-sm text-red-700 bg-red-50 p-3 rounded-lg border border-red-200 font-medium leading-relaxed">
            {{ deleteError }}
          </div>
        </div>
        <div class="flex items-center justify-end gap-2 px-4 pb-4">
          <Button variant="outline" @click="showDeleteDialog = false">
            Cancel
          </Button>
          <Button variant="solid" theme="red" @click="handleDeleteSecret" :loading="deleteResource.loading">
            Delete
          </Button>
        </div>
      </template>
    </Dialog>

    <!-- New Secret Dialog -->
    <NewSecretDialog v-if="showCreateButton" v-model="showNewDialog" :initial-folder="activeFilters.folder" @created="handleCreated" />

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useColumnResize } from '../composables/useColumnResize'
import RefreshIcon from './RefreshIcon.vue'
import FilterPanel from './FilterPanel.vue'
import SortPanel from './SortPanel.vue'
import ColumnPanel from './ColumnPanel.vue'
import {
  Button,
  Dialog,
  TextInput,
  Dropdown,
  Breadcrumbs,
  Select,
  toast
} from 'frappe-ui'
import {
  ListView,
  ListHeader,
  ListHeaderItem,
  ListRows,
  ListRow,
  ListRowItem,
  ListSelectBanner,
  ListFooter
} from 'frappe-ui/experimental'
import {
  mobileSidebarOpened,
  useSecrets,
  useFolders,
  useToggleBookmark,
  useGenerateDemoData,
  useVaultStats,
  useBulkDeleteSecrets,
  useFilterableFields,
  useSortOptions,
} from '../composables/vault'
import { typeFilterOptions, formatDate as formatTime, getFolderIcon } from '../composables/constants'
import EmptyState from './EmptyState.vue'
import NewSecretDialog from './NewSecretDialog.vue'
import SecretTypeIcon from './SecretTypeIcon.vue'
import StrengthBadge from './StrengthBadge.vue'

const props = defineProps({
  fetchParams: {
    type: Object,
    default: () => ({})
  },
  breadcrumbs: {
    type: Array,
    required: true
  },
  emptyState: {
    type: Object,
    default: () => ({
      icon: 'key',
      title: 'No secrets found',
      description: 'Create your first secret to get started',
      showDemoButton: false
    })
  },
  showCreateButton: {
    type: Boolean,
    default: false
  },
  showFolderFilter: {
    type: Boolean,
    default: false
  },
  allowSelection: {
    type: Boolean,
    default: true
  },
  allowDelete: {
    type: Boolean,
    default: false
  }
})

const router = useRouter()

const isVaultAdmin = computed(() => {
  const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name
  if (user === 'Administrator') return true
  const roles = window.frappe?.boot?.user?.roles || window.frappe?.user?.roles || []
  return roles.includes('Vault Admin') || roles.includes('System Manager')
})

const titleQuery = ref('')
const showNewDialog = ref(false)
const selectedSecrets = ref(new Set())
const activeFilters = ref({ secret_type: '', folder: '', ...props.fetchParams })
const panelFilters = ref({})
const pageLength = ref(20)
const currentSort = ref('modified desc')
const showDeleteDialog = ref(false)
const deleteError = ref('')

const defaultColumns = [
  { label: 'Type', key: 'secret_type', width: '10rem' },
  { label: 'Folder', key: 'folder', width: '11rem' },
  { label: 'Strength', key: 'password_strength', width: '10rem' },
  { label: 'Last Modified', key: 'modified', width: '12rem' },
]

const activeColumnDefs = ref([...defaultColumns])

// Initialize secrets resource without auto-fetch
const secrets = useSecrets()
const foldersResource = useFolders()
const toggleBook = useToggleBookmark()
const stats = useVaultStats()
const generateDemo = useGenerateDemoData()
const deleteResource = useBulkDeleteSecrets()
const filterableFields = useFilterableFields()
const sortOptions = useSortOptions()

watch(
  [titleQuery, activeFilters, pageLength, currentSort, panelFilters],
  () => {
    const filters = {
      ...props.fetchParams,
      title: titleQuery.value || undefined,
      secret_type: activeFilters.value.secret_type || undefined,
      folder: activeFilters.value.folder || undefined,
      limit: pageLength.value,
      order_by: currentSort.value,
    }
    // Merge panel filters into the API params
    for (const [key, val] of Object.entries(panelFilters.value)) {
      if (val !== undefined && val !== '') {
        filters[key] = val
      }
    }
    secrets.submit(filters)
  },
  { deep: true, immediate: true }
)

const route = useRoute()
watch(() => route.query.folder, (newFolder) => {
  activeFilters.value.folder = newFolder || ''
}, { immediate: true })

async function handleGenerateDemo() {
  try {
    await generateDemo.submit()
    secrets.reload()
    stats.reload()
    window.dispatchEvent(new CustomEvent('vault-demo-changed'))
  } catch (err) {
  }
}

function handleDemoChanged() {
  secrets.reload()
  stats.reload()
}

onMounted(() => {
  window.addEventListener('vault-demo-changed', handleDemoChanged)
  window.addEventListener('vault-secret-updated', handleDemoChanged)
})

onUnmounted(() => {
  window.removeEventListener('vault-demo-changed', handleDemoChanged)
  window.removeEventListener('vault-secret-updated', handleDemoChanged)
})

const secretsList = computed(() => secrets.data?.secrets || [])
const totalCount = computed(() => secrets.data?.total || secretsList.value.length || 0)
const hasActiveFilters = computed(() =>
  titleQuery.value || activeFilters.value.secret_type || activeFilters.value.folder || Object.keys(panelFilters.value).length > 0
)

const folderFilterOptions = computed(() => {
  const opts = [{ label: 'All Folders', value: '' }]
  for (const f of foldersResource.data || []) {
    opts.push({ label: f.folder_name, value: f.name })
  }
  return opts
})

const moreOptions = computed(() => {
  return [
    {
      group: 'Options',
      items: [
        {
          label: 'Create Secret',
          icon: 'lucide-plus',
          onClick: () => { showNewDialog.value = true }
        },
        {
          label: 'Refresh List',
          icon: 'lucide-refresh-cw',
          onClick: () => { refreshSecrets() }
        }
      ]
    }
  ]
})

const baseColumns = computed(() => {
  const titleCol = { label: 'Title', key: 'title', width: 1 }
  const actionsCol = { label: '', key: '_actions', width: '6rem', align: 'right' }
  return [titleCol, ...activeColumnDefs.value, actionsCol]
})

const { columns, handleColumnWidthUpdated } = useColumnResize('vault-column-widths', baseColumns)

const formattedRows = computed(() => {
  return secretsList.value.map(secret => {
    return {
      ...secret,
      name: secret.name,
      title: {
        title: secret.title,
        subtitle: secret.username || secret.email || secret.url || '',
        secret_type: secret.secret_type,
      },
      secret_type: secret.secret_type,
      folder: secret.folder_name || foldersResource.data?.find(f => f.name === secret.folder)?.folder_name || secret.folder || '',
      folder_icon: secret.folder_icon || foldersResource.data?.find(f => f.name === secret.folder)?.icon || '',
      password_strength: secret.password_strength || '',
      modified: {
        raw: secret.modified,
        formatted: formatTime(secret.modified),
      },
      _actions: secret,
    }
  })
})

const paginatedRows = computed(() => formattedRows.value.slice(0, pageLength.value))

function onFilterUpdate(filters) {
  panelFilters.value = filters
}

function onSortUpdate(sort) {
  currentSort.value = sort
}

function onColumnsUpdate(newColumns) {
  activeColumnDefs.value = newColumns
}

function clearFilters() {
  titleQuery.value = ''
  activeFilters.value = { secret_type: '', folder: '', ...props.fetchParams }
  panelFilters.value = {}
  currentSort.value = 'modified desc'
  activeColumnDefs.value = [...defaultColumns]
}

function refreshSecrets() {
  secrets.reload()
}

function handleCreated(result) {
  showNewDialog.value = false
  secrets.reload()
  stats.reload()
  router.push({ name: 'SecretDetail', params: { name: result.name } })
}

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
  return 'Failed to delete secret(s). Please try again.'
}

async function handleDeleteSecret() {
  if (!selectedSecrets.value || selectedSecrets.value.size === 0) return

  deleteError.value = ''
  try {
    const secret_names = Array.from(selectedSecrets.value).map((item) =>
      typeof item === 'object' && item !== null ? item.name : item
    )
    const res = await deleteResource.submit({ secret_names: JSON.stringify(secret_names) })

    if (res && res.deleted > 0) {
      showDeleteDialog.value = false
      selectedSecrets.value.clear()
      secrets.reload()
      stats.reload()

      if (res.skipped > 0) {
        toast({
          title: 'Partial Success',
          text: `Deleted ${res.deleted} secret(s), but skipped ${res.skipped} due to insufficient permissions.`,
          icon: 'lucide-alert-circle',
          iconClasses: 'text-orange-500'
        })
      } else {
        toast({
          title: 'Success',
          text: `Deleted ${res.deleted} secret(s)`,
          icon: 'lucide-check',
          iconClasses: 'text-green-500'
        })
      }
    } else if (res && res.skipped > 0 && res.deleted === 0) {
      deleteError.value = `You don't have permission to delete the selected secret(s). Only the owner or someone with Full Control access can delete.`
    } else if (res && res.failed > 0) {
      deleteError.value = res.error || 'An unexpected error occurred while deleting.'
    }
  } catch (error) {
    deleteError.value = parseFrappeError(error)
  }
}

async function handleToggleBookmark(secret) {
  try {
    const isBookmarked = secret.is_bookmark
    await toggleBook.submit({
      name: secret.name
    })
    toast({
      title: 'Success',
      text: isBookmarked ? 'Removed from bookmarks' : 'Added to bookmarks',
      icon: 'lucide-check',
      iconClasses: 'text-green-500'
    })
    secrets.reload()
  } catch (err) {
  }
}
</script>
