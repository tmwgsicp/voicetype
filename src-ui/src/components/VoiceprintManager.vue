<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="voiceprint-manager">
    <div class="content-grid">
      <!-- Header Card -->
      <section class="unified-card">
        <div class="card-header">
          <div class="header-left">
            <span class="card-title">声纹识别</span>
            <p class="card-subtitle">只识别您的声音，自动过滤杂音和他人声音</p>
          </div>
          <div class="header-right">
            <el-switch
              v-model="enabled"
              @change="toggleEnabled"
              active-text="已启用"
              inactive-text="已禁用"
            />
          </div>
        </div>

        <div v-if="enabled && voiceprints.length === 0" class="card-hint-block" style="background: #fff7e6; border-left-color: var(--warning-color); color: #d46b08;">
          ⚠ 声纹识别已启用，但未注册声纹。请先注册您的声纹，系统才能识别您的声音。
        </div>

        <div v-else-if="enabled && voiceprints.length > 0" class="card-hint-block" style="background: #f6ffed; border-left-color: var(--success-color); color: #389e0d;">
          ✓ 声纹识别运行中 · 已注册 {{ voiceprints.length }} 个声纹 · 按 F9 录音 → 自动验证声纹 → 通过后识别文字
        </div>

        <!-- Form Section: Voiceprints List or Empty State -->
        <div class="form-section" style="border-bottom: none;">
          <div v-if="voiceprints.length === 0" class="empty-state">
            <div class="empty-icon">🎙</div>
            <div class="empty-title">还没有声纹</div>
            <div class="empty-text">注册您的声纹后，系统将只识别您的声音</div>
            <el-button type="primary" size="large" @click="showEnrollDialog = true">
              注册声纹
            </el-button>
          </div>

          <div v-else>
            <div class="section-header">
              <h3 class="form-section-title">已注册声纹 ({{ voiceprints.length }})</h3>
              <el-button type="primary" size="small" @click="showEnrollDialog = true">
                + 注册新声纹
              </el-button>
            </div>

            <div class="voiceprints-list">
              <div
                v-for="vp in voiceprints"
                :key="vp.speaker_id"
                class="voiceprint-item"
              >
                <div class="vp-header">
                  <div class="vp-info">
                    <span class="vp-icon">🎙</span>
                    <div class="vp-details">
                      <div class="vp-name">{{ vp.speaker_id }}</div>
                      <div class="vp-meta">
                        {{ vp.provider }} · {{ vp.embedding_size }} 维向量
                        <span v-if="vp.enrollment_rounds" class="rounds-badge">
                          已录 {{ vp.enrollment_rounds }} 轮
                        </span>
                      </div>
                    </div>
                  </div>
                  <el-button
                    type="danger"
                    size="small"
                    :icon="Delete"
                    circle
                    @click="deleteVoiceprint(vp.speaker_id)"
                  />
                </div>

                <div class="vp-body">
                  <div class="threshold-control">
                    <div class="threshold-header">
                      <label>相似度阈值</label>
                      <span class="threshold-value">{{ vp.threshold.toFixed(2) }}</span>
                    </div>
                    <el-slider
                      v-model="vp.threshold"
                      :min="0.4"
                      :max="0.8"
                      :step="0.05"
                      :marks="{ 0.4: '实战推荐', 0.5: '平衡', 0.6: '严格' }"
                      @change="(val: number) => updateThreshold(vp.speaker_id, val)"
                    />
                    <div class="threshold-hint">
                      推荐 0.40-0.45（实战）· 0.50+ 容易误伤本人 · 太高会拒绝口音变化
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Enrollment Dialog -->
    <el-dialog
      v-model="showEnrollDialog"
      title="注册声纹"
      width="500px"
      :close-on-click-modal="false"
      @close="resetEnrollDialog"
    >
      <!-- Step 0: Input Speaker ID -->
      <div v-if="enrollStep === 0" class="enroll-content">
        <el-form :model="enrollData" label-width="80px">
          <el-form-item label="用户 ID">
            <el-input
              v-model="enrollData.speaker_id"
              placeholder="例如：user1"
              maxlength="32"
            />
          </el-form-item>
        </el-form>

        <div class="enroll-guide">
          <div class="guide-title">多轮录音说明</div>
          <ul class="guide-list">
            <li>需要录制 {{ totalRounds }} 轮语音，每轮 3-5 秒</li>
            <li>多轮录入可以提高识别准确率</li>
            <li>请在安静环境中，清晰朗读提示文字</li>
            <li>每轮保持正常音量和语速</li>
          </ul>
        </div>
      </div>

      <!-- Step 1: Recording -->
      <div v-if="enrollStep === 1" class="enroll-content">
        <div class="recording-ui">
          <div class="round-indicator">
            第 {{ enrollRound }} / {{ totalRounds }} 轮录音
          </div>
          
          <div class="suggested-text-box">
            <div class="suggested-label">请朗读以下文字：</div>
            <div class="suggested-text">{{ suggestedText }}</div>
          </div>

          <div class="recording-visual">
            <div class="recording-pulse"></div>
            <div class="recording-time">{{ recordingTime }}s / 5s</div>
          </div>

          <div class="recording-hint">
            录音已开始，请清晰朗读上方文字...
          </div>
        </div>
      </div>

      <!-- Step 2: Processing -->
      <div v-if="enrollStep === 2" class="enroll-content">
        <div class="processing-ui">
          <el-icon class="is-loading" :size="48" color="#1890ff">
            <Loading />
          </el-icon>
          <div class="processing-text">正在提取声纹特征...</div>
        </div>
      </div>

      <!-- Step 3: Success -->
      <div v-if="enrollStep === 3" class="enroll-content">
        <div class="success-ui">
          <el-icon :size="64" color="#52c41a">
            <SuccessFilled />
          </el-icon>
          <div class="success-text">声纹注册成功！</div>
        </div>
      </div>

      <template #footer>
        <div v-if="enrollStep === 0">
          <el-button @click="showEnrollDialog = false">取消</el-button>
          <el-button type="primary" @click="startRecording" :disabled="!enrollData.speaker_id.trim()">
            {{ enrollRound === 1 ? '开始录音' : `继续第${enrollRound}轮` }}
          </el-button>
        </div>
        <div v-if="enrollStep === 1">
          <el-button type="danger" @click="stopRecording">停止录音</el-button>
        </div>
        <div v-if="enrollStep === 3">
          <el-button type="primary" @click="resetEnrollDialog">完成</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Loading, SuccessFilled } from '@element-plus/icons-vue'
