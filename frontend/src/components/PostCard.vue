<template>
  <div ref="cardRef" v-show="!hidden" class="post-card" :class="ratingClass" @click="handleCardClick"
       @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd"
       :style="{ transform: swipeDiff ? `translateX(${swipeDiff}px)` : '', transition: swiping ? 'none' : 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)', opacity: Math.max(0, 1 - Math.abs(swipeDiff) / 200), willChange: swiping ? 'transform, opacity' : 'auto' }">
    
    <template v-if="!isOffScreen">
      <!-- Main Content (Always Visible Instantly) -->
      <div class="post-card-media" :style="mediaStyle">
        <!-- Long static posts render a cached top-slice canvas instead of the full
             image (see utils/cropCache): the browser would otherwise decode the
             whole 20-40MP strip on every scroll re-entry, causing heavy jank. -->
        <div v-if="useCrop" :ref="setCropHost" class="post-card-crop-host"></div>
        <img v-else class="post-card-img"
             :class="{ 'post-card-img-cropped': isLong }"
             :src="currentUrl || placeholder"
             :alt="altText"
             loading="lazy"
             decoding="async"
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
                :title="allSites.length > 1 ? lang.t('switch_version', { site }) : ''"
                :role="allSites.length > 1 ? 'button' : undefined"
                :tabindex="allSites.length > 1 ? 0 : undefined"
                @click.stop="allSites.length > 1 ? switchActiveSite(site) : null"
                @keydown.enter.stop.prevent="allSites.length > 1 ? switchActiveSite(site) : null"
                @keydown.space.stop.prevent="allSites.length > 1 ? switchActiveSite(site) : null">
            {{ site === props.post.source_site ? site : '+ ' + site }}
          </span>
          <span class="post-card-rating" :class="ratingClass" :aria-label="'Rating: ' + ratingLabel">{{ ratingLabel }}</span>
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
              :title="lang.t('dislikes_tab')">
        👎
      </button>
      <div v-if="showLikeAnimation" class="like-animation">❤️</div>
    </template>
    <div v-else class="post-card-offscreen-placeholder" :style="mediaStyle"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { useFeedStore } from '../stores/feed'
import { apiAddFavorite, apiCheckFavorite, apiRemoveFavorite } from '../api'
import { useEventLogger } from '../composables/useEventLogger'
import { useIsMobile } from '../composables/useIsMobile'
import { RATING_MAP, RATING_LABELS } from '../types'
import { sanitizeUrl } from '../utils/security'
import { getCroppedCanvas, requestCroppedCanvas, cropTargetWidth } from '../utils/cropCache'
import type { Post, RatingClass, SiteName } from '../types'

const feed = useFeedStore()

const props = withDefaults(
  defineProps<{
    post: Post & { favorite?: boolean }
    isOffScreen?: boolean
  }>(),
  { isOffScreen: true }
)

const emit = defineEmits<{
  (e: 'click-media', post: Post): void
  (e: 'favorite-changed', payload: { sourceSite: SiteName, postId: string | number, isFav: boolean, isDislike: boolean }): void
}>()

const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const { logLike, logFavourite } = useEventLogger()

const activeSite = ref<SiteName>(props.post.source_site)

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

const isMobile = useIsMobile()
const loaded = ref(false)
const cardRef = ref<HTMLElement | null>(null)
const isFav = ref(props.post.favorite ?? false)
const placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="10" height="10"%3E%3C/svg%3E'

const currentUrl = ref('')

function updateUrl() {
  const q = feed.previewQuality // 'thumbnail' | 'sample' | 'full'
  const p = displayedPost.value
  let newUrl = ''
  
  const videoExtensions = ['mp4', 'webm', 'm4v', 'mov', 'mkv', 'swf', 'ogv']
  const isVideoExt = (url: string) => {
    if (!url) return false
    const cleanUrl = (url.split('?')[0] ?? '').toLowerCase()
    return videoExtensions.some(ext => cleanUrl.endsWith('.' + ext))
  }

  const getFirstNonVideo = (candidates: (string | null | undefined)[]) => {
    for (const c of candidates) {
      if (c && !isVideoExt(c)) {
        return c
      }
    }
    return (candidates.find(c => c) || '') as string
  }

  if (q === 'thumbnail') {
    newUrl = getFirstNonVideo([p.preview_url, p.sample_url, p.file_url])
  } else if (q === 'sample') {
    newUrl = getFirstNonVideo([p.sample_url, p.preview_url, p.file_url])
  } else { // 'full'
    newUrl = getFirstNonVideo([p.file_url, p.sample_url, p.preview_url])
  }
  
  if (isVideoExt(newUrl)) {
    newUrl = ''
  }
  
  const sanitized = sanitizeUrl(newUrl)
  if (currentUrl.value !== sanitized) {
    loaded.value = false
    currentUrl.value = sanitized
  }
}

