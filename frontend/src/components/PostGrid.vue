<template>
  <div class="post-grid" ref="gridEl" :style="{ '--card-size': feed.cardSize + 'px' }">
    <div v-for="(col, ci) in columns" :key="ci" class="post-column">
      <div v-for="item in col" :key="item.key" :data-post-key="item.key">
        <component :is="item.component" v-bind="item.props" @click-media="handleCardClick" @favorite-changed="handleFavoriteChanged" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, markRaw } from 'vue'
import { useFeedStore } from '../stores/feed'
import PostCard from './PostCard.vue'
import SkeletonCard from './SkeletonCard.vue'
import { useEventLogger } from '../composables/useEventLogger'
import type { Post, SiteName } from '../types'

const feed = useFeedStore()

const emit = defineEmits<{
  (e: 'click-media', post: Post): void
  (e: 'favorite-changed', payload: { sourceSite: SiteName, postId: string | number, isFav: boolean, isDislike: boolean }): void
}>()

function handleCardClick(post: Post) {
  emit('click-media', post)
}

function handleFavoriteChanged(payload: { sourceSite: SiteName, postId: string | number, isFav: boolean, isDislike: boolean }) {
  emit('favorite-changed', payload)
}

interface GridItem {
  key: string
  component: any
  props: { post?: Post }
}

const props = withDefaults(defineProps<{
  posts?: Post[]
  loading?: boolean
  skeletonCount?: number
}>(), {
  posts: () => [],
  loading: false,
  skeletonCount: 0
})

const gridEl = ref<HTMLElement | null>(null)
const colCount = ref(getColCount())
const columns = ref<GridItem[][]>([])
// Accumulated estimated height per column (in aspect-ratio units = height / width).
// All columns share the same width, so comparing these is equivalent to comparing pixel
// heights without ever touching the DOM — fixes the uneven masonry from count-based balancing.
const colHeights = ref<number[]>([])

// Track all items placed so we can append incrementally
let placedCount = 0
let skeletonKeys: string[] = []

function getColCount() {
  const w = window.innerWidth
  const gap = w <= 768 ? 8 : 16
  const availableWidth = w - 40
  const cols = Math.floor((availableWidth + gap) / (feed.cardSize + gap))
  return Math.max(1, Math.min(20, cols))
}

function initColumns() {
  columns.value = Array.from({ length: colCount.value }, () => [])
  colHeights.value = Array.from({ length: colCount.value }, () => 0)
  placedCount = 0
  skeletonKeys = []
}

// Estimate a card's height in aspect-ratio units (height / width). Mirrors PostCard.mediaStyle:
// known dims use the real ratio, very tall posts are capped at 9/21, unknown dims default to a square.
function estimateHeight(post: Post): number {
  const p = post
  const w = p.width
  const h = p.height
  if (w && h && w > 0) {
    const ratio = h / w
    return ratio >= 21 / 9 ? 21 / 9 : ratio
  }
  return 1
}

function getShortestColIndex() {
  // Use accumulated estimated height as the primary balance signal.
  let minIdx = 0
  let minH = colHeights.value[0] ?? 0
  let minLen = columns.value[0]?.length ?? 0
  for (let i = 1; i < columns.value.length; i++) {
    const h = colHeights.value[i] ?? 0
    const len = columns.value[i]?.length ?? 0
    if (h < minH - 0.001 || (Math.abs(h - minH) <= 0.001 && len < minLen)) {
      minH = h
      minLen = len
      minIdx = i
    }
  }
  return minIdx
}

function appendToColumn(idx: number, item: GridItem, post?: Post) {
  const col = columns.value[idx]
  if (!col) return
  col.push(item)
  if (post) colHeights.value[idx] = (colHeights.value[idx] ?? 0) + estimateHeight(post)
}

// Recompute accumulated heights from scratch (used after filtering / removing items).
function recomputeHeights() {
  const heights = Array.from({ length: columns.value.length }, () => 0)
  columns.value.forEach((col, ci) => {
    if (!col) return
    for (const item of col) {
      const post = item.props?.post
      if (post) heights[ci] = (heights[ci] ?? 0) + estimateHeight(post)
    }
  })
  colHeights.value = heights
}

function placeNewPosts() {
  const newPosts = props.posts.slice(placedCount)
  for (const post of newPosts) {
    const idx = getShortestColIndex()
    appendToColumn(idx, {
      key: `${post.source_site}-${post.id}`,
      component: markRaw(PostCard),
      props: { post },
    }, post)
    placedCount++
  }
}

