<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="settings-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><NavIcon name="voiceprint" /></div>
        <span class="brand-name">VoiceType</span>
      </div>
      <nav class="nav">
        <button :class="['nav-item', { active: activeTab === 'overview' }]" @click="activeTab = 'overview'">
          <NavIcon name="overview" /><span>概览</span>
        </button>

        <div class="nav-group">听写</div>
        <button :class="['nav-item', { active: activeTab === 'api' }]" @click="activeTab = 'api'">
          <NavIcon name="api" /><span>模型与密钥</span>
        </button>
        <button :class="['nav-item', { active: activeTab === 'general' }]" @click="activeTab = 'general'">
          <NavIcon name="general" /><span>快捷键与启动</span>
        </button>

        <div class="nav-group">个性化</div>
        <button :class="['nav-item', { active: activeTab === 'scenes' }]" @click="activeTab = 'scenes'">
          <NavIcon name="scenes" /><span>场景</span>
        </button>
        <button :class="['nav-item', { active: activeTab === 'rules' }]" @click="activeTab = 'rules'">
          <NavIcon name="rules" /><span>术语规则</span>
        </button>
        <button :class="['nav-item', { active: activeTab === 'voiceprint' }]" @click="activeTab = 'voiceprint'">
          <NavIcon name="voiceprint" /><span>声纹</span>
        </button>

        <div class="nav-group">数据</div>
        <button :class="['nav-item', { active: activeTab === 'stats' }]" @click="activeTab = 'stats'">
          <NavIcon name="stats" /><span>统计</span>
        </button>
        <button :class="['nav-item', { active: activeTab === 'history' }]" @click="activeTab = 'history'">
          <NavIcon name="history" /><span>历史</span>
        </button>
      </nav>
    </aside>

    <main class="content">
      <!-- Overview -->
      <div v-if="activeTab === 'overview'" class="page">
        <h1 class="page-title">概览</h1>
        <OverviewView @go="activeTab = $event" />
      </div>

      <!-- API Config Tab -->
      <div v-if="activeTab === 'api'" class="tab-content">
        <h1 class="page-title">模型与密钥</h1>
        <div class="content-grid">
          <!-- Main Config Card -->
          <section class="unified-card">
            <div class="card-hint-block">ASR 和 LLM 可共用同一个阿里云 DashScope API Key</div>

            <!-- ASR Section -->
            <div class="form-section">
              <h3 class="form-section-title">语音识别 (ASR)</h3>
              
              <div class="form-group">
                <label>ASR 提供商</label>
                <select v-model="config.asr_provider" @change="onProviderChange">
                  <option value="sherpa">Sherpa-ONNX（本地离线，推荐）</option>
                  <option value="aliyun">阿里云 DashScope（云端高精度）</option>
                  <option value="tencent">腾讯云实时语音识别（免费 5h/月）</option>
                </select>
                <p class="form-help">本地 ASR 完全免费且隐私保护，云端 ASR 提供更高准确率</p>
              </div>
              
              <div class="form-grid" v-if="config.asr_provider !== 'sherpa'">
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
              </div>
              
              <div class="form-group" v-if="config.asr_provider !== 'sherpa'">
                <label>识别模型</label>
                <select v-model="config.asr_model">
                  <optgroup label="阿里云 DashScope" v-if="config.asr_provider === 'aliyun'">
                    <option value="qwen3-asr-flash-realtime">Qwen3-ASR Flash（推荐）</option>
                  </optgroup>
                  <optgroup label="腾讯云实时 ASR" v-if="config.asr_provider === 'tencent'">
                    <option value="16k_zh_en">16k_zh_en - 中英混合（推荐）</option>
                    <option value="16k_zh">16k_zh - 纯中文</option>
                    <option value="16k_en">16k_en - 纯英文</option>
                  </optgroup>
                </select>
                <p class="form-help">{{ asrModelHelp }}</p>
              </div>
              
              <div v-if="config.asr_provider === 'sherpa'" class="sherpa-info-box">
                <div class="info-icon">✓</div>
                <div class="info-content">
                  <div class="info-title">本地 ASR 模式</div>
                  <div class="info-text">使用 Sherpa-ONNX 中英双语模型，完全本地运行，无需任何 API 密钥。模型已内置，开箱即用。</div>
                </div>
              </div>
              
              <div class="form-grid">
                <div class="form-group">
                  <label>VAD 静音阈值 (ms)</label>
                  <input type="number" v-model.number="config.asr_max_silence_ms" min="300" max="3000" step="100">
                  <p class="form-help">静音多久判断句子结束（推荐 800-1500ms）</p>
                </div>
                <div class="form-group">
                  <label>VAD 灵敏度阈值 ({{ config.asr_vad_threshold }})</label>
                  <input 
                    type="range" 
                    v-model.number="config.asr_vad_threshold" 
                    min="0.3" 
                    max="0.8" 
                    step="0.05"
                    class="slider"
                  >
                  <p class="form-help">越低越敏感，越高越不容易触发（0.5 默认，0.55 减少杂音，0.65 安静环境）</p>
                </div>
              </div>
            </div>

            <!-- KWS Section -->
            <div class="form-section">
              <h3 class="form-section-title">关键词唤醒 (Wake Word)</h3>

              <div class="switch-row">
                <div class="switch-text">
                  <span>启用语音唤醒功能</span>
                  <p class="form-help">基于本地 KWS 模型后台监听唤醒词，检测到后自动开始录音</p>
                </div>
                <label class="switch"><input type="checkbox" v-model="config.sherpa_kws_enabled"><span class="track"></span></label>
              </div>

              <div v-if="config.sherpa_kws_enabled" class="kws-info-box">
                <div class="info-icon">🎙️</div>
                <div class="info-content">
                  <div class="info-title">独立运行</div>
                  <div class="info-text">KWS 与 ASR 完全解耦，无论 ASR 选择本地还是云端，KWS 都基于本地模型运行，保护隐私且无延迟。</div>
                </div>
              </div>

              <div v-if="config.sherpa_kws_enabled" class="form-group">
                <label>唤醒词列表（每行一个）</label>
                <textarea
                  v-model="kwsKeywordsText"
                  @input="updateKeywords"
                  rows="4"
                  placeholder="小明同学&#10;你好语音&#10;开始听写&#10;语音助手"
                  style="font-family: inherit; resize: vertical; min-height: 100px;"
                ></textarea>
                <p class="form-help">要求：2-5个中文字，避免常用词汇。检测延迟 &lt;100ms</p>
              </div>
            </div>

            <!-- LLM Section -->
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
              <div class="form-grid">
                <div class="form-group">
                  <label>API 地址</label>
                  <input type="text" v-model="config.llm_base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1">
                  <p class="form-help">填 OpenAI 兼容接口的 Base URL（阿里云、腾讯云、DeepSeek、OpenAI 等均可）</p>
                </div>
                <div class="form-group">
                  <label>LLM Temperature</label>
                  <input type="number" v-model.number="config.llm_temperature" min="0" max="1" step="0.1">
                  <p class="form-help">控制输出随机性（0=确定性，1=创造性）</p>
                </div>
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
        <h1 class="page-title">术语规则</h1>
        <RuleManager />
      </div>

      <!-- Scenes Tab -->
      <div v-if="activeTab === 'scenes'" class="tab-content">
        <h1 class="page-title">场景</h1>
        <SceneManager />
      </div>

      <!-- Voiceprint Tab -->
      <div v-if="activeTab === 'voiceprint'" class="tab-content">
        <h1 class="page-title">声纹</h1>
        <VoiceprintManager />
      </div>

      <!-- General Settings Tab -->
      <div v-if="activeTab === 'general'" class="tab-content">
        <h1 class="page-title">快捷键与启动</h1>
        <div class="content-grid">
          <section class="unified-card">
            <div class="form-section">
              <h3 class="form-section-title">快捷键设置</h3>
              <div class="form-grid">
                <div class="form-group">
                  <label>听写快捷键</label>
                  <input type="text" v-model="config.hotkey" placeholder="<f9>">
                  <p class="form-help">按一下开始/结束录音（pynput 格式）</p>
                </div>
                <div class="form-group">
                  <label>文本编辑快捷键</label>
                  <input type="text" v-model="config.edit_hotkey" placeholder="<f8>">
                  <p class="form-help">选中文字后按它，弹预设动作菜单（默认 F8）</p>
                </div>
              </div>
              <div class="card-hint-block" style="margin: var(--space-md) 0 0;">
                💡 文本编辑：在任意应用里选中一段文字，按「文本编辑快捷键」，光标旁会弹出预设动作菜单（翻译 / 润色 / 精简 / 正式 / 要点），按数字键 1-5 或点击即可就地改写替换。需已配置 LLM。
              </div>
            </div>

            <div class="form-section">
              <div class="switch-row">
                <div class="switch-text"><span>启动时自动开始录音</span></div>
                <label class="switch"><input type="checkbox" v-model="config.auto_start_asr"><span class="track"></span></label>
              </div>
              <div class="switch-row">
                <div class="switch-text">
                  <span>根据当前应用自动切换场景</span>
                  <p class="form-help">关闭后只用手动选择的场景，不随应用自动切换</p>
                </div>
                <label class="switch"><input type="checkbox" v-model="config.auto_scene_enabled"><span class="track"></span></label>
              </div>
            </div>

            <div class="form-actions">
              <button class="btn btn-primary" @click="onSave">保存配置</button>
              <span v-if="saveStatus" :class="['save-status', statusColor]">{{ saveStatus }}</span>
            </div>
          </section>
        </div>
      </div>

      <!-- Stats Tab -->
      <div v-if="activeTab === 'stats'" class="tab-content">
        <h1 class="page-title">数据统计</h1>
        <StatsView />
      </div>

      <!-- History Tab -->
      <div v-if="activeTab === 'history'" class="tab-content">
        <h1 class="page-title">历史</h1>
        <HistoryView />
      </div>
    </main>
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
import StatsView from './StatsView.vue'
import HistoryView from './HistoryView.vue'
import OverviewView from './OverviewView.vue'
import NavIcon from '../components/NavIcon.vue'
import { loadConfigWithMigration } from '../utils/configMigration'

