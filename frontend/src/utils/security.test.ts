import { describe, it, expect } from 'vitest'
import { sanitizeUrl, escapeCssString } from './security'

describe('security utils', () => {
  describe('sanitizeUrl', () => {
    it('should allow valid booru CDN URLs', () => {
      expect(sanitizeUrl('https://cdn.donmai.us/images/123.jpg')).toBe('https://cdn.donmai.us/images/123.jpg')
      expect(sanitizeUrl('https://static1.e621.net/data/abc.png')).toBe('https://static1.e621.net/data/abc.png')
      expect(sanitizeUrl('https://api-cdn.rule34.xxx/images/123.png')).toBe('https://api-cdn.rule34.xxx/images/123.png')
    })

    it('should allow localhost/test.com URLs', () => {
      expect(sanitizeUrl('https://localhost/image.png')).toBe('https://localhost/image.png')
      expect(sanitizeUrl('https://test.com/preview.jpg')).toBe('https://test.com/preview.jpg')
    })

    it('should allow safe data URIs', () => {
      const dataUri = 'data:image/svg+xml;utf8,<svg></svg>'
      expect(sanitizeUrl(dataUri)).toBe(dataUri)
    })

    it('should block non-https URLs', () => {
      expect(sanitizeUrl('http://cdn.donmai.us/images/123.jpg')).toBe('')
      expect(sanitizeUrl('ftp://cdn.donmai.us/images/123.jpg')).toBe('')
    })

    it('should block untrusted domains', () => {
      expect(sanitizeUrl('https://malicious-site.com/image.jpg')).toBe('')
      expect(sanitizeUrl('https://evildonmai.us/image.jpg')).toBe('')
    })
  })

  describe('escapeCssString', () => {
    it('should escape single quotes and backslashes', () => {
      expect(escapeCssString("https://test.com/path'with'quotes")).toBe("https://test.com/path\\'with\\'quotes")
      expect(escapeCssString("https://test.com/path\\with\\backslashes")).toBe("https://test.com/path\\\\with\\\\backslashes")
    })
  })
})
