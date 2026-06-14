<template>
  <div id="toast-container">
    <div v-for="t in toastStore.toasts" :key="t.id"
         class="toast" :class="'toast-' + t.type"
         :style="{ animation: t.removing ? 'toastOut 0.3s forwards' : 'toastIn 0.3s forwards' }">
      <span>{{ t.icon }}</span>
      <span style="flex: 1;">{{ t.message }}</span>
      <button v-if="t.action" 
              class="btn btn-sm btn-secondary" 
              style="margin-left: 10px; padding: 2px 8px; font-size: 11px; background: rgba(255,255,255,0.15); border: none; color: #fff; cursor: pointer;"
              @click.stop="t.action.callback(); toastStore.remove(t.id)">
        {{ t.action.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToastStore } from '../stores/toast'
const toastStore = useToastStore()
</script>
