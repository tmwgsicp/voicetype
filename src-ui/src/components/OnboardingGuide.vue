<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="onboarding-guide" v-if="showGuide && !guideCompleted">
    <div class="guide-overlay" @click="skipGuide"></div>
    <div class="guide-content">
      <!-- Step 1: Welcome -->
      <div v-if="currentStep === 1" class="guide-step">
        <div class="guide-icon">🎤</div>
        <h2>欢迎使用 VoiceType</h2>
        <p class="guide-desc">AI 驱动的语音输入工具，让打字变得更简单</p>
        <ul class="guide-features">
          <li>✨ 本地 AI 识别，完全免费</li>
          <li>🔒 隐私保护，数据不上云</li>
          <li>⚡ 实时转文字，流畅输出</li>
          <li>🎯 智能纠错，自动加标点</li>
        </ul>
        <div class="guide-actions">
          <button class="btn-secondary" @click="skipGuide">跳过</button>
          <button class="btn-primary" @click="nextStep">开始使用 →</button>
        </div>
      </div>

      <!-- Step 2: LLM Configuration (Optional) -->
      <div v-if="currentStep === 2" class="guide-step">
        <div class="guide-icon">🤖</div>
        <h2>AI 智能优化（可选）</h2>
        <p class="guide-desc">配置 LLM API Key 可以自动纠正标点、优化语句</p>
        
        <div class="llm-info">
          <div class="info-box info-local">
            <h3>🎯 不配置：使用本地模式</h3>
            <ul>
              <li>✅ 完全免费</li>
              <li>✅ 隐私安全</li>
              <li>✅ 基础的语音识别转文字</li>
              <li>⚠️ 不会自动加标点和优化语句</li>
            </ul>
          </div>
          
          <div class="info-box info-cloud">
            <h3>✨ 配置后：AI 智能模式</h3>
            <ul>
              <li>✨ 自动纠正标点符号</li>
              <li>✨ 优化语句通顺度</li>
              <li>✨ 场景智能适配</li>
              <li>💰 需要 LLM API（如阿里云、OpenAI）</li>
            </ul>
          </div>
        </div>

        <div class="llm-config-hint">
          <p>💡 推荐：先跳过此步骤，体验基础功能</p>
          <p>稍后可在「设置」中配置 LLM API Key</p>
        </div>

        <div class="guide-actions">
          <button class="btn-secondary" @click="prevStep">← 上一步</button>
          <button class="btn-link" @click="openSettings">现在配置</button>
          <button class="btn-primary" @click="nextStep">跳过 →</button>
        </div>
      </div>

      <!-- Step 3: Quick Tutorial -->
      <div v-if="currentStep === 3" class="guide-step">
        <div class="guide-icon">📖</div>
        <h2>快速上手</h2>
        <p class="guide-desc">三种方式开始语音输入</p>
        
        <div class="tutorial-cards">
          <div class="tutorial-card">
            <div class="card-icon">🖱️</div>
            <h3>方式一：点击悬浮窗</h3>
            <p>点击悬浮窗（初始在左上角，可拖拽移动）</p>
          </div>
          
          <div class="tutorial-card">
            <div class="card-icon">⌨️</div>
            <h3>方式二：快捷键 F9</h3>
            <p>在任意应用中按 <kbd>F9</kbd> 键</p>
          </div>
          
          <div class="tutorial-card">
            <div class="card-icon">🗣️</div>
            <h3>方式三：语音唤醒</h3>
            <p>说"小明同学"或"你好语音"</p>
            <p class="card-note">需在设置中启用</p>
          </div>
        </div>

        <div class="guide-tips">
          <p class="tips-title">💡 使用技巧</p>
          <ul>
            <li>悬浮窗有三种状态：
              <ul class="status-list">
                <li><span class="status-bar loading"></span> 蓝色 - 正在初始化</li>
                <li><span class="status-bar standby"></span> 青色 - 待机中</li>
                <li><span class="status-bar recording"></span> 红色 - 正在录音</li>
              </ul>
            </li>
            <li>说完后停顿 1 秒左右自动识别完成</li>
            <li>识别结果会自动输入到光标位置</li>
            <li>可以拖拽悬浮窗到任意位置</li>
          </ul>
        </div>

        <div class="guide-actions">
          <button class="btn-secondary" @click="prevStep">← 上一步</button>
          <button class="btn-primary" @click="completeGuide">开始体验 🚀</button>
        </div>
      </div>

      <!-- Progress -->
      <div class="guide-progress">
        <div 
          v-for="i in 3" 
          :key="i" 
          class="progress-dot"
          :class="{ active: i === currentStep }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['open-settings'])

const showGuide = ref(false)
const guideCompleted = ref(false)
const currentStep = ref(1)

