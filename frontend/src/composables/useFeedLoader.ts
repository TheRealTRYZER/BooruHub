import { ref, onUnmounted } from 'vue'
import { apiFeed } from '../api'
import { useEventLogger } from './useEventLogger'
import type { SiteName, Post } from '../types'

export function useFeedLoader(feed: any, toast: any, lang: any, availableSites: SiteName[]) {
  const loading = ref(false)
  const skeletonCount = ref(0)
  const correctedTags = ref<string | null>(null)
  let loadGeneration = 0
  let autoFetchCount = 0
  let lastUnfilteredCount = 0
  const activeTimeouts: any[] = []

  // Set when the backend returns a 429 / "Rate limit exceeded". While set, all
  // further loads are suppressed (no auto-retry spam) and a single toast is shown.
  // It auto-clears after the rate-limit window so the user can resume scrolling.
  let rateLimited = false

  function scheduleTimeout(cb: () => void, ms: number) {
    const id = setTimeout(() => {
      const idx = activeTimeouts.indexOf(id)
      if (idx !== -1) activeTimeouts.splice(idx, 1)
      cb()
    }, ms)
    activeTimeouts.push(id)
    return id
  }

  onUnmounted(() => {
    for (const id of activeTimeouts) {
      clearTimeout(id)
    }
    activeTimeouts.length = 0
  })

  async function loadMore(sentinel?: HTMLElement | null, isAuto = false) {
    if (loading.value || !feed.hasMore) return
    // Suppress everything while we're rate-limited (manual scroll loads included)
    // — a fresh reload() (user-initiated search) clears the flag.
    if (rateLimited) return

    if (!isAuto) {
      autoFetchCount = 0
    } else {
      autoFetchCount++
      const maxAutoFetch = lastUnfilteredCount > 0 ? 10 : 5
      if (autoFetchCount >= maxAutoFetch) {
        console.warn(`Max automatic load attempts reached (${maxAutoFetch}). Stopping to prevent infinite loops.`)
        loading.value = false
        skeletonCount.value = 0
        return
      }
    }

    loading.value = true
    skeletonCount.value = 12
    const gen = ++loadGeneration

    const activeSites = feed.isSplit
      ? (availableSites.filter(s => (feed.ratios[s] ?? 1) > 0) as SiteName[])
      : ((feed.sites.length > 0 ? feed.sites : availableSites) as SiteName[])

    const siteTagSig = feed.isSplit ? JSON.stringify(feed.siteTags) : ''
    feed.lastSearchSignature = `${feed.tags}|${feed.sites.join(',')}|${feed.isSplit}|${siteTagSig}`

    try {
      // Build a single request — let the backend handle multi-site interleaving
      const options: Record<string, any> = {
        tags: feed.isSplit ? '' : feed.tags,
        sites: activeSites.join(','),
        page: feed.page,
        limit: feed.postsLimit || 40,
      }

      // Pass per-site tag overrides for split search
      if (feed.isSplit) {
        for (const site of activeSites) {
          options[`${site}_tags`] = feed.siteTags[site] || ''
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

      if (data.has_more !== undefined) {
        feed.hasMore = data.has_more
      }

      const newPosts: Post[] = data.posts || []

      if (data.corrected_tags) {
        correctedTags.value = data.corrected_tags
      }

      const previousCount = feed.posts.length
      if (newPosts.length > 0) {
        correctedTags.value = null
        feed.addPosts(newPosts)
        skeletonCount.value = 0
      }
      const addedCount = feed.posts.length - previousCount

      if (addedCount > 0) {
        autoFetchCount = 0
      }

      const unfiltered = data.unfiltered_count || 0
      lastUnfilteredCount = unfiltered

      if (unfiltered === 0 || newPosts.length === 0) {
        if (unfiltered === 0) {
          feed.hasMore = false
        } else {
          // Backend returned matches but all were filtered (blacklist / dedup).
          // Reset the auto-fetch counter so blacklist-heavy feeds keep paginating
          // through genuine backend results instead of being cut off by the
          // infinite-loop guard — has_more will eventually end the loop.
          autoFetchCount = 0
          feed.page++
          if (feed.hasMore && gen === loadGeneration) {
            const delay = Math.min(50 * Math.pow(2, autoFetchCount), 1000)
            scheduleTimeout(() => { if (gen === loadGeneration) loadMore(sentinel, true) }, delay)
          }
        }
      } else if (addedCount === 0 && feed.hasMore) {
        // All fetched posts were duplicates and skipped — automatically fetch next page
        feed.page++
        if (gen === loadGeneration) {
          const delay = Math.min(50 * Math.pow(2, autoFetchCount), 1000)
          scheduleTimeout(() => { if (gen === loadGeneration) loadMore(sentinel, true) }, delay)
        }
      } else {
        feed.page++
        // Pre-fetch if sentinel is still within the observer's rootMargin threshold
        if (sentinel) {
          scheduleTimeout(() => {
            if (gen === loadGeneration && sentinel && !loading.value && feed.hasMore) {
              const rect = sentinel.getBoundingClientRect()
              if (rect.top <= window.innerHeight + feed.rootMargin) loadMore(sentinel)
            }
          }, 300)
        }
      }
    } catch (e: any) {
      const msg = (e && e.message) ? e.message : String(e)
      const isRateLimit = /rate limit|429/i.test(msg)
      if (isRateLimit) {
        // Show exactly one toast for the whole rate-limit window and stop the
        // infinite-scroll auto-retry loop instead of toasting on every attempt.
        if (!rateLimited && gen === loadGeneration) {
          rateLimited = true
          toast.show(lang.t('failed_load') + ': ' + msg, 'error')
          // The backend search limiter window is 60s; clear after it expires so
          // the user can resume scrolling without a manual reload.
          scheduleTimeout(() => { rateLimited = false }, 61000)
        }
      } else if (gen === loadGeneration) {
        toast.show(lang.t('failed_load') + ': ' + msg, 'error')
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
    rateLimited = false
    feed.resetFeed()
    correctedTags.value = null
    loadMore(sentinel)
  }

  return { loading, skeletonCount, correctedTags, loadMore, reload }
}