const api = useApi()
const ws = useWebSocket()

const activeTab = ref('overview')

const showAsrKey = ref(false)
const showAsrSecret = ref(false)
const showLlmKey = ref(false)
const saveStatus = ref('')
const statusColor = ref('')

const config = reactive({
  asr_provider: 'sherpa',
  asr_api_key: '',
  asr_secret_key: '',
  asr_model: 'sherpa-local',
  asr_max_silence_ms: 1200,
  asr_vad_threshold: 0.5,
  sherpa_kws_enabled: false,
  sherpa_keywords: ['小明同学', '你好语音'],
  llm_api_key: '',
  llm_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  llm_model: 'qwen-turbo',
  llm_temperature: 0.3,
  hotkey: '<f9>',
  edit_hotkey: '<f8>',
  auto_start_asr: false,
  auto_scene_enabled: true,
})

// KWS keywords as textarea text (one per line)
const kwsKeywordsText = ref('小明同学\n你好语音')

const updateKeywords = () => {
  config.sherpa_keywords = kwsKeywordsText.value
    .split('\n')
    .map(k => k.trim())
    .filter(k => k.length > 0)
}

const asrKeyPlaceholder = computed(() => {
  if (config.asr_provider === 'sherpa') return '本地模型，无需 API Key'
  return config.asr_provider === 'tencent' 
    ? 'AKID... (腾讯云 SecretId)' 
    : 'sk-... (阿里云 API Key)'
})

