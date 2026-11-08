<template>
  <div id="toast-container">
    <div v-for="t in toastStore.toasts" :key="t.id"
         class="toast" :class="'toast-' + t.type"
         :style="{ animation: t.removing ? 'toastOut 0.3s forwards' : 'toastIn 0.3s forwards' }">
      <AppIcon :name="t.type === 'success' ? 'check' : t.type === 'error' ? 'close' : 'info'" :size="16" :stroke-width="2.2" />
      <span style="flex: 1;">{{ t.message }}</span>
      <button v-if="t.action" 
              class="btn btn-sm btn-secondary" 
              style="margin-left: 10px; padding: 6px 12px; font-size: 12px; min-height: 36px;"
              @click.stop="t.action.callback(); toastStore.remove(t.id)">
        {{ t.action.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToastStore } from '../stores/toast'
import AppIcon from './AppIcon.vue'
const toastStore = useToastStore()
</script>
