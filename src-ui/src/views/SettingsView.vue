<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="settings-view">
    <div class="tabs-container">
      <div class="tabs">
        <button 
          :class="['tab', { active: activeTab === 'api' }]"
          @click="activeTab = 'api'"
        >
          API 配置
        </button>
        <button 
          :class="['tab', { active: activeTab === 'rules' }]"
          @click="activeTab = 'rules'"
        >
          术语规则
        </button>
        <button 
          :class="['tab', { active: activeTab === 'scenes' }]"
          @click="activeTab = 'scenes'"
        >
          场景管理
        </button>
        <button 
          :class="['tab', { active: activeTab === 'voiceprint' }]"
          @click="activeTab = 'voiceprint'"
        >
          声纹识别
        </button>
        <button 
          :class="['tab', { active: activeTab === 'general' }]"
          @click="activeTab = 'general'"
        >
          通用设置
        </button>
      </div>

      <!-- API Config Tab -->
      <div v-if="activeTab === 'api'" class="tab-content">
        <div class="content-grid">
          <!-- Original API Config (unchanged) -->
          <section class="unified-card">
            <div class="card-header">
              <span class="card-title">API 配置</span>
            </div>
            <div class="card-hint-block">ASR 和 LLM 可共用同一个阿里云 DashScope API Key</div>

            <div class="form-section">
              <h3 class="form-section-title">语音识别 (ASR)</h3>
              
              <div class="form-group">
                <label>ASR 提供商</label>
                <select v-model="config.asr_provider" @change="onProviderChange">
                  <option value="aliyun">阿里云 DashScope（推荐，Qwen3-ASR）</option>
                  <option value="tencent">腾讯云实时语音识别（免费 5h/月）</option>
                </select>
                <p class="form-help">选择语音识别提供商，可随时切换</p>
              </div>
              
              <div class="form-grid">
                <div class="form-group">
                  <label>API Key / SecretId</label>
                  <div class="input-row">
                    <input :type="showAsrKey ? 'text' : 'password'" v-model="config.asr_api_key" :placeholder="asrKeyPlaceholder">
                    <button class="btn btn-sm" @click="showAsrKey = !showAsrKey">{{ showAsrKey ? '隐藏' : '显示' }}</button>
                  </div>
                  <p class="form-help">{{ asrKeyHelp }}</p>
                </div>
                
                <div class="form-group" v-if="config.asr_provider === 'tencent'">
                  <label>SecretKey（仅腾讯云）</label>
                  <div class="input-row">
                    <input :type="showAsrSecret ? 'text' : 'password'" v-model="config.asr_secret_key" placeholder="腾讯云 SecretKey">
                    <button class="btn btn-sm" @click="showAsrSecret = !showAsrSecret">{{ showAsrSecret ? '隐藏' : '显示' }}</button>
                  </div>
                  <p class="form-help">腾讯云 API SecretKey，在控制台获取</p>
                </div>
                
                <div class="form-group">
                  <label>识别模型</label>
                  <select v-model="config.asr_model">
                    <optgroup label="阿里云 DashScope" v-if="config.asr_provider === 'aliyun'">
                      <option value="qwen3-asr-flash-realtime">Qwen3-ASR（推荐，自带 VAD，静默不计费）</option>
                    </optgroup>
                    <optgroup label="腾讯云实时 ASR" v-if="config.asr_provider === 'tencent'">
                      <option value="16k_zh_en">16k_zh_en - 中英混合（推荐）</option>
                      <option value="16k_zh">16k_zh - 纯中文</option>
                      <option value="16k_en">16k_en - 纯英文</option>
                    </optgroup>
                  </select>
                  <p class="form-help">{{ asrModelHelp }}</p>
                </div>
              </div>
            </div>

            <div class="form-section">
              <h3 class="form-section-title">大语言模型 (LLM)</h3>
              <div class="form-grid">
                <div class="form-group">
                  <label>API Key</label>
                  <div class="input-row">
                    <input :type="showLlmKey ? 'text' : 'password'" v-model="config.llm_api_key" placeholder="sk-...">
                    <button class="btn btn-sm" @click="showLlmKey = !showLlmKey">{{ showLlmKey ? '隐藏' : '显示' }}</button>
                  </div>
                  <p class="form-help">用于清理语音文本（去口语化、纠错、加标点）</p>
                </div>
                <div class="form-group">
                  <label>模型名称</label>
                  <input type="text" v-model="config.llm_model" placeholder="qwen-turbo">
                  <p class="form-help">推荐 qwen-turbo，任何 OpenAI 兼容模型均可</p>
                </div>
              </div>
              <div class="form-group">
                <label>API 地址</label>
                <input type="text" v-model="config.llm_base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1">
                <p class="form-help">填 OpenAI 兼容接口的 Base URL（阿里云、腾讯云、DeepSeek、OpenAI 等均可）</p>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn btn-primary" @click="onSave">保存配置</button>
              <button class="btn" @click="onTest">测试连接</button>
              <span v-if="saveStatus" :class="['save-status', statusColor]">{{ saveStatus }}</span>
            </div>
          </section>
        </div>
      </div>

      <!-- Rules Tab -->
      <div v-if="activeTab === 'rules'" class="tab-content">
        <RuleManager />
      </div>

      <!-- Scenes Tab -->
      <div v-if="activeTab === 'scenes'" class="tab-content">
        <SceneManager />
      </div>

      <!-- Voiceprint Tab -->
      <div v-if="activeTab === 'voiceprint'" class="tab-content">
        <VoiceprintManager />
      </div>

      <!-- General Settings Tab -->
      <div v-if="activeTab === 'general'" class="tab-content">
        <div class="content-grid">
          <section class="unified-card">
            <div class="card-header">
              <span class="card-title">快捷键与行为</span>
            </div>

            <div class="form-section">
              <h3 class="form-section-title">快捷键设置</h3>
              <div class="form-group">
                <label>全局录音快捷键</label>
                <input type="text" v-model="config.hotkey" placeholder="<f9>">
                <p class="form-help">格式：&lt;f9&gt; 或 &lt;ctrl&gt;+&lt;shift&gt;+v（使用 pynput 格式）</p>
              </div>
            </div>

            <div class="form-section">
              <h3 class="form-section-title">高级设置</h3>
              <div class="form-grid">
                <div class="form-group">
                  <label>VAD 静音阈值 (ms)</label>
                  <input type="number" v-model.number="config.asr_max_silence_ms" min="300" max="3000" step="100">
                  <p class="form-help">静音多久判断句子结束（推荐 800-1500ms）</p>
                </div>
                <div class="form-group">
                  <label>LLM Temperature</label>
                  <input type="number" v-model.number="config.llm_temperature" min="0" max="1" step="0.1">
                  <p class="form-help">控制输出随机性（0=确定性，1=创造性）</p>
                </div>
              </div>
            </div>

            <div class="form-section">
              <h3 class="form-section-title">启动行为</h3>
              <div class="form-group">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="config.auto_start_asr">
                  启动时自动开始录音
                </label>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn btn-primary" @click="onSave">保存配置</button>
              <span v-if="saveStatus" :class="['save-status', statusColor]">{{ saveStatus }}</span>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useApi } from '../composables/useApi'
