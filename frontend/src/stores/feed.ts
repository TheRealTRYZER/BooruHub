import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { SiteName, Post } from '../types'

export const useFeedStore = defineStore('feed', () => {
  const tags = ref(sessionStorage.getItem('booruhub_tags') || '')
  
  const savedSiteTags = localStorage.getItem('booruhub_site_tags')
  const siteTags = ref<Record<SiteName, string>>(savedSiteTags ? JSON.parse(savedSiteTags) : { danbooru: '', e621: '', rule34: '' })
  
  const savedRatios = localStorage.getItem('booruhub_ratios')
  const ratios = ref<Record<SiteName, number>>(savedRatios ? JSON.parse(savedRatios) : { danbooru: 1, e621: 1, rule34: 1 })
  
  const isSplit = ref(localStorage.getItem('booruhub_is_split') === 'true')
  
  const savedSites = localStorage.getItem('booruhub_sites')
  const sites = ref<SiteName[]>(savedSites ? JSON.parse(savedSites) : ['danbooru', 'e621', 'rule34'])

  const parseCardSize = (val: string | null): number => {
    const parsed = parseInt(val || '250', 10)
    return Number.isFinite(parsed) && parsed >= 100 && parsed <= 500 ? parsed : 250
  }
  const cardSize = ref(parseCardSize(localStorage.getItem('booruhub_card_size')))

  const parseQuality = (val: string | null): 'thumbnail' | 'sample' | 'full' => {
    const allowed = ['thumbnail', 'sample', 'full']
    return allowed.includes(val || '') ? (val as 'thumbnail' | 'sample' | 'full') : 'thumbnail'
  }
  const previewQuality = ref(parseQuality(localStorage.getItem('booruhub_preview_quality')))

  const parseRootMargin = (val: string | null): number => {
    const parsed = parseInt(val || '1200', 10)
    return Number.isFinite(parsed) && parsed >= 100 && parsed <= 5000 ? parsed : 1200
  }
  const rootMargin = ref(parseRootMargin(localStorage.getItem('booruhub_root_margin')))

  const parsePostsLimit = (val: string | null): number => {
    const parsed = parseInt(val || '40', 10)
    return Number.isFinite(parsed) && parsed >= 10 && parsed <= 200 ? parsed : 40
  }
  const postsLimit = ref(parsePostsLimit(localStorage.getItem('booruhub_posts_limit')))

  const posts = ref<Post[]>([])
  const page = ref(1)
  const hasMore = ref(true)
  const lastSearchSignature = ref('')

  watch(tags, (newVal) => {
    sessionStorage.setItem('booruhub_tags', newVal)
  })

  watch(siteTags, (newVal) => {
    localStorage.setItem('booruhub_site_tags', JSON.stringify(newVal))
  }, { deep: true })

  watch(ratios, (newVal) => {
    localStorage.setItem('booruhub_ratios', JSON.stringify(newVal))
  }, { deep: true })

  watch(isSplit, (newVal) => {
    localStorage.setItem('booruhub_is_split', String(newVal))
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

  watch(postsLimit, (newVal) => {
    localStorage.setItem('booruhub_posts_limit', String(newVal))
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
    // Build O(1) lookup maps once per call instead of find()-scanning all posts per new post.
    const byKey = new Map<string, Post>()
    const byMd5 = new Map<string, Post>()
    for (const p of posts.value) {
      byKey.set(`${p.source_site}:${p.id}`, p)
      if (p.md5) byMd5.set(p.md5, p)
    }

    for (const rawPost of newPosts) {
      const key = `${rawPost.source_site}:${rawPost.id}`
      if (byKey.has(key)) continue

      // Clone post to prevent cache pollution
      const post: Post = {
        ...rawPost,
        tags: [...(rawPost.tags || [])],
        duplicates: rawPost.duplicates ? rawPost.duplicates.map(d => ({ ...d, tags: [...(d.tags || [])] })) : [],
        duplicate_sites: rawPost.duplicate_sites ? [...rawPost.duplicate_sites] : [],
        tags_metadata: rawPost.tags_metadata ? { ...rawPost.tags_metadata } : null
      }

      // 1. Instant check: Exact MD5 match
      if (post.md5) {
        const existingPost = byMd5.get(post.md5)
        if (existingPost) {
          // Merge tags
          const mergedTags = new Set([...existingPost.tags, ...post.tags])
          existingPost.tags = Array.from(mergedTags)

          // Save full duplicate post
          existingPost.duplicates = existingPost.duplicates || []
          if (!existingPost.duplicates.some(d => String(d.id) === String(post.id) && d.source_site === post.source_site)) {
            existingPost.duplicates.push(post)
          }

          // Track duplicate site badge
          if (!existingPost.duplicate_sites) {
            existingPost.duplicate_sites = []
          }
          if (!existingPost.duplicate_sites.includes(post.source_site)) {
            existingPost.duplicate_sites.push(post.source_site)
          }
          // Future duplicates of the same site:id resolve to the merged post
          byKey.set(key, existingPost)
          continue // Skip adding as main post
        }
        byMd5.set(post.md5, post)
      }

      // Initialize with instant fallback hash so store tests pass
      post.hash = getInstantPostHash(post)
      byKey.set(key, post)
      posts.value.push(post)
    }
  }

  return {
    tags, siteTags, ratios, isSplit, sites,
    cardSize, previewQuality, rootMargin, postsLimit,
    posts, page, hasMore, lastSearchSignature,
    toggleSite, toggleSplit, resetFeed, addPosts,
    getInstantPostHash
  }
})
