<template>
  <div v-if="relationshipPosts.length > 1" class="lightbox-relationship-panel post-relationship-panel" @click.stop>
    <div class="sidebar-title post-relationship-header">
      {{ displayedPost.parent_id ? lang.t('post_has_parent') : lang.t('post_has_children') }}
    </div>
    <div class="post-relationship-thumbs vertical-thumbs">
      <img 
        v-for="p in relationshipPosts" 
        :key="p.source_site + ':' + p.id"
        :src="getPostThumbnail(p)"
        class="post-relationship-thumb"
        :class="{ active: String(p.id) === String(displayedPost.id) }"
        :alt="'Thumbnail ' + p.id"
        :style="{ aspectRatio: p.width && p.height ? `${p.width} / ${p.height}` : '1' }"
        @click="$emit('navigate', p)"
      >
    </div>
  </div>
</template>

<script setup lang="ts">
import { useLangStore } from '../stores/lang'
import { sanitizeUrl } from '../utils/security'
import type { Post } from '../types'

defineProps<{
  displayedPost: Post
  relationshipPosts: Post[]
}>()

defineEmits<{
  (e: 'navigate', post: Post): void
}>()

const lang = useLangStore()

function getPostThumbnail(p: Post) {
  const videoExtensions = ['mp4', 'webm', 'm4v', 'mov', 'mkv', 'swf', 'ogv']
  const isVideoExt = (url: string) => {
    if (!url) return false
    const cleanUrl = (url.split('?')[0] ?? '').toLowerCase()
    return videoExtensions.some(ext => cleanUrl.endsWith('.' + ext))
  }
  
  let url = ''
  if (p.preview_url && !isVideoExt(p.preview_url)) url = p.preview_url
  else if (p.sample_url && !isVideoExt(p.sample_url)) url = p.sample_url
  else if (p.file_url && !isVideoExt(p.file_url)) url = p.file_url
  else {
    const fallback = p.preview_url || p.sample_url || p.file_url || ''
    url = isVideoExt(fallback) ? '' : fallback
  }
  return sanitizeUrl(url)
}
</script>

<style scoped>
.lightbox-relationship-panel {
  position: absolute;
  left: 24px;
  top: 80px;
  bottom: 24px;
  width: 300px;
  background: rgba(15, 15, 20, 0.55);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.vertical-thumbs {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding-right: 4px;
}
.vertical-thumbs::-webkit-scrollbar { width: 4px; }
.vertical-thumbs::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 2px; }

.post-relationship-thumb {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 8px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}
.post-relationship-thumb:hover {
  transform: scale(1.04);
  border-color: rgba(255, 255, 255, 0.4);
}
.post-relationship-thumb.active {
  border-color: var(--accent);
  box-shadow: 0 0 10px var(--accent);
}

@media (max-width: 768px) {
  .lightbox-relationship-panel {
    position: static;
    width: 95vw;
    max-height: 150px;
    padding: 12px;
    gap: 12px;
  }
  .vertical-thumbs {
    display: flex;
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
    gap: 12px;
  }
  .post-relationship-thumb {
    width: 70px;
    height: 70px;
    flex-shrink: 0;
  }
}
</style>
