import type {
  AuthResponse,
  FeedResponse,
  SearchResponse,
  TagSuggestResponse,
  FavoritesResponse,
  FavoriteCheckResponse,
  BookmarksResponse,
  BlacklistResponse,
  BlacklistRule,
  TagMapping,
  ApiKeysStatus,
  ApiKeysUpdate,
  Post,
  SiteName,
} from './types'
import { sanitizeUrl } from './utils/security'

const BASE = '/api'

interface CacheEntry {
  data: unknown
  expiry: number
}

const cache = new Map<string, CacheEntry>()
const CACHE_TTL = 60000

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]*)'))
  return match && match[2] !== undefined ? decodeURIComponent(match[2]) : null
}

function getHeaders(method = 'GET'): Record<string, string> {
  const h: Record<string, string> = {}
  if (method !== 'GET') {
    h['Content-Type'] = 'application/json'
  }
  const csrf = getCookie('csrftoken')
  if (csrf) {
    h['X-CSRF-Token'] = csrf
  }
  return h
}

interface FetchOptions {
  method?: string
  headers?: Record<string, string>
  body?: string
  signal?: AbortSignal
}

let _refreshPromise: Promise<void> | null = null
let _onAuthFailure: (() => void) | null = null

export function registerAuthFailureCallback(cb: () => void) {
  _onAuthFailure = cb
}

async function _tryRefreshToken(): Promise<boolean> {
  try {
    const resp = await fetch(BASE + '/auth/refresh', {
      method: 'POST',
      headers: getHeaders('POST'),
      credentials: 'include',
      body: JSON.stringify({}),
    })
    if (!resp.ok) return false
    cache.clear() // Clear cache upon token refresh to prevent mixed data
    return true
  } catch {
    return false
  }
}

function invalidateCache(prefix: string) {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) {
      cache.delete(key)
    }
  }
}

