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
           @load="loaded = true"
           @error="onError" />
    </div>
    <div class="post-card-overlay">
      <div class="post-card-meta">
        <span class="post-card-badge" :class="post.source_site">{{ post.source_site }}</span>
        <span class="post-card-rating" :class="ratingClass">{{ ratingLabel }}</span>
        <span v-if="isAnimated && !isFlash" class="post-card-badge" style="background:#ff4757;color:white;">▶</span>
        <span v-if="isFlash" class="post-card-badge" style="background:#f1c40f;color:black;font-weight:bold;">FLASH</span>
        <span v-if="post.score !== undefined" class="post-card-score">★ {{ post.score }}</span>
      </div>
    </div>
    <button class="post-card-fav" :class="{ active: isFav }"
            @click.stop="toggleFav"
            :title="lang.t('nav_favorites')">
      {{ isFav ? '❤️' : '🤍' }}
    </button>
    <button class="post-card-dislike" :class="{ active: isDisliked }"
            @click.stop="doDislike"
            :title="lang.t('dislikes_tab') || 'Dislike'">
      👎
    </button>
    <div v-if="showLikeAnimation" class="like-animation">❤️</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiAddFavorite, apiCheckFavorite, apiRemoveFavorite } from '../api'
import { useEventLogger } from '../composables/useEventLogger'
import { RATING_MAP, RATING_LABELS } from '../types'
import type { Post, RatingClass } from '../types'

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

const currentUrl = ref(props.post.sample_url || props.post.preview_url || '')
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

function onError() {
  const p = props.post
  if (currentUrl.value === p.sample_url && p.preview_url) {
    loaded.value = false
    currentUrl.value = p.preview_url
    return
  }

  if ((currentUrl.value === p.preview_url || currentUrl.value === p.sample_url) && p.file_url && currentUrl.value !== p.file_url) {
    loaded.value = false
    currentUrl.value = p.file_url
    return
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

let touchStartX = 0
let touchStartY = 0
let tapTimeout: ReturnType<typeof setTimeout> | null = null
let lastTapTime = 0

function doLikeAnimation() {
  showLikeAnimation.value = true
  setTimeout(() => { showLikeAnimation.value = false }, 800)
}

function handleCardClick() {
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
      router.push({ name: 'post', query: { id: String(props.post.id), site: props.post.source_site } })
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
