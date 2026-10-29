<template>
  <div class="flex-1 overflow-y-auto p-3">
    <GridLayout
      v-if="items.length > 0"
      v-model:layout="layout"
      class="h-fit w-full"
      :class="[editing ? 'mb-[20rem] !select-none' : '']"
      :col-num="20"
      :row-height="42"
      :is-draggable="editing"
      :is-resizable="editing"
      :responsive="true"
      :breakpoints="{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }"
      :cols="{ lg: 20, md: 20, sm: 10, xs: 5, xxs: 5 }"
    >
      <template #item="{ item: gridItem }">
        <div class="group/card relative flex h-full w-full p-2 text-ink-gray-8">
          <div
            class="flex h-full w-full items-center justify-center"
            :class="
              editing
                ? 'pointer-events-none [&>div:first-child]:rounded-2xl [&>div:first-child]:group-hover/card:ring-2 [&>div:first-child]:group-hover/card:ring-outline-gray-2'
                : ''
            "
          >
            <DashboardItem
              v-if="getItemByIndex(gridItem.i)"
              :index="getItemIndex(gridItem.i)"
              :item="getItemByIndex(gridItem.i)"
              :editing="editing"
            />
          </div>
          <div
            v-if="editing"
            class="flex absolute right-2 top-2 bg-surface-gray-6 rounded cursor-pointer opacity-0 group-hover/card:opacity-100 z-10 transition-opacity"
          >
            <div
              class="rounded p-1.5 hover:bg-surface-gray-5"
              @click="removeItem(gridItem.i)"
            >
              <span class="lucide-trash-2 w-3.5 h-3.5 text-white" aria-hidden="true" />
            </div>
          </div>
        </div>
      </template>
    </GridLayout>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { GridLayout } from 'grid-layout-plus'
import DashboardItem from './DashboardItem.vue'

const props = defineProps({
  editing: { type: Boolean, default: false },
})

const items = defineModel({ type: Array, default: () => [] })

const layout = computed({
  get() {
    return items.value.map((item) => item.layout)
  },
  set(newLayout) {
    if (!props.editing || !Array.isArray(newLayout)) return
    newLayout.forEach((l) => {
      const found = items.value.find((item) => item.layout.i === l.i)
      if (found) {
        found.layout = { ...found.layout, ...l }
      }
    })
  },
})

function getItemByIndex(id) {
  return items.value.find((item) => item.layout?.i === id)
}

function getItemIndex(id) {
  return items.value.findIndex((item) => item.layout?.i === id)
}

function removeItem(id) {
  const idx = getItemIndex(id)
  if (idx !== -1) {
    items.value.splice(idx, 1)
  }
}
</script>
