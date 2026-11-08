<template>
  <nav id="navbar">
    <div class="nav-inner">
      <div class="nav-logo" @click="router.push('/')" id="nav-logo">
        <span class="nav-logo-icon"><AppIcon name="logo" :size="26" :stroke-width="1.6" /></span>
        <span>BooruHub</span>
      </div>

      <div class="nav-links">
        <button v-for="item in visibleItems" :key="item.id" class="nav-link"
                :class="{ active: route.name === item.route }"
                :title="lang.t(item.label)" :aria-label="lang.t(item.label)"
                @click="router.push(item.path)" :id="'nav-' + item.id">
          <span class="nav-link-icon"><AppIcon :name="item.icon" :size="20" /></span>
          <span>{{ lang.t(item.label) }}</span>
        </button>
      </div>

      <div class="nav-user">
        <span class="nav-divider" aria-hidden="true"></span>
        <button class="nav-icon-btn" @click="themeStore.toggle()"
                :title="themeStore.theme" :aria-label="themeStore.theme" id="nav-theme">
          <AppIcon :name="themeIcon" :size="19" />
        </button>
        <button class="nav-icon-btn nav-lang-btn" @click="toggleLang" id="nav-lang">
          {{ lang.locale.toUpperCase() }}
        </button>
        <template v-if="auth.isAuthenticated">
          <div class="nav-avatar">{{ auth.user?.username?.[0]?.toUpperCase() || '?' }}</div>
          <span class="nav-username">{{ auth.user?.username || '' }}</span>
          <button class="btn btn-ghost btn-sm" @click="doLogout" id="nav-logout" :title="lang.t('logout')">
            <span class="nav-logout-icon">🚪</span>
            <span class="nav-logout-text">{{ lang.t('logout') }}</span>
          </button>
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
import AppIcon from './AppIcon.vue'
import type { IconName } from './AppIcon.vue'
import type { TranslationKey } from '../types'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()
const lang = useLangStore()
const themeStore = useThemeStore()

const items: { id: string; route: string; path: string; label: TranslationKey; icon: IconName }[] = [
  { id: 'feed', route: 'feed', path: '/', label: 'nav_feed', icon: 'home' },
  { id: 'guides', route: 'guides', path: '/guides', label: 'nav_guides', icon: 'guides' },
  { id: 'favorites', route: 'favorites', path: '/favorites', label: 'nav_favorites', icon: 'heart' },
  { id: 'bookmarks', route: 'bookmarks', path: '/bookmarks', label: 'nav_bookmarks', icon: 'bookmark' },
  { id: 'settings', route: 'settings', path: '/settings', label: 'nav_settings', icon: 'settings' },
]

const visibleItems = computed(() =>
  auth.isAuthenticated ? items : items.filter((i) => i.id === 'feed' || i.id === 'guides'),
)

const themeIcon = computed<IconName>(() => {
  if (themeStore.theme === 'dark') return 'moon'
  if (themeStore.theme === 'light') return 'sun'
  return 'monitor'
})

function toggleLang() {
  lang.setLocale(lang.locale === 'en' ? 'ru' : 'en')
}

async function doLogout() {
  await auth.logout()
  toast.show(lang.t('logged_out'), 'info')
  router.push('/')
}
</script>
