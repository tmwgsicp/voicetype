<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0

  地道回复助手：选中对方消息按 F7 → 本窗打开（上下文自动填入）→ 用中文写想回什么 →
  LLM 结合上下文生成地道英文回复 → 复制 → 粘贴到聊天框。
-->
<template>
  <div class="rc-card">
    <div class="rc-head" data-tauri-drag-region>
      <span class="rc-title">地道回复</span>
      <button class="rc-close" @click="close" title="关闭 (Esc)">×</button>
    </div>

    <div class="rc-body">
      <label class="rc-label">对方消息（上下文，可编辑）</label>
      <textarea
        class="rc-input rc-context"
        v-model="context"
        rows="3"
        placeholder="选中对方消息后按 F7 会自动填入；也可手动粘贴/编辑"
      ></textarea>

      <label class="rc-label">你想回复什么（中文 / 英文都行）</label>
      <textarea
        ref="intentEl"
        class="rc-input rc-intent"
        v-model="intent"
        rows="2"
        placeholder="例如：告诉他我已经修好了，晚点发 PR；语气随意点"
        @keydown.enter.meta.prevent="generate"
        @keydown.enter.ctrl.prevent="generate"
      ></textarea>

      <div class="rc-row">
        <div class="rc-tones">
          <button
            v-for="t in tones" :key="t.id"
            class="rc-tone" :class="{ active: tone === t.id }"
            @click="tone = t.id"
          >{{ t.label }}</button>
        </div>
        <button class="btn btn-primary" :disabled="loading || !canGen" @click="generate">
          {{ loading ? '生成中…' : '生成回复' }}
        </button>
      </div>

      <div v-if="result || loading || errMsg" class="rc-result-wrap">
        <label class="rc-label">
          英文回复
          <span v-if="copied" class="rc-copied">✓ 已复制</span>
        </label>
        <div v-if="errMsg" class="rc-error">{{ errMsg }}</div>
        <div v-else class="rc-result" :class="{ dim: loading }">{{ result || '…' }}</div>
        <div class="rc-actions" v-if="result && !loading">
          <button class="btn btn-sm" @click="generate">重新生成</button>
          <span class="spacer"></span>
          <button class="btn btn-sm" @click="copy()">复制</button>
          <button class="btn btn-sm btn-primary" @click="copyAndClose">复制并关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'

const tones = [
  { id: 'auto', label: '自动匹配' },
  { id: 'casual', label: '随意' },
  { id: 'professional', label: '正式' },
]

const context = ref('')
const intent = ref('')
const tone = ref('auto')
const result = ref('')
const loading = ref(false)
const copied = ref(false)
const errMsg = ref('')
const intentEl = ref<HTMLTextAreaElement | null>(null)
let base = ''

const canGen = computed(() => !!(intent.value.trim() || context.value.trim()))

async function apiBase(): Promise<string> {
  if (base) return base
  try { base = `http://127.0.0.1:${await invoke<number>('get_port')}` } catch { base = '' }
  return base
}