import { useApi } from '../composables/useApi'

const api = useApi()

const enabled = ref(false)
const threshold = ref(0.40)
const voiceprints = ref<any[]>([])
const showEnrollDialog = ref(false)
const enrollStep = ref(0)
const enrollRound = ref(1)
const totalRounds = 3
const isRecording = ref(false)
const recordingTime = ref(0)
const enrollData = ref({ speaker_id: '', audioBlob: null as Blob | null })

const suggestedTexts = [
  '今天天气真不错，我正在测试语音输入系统。',
  '这是第二轮声纹录入，请保持自然语速。',
  '最后一轮了，感谢您的耐心配合。'
]
const suggestedText = ref(suggestedTexts[0])

let recordingTimer: ReturnType<typeof setInterval> | null = null
let audioContext: AudioContext | null = null
let mediaStream: MediaStream | null = null
let audioProcessor: ScriptProcessorNode | null = null
let audioBuffers: Float32Array[] = []

const toggleEnabled = async () => {
  try {
    await api.post('/api/voiceprint/settings/enable', { 
      enabled: enabled.value,
      threshold: threshold.value,
      provider: 'local'
    })
    ElMessage.success(enabled.value ? '声纹识别已启用' : '声纹识别已禁用')
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || error?.message || '设置失败'
    ElMessage.error(errorMsg)
    enabled.value = !enabled.value
  }
}

const loadVoiceprints = async () => {
  try {
    const data = await api.get('/api/voiceprint/list')
    voiceprints.value = data.voiceprints || []
  } catch (error) {
    voiceprints.value = []
    console.error('Failed to load voiceprints:', error)
  }
}

