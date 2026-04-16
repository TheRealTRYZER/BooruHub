export type SiteName = 'danbooru' | 'e621' | 'rule34'

export type RatingChar = 'g' | 's' | 'q' | 'e'
export type RatingWord = 'safe' | 'general' | 'questionable' | 'explicit'
export type RatingClass = 'safe' | 'questionable' | 'explicit' | 'unknown'

export interface Post {
  id: string | number
  source_site: SiteName
  preview_url: string | null
  sample_url: string | null
  file_url: string | null
  tags: string[]
  rating: string
  score: number
  width: number | null
  height: number | null
  file_ext: string | null
  md5: string | null
  created_at: string | null
  is_dislike?: boolean
}

export interface User {
  id: number
  username: string
  email: string
  default_tags: string | null
  data_consent?: boolean
}

export type EventType = 'impression' | 'view' | 'like' | 'favourite' | 'search'

export interface UserEventPayload {
  type: EventType
  source?: string
  post_id?: string
  tags?: string[]
  query?: string
  duration_sec?: number
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface FeedResponse {
  posts: Post[]
  page: number
  total: number
  unfiltered_count: number
  resolved_tags: string
  corrected_tags?: string | null
}

export interface SearchResponse extends FeedResponse {}

export interface TagSuggestion {
  tag: string
  is_mapped: boolean
}

export interface TagSuggestResponse {
  suggestions: TagSuggestion[]
}

export interface Favorite {
  id: number
  user_id: number
  source_site: SiteName
  post_id: string
  preview_url: string | null
  file_url: string | null
  sample_url: string | null
  tags: string[]
  rating: string
  score: number
  is_dislike: boolean
}

export interface FavoritesResponse {
  favorites: Favorite[]
}

export interface FavoriteCheckResponse {
  is_favorite: boolean
  favorite_id: number | null
}

export interface Bookmark {
  id: number
  user_id: number
  name: string
  query: string
  sites: SiteName[]
}

export interface BookmarksResponse {
  bookmarks: Bookmark[]
}

export interface BlacklistRule {
  id: number
  user_id: number
  rule_line: string
  is_active: boolean
}

export interface BlacklistResponse {
  rules: BlacklistRule[]
}

export interface TagMapping {
  id: number
  user_id: number
  unitag: string
  danbooru_tags: string | null
  e621_tags: string | null
  rule34_tags: string | null
}

export interface ApiKeysStatus {
  danbooru: boolean
  e621: boolean
  rule34: boolean
  danbooru_login: string | null
  e621_login: string | null
  rule34_user_id: string | null
  search_limit: number | null
  search_interval: number | null
}

export interface ApiKeysUpdate {
  danbooru_login?: string
  danbooru_api_key?: string
  e621_login?: string
  e621_api_key?: string
  rule34_user_id?: string
  rule34_api_key?: string
  search_limit?: number
  search_interval?: number
}

export interface ToastItem {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
  icon: string
  removing: boolean
}

export type TranslationKey = string

export type Locale = 'en' | 'ru'

export const RATING_MAP: Record<string, RatingClass> = {
  g: 'safe',
  general: 'safe',
  s: 'safe',
  q: 'questionable',
  questionable: 'questionable',
  e: 'explicit',
  explicit: 'explicit',
}

export const RATING_LABELS: Record<RatingClass, string> = {
  safe: 'S',
  questionable: 'Q',
  explicit: 'E',
  unknown: '?',
}

export const AVAILABLE_SITES: SiteName[] = ['danbooru', 'e621', 'rule34']
