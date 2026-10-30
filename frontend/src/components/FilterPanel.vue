<template>
  <Popover side="bottom" align="end" :bare="true">
    <template #trigger="{ close }">
      <div class="flex items-center cursor-pointer">
        <Button
          label="Filter"
          :iconLeft="FilterIcon"
          :class="filterCount ? 'rounded-r-none' : ''"
        >
          <template v-if="filterCount" #suffix>
            <div
              class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-elevation-1 pt-px text-xs font-medium text-ink-gray-8 shadow-sm"
            >
              {{ filterCount }}
            </div>
          </template>
        </Button>
        <Button
          v-if="filterCount"
          tooltip="Clear All Filters"
          class="rounded-l-none border-l border-outline-gray-1"
          icon="lucide-x"
          @click.stop="clearAllFilters(close)"
        />
      </div>
    </template>
    <template #default="{ close }">
      <div
        class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
      >
        <div class="min-w-72 p-2 sm:min-w-[400px]">
          <!-- Active Filters -->
          <template v-if="activeFilters.length">
            <div
              v-for="(f, i) in activeFilters"
              :key="i"
              class="mb-3"
            >
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <div class="w-13 pl-2 text-end text-base text-ink-gray-5">
                    {{ i === 0 ? 'Where' : 'And' }}
                  </div>
                  <div class="!min-w-[140px]">
                    <FormControl
                      type="select"
                      :modelValue="f.fieldname"
                      :options="getFieldOptions(f.fieldname)"
                      @update:modelValue="(val) => updateFilterField(val, i)"
                    />
                  </div>
                  <div>
                    <FormControl
                      type="select"
                      :modelValue="f.operator"
                      :options="getOperators(f.fieldtype)"
                      @update:modelValue="(val) => updateOperator(val, i)"
                    />
                  </div>
                  <div class="!min-w-[140px]">
                    <component
                      :is="getValueControl(f)"
                      v-model="f.value"
                      @change="(v) => updateValue(v, i)"
                      @update:modelValue="(v) => updateValue(v, i)"
                    />
                  </div>
                </div>
                <Button
                  variant="ghost"
                  icon="lucide-x"
                  @click="removeFilter(i)"
                />
              </div>
            </div>
          </template>
          <div
            v-else
            class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5"
          >
            Empty - Choose a field to filter by
          </div>
          <!-- Add Filter + Clear -->
          <div v-if="!isAddingFilter" class="flex items-center justify-between gap-2 mt-1">
            <Button
              class="!text-ink-gray-5"
              variant="ghost"
              label="Add Filter"
              iconLeft="lucide-plus"
              @click="isAddingFilter = true"
            />
            <Button
              v-if="activeFilters.length"
              class="!text-ink-gray-5"
              variant="ghost"
              label="Clear All Filters"
              @click="clearAllFilters(close)"
            />
          </div>
          <div v-else class="mt-1 border-t border-outline-gray-2 pt-2">
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-sm font-medium text-ink-gray-7">Select Field</span>
              <Button variant="ghost" icon="lucide-x" class="!h-6 !w-6 !p-1 text-ink-gray-5" @click="isAddingFilter = false; fieldSearch = ''" />
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
                @click="addFilter(field); isAddingFilter = false; fieldSearch = ''"
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
import { ref, computed, h, watch } from 'vue'
import { FormControl, Popover, Button } from 'frappe-ui'
import FilterIcon from './FilterIcon.vue'

const props = defineProps({
  fields: { type: Array, default: () => [] },
})

const emit = defineEmits(['update'])

const activeFilters = ref([])
const fieldSearch = ref('')
const isAddingFilter = ref(false)

const filterCount = computed(() => activeFilters.value.length)

const availableFields = computed(() => {
  const usedFieldnames = new Set(activeFilters.value.map(f => f.fieldname))
  let fields = (props.fields || []).filter(f => !usedFieldnames.has(f.fieldname))
  if (fieldSearch.value) {
    const q = fieldSearch.value.toLowerCase()
    fields = fields.filter(f => f.label.toLowerCase().includes(q))
  }
  return fields
})

function getFieldOptions(currentFieldname) {
  return (props.fields || []).map(f => ({
    label: f.label,
    value: f.fieldname,
  }))
}

