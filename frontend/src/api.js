const BASE = '/api'
const cache = new Map()
const CACHE_TTL = 60000

function getHeaders() {
  const h = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('booruhub_token')
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function _fetch(url, opts = {}) {
  const isCacheable = !opts.method || opts.method === 'GET'
  if (isCacheable && cache.has(url)) {
    const entry = cache.get(url)
    if (Date.now() < entry.expiry) return entry.data
    cache.delete(url)
  }

  opts.headers = { ...getHeaders(), ...(opts.headers || {}) }
  const resp = await fetch(BASE + url, opts)
  
  // If we're modifying data, clear cache
  if (!isCacheable) {
    cache.clear()
  }

  if (resp.status === 401) {
    localStorage.removeItem('booruhub_token')
    localStorage.removeItem('booruhub_user')
    // The lack of token will be detected by components
    throw new Error('Authentication required')
  }

  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`)

  if (isCacheable) {
    cache.set(url, { data, expiry: Date.now() + CACHE_TTL })
    if (cache.size > 100) cache.delete(cache.keys().next().value)
  }

  return data
}

// Auth
export async function apiLogin(loginStr, password) {
  return _fetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ login: loginStr, password }),
  })
}

export async function apiRegister(username, email, password) {
  return _fetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })
}

export async function apiGetMe() {
  return _fetch('/auth/me')
}

// Posts
export async function apiFeed({ tags = '', sites = 'danbooru,e621,rule34', page = 1, limit = 40, skipInterval = false, ...options } = {}) {
  const params = new URLSearchParams({ 
    tags, 
    sites, 
    page, 
    limit, 
    skip_interval: skipInterval ? 'true' : 'false',
    ...options 
  })
  return _fetch(`/posts/feed?${params}`)
}

export async function apiSearch(tags, site = 'danbooru', page = 1, limit = 40, skipInterval = false) {
  const params = new URLSearchParams({ 
    tags, 
    site, 
    page, 
    limit,
    skip_interval: skipInterval ? 'true' : 'false'
  })
  return _fetch(`/posts/search?${params}`)
}

export async function apiSuggestTags(q, limit = 15) {
  const params = new URLSearchParams({ q, limit })
  return _fetch(`/posts/tags/suggest?${params}`)
}

// Favorites
export async function apiGetFavorites(page = 1, limit = 40, isDislike = false) {
  return _fetch(`/favorites?page=${page}&limit=${limit}&is_dislike=${isDislike}`)
}

export async function apiAddFavorite(post, isDislike = false) {
  return _fetch('/favorites', {
    method: 'POST',
    body: JSON.stringify({
      source_site: post.source_site,
      post_id: String(post.id || post.post_id),
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

export async function apiRemoveFavorite(favId) {
  return _fetch(`/favorites/${favId}`, { method: 'DELETE' })
}

export async function apiCheckFavorite(sourceSite, postId) {
  return _fetch(`/favorites/check?source_site=${sourceSite}&post_id=${postId}`)
}

// Bookmarks
export async function apiGetBookmarks() {
  return _fetch('/bookmarks')
}

export async function apiAddBookmark(name, query, sites) {
  return _fetch('/bookmarks', {
    method: 'POST',
    body: JSON.stringify({ name, query, sites }),
  })
}

export async function apiDeleteBookmark(id) {
  return _fetch(`/bookmarks/${id}`, { method: 'DELETE' })
}

// Blacklist
export async function apiGetBlacklist() {
  return _fetch('/blacklist')
}

export async function apiAddBlacklistRule(ruleLine) {
  return _fetch('/blacklist', {
    method: 'POST',
    body: JSON.stringify({ rule_line: ruleLine }),
  })
}

export async function apiUpdateBlacklistRule(id, updates) {
  return _fetch(`/blacklist/${id}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  })
}

export async function apiDeleteBlacklistRule(id) {
  return _fetch(`/blacklist/${id}`, { method: 'DELETE' })
}

// Mappings
export async function apiGetMappings() {
  return _fetch('/mappings')
}

export async function apiCreateMapping(data) {
  return _fetch('/mappings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function apiUpdateMapping(id, data) {
  return _fetch(`/mappings/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function apiDeleteMapping(id) {
  return _fetch(`/mappings/${id}`, { method: 'DELETE' })
}

export async function apiUpdateDefaultTags(tags) {
  return _fetch('/mappings/user/default-tags', {
    method: 'PUT',
    body: JSON.stringify({ default_tags: tags }),
  })
}

export async function apiUpdateApiKeys(data) {
  return _fetch('/user/keys', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function apiGetApiKeysStatus() {
  return _fetch('/user/keys/status')
}
