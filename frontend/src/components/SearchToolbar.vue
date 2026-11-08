<template>
  <div ref="toolbarEl" class="search-toolbar-container" :class="{ 'toolbar-hidden': isScrollingDown, 'is-stuck': isStuck }">
    <div class="search-bar">
      <div class="search-bar-row">
        <div v-show="!feed.isSplit" class="search-input-wrapper" @click="focusActualInput">
          <!-- Plain Text Input Field -->
          <input ref="inputEl" type="text" class="search-input-element"
                 :placeholder="lang.t('search_placeholder')"
                 v-model="inputVal"
                 @input="onSearchInput"
                 @focus="onSearchFocus"
                 @blur="onSearchBlur"
                 @keydown.enter="triggerSearch"
                 @keydown.tab.prevent="onTabPress" />
          <button class="search-submit" @click.stop="triggerSearch"
                  :title="lang.t('search_btn')" :aria-label="lang.t('search_btn')">
            <AppIcon name="search" :size="18" :stroke-width="2" />
          </button>
        </div>

        <div class="search-actions">
          <button v-if="auth.isAuthenticated && !feed.isSplit" class="btn btn-secondary search-icon-btn" @click="saveBookmark"
                  :title="lang.t('save_to_bookmarks')" :aria-label="lang.t('save_to_bookmarks')" id="btn-bookmark">
            <AppIcon name="bookmark" :size="18" />
          </button>
          <button class="btn btn-secondary search-icon-btn" :class="{ 'is-on': feed.isSplit }" @click="feed.toggleSplit()"
                  :title="feed.isSplit ? lang.t('collapse') : lang.t('split_search')"
                  :aria-label="feed.isSplit ? lang.t('collapse') : lang.t('split_search')"
                  :aria-pressed="feed.isSplit" id="btn-split">
            <AppIcon :name="feed.isSplit ? 'arrow-left' : 'split'" :size="18" />
            <span v-if="feed.isSplit" class="split-label">{{ lang.t('collapse') }}</span>
          </button>
        </div>
      </div>
      
      <!-- Autosuggestions Dropdown -->
      <div class="search-suggestions" :class="{ visible: hasSuggestions }">
        <div v-for="tagObj in suggestions" :key="tagObj.tag" 
             class="search-suggestion-item" 
             :class="{ mapped: tagObj.is_mapped, frequent: (tagObj.search_count || 0) > 0 }"
             @mousedown.prevent="selectSuggestion(tagObj.tag)">
          <span v-if="tagObj.is_mapped" class="mapped-star"><AppIcon name="star" :size="11" /></span>
          <span class="suggestion-text autocomplete-tag" :class="tagObj.category">{{ tagObj.tag.replace(/_/g, ' ') }}</span>
          <span v-if="tagObj.category && tagObj.category !== 'general'" class="autocomplete-badge" :class="tagObj.category">{{ tagObj.category }}</span>
          <span v-if="(tagObj.search_count || 0) > 0" class="frequent-badge" :title="lang.t('frequent_tag_hint')">★{{ tagObj.search_count }}</span>
          
          <div class="suggestion-right-group">
            <span v-if="tagObj.post_count" class="tag-count-indicator">{{ formatCount(tagObj.post_count) }}</span>
            <div class="suggestion-sources">
              <span v-if="tagObj.from_danbooru" class="suggestion-source danbooru">db</span>
              <span v-if="tagObj.from_e621" class="suggestion-source e621">e6</span>
              <span v-if="tagObj.from_rule34" class="suggestion-source rule34">r34</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Search History Dropdown -->
      <div class="search-suggestions" :class="{ visible: showHistory && searchHistory.length > 0 && !hasSuggestions }">
        <div v-for="q in searchHistory" :key="q" class="search-suggestion-item history-item"
             @mousedown.prevent="selectHistory(q)">
          <span class="history-clock"><AppIcon name="clock" :size="14" /></span>
          <span class="history-query">{{ q }}</span>
          <span class="history-remove" @mousedown.stop.prevent="removeHistory(q)"><AppIcon name="close" :size="14" /></span>
        </div>
      </div>
    </div>

    <!-- Split Search Section -->
    <div class="split-search-container" v-show="feed.isSplit">
      <div v-for="site in availableSites" :key="site" class="split-search-row">
        <div class="split-search-info">
          <span class="site-filter-dot" :class="site"></span>
          <span class="split-search-site" :class="site">{{ site }}</span>
        </div>
        <div style="flex: 1; position: relative; display: flex; align-items: center;">
          <input type="text" class="input btn-sm split-tag-input"
                 :placeholder="lang.t('tags_for') + ' ' + site + '...'"
                 v-model="feed.siteTags[site]"
                 @input="onSplitSearchInput(site)"
                 @focus="onSplitSearchFocus(site)"
                 @blur="onSplitSearchBlur(site)"
                 @keydown.enter="triggerSearch">
          
          <!-- Split Suggestions Dropdown -->
          <div class="search-suggestions split-suggestions" 
               :class="{ visible: activeSplitSite === site && hasSplitSuggestions }"
               style="top: 100%; left: 0; width: 100%; max-height: 200px; z-index: 101;">
            <div v-for="tagObj in splitSuggestions" :key="tagObj.tag" 
                 class="search-suggestion-item" 
                 :class="{ mapped: tagObj.is_mapped, frequent: (tagObj.search_count || 0) > 0 }"
                 @mousedown.prevent="selectSplitSuggestion(site, tagObj.tag)">
              <span v-if="tagObj.is_mapped" class="mapped-star"><AppIcon name="star" :size="11" /></span>
              <span class="suggestion-text autocomplete-tag" :class="tagObj.category">{{ tagObj.tag.replace(/_/g, ' ') }}</span>
              <span v-if="tagObj.category && tagObj.category !== 'general'" class="autocomplete-badge" :class="tagObj.category">{{ tagObj.category }}</span>
              <span v-if="(tagObj.search_count || 0) > 0" class="frequent-badge" :title="lang.t('frequent_tag_hint')">★{{ tagObj.search_count }}</span>
              
              <div class="suggestion-right-group">
                <span v-if="tagObj.post_count" class="tag-count-indicator">{{ formatCount(tagObj.post_count) }}</span>
                <div class="suggestion-sources">
                  <span v-if="tagObj.from_danbooru" class="suggestion-source danbooru">db</span>
                  <span v-if="tagObj.from_e621" class="suggestion-source e621">e6</span>
                  <span v-if="tagObj.from_rule34" class="suggestion-source rule34">r34</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <button class="btn btn-primary split-search-go" @click="triggerSearch"
                :title="lang.t('search_btn')" :aria-label="lang.t('search_btn')">
          <AppIcon name="search" :size="16" :stroke-width="2" />
        </button>
        <div class="ratio-slider-container">
          <input type="range" class="ratio-slider"
                 min="0" max="10" step="1"
                 v-model.number="feed.ratios[site]">
          <span class="ratio-val">{{ feed.ratios[site] }}</span>
        </div>
      </div>
      <div class="ratio-mixing-help">
        {{ lang.t('mixing_ratio') }}
      </div>
    </div>

    <!-- Filters & Settings (Visible only when not split) -->
    <div class="filter-controls-row" v-show="!feed.isSplit">
      <div class="site-filters">
        <label v-for="site in availableSites" :key="site" class="site-filter"
               :class="[site, { active: feed.sites.includes(site) }]"
               @click="toggleSite(site)">
          <span class="site-filter-dot" :class="site"></span>
          {{ site }}
        </label>
      </div>
      <div class="col-select-dropdown">
        <button class="col-select-btn" @click.stop="toggleColDropdown"
                :title="lang.t('posts_per_row')"
                :aria-label="lang.t('posts_per_row')"
                :aria-expanded="showColDropdown">
          <AppIcon name="columns" :size="16" />
          <span class="col-select-count">{{ currentColCount }}</span>
          <AppIcon name="chevron-down" :size="12" :stroke-width="2.2" class="col-select-caret" />
        </button>
        <div v-if="showColDropdown" class="col-dropdown-menu">
          <div v-for="c in COL_OPTIONS" :key="c" 
               class="col-dropdown-item"
               :class="{ active: c === currentColCount }"
               @click.stop="selectColCount(c)">
            {{ lang.t('posts_per_row_item', { count: c }) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Suggestion Correction Banner -->
    <div v-if="correctedTags" class="suggestion-banner">
      <span>{{ lang.t('did_you_mean') }}: </span>
      <a href="#" @click.prevent="applyCorrection(correctedTags)">{{ correctedTags }}</a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useFeedStore } from '../stores/feed'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiAddBookmark } from '../api'
