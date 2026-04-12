<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="container">
    <!-- 首次启动引导 -->
    <OnboardingGuide />
    
    <!-- 实时状态提示 -->
    <div class="status-toast" v-if="showStatusToast" :class="statusToastType">
      <div class="toast-icon">{{ statusToastIcon }}</div>
      <div class="toast-content">
        <div class="toast-title">{{ statusToastTitle }}</div>
        <div class="toast-message">{{ statusToastMessage }}</div>
      </div>
      <button class="toast-close" @click="showStatusToast = false">×</button>
    </div>
    
    <header>
      <div class="header-top">
        <h1>VoiceType</h1>
        <a class="github-link" href="https://github.com/tmwgsicp/voicetype" target="_blank" rel="noopener">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" style="color:#fa8c16"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          <span>Star</span>
        </a>
      </div>
      <p class="subtitle">AI 语音输入，适用于任何场景</p>
      
      <!-- 快速提示 -->
      <div class="quick-tips">
        <div class="tip-item">
          <span class="tip-icon">🎙️</span>
          <span>按 <kbd>F9</kbd> 开始录音</span>
        </div>
        <div class="tip-item">
          <span class="tip-icon">⏸️</span>
          <span>停顿 1 秒自动识别</span>
        </div>
        <div class="tip-item">
          <span class="tip-icon">✨</span>
          <span>AI 自动优化文本</span>
        </div>
      </div>
    </header>

    <SettingsView v-if="currentTab === 'settings'" />

    <footer>
      <p>
        VoiceType v0.1.0 &middot;
        <a href="https://github.com/tmwgsicp/voicetype" target="_blank">GitHub</a> &middot;
        <a href="https://github.com/tmwgsicp/voicetype/issues" target="_blank">反馈</a> &middot;
        AGPL-3.0
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { initApi } from './composables/useApi'
import { useWebSocket } from './composables/useWebSocket'
import SettingsView from './views/SettingsView.vue'
import OnboardingGuide from './components/OnboardingGuide.vue'

const currentTab = ref('settings')
const ws = useWebSocket()

// 状态提示
const showStatusToast = ref(false)
const statusToastType = ref('info')
const statusToastTitle = ref('')
const statusToastMessage = ref('')
const statusToastIcon = ref('ℹ️')

// WebSocket 消息监听
ws.on('recording', (data: any) => {
  if (data.active) {
    showToast('success', '🎤 开始录音', '请说话，停顿 1 秒自动识别')
  } else {
    showToast('info', '⏸️ 录音停止', '按 F9 或点击悬浮窗继续')
  }
})

ws.on('error', (data: any) => {
  showToast('error', '❌ 错误', data.message || '操作失败，请重试')
})

ws.on('asr_connected', (data: any) => {
  if (data.connected) {
    showToast('success', '✅ ASR 已连接', '语音识别服务准备就绪')
  }
})

function showToast(type: string, title: string, message: string) {
  statusToastType.value = type
  statusToastTitle.value = title
  statusToastMessage.value = message
  statusToastIcon.value = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'
  showStatusToast.value = true
  
  // 3秒后自动关闭
  setTimeout(() => {
    showStatusToast.value = false
  }, 3000)
}

onMounted(async () => {
  await initApi()
  ws.connect()
})
</script>

<style>
:root {
  --primary-color: #1890ff;
  --success-color: #52c41a;
  --warning-color: #fa8c16;
  --error-color: #ff4d4f;
  --text-primary: #262626;
  --text-secondary: #595959;
  --text-muted: #8c8c8c;
  --bg-primary: #ffffff;
  --bg-secondary: #fafafa;
  --bg-hover: #f5f5f5;
  --border-light: #f0f0f0;
  --border-base: #d9d9d9;
  --shadow-light: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-base: 0 4px 12px rgba(0, 0, 0, 0.08);
  --radius-small: 4px;
  --radius-base: 8px;
  --radius-large: 12px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --font-xs: 12px;
  --font-sm: 14px;
  --font-base: 16px;
  --font-lg: 20px;
  --font-xl: 24px;
  --font-regular: 400;
  --font-semibold: 600;
  --font-bold: 700;
  --leading-normal: 1.6;
  --width-wide: 1400px;
  --duration-fast: 200ms;
  --duration-normal: 300ms;
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg-secondary);
  color: var(--text-primary);
  line-height: var(--leading-normal);
  font-size: var(--font-sm);
}

/* 全局按钮样式 */
.btn {
  padding: var(--space-sm) var(--space-lg);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
  box-shadow: var(--shadow-light);
}

.btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
  box-shadow: var(--shadow-base);
}

.btn-primary {
  background: var(--primary-color);
  color: white !important;
  border-color: var(--primary-color);
}

.btn-primary:hover {
  background: #40a9ff;
  border-color: #40a9ff;
}

.btn-sm {
  padding: 6px var(--space-md);
  font-size: var(--font-xs);
}

.btn-danger {
  background: var(--error-color);
  color: white !important;
  border-color: var(--error-color);
}

.btn-danger:hover {
  background: #ff7875;
  border-color: #ff7875;
}

.badge {
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-small);
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
}

.badge-primary {
  background: #e6f7ff;
  color: var(--primary-color);
}

.badge-success {
  background: #f6ffed;
  color: var(--success-color);
}

.badge-warning {
  background: #fff7e6;
  color: var(--warning-color);
}

.container {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-lg) var(--space-md);
}

header { text-align: center; margin-bottom: var(--space-lg); }
.header-top { display: flex; align-items: center; justify-content: center; gap: var(--space-md); }
header h1 { font-size: var(--font-xl); font-weight: 700; letter-spacing: -0.5px; }
.subtitle { font-size: var(--font-sm); color: var(--text-secondary); margin-top: var(--space-xs); }

