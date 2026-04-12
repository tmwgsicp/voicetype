<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="rule-manager">
    <div class="content-grid">
      <section class="unified-card">
        <div class="card-header">
          <span class="card-title">术语规则管理</span>
        </div>
        
        <div class="card-hint-block">
          自动纠正语音识别中的专业术语、产品名、人名等常见错误
        </div>

        <!-- Form Section: Stats & Actions -->
        <div class="form-section">
          <div class="stats-actions-row">
            <div class="stats-group">
              <span class="stat-badge">
                <span class="stat-label">总规则</span>
                <span class="stat-value">{{ rules.length }}</span>
              </span>
              <span class="stat-badge">
                <span class="stat-label">已启用</span>
                <span class="stat-value">{{ enabledCount }}</span>
              </span>
            </div>
            <div class="actions-group">
              <button class="btn btn-sm" @click="showImportDialog = true">导入</button>
              <button class="btn btn-sm" @click="exportRules">导出</button>
              <button class="btn btn-primary" @click="showAddDialog = true">+ 新建规则</button>
            </div>
          </div>
        </div>

        <!-- Form Section: Category Filter -->
        <div class="form-section">
          <h3 class="form-section-title">分类筛选</h3>
          <div class="category-filter">
            <button 
              :class="['filter-btn', { active: selectedCategory === null }]"
              @click="selectedCategory = null"
            >
              全部 ({{ rules.length }})
            </button>
            <button 
              v-for="cat in categories" 
              :key="cat"
              :class="['filter-btn', { active: selectedCategory === cat }]"
              @click="selectedCategory = cat"
            >
              {{ categoryDisplayName(cat) }} ({{ categoryCount(cat) }})
            </button>
          </div>
        </div>

        <!-- Form Section: Rules List -->
        <div class="form-section" style="border-bottom: none;">
          <h3 class="form-section-title">规则列表</h3>
          <div class="rules-list">
            <div v-if="filteredRules.length === 0" class="empty-state">
              <p>暂无规则，点击"新建规则"添加第一条</p>
            </div>
            
            <div 
              v-for="rule in filteredRules" 
              :key="rule.id"
              :class="['rule-item', { disabled: !rule.enabled }]"
            >
              <div class="rule-content">
                <div class="rule-main">
                  <span class="rule-wrong">{{ rule.wrong }}</span>
                  <span class="rule-arrow">→</span>
                  <span class="rule-correct">{{ rule.correct }}</span>
                </div>
                <div class="rule-meta">
                  <span class="rule-category">{{ categoryDisplayName(rule.category) }}</span>
                  <span v-if="rule.case_sensitive" class="rule-flag">区分大小写</span>
                  <span v-if="rule.whole_word" class="rule-flag">全词匹配</span>
                </div>
              </div>
              <div class="rule-actions-cell">
                <label class="toggle-switch">
                  <input type="checkbox" :checked="rule.enabled" @change="toggleRule(rule)">
                  <span class="toggle-slider"></span>
                </label>
                <button class="btn-icon" @click="editRule(rule)" title="编辑">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                  </svg>
                </button>
                <button class="btn-icon btn-danger" @click="deleteRule(rule)" title="删除">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Add/Edit Dialog -->
    <div v-if="showAddDialog || showEditDialog" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog">
        <div class="dialog-header">
          <h3>{{ showEditDialog ? '编辑规则' : '新建规则' }}</h3>
          <button class="dialog-close" @click="closeDialog">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-group">
            <label>错误发音 *</label>
            <input v-model="formData.wrong" placeholder="例如：克劳德库德">
          </div>
          <div class="form-group">
            <label>正确写法 *</label>
            <input v-model="formData.correct" placeholder="例如：Claude Code">
          </div>
          <div class="form-group">
            <label>分类</label>
            <select v-model="formData.category">
              <option value="general">通用</option>
              <option value="tech">技术术语</option>
              <option value="product">产品名</option>
              <option value="person">人名</option>
              <option value="custom">自定义</option>
            </select>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="formData.case_sensitive">
              <span>区分大小写</span>
            </label>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="formData.whole_word">
              <span>全词匹配（仅匹配独立单词）</span>
            </label>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="closeDialog">取消</button>
          <button class="btn btn-primary" @click="saveRule">保存</button>
        </div>
      </div>
    </div>

    <!-- Import Dialog -->
    <div v-if="showImportDialog" class="dialog-overlay" @click.self="showImportDialog = false">
      <div class="dialog">
        <div class="dialog-header">
          <h3>导入规则</h3>
          <button class="dialog-close" @click="showImportDialog = false">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-group">
            <label>JSON 数据</label>
            <textarea v-model="importData" rows="10" placeholder='{"rules": [{"wrong": "...", "correct": "..."}]}'></textarea>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="importMerge">
              <span>合并模式（不清空现有规则）</span>
            </label>
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="showImportDialog = false">取消</button>
          <button class="btn btn-primary" @click="importRules">导入</button>
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

interface Rule {
  id: string
  wrong: string
  correct: string
  category: string
  enabled: boolean
  case_sensitive: boolean
  whole_word: boolean
}

const rules = ref<Rule[]>([])
const selectedCategory = ref<string | null>(null)
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const showImportDialog = ref(false)

const formData = ref({
  id: '',
  wrong: '',
  correct: '',
  category: 'general',
  case_sensitive: false,
  whole_word: false,
})