import { cardSizeForColumns, columnsForCardSize } from '../utils/gridLayout'
import { useSearchHistory } from '../composables/useSearchHistory'
import { useTagSuggestions } from '../composables/useTagSuggestions'
import type { SiteName } from '../types'
import AppIcon from './AppIcon.vue'

const auth = useAuthStore()
const feed = useFeedStore()
const toast = useToastStore()
const lang = useLangStore()

defineProps<{
  correctedTags?: string | null
}>()

const emit = defineEmits<{
  (e: 'search'): void
  (e: 'apply-correction', tags: string): void
}>()

const availableSites: SiteName[] = ['danbooru', 'e621', 'rule34']

// Plain Text Tag Query Builder State
const inputVal = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

const {
  items: suggestions,
  isOpen: hasSuggestions,
  query: fetchSuggestions,
  clear: clearSuggestions,
  onFocus: cancelSuggestClose,
  onBlur: scheduleSuggestClose,
} = useTagSuggestions({
  isFocused: () => document.activeElement === inputEl.value,
})

const activeSplitSite = ref<SiteName | null>(null)
const {
  items: splitSuggestions,
  isOpen: hasSplitSuggestions,
  query: fetchSplitSuggestions,
  clear: clearSplitSuggestions,
  onFocus: cancelSplitClose,
  onBlur: scheduleSplitClose,
} = useTagSuggestions({
  isActive: () => activeSplitSite.value !== null,
  isFocused: () => document.activeElement?.classList.contains('split-tag-input') === true,
  onClose: () => {
    activeSplitSite.value = null
  },
})

