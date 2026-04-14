<template>
  <div>
    <div class="search-bar">
      <div style="display:flex; flex-direction:column; gap:8px;">
        <input type="text" class="input input-search"
               :placeholder="lang.t('search_placeholder')"
               v-model="feed.tags"
               @input="onSearchInput"
               @blur="onSearchBlur"
               @keydown.enter="handleReload"
               @keydown.tab.prevent="onTabPress"
               v-show="!feed.isSplit"
               style="width: 100%;">
        <div style="display:flex; gap:8px; justify-content:flex-end;">
          <button class="btn btn-secondary btn-icon" @click="feed.toggleSplit()" :title="lang.t('advanced_search')">
            {{ feed.isSplit ? '⬅️ ' + lang.t('collapse') : '🔀 ' + lang.t('split_search') }}
          </button>
          <button class="btn btn-primary" @click="handleReload" v-show="!feed.isSplit" style="padding:0 24px;">
            🔍 {{ lang.t('search_btn') }}
          </button>
        </div>
      </div>
      <div class="search-suggestions" :class="{ visible: suggestions.length > 0 }">
        <div v-for="tag in suggestions" :key="tag" class="search-suggestion-item" @mousedown.prevent="selectSuggestion(tag)">
          {{ tag.replace(/_/g, ' ') }}
        </div>
      </div>
    </div>

    <div class="split-search-container" v-show="feed.isSplit">
      <div v-for="site in feed.sites" :key="site" class="split-search-row">
        <div class="split-search-info">
          <span class="site-filter-dot" :class="site"></span>
          <span class="split-search-site" :class="site">{{ site }}</span>
        </div>
        <input type="text" class="input btn-sm split-tag-input"
               :placeholder="lang.t('tags_for') + ' ' + site + '...'"
               v-model="feed.siteTags[site]"
               @keydown.enter="handleReload">
        <button class="btn btn-primary btn-sm" @click="handleReload">🔍</button>
        <div class="ratio-slider-container">
          <input type="range" class="ratio-slider"
                 min="0" max="10" step="1"
                 v-model.number="feed.ratios[site]">
          <span class="ratio-val">{{ feed.ratios[site] }}</span>
        </div>
      </div>
      <div style="text-align:center; font-size:10px; color:var(--text-muted); margin-top:4px;">
        {{ lang.t('mixing_ratio') }}
      </div>
    </div>

    <div class="site-filters" v-show="!feed.isSplit">
      <label v-for="site in availableSites" :key="site" class="site-filter"
             :class="[site, { active: feed.sites.includes(site) }]"
             @click="toggleSite(site)">
        <span class="site-filter-dot" :class="site"></span>
        {{ site }}
      </label>
    </div>

    <div v-if="correctedTags" class="suggestion-banner">
      <span>{{ lang.t('did_you_mean') }}: </span>
      <a href="#" @click.prevent="applyCorrection(correctedTags)">{{ correctedTags }}</a>
    </div>

    <PostGrid :posts="feed.posts" :skeletonCount="skeletonCount" />
    <div v-if="loading" class="loading-spinner" style="margin: 20px auto;"></div>
    <div v-if="!feed.hasMore && feed.posts.length > 0" class="loading-text" style="text-align:center; padding:40px; color:var(--text-muted); width:100%;">
      {{ lang.t('no_more_posts') }}
    </div>
    <div ref="sentinel" style="height:20px; margin-top:50px;"></div>

    <div v-if="!loading && !feed.hasMore && feed.posts.length === 0" class="empty-state" style="padding:100px 20px; text-align:center;">
      <div class="empty-state-icon" style="font-size:4rem; margin-bottom:20px;">🔍</div>
      <div class="empty-state-title" style="font-size:1.5rem; font-weight:700;">{{ lang.t('no_results') }}</div>
      <div class="empty-state-text" style="color:var(--text-muted);">{{ lang.t('try_changing') }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useFeedStore } from '../stores/feed'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiSuggestTags, apiAddBookmark } from '../api'
import { useFeedLoader } from '../composables/useFeedLoader'
import PostGrid from '../components/PostGrid.vue'
import type { SiteName } from '../types'

const route = useRoute()
const auth = useAuthStore()
const feed = useFeedStore()
const toast = useToastStore()
const lang = useLangStore()

const availableSites: SiteName[] = ['danbooru', 'e621', 'rule34']
const sentinel = ref<HTMLElement | null>(null)
const suggestions = ref<string[]>([])
let observer: IntersectionObserver | null = null
let suggestTimeout: any = null

const { loading, skeletonCount, correctedTags, loadMore, reload } = useFeedLoader(feed, toast, lang, availableSites)

const handleReload = () => reload(sentinel.value)

function applyCorrection(newTags: string) {
  feed.tags = newTags
  handleReload()
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
  const val = feed.tags.trim()
  const lastTag = val.split(/\s+/).pop()
  if (lastTag && lastTag.length >= 2) {
    suggestTimeout = setTimeout(async () => {
      try {
        const data = await apiSuggestTags(lastTag)
        suggestions.value = data.suggestions || []
      } catch (e) {
        suggestions.value = []
      }
    }, 300)
  } else {
    suggestions.value = []
  }
}

function onSearchBlur() {
  setTimeout(() => { suggestions.value = [] }, 200)
}

function selectSuggestion(tag: string) {
  const parts = feed.tags.split(/\s+/)
  if (parts.length > 0) {
    parts[parts.length - 1] = tag
  } else {
    parts.push(tag)
  }
  const endsWithColon = tag.endsWith(':')
  feed.tags = parts.join(' ') + (endsWithColon ? '' : ' ')
  suggestions.value = []
}

function onTabPress() {
  if (suggestions.value.length > 0) {
    selectSuggestion(suggestions.value[0])
  }
}

onMounted(() => {
  const guestDefault = "order:score rating:general"
  const hasVisited = sessionStorage.getItem('booruhub_visited')
  
  if (route.query.tags) {
    feed.tags = route.query.tags as string
  } else if (!feed.tags && !hasVisited) {
    sessionStorage.setItem('booruhub_visited', 'true')
    if (auth.isAuthenticated && auth.user?.default_tags) {
      feed.tags = auth.user.default_tags
    } else if (!auth.isAuthenticated) {
      feed.tags = guestDefault
    }
  }

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && !loading.value && feed.hasMore) {
      loadMore(sentinel.value)
    }
  }, { rootMargin: '1000px' })

  if (sentinel.value) observer.observe(sentinel.value)

  const currentSig = feed.isSplit ? `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|${JSON.stringify(feed.siteTags)}` : `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|`
  
  if (feed.posts.length === 0 || feed.lastSearchSignature !== currentSig) {
    reload(sentinel.value)
  }
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

// Keep watching for split tag changes with debounce
// Removed automatic siteTags watch to fulfill "remove automatic search" request
</script>
