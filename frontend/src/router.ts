import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

// FeedView is kept as a static import (it is the initial route); all other views
// are code-split lazily so they don't block first paint or the feed bundle.
import FeedView from './views/FeedView.vue'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'feed', component: FeedView },
  { path: '/post', name: 'post', component: () => import('./views/PostView.vue') },
  { path: '/favorites', name: 'favorites', component: () => import('./views/FavoritesView.vue') },
  { path: '/bookmarks', name: 'bookmarks', component: () => import('./views/BookmarksView.vue') },
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
  { path: '/register', name: 'register', component: () => import('./views/RegisterView.vue') },
  { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue') },
  { path: '/guides', name: 'guides', component: () => import('./views/GuidesView.vue') },
  { path: '/privacy', name: 'privacy', component: () => import('./views/PrivacyView.vue') },
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
