<template>
  <div ref="cardRef" v-show="!hidden" class="post-card" :class="{ 'is-verifying': isVerifying }" @click="handleCardClick"
       @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd"
       :style="{ transform: swipeDiff ? `translateX(${swipeDiff}px)` : '', transition: swiping ? 'none' : 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)', opacity: Math.max(0, 1 - Math.abs(swipeDiff) / 200) }">
    
    <!-- Pulsing Aspect-Ratio Skeleton while Loading/Hashing in Background -->
    <div v-if="isVerifying" class="post-card-skeleton-wrapper" :style="mediaStyle">
      <div class="post-card-skeleton-pulse"></div>
      <!-- Background loaders with crossorigin to prevent tainted canvases -->
      <template v-if="isInViewport">
        <video v-if="isAnimated" ref="videoLoaderRef" :src="currentUrl" muted playsinline crossorigin="anonymous" style="display: none;" @loadeddata="onVideoLoaded" @error="onHashError"></video>
        <img v-else ref="imgLoaderRef" :src="currentUrl" crossorigin="anonymous" style="display: none;" @load="onImageLoaded" @error="onHashError" />
      </template>
    </div>

    <!-- Main Content when Verified -->
    <template v-else>
      <div class="post-card-media" :style="mediaStyle">
        <img class="post-card-img"
             :src="loaded ? currentUrl : placeholder"
             :alt="'Post ' + displayedPost.id"
             loading="lazy"
             :style="{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease-in-out', width: '100%', height: '100%', objectFit: 'cover' }"
             @load="onImageLoad"
             @error="onError" />
      </div>
      <div class="post-card-overlay">
        <div class="post-card-meta">
          <!-- Clickable Interactive Version Switcher Badges -->
          <span v-for="site in allSites" 
                :key="site" 
                class="post-card-badge" 
                :class="[site, { 'interactive-badge': allSites.length > 1, 'active-site': allSites.length > 1 && activeSite === site }]"
                :title="allSites.length > 1 ? 'Switch to ' + site + ' version' : ''"
                @click.stop="allSites.length > 1 ? switchActiveSite(site) : null">
            {{ site === props.post.source_site ? site : '+ ' + site }}
          </span>
          <span class="post-card-rating" :class="ratingClass">{{ ratingLabel }}</span>
          <span v-if="isAnimated && !isFlash" class="post-card-badge" style="background:#ff4757;color:white;">▶</span>
          <span v-if="isFlash" class="post-card-badge" style="background:#f1c40f;color:black;font-weight:bold;">FLASH</span>
          <span v-if="displayedPost.score !== undefined" class="post-card-score">★ {{ displayedPost.score }}</span>
        </div>
      </div>
      <button v-if="!isMobile" class="post-card-fav" :class="{ active: isFav }"
              @click.stop="toggleFav"
              :title="lang.t('nav_favorites')">
        {{ isFav ? '❤️' : '🤍' }}
      </button>
      <button v-if="!isMobile" class="post-card-dislike" :class="{ active: isDisliked }"
              @click.stop="doDislike"
              :title="lang.t('dislikes_tab') || 'Dislike'">
        👎
      </button>
      <div v-if="showLikeAnimation" class="like-animation">❤️</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { useFeedStore } from '../stores/feed'
import { apiAddFavorite, apiCheckFavorite, apiRemoveFavorite } from '../api'
import { useEventLogger } from '../composables/useEventLogger'
import { RATING_MAP, RATING_LABELS } from '../types'
import type { Post, RatingClass, SiteName } from '../types'
import { computeDifferenceHash } from '../utils/perceptualHash'

const feed = useFeedStore()

const props = defineProps<{
  post: Post
  favorite?: boolean
}>()

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const { logLike, logFavourite } = useEventLogger()

// Hashing States
const isVerifying = ref(
  !props.post.hash ||
  props.post.hash.startsWith('md5-') ||
  props.post.hash.startsWith('fn-') ||
  props.post.hash.startsWith('id-')
)
const isInViewport = ref(typeof window === 'undefined' || !('IntersectionObserver' in window))
const activeSite = ref<SiteName>(props.post.source_site)

const imgLoaderRef = ref<HTMLImageElement | null>(null)
const videoLoaderRef = ref<HTMLVideoElement | null>(null)

