import { describe, it, expect, beforeEach } from 'vitest'
import { useColumnResize } from '@/composables/useColumnResize'

describe('useColumnResize Composable', () => {
  const baseColumns = [
    { key: 'title', label: 'Title', width: '200px' },
    { key: 'type', label: 'Type', width: '120px' },
    { key: 'folder', label: 'Folder', width: '150px' },
  ]

  beforeEach(() => {
    localStorage.clear()
  })

  it('initializes with base column widths when no stored width exists', () => {
    const { columns } = useColumnResize('test-table-cols', baseColumns)
    expect(columns.value.map(c => c.width)).toEqual(['200px', '120px', '150px'])
  })

  it('updates width for specified column while preserving others', () => {
    const { columns, handleColumnWidthUpdated } = useColumnResize('test-table-cols', baseColumns)

    handleColumnWidthUpdated({ key: 'title', width: '300px' })

    const updatedCols = columns.value
    expect(updatedCols.find(c => c.key === 'title').width).toBe('300px')
    expect(updatedCols.find(c => c.key === 'type').width).toBe('120px')
    expect(updatedCols.find(c => c.key === 'folder').width).toBe('150px')
  })
})

