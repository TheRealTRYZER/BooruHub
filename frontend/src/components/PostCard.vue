<template>
  <div v-show="!hidden" class="post-card" @click="handleCardClick" 
       @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd"
       :style="{ transform: swipeDiff ? `translateX(${swipeDiff}px)` : '', transition: swiping ? 'none' : 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)', opacity: Math.max(0, 1 - Math.abs(swipeDiff) / 200) }">
    <div class="post-card-media" :style="mediaStyle" ref="cardEl">
      <img class="post-card-img"
           :src="activeSrc"
           :alt="'Post ' + post.id"
           referrerpolicy="no-referrer"
           :style="{ opacity: loaded ? 1 : 0, transition: 'opacity 0.3s ease-in-out', width: '100%', height: '100%', objectFit: 'cover' }"
           @load="onLoad"
           @error="onError" />
    </div>
    <div class="post-card-overlay">
      <div class="post-card-meta">
        <span class="post-card-badge" :class="post.source_site">{{ post.source_site }}</span>
        <span class="post-card-rating" :class="ratingClass">{{ ratingLabel }}</span>
        <span v-if="isAnimated" class="post-card-badge" style="background:#ff4757;color:white;">▶</span>
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

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useToastStore } from '../stores/toast.js'
import { useLangStore } from '../stores/lang.js'
import { apiAddFavorite, apiCheckFavorite, apiRemoveFavorite } from '../api.js'

const props = defineProps({
  post: { type: Object, required: true },
  favorite: { type: Boolean, default: false },
})

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

const loaded = ref(false)
const isFav = ref(props.favorite)
const cardEl = ref(null)

// activeSrc starts empty — IntersectionObserver sets it when card enters viewport
const activeSrc = ref('')
const currentUrl = ref(props.post.sample_url || props.post.preview_url || '')
let observer = null
let errorCount = 0

const isAnimated = computed(() =>
  ['gif', 'webm', 'mp4', 'm4v', 'mov', 'mkv'].includes((props.post.file_ext || '').toLowerCase())
)

const ratingMap = { g: 'safe', general: 'safe', s: 'safe', q: 'questionable', questionable: 'questionable', e: 'explicit', explicit: 'explicit' }
const ratingLabels = { safe: 'S', questionable: 'Q', explicit: 'E', unknown: '?' }

const ratingClass = computed(() => ratingMap[(props.post.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => ratingLabels[ratingClass.value] || '?')

const mediaStyle = computed(() => {
  const p = props.post
  if (p.width && p.height) {
    return { aspectRatio: `${p.width} / ${p.height}`, background: 'var(--bg-secondary)', overflow: 'hidden' }
  }
  return { minHeight: '200px', background: 'var(--bg-secondary)', overflow: 'hidden' }
})

function onLoad() {
  loaded.value = true
  errorCount = 0
}

function onError() {
  const p = props.post
  errorCount++
  
  setTimeout(() => {
    // Stage 1: sample → preview
    if (errorCount === 1 && p.preview_url && activeSrc.value !== p.preview_url) {
      activeSrc.value = p.preview_url
      return
    }
    // Stage 2: preview → file_url
    if (errorCount === 2 && p.file_url && activeSrc.value !== p.file_url) {
      activeSrc.value = p.file_url
      return
    }
    // Stage 3: all direct variants failed — try PROXY
    if (errorCount === 3) {
      console.log('Final fallback — using server proxy for:', p.id)
      const proxyBase = window.location.origin
      activeSrc.value = `${proxyBase}/api/posts/proxy?url=${encodeURIComponent(p.sample_url || p.file_url)}`
      return
    }

    // Stage 4: truly dead
    loaded.value = true
  }, 150)
}

function activate() {
  if (activeSrc.value) return
  activeSrc.value = currentUrl.value
}

onMounted(() => {
  if (!cardEl.value) { activate(); return }
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting) {
        activate()
        observer?.disconnect()
        observer = null
      }
    },
    { rootMargin: '600px' }
  )
  observer.observe(cardEl.value)
})

onUnmounted(() => { observer?.disconnect() })

function toggleFav() {
  if (!auth.isAuthenticated) { toast.show(lang.t('login_to_fav'), 'error'); return }
  try {
    if (isFav.value) {
      apiCheckFavorite(props.post.source_site, props.post.id).then(check => {
        if (check.favorite_id) apiRemoveFavorite(check.favorite_id)
      })
      isFav.value = false
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      apiAddFavorite(props.post)
      isFav.value = true
      isDisliked.value = false
      toast.show(lang.t('added_fav'), 'success')
    }
  } catch (e) { toast.show(e.message, 'error') }
}

const isDisliked = ref(props.post.is_dislike || false)

function doDislike() {
  if (!auth.isAuthenticated) { toast.show(lang.t('login_to_fav'), 'error'); return }
  if (isDisliked.value) {
    apiCheckFavorite(props.post.source_site, props.post.id).then(check => {
      if (check.favorite_id) apiRemoveFavorite(check.favorite_id)
    })
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
let tapTimeout = null
let lastTapTime = 0

function doLikeAnimation() {
  showLikeAnimation.value = true
  setTimeout(() => { showLikeAnimation.value = false }, 800)
}

function handleCardClick() {
  const now = Date.now()
  if (now - lastTapTime < 300) {
    clearTimeout(tapTimeout)
    lastTapTime = 0
    if (!isFav.value) toggleFav()
    doLikeAnimation()
  } else {
    lastTapTime = now
    tapTimeout = setTimeout(() => {
      router.push({ name: 'post', query: { id: props.post.id, site: props.post.source_site } })
    }, 300)
  }
}

function onTouchStart(e) {
  touchStartX = e.changedTouches[0].screenX
  touchStartY = e.changedTouches[0].screenY
  swiping.value = true
}

function onTouchMove(e) {
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
      if (auth.isAuthenticated) apiAddFavorite(props.post, true).catch(() => {})
      isFav.value = false
      hidden.value = true
    }, 300)
  } else {
    swipeDiff.value = 0
  }
}
</script>
