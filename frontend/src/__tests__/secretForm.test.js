import { describe, it, expect } from 'vitest'
import { validateTotpSecret } from '@/utils/secretForm'

describe('Secret Form Utilities & Validations', () => {
  describe('validateTotpSecret', () => {
    it('allows empty secret (optional field)', () => {
      const res = validateTotpSecret('')
      expect(res.ok).toBe(true)
      expect(res.normalized).toBe('')
    })

    it('rejects if user pastes a 6-digit TOTP code instead of base32 seed', () => {
      const res = validateTotpSecret('123456')
      expect(res.ok).toBe(false)
      expect(res.message).toContain('6-digit TOTP passcode')
    })

    it('sanitizes and normalizes valid Base32 secret with spaces and lowercase', () => {
      const res = validateTotpSecret(' jbsr g64t mm====== ')
      expect(res.ok).toBe(true)
      expect(res.normalized).toBe('JBSRG64TMM======')
    })

    it('rejects invalid characters outside Base32 alphabet (e.g. 0, 1, 8, 9)', () => {
      const res = validateTotpSecret('INVALID0189KEY')
      expect(res.ok).toBe(false)
      expect(res.message).toContain('Base32 keys must contain')
    })

    it('rejects keys shorter than 8 characters', () => {
      const res = validateTotpSecret('JBSWY')
      expect(res.ok).toBe(false)
    })

    it('rejects incorrect padding length', () => {
      const res = validateTotpSecret('JBSRG64TMM===') // Invalid padding count
      expect(res.ok).toBe(false)
      expect(res.message).toContain('Incorrect Base32 padding')
    })
  })
})

