<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0

  简洁悬浮窗：固定大小、始终可见的胶囊条。
  左侧音量条（真实音量驱动），右侧显示状态 / 实时识别文字。
  不使用 canvas、不动态改窗口大小，尽量少出错。
-->
<template>
  <div class="fw-root" @contextmenu.prevent="onRightClick" @click="showMenu = false">
    <div
      class="capsule"
      :class="state"
      @mousedown.left="onMouseDown"
    >
      <div class="bars">
        <span v-for="(h, i) in barHeights" :key="i" class="bar" :style="{ height: h + '%' }"></span>
      </div>
      <div class="label">
        <span class="label-text">{{ displayText }}</span>
      </div>
    </div>

    <div v-if="showMenu" class="menu" :style="{ left: menuX + 'px', top: menuY + 'px' }">
      <div class="menu-status">{{ stateLabel }}</div>
      <div class="menu-sep"></div>
      <div class="menu-item" @click="openSettings">设置</div>
      <div class="menu-item" @click="quitApp">退出</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'

type State = 'loading' | 'standby' | 'recording' | 'processing'

// 悬浮窗是在后端就绪后才显示的，会错过一次性的 ready 事件，因此默认就用待机态，
// 避免卡在"加载中"。真正开始录音时由事件切到 recording。
const state = ref<State>('standby')
const isAsrConnected = ref(true)
const captionText = ref('')
let captionClearTimer: number | null = null

const showMenu = ref(false)
const menuX = ref(0)
const menuY = ref(0)

// 真实音量（后端广播 audio_level）
let audioLevel = 0
let audioLevelSmoothed = 0
let pollTimer: number | null = null

const BAR_COUNT = 5
const barHeights = ref<number[]>(Array(BAR_COUNT).fill(20))
const barWeight = [0.6, 0.85, 1, 0.85, 0.6]
let tick = 0
let rafId = 0

const stateLabel = computed(() => ({
  loading: isAsrConnected.value ? '待机' : '正在初始化…',
  standby: '待机',
  recording: '正在录音…',
  processing: '转写中…',
}[state.value] || ''))

const displayText = computed(() => {
  if (state.value === 'recording') return captionText.value || '正在聆听…'
  if (state.value === 'processing') return captionText.value || '转写中…'
  if (state.value === 'loading') return isAsrConnected.value ? '待机' : '加载中…'
  return '待机 · F9'
})

function animate() {
  audioLevelSmoothed += (audioLevel - audioLevelSmoothed) * 0.35
  audioLevel *= 0.9
  tick++
  const next = new Array(BAR_COUNT)
  for (let i = 0; i < BAR_COUNT; i++) {
    let target: number
    if (state.value === 'recording') {
      // 录音时始终有基础起伏（明确"在录音"），再叠加真实音量
      const base = 22 + 16 * Math.sin(tick * 0.32 + i * 1.1)
      const vol = audioLevelSmoothed * 120 * barWeight[i]
      target = Math.min(100, Math.max(14, base + vol))
    } else if (state.value === 'processing') {
      target = 30 + 40 * (0.5 + 0.5 * Math.sin(tick * 0.2 + i * 0.7))
    } else if (state.value === 'loading') {
      target = 25 + 30 * (0.5 + 0.5 * Math.sin(tick * 0.12 + i * 0.6))
    } else {
      target = 18 + 6 * Math.sin(tick * 0.05 + i * 0.5)
    }
    const cur = barHeights.value[i]
    next[i] = cur + (target - cur) * 0.45
  }
  barHeights.value = next
  rafId = requestAnimationFrame(animate)
}

