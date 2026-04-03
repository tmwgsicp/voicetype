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
    console.log(`API request: ${options?.method || 'GET'} ${url}`)
    
    const resp = await fetch(url, options)
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({ detail: 'Request failed' }))
      console.error(`API error: ${resp.status}`, error)
      throw error
    }
    return resp.json()
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

  async function getKBStats() {
    return fetchJson('/api/kb/stats')
  }

  async function getKBDocuments() {
    return fetchJson('/api/kb/documents')
  }

  async function addKBText(title: string, content: string) {
    return fetchJson('/api/kb/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    })
  }

  async function uploadKBFile(file: File) {
    if (!baseUrl.value) await initApi()
    const fd = new FormData()
    fd.append('file', file)
    const resp = await fetch(`${baseUrl.value}/api/kb/upload`, {
      method: 'POST',
      body: fd,
    })
    return resp.json()
  }

  async function deleteKBDocument(id: string) {
    return fetchJson(`/api/kb/documents/${id}`, { method: 'DELETE' })
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
    toggleRecording,
    getKBStats,
    getKBDocuments,
    addKBText,
    uploadKBFile,
    deleteKBDocument,
  }
}
