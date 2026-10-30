<template>
  <div class="flex flex-col h-full overflow-hidden bg-surface-base">
    <!-- Header Toolbar -->
    <header class="flex h-10.5 items-center justify-between border-b border-outline-gray-1 bg-surface-base px-5 py-2.5 shrink-0">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <Button
          class="sm:hidden mr-1 shrink-0"
          variant="ghost"
          icon="lucide-menu"
          @click="mobileSidebarOpened = true"
        />
        <h1 class="text-lg font-medium text-ink-gray-9 truncate">Dashboard</h1>
      </div>

      <div class="flex items-center gap-2">
        <!-- View Mode Header Controls -->
        <template v-if="!editing">
          <Button
            variant="subtle"
            iconLeft="lucide-refresh-cw"
            label="Refresh"
            :loading="dashboardItems.loading"
            @click="dashboardItems.reload"
          />
          <Button
            v-if="isVaultAdmin"
            variant="subtle"
            iconLeft="lucide-pen-line"
            label="Edit"
            @click="enableEditing"
          />
          <Button
            variant="solid"
            iconLeft="lucide-plus"
            label="Add Secret"
            @click="showAddSecretModal = true"
          />
        </template>

        <!-- Edit Mode Header Controls -->
        <template v-else>
          <Button
            label="Chart"
            iconLeft="lucide-plus"
            @click="showAddChartModal = true"
          />
          <Button
            label="Reset to Default"
            iconLeft="lucide-undo-2"
            @click="resetToDefault"
          />
          <Button label="Cancel" @click="cancel" />
          <Button
            variant="solid"
            label="Save"
            :disabled="!dirty"
            :loading="saveDashboard.loading"
            @click="save"
          />
        </template>
      </div>
    </header>

    <!-- Date Range Preset & Filter Controls -->
    <div class="px-5 py-3 border-b border-outline-gray-1 flex items-center gap-4 bg-surface-base shrink-0">
      <Dropdown
        v-if="!showDatePicker"
        v-model="preset"
        :options="presetOptions"
        class="w-48"
        :button="{
          label: preset,
          class: '!w-full justify-between [&>svg]:text-ink-gray-5',
          variant: 'outline',
          iconRight: 'lucide-chevron-down',
          iconLeft: 'lucide-calendar',
        }"
      />

      <DateRangePicker
        v-else
        ref="datePickerRef"
        class="!w-64"
        v-model="filters.period"
        variant="outline"
        placeholder="Select Period"
        :formatter="formatRange"
        @change="
          (v) =>
            updateFilter('period', v, () => {
              showDatePicker = false
              if (!v) {
                filters.period = getLastXDays(30)
                preset = 'Last 30 Days'
              } else {
                preset = formatRange(v)
              }
            })
        "
      >
        <template #prefix>
          <span class="lucide-calendar w-4 h-4 text-ink-gray-5 mr-2" aria-hidden="true" />
        </template>
      </DateRangePicker>
    </div>

    <!-- Dashboard Content Area -->
    <div class="flex-1 overflow-y-auto custom-scrollbar">
      <div v-if="dashboardItems.loading" class="flex h-64 items-center justify-center">
        <LoadingIndicator class="w-8 h-8 text-ink-gray-5" />
      </div>
      <DashboardGrid
        v-else-if="dashboardItems.data && dashboardItems.data.length"
        v-model="dashboardItems.data"
        :editing="editing"
      />
      <div v-else class="flex h-full items-center justify-center p-6">
        <EmptyState icon="layout-dashboard" title="No dashboard items" description="Add charts to customize your vault dashboard" />
      </div>
    </div>

    <!-- Modals -->
    <AddChartModal
      v-if="showAddChartModal"
      v-model="showAddChartModal"
      v-model:items="dashboardItems.data"
    />

    <NewSecretDialog
      v-model="showAddSecretModal"
      @created="onSecretCreated"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, provide, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  createResource,
  Button,
  Dropdown,
  DateRangePicker,
  LoadingIndicator,
  dayjs
} from 'frappe-ui'
import { useSecurityScore, mobileSidebarOpened } from '../composables/vault'
import DashboardGrid from '../components/DashboardGrid.vue'
import AddChartModal from '../components/AddChartModal.vue'
import NewSecretDialog from '../components/NewSecretDialog.vue'
import EmptyState from '../components/EmptyState.vue'

const router = useRouter()
const scoreResource = useSecurityScore()

