<template>
  <svg class="app-icon" :width="size" :height="size" viewBox="0 0 24 24" :fill="filled ? 'currentColor' : 'none'"
       stroke="currentColor" :stroke-width="strokeWidth" stroke-linecap="round" stroke-linejoin="round"
       aria-hidden="true" focusable="false">
    <template v-if="name === 'logo'">
      <path d="M12 2.5 20.2 7.25v9.5L12 21.5l-8.2-4.75v-9.5z" />
    </template>
    <template v-else-if="name === 'home'">
      <path d="M3.5 11 12 4l8.5 7" /><path d="M5.5 9.5V20h13V9.5" /><path d="M10 20v-6h4v6" />
    </template>
    <template v-else-if="name === 'guides'">
      <path d="M4.5 4.5A1.5 1.5 0 0 1 6 3h12v15H6a1.5 1.5 0 0 0-1.5 1.5z" /><path d="M4.5 19.5A1.5 1.5 0 0 0 6 21h12v-3" /><path d="M9 8h6" />
    </template>
    <template v-else-if="name === 'heart'">
      <path d="M12 20.5s-8-4.7-8-10.6A4.4 4.4 0 0 1 12 7.4a4.4 4.4 0 0 1 8 2.5c0 5.9-8 10.6-8 10.6z" />
    </template>
    <template v-else-if="name === 'heart-broken'">
      <path d="M12 20.5s-8-4.7-8-10.6A4.4 4.4 0 0 1 12 7.4a4.4 4.4 0 0 1 8 2.5c0 5.9-8 10.6-8 10.6z" /><path d="m12 7.4-1.5 3.6 3 2-1.5 3.5" />
    </template>
    <template v-else-if="name === 'bookmark'">
      <path d="M6.5 3.5h11v17L12 16.5l-5.5 4z" />
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7" />
    </template>
    <template v-else-if="name === 'moon'">
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z" />
    </template>
    <template v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
    </template>
    <template v-else-if="name === 'monitor'">
      <rect x="3" y="4" width="18" height="12" rx="1.5" /><path d="M8 20h8M12 16v4" />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" />
    </template>
    <template v-else-if="name === 'split'">
      <path d="M4 6h4l8 12h4" /><path d="M4 18h4l2.5-3.8" /><path d="M13.5 9.8 16 6h4" /><path d="m18 4 2 2-2 2M18 16l2 2-2 2" />
    </template>
    <template v-else-if="name === 'columns'">
      <rect x="3.5" y="4" width="17" height="16" rx="2" /><path d="M9.2 4v16M14.8 4v16" />
    </template>
    <template v-else-if="name === 'image'">
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="m4 17 5-4.5 3.5 3 3-2.5 4.5 4" />
    </template>
    <template v-else-if="name === 'play'">
      <path d="M8 5.5v13l10.5-6.5z" />
    </template>
    <template v-else-if="name === 'thumbs-down'">
      <path d="M17 14V4h3v10z" /><path d="M17 14l-3.5 6.2c-1.6 0-2.5-1.2-2.1-2.7L12 14H6.4a2 2 0 0 1-2-2.4l1.2-6A2 2 0 0 1 7.5 4H17" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="M6 6l12 12M18 6 6 18" />
    </template>
    <template v-else-if="name === 'arrow-left'">
      <path d="M19 12H5M11 6l-6 6 6 6" />
    </template>
    <template v-else-if="name === 'arrow-right'">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </template>
    <template v-else-if="name === 'download'">
      <path d="M12 4v11M7 11l5 5 5-5M5 20h14" />
    </template>
    <template v-else-if="name === 'share'">
      <path d="M12 15V3.5M7.5 8 12 3.5 16.5 8" /><path d="M5 12v7.5h14V12" />
    </template>
    <template v-else-if="name === 'link'">
      <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1" />
    </template>
    <template v-else-if="name === 'lock'">
      <rect x="5" y="10.5" width="14" height="10" rx="2" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </template>
    <template v-else-if="name === 'star'">
      <path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 16.9 6.8 19.7l1-5.9-4.3-4.1 5.9-.8z" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" />
    </template>
    <template v-else-if="name === 'chevron-down'">
      <path d="m6 9.5 6 6 6-6" />
    </template>
    <template v-else-if="name === 'check'">
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </template>
    <template v-else-if="name === 'alert'">
      <path d="M12 3.5 21.5 20h-19z" /><path d="M12 10v4.5M12 17.2v.1" />
    </template>
    <template v-else-if="name === 'info'">
      <circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.5M12 7.8v.1" />
    </template>
    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8.5" r="3.7" /><path d="M4.5 20.5c.8-4 3.7-6 7.5-6s6.7 2 7.5 6" />
    </template>
    <template v-else-if="name === 'key'">
      <circle cx="8" cy="15" r="4" /><path d="m11 12 8.5-8.5M16 7l3 3" />
    </template>
    <template v-else-if="name === 'shield'">
      <path d="M12 3 4.5 6v5.5c0 4.5 3.1 8 7.5 9.5 4.4-1.5 7.5-5 7.5-9.5V6z" />
    </template>
    <template v-else-if="name === 'save'">
      <path d="M5 4.5h11l3 3V19.5H5z" /><path d="M8 4.5v5h7v-5M8 19.5v-6h8v6" />
    </template>
    <template v-else-if="name === 'tag'">
      <path d="M3.5 12.2V4.5h7.7l9.3 9.3a1.5 1.5 0 0 1 0 2.1l-5.6 5.6a1.5 1.5 0 0 1-2.1 0z" /><circle cx="8" cy="9" r="1" />
    </template>
    <template v-else-if="name === 'ban'">
      <circle cx="12" cy="12" r="8.5" /><path d="m6 6 12 12" />
    </template>
    <template v-else-if="name === 'edit'">
      <path d="M4 20h4L19 9l-4-4L4 16z" /><path d="m13.5 6.5 4 4" />
    </template>
    <template v-else-if="name === 'sparkle'">
      <path d="M12 3.5v4M12 16.5v4M3.5 12h4M16.5 12h4" /><path d="m7 7 2 2M15 15l2 2M17 7l-2 2M9 15l-2 2" />
    </template>
  </svg>
</template>

<script setup lang="ts">
export type IconName =
  | 'logo' | 'home' | 'guides' | 'heart' | 'heart-broken' | 'bookmark' | 'settings'
  | 'moon' | 'sun' | 'monitor' | 'search' | 'split' | 'columns' | 'image' | 'play'
  | 'thumbs-down' | 'close' | 'arrow-left' | 'arrow-right' | 'download' | 'share' | 'link'
  | 'lock' | 'star' | 'clock' | 'chevron-down' | 'check' | 'alert' | 'info' | 'user'
  | 'key' | 'shield' | 'save' | 'tag' | 'ban' | 'edit' | 'sparkle'

withDefaults(defineProps<{
  name: IconName
  size?: number | string
  strokeWidth?: number | string
  filled?: boolean
}>(), { size: 18, strokeWidth: 2.2, filled: false })
</script>

<style>
.app-icon { flex: none; display: inline-block; vertical-align: middle; }
</style>