function focusActualInput() {
  if (inputEl.value) inputEl.value.focus()
}

function syncToFeedStore() {
  feed.tags = inputVal.value
}

watch(inputVal, () => {
  syncToFeedStore()
})

watch(() => feed.tags, (newVal) => {
  if (newVal !== inputVal.value) {
    inputVal.value = newVal
  }
})

// The toolbar is always `position: sticky` with a fixed box, so scrolling never
// changes layout. `isStuck` only paints the background and `isScrollingDown`
// only slides it away with a transform. Neither touches the page height, which
// used to feed back into the scroll position and make the toolbar flicker.
const toolbarEl = ref<HTMLElement | null>(null)
const isStuck = ref(false)
const isScrollingDown = ref(false)
let lastScrollY = typeof window !== 'undefined' ? window.scrollY : 0
let scrollRaf = 0

const STUCK_AFTER = 60
const HIDE_DELTA = 12

function updateOnScroll() {
  scrollRaf = 0
  const y = Math.max(0, window.scrollY)
  isStuck.value = y > STUCK_AFTER

  // Stay open while typing: the on-screen keyboard resizes the viewport and
  // scrolls the page, which used to hide the field under the user's thumb.
  const busy = !!toolbarEl.value?.contains(document.activeElement) ||
    hasSuggestions.value || hasSplitSuggestions.value || showColDropdown.value
  if (y <= STUCK_AFTER || busy) {
    isScrollingDown.value = false
    lastScrollY = y
    return
  }

  const diff = y - lastScrollY
  if (Math.abs(diff) < HIDE_DELTA) return
  isScrollingDown.value = diff > 0
  lastScrollY = y
}

function handleScroll() {
  if (!scrollRaf) scrollRaf = requestAnimationFrame(updateOnScroll)
}

const showColDropdown = ref(false)

// Reactive so the "N per row" badge keeps up with a window resize; the grid
// reflows on resize too and the two must agree.
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1280)
const currentColCount = computed(() => columnsForCardSize(feed.cardSize, viewportWidth.value))
const COL_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12]

function onViewportResize() {
  viewportWidth.value = window.innerWidth
}

function toggleColDropdown() {
  showColDropdown.value = !showColDropdown.value
}

function selectColCount(cols: number) {
  showColDropdown.value = false
  feed.cardSize = cardSizeForColumns(cols, viewportWidth.value)
}

function closeDropdowns(_e: MouseEvent) {
  if (showColDropdown.value) {
    showColDropdown.value = false
  }
}

onMounted(() => {
  inputVal.value = feed.tags
  onViewportResize()
  window.addEventListener('scroll', handleScroll, { passive: true })
  window.addEventListener('resize', onViewportResize, { passive: true })
  document.addEventListener('click', closeDropdowns)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
  window.removeEventListener('resize', onViewportResize)
  document.removeEventListener('click', closeDropdowns)
  closeHistory()
})

