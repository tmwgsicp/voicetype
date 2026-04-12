<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div
    class="floating-container"
    @mousedown.left="onMouseDown"
    @contextmenu.prevent
    @mouseenter="showTooltip = true"
    @mouseleave="showTooltip = false"
  >
    <canvas ref="canvasRef" :width="canvasW" :height="canvasH"></canvas>
    
    <!-- 工具提示 -->
    <div v-if="showTooltip" class="tooltip" :class="tooltipClass">
      <div class="tooltip-title">{{ tooltipTitle }}</div>
      <div class="tooltip-hint">{{ tooltipHint }}</div>
    </div>
    
    <div v-if="showMenu" class="context-menu" :style="{ left: menuX + 'px', top: menuY + 'px' }">
      <div class="menu-status">{{ stateLabel }}</div>
      <div class="menu-sep"></div>
      <div class="menu-item" @click="openSettings">Settings</div>
      <div class="menu-item" @click="quitApp">Quit</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWindow } from '@tauri-apps/api/window'

const BAR_COUNT = 15
const BAR_WIDTH = 6
const BAR_GAP = 4
const BAR_MAX_H = 40
const BAR_MIN_H = 8
const PADDING_X = 12
const PADDING_Y = 6
const CORNER_RADIUS = 12

const canvasW = PADDING_X * 2 + BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_GAP
const canvasH = PADDING_Y * 2 + BAR_MAX_H

const COLORS: Record<string, { bars: string[]; bg: string; glow?: string }> = {
  standby: {
    bars: [
      '#13c2c2','#36cfc9','#5cdbd3','#87e8de','#b5f5ec','#d6f7f5','#e6fffb','#d6f7f5',
      '#b5f5ec','#87e8de','#5cdbd3','#36cfc9','#13c2c2','#08979c','#006d75'
    ],
    bg: 'rgba(17, 33, 33, 0.92)',
    glow: '#13c2c2',
  },
  recording: {
    bars: [
      '#cf1322','#ff4d4f','#ff7a45','#ffa940','#ffc53d','#ffec3d','#fff566','#ffec3d',
      '#ffc53d','#ffa940','#ff7a45','#ff4d4f','#cf1322','#a8071a','#820014'
    ],
    bg: 'rgba(42, 18, 21, 0.92)',
    glow: '#ff4d4f',
  },
  loading: {
    bars: [
      '#096dd9','#1890ff','#40a9ff','#69c0ff','#91d5ff','#bae7ff','#e6f7ff','#bae7ff',
      '#91d5ff','#69c0ff','#40a9ff','#1890ff','#096dd9','#0050b3','#003a8c'
    ],
    bg: 'rgba(17, 29, 44, 0.92)',
    glow: '#1890ff',
  },
}

const canvasRef = ref<HTMLCanvasElement>()
const state = ref<'loading' | 'standby' | 'recording'>('loading')
const isAsrConnected = ref(false)  // ASR连接状态
const stateLabel = computed(() => {
  if (state.value === 'loading') {
    return isAsrConnected.value ? 'Standby' : 'Initializing ASR...'
  }
  return { standby: 'Standby', recording: 'Recording...' }[state.value] || 'Unknown'
})

const showMenu = ref(false)
const menuX = ref(0)
const menuY = ref(0)

const showTooltip = ref(false)
const tooltipClass = computed(() => state.value)
const tooltipTitle = computed(() => {
  if (state.value === 'loading') {
    return isAsrConnected.value ? '准备就绪' : '正在初始化...'
  }
  if (state.value === 'recording') {
    return '正在录音'
  }
  return '待机中'
})
const tooltipHint = computed(() => {
  if (state.value === 'loading') {
    return isAsrConnected.value ? '点击开始录音' : '请稍候,正在加载 ASR 模型'
  }
  if (state.value === 'recording') {
    return '再次点击或按 F9 停止'
  }
  return '点击开始录音 或 按 F9'
})

let animId = 0
let tick = 0
const barHeights = Array(BAR_COUNT).fill(BAR_MIN_H)
const barTargets = Array(BAR_COUNT).fill(BAR_MIN_H)
const barPhases = Array.from({ length: BAR_COUNT }, () => Math.random() * Math.PI * 2)
const barSpeeds = Array.from({ length: BAR_COUNT }, () => 0.08 + Math.random() * 0.1)

let isDragging = false
let dragStartX = 0
let dragStartY = 0