import { useWebSocket } from '../composables/useWebSocket'
import StatusBar from '../components/StatusBar.vue'
import RuleManager from '../components/RuleManager.vue'
import SceneManager from '../components/SceneManager.vue'
import VoiceprintManager from '../components/VoiceprintManager.vue'

const api = useApi()
const ws = useWebSocket()

const activeTab = ref('api')

const showAsrKey = ref(false)
const showAsrSecret = ref(false)
const showLlmKey = ref(false)
const saveStatus = ref('')
const statusColor = ref('')

const config = reactive({
  asr_provider: 'aliyun',
  asr_api_key: '',
  asr_secret_key: '',
  asr_model: 'qwen3-asr-flash-realtime',
  llm_api_key: '',
  llm_base_url: '',
  llm_model: 'qwen-turbo',
  asr_max_silence_ms: 1200,
  llm_temperature: 0.3,
  hotkey: '<f9>',
  auto_start_asr: false,
})

const asrKeyPlaceholder = computed(() => {
  return config.asr_provider === 'tencent' 
    ? 'AKID... (腾讯云 SecretId)' 
    : 'sk-... (阿里云 API Key)'
})

const asrKeyHelp = computed(() => {
  return config.asr_provider === 'tencent'
    ? '腾讯云 SecretId，在控制台获取'
    : '阿里云 DashScope API Key，用于语音识别'
})

const asrModelHelp = computed(() => {
  if (config.asr_provider === 'tencent') {
    return '推荐：16k_zh（纯中文）或 16k_zh_en（中英混合），每月免费 5 小时'
  }
  return 'Qwen3-ASR 自带服务端 VAD，仅在说话时消耗 token，静默不计费'
})

const onProviderChange = () => {
  if (config.asr_provider === 'tencent') {
    config.asr_model = '16k_zh_en'
  } else {
    config.asr_model = 'qwen3-asr-flash-realtime'
  }
}

const onSave = async () => {
  try {
    await api.saveConfig(config)
    saveStatus.value = '配置已保存'
    statusColor.value = 'success'
    setTimeout(() => { saveStatus.value = '' }, 3000)
  } catch (error) {
    saveStatus.value = '保存失败'
    statusColor.value = 'error'
  }
}

