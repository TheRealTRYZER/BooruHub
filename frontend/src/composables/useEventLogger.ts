/**
 * Event logger composable for the recommendation system.
 * 
 * Batches events and flushes them periodically or when the batch is full.
 * Provides an IntersectionObserver wrapper for impression tracking.
 */
import { ref, onUnmounted } from 'vue'
import { apiLogEvents } from '../api'
import { useAuthStore } from '../stores/auth'
import type { UserEventPayload, Post } from '../types'

// WeakMap for associating Post data with DOM elements (replaces monkey-patching)
const _postMap = new WeakMap<HTMLElement, Post>()

const BATCH_SIZE = 10
const FLUSH_INTERVAL_MS = 15_000 // 15 seconds

// Shared global batch (singleton across components)
const _batch: UserEventPayload[] = []
let _flushTimer: ReturnType<typeof setInterval> | null = null
let _observerInstance: IntersectionObserver | null = null

// Track which post IDs have already logged an impression this session
const _impressedIds = new Set<string>()

function _flush() {
  if (_batch.length === 0) return
  const auth = useAuthStore()
  if (!auth.isAuthenticated) return

  const toSend = _batch.splice(0, _batch.length)
  apiLogEvents(toSend) // fire-and-forget
}

function _ensureTimer() {
  if (_flushTimer) return
  _flushTimer = setInterval(_flush, FLUSH_INTERVAL_MS)

  // Flush on page unload
  if (typeof window !== 'undefined') {
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') _flush()
    })
    window.addEventListener('beforeunload', _flush)
  }
}

export function useEventLogger() {
  _ensureTimer()

  function log(event: UserEventPayload) {
    const auth = useAuthStore()
    if (!auth.isAuthenticated) return
    
    _batch.push(event)
    if (_batch.length >= BATCH_SIZE) _flush()
  }

  function logImpression(post: Post, durationSec: number) {
    const key = `${post.source_site}:${post.id}`
    if (_impressedIds.has(key)) return
    _impressedIds.add(key)

    log({
      type: 'impression',
      source: post.source_site,
      post_id: String(post.id),
      tags: post.tags?.slice(0, 30), // cap at 30 tags to limit payload
      duration_sec: Math.round(durationSec),
    })
  }

  function logView(post: Post) {
    log({
      type: 'view',
      source: post.source_site,
      post_id: String(post.id),
      tags: post.tags?.slice(0, 30),
    })
  }

  function logLike(post: Post) {
    log({
      type: 'like',
      source: post.source_site,
      post_id: String(post.id),
      tags: post.tags?.slice(0, 30),
    })
  }

  function logFavourite(post: Post) {
    log({
      type: 'favourite',
      source: post.source_site,
      post_id: String(post.id),
      tags: post.tags?.slice(0, 30),
    })
  }

  function logSearch(query: string) {
    if (!query.trim()) return
    log({
      type: 'search',
      query,
    })
  }

  /**
   * Create an IntersectionObserver-based impression tracker.
   * Call observe(el, post) for each PostCard element.
   * The observer will fire an impression event after the post is visible for 2+ seconds.
   */
  function createImpressionObserver(): {
    observe: (el: HTMLElement, post: Post) => void
    disconnect: () => void
  } {
    const timers = new Map<HTMLElement, { start: number; post: Post }>()

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const el = entry.target as HTMLElement
          if (entry.isIntersecting) {
            const post = _postMap.get(el)
            if (post) {
              timers.set(el, { start: Date.now(), post })
            }
          } else {
            const info = timers.get(el)
            if (info) {
              const duration = (Date.now() - info.start) / 1000
              if (duration >= 2) {
                logImpression(info.post, duration)
              }
              timers.delete(el)
            }
          }
        }
      },
      { threshold: 0.5 }
    )

    return {
      observe(el: HTMLElement, post: Post) {
        _postMap.set(el, post)
        observer.observe(el)
      },
      disconnect() {
        // Flush remaining timers
        for (const [, info] of timers) {
          const duration = (Date.now() - info.start) / 1000
          if (duration >= 2) {
            logImpression(info.post, duration)
          }
        }
        timers.clear()
        observer.disconnect()
      },
    }
  }

  return {
    log,
    logImpression,
    logView,
    logLike,
    logFavourite,
    logSearch,
    createImpressionObserver,
  }
}