function getOperators(fieldtype) {
  if (['Select', 'Check'].includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
    ]
  }
  if (['Date', 'Datetime'].includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: 'After', value: '>' },
      { label: 'Before', value: '<' },
      { label: 'After or On', value: '>=' },
      { label: 'Before or On', value: '<=' },
    ]
  }
  if (['Int', 'Float', 'Currency'].includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: '>', value: '>' },
      { label: '<', value: '<' },
      { label: '>=', value: '>=' },
      { label: '<=', value: '<=' },
    ]
  }
  if (['Link'].includes(fieldtype)) {
    return [
      { label: 'Equals', value: '=' },
      { label: 'Not Equals', value: '!=' },
      { label: 'Like', value: 'LIKE' },
      { label: 'Not Like', value: 'NOT LIKE' },
      { label: 'Is Set', value: 'is' },
    ]
  }
  // Data, Text, etc.
  return [
    { label: 'Equals', value: '=' },
    { label: 'Not Equals', value: '!=' },
    { label: 'Like', value: 'LIKE' },
    { label: 'Not Like', value: 'NOT LIKE' },
    { label: 'Is Set', value: 'is' },
  ]
}

function getDefaultOperator(fieldtype) {
  if (['Select', 'Check'].includes(fieldtype)) return '='
  if (['Date', 'Datetime'].includes(fieldtype)) return '='
  if (['Int', 'Float', 'Currency'].includes(fieldtype)) return '='
  return 'LIKE'
}

function getDefaultValue(field) {
  if (field.fieldtype === 'Select' && field.options) {
    const opts = String(field.options).split('\n').filter(Boolean)
    return opts[0] || ''
  }
  if (field.fieldtype === 'Check') return 'Yes'
  return ''
}

function getValueControl(f) {
  if (f.operator === 'is') {
    return h(FormControl, {
      type: 'select',
      options: [
        { label: 'Set', value: 'set' },
        { label: 'Not Set', value: 'not set' },
      ],
      modelValue: f.value,
      'onUpdate:modelValue': (v) => {
        f.value = v
        emitFilters()
      },
    })
  }

  if (['Select'].includes(f.fieldtype) && f.options) {
    const opts = String(f.options).split('\n').filter(Boolean).map(o => ({
      label: o,
      value: o,
    }))
    return h(FormControl, {
      type: 'select',
      options: opts,
      modelValue: f.value,
      'onUpdate:modelValue': (v) => {
        f.value = v
        emitFilters()
      },
    })
  }

  if (f.fieldtype === 'Check') {
    return h(FormControl, {
      type: 'select',
      options: [
        { label: 'Yes', value: 'Yes' },
        { label: 'No', value: 'No' },
      ],
      modelValue: f.value,
      'onUpdate:modelValue': (v) => {
        f.value = v
        emitFilters()
      },
    })
  }

  if (['Date'].includes(f.fieldtype)) {
    return h(FormControl, { type: 'date', modelValue: f.value })
  }

  if (['Int', 'Float', 'Currency'].includes(f.fieldtype)) {
    return h(FormControl, { type: 'number' })
  }

  return h(FormControl, { type: 'text', placeholder: 'Value...' })
}

function addFilter(field) {
  activeFilters.value.push({
    fieldname: field.fieldname,
    fieldtype: field.fieldtype,
    label: field.label,
    options: field.options || '',
    operator: getDefaultOperator(field.fieldtype),
    value: getDefaultValue(field),
  })
  fieldSearch.value = ''
  emitFilters()
}

function updateFilterField(fieldname, index) {
  const field = (props.fields || []).find(f => f.fieldname === fieldname)
  if (!field) return
  activeFilters.value[index] = {
    fieldname: field.fieldname,
    fieldtype: field.fieldtype,
    label: field.label,
    options: field.options || '',
    operator: getDefaultOperator(field.fieldtype),
    value: getDefaultValue(field),
  }
  emitFilters()
}

function updateOperator(operator, index) {
  activeFilters.value[index].operator = operator
  if (operator === 'is') {
    activeFilters.value[index].value = 'set'
  }
  emitFilters()
}

function updateValue(value, index) {
  const val = value?.target ? value.target.value : value
  activeFilters.value[index].value = val
  emitFilters()
}

function removeFilter(index) {
  activeFilters.value.splice(index, 1)
  emitFilters()
}

function clearAllFilters(closeFn) {
  activeFilters.value = []
  emitFilters()
  if (closeFn) closeFn()
}

function emitFilters() {
  const result = {}
  for (const f of activeFilters.value) {
    if (f.operator === 'is') {
      result[f.fieldname] = ['is', f.value]
    } else if (f.operator === '=') {
      if (f.fieldtype === 'Check') {
        result[f.fieldname] = f.value === 'Yes' ? 1 : 0
      } else {
        result[f.fieldname] = f.value
      }
    } else if (['LIKE', 'NOT LIKE'].includes(f.operator)) {
      let val = f.value
      if (val && !val.includes('%')) val = `%${val}%`
      result[f.fieldname] = [f.operator, val]
    } else {
      result[f.fieldname] = [f.operator, f.value]
    }
  }
  emit('update', result)
}

defineExpose({ clearAllFilters })
</script>
