<template>
  <div class="post-grid" ref="gridEl" :style="{ '--card-size': feed.cardSize + 'px' }">
    <div v-for="(col, ci) in columns" :key="ci" class="post-column">
      <div v-for="item in col" :key="item.key" :data-post-key="item.key">
        <component :is="item.component" v-bind="item.props" />
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
import type { Post } from '../types'

const feed = useFeedStore()

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
  const availableWidth = w - 40
  return Math.max(1, Math.min(20, Math.floor(availableWidth / feed.cardSize)))
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

// Watch for posts array changes (new search, scroll append, or duplicate removal)
watch(() => props.posts, (newVal, oldVal) => {
  const isNewSearch = !oldVal || newVal.length === 0 || oldVal.length === 0 ||
                      (newVal[0] && oldVal[0] && `${newVal[0].source_site}-${newVal[0].id}` !== `${oldVal[0].source_site}-${oldVal[0].id}`)
  
  removeSkeletons()

  if (isNewSearch) {
    initColumns()
    placeNewPosts()
    setTimeout(observeNewCards, 100)
  } else {
    // Incremental update (duplicate deletion or infinite scroll append)
    // 1. Remove cards that are no longer in props.posts
    for (const col of columns.value) {
      const filtered = col.filter(item => {
        if (item.key.startsWith('sk-')) return true // keep manual loading skeletons
        const [site, id] = item.key.split('-')
        return newVal.some(p => String(p.id) === id && p.source_site === site)
      })
      if (filtered.length !== col.length) {
        col.length = 0
        col.push(...filtered)
      }
    }

    // 2. Identify and place new posts that are not yet in columns
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
}, { deep: true, flush: 'sync' })

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
  cards.forEach((el) => {
    const key = (el as HTMLElement).closest('[data-post-key]')?.getAttribute('data-post-key') || ''
    // Find the post by parsing the key (format: site-id)
    const sep = key.indexOf('-')
    if (sep > 0) {
      const site = key.substring(0, sep)
      const id = key.substring(sep + 1)
      const post = props.posts.find(p => String(p.id) === id && p.source_site === site)
      if (post) {
        impressionTracker!.observe(el as HTMLElement, post)
        el.setAttribute('data-observed', '1')
      }
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
