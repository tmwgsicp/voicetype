<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="scene-manager">
    <div class="content-grid">
      <section class="unified-card">
        <div class="card-header">
          <span class="card-title">场景管理</span>
        </div>

        <div class="card-hint-block">
          根据不同应用和场景自动调整 LLM 提示词,提供更精准的语音输入体验
        </div>

        <!-- Form Section: Stats & Actions -->
        <div class="form-section">
          <div class="stats-actions-row">
            <div class="stats-group">
              <span class="stat-badge">
                <span class="stat-label">总场景</span>
                <span class="stat-value">{{ scenes.length }}</span>
              </span>
              <span class="stat-badge">
                <span class="stat-label">自定义</span>
                <span class="stat-value">{{ customCount }}</span>
              </span>
            </div>
            <div class="actions-group">
              <button class="btn btn-sm" @click="showImportDialog = true">导入</button>
              <button class="btn btn-sm" @click="exportScenes">导出</button>
              <button class="btn btn-primary" @click="showAddDialog = true">+ 新建场景</button>
            </div>
          </div>
        </div>

        <!-- Active Scene Banner -->
        <div v-if="activeScene" class="form-section active-scene-section">
          <div class="active-scene-banner">
            <div class="banner-content">
              <span class="scene-icon">{{ activeScene.icon }}</span>
              <span class="scene-name">当前场景: {{ activeScene.name }}</span>
              <span v-if="manualMode" class="badge badge-warning">手动模式</span>
            </div>
            <button v-if="manualMode" class="btn btn-sm" @click="clearOverride">切换自动</button>
          </div>
        </div>

        <!-- Form Section: Scenes Grid -->
        <div class="form-section" style="border-bottom: none;">
          <h3 class="form-section-title">可用场景</h3>
          <div class="scenes-grid">
            <div 
              v-for="scene in scenes" 
              :key="scene.id"
              :class="['scene-card', { 
                active: activeScene?.id === scene.id,
                disabled: !scene.enabled
              }]"
            >
              <div class="scene-header">
                <div class="scene-title-row">
                  <div class="card-icon">{{ scene.icon }}</div>
                  <div>
                    <h4>
                      {{ scene.name }}
                      <span v-if="scene.builtin" class="badge badge-success">内置</span>
                    </h4>
                    <div class="scene-meta" v-if="scene.hotkey || (scene.app_rules && scene.app_rules.length > 0)">
                      <span v-if="scene.hotkey" class="meta-item">快捷键: {{ scene.hotkey }}</span>
                      <span v-if="scene.app_rules && scene.app_rules.length > 0" class="meta-item">{{ scene.app_rules.length }} 应用</span>
                    </div>
                  </div>
                </div>
                <div class="scene-actions">
                  <button class="btn btn-sm btn-primary" @click="switchToScene(scene)">切换</button>
                  <button v-if="!scene.builtin" class="btn btn-sm" @click="editScene(scene)">编辑</button>
                  <button v-if="!scene.builtin" class="btn-icon btn-danger" @click="deleteScene(scene)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                </div>
              </div>
              
              <div class="scene-body">
                <p>{{ scene.prompt.length > 100 ? scene.prompt.substring(0, 100) + '...' : scene.prompt }}</p>
                <div v-if="scene.app_rules && Array.isArray(scene.app_rules) && scene.app_rules.length > 0" style="margin-top: var(--space-sm);">
                  <div style="display: flex; flex-wrap: wrap; gap: var(--space-sm);">
                    <span v-for="app in scene.app_rules.slice(0, 3)" :key="app" class="badge badge-primary">{{ app }}</span>
                    <span v-if="scene.app_rules.length > 3" class="badge badge-primary">+{{ scene.app_rules.length - 3 }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Add/Edit Dialog -->
    <div v-if="showAddDialog || showEditDialog" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog dialog-large">
        <div class="dialog-header">
          <h3>{{ showEditDialog ? '编辑场景' : '新建场景' }}</h3>
          <button class="dialog-close" @click="closeDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-row">
            <div class="form-group" style="flex: 1;">
              <label>场景名称 *</label>
              <input v-model="formData.name" placeholder="例如：VibeCoding 教程">
            </div>
            <div class="form-group" style="width: 100px;">
              <label>图标</label>
              <input v-model="formData.icon" placeholder="📚" maxlength="2">
            </div>
          </div>
          
          <div class="form-group">
            <label>提示词模板 *</label>
            <textarea 
              v-model="formData.prompt" 
              rows="8" 
              placeholder="你是一位技术教程作者，专注于 VibeCoding 风格的教学内容创作..."
            ></textarea>
            <p class="form-help">提示词将作为 LLM 的场景指导，优先级高于内置场景</p>
          </div>
          
          <div class="form-row">
            <div class="form-group" style="flex: 1;">
              <label>快捷键（可选）</label>
              <input 
                v-model="formData.hotkey" 
                placeholder="<ctrl>+<shift>+1"
                @blur="validateHotkey"
              >
              <p class="form-help">格式：&lt;ctrl&gt;+&lt;shift&gt;+1~9，留空则无快捷键</p>
              <p v-if="hotkeyError" class="form-error">{{ hotkeyError }}</p>
            </div>
          </div>
          
          <div class="form-group">
            <label>应用绑定（可选）</label>
            <input 
              v-model="newAppRule" 
              placeholder="code.exe（按回车添加）"
              @keyup.enter="addAppRule"
            >
            <div v-if="formData.app_rules.length > 0" class="app-rules-list">
              <span 
                v-for="(app, index) in formData.app_rules" 
                :key="index"
                class="app-rule-tag"
              >
                {{ app }}
                <button class="tag-remove" @click="removeAppRule(index)">×</button>
              </span>
            </div>
            <p class="form-help">当检测到这些应用时自动切换到此场景，输入应用名按回车添加</p>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="closeDialog">取消</button>
          <button class="btn btn-primary" @click="saveScene">保存</button>
        </div>
      </div>
    </div>

    <!-- Import Dialog -->
    <div v-if="showImportDialog" class="dialog-overlay" @click.self="showImportDialog = false">
      <div class="dialog">
        <div class="dialog-header">
          <h3>导入场景</h3>
          <button class="dialog-close" @click="showImportDialog = false">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-group">
            <label>JSON 数据</label>
            <textarea v-model="importData" rows="10" placeholder='{"scenes": [{"name": "...", "prompt": "..."}]}'></textarea>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="importMerge">
              <span>合并模式（不清空现有场景）</span>
            </label>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="showImportDialog = false">取消</button>
          <button class="btn btn-primary" @click="importScenes">导入</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '../composables/useApi'

const api = useApi()

interface Scene {
  id: string
  name: string
  prompt: string
  icon: string
  hotkey: string
  app_rules: string[]
  enabled: boolean
  builtin: boolean
}

const scenes = ref<Scene[]>([])
const activeScene = ref<Scene | null>(null)
const manualMode = ref(false)

const showAddDialog = ref(false)
const showEditDialog = ref(false)
const showImportDialog = ref(false)

const formData = ref({
  id: '',
  name: '',
  prompt: '',
  icon: '💬',
  hotkey: '',
  app_rules: [] as string[],
})

const newAppRule = ref('')
const hotkeyError = ref('')

const importData = ref('')
const importMerge = ref(true)

const customCount = computed(() => scenes.value.filter(s => !s.builtin).length)

const loadScenes = async () => {
  try {
    const data = await api.get('/api/scenes')
    scenes.value = (data.scenes || []).map((scene: any) => ({
      ...scene,
      app_rules: scene.app_rules || []
    }))
  } catch (error) {
    scenes.value = []
    ElMessage.error('加载场景失败')
    console.error(error)
  }
}

const loadActiveScene = async () => {
  try {
    const data = await api.get('/api/scenes/active')
    activeScene.value = data
  } catch (error: any) {
    console.log('No active scene or scene not set')
    activeScene.value = null
  }
}

const switchToScene = async (scene: Scene) => {
  try {
    await api.post(`/api/scenes/switch/${scene.id}`, { manual: true })
    ElMessage.success(`已切换到: ${scene.name}`)
    activeScene.value = scene
    manualMode.value = true
  } catch (error) {
    ElMessage.error('切换失败')
    console.error(error)
  }
}

const clearOverride = async () => {
  try {
    await api.post('/api/scenes/clear-override')
    ElMessage.success('已切换为自动检测模式')
    manualMode.value = false
    await loadActiveScene()
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  }
}

const editScene = (scene: Scene) => {
  formData.value = { ...scene }
  showEditDialog.value = true
}

const validateHotkey = async () => {
  if (!formData.value.hotkey) {
    hotkeyError.value = ''
    return
  }

  try {
    const data = await api.post('/api/scenes/validate-hotkey', {
      hotkey: formData.value.hotkey,
      scene_id: formData.value.id
    })
    
    if (!data.valid) {
      hotkeyError.value = data.message
    } else {
      hotkeyError.value = ''
    }
  } catch (error) {
    console.error('Hotkey validation error:', error)
  }
}

const addAppRule = () => {
  if (newAppRule.value.trim()) {
    formData.value.app_rules.push(newAppRule.value.trim())
    newAppRule.value = ''
  }
}

const removeAppRule = (index: number) => {
  formData.value.app_rules.splice(index, 1)
}

const saveScene = async () => {
  if (!formData.value.name || !formData.value.prompt) {
    ElMessage.warning('请填写场景名称和提示词')
    return
  }

  if (hotkeyError.value) {
    ElMessage.warning('请解决快捷键冲突')
    return
  }

  try {
    const isEdit = !!formData.value.id
    
    if (isEdit) {
      await api.put(`/api/scenes/${formData.value.id}`, formData.value)
      ElMessage.success('场景已更新')
    } else {
      await api.post('/api/scenes', formData.value)
      ElMessage.success('场景已创建')
    }
    
    closeDialog()
    await loadScenes()
  } catch (error: any) {
    ElMessage.error(error.detail || '保存失败')
    console.error(error)
  }
}

const deleteScene = async (scene: Scene) => {
  if (!confirm(`确定删除场景 "${scene.name}"？`)) {
    return
  }

  try {
    await api.del(`/api/scenes/${scene.id}`)
    ElMessage.success('场景已删除')
    await loadScenes()
  } catch (error: any) {
    ElMessage.error(error.detail || '删除失败')
    console.error(error)
  }
}

const exportScenes = async () => {
  try {
    const data = await api.get('/api/scenes/export/json?include_builtin=false')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'voicetype-scenes.json'
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success('场景已导出')
  } catch (error) {
    ElMessage.error('导出失败')
    console.error(error)
  }
}

const importScenes = async () => {
  try {
    const data = JSON.parse(importData.value)
    
    const result = await api.post('/api/scenes/import', {
      scenes: data.scenes,
      merge: importMerge.value,
    })
    
    ElMessage.success(`已导入 ${result.imported} 个场景`)
    showImportDialog.value = false
    importData.value = ''
    await loadScenes()
  } catch (error) {
    ElMessage.error('导入失败：格式错误')
    console.error(error)
  }
}

const closeDialog = () => {
  showAddDialog.value = false
  showEditDialog.value = false
  hotkeyError.value = ''
  formData.value = {
    id: '',
    name: '',
    prompt: '',
    icon: '💬',
    hotkey: '',
    app_rules: [],
  }
}

onMounted(() => {
  loadScenes()
  loadActiveScene()
})
</script>

<style scoped>
.scene-manager {
  padding: 0;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-lg);
}

