import { describe, it, expect } from 'vitest'
import {
  getAllDescendants,
  flattenFolderTree,
  getParentFolderOptions,
  normalizeFolderParent,
} from '@/utils/folderTree'

describe('Folder Tree & Parenting Utilities', () => {
  const sampleTree = [
    {
      name: 'folder-root-1',
      folder_name: 'Engineering',
      can_write: true,
      children: [
        {
          name: 'folder-sub-1',
          folder_name: 'DevOps',
          can_write: true,
          children: [
            {
              name: 'folder-sub-1-1',
              folder_name: 'Kubernetes',
              can_write: true,
              children: [],
            },
          ],
        },
        {
          name: 'folder-sub-2',
          folder_name: 'Frontend',
          can_write: false,
          children: [],
        },
      ],
    },
    {
      name: 'folder-root-2',
      folder_name: 'Finance',
      can_write: true,
      children: [],
    },
  ]

  describe('getAllDescendants', () => {
    it('returns empty array when folder has no children', () => {
      const folder = { name: 'leaf', children: [] }
      expect(getAllDescendants(folder)).toEqual([])
    })

    it('recursively gathers all deep children with correct level hierarchy', () => {
      const root = sampleTree[0]
      const descendants = getAllDescendants(root)

      expect(descendants.length).toBe(3)
      expect(descendants.map(d => d.name)).toEqual([
        'folder-sub-1',
        'folder-sub-1-1',
        'folder-sub-2',
      ])
      expect(descendants[0].level).toBe(0)
      expect(descendants[1].level).toBe(1)
    })
  })

  describe('flattenFolderTree', () => {
    it('returns empty array for empty tree', () => {
      expect(flattenFolderTree([])).toEqual([])
    })

    it('flattens tree maintaining correct parent-before-child order and levels', () => {
      const flattened = flattenFolderTree(sampleTree)

      expect(flattened.length).toBe(5)
      expect(flattened[0]).toEqual({
        label: 'Engineering',
        value: 'folder-root-1',
        level: 0,
        can_write: true,
      })
      expect(flattened[1]).toEqual({
        label: 'DevOps',
        value: 'folder-sub-1',
        level: 1,
        can_write: true,
      })
      expect(flattened[2]).toEqual({
        label: 'Kubernetes',
        value: 'folder-sub-1-1',
        level: 2,
        can_write: true,
      })
      expect(flattened[3]).toEqual({
        label: 'Frontend',
        value: 'folder-sub-2',
        level: 1,
        can_write: false,
      })
      expect(flattened[4]).toEqual({
        label: 'Finance',
        value: 'folder-root-2',
        level: 0,
        can_write: true,
      })
    })
  })

  describe('getParentFolderOptions', () => {
    it('includes Root Level and all folders when no folder is being edited', () => {
      const options = getParentFolderOptions(sampleTree, null)
      expect(options[0]).toEqual({ label: '— Root Level —', value: '', level: 0 })
      expect(options.length).toBe(6) // 1 root + 5 folders
    })

    it('strictly forbids a folder from choosing itself as parent', () => {
      const options = getParentFolderOptions(sampleTree, { name: 'folder-root-2', children: [] })
      const optionValues = options.map(o => o.value)

      expect(optionValues).not.toContain('folder-root-2')
      expect(optionValues).toContain('')
      expect(optionValues).toContain('folder-root-1')
    })

    it('strictly forbids a folder from choosing any of its descendants as parent (circular prevention)', () => {
      const rootFolder = sampleTree[0] // Engineering
      const options = getParentFolderOptions(sampleTree, rootFolder)
      const optionValues = options.map(o => o.value)

      // Forbidden: root itself, sub-1, sub-1-1, sub-2
      expect(optionValues).not.toContain('folder-root-1')
      expect(optionValues).not.toContain('folder-sub-1')
      expect(optionValues).not.toContain('folder-sub-1-1')
      expect(optionValues).not.toContain('folder-sub-2')

      // Allowed: Root Level and Finance
      expect(optionValues).toEqual(['', 'folder-root-2'])
    })

    it('finds descendants in folderTree even when currentFolder omits children', () => {
      const options = getParentFolderOptions(sampleTree, { name: 'folder-root-1' })
      const optionValues = options.map(o => o.value)

      expect(optionValues).toEqual(['', 'folder-root-2'])
    })
  })

  describe('normalizeFolderParent', () => {
    it('returns empty string for null, undefined, or empty values', () => {
      expect(normalizeFolderParent(null)).toBe('')
      expect(normalizeFolderParent(undefined)).toBe('')
      expect(normalizeFolderParent('')).toBe('')
    })

    it('returns string unchanged when scalar ID is passed', () => {
      expect(normalizeFolderParent('folder-123')).toBe('folder-123')
    })

    it('extracts scalar value property when object is passed from Combobox', () => {
      expect(normalizeFolderParent({ label: 'DevOps', value: 'folder-sub-1' })).toBe('folder-sub-1')
    })

    it('returns empty string if object has no valid string value property', () => {
      expect(normalizeFolderParent({})).toBe('')
      expect(normalizeFolderParent({ label: 'DevOps' })).toBe('')
    })
  })
})

