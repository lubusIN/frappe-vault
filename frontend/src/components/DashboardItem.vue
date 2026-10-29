<template>
  <div class="h-full w-full">
    <!-- Number Chart (Stat Cards with Sidebar Icons & Click Redirection) -->
    <div
      v-if="item.type == 'number_chart'"
      @click="handleStatClick(item.name)"
      class="flex h-full w-full rounded-2xl bg-surface-elevation-1 border border-outline-gray-1 overflow-hidden p-4 items-center justify-between group/stat shadow-none cursor-pointer hover:border-outline-gray-2 transition-colors"
    >
      <Tooltip v-if="item.data" :text="item.data.tooltip" class="flex-1">
        <div class="flex items-center justify-between w-full">
          <div>
            <p class="text-xs font-medium text-ink-gray-5 mb-1">{{ item.data.title }}</p>
            <div class="flex items-baseline gap-2">
              <p class="text-2xl font-bold text-ink-gray-9">{{ item.data.value }}</p>
              <Badge
                v-if="item.data.delta"
                :label="item.data.deltaSuffix ? `${item.data.delta > 0 ? '+' : ''}${item.data.delta}${item.data.deltaSuffix}` : item.data.delta"
                variant="subtle"
                :theme="item.data.delta >= 0 ? 'green' : 'red'"
              />
            </div>
          </div>
          <div class="size-9 rounded-full bg-surface-gray-2 text-ink-gray-6 group-hover/stat:text-ink-gray-9 flex items-center justify-center transition-colors shrink-0">
            <span :class="getStatIconClass(item.name)" class="w-4.5 h-4.5" aria-hidden="true" />
          </div>
        </div>
      </Tooltip>
      <div v-else class="text-xs text-ink-gray-4 p-2">Loading...</div>
    </div>

    <!-- Security Score Widget -->
    <div
      v-else-if="item.type == 'security_score'"
      class="h-full w-full rounded-2xl bg-surface-elevation-1 border border-outline-gray-1 p-4 flex flex-col justify-between overflow-hidden shadow-none"
    >
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-xs font-medium text-ink-gray-5">Security Score</h2>
        <span class="lucide-shield w-4 h-4 text-ink-gray-4" aria-hidden="true" />
      </div>
      <div class="flex items-center gap-4 flex-1">
        <div class="relative w-13 h-13 shrink-0 flex items-center justify-center">
          <svg class="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" class="stroke-outline-gray-1" stroke-width="8" fill="none" />
            <circle
              cx="50" cy="50" r="42"
              stroke="currentColor"
              :class="scoreColorClass(item.data?.score)"
              stroke-width="8"
              fill="none"
              stroke-linecap="round"
              :stroke-dasharray="`${(item.data?.score || 0) * 2.64} 264`"
            />
          </svg>
          <span class="absolute inset-0 flex items-center justify-center text-lg font-bold text-ink-gray-9">{{ item.data?.score || 0 }}</span>
        </div>
        <div class="flex-1 min-w-0 space-y-1">
          <div v-for="s in (item.data?.suggestions || []).slice(0, 2)" :key="s" class="flex items-start gap-1 text-xs">
            <span class="lucide-alert-circle w-3.5 h-3.5 text-ink-warning shrink-0 mt-0.5" aria-hidden="true" />
            <p class="text-ink-gray-7 leading-tight line-clamp-2">{{ s }}</p>
          </div>
          <div v-if="!item.data?.suggestions?.length" class="flex items-center gap-1.5">
            <span class="lucide-check-circle w-4 h-4 text-ink-green-3" aria-hidden="true" />
            <p class="text-xs text-ink-gray-7">Vault is secure! No critical risks.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Recently Accessed Widget -->
    <div
      v-else-if="item.type == 'recently_accessed'"
      class="h-full w-full rounded-2xl bg-surface-elevation-1 border border-outline-gray-1 overflow-hidden flex flex-col justify-between shadow-none"
    >
      <div class="px-4 py-3 border-b border-outline-gray-1 flex items-center justify-between shrink-0">
        <h2 class="text-sm font-semibold text-ink-gray-9">Recently Accessed</h2>
        <Button variant="ghost" size="sm" label="View All" iconRight="lucide-chevron-right" @click="goToSecrets" />
      </div>
      <div v-if="item.data?.recent_secrets?.length" class="divide-y divide-outline-gray-1 overflow-y-auto flex-1 custom-scrollbar">
        <router-link
          v-for="s in item.data.recent_secrets"
          :key="s.name"
          :to="`/secrets?secret=${s.name}`"
          class="flex items-center py-2.5 px-4 hover:bg-surface-gray-2 text-ink-gray-9 hover:text-blue-600 dark:hover:text-blue-400 transition-colors group/row"
        >
          <SecretTypeIcon :type="s.secret_type" class="mr-2.5 shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="text-xs font-medium truncate">{{ s.title }}</p>
            <p class="text-[11px] text-ink-gray-5 truncate">{{ s.secret_type }}</p>
          </div>
          <span class="lucide-chevron-right w-3.5 h-3.5 text-ink-gray-4 ml-2 shrink-0 group-hover/row:translate-x-1 transition-transform" aria-hidden="true" />
        </router-link>
      </div>
      <div v-else class="p-4 text-center">
        <EmptyState icon="clock" title="No recent activity" description="Access a secret to see it here" />
      </div>
    </div>

    <!-- Spacer -->
    <div
      v-else-if="item.type == 'spacer'"
      class="rounded-2xl bg-surface-base h-full overflow-hidden text-ink-gray-5 flex items-center justify-center border border-dashed border-outline-gray-2"
    >
      {{ editing ? 'Spacer' : '' }}
    </div>

    <!-- Axis Chart (Trends) -->
    <div
      v-else-if="item.type == 'axis_chart'"
      class="h-full w-full rounded-2xl bg-surface-elevation-1 border border-outline-gray-1 p-4 overflow-hidden shadow-none flex flex-col"
    >
      <div class="flex-1 min-h-[180px] w-full">
        <LineChart
          v-if="item.data && item.data.data && item.data.data.length"
          :data="item.data.data"
          :x="item.data.xAxis?.key || 'date'"
          :y="item.data.series ? item.data.series.map(s => s.name) : ['secrets', 'shares', 'revocations']"
          :title="item.data.title"
          :subtitle="item.data.subtitle"
          class="w-full h-full"
        />
        <div v-else-if="item.data && item.data.data" class="h-full flex items-center justify-center text-xs text-ink-gray-4">No data available</div>
        <div v-else class="h-full flex items-center justify-center text-xs text-ink-gray-4">Loading chart...</div>
      </div>
    </div>

    <!-- Donut Chart (Secrets by Folder) -->
    <div
      v-else-if="item.type == 'donut_chart'"
      class="h-full w-full rounded-2xl bg-surface-elevation-1 border border-outline-gray-1 p-4 overflow-hidden shadow-none flex flex-col justify-between"
    >
      <div class="flex-1 min-h-[180px] w-full flex items-center justify-center relative overflow-hidden">
        <DonutChart
          v-if="item.data && item.data.data && item.data.data.length"
          :data="item.data.data"
          :category="item.data.categoryColumn || 'folder_name'"
          :value="item.data.valueColumn || 'count'"
          :title="item.data.title"
          :subtitle="item.data.subtitle"
          class="w-full h-full"
        />
        <div v-else-if="item.data && item.data.data" class="h-full flex items-center justify-center text-xs text-ink-gray-4">No data available</div>
        <div v-else class="h-full flex items-center justify-center text-xs text-ink-gray-4">Loading chart...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Tooltip, Badge, Button } from 'frappe-ui'
import { DonutChart, LineChart } from 'frappe-ui/charts'
import EmptyState from './EmptyState.vue'
import SecretTypeIcon from './SecretTypeIcon.vue'

const props = defineProps({
  index: { type: Number, required: true },
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
})

const router = useRouter()

function goToSecrets() {
  if (props.editing) return
  router.push('/secrets')
}

function handleStatClick(name) {
  if (props.editing) return
  switch (name) {
    case 'total_secrets':
      router.push('/secrets')
      break
    case 'bookmarks':
      router.push('/bookmarks')
      break
    case 'active_shares':
    case 'revoked_shares':
      router.push('/shares')
      break
  }
}

function getStatIconClass(name) {
  switch (name) {
    case 'total_secrets':
      return 'lucide-key'
    case 'bookmarks':
      return 'lucide-bookmark'
    case 'active_shares':
      return 'lucide-share-2'
    case 'revoked_shares':
      return 'lucide-user-x'
    default:
      return 'lucide-activity'
  }
}

function scoreColorClass(s = 0) {
  if (s >= 80) return 'text-ink-green-3'
  if (s >= 60) return 'text-ink-blue-3'
  if (s >= 40) return 'text-ink-yellow-3'
  return 'text-ink-red-3'
}
</script>
