<template>
  <div class="inline-flex items-center gap-2 min-w-0">
    <div class="size-6 rounded-full flex items-center justify-center shrink-0" :class="colorClass">
      <Icon :name="iconName" class="size-3" />
    </div>
    <span v-if="showLabel" class="truncate font-normal text-ink-gray-9">{{ label || type }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { typeIcons, typeColors } from '../composables/constants'

const props = defineProps({
  type: {
    type: String,
    default: 'Other',
  },
  showLabel: {
    type: Boolean,
    default: false,
  },
  label: {
    type: String,
    default: '',
  },
})

const iconName = computed(() => {
  const icon = typeIcons[props.type] || 'file'
  return icon.replace(/^lucide-/, '')
})
const colorClass = computed(() => typeColors[props.type] || 'bg-surface-gray-3 text-ink-gray-6')
</script>
