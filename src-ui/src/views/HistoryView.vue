<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="content-grid">
    <div class="history-header">
      <input
        v-model="query"
        class="search"
        type="text"
        placeholder="搜索历史听写…"
        @input="onSearch"
      />
      <button class="btn btn-clear" @click="onClear" :disabled="!items.length">清空历史</button>
    </div>

    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="!items.length" class="hint">
      {{ query ? '没有匹配的记录' : '还没有听写历史，按 F9 说几句就会出现在这里' }}
    </div>

    <div v-else class="history-list">
      <div v-for="it in items" :key="it.id" class="history-item">
        <div class="item-main">
          <div class="item-text">{{ it.text }}</div>
          <div class="item-meta">
            <span>{{ it.time }}</span>
            <span v-if="it.scene" class="scene-badge">{{ sceneName(it.scene) }}</span>
            <span class="chars">{{ it.chars }} 字</span>
          </div>
        </div>
        <div class="item-actions">
          <button class="icon-btn" title="复制" @click="copy(it)">{{ copiedId === it.id ? '✓' : '复制' }}</button>
          <button class="icon-btn danger" title="删除" @click="remove(it)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useApi } from '../composables/useApi'

interface HistoryItem {
  id: number; ts: number; time: string; text: string; scene: string | null; app: string | null; chars: number
}

const api = useApi()
const items = ref<HistoryItem[]>([])
const query = ref('')
const loading = ref(true)
const copiedId = ref<number | null>(null)
let searchTimer: number | null = null

const SCENE_NAMES: Record<string, string> = {
  general: '通用', terminal: '终端', code: '编程', chat: '聊天',
  email: '邮件', document: '文档', translate_to_en: '中译英',
}
function sceneName(s: string) { return SCENE_NAMES[s] || s }

async function load() {
  loading.value = true
  try {
    const res = await api.getHistory(100, 0, query.value.trim())
    items.value = res.items || []
  } catch (e) {
    console.error('Failed to load history:', e)
  } finally {
    loading.value = false
  }
}

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = window.setTimeout(load, 300)
}

async function copy(it: HistoryItem) {
  try {
    await navigator.clipboard.writeText(it.text)
    copiedId.value = it.id
    setTimeout(() => { if (copiedId.value === it.id) copiedId.value = null }, 1500)
  } catch {
    ElMessage.error('复制失败')
  }
}

async function remove(it: HistoryItem) {
  try {
    await api.deleteHistoryItem(it.id)
    items.value = items.value.filter(x => x.id !== it.id)
  } catch {
    ElMessage.error('删除失败')
  }
}

async function onClear() {
  try {
    await ElMessageBox.confirm('确定清空全部听写历史吗？（统计数据不受影响）', '清空历史', {
      confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  try {
    await api.clearHistory()
    items.value = []
    ElMessage.success('历史已清空')
  } catch {
    ElMessage.error('清空失败')
  }
}

onMounted(load)
</script>

<style scoped>
.content-grid { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-md); }

.history-header { display: flex; gap: var(--space-md); align-items: center; }
.search {
  flex: 1; padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-base); border-radius: var(--radius-base); font-size: var(--font-sm);
}
.search:focus { outline: none; border-color: var(--primary-color); box-shadow: 0 0 0 3px var(--accent-tint); }
.btn-clear {
  padding: var(--space-sm) var(--space-md); border: 1px solid var(--border-base);
  border-radius: var(--radius-base); background: white; cursor: pointer; font-size: var(--font-sm); white-space: nowrap;
}
.btn-clear:hover:not(:disabled) { border-color: var(--error-color); color: var(--error-color); }
.btn-clear:disabled { opacity: 0.5; cursor: not-allowed; }

.hint { text-align: center; color: var(--text-muted); padding: var(--space-xl); font-size: var(--font-sm); }

.history-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.history-item {
  display: flex; align-items: flex-start; gap: var(--space-md);
  background: white; border: 1px solid var(--border-light); border-radius: var(--radius-base);
  padding: var(--space-md); box-shadow: var(--shadow-light);
}
.item-main { flex: 1; min-width: 0; }
.item-text { font-size: var(--font-sm); color: var(--text-primary); line-height: 1.5; word-break: break-word; }
.item-meta { display: flex; gap: var(--space-md); align-items: center; margin-top: 6px; font-size: var(--font-xs); color: var(--text-muted); }
.scene-badge { padding: 1px 8px; background: var(--accent-tint); color: var(--primary-color); border-radius: 10px; }
.chars { color: var(--text-secondary); }

.item-actions { display: flex; gap: var(--space-xs); flex-shrink: 0; }
.icon-btn {
  padding: 4px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-small);
  background: var(--bg-secondary); cursor: pointer; font-size: var(--font-xs); color: var(--text-secondary);
}
.icon-btn:hover { border-color: var(--primary-color); color: var(--primary-color); }
.icon-btn.danger:hover { border-color: var(--error-color); color: var(--error-color); }
</style>
