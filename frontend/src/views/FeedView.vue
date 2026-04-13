<template>
  <div>
    <div class="search-bar">
      <div style="display:flex; flex-direction:column; gap:8px;">
        <input type="text" class="input input-search"
               :placeholder="lang.t('search_placeholder')"
               v-model="feed.tags"
               @input="onSearchInput"
               @blur="onSearchBlur"
               @keydown.enter="reload"
               v-show="!feed.isSplit"
               style="width: 100%;">
        <div style="display:flex; gap:8px; justify-content:flex-end;">
          <button class="btn btn-secondary btn-icon" @click="feed.toggleSplit()" :title="lang.t('advanced_search')">
            {{ feed.isSplit ? '⬅️ ' + lang.t('collapse') : '🔀 ' + lang.t('split_search') }}
          </button>
          <button class="btn btn-primary" @click="reload" v-show="!feed.isSplit" style="padding:0 24px;">
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
               @keydown.enter="reload">
        <button class="btn btn-primary btn-sm" @click="reload">🔍</button>
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

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useFeedStore } from '../stores/feed.js'
import { useToastStore } from '../stores/toast.js'
import { useLangStore } from '../stores/lang.js'
import { apiFeed, apiSuggestTags, apiAddBookmark } from '../api.js'
import PostGrid from '../components/PostGrid.vue'

const route = useRoute()
const auth = useAuthStore()
const feed = useFeedStore()
const toast = useToastStore()
const lang = useLangStore()

const availableSites = ['danbooru', 'e621', 'rule34']
const loading = ref(false)
const sentinel = ref(null)
const suggestions = ref([])
const skeletonCount = ref(0)
let observer = null
let searchTimeout = null
let suggestTimeout = null
let loadGeneration = 0  // Increments on each reload() to cancel stale requests

function toggleSite(site) {
  feed.toggleSite(site)
  // No auto-reload on site toggle
}

async function saveBookmark() {
  const tags = feed.tags.trim()
  if (!tags) {
    toast.show('Введите теги для сохранения', 'error')
    return
  }
  try {
    await apiAddBookmark(tags, tags, feed.sites)
    toast.show('Запрос сохранён в закладки', 'success')
  } catch (e) {
    toast.show(e.message, 'error')
  }
}

