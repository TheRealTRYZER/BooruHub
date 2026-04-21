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
  refresh_token: string
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

export type TranslationKey =
  | 'search_placeholder' | 'search_btn' | 'split_search' | 'collapse'
  | 'advanced_search' | 'mixing_ratio' | 'no_more_posts' | 'no_results'
  | 'try_changing' | 'failed_load'
  | 'nav_feed' | 'nav_guides' | 'nav_favorites' | 'nav_bookmarks' | 'nav_settings'
  | 'logout' | 'login' | 'logged_out'
  | 'added_fav' | 'removed_fav' | 'login_to_fav'
  | 'tags_for'
  | 'bookmarks_title' | 'bookmarks_subtitle' | 'no_bookmarks'
  | 'save_bookmarks_hint' | 'error_load_bookmarks' | 'enter_tags_to_save' | 'bookmark_added_msg'
  | 'favorites_title' | 'favorites_subtitle'
  | 'dislikes_title' | 'dislikes_subtitle' | 'likes_tab' | 'dislikes_tab'
  | 'no_favorites' | 'empty_list' | 'add_favorites_hint' | 'error_load_favorites'
  | 'settings_title' | 'settings_subtitle' | 'profile' | 'start_tags'
  | 'save_settings' | 'settings_saved'
  | 'api_keys_section' | 'search_params' | 'posts_limit' | 'search_interval'
  | 'keys_not_set' | 'keys_configured' | 'api_error'
  | 'manual_mappings' | 'add_mapping' | 'update_mapping'
  | 'mapping_saved' | 'mapping_created' | 'mapping_deleted'
  | 'blacklist_title' | 'add_rule' | 'rule_added' | 'rule_deleted'
  | 'welcome' | 'login_subtitle' | 'username_email' | 'password'
  | 'signing_in' | 'no_account' | 'create_account' | 'fill_fields' | 'logged_in_msg'
  | 'create_title' | 'already_have' | 'register_btn' | 'registering'
  | 'post_not_found' | 'back_to_feed' | 'remove_from_fav' | 'add_to_fav'
  | 'original' | 'source' | 'post_id' | 'rating' | 'score' | 'size' | 'format'
  | 'tags_count' | 'error_load_post'
  | 'guides_title' | 'guides_subtitle'
  | 'tab_tags' | 'tab_api' | 'tab_blacklist' | 'tab_mapping'
  | 'error' | 'loading' | 'back' | 'delete' | 'confirm_delete' | 'save'
  | 'did_you_mean'
  | 'consent_label' | 'privacy_policy' | 'privacy_title' | 'privacy_subtitle' | 'privacy_desc'
  | 'events_collected' | 'delete_history' | 'confirm_delete_history' | 'history_deleted'
  | 'privacy_what_title' | 'privacy_what_text'
  | 'privacy_impression_desc' | 'privacy_view_desc' | 'privacy_like_desc'
  | 'privacy_fav_desc' | 'privacy_search_desc'
  | 'privacy_why_title' | 'privacy_why_text'
  | 'privacy_retention_title' | 'privacy_retention_text'
  | 'privacy_rights_title' | 'privacy_rights_text'
  | 'privacy_right_access' | 'privacy_right_delete' | 'privacy_right_withdraw'
  | 'privacy_sharing_title' | 'privacy_sharing_text'

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
