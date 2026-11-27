import { describe, it, expect } from 'vitest'
import {
  parseDetails,
  getActivityText,
  getActionMainText,
  hasActivityDetails,
  getDetailIcon,
  getActivityDetailText,
} from '@/utils/activity'

describe('Activity & Audit Log Utilities', () => {
  describe('parseDetails', () => {
    it('returns empty object for falsy details', () => {
      expect(parseDetails(null)).toEqual({})
      expect(parseDetails('')).toEqual({})
    })

    it('returns object unchanged if already parsed', () => {
      const obj = { field: 'password' }
      expect(parseDetails(obj)).toBe(obj)
    })

    it('parses valid JSON string', () => {
      expect(parseDetails('{"recipient": "admin@example.com"}')).toEqual({
        recipient: 'admin@example.com',
      })
    })

    it('returns empty object on JSON syntax error', () => {
      expect(parseDetails('invalid-json{')).toEqual({})
    })
  })

  describe('getActivityText', () => {
    it('formats standard CRUD actions', () => {
      expect(getActivityText({ action: 'Created' })).toBe('created this secret')
      expect(getActivityText({ action: 'Updated' })).toBe('updated this secret')
      expect(getActivityText({ action: 'Deleted' })).toBe('deleted this secret')
      expect(getActivityText({ action: 'Viewed' })).toBe('viewed this secret')
    })

    it('formats Copied action with specific field', () => {
      expect(getActivityText({ action: 'Copied', details: JSON.stringify({ field: 'api_key' }) })).toBe(
        'copied the api_key field'
      )
    })

    it('formats Shared action with recipient and permission level', () => {
      const text = getActivityText({
        action: 'Shared',
        details: JSON.stringify({ recipient: 'Jane Doe', permission: 'Full Control' }),
      })
      expect(text).toBe('shared this secret with Jane Doe (Full Control)')
    })

    it('formats Unshared action with recipient', () => {
      const text = getActivityText({
        action: 'Unshared',
        details: JSON.stringify({ recipient: 'John Doe' }),
      })
      expect(text).toBe('revoked access for John Doe')
    })
  })

  describe('getActionMainText', () => {
    it('maps all main actions to user-friendly titles', () => {
      expect(getActionMainText({ action: 'Created' })).toBe('created this secret')
      expect(getActionMainText({ action: 'Copied' })).toBe('copied secret credentials')
      expect(getActionMainText({ action: 'Shared' })).toBe('shared access to this secret')
      expect(getActionMainText({ action: 'Unshared' })).toBe('revoked secret access')
    })
  })

  describe('hasActivityDetails and getDetailIcon', () => {
    it('returns true only for actions with extra metadata (Copied, Shared, Unshared)', () => {
      expect(hasActivityDetails({ action: 'Copied' })).toBe(true)
      expect(hasActivityDetails({ action: 'Shared' })).toBe(true)
      expect(hasActivityDetails({ action: 'Unshared' })).toBe(true)
      expect(hasActivityDetails({ action: 'Created' })).toBe(false)
      expect(hasActivityDetails({ action: 'Viewed' })).toBe(false)
    })

    it('maps actions to expected icon identifiers', () => {
      expect(getDetailIcon({ action: 'Copied' })).toBe('copy')
      expect(getDetailIcon({ action: 'Shared' })).toBe('share-2')
      expect(getDetailIcon({ action: 'Unshared' })).toBe('shield-off')
      expect(getDetailIcon({ action: 'Other' })).toBe('info')
    })
  })

  describe('getActivityDetailText', () => {
    it('formats detail line for copied field', () => {
      expect(getActivityDetailText({ action: 'Copied', details: { field: 'totp_secret' } })).toBe(
        'Field: totp_secret'
      )
    })

    it('formats detail line for shared recipient and permission', () => {
      expect(
        getActivityDetailText({
          action: 'Shared',
          details: { recipient: 'devops-team', permission: 'Edit' },
        })
      ).toBe('devops-team (Edit)')
    })
  })
})