const nextStep = () => {
  if (currentStep.value < 3) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const skipGuide = () => {
  showGuide.value = false
  localStorage.setItem('voicetype_guide_completed', 'true')
}

const openSettings = () => {
  emit('open-settings')
  skipGuide()
}

const completeGuide = () => {
  guideCompleted.value = true
  showGuide.value = false
  localStorage.setItem('voicetype_guide_completed', 'true')
  ElMessage.success('🎉 设置完成！按 F9 或点击悬浮窗开始录音')
}

onMounted(() => {
  // 检查是否首次使用
  const completed = localStorage.getItem('voicetype_guide_completed')
  if (!completed) {
    showGuide.value = true
  }
})
</script>

<style scoped>
.onboarding-guide {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.guide-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
}

.guide-content {
  position: relative;
  background: white;
  border-radius: 16px;
  padding: 40px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.guide-step {
  text-align: center;
}

.guide-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.guide-step h2 {
  font-size: 28px;
  margin-bottom: 12px;
  color: #1890ff;
}

.guide-desc {
  font-size: 16px;
  color: #666;
  margin-bottom: 24px;
}

.guide-features {
  text-align: left;
  list-style: none;
  padding: 0;
  margin: 24px 0;
}

.guide-features li {
  padding: 12px;
  margin: 8px 0;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 15px;
}

.permission-check {
  margin: 24px 0;
}

.check-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 16px;
}

.check-item.active {
  background: #e6f7ff;
  border: 2px solid #1890ff;
}

.check-icon {
  font-size: 24px;
}

.permission-help {
  margin: 24px 0;
  padding: 20px;
  background: #fff7e6;
  border: 2px solid #ffa940;
  border-radius: 8px;
  text-align: left;
}

.help-title {
  font-weight: bold;
  margin-bottom: 12px;
  color: #d46b08;
}

.permission-help ol {
  margin: 12px 0;
  padding-left: 24px;
}

.permission-help li {
  margin: 8px 0;
}

.tutorial-cards {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  margin: 24px 0;
}

.tutorial-card {
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
  text-align: left;
}

.card-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.tutorial-card h3 {
  font-size: 16px;
  margin-bottom: 8px;
  color: #333;
}

.tutorial-card p {
  font-size: 14px;
  color: #666;
  margin: 4px 0;
}

.card-note {
  font-size: 12px;
  color: #999;
  font-style: italic;
}

.tutorial-card kbd {
  display: inline-block;
  padding: 2px 8px;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.guide-tips {
  margin: 24px 0;
  padding: 20px;
  background: #e6f7ff;
  border-radius: 8px;
  text-align: left;
}

.tips-title {
  font-weight: bold;
  margin-bottom: 12px;
  color: #0050b3;
}

.guide-tips ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.guide-tips li {
  padding: 8px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-list {
  list-style: none !important;
  padding-left: 16px !important;
  margin-top: 8px;
}

.status-list li {
  padding: 4px 0 !important;
}

.status-bar {
  display: inline-block;
  width: 24px;
  height: 12px;
  border-radius: 2px;
  margin-right: 8px;
  vertical-align: middle;
}

.status-bar.loading {
  background: linear-gradient(90deg, #096dd9, #1890ff, #40a9ff);
  animation: pulse 1s ease-in-out infinite;
}

.status-bar.standby {
  background: linear-gradient(90deg, #08979c, #13c2c2, #36cfc9);
}

.status-bar.recording {
  background: linear-gradient(90deg, #a8071a, #ff4d4f, #ff7a45);
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.guide-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 32px;
}

.btn-primary, .btn-secondary, .btn-link {
  padding: 12px 32px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary {
  background: #1890ff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #40a9ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
}

.btn-primary:disabled {
  background: #d9d9d9;
  cursor: not-allowed;
}

.btn-secondary {
  background: #f5f5f5;
  color: #666;
}

.btn-secondary:hover {
  background: #e6e6e6;
}

.btn-link {
  background: transparent;
  color: #1890ff;
  text-decoration: underline;
  padding: 8px 16px;
}

.guide-progress {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 24px;
}

.progress-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #d9d9d9;
  transition: all 0.3s;
}

.progress-dot.active {
  width: 24px;
  border-radius: 4px;
  background: #1890ff;
}

/* LLM Configuration Styles */
.llm-info {
  display: flex;
  gap: 16px;
  margin: 24px 0;
}

.info-box {
  flex: 1;
  padding: 20px;
  border-radius: 12px;
  border: 2px solid;
}

.info-box h3 {
  font-size: 16px;
  margin: 0 0 12px 0;
}

.info-box ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.info-box li {
  padding: 6px 0;
  font-size: 14px;
  color: #666;
}

.info-local {
  border-color: #52c41a;
  background: #f6ffed;
}

.info-cloud {
  border-color: #1890ff;
  background: #e6f7ff;
}

.llm-config-hint {
  background: #fff7e6;
  border: 1px solid #ffd666;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.llm-config-hint p {
  margin: 4px 0;
  color: #d48806;
  font-size: 14px;
}

/* 滚动条样式 */
.guide-content::-webkit-scrollbar {
  width: 6px;
}

.guide-content::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 3px;
}

.guide-content::-webkit-scrollbar-thumb:hover {
  background: #bfbfbf;
}
</style>
