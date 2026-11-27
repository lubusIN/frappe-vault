/**
 * Utility functions for Folder Tree operations and parenting validation
 */

/**
 * Recursively retrieves all descendants of a folder.
 * @param {Object} folder - The folder node with potential `children` array
 * @param {number} level - Depth level
 * @returns {Array} Array of descendant folder objects with level indicator
 */
export function getAllDescendants(folder, level = 0) {
  let descendants = []
  if (folder && folder.children && Array.isArray(folder.children)) {
    folder.children.forEach(child => {
      descendants.push({ ...child, level })
      descendants = descendants.concat(getAllDescendants(child, level + 1))
    })
  }
  return descendants
}

/**
 * Flattens a recursive tree of folders into a linear list with indentation levels.
 * @param {Array} nodes - Array of root/tree folder nodes
 * @param {number} level - Starting depth level
 * @returns {Array} Array of { label, value, level, can_write }
 */
export function flattenFolderTree(nodes, level = 0) {
  if (!nodes || !Array.isArray(nodes)) return []
  const options = []
  for (const node of nodes) {
    options.push({
      label: node.folder_name || node.label || node.name,
      value: node.name || node.value,
      level,
      can_write: Boolean(node.can_write),
    })
    if (node.children?.length) {
      options.push(...flattenFolderTree(node.children, level + 1))
    }
  }
  return options
}

function findNodeInTree(nodes, targetName) {
  if (!Array.isArray(nodes)) return null
  for (const node of nodes) {
    if (node.name === targetName) return node
    if (node.children?.length) {
      const found = findNodeInTree(node.children, targetName)
      if (found) return found
    }
  }
  return null
}

/**
 * Computes valid parent folder options for editing or moving a folder.
 * Excludes the folder itself and all of its descendants to prevent circular trees.
 * @param {Array} folderTree - Full folder tree
 * @param {Object|null} currentFolder - The folder being edited or moved
 * @returns {Array} Array of selectable parent options starting with Root Level
 */
export function getParentFolderOptions(folderTree, currentFolder = null) {
  const flattened = flattenFolderTree(folderTree)
  const rootOption = { label: '— Root Level —', value: '', level: 0 }

  if (!currentFolder || !currentFolder.name) {
    return [rootOption, ...flattened]
  }

  const targetNode = findNodeInTree(folderTree, currentFolder.name) || currentFolder
  const forbidden = new Set([
    currentFolder.name,
    ...getAllDescendants(targetNode).map(d => d.name),
  ])

  return [rootOption, ...flattened.filter(o => !forbidden.has(o.value))]
}

/**
 * Normalizes combobox model values to guarantee a scalar string ID.
 * Handles scalar strings, object representations ({ label, value }), and null/undefined.
 * @param {string|Object|null} value
 * @returns {string} The normalized scalar folder ID or empty string
 */
export function normalizeFolderParent(value) {
  if (!value) return ''
  if (typeof value === 'object') {
    return typeof value.value === 'string' ? value.value : ''
  }
  return String(value)
}

