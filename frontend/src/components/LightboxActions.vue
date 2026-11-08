<template>
  <div class="lightbox-actions-panel">
    <button class="btn btn-glass" :class="{ 'btn-fav-active': isFav }" @click="$emit('toggleFav')">
      <AppIcon name="heart" :size="16" :filled="isFav" />
      <span>{{ lang.t('nav_favorites') }}</span>
    </button>
    <button class="btn btn-glass" :class="{ 'btn-dislike-active': isDisliked }" @click="$emit('toggleDislike')"
            :title="lang.t('dislikes_tab')" :aria-label="lang.t('dislikes_tab')">
      <AppIcon name="thumbs-down" :size="16" :filled="isDisliked" />
    </button>
    <button class="btn btn-glass" @click="$emit('download')">
      <AppIcon name="download" :size="16" />
      <span>{{ lang.t('download') }}</span>
    </button>
    <button class="btn btn-glass" @click="$emit('openOriginal')">
      <AppIcon name="link" :size="16" />
      <span>{{ lang.t('original') }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { useLangStore } from '../stores/lang'
import AppIcon from './AppIcon.vue'

defineProps<{
  isFav: boolean
  isDisliked: boolean
}>()

defineEmits<{
  (e: 'toggleFav'): void
  (e: 'toggleDislike'): void
  (e: 'download'): void
  (e: 'openOriginal'): void
}>()

const lang = useLangStore()
</script>

<style scoped>
.lightbox-actions-panel {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  /* With left: 50% the shrink-to-fit width is capped at half the overlay, so the
     buttons used to spill out of the panel; size it to its content instead. */
  width: max-content;
  max-width: calc(100% - 24px);
  gap: 10px;
  background: rgba(0, 0, 0, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.12);
  padding: 12px 20px;
  border-radius: var(--border-radius-lg);
  z-index: 999;
}

.btn-glass {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #fff;
  transition: all 0.2s ease;
  font-size: 12px;
  font-weight: 600;
}
.btn-glass:hover {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.2);
}

.btn-fav-active {
  border-color: var(--rating-explicit) !important;
  color: var(--rating-explicit) !important;
}

.btn-dislike-active {
  border-color: var(--rating-questionable) !important;
  color: var(--rating-questionable) !important;
}

@media (max-width: 768px) {
  .lightbox-actions-panel {
    position: absolute;
    bottom: calc(12px + env(safe-area-inset-bottom, 0px));
    left: 50%;
    transform: translateX(-50%);
    width: max-content;
    max-width: calc(100% - 16px);
    gap: 6px;
    padding: 8px 12px;
    margin-top: 0;
  }
  .lightbox-actions-panel .btn {
    padding: 6px 10px;
    font-size: 11px;
  }
}
</style>