// Computed list of all site versions for this post
const allSites = computed<SiteName[]>(() => {
  const list: SiteName[] = [props.post.source_site]
  if (props.post.duplicate_sites) {
    for (const site of props.post.duplicate_sites) {
      if (!list.includes(site)) {
        list.push(site)
      }
    }
  }
  return list
})

// Computes the active post object to render
const displayedPost = computed<Post>(() => {
  if (activeSite.value === props.post.source_site) {
    return props.post
  }
  const dup = props.post.duplicates?.find(d => d.source_site === activeSite.value)
  return dup || props.post
})

const loaded = ref(false)
const cardRef = ref<HTMLElement | null>(null)
const isFav = ref(props.favorite ?? false)
const placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="10" height="10"%3E%3C/svg%3E'

const currentUrl = ref('')

function updateUrl() {
  const q = feed.previewQuality // 'thumbnail' | 'sample' | 'full'
  const p = displayedPost.value
  if (q === 'thumbnail') {
    currentUrl.value = p.preview_url || p.sample_url || p.file_url || ''
  } else if (q === 'sample') {
    currentUrl.value = p.sample_url || p.preview_url || p.file_url || ''
  } else { // 'full'
    currentUrl.value = p.file_url || p.sample_url || p.preview_url || ''
  }
}

// Watch for quality setting changes or active post updates
watch([() => feed.previewQuality, displayedPost], () => {
  loaded.value = false
  updateUrl()
}, { deep: true })

// Resolve URL immediately during component instantiation
updateUrl()

const isAnimated = computed(() =>
  ['gif', 'webm', 'mp4', 'm4v', 'mov', 'mkv', 'swf'].includes((displayedPost.value.file_ext || '').toLowerCase())
)

const isFlash = computed(() => (displayedPost.value.file_ext || '').toLowerCase() === 'swf')