function onSearchInput() {
  // Clear suggestions timeout
  clearTimeout(suggestTimeout)
  const val = feed.tags.trim()
  const lastTag = val.split(/\s+/).pop()
  if (lastTag.length >= 2) {
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

function selectSuggestion(tag) {
  const parts = feed.tags.trim().split(/\s+/)
  parts[parts.length - 1] = tag
  // Don't add space if it's a prefix like "order:" or "rating:"
  const endsWithColon = tag.endsWith(':')
  feed.tags = parts.join(' ') + (endsWithColon ? '' : ' ')
  suggestions.value = []
  // If it ended with colon, focus might be needed to continue typing
}

function reload() {
  loadGeneration++  // Invalidates any in-flight loadMore calls
  feed.resetFeed()
  loadMore()
}

async function loadMore() {
  if (loading.value || !feed.hasMore) return
  loading.value = true
  skeletonCount.value = 12
  const gen = loadGeneration  // Capture current generation

  const activeSites = feed.sites.length > 0 ? feed.sites : availableSites
  const limitPerSite = Math.ceil(45 / activeSites.length)
  
  // Update signature to match this exact fetch parameters
  const siteTagSig = feed.isSplit ? JSON.stringify(feed.siteTags) : ''
  feed.lastSearchSignature = `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|${siteTagSig}`

  // Track the posts array before this page load begins
  const basePosts = [...feed.posts];
    const unfilteredCounts = {};
    activeSites.forEach(s => unfilteredCounts[s] = 0);

    try {
      const fetchPromises = activeSites.map(async (site, idx) => {
        try {
          if (idx > 0) await new Promise(r => setTimeout(r, idx * 50));
          if (gen !== loadGeneration) return 0  // Aborted by reload()
          
          const options = {}
          if (feed.isSplit) {
            if (feed.siteTags[site]) options[`${site}_tags`] = feed.siteTags[site]
          }
          
          const data = await apiFeed({
            tags: feed.tags,
            sites: site,
            page: feed.page,
            limit: limitPerSite,
            ...options
          })
          if (gen !== loadGeneration) return 0  // Aborted after fetch
          
          const newPosts = data.posts || []
          pagePayloads[site] = newPosts
          unfilteredCounts[site] = data.unfiltered_count || 0
          return newPosts.length
        } catch (siteErr) {
          console.error(`Error loading ${site}:`, siteErr)
          return 0
        }
      })

      const results = await Promise.all(fetchPromises)
      if (gen !== loadGeneration) return  // Aborted - another reload() happened

      const totalNew = results.reduce((acc, val) => acc + val, 0)
      const totalUnfiltered = Object.values(unfilteredCounts).reduce((acc, val) => acc + val, 0)
      
      // A site is exhausted only when the API ITSELF returns 0 (before filtering)
      const allSitesExhausted = activeSites.every(s => unfilteredCounts[s] === 0)
    
    if (totalNew > 0) {
      // Mix results: interleave posts from all sites
      const mixed = []
      const maxLen = Math.max(...activeSites.map(s => pagePayloads[s].length))
      for (let i = 0; i < maxLen; i++) {
        for (const activeSite of activeSites) {
          if (pagePayloads[activeSite][i]) mixed.push(pagePayloads[activeSite][i])
        }
      }
      feed.posts = [...basePosts, ...mixed]
      skeletonCount.value = 0
    }

    if (allSitesExhausted) {
      feed.hasMore = false
    } else {
      feed.page++
      // If everything was filtered out on this page, but sites still have data, auto-trigger next page
      if (totalNew === 0 && feed.hasMore && gen === loadGeneration) {
        // Wait bit to avoid tight loop in case of many empty pages
        setTimeout(() => { if (gen === loadGeneration) loadMore() }, 50)
      } else {
        setTimeout(() => {
          if (gen === loadGeneration && sentinel.value && !loading.value && feed.hasMore) {
            const rect = sentinel.value.getBoundingClientRect()
            if (rect.top <= window.innerHeight + 800) loadMore()
          }
        }, 500)
      }
    }
  } catch (e) {
    if (gen === loadGeneration) {
      toast.show(lang.t('failed_load') + ': ' + e.message, 'error')
    }
  } finally {
    if (gen === loadGeneration) {
      loading.value = false
      skeletonCount.value = 0
    }
  }
}

onMounted(() => {
  const guestDefault = "order:score rating:general"
  const hasVisited = sessionStorage.getItem('booruhub_visited')
  
  if (route.query.tags) {
    feed.tags = route.query.tags
  } else if (!feed.tags && !hasVisited) {
    // Only apply default tags on the very first visit of this session
    sessionStorage.setItem('booruhub_visited', 'true')
    if (auth.isAuthenticated && auth.user?.default_tags) {
      feed.tags = auth.user.default_tags
    } else if (!auth.isAuthenticated) {
      feed.tags = guestDefault
    }
  }

  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && !loading.value && feed.hasMore) {
      loadMore()
    }
  }, { rootMargin: '1000px' })

  if (sentinel.value) observer.observe(sentinel.value)

  // Verify if we should fetch new posts OR restore from cache
  const currentSig = feed.isSplit ? `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|${JSON.stringify(feed.siteTags)}` : `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|`
  
  if (feed.posts.length === 0 || feed.lastSearchSignature !== currentSig) {
    reload()
  }
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

// Keep watching for split tag changes with debounce
// Removed automatic siteTags watch to fulfill "remove automatic search" request
</script>
