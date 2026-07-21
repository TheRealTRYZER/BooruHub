<template>
  <div class="lightbox-sidebar">
    <h3 class="sidebar-title">{{ lang.t('tags_count') }} ({{ displayedPost.tags?.length || 0 }})</h3>
    <div class="lightbox-tags-list">
      <div v-for="group in groupedTags" :key="group.key" class="lightbox-tag-group">
        <div class="lightbox-tag-group-title" :class="group.key">
          {{ group.title }} ({{ group.allTags.length }})
        </div>
        <div class="lightbox-tag-group-chips">
          <span v-for="tag in group.allTags" 
                :key="tag" 
                class="tag-chip" 
                :class="group.key"
                role="button"
                tabindex="0"
                @click="$emit('searchTag', tag)"
                @keydown.enter.prevent="$emit('searchTag', tag)"
                @keydown.space.prevent="$emit('searchTag', tag)">
            {{ tag.replace(/_/g, ' ') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useLangStore } from '../stores/lang'
import type { Post } from '../types'

const props = defineProps<{
  displayedPost: Post
}>()

defineEmits<{
  (e: 'searchTag', tag: string): void
}>()

const lang = useLangStore()

// Group post tags dynamically by category
const groupedTags = computed(() => {
  const post = props.displayedPost
  if (!post || !post.tags) return []
  
  const categoriesOrder = ['artist', 'character', 'copyright', 'species', 'general', 'metadata', 'lore', 'invalid']
  const groups: Record<string, string[]> = {}
  for (const cat of categoriesOrder) {
    groups[cat] = []
  }
  
  const uncategorizedKey = 'general'
  
  for (const tag of post.tags) {
    const cat = post.tags_metadata?.[tag] || uncategorizedKey
    if (!groups[cat]) {
      groups[cat] = []
    }
    groups[cat].push(tag)
  }
  
  const categoryTitles: Record<string, string> = {
    artist: '👤 Artists',
    character: '🎭 Characters',
    copyright: '📚 Copyrights',
    species: '🐾 Species',
    general: '🏷️ General Tags',
    metadata: '⚙️ Metadata',
    lore: '📜 Lore',
    invalid: '❌ Invalid'
  }
  
  return categoriesOrder
    .map(cat => {
      const allTags = groups[cat] || []
      return {
        key: cat,
        title: categoryTitles[cat] || cat,
        allTags
      }
    })
    .filter(g => g.allTags.length > 0)
})
</script>

<style scoped>
.lightbox-sidebar {
  position: absolute;
  right: 24px;
  top: 80px;
  bottom: 24px;
  width: 300px;
  background: rgba(15, 15, 20, 0.55);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 999;
}

.sidebar-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 8px;
}

.lightbox-tags-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  flex: 1;
  padding-right: 4px;
}
.lightbox-tags-list::-webkit-scrollbar {
  width: 4px;
}
.lightbox-tags-list::-webkit-scrollbar-track {
  background: transparent;
}
.lightbox-tags-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}
.lightbox-tags-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.lightbox-tag-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.lightbox-tag-group-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 2px;
  opacity: 0.85;
  user-select: none;
}
.lightbox-tag-group-title.artist { color: #f43f5e; }
.lightbox-tag-group-title.character { color: #34d399; }
.lightbox-tag-group-title.copyright { color: #a78bfa; }
.lightbox-tag-group-title.species { color: #fb923c; }
.lightbox-tag-group-title.general { color: #38bdf8; }
.lightbox-tag-group-title.metadata { color: #fbbf24; }
.lightbox-tag-group-title.lore, .lightbox-tag-group-title.invalid { color: #9ca3af; }

.lightbox-tag-group-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lightbox-sidebar .tag-chip {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 8px;
  display: inline-block;
  line-height: 1.2;
}

.lightbox-tag-more {
  font-size: 11px;
  color: var(--text-muted);
  padding: 3px 4px;
}

@media (max-width: 768px) {
  .lightbox-sidebar {
    position: static;
    width: 95vw;
    padding: 12px;
    margin-top: 16px;
    margin-bottom: 24px;
  }
  .sidebar-title {
    font-size: 13px;
    padding-bottom: 4px;
  }
}
</style>
