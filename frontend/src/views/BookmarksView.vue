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
        <h1 class="page-title">🔖 {{ lang.t('bookmarks_title') }}</h1>
        <p class="page-subtitle">{{ lang.t('bookmarks_subtitle') }}</p>
      </div>

      <div v-if="loading" class="loading-spinner"></div>
      
      <div v-if="!loading && bookmarks.length === 0" class="empty-state">
        <div class="empty-state-icon">📑</div>
        <div class="empty-state-title">{{ lang.t('no_bookmarks') }}</div>
        <div class="empty-state-text">{{ lang.t('save_bookmarks_hint') }}</div>
      </div>

      <div v-if="!loading && bookmarks.length > 0" id="bookmarks-list">
        <div v-for="(b, i) in bookmarks" :key="b.id" class="bookmark-card" :style="{ animationDelay: `${i * 0.05}s` }">
          <div style="flex:1;">
            <div class="bookmark-name">{{ b.name }}</div>
            <div class="bookmark-query">{{ b.query }}</div>
            <div class="bookmark-sites" style="margin-top:6px;">
              <span v-for="s in b.sites || []" :key="s" class="post-card-badge" :class="s" style="font-size:9px;">{{ s }}</span>
            </div>
          </div>
          <button class="btn btn-primary btn-sm" @click.stop="apply(b.query)">
            🔍 {{ lang.t('search_btn') }}
          </button>
          <button class="btn btn-danger btn-sm" @click.stop="del(b.id)">
            ✕
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useFeedStore } from '../stores/feed.js'
import { useToastStore } from '../stores/toast.js'
import { useLangStore } from '../stores/lang.js'
import { apiGetBookmarks, apiDeleteBookmark } from '../api.js'

const auth = useAuthStore()
const feed = useFeedStore()
const router = useRouter()
const toast = useToastStore()
const lang = useLangStore()

const bookmarks = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await apiGetBookmarks()
    bookmarks.value = data.bookmarks || []
  } catch (e) {
    toast.show(lang.t('error_load_bookmarks') + ': ' + e.message, 'error')
  } finally {
    loading.value = false
  }
}

function apply(query) {
  feed.tags = query
  router.push('/')
}

async function del(id) {
  if (!confirm(lang.t('confirm_delete'))) return
  try {
    await apiDeleteBookmark(id)
    bookmarks.value = bookmarks.value.filter(x => x.id !== id)
    toast.show(lang.t('removed_fav'), 'info')
  } catch (e) {
    toast.show(e.message, 'error')
  }
}

onMounted(() => {
  if (auth.isAuthenticated) {
    load()
  }
})
</script>
