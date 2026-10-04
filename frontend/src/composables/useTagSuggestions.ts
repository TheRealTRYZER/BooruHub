import { computed, onUnmounted, ref } from 'vue'
import { apiSuggestTags } from '../api'
import type { TagSuggestion } from '../types'

const DEBOUNCE_MS = 300
const BLUR_GRACE_MS = 200
const MIN_PREFIX_LENGTH = 2

export interface TagSuggestionsOptions {
  /** How many suggestions to keep visible. */
  limit?: number
  /** Return true while the owning input still has focus. */
  isFocused?: () => boolean
  /** Return false to drop in-flight responses, e.g. another split-search site took over. */
  isActive?: () => boolean
  /** Invoked after the list was closed because focus left the input. */
  onClose?: () => void
  debounceMs?: number
  blurGraceMs?: number
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError'
}

function pickCount(a?: number, b?: number): number | undefined {
  if (a == null) return b
  if (b == null) return a
  return Math.max(a, b)
}

/**
 * Fills in the fields the other response left blank. Whichever response knows
 * more about a tag wins, so a late remote answer can never strip a badge, a post
 * count or a "you search this often" marker off an already visible row.
 */
function enrich(base: TagSuggestion, next: TagSuggestion): TagSuggestion {
  return {
    tag: base.tag,
    is_mapped: base.is_mapped || next.is_mapped,
    from_danbooru: Boolean(base.from_danbooru || next.from_danbooru),
    from_e621: Boolean(base.from_e621 || next.from_e621),
    from_rule34: Boolean(base.from_rule34 || next.from_rule34),
    category: next.category || base.category,
    post_count: pickCount(base.post_count, next.post_count),
    search_count: pickCount(base.search_count, next.search_count),
  }
}

function keyOf(tag: string): string {
  return tag.toLowerCase()
}

function mergeByTag(items: TagSuggestion[]): Map<string, TagSuggestion> {
  const byTag = new Map<string, TagSuggestion>()
  for (const item of items) {
    const key = keyOf(item.tag)
    const already = byTag.get(key)
    byTag.set(key, already ? enrich(already, item) : item)
  }
  return byTag
}

/**
 * Merges a newer response into the list that is already on screen without
 * reshuffling it.
 *
 * `list.value = response.suggestions` made the dropdown jump under the cursor
 * ~300ms after every keystroke: the local-only pass ranks tags purely by cached
 * usage, then the remote pass adds post counts and promoted tags, and the rows
 * reordered. Here the rows that already exist keep their position and are only
 * enriched in place; genuinely new matches are appended, and rows the newer
 * pass no longer knows about fall to the end as filler, so nothing is ever
 * duplicated.
 */
function mergePreservingOrder(prev: TagSuggestion[], next: TagSuggestion[]): TagSuggestion[] {
  const nextByTag = mergeByTag(next)
  const prevKeys = new Set(prev.map(item => keyOf(item.tag)))

  const kept: TagSuggestion[] = []
  const dropped: TagSuggestion[] = []
  for (const item of prev) {
    const fresh = nextByTag.get(keyOf(item.tag))
    if (fresh) kept.push(enrich(item, fresh))
    else dropped.push(item)
  }

  const added: TagSuggestion[] = []
  for (const item of nextByTag.values()) {
    if (!prevKeys.has(keyOf(item.tag))) added.push(item)
  }

  return [...kept, ...added, ...dropped]
}

export function useTagSuggestions(options: TagSuggestionsOptions = {}) {
  const limit = options.limit ?? 15
  const debounceMs = options.debounceMs ?? DEBOUNCE_MS
  const blurGraceMs = options.blurGraceMs ?? BLUR_GRACE_MS
  const isFocused = options.isFocused ?? (() => false)
  const isActive = options.isActive ?? (() => true)

  const items = ref<TagSuggestion[]>([])
  const pending = ref(false)

  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let blurTimer: ReturnType<typeof setTimeout> | null = null
  let fastController: AbortController | null = null
  let fullController: AbortController | null = null
  let queryId = 0
  // Whose response established the list currently on screen. A response for a
  // newer query replaces the list outright; later passes for the same query
  // merge into it so the rows never reshuffle.
  let baseId = 0
  let inFlight = 0
  let disposed = false

  function isCurrent(myId: number): boolean {
    return !disposed && myId === queryId && isActive()
  }

  function syncPending() {
    pending.value = inFlight > 0 || debounceTimer !== null
  }

  function trackStart() {
    inFlight++
    syncPending()
  }

  function trackEnd() {
    if (inFlight > 0) inFlight--
    syncPending()
  }

  function cancelRequests() {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (fastController) {
      fastController.abort()
      fastController = null
    }
    if (fullController) {
      fullController.abort()
      fullController = null
    }
    inFlight = 0
    syncPending()
  }

  function cancelPendingClose() {
    if (blurTimer) {
      clearTimeout(blurTimer)
      blurTimer = null
    }
  }

  function clear() {
    queryId++
    baseId = 0
    cancelRequests()
    cancelPendingClose()
    items.value = []
  }

  function close() {
    clear()
    options.onClose?.()
  }

  function apply(myId: number, incoming: TagSuggestion[]) {
    if (!isCurrent(myId)) return
    const base = myId === baseId ? items.value : []
    items.value = mergePreservingOrder(base, incoming).slice(0, limit)
    baseId = myId
  }

  function fail(myId: number, err: unknown) {
    // A failed enrichment pass must not wipe rows the local pass already put on
    // screen, so the list is deliberately left untouched here.
    if (isAbortError(err) || !isCurrent(myId)) return
  }

  function fetchPass(myId: number, prefix: string, fast: boolean) {
    const controller = new AbortController()
    if (fast) fastController = controller
    else fullController = controller

    trackStart()
    apiSuggestTags(prefix, limit, controller.signal, fast)
      .then(data => apply(myId, data.suggestions || []))
      .catch(err => fail(myId, err))
      .finally(() => {
        if (fast && fastController === controller) fastController = null
        if (!fast && fullController === controller) fullController = null
        trackEnd()
      })
  }

  /**
   * Runs both passes for `prefix`: an instant local-only lookup, then a
   * debounced fan-out to the boorus APIs.
   */
  function query(prefix: string) {
    cancelPendingClose()
    queryId++
    baseId = 0
    const myId = queryId
    cancelRequests()

    const clean = prefix.trim()
    if (clean.length < MIN_PREFIX_LENGTH) {
      items.value = []
      return
    }

    fetchPass(myId, clean, true)

    debounceTimer = setTimeout(() => {
      debounceTimer = null
      if (!isCurrent(myId)) return
      fetchPass(myId, clean, false)
    }, debounceMs)
    syncPending()
  }

  /** Cancels a scheduled close, e.g. because the input was refocused. */
  function onFocus() {
    cancelPendingClose()
  }

  /**
   * Closes the dropdown once focus is really gone. The grace period is what lets
   * a click on a suggestion register first, and the `isFocused` re-check stops
   * the timer from closing a list the user has already come back to.
   */
  function onBlur() {
    cancelPendingClose()
    blurTimer = setTimeout(() => {
      blurTimer = null
      if (isFocused()) return
      close()
    }, blurGraceMs)
  }

  onUnmounted(() => {
    disposed = true
    cancelRequests()
    cancelPendingClose()
  })

  return {
    items,
    pending,
    isOpen: computed(() => items.value.length > 0),
    query,
    clear,
    onFocus,
    onBlur,
  }
}
