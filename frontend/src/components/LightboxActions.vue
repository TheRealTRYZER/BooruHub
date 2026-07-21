<template>
  <div class="lightbox-actions-panel">
    <button class="btn btn-glass" :class="{ 'btn-fav-active': isFav }" @click="$emit('toggleFav')">
      {{ isFav ? '❤️ ' + lang.t('nav_favorites') : '🤍 ' + lang.t('nav_favorites') }}
    </button>
    <button class="btn btn-glass" :class="{ 'btn-dislike-active': isDisliked }" @click="$emit('toggleDislike')">
      👎
    </button>
    <button class="btn btn-glass" @click="$emit('download')">
      ⬇️ {{ lang.t('download') }}
    </button>
    <button class="btn btn-glass" @click="$emit('openOriginal')">
      🔗 {{ lang.t('original') }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { useLangStore } from '../stores/lang'

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
  gap: 10px;
  background: rgba(15, 15, 20, 0.55);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px 20px;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
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
  background: rgba(239, 68, 68, 0.2) !important;
  border-color: rgba(239, 68, 68, 0.4) !important;
  color: #ef4444 !important;
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
}

.btn-dislike-active {
  background: rgba(249, 115, 22, 0.2) !important;
  border-color: rgba(249, 115, 22, 0.4) !important;
  color: #f97316 !important;
}

@media (max-width: 768px) {
  .lightbox-actions-panel {
    position: absolute;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    width: auto;
    max-width: 95vw;
    padding: 8px 12px;
    margin-top: 0;
  }
  .lightbox-actions-panel .btn {
    padding: 6px 10px;
    font-size: 11px;
  }
}
</style>