async function _fetch<T>(url: string, opts: FetchOptions = {}): Promise<T> {
  const method = opts.method || 'GET'
  const isCacheable = method === 'GET'
  const cacheKey = url

  if (isCacheable && cache.has(cacheKey)) {
    const entry = cache.get(cacheKey)!
    if (Date.now() < entry.expiry) return entry.data as T
    cache.delete(cacheKey)
  }

  const timeoutSec = Number(localStorage.getItem('booruhub_search_timeout') || '30')
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutSec * 1000)

  opts.headers = { ...getHeaders(method), ...(opts.headers || {}) }
  const fetchOpts: RequestInit = {
    method,
    headers: opts.headers,
    body: opts.body,
    signal: opts.signal || controller.signal,
    credentials: 'include',
  }

  let resp: Response
  try {
    resp = await fetch(BASE + url, fetchOpts)
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutSec} seconds`)
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }

  if (!isCacheable && !url.includes('/events/batch')) {
    if (url.startsWith('/favorites')) {
      invalidateCache('/favorites')
    } else if (url.startsWith('/bookmarks')) {
      invalidateCache('/bookmarks')
    } else if (url.startsWith('/blacklist')) {
      invalidateCache('/blacklist')
    } else if (url.startsWith('/mappings')) {
      invalidateCache('/mappings')
    } else if (url.startsWith('/auth') || url.startsWith('/user')) {
      cache.clear()
    }
  }

  // On 401, try refreshing the token once, EXCEPT for login/register which should return their own error
  if (resp.status === 401 && !url.includes('/auth/login') && !url.includes('/auth/register')) {
    if (!_refreshPromise) {
      _refreshPromise = _tryRefreshToken().then(ok => {
        _refreshPromise = null
        if (!ok) {
          localStorage.removeItem('booruhub_user')
          if (_onAuthFailure) _onAuthFailure()
        }
      })
    }
    await _refreshPromise

    // Retry with new token / cookies
    const retryController = new AbortController()
    const retryTimeoutId = setTimeout(() => retryController.abort(), timeoutSec * 1000)
    opts.headers = { ...getHeaders(method), ...(opts.headers || {}) }
    const retryFetchOpts: RequestInit = {
      method,
      headers: opts.headers,
      body: opts.body,
      signal: opts.signal || retryController.signal,
      credentials: 'include',
    }

    try {
      resp = await fetch(BASE + url, retryFetchOpts)
    } catch (err: any) {
      if (err.name === 'AbortError') {
        throw new Error(`Request timed out after ${timeoutSec} seconds`)
      }
      throw err
    } finally {
      clearTimeout(retryTimeoutId)
    }

    if (resp.status === 401) {
      localStorage.removeItem('booruhub_user')
      if (_onAuthFailure) _onAuthFailure()
      throw new Error('Authentication required')
    }
  }

  const data: Record<string, unknown> = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error((data.detail as string) || `HTTP ${resp.status}`)

  if (isCacheable) {
    cache.set(cacheKey, { data, expiry: Date.now() + CACHE_TTL })
    if (cache.size > 100) {
      const nextKey = cache.keys().next().value
      if (nextKey !== undefined) {
        cache.delete(nextKey)
      }
    }
  }

  return data as T
}

export function apiClearCache() {
  cache.clear()
}

// Auth
export async function apiLogin(loginStr: string, password: string): Promise<AuthResponse> {
  cache.clear()
  return _fetch<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ login: loginStr, password }),
  })
}

export async function apiRegister(username: string, email: string, password: string, dataConsent = false): Promise<AuthResponse> {
  cache.clear()
  return _fetch<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password, data_consent: dataConsent }),
  })
}

export async function apiLogout(): Promise<{ ok: boolean }> {
  cache.clear()
  return _fetch<{ ok: boolean }>('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function apiGetMe(): Promise<{ user: AuthResponse['user'] }> {
  return _fetch('/auth/me')
}

// Posts
interface FeedOptions {
  tags?: string
  sites?: string
  page?: number
  limit?: number
  skipInterval?: boolean
  [key: string]: string | number | boolean | undefined
}

export async function apiFeed(options: FeedOptions = {}): Promise<FeedResponse> {
  const { tags = '', sites = 'danbooru,e621,rule34', page = 1, limit = 40, skipInterval = false, ratios, ...rest } = options
  const params = new URLSearchParams({
    tags,
    sites,
    page: String(page),
    limit: String(limit),
    skip_interval: skipInterval ? 'true' : 'false',
  })
  if (ratios) params.set('ratios', String(ratios))
  for (const [k, v] of Object.entries(rest)) {
    if (v !== undefined) params.set(k, String(v))
  }
  return _fetch<FeedResponse>(`/posts/feed?${params}`)
}

export async function apiSearch(tags: string, site: SiteName = 'danbooru', page = 1, limit = 40, skipInterval = false): Promise<SearchResponse> {
  const params = new URLSearchParams({
    tags,
    site,
    page: String(page),
    limit: String(limit),
    skip_interval: skipInterval ? 'true' : 'false',
  })
  return _fetch<SearchResponse>(`/posts/search?${params}`)
}

export async function apiSuggestTags(q: string, limit = 15, signal?: AbortSignal, fast = false): Promise<TagSuggestResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  if (fast) params.set('fast', 'true')
  return _fetch<TagSuggestResponse>(`/posts/tags/suggest?${params}`, { signal })
}

// Favorites
export async function apiGetFavorites(page = 1, limit = 40, isDislike = false): Promise<FavoritesResponse> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
    is_dislike: isDislike ? 'true' : 'false',
  })
  return _fetch<FavoritesResponse>(`/favorites?${params}`)
}

export async function apiAddFavorite(post: Post, isDislike = false): Promise<unknown> {
  return _fetch('/favorites', {
    method: 'POST',
    body: JSON.stringify({
      source_site: post.source_site,
      post_id: String(post.id),
      preview_url: sanitizeUrl(post.preview_url),
      file_url: sanitizeUrl(post.file_url),
      sample_url: sanitizeUrl(post.sample_url),
      tags: post.tags || [],
      rating: post.rating,
      score: post.score || 0,
      is_dislike: isDislike,
    }),
  })
}

export async function apiRemoveFavorite(favId: number): Promise<unknown> {
  return _fetch(`/favorites/${favId}`, { method: 'DELETE' })
}

export async function apiCheckFavorite(sourceSite: SiteName, postId: string | number): Promise<FavoriteCheckResponse> {
  return _fetch<FavoriteCheckResponse>(`/favorites/check?source_site=${sourceSite}&post_id=${postId}`)
}

// Bookmarks
export async function apiGetBookmarks(): Promise<BookmarksResponse> {
  return _fetch<BookmarksResponse>('/bookmarks')
}

export async function apiAddBookmark(name: string, query: string, sites: SiteName[]): Promise<unknown> {
  return _fetch('/bookmarks', {
    method: 'POST',
    body: JSON.stringify({ name, query, sites }),
  })
}

export async function apiDeleteBookmark(id: number): Promise<unknown> {
  return _fetch(`/bookmarks/${id}`, { method: 'DELETE' })
}

// Blacklist
export async function apiGetBlacklist(): Promise<BlacklistResponse> {
  return _fetch<BlacklistResponse>('/blacklist')
}

export async function apiAddBlacklistRule(ruleLine: string): Promise<unknown> {
  return _fetch('/blacklist', {
    method: 'POST',
    body: JSON.stringify({ rule_line: ruleLine }),
  })
}

export async function apiUpdateBlacklistRule(id: number, updates: Partial<Pick<BlacklistRule, 'rule_line' | 'is_active'>>): Promise<unknown> {
  return _fetch(`/blacklist/${id}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  })
}

