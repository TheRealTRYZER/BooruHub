import { ref } from 'vue'
import { apiFeed } from '../api'
import type { SiteName, Post } from '../types'

export function useFeedLoader(feed: any, toast: any, lang: any, availableSites: SiteName[]) {
  const loading = ref(false)
  const skeletonCount = ref(0)
  const correctedTags = ref<string | null>(null)
  let loadGeneration = 0

  async function loadMore(sentinel?: HTMLElement | null) {
    if (loading.value || !feed.hasMore) return
    loading.value = true
    skeletonCount.value = 12
    const gen = ++loadGeneration

    const activeSites = (feed.sites.length > 0 ? feed.sites : availableSites) as SiteName[]
    const limitPerSite = Math.ceil(45 / activeSites.length)
    
    const siteTagSig = feed.isSplit ? JSON.stringify(feed.siteTags) : ''
    feed.lastSearchSignature = `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|${siteTagSig}`

    const basePosts = [...feed.posts];
    const pagePayloads: Record<string, Post[]> = {};
    const unfilteredCounts: Record<string, number> = {};
    activeSites.forEach(s => {
      pagePayloads[s] = [];
      unfilteredCounts[s] = 0;
    });

    try {
      const fetchPromises = activeSites.map(async (site, idx) => {
        try {
          if (idx > 0) await new Promise(r => setTimeout(r, idx * 50));
          if (gen !== loadGeneration) return 0
          
          const options: Record<string, any> = {}
          if (feed.isSplit) {
            if (feed.siteTags[site]) options[`${site}_tags`] = feed.siteTags[site]
          }
          
          const data = await apiFeed({
            tags: feed.tags,
            sites: site,
            page: feed.page,
            limit: limitPerSite,
            ...options
          })
          if (gen !== loadGeneration) return 0
          
          // Always update with the latest suggestion from any site if results are empty
          if (data.corrected_tags) {
            correctedTags.value = data.corrected_tags
          }

          const newPosts = data.posts || []
          pagePayloads[site] = newPosts
          unfilteredCounts[site] = data.unfiltered_count || 0
          return newPosts.length
        } catch (siteErr) {
          console.error(`Error loading ${site}:`, siteErr)
          return 0
        }
      })

      const results = await Promise.all(fetchPromises)
      if (gen !== loadGeneration) return

      const totalNew = results.reduce((acc, val) => acc + val, 0)
      const allSitesExhausted = activeSites.every(s => unfilteredCounts[s] === 0)
      
      if (totalNew > 0) {
        correctedTags.value = null // Hide suggestion if we found something
        const mixed: Post[] = []
        const maxLen = Math.max(...activeSites.map(s => pagePayloads[s].length))
        for (let i = 0; i < maxLen; i++) {
          for (const activeSite of activeSites) {
            if (pagePayloads[activeSite][i]) mixed.push(pagePayloads[activeSite][i])
          }
        }
        feed.posts = [...basePosts, ...mixed]
        skeletonCount.value = 0
      }

      if (allSitesExhausted) {
        feed.hasMore = false
      } else {
        feed.page++
        if (totalNew === 0 && feed.hasMore && gen === loadGeneration) {
          setTimeout(() => { if (gen === loadGeneration) loadMore(sentinel) }, 50)
        } else if (sentinel) {
          setTimeout(() => {
            if (gen === loadGeneration && sentinel && !loading.value && feed.hasMore) {
              const rect = sentinel.getBoundingClientRect()
              if (rect.top <= window.innerHeight + 800) loadMore(sentinel)
            }
          }, 500)
        }
      }
    } catch (e: any) {
      if (gen === loadGeneration) {
        toast.show(lang.t('failed_load') + ': ' + (e.message || e), 'error')
      }
    } finally {
      if (gen === loadGeneration) {
        loading.value = false
        skeletonCount.value = 0
      }
    }
  }

  function reload(sentinel?: HTMLElement | null) {
    feed.resetFeed()
    correctedTags.value = null
    loadMore(sentinel)
  }

  return { loading, skeletonCount, correctedTags, loadMore, reload }
}
