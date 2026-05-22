<template>
  <div ref="cardRef" v-show="!hidden" class="post-card" @click="handleCardClick"
       @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd"
       :style="{ transform: swipeDiff ? `translateX(${swipeDiff}px)` : '', transition: swiping ? 'none' : 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)', opacity: Math.max(0, 1 - Math.abs(swipeDiff) / 200) }">
    <div class="post-card-media" :style="mediaStyle">
      <img class="post-card-img"
           :src="loaded ? currentUrl : placeholder"
           :alt="'Post ' + post.id"
           loading="lazy"
           :style="{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease-in-out', width: '100%', height: '100%', objectFit: 'cover' }"
           @load="onImageLoad"
           @error="onError" />
    </div>
    <div class="post-card-overlay">
      <div class="post-card-meta">
        <span class="post-card-badge" :class="post.source_site">{{ post.source_site }}</span>
        <template v-if="post.duplicate_sites && post.duplicate_sites.length">
          <span v-for="dupSite in post.duplicate_sites" :key="dupSite" class="post-card-badge duplicate-badge" :class="dupSite" :title="'Duplicate found on ' + dupSite">
            + {{ dupSite }}
          </span>
        </template>
        <span class="post-card-rating" :class="ratingClass">{{ ratingLabel }}</span>
        <span v-if="isAnimated && !isFlash" class="post-card-badge" style="background:#ff4757;color:white;">▶</span>
        <span v-if="isFlash" class="post-card-badge" style="background:#f1c40f;color:black;font-weight:bold;">FLASH</span>
        <span v-if="post.score !== undefined" class="post-card-score">★ {{ post.score }}</span>
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
import type { Post, RatingClass } from '../types'

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
const loaded = ref(false)
const cardRef = ref<HTMLElement | null>(null)
const isFav = ref(props.favorite ?? false)
const placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="10" height="10"%3E%3C/svg%3E'

const currentUrl = ref('')

function updateUrl() {
  const q = feed.previewQuality // 'thumbnail' | 'sample' | 'full'
  const p = props.post
  if (q === 'thumbnail') {
    currentUrl.value = p.preview_url || p.sample_url || p.file_url || ''
  } else if (q === 'sample') {
    currentUrl.value = p.sample_url || p.preview_url || p.file_url || ''
  } else { // 'full'
    currentUrl.value = p.file_url || p.sample_url || p.preview_url || ''
  }
}

// Watch for quality setting changes
watch(() => feed.previewQuality, () => {
  loaded.value = false
  updateUrl()
})
const isAnimated = computed(() =>
  ['gif', 'webm', 'mp4', 'm4v', 'mov', 'mkv', 'swf'].includes((props.post.file_ext || '').toLowerCase())
)

const isFlash = computed(() => (props.post.file_ext || '').toLowerCase() === 'swf')

