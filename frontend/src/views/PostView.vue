<template>
  <div v-if="!post" class="empty-state">
    <div class="empty-state-icon">❌</div>
    <div class="empty-state-title">{{ lang.t('post_not_found') }}</div>
    <button class="btn btn-primary" @click="$router.push('/')">{{ lang.t('back_to_feed') }}</button>
  </div>
  <div v-else class="post-detail">
    <div class="post-detail-image">
      <video v-if="isVideo" :src="mediaUrl" controls loop autoplay muted style="width:100%;max-height:85vh;"></video>
      <img v-else :src="mediaUrl" :alt="'Post ' + post.id" @click="openOriginal" style="cursor:zoom-in;">
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
          <span class="post-detail-info-value">
            <span class="post-card-badge" :class="post.source_site">{{ post.source_site }}</span>
          </span>
        </div>
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('post_id') }}</span>
          <span class="post-detail-info-value">{{ post.id }}</span>
        </div>
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('rating') }}</span>
          <span class="post-detail-info-value">
            <span class="post-card-rating" :class="ratingClass">{{ ratingLabel }}</span>
          </span>
        </div>
        <div class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('score') }}</span>
          <span class="post-detail-info-value">★ {{ post.score || 0 }}</span>
        </div>
        <div v-if="post.width" class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('size') }}</span>
          <span class="post-detail-info-value">{{ post.width }}×{{ post.height }}</span>
        </div>
        <div v-if="post.file_ext" class="post-detail-info-row">
          <span class="post-detail-info-label">{{ lang.t('format') }}</span>
          <span class="post-detail-info-value">{{ post.file_ext.toUpperCase() }}</span>
        </div>
      </div>

      <div class="post-detail-tags" v-if="post.tags && post.tags.length">
        <div class="post-detail-tags-title">{{ lang.t('tags_count') }} ({{ post.tags.length }})</div>
        <div class="post-detail-tags-list">
          <TagChip v-for="tag in post.tags" :key="tag" :tag="tag" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useToastStore } from '../stores/toast.js'
import { useLangStore } from '../stores/lang.js'
import { apiCheckFavorite, apiAddFavorite, apiRemoveFavorite, apiSearch } from '../api.js'
import TagChip from '../components/TagChip.vue'

const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()

const post = ref(null)
const isFav = ref(false)
const favId = ref(null)

const isVideo = computed(() => {
  if (!post.value) return false
  const ext = (post.value.file_ext || '').toLowerCase()
  const url = (post.value.file_url || '').toLowerCase()
  const videoExts = ['webm', 'mp4', 'm4v', 'mov', 'mkv', 'ogv']
  
  return videoExts.includes(ext) || videoExts.some(ve => url.endsWith('.' + ve) || url.includes('.' + ve + '?'))
})

const mediaUrl = computed(() => {
  if (!post.value) return ''
  // For videos, always use the direct file URL, samples might be just images
  if (isVideo.value) return post.value.file_url
  return post.value.sample_url || post.value.file_url
})

const ratingMap = { g: 'safe', general: 'safe', s: 'safe', q: 'questionable', questionable: 'questionable', e: 'explicit', explicit: 'explicit' }
const ratingLabels = { safe: 'S', questionable: 'Q', explicit: 'E', unknown: '?' }

const ratingClass = computed(() => {
  if (!post.value) return 'unknown'
  return ratingMap[(post.value.rating || '').toLowerCase()] || 'unknown'
})
const ratingLabel = computed(() => ratingLabels[ratingClass.value] || '?')

function openOriginal() {
  if (post.value && post.value.file_url) {
    window.open(post.value.file_url, '_blank')
  }
}

async function checkFav() {
  if (!auth.isAuthenticated || !post.value) return
  try {
    const data = await apiCheckFavorite(post.value.source_site, post.value.id)
    isFav.value = data.is_favorite
    favId.value = data.favorite_id
  } catch (e) {}
}

async function toggleFavorite() {
  if (!auth.isAuthenticated) {
    toast.show(lang.t('login_to_fav'), 'error')
    return
  }
  try {
    if (isFav.value && favId.value) {
      await apiRemoveFavorite(favId.value)
      isFav.value = false
      favId.value = null
      toast.show(lang.t('removed_fav'), 'info')
    } else {
      await apiAddFavorite(post.value)
      isFav.value = true
      toast.show(lang.t('added_fav'), 'success')
      await checkFav()
    }
  } catch (e) {
    toast.show(e.message, 'error')
  }
}

onMounted(async () => {
  const id = route.query.id
  const site = route.query.site
  if (!id || !site) return
  
  try {
    const data = await apiSearch(`id:${id}`, site, 1, 1)
    if (data.posts && data.posts.length > 0) {
      post.value = data.posts[0]
      await checkFav()
    }
  } catch(e) {
    toast.show(lang.t('error_load_post'), 'error')
  }
})
</script>
