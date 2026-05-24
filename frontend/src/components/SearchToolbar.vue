<template>
  <div class="search-toolbar-container">
    <div class="search-bar">
      <div class="search-bar-row">
        <div v-show="!feed.isSplit" class="search-input-wrapper" @click="focusActualInput">
          <!-- Tag Pills List -->
          <span v-for="(pill, idx) in pills" :key="pill + idx" 
                class="tag-pill" 
                :class="[getPillCategory(pill), { negated: pill.startsWith('-') }]"
                @click.stop="toggleNegation(idx)">
            <span class="tag-pill-text">{{ pill }}</span>
            <span class="tag-pill-remove" @click.stop="removeTagPill(idx)">×</span>
          </span>
          
          <!-- Invisible Actual Input Field for typing next tag -->
          <input ref="inputEl" type="text" class="search-input-element"
                 :placeholder="pills.length === 0 ? lang.t('search_placeholder') : ''"
                 v-model="inputVal"
                 @input="onSearchInput"
                 @focus="onSearchFocus"
                 @blur="onSearchBlur"
                 @keydown="onKeydown"
                 @keydown.tab.prevent="onTabPress" />
        </div>
               
        <div class="search-actions">
          <button v-if="auth.isAuthenticated && !feed.isSplit" class="btn btn-secondary" @click="saveBookmark" :title="lang.t('save_to_bookmarks')" id="btn-bookmark">
            🔖 <span class="btn-bookmark-text">{{ lang.t('save_to_bookmarks') }}</span>
          </button>
          <button class="btn btn-secondary btn-icon" @click="feed.toggleSplit()" :title="lang.t('advanced_search')">
            {{ feed.isSplit ? '⬅️ ' + lang.t('collapse') : '🔀 ' + lang.t('split_search') }}
          </button>
          <button class="btn btn-primary btn-search" @click="triggerSearch" v-show="!feed.isSplit">
            🔍 {{ lang.t('search_btn') }}
          </button>
        </div>
      </div>
      
      <!-- Autosuggestions Dropdown -->
      <div class="search-suggestions" :class="{ visible: suggestions.length > 0 }">
        <div v-for="tagObj in suggestions" :key="tagObj.tag" 
             class="search-suggestion-item" 
             :class="{ mapped: tagObj.is_mapped }"
             @mousedown.prevent="selectSuggestion(tagObj.tag)">
          <span v-if="tagObj.is_mapped" class="mapped-star">⭐</span>
          <span class="suggestion-text autocomplete-tag" :class="tagObj.category">{{ tagObj.tag.replace(/_/g, ' ') }}</span>
          <span v-if="tagObj.category && tagObj.category !== 'general'" class="autocomplete-badge" :class="tagObj.category">{{ tagObj.category }}</span>
          
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
      <div class="search-suggestions" :class="{ visible: showHistory && searchHistory.length > 0 && suggestions.length === 0 }">
        <div v-for="q in searchHistory" :key="q" class="search-suggestion-item history-item"
             @mousedown.prevent="selectHistory(q)">
          <span class="history-clock">🕐</span>
          <span class="history-query">{{ q }}</span>
          <span class="history-remove" @mousedown.stop.prevent="removeHistory(q)">×</span>
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
        <input type="text" class="input btn-sm split-tag-input"
               :placeholder="lang.t('tags_for') + ' ' + site + '...'"
               v-model="feed.siteTags[site]"
               @keydown.enter="triggerSearch">
        <button class="btn btn-primary btn-sm" @click="triggerSearch">🔍</button>
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

      <div class="feed-controls">
        <div class="feed-control-group">
          <label class="feed-control-label">🎚️ {{ lang.t('card_size') }}</label>
          <input type="range" min="75" max="400" step="5" v-model.number="feed.cardSize" class="size-slider">
          <span class="size-val">{{ feed.cardSize }}px</span>
        </div>
        
        <div class="feed-control-group">
          <label class="feed-control-label">🖼️ {{ lang.t('preview_quality') }}</label>
          <select v-model="feed.previewQuality" class="quality-select">
            <option value="thumbnail">{{ lang.t('quality_thumbnail') }}</option>
            <option value="sample">{{ lang.t('quality_sample') }}</option>
            <option value="full">{{ lang.t('quality_full') }}</option>
          </select>
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
import { ref, watch, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useFeedStore } from '../stores/feed'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiSuggestTags, apiAddBookmark } from '../api'
import { useSearchHistory } from '../composables/useSearchHistory'
import type { SiteName } from '../types'

const auth = useAuthStore()
const feed = useFeedStore()
const toast = useToastStore()
const lang = useLangStore()

const props = defineProps<{
  correctedTags?: string | null
}>()

const emit = defineEmits<{
  (e: 'search'): void
  (e: 'apply-correction', tags: string): void
}>()

