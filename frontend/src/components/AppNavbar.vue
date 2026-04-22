<template>
  <nav id="navbar">
    <div class="nav-inner">
      <div class="nav-logo" @click="router.push('/')" id="nav-logo">
        <span class="nav-logo-icon">⬡</span>
        <span>BooruHub</span>
      </div>

      <div class="nav-links">
        <button class="nav-link" :class="{ active: route.name === 'feed' }"
                @click="router.push('/')" id="nav-feed">
          <span class="nav-link-icon">🏠</span>
          <span>{{ lang.t('nav_feed') }}</span>
        </button>
        <button class="nav-link" :class="{ active: route.name === 'guides' }"
                @click="router.push('/guides')" id="nav-guides">
          <span class="nav-link-icon">📚</span>
          <span>{{ lang.t('nav_guides') }}</span>
        </button>
        <template v-if="auth.isAuthenticated">
          <button class="nav-link" :class="{ active: route.name === 'favorites' }"
                  @click="router.push('/favorites')" id="nav-favorites">
            <span class="nav-link-icon">❤️</span>
            <span>{{ lang.t('nav_favorites') }}</span>
          </button>
          <button class="nav-link" :class="{ active: route.name === 'bookmarks' }"
                  @click="router.push('/bookmarks')" id="nav-bookmarks">
            <span class="nav-link-icon">🔖</span>
            <span>{{ lang.t('nav_bookmarks') }}</span>
          </button>
          <button class="nav-link" :class="{ active: route.name === 'settings' }"
                  @click="router.push('/settings')" id="nav-settings">
            <span class="nav-link-icon">⚙️</span>
            <span>{{ lang.t('nav_settings') }}</span>
          </button>
        </template>
      </div>

      <div class="nav-user">
        <button class="btn btn-ghost btn-sm" @click="themeStore.toggle()"
                :title="themeStore.theme" id="nav-theme"
                style="font-size: 16px; padding: 4px 8px;">
          {{ themeIcon }}
        </button>
        <button class="btn btn-ghost btn-sm" @click="toggleLang" style="font-weight: 700; color: var(--accent);">
          {{ lang.locale.toUpperCase() }}
        </button>
        <template v-if="auth.isAuthenticated">
          <div class="nav-avatar">{{ auth.user!.username[0].toUpperCase() }}</div>
          <span class="nav-username">{{ auth.user!.username }}</span>
          <button class="btn btn-ghost btn-sm" @click="doLogout" id="nav-logout">{{ lang.t('logout') }}</button>
        </template>
        <template v-else>
          <button class="btn btn-primary btn-sm" @click="router.push('/login')" id="nav-login">{{ lang.t('login') }}</button>
        </template>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useToastStore } from '../stores/toast'
import { useLangStore } from '../stores/lang'
import { useThemeStore } from '../stores/theme'
import { computed } from 'vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const themeStore = useThemeStore()

const themeIcon = computed(() => {
  if (themeStore.theme === 'dark') return '🌙'
  if (themeStore.theme === 'light') return '☀️'
  return '🖥'
})

function toggleLang() {
  lang.setLocale(lang.locale === 'en' ? 'ru' : 'en')
}

function doLogout() {
  auth.logout()
  toast.show(lang.t('logged_out'), 'info')
  router.push('/')
}
</script>