function onMouseDown(e: MouseEvent) {
  showMenu.value = false
  let dragging = false
  const sx = e.screenX, sy = e.screenY
  const win = getCurrentWindow()
  const onMove = (ev: MouseEvent) => {
    if (!dragging && (Math.abs(ev.screenX - sx) > 5 || Math.abs(ev.screenY - sy) > 5)) {
      dragging = true
      win.startDragging().catch(() => {})
    }
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    if (!dragging) onToggle()
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function onRightClick(e: MouseEvent) {
  menuX.value = Math.min(e.offsetX, 200)
  menuY.value = Math.max(0, e.offsetY - 60)
  showMenu.value = true
}

async function onToggle() {
  try { await invoke('toggle_recording') } catch {}
}
function openSettings() {
  showMenu.value = false
  invoke('show_main_window').catch(() => { window.open('/', '_blank') })
}
function quitApp() {
  showMenu.value = false
  import('@tauri-apps/plugin-process').then(m => m.exit(0)).catch(() => {})
}

function setCaption(text: string) {
  const t = (text || '').trim()
  if (!t) return
  captionText.value = t
  if (captionClearTimer) { clearTimeout(captionClearTimer); captionClearTimer = null }
}
function scheduleCaptionClear(delay = 2500) {
  if (captionClearTimer) clearTimeout(captionClearTimer)
  captionClearTimer = window.setTimeout(() => { captionText.value = '' }, delay)
}

onMounted(async () => {
  rafId = requestAnimationFrame(animate)

  await listen<any>('backend-event', (event) => {
    const data = event.payload || {}
    switch (data.type) {
      case 'recording':
        if (data.active) {
          state.value = 'recording'
          captionText.value = ''
          if (captionClearTimer) { clearTimeout(captionClearTimer); captionClearTimer = null }
        } else {
          // 停止后回待机（可能先短暂"转写中"）。绝不回到"加载中"——那只是初始态。
          state.value = captionText.value ? 'processing' : 'standby'
          if (state.value === 'processing') {
            setTimeout(() => {
              if (state.value === 'processing') state.value = 'standby'
              scheduleCaptionClear(500)
            }, 1200)
          }
        }
        break
      case 'asr_connected':
        // 仅记录状态。录音结束后 ASR 会正常断开，不能据此回到"加载中"。
        isAsrConnected.value = data.connected
        break
      case 'audio_level':
        audioLevel = Math.max(audioLevel, data.level || 0)
        break
      case 'asr_partial':
      case 'raw_text':
        if (data.text) { setCaption(data.text); if (state.value !== 'recording') state.value = 'recording' }
        break
      case 'final_complete':
        if (data.text) { setCaption(data.text); scheduleCaptionClear(2500) }
        break
    }
  })

  await listen<any>('backend-status', (event) => {
    const d = event.payload
    if (d && d.ready && state.value === 'loading') state.value = 'standby'
  })

  // 兜底轮询：即使 Tauri 事件丢失，也能保证录音状态正确切换（波形/颜色随之变化）
  try {
    const port = await invoke<number>('get_port')
    const base = `http://127.0.0.1:${port}`
    pollTimer = window.setInterval(async () => {
      try {
        const s = await (await fetch(`${base}/api/status`)).json()
        if (s.is_recording && state.value !== 'recording') {
          state.value = 'recording'
        } else if (!s.is_recording && state.value === 'recording') {
          state.value = 'standby'
          scheduleCaptionClear(600)
        }
      } catch {}
    }, 500)
  } catch {}
})

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  if (captionClearTimer) clearTimeout(captionClearTimer)
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style>
html, body { margin: 0; padding: 0; overflow: hidden; background: transparent; }
</style>

<style scoped>
.fw-root {
  width: 100vw; height: 100vh;
  display: flex; align-items: center; justify-content: center;
  user-select: none;
}

.capsule {
  display: flex; align-items: center; gap: 10px;
  width: calc(100vw - 12px); height: 42px;
  padding: 0 14px; box-sizing: border-box;
  background: #1f2229;
  border: none;
  border-radius: 21px;
  box-shadow: none;
  cursor: pointer;
  transition: box-shadow 0.2s;
}
/* 录音/转写时才加彩色辉光作为状态反馈；待机时完全无阴影、边缘纯透明 */
.capsule.recording { box-shadow: 0 0 14px rgba(255, 77, 79, 0.5); }
.capsule.processing { box-shadow: 0 0 14px rgba(146, 84, 222, 0.45); }

.bars { display: flex; align-items: center; gap: 3px; height: 22px; flex-shrink: 0; }
.bar {
  width: 3px; min-height: 3px; border-radius: 2px;
  background: #8c8c8c; align-self: center;
  transition: height 0.08s linear;
}
.capsule.recording .bar { background: linear-gradient(180deg, #ff7875, #ff4d4f); }
.capsule.processing .bar { background: linear-gradient(180deg, #b37feb, #9254de); }
.capsule.standby .bar { background: linear-gradient(180deg, #5cdbd3, #13c2c2); }
.capsule.loading .bar { background: linear-gradient(180deg, #69c0ff, #1890ff); }

.label {
  flex: 1; min-width: 0; overflow: hidden;
  display: flex; justify-content: flex-end;
}
.label-text {
  white-space: nowrap; color: #f0f0f0; font-size: 13px;
  font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif;
}

.menu {
  position: absolute; background: #262626; border-radius: 8px;
  padding: 4px 0; min-width: 110px; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.35);
}
.menu-status { padding: 6px 12px; font-size: 12px; color: #8c8c8c; }
.menu-sep { height: 1px; background: #3a3a3a; margin: 2px 0; }
.menu-item { padding: 6px 12px; font-size: 13px; color: #e8e8e8; cursor: pointer; }
.menu-item:hover { background: #3a3a3a; }
</style>
