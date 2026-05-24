<template>
  <Transition name="fade">
    <div class="lightbox-overlay" @click.self="closeLightbox">
      
      <!-- Dynamic Ambilight Theatre Backdrop -->
      <div class="ambient-glow-container">
        <div class="ambient-glow-backdrop" :style="{ backgroundImage: `url(${mediaUrl})` }"></div>
      </div>

      <!-- Close Button -->
      <button class="lightbox-close-btn" @click="closeLightbox" :title="lang.t('close')">×</button>

      <!-- Left Navigation Arrow -->
      <button v-if="hasPrev" class="lightbox-nav-btn left" @click="prevPost" title="Previous (←)">‹</button>

      <!-- Center Media Container -->
      <div class="lightbox-media-container" 
           @touchstart="onTouchStart" 
           @touchmove="onTouchMove" 
           @touchend="onTouchEnd"
           :style="{ transform: swipeDiff ? `translateX(${swipeDiff}px)` : '', transition: swiping ? 'none' : 'transform 0.3s ease-out' }">
        
        <!-- Video Player -->
        <video v-if="isVideo" 
               :key="mediaUrl" 
               :src="mediaUrl" 
               controls 
               loop 
               autoplay 
               muted 
               class="lightbox-media video"></video>
               
        <!-- Standard Image -->
        <img v-else 
             :key="mediaUrl" 
             :src="mediaUrl" 
             :alt="'Post ' + activePost.id" 
             class="lightbox-media image" 
             @click="toggleZoom"
             :class="{ zoomed: isZoomed }" />
      </div>

      <!-- Right Navigation Arrow -->
      <button v-if="hasNext" class="lightbox-nav-btn right" @click="nextPost" title="Next (→)">›</button>

      <!-- Dynamic Header Info (Glassmorphic) -->
      <div class="lightbox-header">
        <div class="lightbox-header-left">
          <span class="lightbox-site-badge" :class="activePost.source_site">{{ activePost.source_site }}</span>
          <span class="lightbox-id">#{{ activePost.id }}</span>
          <span class="lightbox-rating" :class="ratingClass">{{ ratingLabel }}</span>
        </div>
        <div class="lightbox-header-right">
          <span v-if="activePost.score !== undefined" class="lightbox-score">★ {{ activePost.score }}</span>
          <span class="lightbox-resolution">{{ activePost.width }}x{{ activePost.height }}</span>
        </div>
      </div>

      <!-- Dynamic Footer Controls (Glassmorphic) -->
      <div class="lightbox-footer">
        <div class="lightbox-tags-row">
          <span v-for="tag in activePost.tags.slice(0, 10)" 
                :key="tag" 
                class="lightbox-tag-chip" 
                @click="searchTag(tag)">
            {{ tag.replace(/_/g, ' ') }}
          </span>
          <span v-if="activePost.tags.length > 10" class="lightbox-tag-more">+{{ activePost.tags.length - 10 }} more</span>
        </div>
        
        <div class="lightbox-actions">
          <button class="btn btn-glass" :class="{ 'btn-fav-active': isFav }" @click="toggleFav">
            {{ isFav ? '❤️ ' + lang.t('nav_favorites') : '🤍 ' + lang.t('nav_favorites') }}
          </button>
          <button class="btn btn-glass" :class="{ 'btn-dislike-active': isDisliked }" @click="toggleDislike">
            👎
          </button>
          <button class="btn btn-glass" @click="downloadFile">
            ⬇️ {{ lang.t('download') || 'Download' }}
          </button>
          <button class="btn btn-glass" @click="openOriginal">
            🔗 {{ lang.t('original') }}
          </button>
        </div>
      </div>

    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiAddFavorite, apiCheckFavorite, apiRemoveFavorite } from '../api'
import { RATING_MAP, RATING_LABELS } from '../types'
import type { Post, RatingClass } from '../types'