const startRecording = async () => {
  try {
    enrollStep.value = 1
    isRecording.value = true
    recordingTime.value = 0
    audioBuffers = []

    audioContext = new AudioContext({ sampleRate: 16000 })
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const source = audioContext.createMediaStreamSource(mediaStream)
    
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1)
    
    audioProcessor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0)
      audioBuffers.push(new Float32Array(inputData))
    }

    source.connect(audioProcessor)
    audioProcessor.connect(audioContext.destination)

    recordingTimer = setInterval(() => {
      recordingTime.value++
      if (recordingTime.value >= 5) {
        stopRecording()
      }
    }, 1000)
  } catch (error) {
    ElMessage.error('无法访问麦克风')
    enrollStep.value = 0
  }
}

const stopRecording = () => {
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }

  if (audioProcessor) {
    audioProcessor.disconnect()
    audioProcessor = null
  }

  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }

  if (audioContext) {
    audioContext.close()
    audioContext = null
  }

  isRecording.value = false

  if (audioBuffers.length > 0) {
    enrollData.value.audioBlob = createWavBlob(audioBuffers, 16000)
    processEnrollment()
  } else {
    ElMessage.error('录音数据为空')
    enrollStep.value = 0
  }
}

const createWavBlob = (buffers: Float32Array[], sampleRate: number): Blob => {
  const totalLength = buffers.reduce((sum, buf) => sum + buf.length, 0)
  const pcmData = new Int16Array(totalLength)
  let offset = 0
  for (const buf of buffers) {
    for (let i = 0; i < buf.length; i++) {
      pcmData[offset++] = Math.max(-1, Math.min(1, buf[i])) * 0x7FFF
    }
  }

  const wavHeader = new ArrayBuffer(44)
  const view = new DataView(wavHeader)
  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + pcmData.byteLength, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, pcmData.byteLength, true)

  return new Blob([wavHeader, pcmData.buffer], { type: 'audio/wav' })
}

const processEnrollment = async () => {
  enrollStep.value = 2
  try {
    if (!enrollData.value.audioBlob) {
      throw new Error('录音数据为空')
    }
    const audioBuffer = await enrollData.value.audioBlob.arrayBuffer()
    const uint8Array = new Uint8Array(audioBuffer)
    let audio_base64 = ''
    const chunkSize = 8192
    for (let i = 0; i < uint8Array.length; i += chunkSize) {
      const chunk = uint8Array.subarray(i, Math.min(i + chunkSize, uint8Array.length))
      audio_base64 += String.fromCharCode.apply(null, Array.from(chunk))
    }
    audio_base64 = btoa(audio_base64)
    const response = await api.post('/api/voiceprint/enroll', {
      speaker_id: enrollData.value.speaker_id,
      audio_base64: audio_base64,
    })
    
    if (enrollRound.value < totalRounds) {
      enrollRound.value++
      suggestedText.value = suggestedTexts[Math.min(enrollRound.value - 1, suggestedTexts.length - 1)]
      ElMessage.success(`第${enrollRound.value - 1}轮完成，继续第${enrollRound.value}轮`)
      enrollStep.value = 0
      recordingTime.value = 0
      audioBuffers = []
    } else {
      enrollStep.value = 3
      await loadVoiceprints()
      ElMessage.success(`声纹注册完成！共${totalRounds}轮`)
    }
  } catch (error: any) {
    const errorMsg = error?.detail || error?.message || '注册失败'
    ElMessage.error(errorMsg)
    showEnrollDialog.value = false
    enrollStep.value = 0
    enrollRound.value = 1
    enrollData.value = { speaker_id: '', audioBlob: null }
  }
}

const resetEnrollDialog = () => {
  showEnrollDialog.value = false
  enrollStep.value = 0
  enrollRound.value = 1
  suggestedText.value = suggestedTexts[0]
  isRecording.value = false
  enrollData.value = { speaker_id: '', audioBlob: null }
  
  if (recordingTimer) {
    clearInterval(recordingTimer)
    recordingTimer = null
  }
}

