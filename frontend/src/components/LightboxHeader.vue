<template>
  <div class="lightbox-header">
    <div class="lightbox-header-left">
      <span v-for="site in allSites" 
            :key="site" 
            class="lightbox-site-badge" 
            :class="[site, { 'interactive-badge': allSites.length > 1, 'active-site': allSites.length > 1 && activeSite === site }]"
            :title="allSites.length > 1 ? lang.t('switch_version', { site }) : ''"
            :role="allSites.length > 1 ? 'button' : undefined"
            :tabindex="allSites.length > 1 ? 0 : undefined"
            @click="allSites.length > 1 ? $emit('switchSite', site) : null"
            @keydown.enter.stop.prevent="allSites.length > 1 ? $emit('switchSite', site) : null"
            @keydown.space.stop.prevent="allSites.length > 1 ? $emit('switchSite', site) : null">
        {{ site === activePost.source_site ? site : '+ ' + site }}
      </span>
      <span class="lightbox-id">#{{ displayedPost.id }}</span>
      <span class="lightbox-rating" :class="ratingClass" :aria-label="'Rating: ' + ratingLabel">{{ ratingLabel }}</span>
    </div>
    <div class="lightbox-header-right">
      <span v-if="displayedPost.score !== undefined" class="lightbox-score">★ {{ displayedPost.score }}</span>
      <span class="lightbox-resolution">{{ displayedPost.width }}x{{ displayedPost.height }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useLangStore } from '../stores/lang'
import { RATING_MAP, RATING_LABELS } from '../types'
import type { Post, RatingClass, SiteName } from '../types'

const props = defineProps<{
  displayedPost: Post
  activePost: Post
  allSites: SiteName[]
  activeSite: SiteName
}>()

defineEmits<{
  (e: 'switchSite', site: SiteName): void
}>()

const lang = useLangStore()

const ratingClass = computed<RatingClass>(() => RATING_MAP[(props.displayedPost.rating || '').toLowerCase()] || 'unknown')
const ratingLabel = computed(() => RATING_LABELS[ratingClass.value] || '?')
</script>

<style scoped>
.lightbox-header {
  position: absolute;
  top: 20px; left: 24px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 10px 18px;
  border-radius: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  color: #fff;
  z-index: 999;
  font-size: 13px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
}
.lightbox-header-left, .lightbox-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lightbox-site-badge {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
}
.lightbox-site-badge.danbooru { background: var(--danbooru); color: #fff; }
.lightbox-site-badge.e621 { background: var(--e621); color: #fff; }
.lightbox-site-badge.rule34 { background: var(--rule34); color: #222; }

.lightbox-site-badge.interactive-badge {
  cursor: pointer;
  transition: all 0.15s ease;
}
.lightbox-site-badge.interactive-badge:hover {
  transform: scale(1.08);
  filter: brightness(1.2);
}
.lightbox-site-badge.interactive-badge.active-site {
  box-shadow: 0 0 0 2px rgba(15, 15, 20, 0.6), 0 0 0 3px var(--accent);
  transform: scale(1.1);
  font-weight: 800;
  z-index: 2;
}

.lightbox-rating {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}
.lightbox-rating.safe { background: rgba(52, 211, 153, 0.15); color: #6ee7b7; border: 1px solid rgba(52, 211, 153, 0.3); }
.lightbox-rating.questionable { background: rgba(251, 146, 60, 0.15); color: #fdba74; border: 1px solid rgba(251, 146, 60, 0.3); }
.lightbox-rating.explicit { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
.lightbox-rating.unknown { background: rgba(156, 163, 175, 0.15); color: #d1d5db; border: 1px solid rgba(156, 163, 175, 0.3); }

.lightbox-score {
  color: #fbbf24;
  font-weight: 700;
}
.lightbox-resolution {
  color: var(--text-muted);
}

@media (max-width: 768px) {
  .lightbox-header {
    top: 12px; left: 12px;
    padding: 6px 12px;
    font-size: 11px;
    gap: 12px;
  }
}
</style>