// Watch for quality setting changes or active post updates shallowly (prevent traversing tags/duplicates)
watch(
  [
    () => feed.previewQuality,
    () => displayedPost.value.id,
    () => displayedPost.value.source_site,
    () => displayedPost.value.preview_url,
    () => displayedPost.value.sample_url,
    () => displayedPost.value.file_url
  ],
  () => {
    updateUrl()
  }
)

// Resolve URL immediately during component instantiation
updateUrl()

const isAnimated = computed(() =>
  ['gif', 'webm', 'mp4', 'm4v', 'mov', 'mkv', 'swf'].includes((displayedPost.value.file_ext || '').toLowerCase())
)

const isFlash = computed(() => (displayedPost.value.file_ext || '').toLowerCase() === 'swf')

const ratingClass = computed<RatingClass>(() => RATING_MAP[(displayedPost.value.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')

const LONG_RATIO = 21 / 9 // height is >= 21/9 of width => very tall post

const isLong = computed(() => {
  const p = displayedPost.value
  if (p.width && p.height && p.width > 0) {
    return p.height / p.width >= LONG_RATIO
  }
  return false
})

const mediaStyle = computed(() => {
  const p = displayedPost.value
  if (isLong.value) {
    return { aspectRatio: '9 / 21', background: 'var(--bg-secondary)', overflow: 'hidden' }
  }
  if (p.width && p.height) {
    return { aspectRatio: `${p.width} / ${p.height}`, background: 'var(--bg-secondary)', overflow: 'hidden' }
  }
  return { minHeight: '200px', background: 'var(--bg-secondary)', overflow: 'hidden' }
})

// Cropped-preview pipeline for long static posts. Animated/flash posts keep the
// plain <img> path — a canvas would freeze them on the first frame.
const cropFailed = ref(false)
const useCrop = computed(() =>
  isLong.value && !isAnimated.value && !isFlash.value && !!displayedPost.value.file_url && !cropFailed.value
)

const cropHostEl = ref<HTMLElement | null>(null)
let cropGen = 0

function setCropHost(el: Element | ComponentPublicInstance | null) {
  const host = (el instanceof HTMLElement ? el : null)
  cropHostEl.value = host
  if (host) {
    attachCrop(host)
  } else {
    cropGen++ // host unmounted by virtualization — cancel any pending attach
  }
}

async function attachCrop(host: HTMLElement) {
  const gen = ++cropGen
  const p = displayedPost.value
  const src = p.file_url ? sanitizeUrl(p.file_url) : ''
  if (!src) {
    cropFailed.value = true
    return
  }
  const targetW = cropTargetWidth(feed.cardSize, window.devicePixelRatio || 1)
  const key = `${p.source_site}-${p.id}-${targetW}`

  const cached = getCroppedCanvas(key)
  if (cached) {
    if (gen === cropGen) host.replaceChildren(cached)
    return
  }

  try {
    const canvas = await requestCroppedCanvas(key, src, targetW)
    if (gen === cropGen && host.isConnected) {
      host.replaceChildren(canvas)
    }
  } catch {
    if (gen === cropGen) cropFailed.value = true // fall back to the plain <img> path
  }
}

// Rebuild the crop when the displayed version or the card size changes
watch(
  [() => displayedPost.value.id, () => displayedPost.value.source_site, () => feed.cardSize],
  () => {
    cropFailed.value = false
    if (useCrop.value && cropHostEl.value) attachCrop(cropHostEl.value)
  }
)

const altText = computed(() => {
  const firstTag = displayedPost.value.tags?.[0]
  const rating = displayedPost.value.rating ? `[Rating: ${displayedPost.value.rating.toUpperCase()}]` : ''
  return `Post ${displayedPost.value.id} ${firstTag ? '- ' + firstTag.replace(/_/g, ' ') : ''} ${rating}`.trim()
})

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
      currentUrl.value = sanitizeUrl(p.sample_url)
      return
    } else if (p.preview_url && p.preview_url !== p.file_url) {
      loaded.value = false
      currentUrl.value = sanitizeUrl(p.preview_url)
      return
    }
  }
  
  if (currentUrl.value === p.sample_url) {
    if (p.preview_url && p.preview_url !== p.sample_url) {
      loaded.value = false
      currentUrl.value = sanitizeUrl(p.preview_url)
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
      emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: false, isDislike: false })
    } else {
      await apiAddFavorite(displayedPost.value)
      isFav.value = true
      isDisliked.value = false
      logFavourite(displayedPost.value)
      toast.show(lang.t('added_fav'), 'success')
      emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: true, isDislike: false })
    }
  } catch (e) {
    toast.show((e as Error).message, 'error')
  }
}

