/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

const backendPort = ref(0)
const baseUrl = ref('')

let _initialized = false

export async function initApi() {
  if (_initialized) return
  
  // 浏览器环境检测：优先使用环境变量端口，否则使用Tauri
  const isWebMode = typeof window !== 'undefined' && !(window as any).__TAURI__
  
  try {
    if (isWebMode) {
      // 浏览器直接访问模式：使用默认端口
      const port = 18233
      backendPort.value = port
      baseUrl.value = `http://127.0.0.1:${port}`
      _initialized = true
      console.log(`API initialized (Web mode): ${baseUrl.value}`)
    } else {
      // Tauri模式：从Rust获取动态端口
      console.log('Initializing API, fetching port from Tauri...')
      const port = await invoke<number>('get_port')
      backendPort.value = port
      baseUrl.value = `http://127.0.0.1:${port}`
      _initialized = true
      console.log(`API initialized (Tauri mode): ${baseUrl.value}`)
    }
  } catch (error) {
    console.error('Failed to initialize API:', error)
    // Fallback到默认端口
    baseUrl.value = 'http://127.0.0.1:18233'
    console.warn('Using fallback URL:', baseUrl.value)
  }
}

export function useApi() {
  async function fetchJson<T = any>(path: string, options?: RequestInit): Promise<T> {
    if (!baseUrl.value) await initApi()
    if (!baseUrl.value) {
      throw new Error('后端服务未就绪，请稍后重试')
    }

    const url = `${baseUrl.value}${path}`

    // 后端启动 + 模型预热需要几秒。连接失败（后端还没起来）时退避重试，
    // 避免各组件在启动瞬间弹一堆"加载失败"误报。HTTP 错误（4xx/5xx）是真错，不重试。
    let lastErr: any
    for (let attempt = 0; attempt < 12; attempt++) {
      try {
        const resp = await fetch(url, options)
        if (!resp.ok) {
          const error = await resp.json().catch(() => ({ detail: 'Request failed' }))
          error.__httpStatus = resp.status
          throw error
        }
        return await resp.json()
      } catch (e: any) {
        // 已到达后端并返回错误（有 detail/状态码）→ 真错，直接抛
        if (e && (e.__httpStatus !== undefined || e.detail !== undefined)) throw e
        // 连接失败（后端未就绪）→ 退避重试
        lastErr = e
        await new Promise(r => setTimeout(r, 500))
      }
    }
    throw lastErr || new Error('后端服务未就绪')
  }

  async function get<T = any>(path: string): Promise<T> {
    return fetchJson(path)
  }

  async function post<T = any>(path: string, data?: any): Promise<T> {
    return fetchJson(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async function put<T = any>(path: string, data?: any): Promise<T> {
    return fetchJson(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async function del<T = any>(path: string): Promise<T> {
    return fetchJson(path, {
      method: 'DELETE',
    })
  }

  async function getStatus() {
    return fetchJson('/api/status')
  }

  async function getConfig() {
    return fetchJson('/api/config')
  }

  async function saveConfig(data: Record<string, any>) {
    return fetchJson('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  }

  async function testConnection() {
    return fetchJson('/api/config/test', { method: 'POST' })
  }

  async function toggleRecording() {
    return fetchJson('/api/toggle', { method: 'POST' })
  }

  async function getStatsSummary() {
    return fetchJson('/api/stats/summary')
  }

  async function getStatsDaily(days = 30) {
    return fetchJson(`/api/stats/daily?days=${days}`)
  }

  async function getStatsScenes() {
    return fetchJson('/api/stats/scenes')
  }

  async function getHistory(limit = 50, offset = 0, q = '') {
    const qs = new URLSearchParams({ limit: String(limit), offset: String(offset), q })
    return fetchJson(`/api/stats/history?${qs.toString()}`)
  }

  async function deleteHistoryItem(id: number) {
    return fetchJson(`/api/stats/history/${id}`, { method: 'DELETE' })
  }

  async function clearHistory() {
    return fetchJson('/api/stats/history/clear', { method: 'POST' })
  }

  return {
    baseUrl,
    backendPort,
    get,
    post,
    put,
    del,
    getStatus,
    getConfig,
    saveConfig,
    testConnection,
    getStatsSummary,
    getStatsDaily,
    getStatsScenes,
    getHistory,
    deleteHistoryItem,
    clearHistory,
    toggleRecording,
  }
}
