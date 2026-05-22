import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { SiteName, Post } from '../types'

export const useFeedStore = defineStore('feed', () => {
  const tags = ref(sessionStorage.getItem('booruhub_tags') || '')
  const siteTags = ref<Record<SiteName, string>>({ danbooru: '', e621: '', rule34: '' })
  const ratios = ref<Record<SiteName, number>>({ danbooru: 1, e621: 1, rule34: 1 })
  const isSplit = ref(false)
  const savedSites = localStorage.getItem('booruhub_sites')
  const sites = ref<SiteName[]>(savedSites ? JSON.parse(savedSites) : ['danbooru', 'e621', 'rule34'])

  const cardSize = ref(parseInt(localStorage.getItem('booruhub_card_size') || '250'))
  const previewQuality = ref(localStorage.getItem('booruhub_preview_quality') || 'sample')

  const posts = ref<Post[]>([])
  const page = ref(1)
  const hasMore = ref(true)
  const lastSearchSignature = ref('')

  watch(tags, (newVal) => {
    sessionStorage.setItem('booruhub_tags', newVal)
  })

  watch(sites, (newVal) => {
    localStorage.setItem('booruhub_sites', JSON.stringify(newVal))
  }, { deep: true })

  watch(cardSize, (newVal) => {
    localStorage.setItem('booruhub_card_size', String(newVal))
  })

  watch(previewQuality, (newVal) => {
    localStorage.setItem('booruhub_preview_quality', newVal)
  })

  function toggleSite(site: SiteName) {
    if (sites.value.includes(site)) {
      if (sites.value.length > 1) {
        sites.value = sites.value.filter(s => s !== site)
      }
    } else {
      sites.value = [...sites.value, site]
    }
  }

  function toggleSplit() {
    isSplit.value = !isSplit.value
  }

  function resetFeed() {
    posts.value = []
    page.value = 1
    hasMore.value = true
  }

  function registerPostHash(postId: string | number, site: SiteName, hash: string, tagsList: string[]) {
    const existingPost = posts.value.find(p => p.hash === hash && !(p.id === postId && p.source_site === site))
    
    if (existingPost) {
      const mergedTags = new Set([...existingPost.tags, ...tagsList])
      existingPost.tags = Array.from(mergedTags)
      
      if (!existingPost.duplicate_sites) {
        existingPost.duplicate_sites = []
      }
      if (!existingPost.duplicate_sites.includes(site)) {
        existingPost.duplicate_sites.push(site)
      }
      
      posts.value = posts.value.filter(p => !(p.id === postId && p.source_site === site))
      return true
    } else {
      const currentPost = posts.value.find(p => p.id === postId && p.source_site === site)
      if (currentPost) {
        currentPost.hash = hash
      }
      return false
    }
  }

  return {
    tags, siteTags, ratios, isSplit, sites,
    cardSize, previewQuality,
    posts, page, hasMore, lastSearchSignature,
    toggleSite, toggleSplit, resetFeed, registerPostHash,
  }
})