function formatCount(num?: number): string {
  if (!num) return ''
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(0) + 'k'
  }
  return String(num)
}
const showHistory = ref(false)
let historyBlurTimer: ReturnType<typeof setTimeout> | null = null

const { history: searchHistory, addQuery: addSearchQuery, removeQuery: removeSearchQuery } = useSearchHistory()

function closeHistory() {
  if (historyBlurTimer) {
    clearTimeout(historyBlurTimer)
    historyBlurTimer = null
  }
  showHistory.value = false
}

function triggerSearch() {
  if (feed.tags.trim()) {
    addSearchQuery(feed.tags.trim())
  }
  clearSuggestions()
  closeHistory()
  emit('search')
}

function applyCorrection(newTags: string) {
  emit('apply-correction', newTags)
}

function toggleSite(site: SiteName) {
  feed.toggleSite(site)
}

async function saveBookmark() {
  const tags = feed.tags.trim()
  if (!tags) {
    toast.show(lang.t('enter_tags_to_save'), 'error')
    return
  }
  try {
    await apiAddBookmark(tags, tags, feed.sites)
    toast.show(lang.t('bookmark_added_msg'), 'success')
  } catch (e: any) {
    toast.show(e.message || e, 'error')
  }
}

/** The tag fragment the caret sits on, with any `-` operator stripped. */
function activePrefix(): string {
  const words = (inputVal.value || '').split(/\s+/)
  const lastWord = words[words.length - 1] || ''
  return lastWord.startsWith('-') ? lastWord.substring(1) : lastWord
}

function onSearchInput() {
  fetchSuggestions(activePrefix())
}

function onSearchFocus() {
  // Cancels the close a preceding blur scheduled, so clicking back into the
  // input no longer wipes the list that was about to disappear.
  cancelSuggestClose()
  if (!inputVal.value.trim()) {
    showHistory.value = true
    return
  }
  // Re-run the lookup: without this the dropdown only returned after another
  // keystroke, so focusing an already filled input showed nothing at all.
  fetchSuggestions(activePrefix())
}

function onSearchBlur() {
  scheduleSuggestClose()
  if (historyBlurTimer) clearTimeout(historyBlurTimer)
  historyBlurTimer = setTimeout(() => {
    historyBlurTimer = null
    showHistory.value = false
  }, 200)
}

function selectSuggestion(tag: string) {
  const text = inputVal.value || ''
  const words = text.split(/\s+/)
  if (words.length > 0) {
    const lastWord = words[words.length - 1]
    if (lastWord !== undefined && lastWord.startsWith('-')) {
      words[words.length - 1] = '-' + tag
    } else {
      words[words.length - 1] = tag
    }
    inputVal.value = words.join(' ') + ' '
  } else {
    inputVal.value = tag + ' '
  }
  clearSuggestions()
  closeHistory()
  syncToFeedStore()
  if (inputEl.value) inputEl.value.focus()
}

function selectHistory(q: string) {
  feed.tags = q
  closeHistory()
}

function removeHistory(q: string) {
  removeSearchQuery(q)
}

function onTabPress() {
  const first = suggestions.value[0]
  if (first) {
    selectSuggestion(first.tag)
  }
}

// Split Search Autocomplete Logic
function onSplitSearchInput(site: SiteName) {
  activeSplitSite.value = site
  const words = (feed.siteTags[site] || '').split(/\s+/)
  fetchSplitSuggestions(words[words.length - 1] || '')
}

function onSplitSearchFocus(site: SiteName) {
  cancelSplitClose()
  onSplitSearchInput(site)
}

function onSplitSearchBlur(_site: SiteName) {
  scheduleSplitClose()
}

function selectSplitSuggestion(site: SiteName, tag: string) {
  const text = feed.siteTags[site] || ''
  const words = text.split(/\s+/)
  if (words.length > 0) {
    words[words.length - 1] = tag
    feed.siteTags[site] = words.join(' ') + ' '
  } else {
    feed.siteTags[site] = tag + ' '
  }
  clearSplitSuggestions()
  activeSplitSite.value = null
}
</script>

