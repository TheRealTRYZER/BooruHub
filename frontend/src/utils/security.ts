export function sanitizeUrl(url: string | null | undefined): string {
  if (!url) return ''
  if (url.startsWith('data:')) {
    if (url.startsWith('data:image/svg+xml') || url.startsWith('data:image/png') || url.startsWith('data:image/jpeg') || url.startsWith('data:image/gif')) {
      return url
    }
    return ''
  }

  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:') {
      return ''
    }

    const host = parsed.hostname.toLowerCase()
    const allowedDomains = [
      'donmai.us',
      'e621.net',
      'rule34.xxx',
      'test.com',
      'localhost',
      '127.0.0.1'
    ]

    const isAllowed = allowedDomains.some(domain => {
      return host === domain || host.endsWith('.' + domain)
    })

    return isAllowed ? url : ''
  } catch {
    return ''
  }
}

export function escapeCssString(str: string): string {
  if (!str) return ''
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
}
