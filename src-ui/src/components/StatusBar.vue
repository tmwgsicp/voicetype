<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <section class="unified-card status-bar">
    <div class="status-left">
      <div class="status-item">
        <span :class="['status-dot', { active: isRecording }]"></span>
        <span class="status-label">{{ isRecording ? '录音中' : '待命' }}</span>
      </div>
      <div class="status-divider"></div>
      <div class="status-item">
        <span class="status-meta">场景</span>
        <span>{{ scene }}</span>
      </div>
      <div class="status-divider"></div>
      <div class="status-item">
        <span class="status-meta">窗口</span>
        <span class="text-truncate">{{ activeWindow }}</span>
      </div>
    </div>
    <button :class="['btn', 'btn-primary', 'btn-record', { recording: isRecording }]" @click="onToggle">
      <svg v-if="!isRecording" class="btn-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
      </svg>
      <svg v-else class="btn-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <rect x="6" y="6" width="12" height="12" rx="2"/>
      </svg>
      <span>{{ isRecording ? '停止' : '开始录音' }}</span>
    </button>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  isRecording: boolean
  scene: string
  activeWindow: string
}>()

const emit = defineEmits<{
  toggle: []
}>()

function onToggle() {
  emit('toggle')
}
</script>

<style scoped>
.status-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-md) var(--space-lg);
}
.status-left { display: flex; align-items: center; gap: var(--space-md); flex-wrap: wrap; flex: 1; min-width: 0; }
.status-item { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-sm); white-space: nowrap; }
.status-meta { color: var(--text-muted); font-size: var(--font-xs); }
.status-divider { width: 1px; height: 16px; background: var(--border-light); }
.status-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--border-base); transition: background var(--duration-normal) var(--ease-in-out); flex-shrink: 0;
}
.status-dot.active { background: var(--error-color); animation: pulse 1.5s infinite; }
.status-label { font-weight: var(--font-semibold); }
.text-truncate { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.btn {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-base); border-radius: var(--radius-base);
  background: var(--bg-primary); cursor: pointer; font-size: var(--font-sm);
  transition: all var(--duration-fast) var(--ease-in-out); white-space: nowrap;
}
.btn:hover { border-color: var(--primary-color); color: var(--primary-color); }
.btn-primary { background: var(--primary-color); color: white; border-color: var(--primary-color); }
.btn-primary:hover { background: #40a9ff; border-color: #40a9ff; color: white; }
.btn-record { display: inline-flex; align-items: center; gap: var(--space-sm); font-weight: var(--font-semibold); flex-shrink: 0; }
.btn-record.recording { background: var(--error-color); border-color: var(--error-color); }
.btn-record.recording:hover { background: #ff7875; border-color: #ff7875; }
.btn-icon { flex-shrink: 0; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