const availableSites: SiteName[] = ['danbooru', 'e621', 'rule34']
const suggestions = ref<any[]>([])

// Visual Tag Query Builder State & Logic
const pills = ref<string[]>([])
const inputVal = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

function focusActualInput() {
  if (inputEl.value) inputEl.value.focus()
}

function getPillCategory(pill: string): string {
  const clean = pill.startsWith('-') ? pill.substring(1) : pill
  if (clean.includes(':')) return 'metadata'
  
  // Lookup inside cache or fetched suggestions matching this tag name
  const match = suggestions.value.find(s => s.tag === clean)
  if (match && match.category) return match.category
  
  return 'general'
}

function toggleNegation(idx: number) {
  const pill = pills.value[idx]
  if (pill.startsWith('-')) {
    pills.value[idx] = pill.substring(1)
  } else {
    pills.value[idx] = '-' + pill
  }
  syncToFeedStore()
}

function removeTagPill(idx: number) {
  pills.value.splice(idx, 1)
  syncToFeedStore()
}

function addTagPill(val: string) {
  const clean = val.trim().toLowerCase()
  if (clean) {
    // If it's already in pills, don't duplicate
    if (!pills.value.includes(clean)) {
      pills.value.push(clean)
    }
  }
  inputVal.value = ''
  suggestions.value = []
  syncToFeedStore()
}

function removeLastPill() {
  if (pills.value.length > 0) {
    pills.value.pop()
    syncToFeedStore()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === ' ' || e.key === 'Enter') {
    const val = inputVal.value.trim()
    if (val) {
      e.preventDefault()
      addTagPill(val)
      if (e.key === 'Enter') {
        triggerSearch()
      }
    } else if (e.key === 'Enter') {
      triggerSearch()
    }
  } else if (e.key === 'Backspace' && !inputVal.value) {
    removeLastPill()
  }
}

function syncToFeedStore() {
  const combined = pills.value.join(' ')
  feed.tags = combined + (inputVal.value ? ' ' + inputVal.value : '')
}

function parseExternalTags() {
  const tagsStr = feed.tags.trim()
  if (!tagsStr) {
    pills.value = []
    inputVal.value = ''
    return
  }
  pills.value = tagsStr.split(/\s+/)
  inputVal.value = ''
}

watch(inputVal, () => {
  syncToFeedStore()
})

watch(() => feed.tags, (newVal) => {
  const combined = pills.value.join(' ') + (inputVal.value ? ' ' + inputVal.value : '')
  if (newVal.trim() !== combined.trim()) {
    parseExternalTags()
  }
})

onMounted(() => {
  parseExternalTags()
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
let suggestTimeout: any = null

const { history: searchHistory, addQuery: addSearchQuery, removeQuery: removeSearchQuery } = useSearchHistory()

function triggerSearch() {
  if (feed.tags.trim()) {
    addSearchQuery(feed.tags.trim())
  }
  suggestions.value = []
  showHistory.value = false
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

function onSearchInput() {
  clearTimeout(suggestTimeout)
  const val = inputVal.value.trim()
  if (val && val.length >= 2) {
    suggestTimeout = setTimeout(async () => {
      try {
        const data = await apiSuggestTags(val)
        suggestions.value = data.suggestions || []
      } catch (e) {
        suggestions.value = []
      }
    }, 300)
  } else {
    suggestions.value = []
  }
}

function onSearchFocus() {
  if (pills.value.length === 0 && !inputVal.value.trim()) showHistory.value = true
}

function onSearchBlur() {
  setTimeout(() => {
    suggestions.value = []
    showHistory.value = false
  }, 200)
}

function selectSuggestion(tag: string) {
  addTagPill(tag)
  triggerSearch()
}

function selectHistory(q: string) {
  feed.tags = q
  showHistory.value = false
  triggerSearch()
}

function removeHistory(q: string) {
  removeSearchQuery(q)
}

function onTabPress() {
  if (suggestions.value.length > 0) {
    selectSuggestion(suggestions.value[0].tag)
  }
}
</script>

<style scoped>
.search-toolbar-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
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
.btn-search {
  padding: 0 24px;
}
.mapped-star {
  margin-right: 6px;
  font-size: 10px;
}
.history-clock {
  margin-right: 8px;
  opacity: 0.5;
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
.feed-controls {
  margin-bottom: 0;
}
@media (max-width: 768px) {
  .search-bar-row {
    flex-wrap: wrap;
  }
  .input-search {
    min-width: 100%;
  }
  .search-actions {
    width: 100%;
    justify-content: flex-end;
  }
  .filter-controls-row {
    flex-direction: column;
    align-items: stretch;
  }
  .site-filters {
    width: 100%;
  }
  .feed-controls {
    width: 100%;
  }
}
</style>
