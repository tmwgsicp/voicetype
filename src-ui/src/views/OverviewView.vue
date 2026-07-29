<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="overview">
    <!-- 状态卡：应用当前在做什么 -->
    <section class="status-card" :class="{ recording }">
      <div class="status-left">
        <span class="status-dot"></span>
        <div>
          <div class="status-title">{{ recording ? '正在录音…' : '待机中' }}</div>
          <div class="status-sub">{{ recording ? '再次按 F9 结束' : '按 F9 开始听写' }}</div>
        </div>
      </div>
      <kbd class="hotkey">F9</kbd>
    </section>

    <!-- 数据概览 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-value">{{ fmt(summary.today_chars) }}</div>
        <div class="stat-label">今日字数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ fmt(summary.total_chars) }}</div>
        <div class="stat-label">累计字数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ summary.streak_days }}<span class="unit">天</span></div>
        <div class="stat-label">连续使用</div>
      </div>
      <div class="stat-card accent">
        <div class="stat-value">{{ typingSaved }}</div>
        <div class="stat-label">省下打字时间</div>
      </div>
    </div>

    <!-- 最近听写 -->
    <section class="recent">
      <div class="section-head">
        <span class="section-title">最近听写</span>
        <button class="link" @click="emit('go', 'history')">查看全部 ›</button>
      </div>
      <div v-if="recent.length" class="recent-list">
        <div v-for="it in recent" :key="it.id" class="recent-item">
          <span class="recent-text">{{ it.text }}</span>
          <span class="recent-time">{{ it.time.slice(5) }}</span>
        </div>
      </div>
      <div v-else class="recent-empty">还没有听写记录，按 F9 说几句试试</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useApi } from '../composables/useApi'

const emit = defineEmits<{ go: [tab: string] }>()
const api = useApi()

const summary = reactive<any>({ total_chars: 0, today_chars: 0, streak_days: 0, est_typing_minutes: 0 })
const recent = ref<Array<{ id: number; text: string; time: string }>>([])
const recording = ref(false)
let poll: number | null = null

const typingSaved = computed(() => {
  const m = summary.est_typing_minutes || 0
  if (m < 1) return '<1 分'
  if (m < 60) return `${Math.round(m)} 分`
  return `${Math.floor(m / 60)} 时 ${Math.round(m % 60)} 分`
})
function fmt(n: number) { return (n ?? 0).toLocaleString('en-US') }

async function refresh() {
  try {
    const [s, h] = await Promise.all([api.getStatsSummary(), api.getHistory(5, 0, '')])
    Object.assign(summary, s)
    recent.value = (h.items || []).slice(0, 5)
  } catch {}
}

onMounted(async () => {
  await refresh()
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const port = await invoke<number>('get_port')
    poll = window.setInterval(async () => {
      try {
        const st = await (await fetch(`http://127.0.0.1:${port}/api/status`)).json()
        const wasRec = recording.value
        recording.value = !!st.is_recording
        if (wasRec && !recording.value) refresh()   // 录音结束刷新最近听写
      } catch {}
    }, 1000)
  } catch {}
})
onUnmounted(() => { if (poll) clearInterval(poll) })
</script>

<style scoped>
.overview { display: flex; flex-direction: column; gap: var(--space-xl); max-width: 760px; }

.status-card {
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bg-card); border-radius: var(--radius-card);
  padding: var(--space-lg) var(--space-xl); box-shadow: var(--shadow-card);
}
.status-left { display: flex; align-items: center; gap: var(--space-md); }
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--label-quaternary); }
.status-card.recording .status-dot { background: var(--red); animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.status-title { font-size: var(--text-title3); font-weight: var(--weight-semibold); color: var(--label); }
.status-sub { font-size: var(--text-subhead); color: var(--label-secondary); margin-top: 2px; }
.hotkey {
  font-family: var(--font-system); font-size: var(--text-subhead); color: var(--label-secondary);
  background: var(--bg-fill); padding: 4px 12px; border-radius: var(--radius-small);
}

.stat-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md); }
.stat-card {
  background: var(--bg-card); border-radius: var(--radius-card); padding: var(--space-lg);
  box-shadow: var(--shadow-card);
}
.stat-card.accent { background: linear-gradient(180deg, var(--accent-tint-strong), var(--bg-card)); }
.stat-value { font-size: 24px; font-weight: var(--weight-bold); color: var(--label); letter-spacing: -0.5px; }
.stat-value .unit { font-size: 14px; font-weight: var(--weight-medium); color: var(--label-secondary); margin-left: 2px; }
.stat-card.accent .stat-value { color: var(--accent); }
.stat-label { font-size: var(--text-footnote); color: var(--label-secondary); margin-top: 6px; }

.recent { background: var(--bg-card); border-radius: var(--radius-card); box-shadow: var(--shadow-card); overflow: hidden; }
.section-head { display: flex; align-items: center; justify-content: space-between; padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--separator); }
.section-title { font-size: var(--text-headline); font-weight: var(--weight-semibold); }
.link { border: none; background: none; color: var(--accent); font-size: var(--text-subhead); cursor: pointer; }
.link:hover { text-decoration: underline; }
.recent-list { display: flex; flex-direction: column; }
.recent-item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md); padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--separator); }
.recent-item:last-child { border-bottom: none; }
.recent-text { font-size: var(--text-body); color: var(--label); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-time { font-size: var(--text-footnote); color: var(--label-tertiary); flex-shrink: 0; }
.recent-empty { padding: var(--space-xl); text-align: center; color: var(--label-tertiary); font-size: var(--text-subhead); }

@media (max-width: 720px) { .stat-row { grid-template-columns: repeat(2, 1fr); } }
</style>
