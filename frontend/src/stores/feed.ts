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
  const rootMargin = ref(parseInt(localStorage.getItem('booruhub_root_margin') || '2500'))

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

  watch(rootMargin, (newVal) => {
    localStorage.setItem('booruhub_root_margin', String(newVal))
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

  function getInstantPostHash(post: Post): string {
    if (post.md5) {
      return `md5-${post.md5}`
    }
    
    const fileUrl = post.file_url || post.sample_url || post.preview_url || ''
    if (fileUrl) {
      const filename = fileUrl.substring(fileUrl.lastIndexOf('/') + 1)
      let hash = 0
      for (let i = 0; i < filename.length; i++) {
        const char = filename.charCodeAt(i)
        hash = (hash << 5) - hash + char
        hash |= 0
      }
      return `fn-${hash}`
    }
    
    return `id-${post.source_site}-${post.id}`
  }

  function addPosts(newPosts: Post[]) {
    for (const post of newPosts) {
      // Avoid adding exact duplicate by site ID
      const exists = posts.value.find(p => p.id === post.id && p.source_site === post.source_site)
      if (exists) continue

      post.duplicates = post.duplicates || []
      post.duplicate_sites = post.duplicate_sites || []

      // 1. Instant check: Exact MD5 match
      if (post.md5) {
        const existingPost = posts.value.find(p => p.md5 === post.md5)
        if (existingPost) {
          // Merge tags
          const mergedTags = new Set([...existingPost.tags, ...post.tags])
          existingPost.tags = Array.from(mergedTags)
          
          // Save full duplicate post
          existingPost.duplicates = existingPost.duplicates || []
          if (!existingPost.duplicates.some(d => d.id === post.id && d.source_site === post.source_site)) {
            existingPost.duplicates.push(post)
          }

          // Track duplicate site badge
          if (!existingPost.duplicate_sites) {
            existingPost.duplicate_sites = []
          }
          if (!existingPost.duplicate_sites.includes(post.source_site)) {
            existingPost.duplicate_sites.push(post.source_site)
          }
          continue // Skip adding as main post
        }
      }

      // Initialize with instant fallback hash so store tests pass, and component triggers verification based on prefix
      post.hash = getInstantPostHash(post)
      posts.value.push(post)
    }
  }

  return {
    tags, siteTags, ratios, isSplit, sites,
    cardSize, previewQuality, rootMargin,
    posts, page, hasMore, lastSearchSignature,
    toggleSite, toggleSplit, resetFeed, addPosts,
    getInstantPostHash
  }
})

