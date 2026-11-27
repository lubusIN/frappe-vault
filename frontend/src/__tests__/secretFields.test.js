import { describe, it, expect } from 'vitest'
import { secretFieldsConfig } from '@/composables/secretFields'
import { SECRET_TYPES } from '@/composables/constants'

describe('Secret Fields Configuration', () => {
  it('provides a fields configuration for every defined secret type', () => {
    SECRET_TYPES.forEach(type => {
      expect(secretFieldsConfig[type]).toBeDefined()
      expect(Array.isArray(secretFieldsConfig[type])).toBe(true)
    })
  })

  it('configures Password type with essential credentials and TOTP', () => {
    const fieldNames = secretFieldsConfig['Password'].map(f => f.name)
    expect(fieldNames).toContain('url')
    expect(fieldNames).toContain('username')
    expect(fieldNames).toContain('email')
    expect(fieldNames).toContain('password')
    expect(fieldNames).toContain('totp_secret')

    const passwordField = secretFieldsConfig['Password'].find(f => f.name === 'password')
    expect(passwordField.type).toBe('password')
    expect(passwordField.mono).toBe(true)
  })

  it('configures Database type with host, port, db name, and password', () => {
    const fieldNames = secretFieldsConfig['Database'].map(f => f.name)
    expect(fieldNames).toContain('db_host')
    expect(fieldNames).toContain('db_port')
    expect(fieldNames).toContain('db_name')
    expect(fieldNames).toContain('username')
    expect(fieldNames).toContain('db_password')
  })

  it('configures Credit Card type with cardholder, number, expiry, and CVV', () => {
    const fieldNames = secretFieldsConfig['Credit Card'].map(f => f.name)
    expect(fieldNames).toContain('card_holder')
    expect(fieldNames).toContain('card_number')
    expect(fieldNames).toContain('card_expiry')
    expect(fieldNames).toContain('card_cvv')

    const cvv = secretFieldsConfig['Credit Card'].find(f => f.name === 'card_cvv')
    expect(cvv.type).toBe('password')
  })

  it('configures Media type with attachment file field', () => {
    const attachmentField = secretFieldsConfig['Media'].find(f => f.name === 'attachment')
    expect(attachmentField).toBeDefined()
    expect(attachmentField.type).toBe('file')
  })

  it('configures SSH Key with textarea for private key', () => {
    const privateKey = secretFieldsConfig['SSH Key'].find(f => f.name === 'ssh_private_key')
    expect(privateKey).toBeDefined()
    expect(privateKey.type).toBe('textarea')
    expect(privateKey.mono).toBe(true)
  })
})

