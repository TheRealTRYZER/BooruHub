import { ref } from 'vue'
import { apiFeed } from '../api'
import { useEventLogger } from './useEventLogger'
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

    const siteTagSig = feed.isSplit ? JSON.stringify(feed.siteTags) : ''
    feed.lastSearchSignature = `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|${siteTagSig}`

    const basePosts = [...feed.posts]

    try {
      // Build a single request — let the backend handle multi-site interleaving
      const options: Record<string, any> = {
        tags: feed.tags,
        sites: activeSites.join(','),
        page: feed.page,
        limit: 45,
      }

      // Pass per-site tag overrides for split search
      if (feed.isSplit) {
        for (const site of activeSites) {
          if (feed.siteTags[site]) {
            options[`${site}_tags`] = feed.siteTags[site]
          }
        }
      }

      // Pass ratios if non-default
      const ratioValues = activeSites.map(s => feed.ratios[s] ?? 1)
      const hasCustomRatios = ratioValues.some((v: number) => v !== 1)
      if (hasCustomRatios) {
        options.ratios = ratioValues.join(',')
      }

      const data = await apiFeed(options)
      if (gen !== loadGeneration) return

      const newPosts: Post[] = data.posts || []

      if (data.corrected_tags) {
        correctedTags.value = data.corrected_tags
      }

      if (newPosts.length > 0) {
        correctedTags.value = null
        feed.posts = [...basePosts, ...newPosts]
        skeletonCount.value = 0
      }

      const unfiltered = data.unfiltered_count || 0
      if (unfiltered === 0 || newPosts.length === 0) {
        if (unfiltered === 0) {
          feed.hasMore = false
        } else {
          // Backend returned matches but all were filtered — try next page
          feed.page++
          if (feed.hasMore && gen === loadGeneration) {
            setTimeout(() => { if (gen === loadGeneration) loadMore(sentinel) }, 50)
          }
        }
      } else {
        feed.page++
        // Pre-fetch if sentinel is still visible
        if (sentinel) {
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
    const { logSearch } = useEventLogger()
    if (feed.tags) logSearch(feed.tags)
    feed.resetFeed()
    correctedTags.value = null
    loadMore(sentinel)
  }

  return { loading, skeletonCount, correctedTags, loadMore, reload }
}
