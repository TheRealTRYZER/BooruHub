<template>
  <div class="post-grid" ref="gridEl">
    <div v-for="(col, ci) in columns" :key="ci" class="post-column">
      <component v-for="item in col" :key="item.key" :is="item.component" v-bind="item.props" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, markRaw } from 'vue'
import PostCard from './PostCard.vue'
import SkeletonCard from './SkeletonCard.vue'

const props = defineProps({
  posts: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  skeletonCount: { type: Number, default: 0 },
})

const gridEl = ref(null)
const colCount = ref(getColCount())
const columns = ref([])

// Track all items placed so we can append incrementally
let placedCount = 0
let skeletonKeys = []

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

function addSkeletons(count) {
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
})

// Watch loading state for skeletons
watch(() => props.skeletonCount, (count) => {
  if (count > 0) {
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

onMounted(() => {
  initColumns()
  placeNewPosts()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})
</script>