const props = defineProps<{
  post: Post
  posts: Post[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

// Keep internal state of the active index in the array of posts
const activeIndex = ref(props.posts.findIndex(p => String(p.id) === String(props.post.id) && p.source_site === props.post.source_site))
if (activeIndex.value === -1) activeIndex.value = 0

const activePost = computed<Post>(() => props.posts[activeIndex.value] || props.post)

const mediaUrl = computed(() => {
  const p = activePost.value
  return p.sample_url || p.file_url || p.preview_url || ''
})

const isVideo = computed(() =>
  ['webm', 'mp4', 'm4v', 'mov', 'mkv'].includes((activePost.value.file_ext || '').toLowerCase())
)

const ratingClass = computed<RatingClass>(() => RATING_MAP[(activePost.value.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')

// Sibling state
const hasPrev = computed(() => activeIndex.value > 0)
const hasNext = computed(() => activeIndex.value < props.posts.length - 1)

function prevPost() {
  if (hasPrev.value) {
    activeIndex.value--
    isZoomed.value = false
    checkFavoriteState()
  }
}

function nextPost() {
  if (hasNext.value) {
    activeIndex.value++
    isZoomed.value = false
    checkFavoriteState()
  }
}

function closeLightbox() {
  emit('close')
}

// Zoom functionality for images
const isZoomed = ref(false)
function toggleZoom() {
  isZoomed.value = !isZoomed.value
}

// Favorite state handling
const isFav = ref(false)
const isDisliked = ref(activePost.value.is_dislike || false)

async function checkFavoriteState() {
  if (!auth.isAuthenticated) return
  try {
    const res = await apiCheckFavorite(activePost.value.source_site, String(activePost.value.id))
    isFav.value = res.is_favorite
    isDisliked.value = res.is_dislike ?? false
  } catch {
    isFav.value = false
  }
}

async function toggleFav() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }
  try {
    if (isFav.value) {
      const check = await apiCheckFavorite(activePost.value.source_site, String(activePost.value.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
      isFav.value = false
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      await apiAddFavorite(activePost.value)
      isFav.value = true
      isDisliked.value = false
      toast.show(lang.t('added_fav'), 'success')
    }
  } catch (e) {
    toast.show((e as Error).message, 'error')
  }
}

async function toggleDislike() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }
  try {
    if (isDisliked.value) {
      const check = await apiCheckFavorite(activePost.value.source_site, String(activePost.value.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
      isDisliked.value = false
      toast.show(lang.t('removed_fav') || 'Removed', 'info')
    } else {
      await apiAddFavorite(activePost.value, true)
      isDisliked.value = true
      isFav.value = false
      toast.show(lang.t('disliked') || 'Post Disliked', 'info')
    }
  } catch (e) {
    toast.show((e as Error).message, 'error')
  }
}

// File downloader
async function downloadFile() {
  const url = activePost.value.file_url || activePost.value.sample_url || activePost.value.preview_url
  if (!url) return
  
  toast.show(lang.t('downloading') || 'Downloading...', 'info')
  try {
    const response = await fetch(url)
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    
    const a = document.createElement('a')
    a.href = blobUrl
    
    const ext = url.split('.').pop()?.split('?')[0] || 'jpg'
    a.download = `booruhub_${activePost.value.source_site}_${activePost.value.id}.${ext}`
    
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
    toast.show(lang.t('download_success') || 'Download completed!', 'success')
  } catch (e) {
    window.open(url, '_blank')
  }
}

function openOriginal() {
  window.open(mediaUrl.value, '_blank')
}

function searchTag(tag: string) {
  closeLightbox()
  router.push({ name: 'feed', query: { tags: tag } })
}

// Keyboard shortcuts support
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft') {
    prevPost()
  } else if (e.key === 'ArrowRight') {
    nextPost()
  } else if (e.key === 'Escape') {
    closeLightbox()
  } else if (e.key.toLowerCase() === 'l') {
    toggleFav()
  } else if (e.key.toLowerCase() === 'd') {
    downloadFile()
  }
}

// Swipe gestures for touch devices
const swipeDiff = ref(0)
const swiping = ref(false)
let touchStartX = 0
let touchStartY = 0

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
  if (!swiping.value) return
  swiping.value = false
  if (Math.abs(swipeDiff.value) > 80) {
    if (swipeDiff.value > 0) {
      if (hasPrev.value) prevPost()
      else swipeDiff.value = 0
    } else {
      if (hasNext.value) nextPost()
      else swipeDiff.value = 0
    }
  }
  swipeDiff.value = 0
}

watch(activePost, () => {
  checkFavoriteState()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  document.body.style.overflow = 'hidden' // Lock background scroll
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  document.body.style.overflow = '' // Unlock scroll
})
</script>

<style scoped>
.lightbox-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  width: 100vw; height: 100vh;
  background: rgba(8, 8, 10, 0.88);
  backdrop-filter: blur(16px);
  z-index: 99999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-close-btn {
  position: absolute;
  top: 20px; right: 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 32px;
  width: 48px; height: 48px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 10000;
  line-height: 1;
}
.lightbox-close-btn:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.4);
  transform: scale(1.08);
}

