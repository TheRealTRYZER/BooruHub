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
      <button v-if="hasPrev" class="lightbox-nav-btn left" @click="prevPost" title="Previous (← / A)">‹</button>

      <!-- Center Media Container (Perfect Center) -->
      <div class="lightbox-media-container" 
           @click.self="closeLightbox"
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
             :alt="'Post ' + displayedPost.id" 
             class="lightbox-media image" 
             @click="toggleZoom"
             :class="{ zoomed: isZoomed }" />
      </div>

      <!-- Right Column: Glassmorphic Tags Sidebar (Absolutely Positioned Far Right Edge) -->
      <div class="lightbox-sidebar">
        <h3 class="sidebar-title">{{ lang.t('tags_count') || 'Tags' }} ({{ displayedPost.tags?.length || 0 }})</h3>
        <div class="lightbox-tags-list">
          <div v-for="group in groupedTags" :key="group.key" class="lightbox-tag-group">
            <div class="lightbox-tag-group-title" :class="group.key">
              {{ group.title }} ({{ group.tags.length }})
            </div>
            <div class="lightbox-tag-group-chips">
              <span v-for="tag in group.tags" 
                    :key="tag" 
                    class="tag-chip" 
                    :class="group.key"
                    @click="searchTag(tag)">
                {{ tag.replace(/_/g, ' ') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions Panel: Under Media (Absolutely Positioned Bottom Center) -->
      <div class="lightbox-actions-panel">
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

      <!-- Right Navigation Arrow -->
      <button v-if="hasNext" class="lightbox-nav-btn right" @click="nextPost" title="Next (→ / D)">›</button>

      <!-- Dynamic Header Info (Glassmorphic) -->
      <div class="lightbox-header">
        <div class="lightbox-header-left">
          <span v-for="site in allSites" 
                :key="site" 
                class="lightbox-site-badge" 
                :class="[site, { 'interactive-badge': allSites.length > 1, 'active-site': allSites.length > 1 && activeSite === site }]"
                :title="allSites.length > 1 ? 'Switch to ' + site + ' version' : ''"
                @click="allSites.length > 1 ? switchActiveSite(site) : null">
            {{ site === activePost.source_site ? site : '+ ' + site }}
          </span>
          <span class="lightbox-id">#{{ displayedPost.id }}</span>
          <span class="lightbox-rating" :class="ratingClass">{{ ratingLabel }}</span>
        </div>
        <div class="lightbox-header-right">
          <span v-if="displayedPost.score !== undefined" class="lightbox-score">★ {{ displayedPost.score }}</span>
          <span class="lightbox-resolution">{{ displayedPost.width }}x{{ displayedPost.height }}</span>
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
import type { Post, RatingClass, SiteName } from '../types'

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
const activeIndex = ref(props.posts.findIndex(p => 
  (String(p.id) === String(props.post.id) && p.source_site === props.post.source_site) ||
  p.duplicates?.some(d => String(d.id) === String(props.post.id) && d.source_site === props.post.source_site)
))
if (activeIndex.value === -1) activeIndex.value = 0

const activePost = computed<Post>(() => props.posts[activeIndex.value] || props.post)

// Active duplicate/version state
const activeSite = ref<SiteName>(props.post.source_site)

const allSites = computed<SiteName[]>(() => {
  const p = activePost.value
  const list: SiteName[] = [p.source_site]
  if (p.duplicate_sites) {
    for (const site of p.duplicate_sites) {
      if (!list.includes(site)) {
        list.push(site)
      }
    }
  }
  return list
})

const displayedPost = computed<Post>(() => {
  const p = activePost.value
  if (activeSite.value === p.source_site) {
    return p
  }
  const dup = p.duplicates?.find(d => d.source_site === activeSite.value)
  return dup || p
})

function switchActiveSite(site: SiteName) {
  activeSite.value = site
  checkFavoriteState()
}

const isVideo = computed(() => {
  const ext = (displayedPost.value.file_ext || '').toLowerCase()
  const url = (displayedPost.value.file_url || '').toLowerCase()
  const videoExts = ['webm', 'mp4', 'm4v', 'mov', 'mkv', 'ogv']
  return videoExts.includes(ext) || videoExts.some(ve => url.endsWith('.' + ve) || url.includes('.' + ve + '?'))
})

const mediaUrl = computed(() => {
  const p = displayedPost.value
  if (isVideo.value) return p.file_url || ''
  return p.sample_url || p.file_url || p.preview_url || ''
})

// Group post tags dynamically by category
const groupedTags = computed(() => {
  const post = displayedPost.value
  if (!post || !post.tags) return []
  
  const categoriesOrder = ['artist', 'character', 'copyright', 'species', 'general', 'metadata', 'lore', 'invalid']
  const groups: Record<string, string[]> = {}
  for (const cat of categoriesOrder) {
    groups[cat] = []
  }
  
  const uncategorizedKey = 'general'
  
  for (const tag of post.tags) {
    const cat = post.tags_metadata?.[tag] || uncategorizedKey
    if (!groups[cat]) {
      groups[cat] = []
    }
    groups[cat].push(tag)
  }
  
  const categoryTitles: Record<string, string> = {
    artist: '👤 Artists',
    character: '🎭 Characters',
    copyright: '📚 Copyrights',
    species: '🐾 Species',
    general: '🏷️ General Tags',
    metadata: '⚙️ Metadata',
    lore: '📜 Lore',
    invalid: '❌ Invalid'
  }
  
  return categoriesOrder
    .map(cat => ({
      key: cat,
      title: categoryTitles[cat] || cat,
      tags: groups[cat] || []
    }))
    .filter(g => g.tags.length > 0)
})

const ratingClass = computed<RatingClass>(() => RATING_MAP[(displayedPost.value.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')

// Sibling state
const hasPrev = computed(() => activeIndex.value > 0)
const hasNext = computed(() => activeIndex.value < props.posts.length - 1)

function prevPost() {
  if (hasPrev.value) {
    activeIndex.value--
  }
}

function nextPost() {
  if (hasNext.value) {
    activeIndex.value++
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
const isDisliked = ref(displayedPost.value.is_dislike || false)

async function checkFavoriteState() {
  if (!auth.isAuthenticated) {
    isFav.value = false
    isDisliked.value = displayedPost.value.is_dislike || false
    return
  }
  try {
    const res = await apiCheckFavorite(displayedPost.value.source_site, String(displayedPost.value.id))
    isFav.value = res.is_favorite
    isDisliked.value = res.is_dislike ?? false
  } catch {
    isFav.value = false
    isDisliked.value = displayedPost.value.is_dislike || false
  }
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
      const check = await apiCheckFavorite(displayedPost.value.source_site, String(displayedPost.value.id))
      if (check.favorite_id) await apiRemoveFavorite(check.favorite_id)
      isDisliked.value = false
      toast.show(lang.t('removed_fav') || 'Removed', 'info')
    } else {
      await apiAddFavorite(displayedPost.value, true)
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
  const url = displayedPost.value.file_url || displayedPost.value.sample_url || displayedPost.value.preview_url
  if (!url) return
  
  toast.show(lang.t('downloading') || 'Downloading...', 'info')
  try {
    const response = await fetch(url)
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    
    const a = document.createElement('a')
    a.href = blobUrl
    
    const ext = url.split('.').pop()?.split('?')[0] || 'jpg'
    a.download = `booruhub_${displayedPost.value.source_site}_${displayedPost.value.id}.${ext}`
    
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
  const key = e.key.toLowerCase()
  if (e.key === 'ArrowLeft' || key === 'a') {
    prevPost()
  } else if (e.key === 'ArrowRight' || key === 'd') {
    nextPost()
  } else if (e.key === 'Escape') {
    closeLightbox()
  } else if (key === 'l') {
    toggleFav()
  } else if (key === 's') {
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

watch(activePost, (newPost) => {
  activeSite.value = newPost.source_site
  isZoomed.value = false
})

watch(displayedPost, () => {
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
.lightbox-nav-btn.right { right: 340px; }

/* Center Media Container (Perfect Center Alignment) */
.lightbox-media-container {
  max-width: 60vw;
  max-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  will-change: transform;
}

.lightbox-media {
  max-width: 100%;
  max-height: 70vh;
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

/* Actions Panel: absolutely positioned at the bottom center */
.lightbox-actions-panel {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  justify-content: center;
  gap: 10px;
  background: rgba(15, 15, 20, 0.55);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px 20px;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 999;
}

/* Glassmorphic Tags Sidebar: absolutely positioned far right */
.lightbox-sidebar {
  position: absolute;
  right: 24px;
  top: 80px;
  bottom: 24px;
  width: 300px;
  background: rgba(15, 15, 20, 0.55);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 999;
}

.sidebar-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 8px;
}

.lightbox-tags-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  flex: 1;
  padding-right: 4px;
}
.lightbox-tags-list::-webkit-scrollbar {
  width: 4px;
}
.lightbox-tags-list::-webkit-scrollbar-track {
  background: transparent;
}
.lightbox-tags-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}
.lightbox-tags-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.lightbox-tag-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.lightbox-tag-group-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 2px;
  opacity: 0.85;
  user-select: none;
}
.lightbox-tag-group-title.artist { color: #f43f5e; }
.lightbox-tag-group-title.character { color: #34d399; }
.lightbox-tag-group-title.copyright { color: #a78bfa; }
.lightbox-tag-group-title.species { color: #fb923c; }
.lightbox-tag-group-title.general { color: #38bdf8; }
.lightbox-tag-group-title.metadata { color: #fbbf24; }
.lightbox-tag-group-title.lore, .lightbox-tag-group-title.invalid { color: #9ca3af; }

.lightbox-tag-group-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lightbox-sidebar .tag-chip {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 8px;
  display: inline-block;
  line-height: 1.2;
}

.lightbox-tag-more {
  font-size: 11px;
  color: var(--text-muted);
  padding: 3px 4px;
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

.lightbox-site-badge.interactive-badge {
  cursor: pointer;
  transition: all 0.15s ease;
}
.lightbox-site-badge.interactive-badge:hover {
  transform: scale(1.08);
  filter: brightness(1.2);
}
.lightbox-site-badge.interactive-badge.active-site {
  box-shadow: 0 0 0 2px rgba(15, 15, 20, 0.6), 0 0 0 3px var(--accent);
  transform: scale(1.1);
  font-weight: 800;
  z-index: 2;
}

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
  .lightbox-overlay {
    flex-direction: column;
    justify-content: flex-start;
    padding-top: 75px;
    overflow-y: auto;
  }
  .lightbox-nav-btn {
    display: none; /* Rely on swipes on mobile */
  }
  .lightbox-media-container {
    max-width: 95vw;
    max-height: 50vh;
    margin-bottom: 20px;
  }
  .lightbox-media {
    max-height: 50vh;
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
  .lightbox-actions-panel {
    position: static;
    transform: none;
    width: 95vw;
    padding: 8px 12px;
    margin-top: 16px;
  }
  .lightbox-actions-panel .btn {
    padding: 6px 10px;
    font-size: 11px;
  }
  .lightbox-sidebar {
    position: static;
    width: 95vw;
    height: 140px;
    padding: 12px;
    margin-top: 16px;
    margin-bottom: 24px;
  }
  .sidebar-title {
    font-size: 13px;
    padding-bottom: 4px;
  }
  .lightbox-tags-list {
    max-height: 90px;
  }
}
</style>