.unified-card {
  background: white;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-light);
  overflow: hidden;
}

.card-header {
  padding: var(--space-lg);
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-secondary);
}

.card-title {
  font-size: 18px;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card-hint-block {
  padding: var(--space-md);
  background: #e6f7ff;
  border-left: 4px solid var(--primary-color);
  margin: var(--space-lg);
  border-radius: var(--radius-small);
  font-size: var(--font-sm);
  color: #0050b3;
}

.form-section {
  padding: var(--space-lg);
  border-bottom: 1px solid var(--border-light);
}

.form-section:last-child {
  border-bottom: none;
}

.form-section-title {
  font-size: 16px;
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-md);
}

.stats-actions-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-md);
}

.stats-group {
  display: flex;
  gap: var(--space-md);
}

.stat-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-small);
}

.stat-label {
  font-size: var(--font-sm);
  color: var(--text-secondary);
}

.stat-value {
  font-size: var(--font-base);
  font-weight: var(--font-bold);
  color: var(--primary-color);
}

.actions-group {
  display: flex;
  gap: var(--space-sm);
}

.active-scene-section {
  border-bottom: 1px solid var(--border-light);
}

.active-scene-banner {
  padding: var(--space-md);
  background: #f0f8ff;
  border: 1px solid var(--primary-color);
  border-left: 4px solid var(--primary-color);
  border-radius: var(--radius-small);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.banner-content {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.scene-icon {
  font-size: 24px;
}

.scene-name {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.scenes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-md);
}

.scene-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-md);
  transition: all var(--duration-fast);
}

