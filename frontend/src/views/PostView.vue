<template>
  <div v-if="!displayedPost" class="empty-state">
    <div class="empty-state-icon">❌</div>
    <div class="empty-state-title">{{ lang.t('post_not_found') }}</div>
    <button class="btn btn-primary" @click="$router.push('/')">{{ lang.t('back_to_feed') }}</button>
  </div>
  <div v-else class="post-detail" :class="{ 'has-relationships': relationshipPosts.length > 1 }">
    <!-- Dynamic Ambilight Theatre Backdrop -->
    <div class="ambient-glow-container">
      <div class="ambient-glow-backdrop" :style="{ backgroundImage: backdropUrl ? 'url(' + escapeCssString(backdropUrl) + ')' : 'none' }"></div>
    </div>
    
    <!-- Parent/Child Relationships Panel (Left Sidebar) -->
    <div v-if="relationshipPosts.length > 1" class="post-relationship-panel">
      <div class="post-relationship-header">
        <span>
          {{ displayedPost.parent_id ? lang.t('post_has_parent') : lang.t('post_has_children') }}
        </span>
        <span class="post-relationship-toggle" 
              role="button" 
              tabindex="0"
              @click="showRelationshipPanel = !showRelationshipPanel"
              @keydown.enter.prevent="showRelationshipPanel = !showRelationshipPanel"
              @keydown.space.prevent="showRelationshipPanel = !showRelationshipPanel">
          « {{ showRelationshipPanel ? lang.t('hide') : lang.t('show') }}
        </span>
      </div>
      <div v-if="showRelationshipPanel" class="post-relationship-thumbs">
        <img 
          v-for="p in relationshipPosts" 
          :key="p.source_site + ':' + p.id"
          :src="getPostThumbnail(p)"
          class="post-relationship-thumb"
          :class="{ active: String(p.id) === String(displayedPost.id) }"
          :alt="'Thumbnail ' + p.id"
          @click="navigateToPost(p)"
        >
      </div>
    </div>

    <div class="post-detail-image">
      <video v-if="isVideo" :src="mediaUrl" controls loop autoplay muted style="width:100%;max-height:85vh;"></video>
      <img v-else :src="mediaUrl" :alt="altText" @click="openOriginal" style="cursor:zoom-in;">
    </div>
    
    <div class="post-detail-sidebar">
      <div class="post-detail-actions">
        <button class="btn" :class="isFav ? 'btn-danger' : 'btn-primary'" @click="toggleFavorite" style="flex:1;">
          {{ isFav ? '💔 ' + lang.t('remove_from_fav') : '❤️ ' + lang.t('add_to_fav') }}
        </button>
        <button class="btn btn-secondary" @click="openOriginal" style="flex:1;">
          🔗 {{ lang.t('original') }}
        </button>
      </div>
      
      <div class="post-detail-info">
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('source') }}</span>
          <span class="post-detail-info-value" style="display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end;">
            <span v-for="site in allSites" 
                  :key="site" 
                  class="post-card-badge" 
                  :class="[site, { 'interactive-badge': allSites.length > 1, 'active-site': allSites.length > 1 && activeSite === site }]"
                  :title="allSites.length > 1 ? lang.t('switch_version', { site }) : ''"
                  :role="allSites.length > 1 ? 'button' : undefined"
                  :tabindex="allSites.length > 1 ? 0 : undefined"
                  @click="allSites.length > 1 ? switchActiveSite(site) : null"
                  @keydown.enter.stop.prevent="allSites.length > 1 ? switchActiveSite(site) : null"
                  @keydown.space.stop.prevent="allSites.length > 1 ? switchActiveSite(site) : null">
              {{ site }}
            </span>
          </span>
        </div>
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('post_id') }}</span>
          <span class="post-detail-info-value">{{ displayedPost.id }}</span>
        </div>
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('rating') }}</span>
          <span class="post-detail-info-value">
            <span class="post-card-rating" :class="ratingClass" :aria-label="'Rating: ' + ratingLabel">{{ ratingLabel }}</span>
          </span>
        </div>
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('score') }}</span>
          <span class="post-detail-info-value">★ {{ displayedPost.score || 0 }}</span>
        </div>
        <div v-if="displayedPost.width" class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('size') }}</span>
          <span class="post-detail-info-value">{{ displayedPost.width }}×{{ displayedPost.height }}</span>
        </div>
        <div v-if="displayedPost.file_ext" class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('format') }}</span>
          <span class="post-detail-info-value">{{ displayedPost.file_ext.toUpperCase() }}</span>
        </div>
      </div>

      <div class="post-detail-tags" v-if="displayedPost.tags && displayedPost.tags.length">
        <div class="post-detail-tags-title">{{ lang.t('tags_count') }} ({{ displayedPost.tags.length }})</div>
        
        <div v-for="group in groupedTags" :key="group.key" style="margin-bottom: 14px;">
          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; letter-spacing: 0.5px;">
            {{ group.title }} ({{ group.tags.length }})
          </div>
          <div class="post-detail-tags-list" style="margin-bottom: 8px;">
            <TagChip v-for="tag in group.tags" :key="tag" :tag="tag" :class="group.key" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { useFeedStore } from '../stores/feed'