.github-link {
  display: inline-flex; align-items: center; gap: var(--space-xs);
  padding: var(--space-xs) var(--space-sm);
  border: 1px solid var(--border-base); border-radius: var(--radius-base);
  color: var(--text-primary); text-decoration: none;
  font-size: var(--font-xs); font-weight: var(--font-semibold);
  transition: all var(--duration-fast) var(--ease-in-out);
  background: var(--bg-primary);
}
.github-link:hover { border-color: var(--primary-color); color: var(--primary-color); box-shadow: var(--shadow-light); }

.tab-nav {
  display: flex; gap: var(--space-xs); margin-bottom: var(--space-md);
  background: var(--bg-primary); border: 1px solid var(--border-light);
  border-radius: var(--radius-large); padding: var(--space-xs); box-shadow: var(--shadow-light);
}
.tab-btn {
  flex: 1; padding: var(--space-sm) var(--space-md);
  border: none; border-radius: var(--radius-base); background: transparent;
  cursor: pointer; font-size: var(--font-sm); font-weight: var(--font-regular);
  color: var(--text-secondary); transition: all var(--duration-fast) var(--ease-in-out);
}
.tab-btn:hover { background: var(--bg-hover); }
.tab-btn.active { background: var(--primary-color); color: white; font-weight: var(--font-semibold); }

footer { text-align: center; padding: var(--space-lg) 0 var(--space-sm); color: var(--text-muted); font-size: var(--font-xs); }
footer a { color: var(--text-secondary); text-decoration: none; }
footer a:hover { color: var(--primary-color); }

/* 快速提示 */
.quick-tips {
  display: flex;
  justify-content: center;
  gap: var(--space-lg);
  margin-top: var(--space-md);
  flex-wrap: wrap;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  font-size: var(--font-xs);
  color: var(--text-secondary);
  padding: var(--space-xs) var(--space-sm);
  background: var(--bg-primary);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-light);
}

.tip-icon {
  font-size: 16px;
}

.tip-item kbd {
  display: inline-block;
  padding: 2px 6px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-base);
  border-radius: 3px;
  font-family: monospace;
  font-size: 11px;
  box-shadow: 0 1px 1px rgba(0,0,0,0.1);
}

/* 状态提示 Toast */
.status-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  min-width: 300px;
  max-width: 400px;
  background: white;
  border-radius: var(--radius-large);
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  display: flex;
  align-items: start;
  gap: var(--space-md);
  padding: var(--space-md);
  animation: slideIn 0.3s ease-out;
  z-index: 10000;
}

@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.status-toast.success {
  border-left: 4px solid var(--success-color);
}

.status-toast.error {
  border-left: 4px solid var(--error-color);
}

.status-toast.info {
  border-left: 4px solid var(--primary-color);
}

.toast-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.toast-content {
  flex: 1;
}

.toast-title {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 4px;
}

.toast-message {
  font-size: var(--font-xs);
  color: var(--text-secondary);
}

.toast-close {
  background: none;
  border: none;
  font-size: 24px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.toast-close:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

</style>

<style>
/* ElementPlus组件全局样式覆盖 */
.el-dialog {
  border-radius: var(--radius-large) !important;
  box-shadow: var(--shadow-base) !important;
}

.el-dialog__header {
  padding: var(--space-lg) var(--space-xl) !important;
  border-bottom: 1px solid var(--border-light) !important;
  margin: 0 !important;
}

.el-dialog__title {
  font-size: 18px !important;
  font-weight: var(--font-semibold) !important;
  color: var(--text-primary) !important;
  line-height: var(--leading-normal) !important;
}

.el-dialog__headerbtn {
  top: var(--space-lg) !important;
  right: var(--space-xl) !important;
  width: 32px !important;
  height: 32px !important;
  font-size: 24px !important;
}

.el-dialog__headerbtn:hover {
  background: var(--bg-secondary) !important;
  border-radius: var(--radius-small) !important;
}

.el-dialog__body {
  padding: var(--space-xl) !important;
  color: var(--text-primary) !important;
  font-size: var(--font-sm) !important;
  line-height: var(--leading-normal) !important;
}

.el-dialog__footer {
  padding: var(--space-md) var(--space-xl) var(--space-xl) !important;
  border-top: 1px solid var(--border-light) !important;
}

.el-button {
  font-family: inherit !important;
  border-radius: var(--radius-base) !important;
  font-weight: var(--font-semibold) !important;
  transition: all var(--duration-fast) var(--ease-in-out) !important;
}

.el-button--primary {
  background-color: var(--primary-color) !important;
  border-color: var(--primary-color) !important;
}

.el-button--primary:hover {
  background-color: #40a9ff !important;
  border-color: #40a9ff !important;
}

.el-button--danger {
  background-color: var(--error-color) !important;
  border-color: var(--error-color) !important;
}

.el-button--danger:hover {
  background-color: #ff7875 !important;
  border-color: #ff7875 !important;
}

.el-message {
  border-radius: var(--radius-base) !important;
  box-shadow: var(--shadow-base) !important;
  font-size: var(--font-sm) !important;
}

.el-message-box {
  border-radius: var(--radius-large) !important;
  box-shadow: var(--shadow-base) !important;
}

.el-message-box__header {
  padding: var(--space-lg) var(--space-xl) var(--space-md) !important;
}

.el-message-box__title {
  font-size: 18px !important;
  font-weight: var(--font-semibold) !important;
  color: var(--text-primary) !important;
}

.el-message-box__content {
  padding: 0 var(--space-xl) var(--space-lg) !important;
  font-size: var(--font-sm) !important;
  line-height: var(--leading-normal) !important;
}

.el-message-box__btns {
  padding: var(--space-md) var(--space-xl) var(--space-xl) !important;
}
</style>