.scene-card:hover {
  box-shadow: var(--shadow-light);
}

.scene-card.active {
  border-color: var(--primary-color);
  background: #f0f8ff;
}

.scene-card.disabled {
  opacity: 0.5;
}

.scene-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-sm);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-light);
}

.scene-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex: 1;
}

.card-icon {
  font-size: 24px;
  line-height: 1;
}

.scene-title-row h4 {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.scene-meta {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.meta-item {
  font-size: var(--font-xs);
  color: var(--text-secondary);
}

.scene-actions {
  display: flex;
  gap: var(--space-xs);
  flex-shrink: 0;
}

.scene-body {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.badge {
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-small);
  font-size: 11px;
  font-weight: var(--font-semibold);
  margin-left: var(--space-xs);
}

.badge-success {
  background: var(--success-color);
  color: white;
}

.badge-warning {
  background: var(--warning-color);
  color: white;
}

.badge-primary {
  background: #e6f7ff;
  color: var(--primary-color);
}

.btn-icon {
  padding: var(--space-xs);
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: var(--radius-small);
  transition: all var(--duration-fast) var(--ease-in-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: var(--bg-secondary);
  color: var(--primary-color);
}

.btn-icon.btn-danger:hover {
  background: #fff1f0;
  color: var(--error-color);
}

.form-row {
  display: flex;
  gap: var(--space-md);
}

.form-group {
  margin-bottom: var(--space-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--space-sm);
  font-weight: var(--font-regular);
  color: var(--text-primary);
  font-size: var(--font-sm);
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: var(--space-sm) 12px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-small);
  font-size: var(--font-sm);
  font-family: inherit;
  color: var(--text-primary);
  background: var(--bg-primary);
  transition: border-color var(--duration-fast) var(--ease-in-out),
              box-shadow var(--duration-fast) var(--ease-in-out);
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px #e6f7ff;
}

.form-group input::placeholder,
.form-group textarea::placeholder {
  color: var(--text-muted);
}

.form-help {
  margin-top: var(--space-xs);
  font-size: var(--font-xs);
  color: var(--text-secondary);
  line-height: var(--leading-normal);
}

.form-error {
  margin-top: var(--space-xs);
  font-size: var(--font-xs);
  color: var(--error-color);
}

.checkbox-label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  cursor: pointer;
  font-weight: var(--font-regular);
  font-size: var(--font-sm);
  color: var(--text-primary);
  user-select: none;
  padding: var(--space-sm);
  border-radius: var(--radius-small);
  transition: background var(--duration-fast) var(--ease-in-out);
}

.checkbox-label:hover {
  background: var(--bg-hover);
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  margin: 0;
  flex-shrink: 0;
}

.checkbox-label span {
  line-height: var(--leading-normal);
}

.app-rules-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  margin-top: var(--space-sm);
}