import { apiCheckFavorite, apiAddFavorite, apiRemoveFavorite, apiSearch } from '../api'
import { useEventLogger } from '../composables/useEventLogger'
import TagChip from '../components/TagChip.vue'
import { sanitizeUrl, escapeCssString } from '../utils/security'
import { RATING_MAP, RATING_LABELS } from '../types'
import type { Post, SiteName } from '../types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const { logView, logFavourite } = useEventLogger()

const mainPost = ref<Post | null>(null)
const activeSite = ref<SiteName>('danbooru')
const isFav = ref(false)
const favId = ref<number | null>(null)

// Compute all sites available for version switching
const allSites = computed<SiteName[]>(() => {
  if (!mainPost.value) return []
  const list: SiteName[] = [mainPost.value.source_site]
  if (mainPost.value.duplicate_sites) {
    for (const site of mainPost.value.duplicate_sites) {
      if (!list.includes(site)) {
        list.push(site)
      }
    }
  }
  return list
})

// Compute currently displayed post based on active site version
const displayedPost = computed<Post | null>(() => {
  if (!mainPost.value) return null
  if (activeSite.value === mainPost.value.source_site) {
    return mainPost.value
  }
  const dup = mainPost.value.duplicates?.find(d => d.source_site === activeSite.value)
  return dup || mainPost.value
})

const isVideo = computed(() => {
  if (!displayedPost.value) return false
  const ext = (displayedPost.value.file_ext || '').toLowerCase()
  const url = (displayedPost.value.file_url || '').toLowerCase()
  const videoExts = ['webm', 'mp4', 'm4v', 'mov', 'mkv', 'ogv']
  
  return videoExts.includes(ext) || videoExts.some(ve => url.endsWith('.' + ve) || url.includes('.' + ve + '?'))
})

const mediaUrl = computed(() => {
  if (!displayedPost.value) return ''
  // For videos, always use the direct file URL, samples might be just images
  if (isVideo.value) return sanitizeUrl(displayedPost.value.file_url || '')
  return sanitizeUrl(displayedPost.value.sample_url || displayedPost.value.file_url || '')
})

const backdropUrl = computed(() => {
  const p = displayedPost.value
  if (!p) return ''
  
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
  if (!displayedPost.value) return ''
  const firstTag = displayedPost.value.tags?.[0]
  const rating = displayedPost.value.rating ? `[Rating: ${displayedPost.value.rating.toUpperCase()}]` : ''
  return `Post ${displayedPost.value.id} ${firstTag ? '- ' + firstTag.replace(/_/g, ' ') : ''} ${rating}`.trim()
})

