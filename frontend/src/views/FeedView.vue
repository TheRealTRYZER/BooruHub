<template>
  <div>
    <SearchToolbar 
      :corrected-tags="correctedTags" 
      @search="handleReload" 
      @apply-correction="applyCorrection" 
    />

    <PostGrid :posts="feed.posts" :skeletonCount="skeletonCount" @click-media="openLightbox" />
    <div v-if="loading" class="loading-spinner" style="margin: 20px auto;"></div>
    <div v-if="!feed.hasMore && feed.posts.length > 0" class="loading-text" style="text-align:center; padding:40px; color:var(--text-muted); width:100%;">
      {{ lang.t('no_more_posts') }}
    </div>
    <div ref="sentinel" style="height:20px; margin-top:50px;"></div>

    <div v-if="!loading && !feed.hasMore && feed.posts.length === 0 && !correctedTags" class="empty-state" style="padding:100px 20px; text-align:center;">
      <div class="empty-state-icon" style="font-size:4rem; margin-bottom:20px;">🔍</div>
      <div class="empty-state-title" style="font-size:1.5rem; font-weight:700;">{{ lang.t('no_results') }}</div>
      <div class="empty-state-text" style="color:var(--text-muted);">{{ lang.t('try_changing') }}</div>
    </div>

    <!-- Immersive Lightbox Slider Modal -->
    <LightboxModal
      v-if="selectedPost"
      :post="selectedPost"
      :posts="feed.posts"
      @close="selectedPost = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useFeedStore } from '../stores/feed'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { useFeedLoader } from '../composables/useFeedLoader'
import { useSearchHistory } from '../composables/useSearchHistory'
import PostGrid from '../components/PostGrid.vue'
import SearchToolbar from '../components/SearchToolbar.vue'
import LightboxModal from '../components/LightboxModal.vue'
import type { Post, SiteName } from '../types'

const route = useRoute()
const auth = useAuthStore()
const feed = useFeedStore()
const toast = useToastStore()
const lang = useLangStore()

const availableSites: SiteName[] = ['danbooru', 'e621', 'rule34']
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const { loading, skeletonCount, correctedTags, loadMore, reload } = useFeedLoader(feed, toast, lang, availableSites)
const { addQuery: addSearchQuery } = useSearchHistory()

const selectedPost = ref<Post | null>(null)
function openLightbox(post: Post) {
  selectedPost.value = post
}

const handleReload = () => {
  if (feed.tags.trim()) addSearchQuery(feed.tags.trim())
  reload(sentinel.value)
}

function applyCorrection(newTags: string) {
  feed.tags = newTags
  handleReload()
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
    const entry = entries[0]
    if (entry && entry.isIntersecting && !loading.value && feed.hasMore) {
      loadMore(sentinel.value)
    }
  }, { rootMargin: `${feed.rootMargin}px` })

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