const hidden = ref(false)
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
    hidden.value = false
    toast.show(lang.t('removed_fav'), 'info')
    emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: false, isDislike: false })
  } else {
    try {
      await apiAddFavorite(displayedPost.value, true)
    } catch { /* ignore */ }
    isDisliked.value = true
    isFav.value = false
    hidden.value = true
    emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: false, isDislike: true })

    toast.show(
      lang.t('removed_fav'),
      'info',
      {
        label: lang.t('undo'),
        callback: async () => {
          try {
            const check = await apiCheckFavorite(displayedPost.value.source_site, String(displayedPost.value.id))
            if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
          } catch { /* ignore */ }
          isDisliked.value = false
          hidden.value = false
          emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: false, isDislike: false })
        }
      }
    )
  }
}
const showLikeAnimation = ref(false)
const swipeDiff = ref(0)
const swiping = ref(false)

let touchStartX = 0
let touchStartY = 0
let tapTimeout: ReturnType<typeof setTimeout> | null = null
let lastTapTime = 0

watch(
  () => displayedPost.value,
  (newPost) => {
    isFav.value = newPost.favorite ?? false
    isDisliked.value = newPost.is_dislike ?? false
  },
  { immediate: true, deep: false }
)

onMounted(() => {
  updateUrl()
})

onUnmounted(() => {
  if (tapTimeout) clearTimeout(tapTimeout)
})

function doLikeAnimation() {
  showLikeAnimation.value = true
  setTimeout(() => { showLikeAnimation.value = false }, 800)
}

function handleCardClick() {
  if (!isMobile.value) {
    emit('click-media', displayedPost.value)
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
      emit('click-media', displayedPost.value)
    }, 300)
  }
}

function onTouchStart(e: TouchEvent) {
  const touch = e.changedTouches[0]
  if (touch) {
    touchStartX = touch.screenX
    touchStartY = touch.screenY
    swiping.value = true
  }
}

function onTouchMove(e: TouchEvent) {
  if (!swiping.value) return
  const touch = e.changedTouches[0]
  if (touch) {
    const diffX = touch.screenX - touchStartX
    const diffY = touch.screenY - touchStartY

    if (Math.abs(diffX) > Math.abs(diffY)) {
      swipeDiff.value = diffX
    } else {
      swiping.value = false
      swipeDiff.value = 0
    }
  }
}

function onTouchEnd() {
  swiping.value = false
  if (Math.abs(swipeDiff.value) > 80) {
    if (!auth.isAuthenticated) {
      toast.show(lang.t('login_to_fav'), 'error')
      swipeDiff.value = 0
      return
    }
    const dir = swipeDiff.value > 0 ? 1 : -1
    swipeDiff.value = dir * window.innerWidth
    setTimeout(() => {
      apiAddFavorite(displayedPost.value, true).catch(() => {})
      isFav.value = false
      isDisliked.value = true
      hidden.value = true
      emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: false, isDislike: true })

      toast.show(
        lang.t('removed_fav'),
        'info',
        {
          label: lang.t('undo'),
          callback: async () => {
            try {
              const check = await apiCheckFavorite(displayedPost.value.source_site, String(displayedPost.value.id))
              if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
            } catch { /* ignore */ }
            isDisliked.value = false
            hidden.value = false
            emit('favorite-changed', { sourceSite: displayedPost.value.source_site, postId: displayedPost.value.id, isFav: false, isDislike: false })
          }
        }
      )
    }, 300)
  } else {
    swipeDiff.value = 0
  }
}

defineExpose({ cardRef, post: props.post })
</script>
