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
    </header>


    <ViewControlsBar>
      <template #left>
        <!-- Title Quick Filter -->
        <TextInput
          v-model="titleQuery"
          placeholder="Title"
          class="w-44 shrink-0"
        />
      </template>
      <template #right>


        <!-- Refresh Button -->
        <Button
          :tooltip="'Refresh'"
          :icon="RefreshIcon"
          :loading="shared.loading"
          @click="shared.reload()"
        />
      </template>
    </ViewControlsBar>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Loading state -->
      <div v-if="shared.loading && !shared.data" class="p-6 space-y-3">
        <div v-for="i in 5" :key="i" class="h-16 bg-surface-gray-3 rounded-lg animate-pulse" />
      </div>

      <!-- Shared secrets list view -->
      <template v-else-if="filteredList.length">
        <ListView
          class="flex-1 flex flex-col overflow-hidden bg-surface-base"
          :columns="columns"
          :rows="paginatedRows"
          row-key="name"
          v-model:selections="selectedShares"
          :options="{
            selectable: true,
            showTooltip: true,
            resizeColumn: true,
            onRowClick: (row) => handleRowClick(row),
          }"
        >
          <ListHeader class="sm:mx-5 mx-3 shrink-0">
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
              @click="handleRowClick(row)"
            >
              <ListRowItem :item="item" :align="column.align" class="overflow-hidden">
                <template #default>
                  <!-- Title column -->
                  <div v-if="column.key === 'title'" class="flex items-center py-1 min-w-0">
                    <span class="min-w-0 flex-1 font-medium text-ink-gray-9 cursor-pointer text-base truncate block leading-normal">{{ item.title }}</span>
                  </div>

                  <!-- Type column -->
                  <div v-else-if="column.key === 'secret_type'" class="flex items-center text-base text-ink-gray-9">
                    <template v-if="row.shared_doctype === 'Vault Folder'">
                      <div class="flex items-center gap-2">
                        <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-surface-gray-3 text-ink-gray-7">
                          <Icon :name="getFolderIcon(row.title, foldersResource.data).replace(/^lucide-/, '')" class="w-3.5 h-3.5" />
                        </div>
                        <span>Folder</span>
                      </div>
                    </template>
                    <template v-else>
                      <SecretTypeIcon :type="item" show-label />
                    </template>
                  </div>

                  <!-- Shared By column -->
                  <span v-else-if="column.key === 'shared_by'" class="text-base text-ink-gray-6 truncate">{{ item }}</span>

                  <!-- Permission column -->
                  <Badge
                    v-else-if="column.key === 'permission_level'"
                    :theme="permissionTheme[item] || 'gray'"
                    variant="subtle"
                  >
                    {{ item }}
                  </Badge>

                  <!-- Expires On column -->
                  <span v-else-if="column.key === 'expires_on'" class="text-base text-ink-gray-6">{{ item }}</span>
                </template>
              </ListRowItem>
            </ListRow>
          </ListRows>
          <ListSelectBanner>
            <template #actions>
              <Button
                variant="solid"
                theme="gray"
                iconLeft="lucide-eye-off"
                label="Dismiss Logs"
                :loading="bulkDeleteLoading"
                @click="handleBulkDismiss"
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
      <EmptyState v-else icon="lucide-users" title="Nothing shared with you" description="When someone shares a secret with you, it will appear here" />
    </div>
  </div>
</template>

<script setup>
import ViewControlsBar from '../components/ViewControlsBar.vue'
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useColumnResize } from '../composables/useColumnResize'
import { Badge, Button, TextInput, Breadcrumbs, toast } from 'frappe-ui'
import { ListView, ListHeader, ListHeaderItem, ListRows, ListRow, ListRowItem, ListSelectBanner, ListFooter } from 'frappe-ui/experimental'
import { mobileSidebarOpened, useSharedWithMe, useFolders } from '../composables/vault'
import { createResource } from 'frappe-ui'
import EmptyState from '../components/EmptyState.vue'
import SecretTypeIcon from '../components/SecretTypeIcon.vue'
import { permissionTheme, formatDateTime as formatTime, getFolderIcon } from '../composables/constants'

const router = useRouter()
const shared = useSharedWithMe()
const foldersResource = useFolders()

const titleQuery = ref('')
const selectedShares = ref(new Set())
const bulkDeleteLoading = ref(false)
const pageLength = ref(20)

const dismissResource = createResource({
  url: 'frappe_vault.api.sharing.dismiss_shared_logs',
})

const list = computed(() => shared.data?.shared || [])
const totalCount = computed(() => shared.data?.total || filteredList.value.length || 0)

watch(pageLength, (newLength) => {
  shared.submit({
    limit: newLength,
  })
}, { immediate: true })
const breadcrumbs = computed(() => [{ label: 'Shared with Me' }])

const filteredList = computed(() => {
  let result = list.value
  if (titleQuery.value.trim()) {
    const q = titleQuery.value.toLowerCase().trim()
    result = result.filter(item =>
      (item.title && item.title.toLowerCase().includes(q)) ||
      (item.shared_by && item.shared_by.toLowerCase().includes(q))
    )
  }
  return result || []
})

const defaultColumns = [
  { label: 'Type', key: 'secret_type', width: '10rem' },
  { label: 'Shared By', key: 'shared_by', width: '14rem' },
  { label: 'Permission', key: 'permission_level', width: '11rem' },
  { label: 'Expires On', key: 'expires_on', width: '11rem' }
]

const baseColumns = computed(() => {
  const titleCol = { label: 'Title', key: 'title', width: 1 }
  return [titleCol, ...defaultColumns]
})

const { columns, handleColumnWidthUpdated } = useColumnResize('shared-with-me-column-widths', baseColumns)

const formattedRows = computed(() => {
  return filteredList.value.map(s => {
    return {
      name: s.share_name, // Unique share ID as row key to avoid duplicates
      secret_name: s.shared_name, // Actual secret/folder ID
      shared_doctype: s.shared_doctype,
      title: {
        title: s.title || (s.shared_doctype === 'Vault Folder' ? 'Deleted Folder' : 'Deleted Secret'),
        secret_type: s.secret_type || 'Other',
      },
      secret_type: s.secret_type || 'Other',
      shared_by: s.shared_by || 'Unknown',
      permission_level: s.is_revoked ? 'Revoked' : (s.permission_level || 'View Only'),
      expires_on: s.expires_on ? formatTime(s.expires_on) : 'Never',
      is_revoked: s.is_revoked,
    }
  })
})

const paginatedRows = computed(() => formattedRows.value.slice(0, pageLength.value))

function handleRowClick(row) {
  if (row.is_revoked) {
    toast.error('This share has been revoked and is no longer accessible')
    return
  }
  if (row.shared_doctype === 'Vault Folder') {
    router.push({ path: '/secrets', query: { folder: row.secret_name } })
  } else {
    router.push({ name: 'SecretDetail', params: { name: row.secret_name } })
  }
}

async function handleBulkDismiss() {
  if (selectedShares.value.size === 0) return
  bulkDeleteLoading.value = true
  try {
    await dismissResource.submit({
      share_names: JSON.stringify(Array.from(selectedShares.value))
    })
    toast.success('Selected logs dismissed successfully')
    selectedShares.value.clear()
    shared.reload()
  } catch (err) {
    toast.error(err.message || 'Failed to dismiss logs')
  } finally {
    bulkDeleteLoading.value = false
  }
}
</script>