function removeSkeletons() {
  for (const col of columns.value) {
    // Filter out skeletons
    if (col) {
      const filtered = col.filter(item => !item.key.startsWith('sk-'))
      col.length = 0
      col.push(...filtered)
    }
  }
  skeletonKeys = []
}

function addSkeletons(count: number) {
  removeSkeletons()
  for (let i = 0; i < count; i++) {
    const idx = i % colCount.value
    const key = `sk-${Date.now()}-${i}`
    appendToColumn(idx, {
      key,
      component: markRaw(SkeletonCard),
      props: {},
    })
    skeletonKeys.push(key)
  }
}

let lastFirstPostKey = ''

// Watch posts via a cheap signature (length + first/last key) instead of deep-watching
// the whole array. Deep watching traverses every nested tag/duplicate on each reactive
// tick — O(N * tags) — which is the main source of lag with many posts.
watch(() => {
  const arr = props.posts
  if (!arr || arr.length === 0) return '0|'
  const first = arr[0]!
  const last = arr[arr.length - 1]!
  return `${arr.length}|${first.source_site}-${first.id}|${last.source_site}-${last.id}`
}, () => {
  const newVal = props.posts
  if (!newVal) return
  const firstPost = newVal[0]
  const firstPostKey = firstPost ? `${firstPost.source_site}-${firstPost.id}` : ''
  const isNewSearch = newVal.length === 0 || firstPostKey !== lastFirstPostKey
  
  lastFirstPostKey = firstPostKey
  
  removeSkeletons()

  if (isNewSearch) {
    initColumns()
    placeNewPosts()
    setTimeout(observeNewCards, 100)
  } else {
    // 1. Build a lookup set of active post keys in O(M) time
    const activeKeys = new Set(newVal.map(p => `${p.source_site}-${p.id}`))

    // 2. Filter out deleted cards in O(N) time
    for (const col of columns.value) {
      if (col) {
        const filtered = col.filter(item => {
          if (item.key.startsWith('sk-')) return true // keep manual loading skeletons
          return activeKeys.has(item.key)
        })
        if (filtered.length !== col.length) {
          col.length = 0
          col.push(...filtered)
        }
      }
    }
    recomputeHeights()

    // 3. Identify and place new posts that are not yet in columns in O(N + M) time
    const placedKeys = new Set(columns.value.flatMap(col => col ? col.map(item => item.key) : []))
    const newPosts = newVal.filter(p => !placedKeys.has(`${p.source_site}-${p.id}`))
    
    for (const post of newPosts) {
      const idx = getShortestColIndex()
      appendToColumn(idx, {
        key: `${post.source_site}-${post.id}`,
        component: markRaw(PostCard),
        props: { post },
      }, post)
    }
    
    placedCount = newVal.length
    setTimeout(observeNewCards, 100)
  }
})

// Watch for card size changes
watch(() => feed.cardSize, () => {
  const newCount = getColCount()
  if (newCount !== colCount.value) {
    colCount.value = newCount
    initColumns()
    placeNewPosts()
  }
})

// Watch loading state for skeletons
watch(() => props.skeletonCount, (count) => {
  if (count && count > 0) {
    addSkeletons(count)
  } else {
    removeSkeletons()
  }
})

function onResize() {
  const newCount = getColCount()
  if (newCount !== colCount.value) {
    colCount.value = newCount
    initColumns()
    placeNewPosts()
  }
}

// Impression tracking
const { createImpressionObserver } = useEventLogger()
let impressionTracker: ReturnType<typeof createImpressionObserver> | null = null

function observeNewCards() {
  if (!gridEl.value || !impressionTracker) return
  const cards = gridEl.value.querySelectorAll('.post-card:not([data-observed])')
  if (cards.length === 0) return

  // Build a fast lookup Map of props.posts in O(N)
  const postMap = new Map<string, Post>()
  for (const post of props.posts) {
    postMap.set(`${post.source_site}-${post.id}`, post)
  }

  cards.forEach((el) => {
    const key = (el as HTMLElement).closest('[data-post-key]')?.getAttribute('data-post-key') || ''
    const post = postMap.get(key)
    if (post) {
      impressionTracker!.observe(el as HTMLElement, post)
      el.setAttribute('data-observed', '1')
    }
  })
}

onMounted(() => {
  initColumns()
  placeNewPosts()
  window.addEventListener('resize', onResize)
  impressionTracker = createImpressionObserver()
  // Observe initially rendered cards after next tick
  setTimeout(observeNewCards, 100)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (impressionTracker) impressionTracker.disconnect()
})
</script>
