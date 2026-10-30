<template>
  <!-- No active sorts: field picker button opens directly -->
  <Popover v-if="!sortEntries.length" side="bottom" align="end" :bare="true">
    <template #trigger>
      <Button label="Sort">
        <template #prefix>
          <SortIcon class="h-4" />
        </template>
      </Button>
    </template>
    <template #default="{ close }">
      <div class="my-1 max-h-64 min-w-44 overflow-y-auto rounded-lg bg-surface-elevation-2 p-1.5 shadow-2xl ring-1 ring-black ring-opacity-5">
        <div class="mb-1 px-1">
          <FormControl
            v-model="fieldSearch"
            type="text"
            placeholder="Search..."
            class="w-full"
          />
        </div>
        <div
          v-for="field in availableFields"
          :key="field.fieldname"
          class="cursor-pointer rounded-md px-2.5 py-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2 transition-colors"
          @click="addSort(field); fieldSearch = ''; close()"
        >
          {{ field.label }}
        </div>
        <div v-if="!availableFields.length" class="px-2.5 py-2 text-sm text-ink-gray-5">
          No fields available
        </div>
      </div>
    </template>
  </Popover>

  <!-- Active sorts: full popover panel -->
  <Popover v-else side="bottom" align="end" :bare="true">
    <template #trigger>
      <div class="flex items-center cursor-pointer">
        <!-- Single sort: direction toggle + field label -->
        <template v-if="sortEntries.length === 1">
          <Button
            class="rounded-r-none border-r border-outline-gray-1"
            :icon="sortEntries[0].direction === 'asc' ? AscendingIcon : DescendingIcon"
            @click.stop="toggleDirection(0)"
          />
          <Button
            :label="getSortLabel(sortEntries[0])"
            class="shrink-0 rounded-l-none"
          />
        </template>
        <!-- Multiple sorts: icon + label + count -->
        <template v-else>
          <Button label="Sort">
            <template #prefix>
              <SortIcon class="h-4" />
            </template>
            <template #suffix>
              <div
                class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-elevation-1 pt-px text-xs font-medium text-ink-gray-8 shadow-sm"
              >
                {{ sortEntries.length }}
              </div>
            </template>
          </Button>
        </template>
      </div>
    </template>
    <template #default="{ close }">
      <div
        class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
      >
        <div class="min-w-60 p-2">
          <!-- Sort rows -->
          <div v-if="sortEntries.length" class="mb-3 flex flex-col gap-2">
            <div
              v-for="(sort, i) in sortEntries"
              :key="sort.fieldname + i"
              class="flex items-center gap-1"
            >
              <div class="flex flex-1">
                <Button
                  size="md"
                  class="rounded-r-none border-r border-outline-gray-1"
                  :icon="sort.direction === 'asc' ? AscendingIcon : DescendingIcon"
                  @click="toggleDirection(i)"
                />
                <FormControl
                  type="select"
                  :modelValue="sort.fieldname"
                  :options="getSortFieldOptions(sort.fieldname)"
                  class="flex-1 rounded-l-none"
                  @update:modelValue="(val) => updateSortField(val, i)"
                />
              </div>
              <Button variant="ghost" icon="lucide-x" @click="removeSort(i)" />
            </div>
          </div>
          <div
            v-else
            class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5"
          >
            Empty - Choose a field to sort by
          </div>
          <!-- Add Sort + Clear -->
          <div v-if="!isAddingSort" class="flex items-center justify-between gap-2">
            <Button
              class="!text-ink-gray-5"
              variant="ghost"
              label="Add Sort"
              iconLeft="lucide-plus"
              @click="isAddingSort = true"
            />
            <Button
              v-if="sortEntries.length"
              class="!text-ink-gray-5"
              variant="ghost"
              label="Clear Sort"
              @click="clearSort(close)"
            />
          </div>
          <div v-else class="mt-1 border-t border-outline-gray-2 pt-2">
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-sm font-medium text-ink-gray-7 pl-1">Select Field</span>
              <Button variant="ghost" icon="lucide-x" class="!h-6 !w-6 !p-1 text-ink-gray-5" @click="isAddingSort = false; fieldSearch = ''" />
            </div>
            <FormControl
              v-model="fieldSearch"
              type="text"
              placeholder="Search..."
              class="w-full mb-2"
            />
            <div class="max-h-40 overflow-y-auto rounded-lg border border-outline-gray-2 bg-surface-base p-1">
              <div
                v-for="field in availableFields"
                :key="field.fieldname"
                class="cursor-pointer rounded-md px-2.5 py-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-2 transition-colors"
                @click="addSort(field); isAddingSort = false; fieldSearch = ''"
              >
                {{ field.label }}
              </div>
              <div v-if="!availableFields.length" class="px-2.5 py-2 text-sm text-ink-gray-5 text-center">
                No fields available
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { ref, computed, h } from 'vue'
import { FormControl, Popover, Button } from 'frappe-ui'
import SortIcon from './SortIcon.vue'

const AscendingIcon = {
  render: () => h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', class: 'h-4 w-4' }, [
    h('path', { d: 'M12 5v14' }),
    h('path', { d: 'M6 11l6-6 6 6' }),
  ])
}

const DescendingIcon = {
  render: () => h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', class: 'h-4 w-4' }, [
    h('path', { d: 'M12 5v14' }),
    h('path', { d: 'M18 13l-6 6-6-6' }),
  ])
}

const props = defineProps({
  fields: { type: Array, default: () => [] },
})

const emit = defineEmits(['update'])

const sortEntries = ref([])
const fieldSearch = ref('')
const isAddingSort = ref(false)

const availableFields = computed(() => {
  const usedFieldnames = new Set(sortEntries.value.map(s => s.fieldname))
  let fields = (props.fields || []).filter(f => !usedFieldnames.has(f.fieldname))
  if (fieldSearch.value) {
    const q = fieldSearch.value.toLowerCase()
    fields = fields.filter(f => f.label.toLowerCase().includes(q))
  }
  return fields
})

function getSortFieldOptions(currentFieldname) {
  return (props.fields || []).map(f => ({
    label: f.label,
    value: f.fieldname,
  }))
}

function getSortLabel(sort) {
  const field = (props.fields || []).find(f => f.fieldname === sort.fieldname)
  return field?.label || sort.fieldname
}

function addSort(field) {
  sortEntries.value.push({
    fieldname: field.fieldname,
    direction: 'asc',
  })
  emitSort()
}

function updateSortField(fieldname, index) {
  sortEntries.value[index].fieldname = fieldname
  emitSort()
}

function toggleDirection(index) {
  sortEntries.value[index].direction =
    sortEntries.value[index].direction === 'asc' ? 'desc' : 'asc'
  emitSort()
}

function removeSort(index) {
  sortEntries.value.splice(index, 1)
  emitSort()
}

function clearSort(closeFn) {
  sortEntries.value = []
  emitSort()
  if (closeFn) closeFn()
}

function emitSort() {
  if (!sortEntries.value.length) {
    emit('update', 'modified desc')
    return
  }
  const orderBy = sortEntries.value
    .map(s => `${s.fieldname} ${s.direction}`)
    .join(', ')
  emit('update', orderBy)
}
</script>
