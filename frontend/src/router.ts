import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import FeedView from './views/FeedView.vue'
import PostView from './views/PostView.vue'
import FavoritesView from './views/FavoritesView.vue'
import BookmarksView from './views/BookmarksView.vue'
import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import SettingsView from './views/SettingsView.vue'
import GuidesView from './views/GuidesView.vue'
import PrivacyView from './views/PrivacyView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'feed', component: FeedView },
  { path: '/post', name: 'post', component: PostView },
  { path: '/favorites', name: 'favorites', component: FavoritesView },
  { path: '/bookmarks', name: 'bookmarks', component: BookmarksView },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/register', name: 'register', component: RegisterView },
  { path: '/settings', name: 'settings', component: SettingsView },
  { path: '/guides', name: 'guides', component: GuidesView },
  { path: '/privacy', name: 'privacy', component: PrivacyView },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
})

export default router
