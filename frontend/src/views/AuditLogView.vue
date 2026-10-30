<template>
  <div class="flex-1 flex flex-col overflow-auto p-6">
    <h1 class="text-xl font-semibold text-ink-gray-9 mb-4">Audit Log</h1>
    <div v-if="logs.loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="h-12 bg-surface-gray-3 rounded animate-pulse" />
    </div>
    <div v-else-if="logList.length" class="bg-surface-elevation-1 rounded-xl border border-outline-gray-1 divide-y divide-outline-gray-1">
      <div v-for="log in logList" :key="log.name" class="flex items-start justify-between px-5 py-3.5 gap-3.5">
        <span :class="['lucide-' + (actionIcons[log.action] || 'activity').replace(/^lucide-/, ''), 'w-4 h-4 shrink-0 mt-1 text-ink-gray-5']" aria-hidden="true" />
        <div class="min-w-0 flex-1 text-sm leading-relaxed text-ink-gray-8">
          <span class="font-bold text-ink-gray-9">{{ log.user }}</span>
          <span class="text-ink-gray-6 ml-1.5">{{ log.action.toLowerCase() }}</span>
          <span v-if="getSecretLabel(log)" class="font-semibold text-ink-gray-9 ml-1">{{ getSecretLabel(log) }}</span>
          <div v-if="log.ip_address" class="text-xs text-ink-gray-4 mt-0.5 font-mono">{{ log.ip_address }}</div>
        </div>
        <span class="ml-auto text-xs text-ink-gray-4 shrink-0 whitespace-nowrap text-right pt-0.5">{{ formatTime(log.timestamp) }}</span>
      </div>
    </div>
    <EmptyState v-else icon="lucide-activity" title="No audit logs" description="Activity will be tracked here" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuditLogs } from '../composables/vault'
import { actionIcons, formatRelativeTime as formatTime } from '../composables/constants'
import EmptyState from '../components/EmptyState.vue'

const logs = useAuditLogs()
const logList = computed(() => logs.data?.logs || [])

function getSecretLabel(log) {
  if (log.secret) {
    return log.secret
  }
  if (log.details) {
    try {
      const detailsObj = typeof log.details === 'string' ? JSON.parse(log.details) : log.details
      if (detailsObj.title && detailsObj.deleted_secret_name) {
        return `${detailsObj.title} (${detailsObj.deleted_secret_name})`
      }
      if (detailsObj.title) {
        return detailsObj.title
      }
      if (detailsObj.deleted_secret_name) {
        return detailsObj.deleted_secret_name
      }
    } catch (e) {
    }
  }
  return ''
}
</script>
