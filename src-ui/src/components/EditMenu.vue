<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0

  预设文本动作菜单（在光标处弹出的小卡片）。
  选中文字 → 编辑快捷键 → 后端广播 edit_menu_show → 本窗弹出 →
  数字键 1-5 / 点击选动作 → 就地改写替换；Esc / 失焦取消。
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
        <span class="kbd">{{ a.key }}</span>
        <span class="labels">
          <span class="label">{{ a.label }}</span>
          <span class="hint">{{ a.hint }}</span>
        </span>
      </button>
    </div>
    <div class="menu-foot">
      <span><b>1–5</b> 选择</span>
      <span><b>Esc</b> 取消</span>
    </div>
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

// 键盘（1-5 / Esc）由后端全局捕获——菜单窗是非激活窗口，不获得键盘焦点，
// 这样目标程序的选区不会丢失，套用改写才能正确「替换」。此处只处理鼠标点击/悬停。

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
.menu-item.active .kbd {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  border-color: transparent;
}

.kbd {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: rgba(60, 60, 67, 0.6);
  background: rgba(120, 120, 128, 0.12);
  border: 0.5px solid rgba(0, 0, 0, 0.06);
  border-radius: 5px;
}

.labels { display: flex; flex-direction: column; line-height: 1.2; }
.label { font-size: 13px; font-weight: 500; color: #1d1d1f; }
.hint { font-size: 11px; color: rgba(60, 60, 67, 0.5); }

.menu-foot {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px 2px;
  margin-top: 4px;
  border-top: 0.5px solid rgba(60, 60, 67, 0.1);
  font-size: 10px;
  color: rgba(60, 60, 67, 0.45);
}
.menu-foot b { font-weight: 600; color: rgba(60, 60, 67, 0.7); }

@media (prefers-color-scheme: dark) {
  .menu-card {
    background: rgba(44, 44, 46, 0.9);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .menu-title, .menu-foot { color: rgba(235, 235, 245, 0.5); }
  .menu-preview { color: rgba(235, 235, 245, 0.8); }
  .label { color: #f5f5f7; }
  .hint { color: rgba(235, 235, 245, 0.45); }
  .kbd { background: rgba(120, 120, 128, 0.24); color: rgba(235, 235, 245, 0.7); border-color: transparent; }
  .menu-head, .menu-foot { border-color: rgba(255, 255, 255, 0.1); }
  .menu-foot b { color: rgba(235, 235, 245, 0.7); }
}
</style>
