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

const BASE = '/api'

interface CacheEntry {
  data: unknown
  expiry: number
}

const cache = new Map<string, CacheEntry>()
const CACHE_TTL = 60000

function getHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('booruhub_token')
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

interface FetchOptions {
  method?: string
  headers?: Record<string, string>
  body?: string
}

let _refreshPromise: Promise<void> | null = null

async function _tryRefreshToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem('booruhub_refresh_token')
  if (!refreshToken) return false

  try {
    const resp = await fetch(BASE + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!resp.ok) return false
    const data = await resp.json()
    if (data.access_token) {
      localStorage.setItem('booruhub_token', data.access_token)
      return true
    }
    return false
  } catch {
    return false
  }
}

async function _fetch<T>(url: string, opts: FetchOptions = {}): Promise<T> {
  const isCacheable = !opts.method || opts.method === 'GET'
  if (isCacheable && cache.has(url)) {
    const entry = cache.get(url)!
    if (Date.now() < entry.expiry) return entry.data as T
    cache.delete(url)
  }

  opts.headers = { ...getHeaders(), ...(opts.headers || {}) }
  let resp = await fetch(BASE + url, opts)

  if (!isCacheable) {
    cache.clear()
  }

  // On 401, try refreshing the token once
  if (resp.status === 401) {
    if (!_refreshPromise) {
      _refreshPromise = _tryRefreshToken().then(ok => {
        _refreshPromise = null
        if (!ok) {
          localStorage.removeItem('booruhub_token')
          localStorage.removeItem('booruhub_user')
          localStorage.removeItem('booruhub_refresh_token')
        }
      })
    }
    await _refreshPromise

    // Retry with new token if we have one
    const newToken = localStorage.getItem('booruhub_token')
    if (newToken) {
      opts.headers = { ...getHeaders(), ...(opts.headers || {}) }
      resp = await fetch(BASE + url, opts)
    }

    if (resp.status === 401) {
      localStorage.removeItem('booruhub_token')
      localStorage.removeItem('booruhub_user')
      localStorage.removeItem('booruhub_refresh_token')
      throw new Error('Authentication required')
    }
  }

  const data: Record<string, unknown> = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error((data.detail as string) || `HTTP ${resp.status}`)

  if (isCacheable) {
    cache.set(url, { data, expiry: Date.now() + CACHE_TTL })
    if (cache.size > 100) cache.delete(cache.keys().next().value!)
  }

  return data as T
}

export function apiClearCache() {
  cache.clear()
}

// Auth
export async function apiLogin(loginStr: string, password: string): Promise<AuthResponse> {
  return _fetch<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ login: loginStr, password }),
  })
}

export async function apiRegister(username: string, email: string, password: string, dataConsent = false): Promise<AuthResponse> {
  return _fetch<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password, data_consent: dataConsent }),
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
  if (ratios) params.set('ratios', ratios)
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

export async function apiSuggestTags(q: string, limit = 15): Promise<TagSuggestResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return _fetch<TagSuggestResponse>(`/posts/tags/suggest?${params}`)
}

// Favorites
export async function apiGetFavorites(page = 1, limit = 40, isDislike = false): Promise<FavoritesResponse> {
  return _fetch<FavoritesResponse>(`/favorites?page=${page}&limit=${limit}&is_dislike=${isDislike}`)
}

export async function apiAddFavorite(post: Post, isDislike = false): Promise<unknown> {
  return _fetch('/favorites', {
    method: 'POST',
    body: JSON.stringify({
      source_site: post.source_site,
      post_id: String(post.id),
      preview_url: post.preview_url,
      file_url: post.file_url,
      sample_url: post.sample_url,
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
  interface MappingsData {
    mappings: TagMapping[]
  }
  const data = await _fetch<MappingsData | TagMapping[]>('/mappings')
  return (Array.isArray(data) ? data : data.mappings || []) as TagMapping[]
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
