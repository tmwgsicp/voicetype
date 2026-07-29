<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
  轻量线性图标（stroke, currentColor），观感接近 SF Symbols，不用 emoji。
-->
<template>
  <svg viewBox="0 0 24 24" width="17" height="17" fill="none"
       stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
    <path v-for="(d, i) in paths" :key="i" :d="d" />
    <template v-if="name === 'stats'">
      <line x1="6" y1="20" x2="6" y2="13" /><line x1="12" y1="20" x2="12" y2="8" /><line x1="18" y1="20" x2="18" y2="11" />
    </template>
    <circle v-if="name === 'voiceprint'" cx="12" cy="8" r="3.2" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ name: string }>()
const MAP: Record<string, string[]> = {
  overview: ['M4 13h7V4H4z', 'M13 20h7v-9h-7z', 'M4 20h7v-4H4z', 'M13 8h7V4h-7z'],
  api: ['M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
        'M19.4 13a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 6.6 19l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 13.4H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 6.6l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 11 3.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z'],
  general: ['M3 6h18v12H3z', 'M7 10h.01M11 10h.01M15 10h.01M7 14h10'],
  scenes: ['M3 8l9-4 9 4-9 4z', 'M3 12l9 4 9-4', 'M3 16l9 4 9-4'],
  rules: ['M8 6h13M8 12h13M8 18h13', 'M3 6h.01M3 12h.01M3 18h.01'],
  voiceprint: ['M4 20a8 8 0 0 1 16 0'],
  history: ['M12 7v5l3 2', 'M3.5 12a8.5 8.5 0 1 0 2.5-6', 'M3 4v4h4'],
  lock: ['M6 11h12v9H6z', 'M8.5 11V7.5a3.5 3.5 0 0 1 7 0V11'],
  sparkle: ['M12 3l1.7 4.6L18.5 9l-4.8 1.4L12 15l-1.7-4.6L5.5 9l4.8-1.4z'],
  stats: [],
}
const paths = computed(() => MAP[props.name] || [])
</script>