const onTest = async () => {
  saveStatus.value = '测试连接中...'
  statusColor.value = 'warning'
  
  try {
    await api.getStatus()
    saveStatus.value = '连接正常'
    statusColor.value = 'success'
  } catch (error) {
    saveStatus.value = '连接失败'
    statusColor.value = 'error'
  }
  
  setTimeout(() => { saveStatus.value = '' }, 3000)
}

const onToggle = async () => {
  try {
    await api.toggleRecording()
  } catch (error) {
    console.error('Failed to toggle recording:', error)
  }
}

onMounted(async () => {
  try {
    const data = await api.getConfig()
    Object.assign(config, data)
  } catch (error) {
    console.error('Failed to load config:', error)
    // 配置加载失败不影响使用，使用默认值
    ElMessage.warning('配置加载失败，使用默认值')
  }
})
</script>

<style scoped>
.settings-view {
  min-height: 100vh;
  background: var(--bg-secondary);
}

/* 紧凑状态栏 */
.status-bar-compact {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-xl);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-light);
  box-shadow: var(--shadow-light);
}

.status-left {
  display: flex;
  align-items: center;
  gap: var(--space-xl);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 6px var(--space-md);
  background: var(--bg-secondary);
  border-radius: 20px;
  border: 1px solid var(--border-light);
}

.status-indicator.recording {
  background: #fff1f0;
  border-color: var(--error-color);
  animation: pulse-border 2s ease-in-out infinite;
}

@keyframes pulse-border {
  0%, 100% { border-color: var(--error-color); }
  50% { border-color: #ff7875; }
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #bfbfbf;
  border-radius: 50%;
}

.status-indicator.recording .status-dot {
  background: var(--error-color);
  animation: pulse-dot 1s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.2); }
}

.status-text {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.status-info {
  display: flex;
  gap: var(--space-lg);
}

.info-item {
  font-size: var(--font-sm);
  color: var(--text-secondary);
}

.btn-toggle {
  padding: var(--space-sm) var(--space-xl);
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--radius-base);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-in-out);
  box-shadow: 0 2px 8px #bae7ff;
}

.btn-toggle:hover {
  background: #40a9ff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px #bae7ff;
}

.tabs-container { 
  max-width: var(--width-wide);
  margin: 0 auto;
  padding: var(--space-xl);
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  border-bottom: 2px solid var(--border-light);
}

.tab {
  padding: 12px 24px;
  border: none;
  background: none;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.tab.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}

.tab-content {}

.content-grid { display: grid; grid-template-columns: 1fr; gap: var(--space-lg); }

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

.card-title { font-size: 18px; font-weight: var(--font-semibold); color: var(--text-primary); }

.card-hint-block {
  padding: var(--space-md);
  background: #e6f7ff;
  border-left: 4px solid var(--primary-color);
  margin: var(--space-lg);
  border-radius: var(--radius-small);
  font-size: var(--font-sm);
  color: #0050b3;
}

.form-section { padding: var(--space-lg); border-bottom: 1px solid var(--border-light); }
.form-section:last-child { border-bottom: none; }

.form-section-title { font-size: 16px; font-weight: var(--font-semibold); margin-bottom: var(--space-md); }

.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--space-md); }

.form-group { margin-bottom: var(--space-md); }
.form-group:last-child { margin-bottom: 0; }

.form-group label { 
  display: block;
  margin-bottom: var(--space-xs);
  font-weight: var(--font-regular);
  color: var(--text-primary);
}

.form-group input, .form-group select, .form-group textarea {
  width: 100%;
  padding: var(--space-sm);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-small);
  font-size: var(--font-sm);
}

.form-group input:focus, .form-group select:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px #e6f7ff;
}

.input-row { display: flex; gap: var(--space-sm); }
.input-row input { flex: 1; }

.form-help { 
  margin-top: var(--space-xs);
  font-size: var(--font-xs);
  color: var(--text-secondary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: normal;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
}

.form-actions {
  padding: var(--space-lg);
  display: flex;
  gap: var(--space-sm);
  align-items: center;
}

.btn {
  padding: var(--space-sm) var(--space-lg);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-small);
  background: white;
  cursor: pointer;
  font-size: var(--font-sm);
  transition: all 0.2s;
}

.btn:hover { border-color: var(--primary-color); color: var(--primary-color); }
.btn-primary { background: var(--primary-color); color: white; border-color: var(--primary-color); }
.btn-primary:hover { background: #0077cc; }
.btn-sm { padding: var(--space-xs) 10px; font-size: var(--font-xs); }

.save-status { font-size: var(--font-xs); margin-left: var(--space-sm); }
.save-status.success { color: var(--success-color); }
.save-status.warning { color: var(--warning-color); }
.save-status.error { color: var(--error-color); }

@media (max-width: 900px) {
  .content-grid { grid-template-columns: 1fr; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>
