<template>
  <Transition name="fade">
    <div class="lightbox-overlay" role="dialog" aria-modal="true" aria-label="Image Details" @click.self="closeLightbox">
      
      <!-- Dynamic Ambilight Theatre Backdrop -->
      <div class="ambient-glow-container">
        <div class="ambient-glow-backdrop" :style="{ backgroundImage: backdropUrl ? 'url(' + escapeCssString(backdropUrl) + ')' : 'none' }"></div>
      </div>

      <!-- Close Button -->
      <button ref="closeBtnRef" class="lightbox-close-btn" @click="closeLightbox" :title="lang.t('close')">×</button>

      <!-- Left Navigation Arrow -->
      <button v-if="hasPrev" 
              class="lightbox-nav-btn left" 
              :class="{ 'shifted-right': relationshipPosts.length > 1 }"
              @click="prevPost" 
              :title="lang.t('prev_title')">‹</button>

      <!-- Scrollable content (relationships + media + sidebar). On desktop this wrapper is transparent (display: contents). -->
      <div class="lightbox-scroll-content">
        <!-- Parent/Child Relationships Panel -->
        <LightboxRelationships 
          :displayed-post="displayedPost"
          :relationship-posts="relationshipPosts"
          @navigate="navigateToPost"
        />

        <!-- Center Media Container (Perfect Center) -->
        <div class="lightbox-content-wrapper" @click.self="closeLightbox">
          <div class="lightbox-media-container" 
               :class="{ 'lightbox-media-scrollable': !isVideo && isLong }"
               @click.self="closeLightbox">
            
            <!-- Video Player -->
            <video v-if="isVideo" 
                   ref="zoomImageRef"
                   :key="mediaUrl" 
                   :src="mediaUrl" 
                   controls 
                   loop 
                   autoplay 
                   muted 
                   class="lightbox-media video"
                   :style="{ transform: `translate(${translateX}px, ${translateY}px) scale(${scale})`, transition: (isPinching || isPanning) ? 'none' : 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)', touchAction: scale > 1 ? 'none' : 'auto' }"
                   :class="{ zoomed: scale > 1 }"></video>
                   
            <!-- Standard Image -->
            <img v-else 
                 ref="zoomImageRef"
                 :key="mediaUrl" 
                 :src="mediaUrl" 
                 :alt="altText" 
                 class="lightbox-media image" 
                 :class="{ 'lightbox-media-scrollable-img': isLong, zoomed: scale > 1 }"
                 @click="toggleZoom"
                 :style="{ transform: `translate(${translateX}px, ${translateY}px) scale(${scale})`, transition: (isPinching || isPanning) ? 'none' : 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)', cursor: scale > 1 ? 'zoom-out' : 'zoom-in', touchAction: scale > 1 ? 'none' : 'auto' }" />
          </div>
        </div>

        <!-- Right Column: Glassmorphic Tags Sidebar -->
        <LightboxSidebar 
          :displayed-post="displayedPost"
          @search-tag="searchTag"
        />
      </div>

      <!-- Actions Panel: Under Media -->
      <LightboxActions 
        :is-fav="isFav"
        :is-disliked="isDisliked"
        @toggle-fav="toggleFav"
        @toggle-dislike="toggleDislike"
        @download="downloadFile"
        @open-original="openOriginal"
      />

      <!-- Right Navigation Arrow -->
      <button v-if="hasNext" class="lightbox-nav-btn right" @click="nextPost" :title="lang.t('next_title')">›</button>

      <!-- Dynamic Header Info (Glassmorphic) -->
      <LightboxHeader 
        :displayed-post="displayedPost"
        :active-post="activePost"
        :all-sites="allSites"
        :active-site="activeSite"
        @switch-site="switchActiveSite"
      />

    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiAddFavorite, apiCheckFavorite, apiRemoveFavorite, apiSearch } from '../api'
import { sanitizeUrl, escapeCssString } from '../utils/security'
import type { Post, SiteName } from '../types'
import { usePinchZoom } from '../composables/usePinchZoom'

import LightboxHeader from './LightboxHeader.vue'
import LightboxSidebar from './LightboxSidebar.vue'
import LightboxActions from './LightboxActions.vue'
import LightboxRelationships from './LightboxRelationships.vue'

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

