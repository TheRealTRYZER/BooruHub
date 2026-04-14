<template>
  <span class="tag-chip" :title="tag" @click.stop="$router.push({ name: 'feed', query: { tags: tag } })">
    {{ tag.replace(/_/g, ' ') }}
  </span>
</template>

<script setup lang="ts">
defineProps<{
  tag: string
}>()
</script>
