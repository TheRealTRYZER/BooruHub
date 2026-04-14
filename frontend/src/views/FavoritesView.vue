<template>
  <div>
    <div v-if="!auth.isAuthenticated" class="empty-state">
      <div class="empty-state-icon">🔒</div>
      <div class="empty-state-title">{{ lang.t('login') }}</div>
      <div class="empty-state-text">{{ lang.t('login_to_fav') }}</div>
      <button class="btn btn-primary" @click="$router.push('/login')" style="margin-top:16px;">{{ lang.t('login') }}</button>
    </div>
    <template v-else>
      <div class="page-header">
        <h1 class="page-title">{{ showDislikes ? '💔' : '❤️' }} {{ showDislikes ? (lang.t('dislikes_title') || 'Dislikes') : lang.t('favorites_title') }}</h1>
        <p class="page-subtitle">{{ showDislikes ? (lang.t('dislikes_subtitle') || 'Hidden from feed') : lang.t('favorites_subtitle') }}</p>
      </div>

      <div class="tabs">
        <button class="tab-btn" :class="{active: !showDislikes}" @click="switchTab(false)">👍 {{ lang.t('likes_tab') || 'Likes' }}</button>
        <button class="tab-btn" :class="{active: showDislikes}" @click="switchTab(true)">👎 {{ lang.t('dislikes_tab') || 'Dislikes' }}</button>
      </div>

      <PostGrid :posts="posts" :skeletonCount="loading ? 15 : 0" />

      <div v-if="!loading && posts.length === 0" class="empty-state">
        <div class="empty-state-icon">💫</div>
        <div class="empty-state-title">{{ lang.t('empty_list') || 'Empty' }}</div>
      </div>

      <button v-if="hasMore" class="btn btn-secondary" @click="loadMore" style="display:block; margin:24px auto;">
        {{ loading ? '...' : lang.t('search_btn') }}
      </button>
    </template>
  </div>
</template>

<style scoped>
.tabs {
  display: flex; gap: 12px; margin-bottom: 24px;
}
.tab-btn {
  padding: 8px 16px; background: rgba(255,255,255,0.05); border-radius: 20px;
  color: var(--text-muted); font-weight: 600; font-size: 14px; transition: all 0.2s;
}
.tab-btn.active {
  background: var(--bg-card); color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
}
</style>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { apiGetFavorites } from '../api'
import PostGrid from '../components/PostGrid.vue'
import type { Post } from '../types'

const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const posts = ref<Post[]>([])
const page = ref(1)
const loading = ref(false)
const hasMore = ref(false)
const showDislikes = ref(false)

function switchTab(isDislike: boolean) {
  if (showDislikes.value === isDislike) return
  showDislikes.value = isDislike
  posts.value = []
  page.value = 1
  hasMore.value = false
  loadMore()
}

async function loadMore() {
  if (loading.value) return
  loading.value = true

  try {
    const data = await apiGetFavorites(page.value, 40, showDislikes.value)
    const favs = data.favorites || []

    const mapped: Post[] = favs.map(fav => ({
      id: fav.post_id,
      source_site: fav.source_site,
      preview_url: fav.preview_url,
      sample_url: fav.sample_url,
      file_url: fav.file_url,
      tags: fav.tags || [],
      rating: fav.rating,
      score: fav.score,
      width: null,
      height: null,
      file_ext: null,
      md5: null,
      created_at: null,
      is_dislike: showDislikes.value,
    }))

    posts.value.push(...mapped)
    page.value++
    hasMore.value = favs.length >= 40
  } catch (e: any) {
    toast.show(lang.t('error_load_favorites') + ': ' + (e.message || e), 'error')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (auth.isAuthenticated) {
    loadMore()
  }
})
</script>