const asrKeyHelp = computed(() => {
  if (config.asr_provider === 'sherpa') return '使用本地 ONNX 模型，无需任何 API 密钥'
  return config.asr_provider === 'tencent'
    ? '腾讯云 SecretId，在控制台获取'
    : '阿里云 DashScope Key（与下方 LLM 同一个）。留空将自动使用 LLM 的 Key'
})

const asrModelHelp = computed(() => {
  if (config.asr_provider === 'sherpa') {
    return '完全本地运行，无需网络，隐私保护'
  }
  if (config.asr_provider === 'tencent') {
    return '推荐 16k_zh_en（中英混合），每月免费 5 小时'
  }
  return 'Qwen3-ASR 自带 VAD（静默不计费），实时流式识别，中英混合'
})

const onProviderChange = () => {
  if (config.asr_provider === 'sherpa') {
    config.asr_model = 'sherpa-local'
  } else if (config.asr_provider === 'tencent') {
    if (!config.asr_model || config.asr_model.startsWith('qwen') || config.asr_model === 'sherpa-local') {
      config.asr_model = '16k_zh_en'
    }
  } else {
    if (!config.asr_model || config.asr_model.startsWith('16k_') || config.asr_model === 'sherpa-local') {
      config.asr_model = 'qwen3-asr-flash-realtime'
    }
    // 阿里云 ASR 与 LLM 共用同一个 DashScope Key：ASR 未单独填时自动带入 LLM 的 Key（预置）
    if (!config.asr_api_key && config.llm_api_key) {
      config.asr_api_key = config.llm_api_key
    }
  }

  // KWS 与 ASR 完全独立，不再自动禁用
}

