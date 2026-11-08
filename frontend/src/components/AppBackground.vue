<template>
  <div v-if="kind !== 'off'" class="app-bg" aria-hidden="true">
    <template v-if="kind === 'dots'">
      <div class="bg-dots"></div>
      <div class="bg-spot"></div>
    </template>
    <template v-else-if="kind === 'scan'">
      <div class="bg-scan"></div>
      <div class="bg-sweep"></div>
    </template>
    <template v-else-if="kind === 'rings'">
      <div class="bg-rings"></div>
    </template>
    <template v-else>
      <div class="bg-glow"></div>
      <span v-for="(s, i) in sparks" :key="i" class="bg-spark" :style="s"></span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useThemeStore } from '../stores/theme'

const theme = useThemeStore()
const kind = computed(() => theme.backgroundKind)

// Fixed table so the sparks look the same on every launch: x position, size (px),
// duration (s), delay (s), sideways drift (px).
const SPARK_TABLE: [number, number, number, number, number][] = [
  [5, 4, 11, 0, 24],
  [12, 5, 14, 3, -18],
  [20, 3, 10, 7, 30],
  [28, 4, 13, 1, -26],
  [36, 5, 12, 9, 16],
  [44, 3, 15, 4, -12],
  [52, 4, 10, 8, 28],
  [60, 5, 13, 2, -30],
  [68, 3, 11, 6, 20],
  [76, 4, 14, 5, -16],
  [84, 5, 12, 10, 22],
  [92, 3, 15, 7, -24],
  [16, 3, 12, 11, 14],
  [48, 4, 16, 13, -20],
  [72, 3, 13, 12, 18],
  [96, 4, 14, 9, -14],
]

const sparks = SPARK_TABLE.map(([x, s, dur, delay, drift]) => ({
  '--x': `${x}%`,
  '--s': `${s}px`,
  '--dur': `${dur}s`,
  '--delay': `-${delay}s`,
  '--drift': `${drift}px`,
}))
</script>
