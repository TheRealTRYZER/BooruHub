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
        <h1 class="page-title">❤️ {{ lang.t('favorites_title') }}</h1>
        <p class="page-subtitle">{{ lang.t('favorites_subtitle') }}</p>
      </div>

      <PostGrid :posts="posts" :skeletonCount="loading ? 15 : 0" />

      <div v-if="!loading && posts.length === 0" class="empty-state">
        <div class="empty-state-icon">💫</div>
        <div class="empty-state-title">{{ lang.t('no_favorites') }}</div>
        <div class="empty-state-text">{{ lang.t('add_favorites_hint') }}</div>
      </div>

      <button v-if="hasMore" class="btn btn-secondary" @click="loadMore" style="display:block; margin:24px auto;">
        {{ loading ? '...' : lang.t('search_btn') }}
      </button>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { useToastStore } from '../stores/toast.js'
import { useLangStore } from '../stores/lang.js'
import { apiGetFavorites } from '../api.js'
import PostGrid from '../components/PostGrid.vue'

const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const posts = ref([])
const page = ref(1)
const loading = ref(false)
const hasMore = ref(false)

async function loadMore() {
  if (loading.value) return
  loading.value = true

  try {
    const data = await apiGetFavorites(page.value, 40)
    const favs = data.favorites || []

    const mapped = favs.map(fav => ({
      id: fav.post_id,
      source_site: fav.source_site,
      preview_url: fav.preview_url,
      sample_url: fav.sample_url,
      file_url: fav.file_url,
      tags: fav.tags || [],
      rating: fav.rating,
      score: fav.score,
    }))

    posts.value.push(...mapped)
    page.value++
    hasMore.value = favs.length >= 40
  } catch (e) {
    toast.show(lang.t('error_load_favorites') + ': ' + e.message, 'error')
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
