<template>
  <Popover side="bottom" align="end" :bare="true">
    <template #trigger>
      <Button label="Columns">
        <template #prefix>
          <ColumnsIcon class="h-4" />
        </template>
      </Button>
    </template>
    <template #default="{ close }">
      <div
        class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 p-1.5 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
      >
        <!-- Column List (draggable) -->
        <Draggable
          :list="visibleColumns"
          item-key="key"
          handle=".drag-handle"
          :animation="200"
          @end="emitColumns"
        >
          <template #item="{ element }">
            <div
              class="flex cursor-grab items-center justify-between gap-6 rounded px-2 py-1.5 text-base text-ink-gray-8 hover:bg-surface-gray-2"
            >
              <div class="flex items-center gap-2">
                <svg class="drag-handle h-3.5 w-3.5 shrink-0 text-ink-gray-4 cursor-grab" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="9" cy="5" r="1" fill="currentColor" />
                  <circle cx="15" cy="5" r="1" fill="currentColor" />
                  <circle cx="9" cy="12" r="1" fill="currentColor" />
                  <circle cx="15" cy="12" r="1" fill="currentColor" />
                  <circle cx="9" cy="19" r="1" fill="currentColor" />
                  <circle cx="15" cy="19" r="1" fill="currentColor" />
                </svg>
                <div>{{ element.label }}</div>
              </div>
              <div class="flex cursor-pointer items-center gap-0.5">
                <Button
                  v-if="!element.fixed"
                  variant="ghost"
                  class="!h-5 w-5 !p-1"
                  icon="lucide-x"
                  @click="removeColumn(element)"
                />
              </div>
            </div>
          </template>
        </Draggable>

        <!-- Add Column + Reset -->
        <div
          class="mt-1.5 flex flex-col gap-1 border-t border-outline-gray-modals pt-1.5"
        >
          <div v-if="!isAddingColumn">
            <Button
              class="w-full !justify-start !text-ink-gray-5"
              variant="ghost"
              label="Add Column"
              iconLeft="lucide-plus"
              @click="isAddingColumn = true"
            />
          </div>
          <div v-else class="mt-1 border-t border-outline-gray-2 pt-2">
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-sm font-medium text-ink-gray-7 pl-1">Select Field</span>
              <Button variant="ghost" icon="lucide-x" class="!h-6 !w-6 !p-1 text-ink-gray-5" @click="isAddingColumn = false; fieldSearch = ''" />
            </div>
            <FormControl
              v-model="fieldSearch"
              type="text"
              placeholder="Search..."
              class="w-full mb-2"
            />
            <div class="max-h-40 overflow-y-auto rounded-lg border border-outline-gray-2 bg-surface-base p-1">
              <div
                v-for="field in availableColumns"
                :key="field.fieldname"
                class="cursor-pointer rounded-md px-2.5 py-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2 transition-colors"
                @click="addColumn(field); isAddingColumn = false; fieldSearch = ''"
              >
                {{ field.label }}
              </div>
              <div v-if="!availableColumns.length" class="px-2.5 py-2 text-sm text-ink-gray-5 text-center">
                No more fields available
              </div>
            </div>
          </div>
          <Button
            v-if="hasChanges"
            class="w-full !justify-start !text-ink-gray-5"
            variant="ghost"
            label="Reset to Default"
            iconLeft="lucide-rotate-ccw"
            @click="resetToDefault(close)"
          />
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { FormControl, Popover, Button } from 'frappe-ui'
import Draggable from 'vuedraggable'
import ColumnsIcon from './ColumnsIcon.vue'

const props = defineProps({
  defaultColumns: { type: Array, default: () => [] },
  allFields: { type: Array, default: () => [] },
})

const emit = defineEmits(['update'])

const visibleColumns = ref([])
const fieldSearch = ref('')
const isAddingColumn = ref(false)
const initializedDefaults = ref(false)

watch(
  () => props.defaultColumns,
  (cols) => {
    if (cols?.length && !initializedDefaults.value) {
      visibleColumns.value = cols.map(c => ({ ...c }))
      initializedDefaults.value = true
    }
  },
  { immediate: true }
)

const hasChanges = computed(() => {
  if (visibleColumns.value.length !== props.defaultColumns.length) return true
  return visibleColumns.value.some((col, i) => col.key !== props.defaultColumns[i]?.key)
})

const availableColumns = computed(() => {
  const visibleKeys = new Set(visibleColumns.value.map(c => c.key))
  let fields = (props.allFields || []).filter(f => !visibleKeys.has(f.fieldname))
  if (fieldSearch.value) {
    const q = fieldSearch.value.toLowerCase()
    fields = fields.filter(f => f.label.toLowerCase().includes(q))
  }
  return fields
})

function addColumn(field) {
  const align = ['Float', 'Int', 'Currency'].includes(field.fieldtype) ? 'right' : 'left'
  visibleColumns.value.push({
    label: field.label,
    key: field.fieldname,
    width: '10rem',
    align,
  })
  fieldSearch.value = ''
  emitColumns()
}

function removeColumn(col) {
  visibleColumns.value = visibleColumns.value.filter(c => c.key !== col.key)
  emitColumns()
}

function resetToDefault(closeFn) {
  visibleColumns.value = props.defaultColumns.map(c => ({ ...c }))
  emitColumns()
  if (closeFn) closeFn()
}

function emitColumns() {
  emit('update', [...visibleColumns.value])
}
</script>
