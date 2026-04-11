<template>
  <div class="skeleton skeleton-card" :style="{ height: height + 'px' }"></div>
</template>

<script setup>
const height = 150 + Math.random() * 200
</script>
