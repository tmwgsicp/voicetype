<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
  首次启动引导 —— 苹果风：克制、排版建层级、线性图标、单一强调色。
-->
<template>
  <transition name="ob-fade">
    <div class="onboarding" v-if="show">
      <div class="ob-backdrop"></div>
      <div class="ob-card">
        <!-- Step 1: 欢迎 -->
        <div v-if="step === 1" class="ob-step">
          <div class="ob-mark"><NavIcon name="voiceprint" /></div>
          <h2 class="ob-title">欢迎使用 VoiceType</h2>
          <p class="ob-sub">按一下快捷键，说话就能变成文字</p>
          <div class="ob-list">
            <div class="ob-row"><span class="ob-ic"><NavIcon name="lock" /></span><div><b>本地离线，隐私优先</b><span>Sherpa-ONNX 本地识别，数据不上云，完全免费</span></div></div>
            <div class="ob-row"><span class="ob-ic"><NavIcon name="sparkle" /></span><div><b>AI 自动优化</b><span>去口语、加标点、纠错（配置 LLM 后）</span></div></div>
            <div class="ob-row"><span class="ob-ic"><NavIcon name="scenes" /></span><div><b>场景自适应</b><span>按当前应用自动切换写作风格</span></div></div>
          </div>
        </div>

        <!-- Step 2: 怎么用 -->
        <div v-else-if="step === 2" class="ob-step">
          <h2 class="ob-title">三步开始</h2>
          <p class="ob-sub">在任意应用里都能用</p>
          <div class="ob-steps">
            <div class="ob-howto"><span class="num">1</span><div><b>按 <kbd>F9</kbd></b><span>或点击屏幕底部的胶囊，开始录音（变红）</span></div></div>
            <div class="ob-howto"><span class="num">2</span><div><b>说话</b><span>说完停顿约 1 秒，自动识别</span></div></div>
            <div class="ob-howto"><span class="num">3</span><div><b>自动上屏</b><span>文字直接输入到光标位置</span></div></div>
          </div>
        </div>

        <!-- Step 3: 可选 AI + 开始 -->
        <div v-else class="ob-step">
          <h2 class="ob-title">开启 AI 优化（可选）</h2>
          <p class="ob-sub">配置一个 OpenAI 兼容的 LLM Key，识别结果会自动去口语、加标点、纠错</p>
          <div class="ob-note">
            不配置也能用（本地识别 + 基础上屏），随时可在「模型与密钥」里补上。
          </div>
          <div class="ob-cta">
            <button class="ob-btn ghost" @click="openSettings">现在去配置</button>
            <button class="ob-btn ghost" @click="complete">稍后再说</button>
          </div>
        </div>

        <!-- 底部：进度 + 操作 -->
        <div class="ob-footer">
          <div class="ob-dots">
            <span v-for="i in 3" :key="i" class="dot" :class="{ on: i === step }"></span>
          </div>
          <div class="ob-actions">
            <button v-if="step > 1" class="ob-btn text" @click="step--">上一步</button>
            <button v-if="step === 1" class="ob-btn text" @click="skip">跳过</button>
            <button v-if="step < 3" class="ob-btn primary" @click="step++">继续</button>
            <button v-else class="ob-btn primary" @click="complete">开始使用</button>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import NavIcon from './NavIcon.vue'

const visible = ref(false)
const done = ref(false)
const step = ref(1)
const show = computed(() => visible.value && !done.value)

function skip() { done.value = true; localStorage.setItem('voicetype_guide_completed', 'true') }
function complete() { done.value = true; localStorage.setItem('voicetype_guide_completed', 'true') }
function openSettings() { /* 已在设置窗口内，关闭引导即到「模型与密钥」由用户自行点开 */ complete() }

onMounted(() => {
  if (!localStorage.getItem('voicetype_guide_completed')) visible.value = true
})
</script>

<style scoped>
.onboarding { position: fixed; inset: 0; z-index: 9999; display: flex; align-items: center; justify-content: center; }
.ob-backdrop { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.32); backdrop-filter: blur(3px); }

.ob-card {
  position: relative; width: 460px; max-width: calc(100vw - 40px);
  background: var(--bg-card); border-radius: 18px;
  box-shadow: var(--shadow-pop); padding: var(--space-2xl) var(--space-2xl) var(--space-lg);
  display: flex; flex-direction: column;
}
.ob-step { min-height: 300px; }

.ob-mark {
  width: 56px; height: 56px; border-radius: 14px; margin: 0 auto var(--space-lg);
  background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center;
}
.ob-mark :deep(svg) { width: 30px; height: 30px; }

.ob-title { font-size: var(--text-title); font-weight: var(--weight-bold); color: var(--label); text-align: center; margin: 0 0 6px; letter-spacing: -0.3px; }
.ob-sub { font-size: var(--text-subhead); color: var(--label-secondary); text-align: center; margin: 0 0 var(--space-xl); line-height: 1.5; }

.ob-list, .ob-steps { display: flex; flex-direction: column; gap: var(--space-md); }
.ob-row, .ob-howto { display: flex; gap: var(--space-md); align-items: flex-start; }
.ob-row div, .ob-howto div { display: flex; flex-direction: column; }
.ob-row b, .ob-howto b { font-size: var(--text-body); color: var(--label); font-weight: var(--weight-semibold); }
.ob-row span, .ob-howto span { font-size: var(--text-footnote); color: var(--label-secondary); margin-top: 1px; }

.ob-ic { width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0; background: var(--accent-tint); display: flex; align-items: center; justify-content: center; }
.ob-ic :deep(svg) { width: 17px; height: 17px; color: var(--accent); }
.ob-howto .num {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent); color: #fff; font-size: var(--text-footnote); font-weight: var(--weight-bold);
  display: flex; align-items: center; justify-content: center;
}
kbd { font-family: var(--font-system); background: var(--bg-fill); border-radius: 5px; padding: 1px 7px; font-size: var(--text-footnote); }

.ob-note {
  background: var(--bg-fill); border-radius: var(--radius-control); padding: var(--space-md);
  font-size: var(--text-footnote); color: var(--label-secondary); margin: var(--space-lg) 0;
}
.ob-cta { display: flex; gap: var(--space-sm); }

.ob-footer { display: flex; align-items: center; justify-content: space-between; margin-top: var(--space-lg); padding-top: var(--space-md); }
.ob-dots { display: flex; gap: 6px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: var(--label-quaternary); transition: all 0.2s; }
.dot.on { background: var(--accent); width: 18px; border-radius: 3px; }
.ob-actions { display: flex; gap: var(--space-sm); }

.ob-btn { font-family: var(--font-system); font-size: var(--text-body); border-radius: var(--radius-control); padding: 7px 16px; cursor: pointer; border: 1px solid transparent; transition: all var(--duration-fast) var(--ease-in-out); }
.ob-btn.primary { background: var(--accent); color: #fff; }
.ob-btn.primary:hover { background: var(--accent-hover); }
.ob-btn.text { background: none; color: var(--label-secondary); }
.ob-btn.text:hover { color: var(--label); }
.ob-btn.ghost { flex: 1; background: var(--bg-fill); color: var(--label); }
.ob-btn.ghost:hover { background: var(--bg-fill-hover); }

.ob-fade-enter-active, .ob-fade-leave-active { transition: opacity 0.25s ease; }
.ob-fade-enter-from, .ob-fade-leave-to { opacity: 0; }
</style>
