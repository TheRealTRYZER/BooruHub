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
  placedCount = 0
  skeletonKeys = []
}

function getShortestColIndex() {
  // Use item count as proxy for height to avoid DOM measurement during render
  let minIdx = 0
  let minLen = columns.value[0]?.length ?? 0
  for (let i = 1; i < columns.value.length; i++) {
    if ((columns.value[i]?.length ?? 0) < minLen) {
      minLen = columns.value[i].length
      minIdx = i
    }
  }
  return minIdx
}

function placeNewPosts() {
  const newPosts = props.posts.slice(placedCount)
  for (const post of newPosts) {
    const idx = getShortestColIndex()
    columns.value[idx].push({
      key: `${post.source_site}-${post.id}`,
      component: markRaw(PostCard),
      props: { post },
    })
    placedCount++
  }
}

function removeSkeletons() {
  for (const col of columns.value) {
    // Filter out skeletons
    const filtered = col.filter(item => !item.key.startsWith('sk-'))
    col.length = 0
    col.push(...filtered)
  }
  skeletonKeys = []
}

function addSkeletons(count: number) {
  removeSkeletons()
  for (let i = 0; i < count; i++) {
    const idx = i % colCount.value
    const key = `sk-${Date.now()}-${i}`
    columns.value[idx].push({
      key,
      component: markRaw(SkeletonCard),
      props: {},
    })
    skeletonKeys.push(key)
  }
}

let lastFirstPostKey = ''

// Watch for posts array changes (new search, scroll append, or duplicate removal)
watch(() => props.posts, (newVal) => {
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
      const filtered = col.filter(item => {
        if (item.key.startsWith('sk-')) return true // keep manual loading skeletons
        return activeKeys.has(item.key)
      })
      if (filtered.length !== col.length) {
        col.length = 0
        col.push(...filtered)
      }
    }

    // 3. Identify and place new posts that are not yet in columns in O(N + M) time
    const placedKeys = new Set(columns.value.flatMap(col => col.map(item => item.key)))
    const newPosts = newVal.filter(p => !placedKeys.has(`${p.source_site}-${p.id}`))
    
    for (const post of newPosts) {
      const idx = getShortestColIndex()
      columns.value[idx].push({
        key: `${post.source_site}-${post.id}`,
        component: markRaw(PostCard),
        props: { post },
      })
    }
    
    placedCount = newVal.length
    setTimeout(observeNewCards, 100)
  }
}, { deep: true })

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