<style scoped>
.search-toolbar-container {
  --tb-pad: 12px;
  --tb-top: calc(64px + var(--inset-top) + 8px); /* just below the fixed navbar */
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: var(--tb-top);
  z-index: 100; /* above the grid, below the navbar and modals */
  /* Constant box: padding is cancelled by the negative margin and the border is
     always present (transparent until stuck), so nothing reflows on scroll. */
  padding: var(--tb-pad);
  margin: calc(-1 * var(--tb-pad)) calc(-1 * var(--tb-pad)) 16px;
  border: 1px solid transparent;
  border-radius: var(--border-radius-lg);
  background: transparent;
  will-change: transform;
  transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.2s ease, background-color 0.2s, border-color 0.2s, box-shadow 0.2s;
}

/* Solid panel once the page has scrolled */
.search-toolbar-container.is-stuck {
  background: var(--bg-primary);
  border-color: var(--border-color-hover);
  box-shadow: var(--shadow-md);
}

/* Slide up and out of the way while scrolling down */
.search-toolbar-container.toolbar-hidden {
  transform: translateY(calc(-100% - var(--tb-top)));
  opacity: 0;
  pointer-events: none;
}
.search-bar-row {
  display: flex;
  gap: 12px;
  align-items: center;
}
.input-search {
  flex: 1;
}
.search-actions {
  display: flex;
  gap: 8px;
}
/* Search button lives inside the input, on its right edge. */
.search-submit {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin-left: auto;
  background: var(--accent);
  color: var(--on-accent);
  border-radius: calc(var(--border-radius-sm) - 2px);
  transition: background-color 0.2s var(--ease-out), transform 0.2s var(--ease-out);
}
.search-submit:hover { background: var(--accent-hover); }
.search-submit:active { transform: scale(0.94); }
.search-icon-btn {
  min-width: 48px;
  height: 48px;
  padding: 0 12px;
}
.search-icon-btn.is-on { border-color: var(--accent-text); color: var(--accent-text); }
.split-label { font-size: 13px; }
.split-search-go { width: 44px; height: 44px; padding: 0; flex: none; }
.mapped-star {
  display: inline-flex;
  margin-right: 6px;
  color: var(--accent-text);
}
.frequent-badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--warning);
  border: 1px solid color-mix(in srgb, var(--warning) 40%, transparent);
  border-radius: 8px;
  padding: 1px 6px;
  margin-left: 6px;
  white-space: nowrap;
}
.history-clock {
  display: inline-flex;
  margin-right: 8px;
  opacity: 0.6;
}
.ratio-mixing-help {
  text-align: center;
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}
.filter-controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.site-filters {
  margin-bottom: 0;
}
@media (max-width: 768px) {
  .search-toolbar-container {
    --tb-pad: 8px;
    --tb-top: calc(64px + var(--inset-top) + 4px);
    border-radius: var(--border-radius);
  }
  .search-bar-row {
    gap: 8px;
  }
  .search-input-wrapper {
    min-width: 0;
  }
  .search-icon-btn {
    min-width: 44px;
    padding: 0 10px;
  }
  .split-label { display: none; }
  .filter-controls-row {
    flex-wrap: nowrap;
    gap: 8px;
  }
  .site-filters {
    flex-wrap: nowrap;
    min-width: 0;
  }
}
.col-select-dropdown {
  position: relative;
  display: inline-block;
  /* The row wraps on narrow screens, so an extra left margin would only offset
     the button once it lands on its own line. */
  margin-left: 0;
}
.col-select-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: var(--bg-input);
  border: 1px solid var(--border-color-hover);
  border-radius: var(--border-radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-mono);
  cursor: pointer;
  height: 36px;
  /* Never let the control grow past the row it lives in on a 320px screen. */
  min-width: 0;
  max-width: 100%;
  padding: 0 10px;
  transition: background-color 0.2s;
}
@media (max-width: 768px) {
  .col-select-btn { height: 44px; min-width: 44px; }
}
.col-select-count {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.col-select-caret {
  opacity: 0.7;
}
.col-select-btn:hover {
  background: var(--bg-card-hover);
}
.col-dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color-hover);
  border-radius: var(--border-radius-sm);
  box-shadow: var(--shadow-lg);
  z-index: 102;
  min-width: 130px;
  max-width: calc(100vw - 24px);
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}
.col-dropdown-item {
  padding: 12px 16px;
  font-size: 13px;
  cursor: pointer;
  color: var(--text-secondary);
  text-align: left;
  white-space: nowrap;
  transition: background-color 0.15s, color 0.15s;
}
.col-dropdown-item:hover {
  background: var(--bg-card-hover);
  color: var(--accent-text);
}
.col-dropdown-item.active {
  color: var(--accent-text);
  font-weight: 600;
}
</style>
