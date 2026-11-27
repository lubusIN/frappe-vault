import { describe, it, expect } from 'vitest'
import {
  SECRET_TYPES,
  secretTypeOptions,
  typeIcons,
  strengthTheme,
  permissionTheme,
  formatDateOnly,
} from '@/composables/constants'

describe('Application Constants & Formatters', () => {
  it('defines 8 core secret types', () => {
    expect(SECRET_TYPES).toEqual([
      'Password',
      'API Key',
      'Note',
      'SSH Key',
      'Media',
      'Credit Card',
      'Database',
      'Other',
    ])
  })

  it('maps all secret types to matching select options', () => {
    expect(secretTypeOptions.length).toBe(SECRET_TYPES.length)
    expect(secretTypeOptions[0]).toEqual({ label: 'Password', value: 'Password' })
  })

  it('maps each secret type to an icon without missing entries', () => {
    SECRET_TYPES.forEach(type => {
      expect(typeIcons[type]).toBeDefined()
      expect(typeof typeIcons[type]).toBe('string')
    })
  })

  it('maps permission levels to correct badge themes', () => {
    expect(permissionTheme['View Only']).toBe('gray')
    expect(permissionTheme['View & Copy']).toBe('blue')
    expect(permissionTheme['Edit']).toBe('orange')
    expect(permissionTheme['Full Control']).toBe('green')
    expect(permissionTheme['Revoked']).toBe('red')
  })

  it('maps password strength levels to appropriate color themes', () => {
    expect(strengthTheme.weak).toBe('red')
    expect(strengthTheme.fair).toBe('orange')
    expect(strengthTheme.good).toBe('blue')
    expect(strengthTheme.strong).toBe('green')
    expect(strengthTheme.excellent).toBe('green')
  })

  describe('formatDateOnly', () => {
    it('returns "Never" when given null or empty date', () => {
      expect(formatDateOnly(null)).toBe('Never')
      expect(formatDateOnly('')).toBe('Never')
    })

    it('formats valid ISO dates into readable US string', () => {
      const formatted = formatDateOnly('2026-10-30T10:00:00Z')
      expect(formatted).toContain('2026')
      expect(formatted).toContain('Oct')
    })
  })
})