function getPostThumbnail(p: Post) {
  const videoExtensions = ['mp4', 'webm', 'm4v', 'mov', 'mkv', 'swf', 'ogv']
  const isVideoExt = (url: string) => {
    if (!url) return false
    const cleanUrl = (url.split('?')[0] ?? '').toLowerCase()
    return videoExtensions.some(ext => cleanUrl.endsWith('.' + ext))
  }
  
  let url = ''
  if (p.preview_url && !isVideoExt(p.preview_url)) url = p.preview_url
  else if (p.sample_url && !isVideoExt(p.sample_url)) url = p.sample_url
  else if (p.file_url && !isVideoExt(p.file_url)) url = p.file_url
  else {
    const fallback = p.preview_url || p.sample_url || p.file_url || ''
    url = isVideoExt(fallback) ? '' : fallback
  }
  return sanitizeUrl(url)
}

const ratingClass = computed(() => {
  if (!displayedPost.value) return 'unknown'
  return RATING_MAP[(displayedPost.value.rating || '').toLowerCase()] || 'unknown'
})
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')

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

function openOriginal() {
  if (displayedPost.value && displayedPost.value.file_url) {
    const url = sanitizeUrl(displayedPost.value.file_url)
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }
}

async function checkFav() {
  if (!auth.isAuthenticated || !displayedPost.value) return
  try {
    const data = await apiCheckFavorite(displayedPost.value.source_site, displayedPost.value.id)
    isFav.value = data.is_favorite
    favId.value = data.favorite_id
  } catch (e) {}
}

async function toggleFavorite() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }
  if (!displayedPost.value) return
  try {
    if (isFav.value && favId.value) {
      await apiRemoveFavorite(favId.value)
      isFav.value = false
      favId.value = null
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      await apiAddFavorite(displayedPost.value)
      isFav.value = true
      logFavourite(displayedPost.value)
      toast.show(lang.t('added_fav'), 'success')
      await checkFav()
    }
  } catch (e: any) {
    toast.show(e.message || e, 'error')
  }
}

async function switchActiveSite(site: SiteName) {
  activeSite.value = site
  
  // Sync router query with active version to preserve history/sharing URLs
  if (displayedPost.value) {
    router.replace({
      query: {
        ...route.query,
        id: String(displayedPost.value.id),
        site: displayedPost.value.source_site
      }
    })
  }

  await checkFav()
}

// Relationships State & Loader
const relationshipPosts = ref<Post[]>([])
const loadingRelationships = ref(false)
const showRelationshipPanel = ref(true)

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
  router.push({
    query: {
      ...route.query,
      id: String(p.id),
      site: p.source_site
    }
  })
}

async function fetchAndSetPost() {
  const id = route.query.id as string
  const site = route.query.site as SiteName
  if (!id || !site) return
  
  activeSite.value = site

  // 1. Try finding the post in memory (feed.posts) first for instant (0ms) loading
  const feed = useFeedStore()
  let found = feed.posts.find(p => String(p.id) === id && p.source_site === site)
  if (!found) {
    // Check if it's a duplicate of any post in feed.posts
    found = feed.posts.find(p => p.duplicates?.some(d => String(d.id) === id && d.source_site === site))
  }

  if (found) {
    mainPost.value = found
    if (displayedPost.value) {
      logView(displayedPost.value)
    }
    await checkFav()
    await loadRelationships()
    return
  }
  
  // 2. Fall back to API fetch if refreshed or direct link
  try {
    const data = await apiSearch(`id:${id}`, site, 1, 1)
    if (data.posts && data.posts.length > 0) {
      const firstPost = data.posts[0]
      if (firstPost) {
        mainPost.value = firstPost
      }
      if (displayedPost.value) {
        logView(displayedPost.value)
      }
      await checkFav()
      await loadRelationships()
    }
  } catch(e) {
    toast.show(lang.t('error_load_post'), 'error')
  }
}

onMounted(async () => {
  await fetchAndSetPost()
})

// Watch route parameter changes to load posts smoothly without a full page refresh
watch(
  () => [route.query.id, route.query.site],
  async ([newId, newSite]) => {
    if (newId && newSite) {
      await fetchAndSetPost()
    }
  }
)
</script>