.app-rule-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
  background: var(--primary-color);
  color: white;
  border-radius: var(--radius-small);
  font-size: 13px;
}

.tag-remove {
  border: none;
  background: white;
  color: white;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 14px;
}

.tag-remove:hover {
  background: white;
}

.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn var(--duration-fast) var(--ease-in-out);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.dialog {
  background: var(--bg-primary);
  border-radius: var(--radius-large);
  width: 500px;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-base);
  animation: slideUp var(--duration-normal) var(--ease-in-out);
}

@keyframes slideUp {
  from { 
    opacity: 0;
    transform: translateY(20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

.dialog-large {
  width: 700px;
}

.dialog-header {
  padding: var(--space-lg) var(--space-xl);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dialog-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.dialog-close {
  border: none;
  background: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-small);
  transition: background var(--duration-fast) var(--ease-in-out);
}

.dialog-close:hover {
  background: var(--bg-secondary);
}

.dialog-body {
  padding: var(--space-xl);
  overflow-y: auto;
}

.dialog-footer {
  padding: var(--space-md) var(--space-xl) var(--space-xl);
  border-top: 1px solid var(--border-light);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
}

@media (max-width: 900px) {
  .stats-actions-row {
    flex-direction: column;
    align-items: stretch;
  }
  .scenes-grid {
    grid-template-columns: 1fr;
  }
}
</style>