const localPosts = ref<Post[]>([...props.posts])

watch(() => props.posts, (newVal) => {
  localPosts.value = [...newVal]
})

// Keep internal state of the active index in the array of posts
const activeIndex = ref(localPosts.value.findIndex(p => 
  (String(p.id) === String(props.post.id) && p.source_site === props.post.source_site) ||
  p.duplicates?.some(d => String(d.id) === String(props.post.id) && d.source_site === props.post.source_site)
))
if (activeIndex.value === -1) activeIndex.value = 0

const activePost = computed<Post>(() => localPosts.value[activeIndex.value] || props.post)

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

// Sibling/Parent relationships state
const relationshipPosts = ref<Post[]>([])
const loadingRelationships = ref(false)

async function loadRelationships() {
  const post = displayedPost.value
  if (!post) {
    relationshipPosts.value = []
    return
  }

  const pId = post.parent_id
  const hasChildren = post.has_children

  if (!pId && !hasChildren) {
    relationshipPosts.value = []
    return
  }

  loadingRelationships.value = true
  try {
    const postsMap = new Map<string, Post>()
    const addPost = (p: Post) => {
      const key = `${p.source_site}:${p.id}`
      postsMap.set(key, p)
    }

    addPost(post)

    if (pId) {
      // 1. Fetch parent
      try {
        const parentRes = await apiSearch(`id:${pId}`, post.source_site, 1, 1, true)
        if (parentRes.posts && parentRes.posts.length > 0) {
          const firstParent = parentRes.posts[0]
          if (firstParent) {
            addPost(firstParent)
          }
        }
      } catch (e) {
        console.error("Error fetching parent post:", e)
      }

      // 2. Fetch siblings
      try {
        const childrenRes = await apiSearch(`parent:${pId}`, post.source_site, 1, 100, true)
        if (childrenRes.posts) {
          childrenRes.posts.forEach(addPost)
        }
      } catch (e) {
        console.error("Error fetching sibling posts:", e)
      }
    } else if (hasChildren) {
      // Fetch children
      try {
        const childrenRes = await apiSearch(`parent:${post.id}`, post.source_site, 1, 100, true)
        if (childrenRes.posts) {
          childrenRes.posts.forEach(addPost)
        }
      } catch (e) {
        console.error("Error fetching children posts:", e)
      }
    }

    const allPosts = Array.from(postsMap.values())
    const targetParentId = pId || post.id
    
    // Sort: Parent always comes first, others sorted by numeric ID
    allPosts.sort((a, b) => {
      const aIsParent = String(a.id) === String(targetParentId)
      const bIsParent = String(b.id) === String(targetParentId)
      if (aIsParent) return -1
      if (bIsParent) return 1
      return Number(a.id) - Number(b.id)
    })

    relationshipPosts.value = allPosts
  } catch (err) {
    console.error("Error loading relationships:", err)
  } finally {
    loadingRelationships.value = false
  }
}

function navigateToPost(p: Post) {
  if (String(p.id) === String(displayedPost.value?.id)) return
  
  // Try to find in localPosts first
  const idx = localPosts.value.findIndex(post => 
    (String(post.id) === String(p.id) && post.source_site === p.source_site) ||
    post.duplicates?.some(d => String(d.id) === String(p.id) && d.source_site === p.source_site)
  )
  
  if (idx !== -1) {
    activeIndex.value = idx
    const foundPost = localPosts.value[idx]
    if (foundPost) {
      activeSite.value = p.source_site
    }
  } else {
    // Insert the new post into localPosts right after the current activeIndex, and go there
    localPosts.value.splice(activeIndex.value + 1, 0, p)
    activeIndex.value++
    activeSite.value = p.source_site
  }
}

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

// Very tall posts (height/width >= 21/9) are shown at natural size in the lightbox
// inside a scrollable frame so they can be read (and zoomed) without shrinking.
const isLong = computed(() => {
  const p = displayedPost.value
  if (p && p.width && p.height && p.width > 0) {
    return p.height / p.width >= 21 / 9
  }
  return false
})

