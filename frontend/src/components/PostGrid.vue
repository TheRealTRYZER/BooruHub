<template>
  <div class="post-grid" ref="gridEl">
    <div v-for="(col, ci) in columns" :key="ci" class="post-column">
      <div v-for="item in col" :key="item.key" :data-post-key="item.key">
        <component :is="item.component" v-bind="item.props" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, markRaw } from 'vue'
import PostCard from './PostCard.vue'
import SkeletonCard from './SkeletonCard.vue'
import { useEventLogger } from '../composables/useEventLogger'
import type { Post } from '../types'

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
  if (w >= 1400) return 5
  if (w >= 1100) return 4
  if (w >= 768) return 3
  return 2
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

// Watch for new posts appended
watch(() => props.posts.length, () => {
  removeSkeletons()
  placeNewPosts()
  setTimeout(observeNewCards, 100)
})

// Watch loading state for skeletons
watch(() => props.skeletonCount, (count) => {
  if (count && count > 0) {
    addSkeletons(count)
  } else {
    removeSkeletons()
  }
})

// Full reset when posts array reference changes (new search)
watch(() => props.posts, (newVal, oldVal) => {
  if (newVal !== oldVal || newVal.length === 0) {
    initColumns()
    placeNewPosts()
  }
}, { flush: 'sync' })

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