.lightbox-nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 36px;
  width: 60px; height: 60px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 9999;
  user-select: none;
}
.lightbox-nav-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: var(--accent);
  box-shadow: 0 0 15px rgba(124, 58, 237, 0.35);
  transform: translateY(-50%) scale(1.06);
}
.lightbox-nav-btn.left { left: 32px; }
.lightbox-nav-btn.right { right: 32px; }

.lightbox-media-container {
  max-width: 80vw;
  max-height: 75vh;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  will-change: transform;
}

.lightbox-media {
  max-width: 100%;
  max-height: 75vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.6);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.lightbox-media.image {
  cursor: zoom-in;
}
.lightbox-media.image.zoomed {
  transform: scale(1.35);
  cursor: zoom-out;
  z-index: 1000;
}

/* Glassmorphic panels */
.lightbox-header {
  position: absolute;
  top: 20px; left: 24px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 10px 18px;
  border-radius: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  color: #fff;
  z-index: 999;
  font-size: 13px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
}
.lightbox-header-left, .lightbox-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lightbox-site-badge {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
}
.lightbox-site-badge.danbooru { background: var(--danbooru); color: #fff; }
.lightbox-site-badge.e621 { background: var(--e621); color: #fff; }
.lightbox-site-badge.rule34 { background: var(--rule34); color: #222; }

.lightbox-rating {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}
.lightbox-rating.safe { background: rgba(52, 211, 153, 0.15); color: #6ee7b7; border: 1px solid rgba(52, 211, 153, 0.3); }
.lightbox-rating.questionable { background: rgba(251, 146, 60, 0.15); color: #fdba74; border: 1px solid rgba(251, 146, 60, 0.3); }
.lightbox-rating.explicit { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
.lightbox-rating.unknown { background: rgba(156, 163, 175, 0.15); color: #d1d5db; border: 1px solid rgba(156, 163, 175, 0.3); }

.lightbox-score {
  color: #fbbf24;
  font-weight: 700;
}
.lightbox-resolution {
  color: var(--text-muted);
}

.lightbox-footer {
  position: absolute;
  bottom: 24px; left: 50%;
  transform: translateX(-50%);
  width: 90%;
  max-width: 800px;
  background: rgba(15, 15, 20, 0.55);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 16px 20px;
  border-radius: 16px;
  z-index: 999;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.lightbox-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 32px;
  overflow: hidden;
}
.lightbox-tag-chip {
  font-size: 11px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
  padding: 3px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.lightbox-tag-chip:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.lightbox-tag-more {
  font-size: 11px;
  color: var(--text-muted);
  padding: 3px 4px;
}

.lightbox-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}

.btn-glass {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
  transition: all 0.2s ease;
  font-size: 12px;
  font-weight: 600;
}
.btn-glass:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.2);
}

.btn-fav-active {
  background: rgba(239, 68, 68, 0.2) !important;
  border-color: rgba(239, 68, 68, 0.4) !important;
  color: #ef4444 !important;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
}

.btn-dislike-active {
  background: rgba(249, 115, 22, 0.2) !important;
  border-color: rgba(249, 115, 22, 0.4) !important;
  color: #f97316 !important;
}

/* Animations */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Mobile optimizations */
@media (max-width: 768px) {
  .lightbox-nav-btn {
    display: none; /* Rely on swipes on mobile */
  }
  .lightbox-media-container {
    max-width: 95vw;
  }
  .lightbox-header {
    top: 12px; left: 12px;
    padding: 6px 12px;
    font-size: 11px;
    gap: 12px;
  }
  .lightbox-close-btn {
    top: 10px; right: 12px;
    width: 38px; height: 38px;
    font-size: 24px;
  }
  .lightbox-footer {
    bottom: 12px;
    padding: 10px 12px;
  }
  .lightbox-tags-row {
    display: none; /* Hide tags inside footer on mobile to save space */
  }
  .lightbox-actions .btn {
    padding: 6px 10px;
    font-size: 11px;
  }
}
</style>
