import { computed, unref } from 'vue'
import { useStorage } from '@vueuse/core'

export function useColumnResize(storageKey, baseColumnsConfig) {
  const columnWidths = useStorage(storageKey, {})

  function handleColumnWidthUpdated(payload) {
    columnWidths.value[payload.key] = payload.width
  }

  const columns = computed(() => {
    const baseCols = unref(baseColumnsConfig)
    return baseCols.map(col => ({
      ...col,
      width: columnWidths.value[col.key] ?? col.width
    }))
  })

  return {
    columns,
    handleColumnWidthUpdated
  }
}
