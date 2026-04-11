<template>
  <div id="toast-container">
    <div v-for="t in toastStore.toasts" :key="t.id"
         class="toast" :class="'toast-' + t.type"
         :style="{ animation: t.removing ? 'toastOut 0.3s forwards' : 'toastIn 0.3s forwards' }">
      <span>{{ t.icon }}</span>
      <span>{{ t.message }}</span>
    </div>
  </div>
</template>

<script setup>
import { useToastStore } from '../stores/toast.js'
const toastStore = useToastStore()
</script>