const ratingClass = computed<RatingClass>(() => RATING_MAP[(props.post.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')

const mediaStyle = computed(() => {
  const p = props.post
  if (p.width && p.height) {
    return { aspectRatio: `${p.width} / ${p.height}`, background: 'var(--bg-secondary)', overflow: 'hidden' }
  }
  return { minHeight: '200px', background: 'var(--bg-secondary)', overflow: 'hidden' }
})

function calculateAverageHash(img: HTMLImageElement): string {
  const size = 16
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Could not get 2d context')
  
  ctx.drawImage(img, 0, 0, size, size)
  const imgData = ctx.getImageData(0, 0, size, size)
  const data = imgData.data
  
  let sum = 0
  let minGray = 255
  let maxGray = 0
  const grays = new Uint8Array(size * size)
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    const gray = Math.round(0.299 * r + 0.587 * g + 0.114 * b)
    grays[i / 4] = gray
    sum += gray
    if (gray < minGray) minGray = gray
    if (gray > maxGray) maxGray = gray
  }
  
  // Safeguard: If the image is extremely low contrast/monochrome (like a pure black or solid color frame),
  // throw an error to fallback to metadata/URL hashes to avoid false duplicate matches.
  if (maxGray - minGray < 5) {
    throw new Error('Image is monochrome or extremely low contrast')
  }
  
  const avg = sum / (size * size)
  let hash = ''
  for (let i = 0; i < grays.length; i++) {
    hash += grays[i] >= avg ? '1' : '0'
  }
  
  let hexHash = ''
  for (let i = 0; i < hash.length; i += 4) {
    const chunk = hash.substring(i, i + 4)
    hexHash += parseInt(chunk, 2).toString(16)
  }
  return hexHash
}

function computePostHash(img: HTMLImageElement | null, post: Post): string {
  // Video Safeguard: Skip canvas parsing for video/animated files because
  // their previews are often blank, black, or highly generic cover frames
  if (img && !isAnimated.value) {
    try {
      return calculateAverageHash(img)
    } catch (e) {
      // SecurityError (CORS) or monochrome safeguard triggered
    }
  }
  
  if (post.md5) {
    return `md5-${post.md5}`
  }
  
  const fileUrl = post.file_url || post.sample_url || post.preview_url || ''
  if (fileUrl) {
    const filename = fileUrl.substring(fileUrl.lastIndexOf('/') + 1)
    let hash = 0
    for (let i = 0; i < filename.length; i++) {
      const char = filename.charCodeAt(i)
      hash = (hash << 5) - hash + char
      hash |= 0
    }
    return `fn-${hash}`
  }
  
  return `id-${post.source_site}-${post.id}`
}

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  if (img.src && img.src.startsWith('data:')) {
    // Placeholder loaded, triggers real URL load
    loaded.value = true
    return
  }
  
  loaded.value = true
  
  // Calculate average hash or fallback hash, and register in Pinia store
  const hash = computePostHash(img, props.post)
  feed.registerPostHash(props.post.id, props.post.source_site, hash, props.post.tags)
}

function onError() {
  const p = props.post
  // If current is file_url, try sample_url, then preview_url
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
  
  // If current is sample_url, try preview_url
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
      const check = await apiCheckFavorite(props.post.source_site, String(props.post.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
      isFav.value = false
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      await apiAddFavorite(props.post)
      isFav.value = true
      isDisliked.value = false
      logFavourite(props.post)
      toast.show(lang.t('added_fav'), 'success')
    }
  } catch (e) {
    toast.show((e as Error).message, 'error')
  }
}

const isDisliked = ref(props.post.is_dislike || false)

async function doDislike() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }

  if (isDisliked.value) {
    try {
      const check = await apiCheckFavorite(props.post.source_site, String(props.post.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
    } catch { /* ignore */ }
    isDisliked.value = false
    hidden.value = true
    toast.show(lang.t('removed_fav') || 'Removed', 'info')
  } else {
    apiAddFavorite(props.post, true).catch(() => {})
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

onMounted(() => {
  updateUrl()
  updateMobileState()
  window.addEventListener('resize', updateMobileState)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMobileState)
  if (tapTimeout) clearTimeout(tapTimeout)
})

function doLikeAnimation() {
  showLikeAnimation.value = true
  setTimeout(() => { showLikeAnimation.value = false }, 800)
}

function handleCardClick() {
  if (!isMobile.value) {
    // Desktop: Immediate navigation
    router.push({ 
      name: 'post', 
      query: { id: String(props.post.id), site: props.post.source_site } 
    })
    return
  }

  // Mobile: Double-tap buffer to allow "Like" action
  const now = Date.now()
  if (now - lastTapTime < 300) {
    if (tapTimeout) clearTimeout(tapTimeout)
    lastTapTime = 0
    if (!isFav.value) toggleFav()
    logLike(props.post)
    doLikeAnimation()
  } else {
    lastTapTime = now
    tapTimeout = setTimeout(() => {
      router.push({ 
        name: 'post', 
        query: { id: String(props.post.id), site: props.post.source_site } 
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
        apiAddFavorite(props.post, true).catch(() => {})
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