const mediaUrl = computed(() => {
  const p = displayedPost.value
  let url = ''
  if (isVideo.value) url = p.file_url || ''
  else url = p.sample_url || p.file_url || p.preview_url || ''
  return sanitizeUrl(url)
})

const backdropUrl = computed(() => {
  const p = displayedPost.value
  const videoExtensions = ['mp4', 'webm', 'm4v', 'mov', 'mkv', 'swf', 'ogv']
  const isVideoExt = (url: string) => {
    if (!url) return false
    const cleanUrl = (url.split('?')[0] ?? '').toLowerCase()
    return videoExtensions.some(ext => cleanUrl.endsWith('.' + ext))
  }
  
  let url = ''
  if (p.sample_url && !isVideoExt(p.sample_url)) {
    url = p.sample_url
  } else if (p.preview_url && !isVideoExt(p.preview_url)) {
    url = p.preview_url
  } else if (p.file_url && !isVideoExt(p.file_url)) {
    url = p.file_url
  } else {
    const fallback = p.preview_url || p.sample_url || ''
    url = isVideoExt(fallback) ? '' : fallback
  }
  return sanitizeUrl(url)
})

const altText = computed(() => {
  const firstTag = displayedPost.value.tags?.[0]
  const rating = displayedPost.value.rating ? `[Rating: ${displayedPost.value.rating.toUpperCase()}]` : ''
  return `Post ${displayedPost.value.id} ${firstTag ? '- ' + firstTag.replace(/_/g, ' ') : ''} ${rating}`.trim()
})

// Sibling state
const hasPrev = computed(() => activeIndex.value > 0)
const hasNext = computed(() => activeIndex.value < localPosts.value.length - 1)

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
const {
  scale,
  translateX,
  translateY,
  isPinching,
  isPanning,
  onTouchStart: onImageTouchStart,
  onTouchMove: onImageTouchMove,
  onTouchEnd: onImageTouchEnd,
  reset: resetZoom
} = usePinchZoom()

const zoomImageRef = ref<HTMLElement | null>(null)

watch(zoomImageRef, (newEl, oldEl) => {
  if (oldEl) {
    oldEl.removeEventListener('touchstart', onImageTouchStart)
    oldEl.removeEventListener('touchmove', onImageTouchMove)
    oldEl.removeEventListener('touchend', onImageTouchEnd)
  }
  if (newEl) {
    newEl.addEventListener('touchstart', onImageTouchStart, { passive: false })
    newEl.addEventListener('touchmove', onImageTouchMove, { passive: false })
    newEl.addEventListener('touchend', onImageTouchEnd, { passive: false })
  }
})

function toggleZoom() {
  if (scale.value > 1) {
    resetZoom()
  } else {
    scale.value = 2.5
    translateX.value = 0
    translateY.value = 0
  }
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
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      await apiAddFavorite(displayedPost.value, true)
      isDisliked.value = true
      isFav.value = false
      toast.show(lang.t('disliked'), 'info')
    }
  } catch (e) {
    toast.show((e as Error).message, 'error')
  }
}

// File downloader
async function downloadFile() {
  const rawUrl = displayedPost.value.file_url || displayedPost.value.sample_url || displayedPost.value.preview_url
  const url = sanitizeUrl(rawUrl)
  if (!url) return
  
  toast.show(lang.t('downloading'), 'info')
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
    toast.show(lang.t('download_success'), 'success')
  } catch (e) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

function openOriginal() {
  const url = sanitizeUrl(mediaUrl.value)
  if (url) {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

function searchTag(tag: string) {
  closeLightbox()
  router.push({ name: 'feed', query: { tags: tag } })
}

// Accessibility dialog elements
const closeBtnRef = ref<HTMLElement | null>(null)
let previousActiveElement: HTMLElement | null = null

function handleTabKey(e: KeyboardEvent) {
  const overlay = document.querySelector('.lightbox-overlay')
  if (!overlay) return
  const focusable = Array.from(
    overlay.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex="0"]'
    )
  ).filter(el => {
    return (el as HTMLElement).tabIndex >= 0 && (el as HTMLElement).offsetWidth > 0
  }) as HTMLElement[]

  if (focusable.length === 0) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first || !last) return

  if (e.shiftKey) {
    if (document.activeElement === first) {
      last.focus()
      e.preventDefault()
    }
  } else {
    if (document.activeElement === last) {
      first.focus()
      e.preventDefault()
    }
  }
}

