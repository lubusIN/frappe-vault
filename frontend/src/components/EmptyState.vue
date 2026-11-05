<template>
  <div class="flex-1 flex flex-col items-center justify-center h-full min-h-[16rem] text-center p-6 my-auto">
    <Icon :name="iconName" class="size-12 text-ink-gray-4 mb-4" />
    <h3 class="font-medium text-ink-gray-8 mb-1">{{ title }}</h3>
    <p class="text-sm text-ink-gray-5 mb-4">{{ description }}</p>
    <slot name="actions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  icon: { type: String, default: 'inbox' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})

const iconName = computed(() => {
  if (!props.icon) return 'inbox'
  return props.icon.replace(/^lucide-/, '')
})
</script>