const ratingClass = computed<RatingClass>(() => RATING_MAP[(displayedPost.value.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')

const mediaStyle = computed(() => {
  const p = displayedPost.value
  if (p.width && p.height) {
    return { aspectRatio: `${p.width} / ${p.height}`, background: 'var(--bg-secondary)', overflow: 'hidden' }
  }
  return { minHeight: '200px', background: 'var(--bg-secondary)', overflow: 'hidden' }
})

// Hashing Callbacks
function onImageLoaded() {
  const img = imgLoaderRef.value
  if (img) {
    performVerification(img)
  }
}

let videoTimeout: ReturnType<typeof setTimeout> | null = null

function onVideoLoaded() {
  const video = videoLoaderRef.value
  if (!video) return
  
  // Seek to 1s or half duration to get a real frame instead of black screen
  const seekTime = Math.min(1.0, video.duration / 2 || 0)
  video.currentTime = seekTime
  
  // Set a backup timeout of 2 seconds in case seeked doesn't fire
  videoTimeout = setTimeout(() => {
    if (isVerifying.value) {
      performVerification(video)
    }
  }, 2000)

  video.addEventListener('seeked', () => {
    if (videoTimeout) clearTimeout(videoTimeout)
    performVerification(video)
  }, { once: true })
}

function onHashError() {
  performVerification(null)
}

function performVerification(mediaEl: HTMLImageElement | HTMLVideoElement | null) {
  if (!isVerifying.value) return

  let hash = ''
  if (mediaEl) {
    try {
      hash = computeDifferenceHash(mediaEl, 16)
    } catch (e) {
      console.error('Failed to compute perceptual hash, fallback to instant hash', e)
    }
  }

  // Fallback if hash calculation failed
  if (!hash) {
    hash = feed.getInstantPostHash(props.post)
  }

  const isDuplicate = feed.registerPostHash(props.post.id, props.post.source_site, hash, props.post.tags)
  
  if (!isDuplicate) {
    isVerifying.value = false
    loaded.value = false
    updateUrl()
  }
}

function switchActiveSite(site: SiteName) {
  activeSite.value = site
  loaded.value = false
  updateUrl()
}

function onImageLoad() {
  loaded.value = true
}

function onError() {
  const p = displayedPost.value
  if (currentUrl.value === p.file_url) {
    if (p.sample_url && p.sample_url !== p.file_url) {
      loaded.value = false
      currentUrl.value = p.sample_url
      return
    } else if (p.preview_url && p.preview_url !== p.file_url) {
      loaded.value = false
      currentUrl.value = p.preview_url
      return
    }
  }
  
  if (currentUrl.value === p.sample_url) {
    if (p.preview_url && p.preview_url !== p.sample_url) {
      loaded.value = false
      currentUrl.value = p.preview_url
      return
    }
  }

  loaded.value = true
}

async function toggleFav() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }
  try {
    if (isFav.value) {
      const check = await apiCheckFavorite(displayedPost.value.source_site, String(displayedPost.value.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
      isFav.value = false
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      await apiAddFavorite(displayedPost.value)
      isFav.value = true
      isDisliked.value = false
      logFavourite(displayedPost.value)
      toast.show(lang.t('added_fav'), 'success')
    }
  } catch (e) {
    toast.show((e as Error).message, 'error')
  }
}

const isDisliked = ref(displayedPost.value.is_dislike || false)

async function doDislike() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }

  if (isDisliked.value) {
    try {
      const check = await apiCheckFavorite(displayedPost.value.source_site, String(displayedPost.value.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
    } catch { /* ignore */ }
    isDisliked.value = false
    hidden.value = true
    toast.show(lang.t('removed_fav') || 'Removed', 'info')
  } else {
    apiAddFavorite(displayedPost.value, true).catch(() => {})
    isDisliked.value = true
    isFav.value = false
    hidden.value = true
  }
}

const hidden = ref(false)
const showLikeAnimation = ref(false)
const swipeDiff = ref(0)
const swiping = ref(false)
const isMobile = ref(false)

let touchStartX = 0
let touchStartY = 0
let tapTimeout: ReturnType<typeof setTimeout> | null = null
let lastTapTime = 0

function updateMobileState() {
  isMobile.value = window.matchMedia('(max-width: 768px)').matches
}

let observer: IntersectionObserver | null = null

onMounted(() => {
  updateUrl()
  updateMobileState()
  window.addEventListener('resize', updateMobileState)

  if (isVerifying.value && !isInViewport.value) {
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        isInViewport.value = true
        observer?.disconnect()
        observer = null
      }
    }, {
      rootMargin: '200px'
    })
    if (cardRef.value) {
      observer.observe(cardRef.value)
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMobileState)
  if (tapTimeout) clearTimeout(tapTimeout)
  if (videoTimeout) clearTimeout(videoTimeout)
  if (observer) {
    observer.disconnect()
    observer = null
  }
})

function doLikeAnimation() {
  showLikeAnimation.value = true
  setTimeout(() => { showLikeAnimation.value = false }, 800)
}

function handleCardClick() {
  if (!isMobile.value) {
    router.push({ 
      name: 'post', 
      query: { id: String(displayedPost.value.id), site: displayedPost.value.source_site } 
    })
    return
  }

  const now = Date.now()
  if (now - lastTapTime < 300) {
    if (tapTimeout) clearTimeout(tapTimeout)
    lastTapTime = 0
    if (!isFav.value) toggleFav()
    logLike(displayedPost.value)
    doLikeAnimation()
  } else {
    lastTapTime = now
    tapTimeout = setTimeout(() => {
      router.push({ 
        name: 'post', 
        query: { id: String(displayedPost.value.id), site: displayedPost.value.source_site } 
      })
    }, 300)
  }
}

function onTouchStart(e: TouchEvent) {
  touchStartX = e.changedTouches[0].screenX
  touchStartY = e.changedTouches[0].screenY
  swiping.value = true
}

function onTouchMove(e: TouchEvent) {
  if (!swiping.value) return
  const diffX = e.changedTouches[0].screenX - touchStartX
  const diffY = e.changedTouches[0].screenY - touchStartY

  if (Math.abs(diffX) > Math.abs(diffY)) {
    swipeDiff.value = diffX
  } else {
    swiping.value = false
    swipeDiff.value = 0
  }
}

function onTouchEnd() {
  swiping.value = false
  if (Math.abs(swipeDiff.value) > 80) {
    const dir = swipeDiff.value > 0 ? 1 : -1
    swipeDiff.value = dir * window.innerWidth
    setTimeout(() => {
      if (auth.isAuthenticated) {
        apiAddFavorite(displayedPost.value, true).catch(() => {})
      }
      isFav.value = false
      hidden.value = true
    }, 300)
  } else {
    swipeDiff.value = 0
  }
}

defineExpose({ cardRef, post: props.post })
</script>