// Keyboard shortcuts support
function handleKeyDown(e: KeyboardEvent) {
  const key = e.key.toLowerCase()
  if (e.key === 'Tab') {
    handleTabKey(e)
  } else if (e.key === 'ArrowLeft' || key === 'a') {
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



watch(activePost, (newPost) => {
  activeSite.value = newPost.source_site
  resetZoom()
})

watch(displayedPost, () => {
  checkFavoriteState()
  loadRelationships()
}, { immediate: true })

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  document.body.style.overflow = 'hidden' // Lock background scroll
  previousActiveElement = document.activeElement as HTMLElement
  setTimeout(() => {
    closeBtnRef.value?.focus()
  }, 50)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  document.body.style.overflow = '' // Unlock scroll
  previousActiveElement?.focus()
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
  z-index: 999;
  user-select: none;
}
.lightbox-nav-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: var(--accent);
  box-shadow: 0 0 15px rgba(124, 58, 237, 0.35);
  transform: translateY(-50%) scale(1.06);
}
.lightbox-nav-btn.left { left: 32px; }
.lightbox-nav-btn.left.shifted-right { left: 340px; }
.lightbox-nav-btn.right { right: 340px; }

.lightbox-content-wrapper {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

/* Transparent wrapper on desktop — children participate in overlay's flex layout directly.
   On mobile it becomes the scrollable region between the fixed header and actions bar. */
.lightbox-scroll-content {
  display: contents;
}

.lightbox-media-container {
  max-width: calc(100vw - 690px);
  max-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  will-change: transform;
}

.lightbox-media {
  max-width: 100%;
  max-height: calc(100vh - 200px);
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.6);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.lightbox-media.image {
  cursor: zoom-in;
}

/* Very tall posts (comics) on desktop: shown at natural size inside a scrollable
   frame instead of being shrunk to fit. Zoom (click/pinch) still applies and the
   frame scrolls so the whole page can be read. */
.lightbox-media-container.lightbox-media-scrollable {
  max-width: calc(100vw - 690px);
  max-height: calc(100vh - 200px);
  width: auto;
  overflow-x: hidden;
  overflow-y: auto;
  align-items: flex-start;
  justify-content: center;
}
.lightbox-media-container.lightbox-media-scrollable::-webkit-scrollbar { width: 6px; }
.lightbox-media-container.lightbox-media-scrollable::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.18);
  border-radius: 3px;
}
.lightbox-media.lightbox-media-scrollable-img {
  width: 100%;
  height: auto;
  max-height: none;
  object-fit: fill;
  display: block;
}
.lightbox-media.zoomed {
  z-index: 1000;
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
    align-items: center;
    overflow: hidden;
    padding-top: 0;
  }
  .lightbox-nav-btn {
    display: none; /* Rely on swipes on mobile */
  }
  .lightbox-scroll-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    overflow-y: auto;
    overflow-x: hidden;
    width: 100%;
    flex: 1 1 auto;
    min-height: 0;
    padding-top: 64px;   /* leave room for the fixed header */
    padding-bottom: 88px; /* leave room for the fixed actions bar */
    -webkit-overflow-scrolling: touch;
  }
  .lightbox-content-wrapper {
    flex-direction: column;
    gap: 16px;
    width: 100%;
    height: auto;
    flex-shrink: 0;
  }
  .lightbox-media-container {
    max-width: 95vw;
    max-height: none;
    margin-bottom: 0;
  }
  .lightbox-media {
    max-height: none;
  }
  /* On mobile the whole post (media + tags) scrolls via .lightbox-scroll-content,
     so the per-image frame must not impose its own scroll limit. */
  .lightbox-media-container.lightbox-media-scrollable {
    max-width: 95vw;
    max-height: none;
    overflow: visible;
  }
  .lightbox-close-btn {
    top: 10px; right: 12px;
    width: 38px; height: 38px;
    font-size: 24px;
  }
}
</style>
