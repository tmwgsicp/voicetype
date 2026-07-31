<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0

  预设文本动作菜单（在光标处弹出的小卡片）。
  选中文字 → 编辑快捷键 → 后端广播 edit_menu_show → 本窗弹出 →
  鼠标点选动作 → 就地改写替换。菜单窗是非激活窗口（不抢焦点，保住目标选区），
  故用鼠标点选/点「取消」；12s 无操作自动收起。
-->
<template>
  <div class="menu-card" @mousedown.prevent>
    <div class="menu-head">
      <span class="menu-title">改写选中文字</span>
      <span class="menu-preview" v-if="preview">{{ preview }}</span>
    </div>
    <div class="menu-list">
      <button
        v-for="(a, i) in actions"
        :key="a.id"
        class="menu-item"
        :class="{ active: i === hovered }"
        @mouseenter="hovered = i"
        @click="pick(a.id)"
      >
        <span class="dot"></span>
        <span class="labels">
          <span class="label">{{ a.label }}</span>
          <span class="hint">{{ a.hint }}</span>
        </span>
      </button>
    </div>
    <button class="menu-cancel" @click="cancel">取消</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'

interface Action { id: string; label: string; hint: string; key: string }

const actions = ref<Action[]>([])
const preview = ref('')
const hovered = ref(0)
let base = ''
let busy = false

async function apiBase(): Promise<string> {
  if (base) return base
  try {
    const port = await invoke<number>('get_port')
    base = `http://127.0.0.1:${port}`
  } catch {
    base = ''
  }
  return base
}

async function hideWindow() {
  try { await invoke('hide_edit_menu') } catch {}
}

async function pick(actionId: string) {
  if (busy) return
  busy = true
  await hideWindow()           // 立即收起，体感更快
  try {
    const b = await apiBase()
    await fetch(`${b}/api/edit/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: actionId }),
    })
  } catch {}
  busy = false
}

async function cancel() {
  if (busy) return
  busy = true
  await hideWindow()
  try {
    const b = await apiBase()
    await fetch(`${b}/api/edit/cancel`, { method: 'POST' })
  } catch {}
  busy = false
}

// 菜单窗是非激活窗口，不获得键盘焦点（这样目标程序的选区不会丢失，套用才能正确「替换」）。
// 因此这里只处理鼠标点击/悬停；取消用「取消」按钮，或后端 12s 兜底自动收起。

onMounted(async () => {
  await listen<any>('backend-event', (event) => {
    const d = event.payload
    if (!d || !d.type) return
    if (d.type === 'edit_menu_show') {
      actions.value = d.actions || []
      preview.value = d.preview || ''
      hovered.value = 0
      busy = false
    } else if (d.type === 'edit_menu_hide') {
      actions.value = []
      preview.value = ''
    }
  })
})

onUnmounted(() => {})
</script>

<style scoped>
* { box-sizing: border-box; }

.menu-card {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  width: 100%;
  height: 100vh;
  padding: 8px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  box-shadow: 0 10px 34px rgba(0, 0, 0, 0.18), 0 2px 6px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  user-select: none;
}

.menu-head {
  padding: 4px 8px 8px;
  border-bottom: 0.5px solid rgba(60, 60, 67, 0.1);
  margin-bottom: 4px;
}
.menu-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: rgba(60, 60, 67, 0.6);
  letter-spacing: 0.02em;
}
.menu-preview {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: rgba(60, 60, 67, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.menu-list { display: flex; flex-direction: column; gap: 1px; }

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 8px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s ease;
}
.menu-item.active { background: #0a84ff; }
.menu-item.active .label { color: #fff; }
.menu-item.active .hint { color: rgba(255, 255, 255, 0.8); }
.menu-item.active .dot { background: #fff; }

.dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(10, 132, 255, 0.55);
}

.labels { display: flex; flex-direction: column; line-height: 1.2; }
.label { font-size: 13px; font-weight: 500; color: #1d1d1f; }
.hint { font-size: 11px; color: rgba(60, 60, 67, 0.5); }

.menu-cancel {
  margin-top: 4px;
  padding: 7px 8px;
  border: none;
  border-top: 0.5px solid rgba(60, 60, 67, 0.1);
  background: transparent;
  color: rgba(60, 60, 67, 0.55);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border-radius: 0 0 10px 10px;
  transition: background 0.12s ease, color 0.12s ease;
}
.menu-cancel:hover { background: rgba(120, 120, 128, 0.1); color: rgba(60, 60, 67, 0.9); }

@media (prefers-color-scheme: dark) {
  .menu-card {
    background: rgba(44, 44, 46, 0.9);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .menu-title { color: rgba(235, 235, 245, 0.5); }
  .menu-preview { color: rgba(235, 235, 245, 0.8); }
  .label { color: #f5f5f7; }
  .hint { color: rgba(235, 235, 245, 0.45); }
  .menu-head { border-color: rgba(255, 255, 255, 0.1); }
  .menu-cancel { color: rgba(235, 235, 245, 0.55); border-color: rgba(255, 255, 255, 0.1); }
  .menu-cancel:hover { background: rgba(120, 120, 128, 0.2); color: rgba(235, 235, 245, 0.9); }
}
</style>
