<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="app-root">
    <OnboardingGuide />

    <transition name="toast">
      <div v-if="showStatusToast" class="status-toast" :class="statusToastType">
        <div class="toast-icon">{{ statusToastIcon }}</div>
        <div class="toast-content">
          <div class="toast-title">{{ statusToastTitle }}</div>
          <div class="toast-message">{{ statusToastMessage }}</div>
        </div>
        <button class="toast-close" @click="showStatusToast = false">×</button>
      </div>
    </transition>

    <SettingsView />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { initApi } from './composables/useApi'
import { useWebSocket } from './composables/useWebSocket'
import SettingsView from './views/SettingsView.vue'
import OnboardingGuide from './components/OnboardingGuide.vue'
import { onMounted } from 'vue'

const ws = useWebSocket()

const showStatusToast = ref(false)
const statusToastType = ref('info')
const statusToastTitle = ref('')
const statusToastMessage = ref('')
const statusToastIcon = ref('ℹ️')

ws.on('recording', (data: any) => {
  if (data.active) showToast('success', '开始录音', '请说话，停顿 1 秒自动识别')
  else showToast('info', '录音停止', '按 F9 或点击悬浮窗继续')
})
ws.on('error', (data: any) => showToast('error', '出错了', data.message || '操作失败，请重试'))
ws.on('asr_connected', (data: any) => {
  if (data.connected) showToast('success', 'ASR 已连接', '语音识别准备就绪')
})

function showToast(type: string, title: string, message: string) {
  statusToastType.value = type
  statusToastTitle.value = title
  statusToastMessage.value = message
  statusToastIcon.value = type === 'success' ? '✅' : type === 'error' ? '⚠️' : 'ℹ️'
  showStatusToast.value = true
  setTimeout(() => { showStatusToast.value = false }, 3000)
}

onMounted(async () => {
  await initApi()
  ws.connect()
})
</script>

<style>
.app-root { height: 100%; }

/* 状态提示 Toast（右上角，柔和材质） */
.status-toast {
  position: fixed; top: 16px; right: 16px; z-index: 10000;
  min-width: 280px; max-width: 380px;
  display: flex; align-items: flex-start; gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid var(--separator);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-pop);
}
.status-toast.success { border-left: 3px solid var(--green); }
.status-toast.error { border-left: 3px solid var(--red); }
.status-toast.info { border-left: 3px solid var(--accent); }
.toast-icon { font-size: 18px; flex-shrink: 0; line-height: 1.4; }
.toast-content { flex: 1; }
.toast-title { font-size: var(--text-subhead); font-weight: var(--weight-semibold); color: var(--label); }
.toast-message { font-size: var(--text-footnote); color: var(--label-secondary); margin-top: 2px; }
.toast-close {
  background: none; border: none; font-size: 20px; color: var(--label-tertiary);
  cursor: pointer; padding: 0; width: 22px; height: 22px; line-height: 1;
}
.toast-close:hover { color: var(--label); }

.toast-enter-active, .toast-leave-active { transition: all 0.28s cubic-bezier(0.32, 0.72, 0, 1); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(20px); }
</style>
