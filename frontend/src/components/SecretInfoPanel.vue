<template>
  <div v-if="secretData.notes" class="h-px w-full bg-outline-gray-2" />

  <article v-if="secretData.notes" class="space-y-2">
    <div class="flex items-center justify-between cursor-pointer select-none group" @click="notesOpen = !notesOpen">
      <h3 class="text-xs font-semibold text-ink-gray-5 uppercase tracking-wider group-hover:text-ink-gray-7 transition-colors">Notes</h3>
      <span class="lucide-chevron-down w-4 h-4 text-ink-gray-4 transition-transform duration-200" :class="{ '-rotate-90': !notesOpen }" aria-hidden="true" />
    </div>
    <div v-show="notesOpen" class="mt-2.5 py-1 text-sm text-ink-gray-8 leading-relaxed whitespace-pre-wrap font-normal">{{ secretData.notes }}</div>
  </article>

  <div class="h-px w-full bg-outline-gray-2" />

  <article class="space-y-2">
    <div class="flex items-center justify-between cursor-pointer select-none group" @click="metaOpen = !metaOpen">
      <h3 class="text-xs font-semibold text-ink-gray-5 uppercase tracking-wider group-hover:text-ink-gray-7 transition-colors">Metadata</h3>
      <span class="lucide-chevron-down w-4 h-4 text-ink-gray-4 transition-transform duration-200" :class="{ '-rotate-90': !metaOpen }" aria-hidden="true" />
    </div>
    <div v-show="metaOpen" class="mt-3 space-y-2.5 py-1">
      <div v-if="secretData.secret_type === 'Password' && secretData.password_strength" class="flex items-center justify-between py-1 text-sm">
        <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Strength</span>
        <div class="min-w-0 flex-1 flex justify-end">
          <StrengthBadge :strength="secretData.password_strength" size="sm" />
        </div>
      </div>

      <div class="flex items-center justify-between py-1 text-sm">
        <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Last Accessed</span>
        <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">{{ formatDateOnly(secretData.last_accessed) }}</span>
      </div>

      <div class="flex items-center justify-between py-1 text-sm">
        <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Access Count</span>
        <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">{{ secretData.access_count || 0 }} times</span>
      </div>

      <div class="flex items-center justify-between py-1 text-sm">
        <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Last Changed</span>
        <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">{{ formatDateOnly(secretData.password_last_changed) }}</span>
      </div>
    </div>
  </article>
</template>

<script setup>
import { ref } from 'vue'
import StrengthBadge from './StrengthBadge.vue'
import { formatDateOnly } from '../composables/constants'

const props = defineProps({
  secretData: {
    type: Object,
    required: true
  }
})

const notesOpen = ref(true)
const metaOpen = ref(true)
</script>