function animate() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!

  tick++
  const scheme = COLORS[state.value] || COLORS.loading

  // Update targets with subtle animation
  for (let i = 0; i < BAR_COUNT; i++) {
    if (state.value === 'recording') {
      // 录音模式：动态动画
      barPhases[i] += barSpeeds[i] * 1.5
      const base = 0.6 + 0.4 * Math.sin(barPhases[i])
      const jitter = (Math.random() - 0.5) * 0.4
      const spike = Math.random() < 0.12 ? 0.3 : 0
      barTargets[i] = BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * Math.max(0.15, Math.min(1, base + jitter + spike))
    } else if (state.value === 'loading') {
      // 加载模式：明显的流动动画（提示正在初始化ASR）
      barTargets[i] = BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * (0.25 + 0.25 * Math.sin(tick * 0.1 + i * 0.5))
    } else {
      // 待机模式：静态 + 极轻微呼吸（几乎不动）
      barTargets[i] = BAR_MIN_H + (BAR_MAX_H - BAR_MIN_H) * (0.12 + 0.03 * Math.sin(tick * 0.02 + i * 0.4))
    }
  }

  const lerp = state.value === 'recording' ? 0.45 : 0.15
  for (let i = 0; i < BAR_COUNT; i++) {
    barHeights[i] += (barTargets[i] - barHeights[i]) * lerp
  }

  // Draw bg with subtle glow
  ctx.clearRect(0, 0, canvasW, canvasH)
  
  // Outer glow (only when recording)
  if (scheme.glow && state.value === 'recording') {
    ctx.shadowColor = scheme.glow
    ctx.shadowBlur = 6
  }
  
  ctx.beginPath()
  ctx.roundRect(0, 0, canvasW, canvasH, CORNER_RADIUS)
  ctx.fillStyle = scheme.bg
  ctx.fill()
  ctx.shadowBlur = 0

  // Draw bars
  for (let i = 0; i < BAR_COUNT; i++) {
    const h = Math.max(BAR_MIN_H, barHeights[i])
    const x = PADDING_X + i * (BAR_WIDTH + BAR_GAP)
    const yTop = PADDING_Y + (BAR_MAX_H - h)
    
    ctx.fillStyle = scheme.bars[i]
    ctx.beginPath()
    ctx.roundRect(x, yTop, BAR_WIDTH, h, 2.5)
    ctx.fill()
  }

  animId = requestAnimationFrame(animate)
}

function onMouseDown(e: MouseEvent) {
  showMenu.value = false
  isDragging = false
  dragStartX = e.screenX
  dragStartY = e.screenY

  const currentWindow = getCurrentWindow()

  const onMove = (ev: MouseEvent) => {
    const dx = Math.abs(ev.screenX - dragStartX)
    const dy = Math.abs(ev.screenY - dragStartY)
    
    // 移动超过5px才触发拖动，避免误触
    if ((dx > 5 || dy > 5) && !isDragging) {
      isDragging = true
      currentWindow.startDragging().catch(() => {})
    }
  }

  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    if (!isDragging) {
      onToggle()
    }
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function onRightClick(e: MouseEvent) {
  menuX.value = e.offsetX
  menuY.value = e.offsetY
  showMenu.value = true
}

async function onToggle() {
  try { await invoke('toggle_recording') } catch {}
}

function openSettings() {
  showMenu.value = false
  const appWindow = getCurrentWindow()
  // Emit event to main window to show settings
  invoke('get_port').then(() => {
    window.open('/', '_blank')
  }).catch(() => {})
}

function quitApp() {
  showMenu.value = false
  import('@tauri-apps/plugin-process').then(mod => mod.exit(0)).catch(() => {})
}

onMounted(async () => {
  animId = requestAnimationFrame(animate)

  await listen<any>('backend-event', (event) => {
    const data = event.payload
    if (data.type === 'recording') {
      // 只有在ASR已连接时才允许进入standby/recording
      if (data.active) {
        state.value = 'recording'
      } else if (isAsrConnected.value) {
        state.value = 'standby'
      } else {
        state.value = 'loading'  // 如果ASR未连接，保持loading
      }
    }
    if (data.type === 'asr_connected') {
      isAsrConnected.value = data.connected
      // ASR连接后，如果不在录音，则进入standby
      if (data.connected && state.value === 'loading') {
        state.value = 'standby'
      }
      // ASR断开后，强制进入loading
      if (!data.connected) {
        state.value = 'loading'
      }
    }
    // 声纹验证被拒绝
    if (data.type === 'voiceprint_reject') {
      console.log('🚫 Voiceprint rejected:', data)
      // TODO: 显示视觉反馈（闪烁或通知）
    }
  })

  await listen<any>('backend-status', (event) => {
    const data = event.payload
    if (data && data.ready) {
      // 后端就绪，但ASR可能尚未连接，保持loading直到收到asr_connected事件
      if (state.value === 'loading' && isAsrConnected.value) {
        state.value = 'standby'
      }
    }
  })

  window.addEventListener('click', () => { showMenu.value = false })
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
})
</script>

<style>
html, body { margin: 0; padding: 0; overflow: hidden; background: transparent; }
</style>

<style scoped>
.floating-container {
  width: v-bind(canvasW + 'px');
  height: v-bind(canvasH + 'px');
  cursor: pointer;
  user-select: none;
  position: relative;
}

canvas { display: block; }

.context-menu {
  position: absolute; background: #262626; border-radius: 8px;
  padding: 4px 0; min-width: 120px; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.menu-status { padding: 6px 12px; font-size: 12px; color: #8c8c8c; }
.menu-sep { height: 1px; background: #3a3a3a; margin: 2px 0; }
.menu-item {
  padding: 6px 12px; font-size: 13px; color: #e8e8e8; cursor: pointer;
  transition: background 150ms;
}
.menu-item:hover { background: #3a3a3a; }

/* 工具提示 */
.tooltip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(-8px);
  background: rgba(38, 38, 38, 0.95);
  border-radius: 8px;
  padding: 8px 12px;
  white-space: nowrap;
  pointer-events: none;
  animation: tooltipFadeIn 0.2s ease-out;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(-8px);
  }
}

.tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: rgba(38, 38, 38, 0.95);
}

.tooltip-title {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 2px;
}

.tooltip-hint {
  font-size: 11px;
  color: #bfbfbf;
}

.tooltip.recording .tooltip-title {
  color: #ff4d4f;
}

.tooltip.loading .tooltip-title {
  color: #1890ff;
}

.tooltip.standby .tooltip-title {
  color: #13c2c2;
}

</style>