const onSave = async () => {
  try {
    // config.json 是唯一数据源，由后端独占持久化。
    // 未修改的 Key 以打码形式回传，后端会自动丢弃、保留原值。
    await api.saveConfig({ ...config })
    ElMessage.success('配置已保存')
    saveStatus.value = ''
    statusColor.value = 'success'
  } catch (error: any) {
    console.error('Save config error:', error)
    ElMessage.error('保存失败: ' + (error.message || '未知错误'))
    saveStatus.value = ''
    statusColor.value = 'error'
  }
}

const onTest = async () => {
  saveStatus.value = '测试 LLM 连接中...'
  statusColor.value = 'warning'
  
  try {
    const result = await api.post('/api/config/test', {})
    
    // Check LLM test result
    if (result.llm && result.llm.status === 'ok') {
      saveStatus.value = `✓ LLM 连接正常 (${result.llm.model})`
      statusColor.value = 'success'
      ElMessage.success(result.llm.message || 'LLM 连接测试通过')
    } else if (result.llm) {
      saveStatus.value = `✗ LLM 连接失败: ${result.llm.message}`
      statusColor.value = 'error'
      ElMessage.error(result.llm.message || 'LLM 连接测试失败')
    } else {
      saveStatus.value = '✗ 测试失败'
      statusColor.value = 'error'
      ElMessage.error('无法获取测试结果')
    }
  } catch (error: any) {
    saveStatus.value = '✗ 请求失败'
    statusColor.value = 'error'
    ElMessage.error(error.message || '网络请求失败')
  }
  
  setTimeout(() => { saveStatus.value = '' }, 5000)
}

const onToggle = async () => {
  try {
    await api.toggleRecording()
  } catch (error) {
    console.error('Failed to toggle recording:', error)
  }
}

onMounted(async () => {
  // 后端启动需要几秒（含模型预热），重试拉取配置，避免"配置加载失败"误报。
  let serverData: any = null
  for (let attempt = 0; attempt < 15; attempt++) {
    try {
      serverData = await api.getConfig()
      break
    } catch (error) {
      await new Promise(r => setTimeout(r, 600))
    }
  }

  if (!serverData) {
    console.error('Failed to load config after retries')
    ElMessage.warning('配置加载失败，使用默认值')
    return
  }

  // 加载并迁移配置；API Keys 由后端以打码形式返回，直接进 config 展示。
  const migrated = loadConfigWithMigration(config, serverData)
  Object.assign(config, migrated)
  if (config.sherpa_keywords && Array.isArray(config.sherpa_keywords)) {
    kwsKeywordsText.value = config.sherpa_keywords.join('\n')
  }
})
</script>