const updateThreshold = async (speakerId: string, threshold: number) => {
  try {
    await api.post(`/api/voiceprint/${speakerId}/threshold`, { threshold })
    ElMessage.success('阈值已更新')
    await loadVoiceprints()
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const deleteVoiceprint = async (speakerId: string) => {
  try {
    await ElMessageBox.confirm(`确定删除声纹 "${speakerId}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await api.del(`/api/voiceprint/${speakerId}`)
    ElMessage.success('已删除')
    await loadVoiceprints()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(async () => {
  await loadVoiceprints()
  try {
    const settings = await api.get('/api/voiceprint/settings')
    enabled.value = settings.enabled || false
    threshold.value = settings.threshold || 0.5
  } catch (error) {
    console.error('Failed to load voiceprint settings:', error)
  }
})

// 监听阈值变化，自动保存
watch(threshold, async (newValue) => {
  if (!enabled.value) return  // 仅在启用时保存
  
  try {
    await api.post('/api/voiceprint/settings/enable', {
      enabled: enabled.value,
      threshold: newValue,
      provider: 'local'
    })
  } catch (error: any) {
    console.error('Failed to update threshold:', error)
  }
})

</script>

<style scoped>
.voiceprint-manager {
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
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left {
  flex: 1;
}

.card-title {
  font-size: 18px;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  display: block;
  margin-bottom: 4px;
}

.card-subtitle {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin: 0;
}

.header-right {
  margin-left: var(--space-lg);
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.section-header h3 {
  margin: 0;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: var(--space-xl) 0;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: var(--space-md);
}

.empty-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.empty-text {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-lg);
}

/* Voiceprints List */
.voiceprints-list {
  display: grid;
  gap: var(--space-md);
}

.voiceprint-item {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-md);
  background: var(--bg-primary);
  transition: all var(--duration-fast);
}

.voiceprint-item:hover {
  box-shadow: var(--shadow-light);
}

.vp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-md);
}

.vp-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.vp-icon {
  font-size: 24px;
}

.vp-name {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.vp-meta {
  font-size: var(--font-xs);
  color: var(--text-secondary);
}

.rounds-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--primary-color);
  color: white;
  border-radius: var(--radius-small);
  font-size: 11px;
  font-weight: 600;
  margin-left: var(--space-sm);
}

.vp-body {
  padding-top: var(--space-md);
  border-top: 1px solid var(--border-light);
}

.threshold-control {
  padding: var(--space-sm) 0;
}

.threshold-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.threshold-header label {
  font-size: var(--font-sm);
  color: var(--text-primary);
  font-weight: var(--font-regular);
}

.threshold-value {
  font-size: var(--font-sm);
  color: var(--primary-color);
  font-weight: var(--font-semibold);
}

.threshold-hint {
  font-size: var(--font-xs);
  color: var(--text-secondary);
  margin-top: var(--space-sm);
  line-height: 1.5;
  word-break: keep-all;
  white-space: normal;
}

/* Enrollment Dialog */
.enroll-content {
  padding: var(--space-lg) 0;
}

.enroll-guide {
  background: var(--bg-secondary);
  padding: var(--space-md);
  border-radius: var(--radius-base);
  margin-top: var(--space-md);
}

.guide-title {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-sm);
}

.guide-list {
  margin: 0;
  padding-left: var(--space-lg);
  font-size: var(--font-sm);
  color: var(--text-secondary);
  line-height: 2;
}

.recording-ui,
.processing-ui,
.success-ui {
  text-align: center;
  padding: var(--space-xl) 0;
}

.round-indicator {
  font-size: var(--font-lg);
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  background: #e6f7ff;
  border-radius: var(--radius-base);
  display: inline-block;
}

.suggested-text-box {
  background: var(--bg-secondary);
  padding: var(--space-md);
  border-radius: var(--radius-base);
  margin-bottom: var(--space-lg);
}

.suggested-label {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}

.suggested-text {
  font-size: var(--font-base);
  color: var(--text-primary);
  line-height: var(--leading-normal);
  font-weight: var(--font-semibold);
}

.recording-visual {
  margin: var(--space-xl) 0;
}

.recording-pulse {
  width: 80px;
  height: 80px;
  margin: 0 auto var(--space-md);
  background: var(--error-color);
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
}

.recording-time {
  font-size: var(--font-xl);
  font-weight: 700;
  color: var(--error-color);
}

.recording-hint {
  font-size: var(--font-sm);
  color: var(--text-secondary);
}

.processing-text,
.success-text {
  font-size: var(--font-base);
  color: var(--text-primary);
  margin-top: var(--space-md);
}
</style>