const isVaultAdmin = computed(() => {
  const user = window.frappe?.session?.user || window.frappe?.boot?.user?.name
  if (user === 'Administrator') return true
  const roles = window.frappe?.boot?.user?.roles || window.frappe?.user?.roles || []
  return roles.includes('Vault Admin') || roles.includes('System Manager')
})

const editing = ref(false)
const showDatePicker = ref(false)
const datePickerRef = ref(null)
const preset = ref('Last 30 Days')
const showAddChartModal = ref(false)
const showAddSecretModal = ref(false)

function getLastXDays(range = 30) {
  const today = new Date()
  const lastXDate = new Date(today)
  lastXDate.setDate(today.getDate() - range)
  return `${dayjs(lastXDate).format('YYYY-MM-DD')},${dayjs(today).format('YYYY-MM-DD')}`
}

function formatRange(rangeStr) {
  if (!rangeStr) return ''
  const [from, to] = rangeStr.split(',')
  if (!from || !to) return rangeStr
  return `${formatSingleDate(from)} to ${formatSingleDate(to)}`
}

function formatSingleDate(dateStr) {
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch (e) {
    return dateStr
  }
}

const filters = reactive({
  period: getLastXDays(30),
})

const fromDate = computed(() => {
  if (!filters.period) return null
  return filters.period.split(',')[0]
})

const toDate = computed(() => {
  if (!filters.period) return null
  return filters.period.split(',')[1]
})

provide('fromDate', fromDate)
provide('toDate', toDate)
provide('filters', filters)

function updateFilter(key, value, callback) {
  filters[key] = value
  callback?.()
  dashboardItems.reload()
}

const presetOptions = computed(() => [
  {
    group: 'Presets',
    hideLabel: true,
    items: [
      {
        label: 'Last 7 Days',
        onClick: () => {
          preset.value = 'Last 7 Days'
          filters.period = getLastXDays(7)
          dashboardItems.reload()
        },
      },
      {
        label: 'Last 30 Days',
        onClick: () => {
          preset.value = 'Last 30 Days'
          filters.period = getLastXDays(30)
          dashboardItems.reload()
        },
      },
      {
        label: 'Last 60 Days',
        onClick: () => {
          preset.value = 'Last 60 Days'
          filters.period = getLastXDays(60)
          dashboardItems.reload()
        },
      },
      {
        label: 'Last 90 Days',
        onClick: () => {
          preset.value = 'Last 90 Days'
          filters.period = getLastXDays(90)
          dashboardItems.reload()
        },
      },
    ],
  },
  {
    label: 'Custom Range',
    onClick: () => {
      showDatePicker.value = true
      setTimeout(() => datePickerRef.value?.open(), 0)
      preset.value = 'Custom Range'
      filters.period = null
    },
  },
])

const dashboardItems = createResource({
  url: 'frappe_vault.api.dashboard.get_vault_dashboard',
  makeParams() {
    return {
      from_date: fromDate.value,
      to_date: toDate.value,
    }
  },
  auto: true,
})

const oldItems = ref([])
const dirty = computed(() => {
  if (!editing.value) return false
  return JSON.stringify(dashboardItems.data) !== JSON.stringify(oldItems.value)
})

function copy(obj) {
  return JSON.parse(JSON.stringify(obj))
}

function enableEditing() {
  editing.value = true
  oldItems.value = copy(dashboardItems.data)
}

function cancel() {
  editing.value = false
  dashboardItems.data = copy(oldItems.value)
}

const saveDashboard = createResource({
  url: 'frappe_vault.api.dashboard.save_dashboard_layout',
  method: 'POST',
  onSuccess: () => {
    dashboardItems.reload()
    editing.value = false
  },
})

function save() {
  const itemsCopy = copy(dashboardItems.data)
  itemsCopy.forEach((item) => {
    delete item.data
  })
  saveDashboard.submit({
    layout: itemsCopy,
  })
}

function resetToDefault() {
  createResource({
    url: 'frappe_vault.api.dashboard.reset_dashboard_layout',
    auto: true,
    onSuccess: () => {
      dashboardItems.reload()
      editing.value = false
    },
  })
}

function onSecretCreated(newSecret) {
  showAddSecretModal.value = false
  dashboardItems.reload()
  scoreResource.reload()
  if (newSecret && newSecret.name) {
    router.push(`/secrets?secret=${newSecret.name}`)
  } else {
    router.push('/secrets')
  }
}

function handleDemoChanged() {
  dashboardItems.reload()
  scoreResource.reload()
}

onMounted(() => {
  window.addEventListener('vault-demo-changed', handleDemoChanged)
})

onUnmounted(() => {
  window.removeEventListener('vault-demo-changed', handleDemoChanged)
})
</script>