<style scoped>
.settings-shell {
  display: flex;
  height: 100vh;
  background: var(--bg-content);
}

/* 侧边栏：半透明材质 + 分组 + 选中态填充（macOS 设置观感） */
.sidebar {
  width: 210px;
  flex-shrink: 0;
  background: var(--bg-sidebar);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-right: 1px solid var(--separator);
  padding: var(--space-md) 10px var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}
.brand {
  display: flex; align-items: center; gap: var(--space-sm);
  padding: var(--space-sm) var(--space-sm) var(--space-lg);
}
.brand-mark {
  width: 26px; height: 26px; border-radius: 7px;
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
}
.brand-mark :deep(svg) { width: 15px; height: 15px; }
.brand-name { font-size: var(--text-headline); font-weight: var(--weight-semibold); color: var(--label); }

.nav-group {
  font-size: var(--text-caption); font-weight: var(--weight-semibold);
  color: var(--label-tertiary); padding: var(--space-md) var(--space-sm) 4px;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  width: 100%; padding: 7px 10px; border: none; background: none;
  border-radius: var(--radius-control); cursor: pointer;
  font-size: var(--text-body); color: var(--label); text-align: left;
  transition: background var(--duration-fast) var(--ease-in-out);
}
.nav-item :deep(svg) { color: var(--label-secondary); flex-shrink: 0; }
.nav-item:hover { background: var(--bg-fill); }
.nav-item.active { background: var(--accent); color: #fff; }
.nav-item.active :deep(svg) { color: #fff; }

/* 内容区 */
.content {
  flex: 1; min-width: 0; overflow-y: auto;
  padding: var(--space-2xl) var(--space-2xl) 60px;
}
.page { max-width: 780px; }
.page-title {
  font-size: var(--text-large-title); font-weight: var(--weight-bold);
  color: var(--label); letter-spacing: -0.4px; margin: 0 0 var(--space-xl);
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
  box-shadow: var(--shadow-card);
}

.btn-toggle:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-card);
}

.tab-content { }

.content-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  max-width: 780px;
}

/* 开关行：左文字右原生开关（iOS/macOS 观感） */
.switch-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--space-lg); padding: 6px 0;
}
.switch-row + .switch-row {
  border-top: 1px solid var(--separator); margin-top: var(--space-sm); padding-top: var(--space-md);
}
.switch-text > span { font-size: var(--text-body); color: var(--label); }
.switch-text .form-help { margin-top: 2px; }

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
  background: var(--accent-tint);
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
  box-shadow: 0 0 0 3px var(--accent-tint);
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

.sherpa-info-box {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-md);
  background: var(--bg-fill);
  border: 1px solid var(--separator);
  border-radius: var(--radius-base);
  margin-bottom: var(--space-md);
}

.kws-info-box {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-md);
  background: var(--bg-fill);
  border: 1px solid var(--separator);
  border-radius: var(--radius-base);
  margin-bottom: var(--space-md);
}

.info-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: white;
  border-radius: 50%;
  font-size: 18px;
  font-weight: bold;
}

.info-content {
  flex: 1;
}

.info-title {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--label);
  margin-bottom: 4px;
}

.info-text {
  font-size: var(--font-xs);
  color: var(--label-secondary);
  line-height: 1.5;
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
.btn-primary:hover { background: var(--accent-hover); }
.btn-sm { padding: var(--space-xs) 10px; font-size: var(--font-xs); }

.save-status { font-size: var(--font-xs); margin-left: var(--space-sm); }
.save-status.success { color: var(--success-color); }
.save-status.warning { color: var(--warning-color); }
.save-status.error { color: var(--error-color); }

@media (max-width: 900px) {
  .content-grid { 
    max-width: 100%;
    padding: 0 var(--space-sm);
  }
  .form-grid { grid-template-columns: 1fr; }
}
</style>
