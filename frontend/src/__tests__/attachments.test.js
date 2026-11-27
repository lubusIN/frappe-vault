import { describe, it, expect } from 'vitest'
import {
  cleanUrl,
  parseAttachments,
  isImageUrl,
  getFileName,
} from '@/utils/attachments'

describe('Attachment Utilities', () => {
  describe('cleanUrl', () => {
    it('returns empty string for non-string input', () => {
      expect(cleanUrl(null)).toBe('')
      expect(cleanUrl(123)).toBe('')
      expect(cleanUrl({})).toBe('')
    })

    it('strips leading and trailing quotes, brackets, and whitespace', () => {
      expect(cleanUrl('  "/private/files/test.png"  ')).toBe('/private/files/test.png')
      expect(cleanUrl("['/private/files/doc.pdf']")).toBe('/private/files/doc.pdf')
      expect(cleanUrl('["http://example.com/image.jpg"]')).toBe('http://example.com/image.jpg')
    })
  })

  describe('isImageUrl', () => {
    it('returns false for empty or non-image URLs', () => {
      expect(isImageUrl('')).toBe(false)
      expect(isImageUrl('/files/document.pdf')).toBe(false)
      expect(isImageUrl('/files/archive.zip')).toBe(false)
    })

    it('returns true for common image file extensions case-insensitively', () => {
      expect(isImageUrl('/files/photo.PNG')).toBe(true)
      expect(isImageUrl('/files/photo.jpg')).toBe(true)
      expect(isImageUrl('/files/photo.jpeg')).toBe(true)
      expect(isImageUrl('/files/graphic.svg')).toBe(true)
      expect(isImageUrl('/files/badge.webp')).toBe(true)
      expect(isImageUrl('/files/animation.gif')).toBe(true)
    })
  })

  describe('getFileName', () => {
    it('returns empty string for empty input', () => {
      expect(getFileName('')).toBe('')
    })

    it('extracts filename from URL path', () => {
      expect(getFileName('/private/files/server-key.pem')).toBe('server-key.pem')
      expect(getFileName('https://cdn.example.com/uploads/photo.jpg')).toBe('photo.jpg')
    })
  })

  describe('parseAttachments', () => {
    it('returns empty array for falsy values', () => {
      expect(parseAttachments(null)).toEqual([])
      expect(parseAttachments('')).toEqual([])
      expect(parseAttachments([])).toEqual([])
    })

    it('parses JSON array string', () => {
      const jsonStr = JSON.stringify(['/files/a.png', '/files/b.pdf'])
      expect(parseAttachments(jsonStr)).toEqual(['/files/a.png', '/files/b.pdf'])
    })

    it('handles doubly-encoded JSON strings', () => {
      const doubleEncoded = JSON.stringify(JSON.stringify(['/files/document.pdf']))
      expect(parseAttachments(doubleEncoded)).toEqual(['/files/document.pdf'])
    })

    it('falls back to comma or newline delimited strings', () => {
      const rawText = '/files/one.png,\n/files/two.pdf'
      expect(parseAttachments(rawText)).toEqual(['/files/one.png', '/files/two.pdf'])
    })

    it('filters out invalid or too-short paths', () => {
      expect(parseAttachments(['/a', 'invalid', '/files/valid.png'])).toEqual(['/files/valid.png'])
    })
  })
})