export async function apiDeleteBlacklistRule(id: number): Promise<unknown> {
  return _fetch(`/blacklist/${id}`, { method: 'DELETE' })
}

// Mappings
export async function apiGetMappings(): Promise<TagMapping[]> {
  const data = await _fetch<{ mappings: TagMapping[] }>('/mappings')
  return data.mappings || []
}

export async function apiCreateMapping(data: Omit<TagMapping, 'id' | 'user_id'>): Promise<unknown> {
  return _fetch('/mappings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function apiUpdateMapping(id: number, data: Partial<Omit<TagMapping, 'id' | 'user_id'>>): Promise<unknown> {
  return _fetch(`/mappings/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function apiDeleteMapping(id: number): Promise<unknown> {
  return _fetch(`/mappings/${id}`, { method: 'DELETE' })
}

export async function apiUpdateDefaultTags(tags: string): Promise<{ default_tags: string }> {
  return _fetch('/mappings/user/default-tags', {
    method: 'PUT',
    body: JSON.stringify({ default_tags: tags }),
  })
}

export async function apiUpdateApiKeys(data: ApiKeysUpdate): Promise<unknown> {
  return _fetch('/user/keys', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function apiGetApiKeysStatus(): Promise<ApiKeysStatus> {
  return _fetch<ApiKeysStatus>('/user/keys/status')
}

// Events (recommendation system data collection)
export async function apiLogEvents(events: import('./types').UserEventPayload[]): Promise<unknown> {
  if (events.length === 0) return { accepted: 0 }
  return _fetch('/events/batch', {
    method: 'POST',
    body: JSON.stringify({ events }),
  }).catch(() => {}) // Fire-and-forget, never block UI
}

// GDPR: delete all user event history
export async function apiDeleteHistory(): Promise<{ deleted: number }> {
  return _fetch('/events/history', { method: 'DELETE' })
}

export async function apiGetEventCount(): Promise<{ total: number }> {
  return _fetch('/events/count')
}

export async function apiUpdateConsent(consent: boolean): Promise<{ data_consent: boolean }> {
  return _fetch('/user/consent', {
    method: 'PUT',
    body: JSON.stringify({ data_consent: consent }),
  })
}