async function generate() {
  if (loading.value || !canGen.value) return
  loading.value = true
  errMsg.value = ''
  copied.value = false
  try {
    const b = await apiBase()
    const resp = await fetch(`${b}/api/edit/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context: context.value.trim(), intent: intent.value.trim(), tone: tone.value }),
    })
    const data = await resp.json()
    if (data.status === 'ok' && data.reply) {
      result.value = data.reply
      await copy(true)          // 生成后自动复制，用户直接去聊天框 Ctrl+V
    } else {
      errMsg.value = data.message || '生成失败'
    }
  } catch {
    errMsg.value = '请求失败，请检查后端/网络'
  }
  loading.value = false
}

async function copy(silent = false) {
  if (!result.value) return
  try {
    await navigator.clipboard.writeText(result.value)
  } catch {
    // 回退：隐藏 textarea + execCommand
    const ta = document.createElement('textarea')
    ta.value = result.value
    document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy') } catch {}
    document.body.removeChild(ta)
  }
  copied.value = true
  if (!silent) setTimeout(() => { copied.value = false }, 2000)
}

async function copyAndClose() {
  await copy(true)
  close()
}

async function close() {
  try { await invoke('hide_reply_window') } catch {}
  try {
    const b = await apiBase()
    await fetch(`${b}/api/edit/reply/cancel`, { method: 'POST' })
  } catch {}
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') { e.preventDefault(); close() }
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await listen<any>('backend-event', (event) => {
    const d = event.payload
    if (!d || !d.type) return
    if (d.type === 'reply_compose_show') {
      context.value = d.context || ''
      intent.value = ''
      result.value = ''
      errMsg.value = ''
      copied.value = false
      loading.value = false
      nextTick(() => { window.focus(); intentEl.value?.focus() })
    } else if (d.type === 'reply_compose_hide') {
      // 后端也可能主动要求关闭
    }
  })
})

onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
* { box-sizing: border-box; }

.rc-card {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  margin: 10px;
  height: calc(100vh - 20px);
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border: 0.5px solid rgba(0, 0, 0, 0.1);
  border-radius: 16px;
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.22), 0 3px 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.rc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 0.5px solid rgba(60, 60, 67, 0.12);
  cursor: default;
  user-select: none;
}
.rc-title { font-size: 13px; font-weight: 600; color: #1d1d1f; }
.rc-close {
  width: 24px; height: 24px; border: none; background: transparent;
  font-size: 20px; line-height: 1; color: rgba(60,60,67,0.5); cursor: pointer; border-radius: 6px;
}
.rc-close:hover { background: rgba(120,120,128,0.14); color: #1d1d1f; }

.rc-body { flex: 1; overflow-y: auto; padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 6px; }

.rc-label {
  font-size: 11px; font-weight: 600; color: rgba(60,60,67,0.78); margin-top: 6px;
  display: flex; align-items: center; gap: 8px;
}
.rc-copied { color: #34c759; font-weight: 500; }

.rc-input {
  width: 100%;
  border: 1px solid #e3e3e6;
  border-radius: 9px;
  padding: 8px 10px;
  font-size: 13px;
  color: #1d1d1f;
  background: #fff;
  font-family: inherit;
  line-height: 1.5;
  resize: vertical;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.rc-input:focus { outline: none; border-color: #0a84ff; box-shadow: 0 0 0 3px rgba(10,132,255,0.12); }
.rc-context { color: rgba(60,60,67,0.85); }

.rc-row { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.rc-tones { display: flex; gap: 2px; background: rgba(120,120,128,0.1); border-radius: 8px; padding: 2px; flex: 1; }
.rc-tone {
  flex: 1; border: none; background: transparent; border-radius: 6px; padding: 5px 8px;
  font-size: 12px; color: rgba(60,60,67,0.7); cursor: pointer; transition: all 0.15s ease;
}
.rc-tone.active { background: #fff; color: #1d1d1f; font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,0.08); }

.rc-result-wrap { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.rc-result {
  background: rgba(10,132,255,0.06);
  border: 1px solid rgba(10,132,255,0.15);
  border-radius: 9px; padding: 10px 12px;
  font-size: 14px; color: #1d1d1f; line-height: 1.55; white-space: pre-wrap; word-break: break-word;
}
.rc-result.dim { color: rgba(60,60,67,0.4); }
.rc-error {
  background: rgba(255,59,48,0.08); border: 1px solid rgba(255,59,48,0.2);
  border-radius: 9px; padding: 10px 12px; font-size: 13px; color: #d0021b;
}
.rc-actions { display: flex; align-items: center; gap: 8px; }
.spacer { flex: 1; }

/* 复用全局 .btn 系统，仅补充按钮字号在此窗内的一致性 */
.btn { font-size: 13px; }
.btn-sm { font-size: 12px; }

@media (prefers-color-scheme: dark) {
  .rc-card { background: rgba(40,40,42,0.98); border-color: rgba(255,255,255,0.14); }
  .rc-title, .rc-result { color: #f5f5f7; }
  .rc-label { color: rgba(235,235,245,0.65); }
  .rc-head { border-color: rgba(255,255,255,0.1); }
  .rc-close { color: rgba(235,235,245,0.5); }
  .rc-close:hover { background: rgba(120,120,128,0.3); color: #f5f5f7; }
  .rc-input { background: rgba(20,20,22,0.6); border-color: rgba(255,255,255,0.14); color: #f5f5f7; }
  .rc-input::placeholder { color: rgba(235,235,245,0.3); }
  .rc-context { color: rgba(235,235,245,0.85); }
  .rc-tones { background: rgba(120,120,128,0.24); }
  .rc-tone { color: rgba(235,235,245,0.6); }
  .rc-tone.active { background: rgba(90,90,95,0.95); color: #f5f5f7; }
  .rc-result { background: rgba(10,132,255,0.14); border-color: rgba(10,132,255,0.3); }
}
</style>
