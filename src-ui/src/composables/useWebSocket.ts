/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

import { ref, onUnmounted } from 'vue'
import { listen } from '@tauri-apps/api/event'
import type { UnlistenFn } from '@tauri-apps/api/event'

export interface RecordingState {
  isRecording: boolean
  scene: string
  activeWindow: string
}

export function useWebSocket() {
  const state = ref<RecordingState>({
    isRecording: false,
    scene: 'general',
    activeWindow: '-',
  })

  let unlisten: UnlistenFn | null = null
  let pollInterval: number | null = null

  async function startListening() {
    const isWebMode = typeof window !== 'undefined' && !(window as any).__TAURI__
    
    if (isWebMode) {
      // Web模式：使用HTTP轮询（简化版，仅用于配置页面）
      console.log('WebSocket: Using HTTP polling (Web mode)')
      pollInterval = window.setInterval(async () => {
        try {
          const resp = await fetch('http://127.0.0.1:18233/api/status')
          if (resp.ok) {
            const data = await resp.json()
            state.value.isRecording = data.recording || false
            state.value.scene = data.scene || 'general'
            state.value.activeWindow = data.window || '-'
          }
        } catch (err) {
          // 忽略轮询错误
        }
      }, 1000) as unknown as number
    } else {
      // Tauri模式：使用事件监听
      unlisten = await listen<any>('backend-event', (event) => {
        const data = event.payload
        if (data.type === 'recording') {
          state.value.isRecording = data.active
        }
        if (data.type === 'scene_change') {
          state.value.scene = data.display_name || data.scene
        }
      })
    }
  }

  function stopListening() {
    if (unlisten) {
      unlisten()
      unlisten = null
    }
    if (pollInterval !== null) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  onUnmounted(stopListening)

  return { state, startListening, stopListening }
}