const importData = ref('')
const importMerge = ref(true)

const enabledCount = computed(() => rules.value.filter(r => r.enabled).length)

const categories = computed(() => {
  const cats = new Set(rules.value.map(r => r.category))
  return Array.from(cats).sort()
})

const filteredRules = computed(() => {
  if (selectedCategory.value === null) {
    return rules.value
  }
  return rules.value.filter(r => r.category === selectedCategory.value)
})

const categoryDisplayName = (cat: string) => {
  const names: Record<string, string> = {
    general: '通用',
    tech: '技术术语',
    product: '产品名',
    person: '人名',
    custom: '自定义',
  }
  return names[cat] || cat
}

const categoryCount = (cat: string) => {
  return rules.value.filter(r => r.category === cat).length
}

const loadRules = async () => {
  try {
    const data = await api.get('/api/rules')
    rules.value = data.rules
  } catch (error) {
    ElMessage.error('加载规则失败')
    console.error(error)
  }
}

const editRule = (rule: Rule) => {
  formData.value = { ...rule }
  showEditDialog.value = true
}

const saveRule = async () => {
  if (!formData.value.wrong || !formData.value.correct) {
    ElMessage.warning('请填写错误发音和正确写法')
    return
  }

  try {
    const isEdit = !!formData.value.id
    
    if (isEdit) {
      await api.put(`/api/rules/${formData.value.id}`, formData.value)
      ElMessage.success('规则已更新')
    } else {
      await api.post('/api/rules', formData.value)
      ElMessage.success('规则已创建')
    }
    
    closeDialog()
    await loadRules()
  } catch (error) {
    ElMessage.error('保存失败')
    console.error(error)
  }
}

const toggleRule = async (rule: Rule) => {
  try {
    await api.put(`/api/rules/${rule.id}`, { enabled: !rule.enabled })
    rule.enabled = !rule.enabled
  } catch (error) {
    ElMessage.error('更新失败')
    console.error(error)
  }
}

const deleteRule = async (rule: Rule) => {
  if (!confirm(`确定删除规则 "${rule.wrong} → ${rule.correct}"？`)) {
    return
  }

  try {
    await api.del(`/api/rules/${rule.id}`)
    ElMessage.success('规则已删除')
    await loadRules()
  } catch (error) {
    ElMessage.error('删除失败')
    console.error(error)
  }
}

const exportRules = async () => {
  try {
    const data = await api.get('/api/rules/export/json')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'voicetype-rules.json'
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success('规则已导出')
  } catch (error) {
    ElMessage.error('导出失败')
    console.error(error)
  }
}

const importRules = async () => {
  try {
    const data = JSON.parse(importData.value)
    
    const result = await api.post('/api/rules/import', {
      rules: data.rules,
      merge: importMerge.value,
    })
    
    ElMessage.success(`已导入 ${result.imported} 条规则`)
    showImportDialog.value = false
    importData.value = ''
    await loadRules()
  } catch (error) {
    ElMessage.error('导入失败：格式错误')
    console.error(error)
  }
}

const closeDialog = () => {
  showAddDialog.value = false
  showEditDialog.value = false
  formData.value = {
    id: '',
    wrong: '',
    correct: '',
    category: 'general',
    case_sensitive: false,
    whole_word: false,
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.rule-manager {
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

.category-filter {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.filter-btn {
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-small);
  background: white;
  cursor: pointer;
  font-size: var(--font-sm);
  color: var(--text-secondary);
  transition: all 0.2s;
}

.filter-btn:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.filter-btn.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.rules-list {}

.empty-state {
  padding: var(--space-xl);
  text-align: center;
  color: var(--text-secondary);
}

.rule-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border-light);
  transition: background var(--duration-fast);
}

.rule-item:last-child {
  border-bottom: none;
}

.rule-item:hover {
  background: var(--bg-secondary);
}

.rule-item.disabled {
  opacity: 0.5;
}

.rule-content {
  flex: 1;
}

.rule-main {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
  font-size: var(--font-base);
}

.rule-wrong {
  color: var(--error-color);
  font-weight: var(--font-semibold);
}

.rule-arrow {
  color: var(--text-secondary);
  font-size: var(--font-lg);
}

.rule-correct {
  color: var(--success-color);
  font-weight: var(--font-semibold);
}

.rule-meta {
  display: flex;
  gap: var(--space-sm);
  font-size: var(--font-xs);
}

.rule-category {
  padding: var(--space-xs) var(--space-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-small);
  color: var(--text-secondary);
  font-weight: var(--font-semibold);
}

.rule-flag {
  padding: var(--space-xs) var(--space-sm);
  background: #fff7e6;
  color: var(--warning-color);
  border-radius: var(--radius-small);
  font-weight: var(--font-semibold);
}

.rule-actions-cell {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

@media (max-width: 900px) {
  .stats-actions-row {
    flex-direction: column;
    align-items: stretch;
  }
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: 0.3s;
  border-radius: 24px;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

input:checked + .toggle-slider {
  background-color: var(--primary-color);
}

input:checked + .toggle-slider:before {
  transform: translateX(20px);
}

.btn-icon {
  padding: var(--space-xs);
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: var(--radius-small);
  transition: all var(--duration-fast) var(--ease-in-out);
}

.btn-icon:hover {
  background: var(--bg-secondary);
  color: var(--primary-color);
}

.btn-icon.btn-danger:hover {
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

.dialog-wide {
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
</style>