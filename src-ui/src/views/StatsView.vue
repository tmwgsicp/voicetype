<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0
-->
<template>
  <div class="content-grid">
    <!-- 概览卡片 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-value">{{ fmt(summary.total_chars) }}</div>
        <div class="stat-label">累计字数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ fmt(summary.today_chars) }}</div>
        <div class="stat-label">今日字数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">🔥 {{ summary.streak_days }}</div>
        <div class="stat-label">连续使用（天）</div>
      </div>
      <div class="stat-card highlight">
        <div class="stat-value">{{ typingSaved }}</div>
        <div class="stat-label">预计省下打字时间</div>
      </div>
    </div>

    <!-- 次要指标 -->
    <div class="mini-stats">
      <span>累计听写 <b>{{ fmt(summary.total_dictations) }}</b> 次</span>
      <span>本周 <b>{{ fmt(summary.week_chars) }}</b> 字</span>
      <span>使用 <b>{{ summary.active_days }}</b> 天</span>
      <span v-if="summary.first_use">自 {{ summary.first_use }} 起</span>
    </div>

    <!-- 每日趋势 -->
    <section class="unified-card">
      <div class="card-header">
        <span class="card-title">最近 30 天</span>
        <span class="card-sub">共 {{ fmt(daysTotal) }} 字</span>
      </div>
      <div class="chart">
        <div
          v-for="d in daily"
          :key="d.day"
          class="bar-wrap"
          :title="`${d.day}: ${d.chars} 字 / ${d.dictations} 次`"
        >
          <div class="bar" :style="{ height: barHeight(d.chars) }" :class="{ empty: d.chars === 0 }"></div>
        </div>
      </div>
      <div class="chart-axis">
        <span>{{ daily.length ? daily[0].day.slice(5) : '' }}</span>
        <span>今天</span>
      </div>
    </section>

    <!-- 场景分布 -->
    <section class="unified-card" v-if="scenes.length">
      <div class="card-header"><span class="card-title">场景分布</span></div>
      <div class="scene-list">
        <div v-for="s in scenes" :key="s.scene" class="scene-row">
          <span class="scene-name">{{ sceneName(s.scene) }}</span>
          <div class="scene-track">
            <div class="scene-fill" :style="{ width: scenePct(s.chars) }"></div>
          </div>
          <span class="scene-num">{{ fmt(s.chars) }} 字</span>
        </div>
      </div>
    </section>

    <div v-if="!loading && summary.total_chars === 0" class="empty-hint">
      还没有听写记录，按 F9 说几句试试吧 🎤
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useApi } from '../composables/useApi'

const api = useApi()
const loading = ref(true)

const summary = reactive<any>({
  total_chars: 0, total_words: 0, total_dictations: 0,
  today_chars: 0, today_dictations: 0, week_chars: 0,
  streak_days: 0, active_days: 0, est_typing_minutes: 0, first_use: null,
})
const daily = ref<Array<{ day: string; chars: number; dictations: number }>>([])
const scenes = ref<Array<{ scene: string; chars: number; dictations: number }>>([])

const maxChars = computed(() => Math.max(1, ...daily.value.map(d => d.chars)))
const daysTotal = computed(() => daily.value.reduce((a, d) => a + d.chars, 0))
const scenesMax = computed(() => Math.max(1, ...scenes.value.map(s => s.chars)))

const typingSaved = computed(() => {
  const m = summary.est_typing_minutes || 0
  if (m < 1) return '<1 分钟'
  if (m < 60) return `${Math.round(m)} 分钟`
  const h = Math.floor(m / 60)
  const mm = Math.round(m % 60)
  return mm ? `${h} 小时 ${mm} 分` : `${h} 小时`
})

function fmt(n: number) {
  return (n ?? 0).toLocaleString('en-US')
}
function barHeight(chars: number) {
  return `${Math.max(2, Math.round((chars / maxChars.value) * 100))}%`
}
function scenePct(chars: number) {
  return `${Math.max(2, Math.round((chars / scenesMax.value) * 100))}%`
}
const SCENE_NAMES: Record<string, string> = {
  general: '通用', terminal: '终端', code: '编程', chat: '聊天',
  email: '邮件', doc: '文档', browser: '浏览器',
}
function sceneName(s: string) {
  return SCENE_NAMES[s] || s
}

onMounted(async () => {
  try {
    const [s, d, sc] = await Promise.all([
      api.getStatsSummary(),
      api.getStatsDaily(30),
      api.getStatsScenes(),
    ])
    Object.assign(summary, s)
    daily.value = d.days || []
    scenes.value = sc.scenes || []
  } catch (e) {
    console.error('Failed to load stats:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.content-grid { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-lg); }

.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md); }
.stat-card {
  background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-large);
  padding: var(--space-lg); text-align: center; box-shadow: var(--shadow-light);
}
.stat-card.highlight { background: var(--accent-tint); border-color: var(--accent-tint-strong); }
.stat-value { font-size: 26px; font-weight: 700; color: var(--primary-color); line-height: 1.2; }
.stat-label { font-size: var(--font-xs); color: var(--text-secondary); margin-top: 6px; }

.mini-stats { display: flex; flex-wrap: wrap; gap: var(--space-lg); justify-content: center;
  font-size: var(--font-sm); color: var(--text-secondary); }
.mini-stats b { color: var(--text-primary); }

.unified-card { background: var(--bg-card); border: 1px solid var(--border-light); border-radius: var(--radius-large);
  box-shadow: var(--shadow-light); overflow: hidden; }
.card-header { padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border-light);
  display: flex; justify-content: space-between; align-items: center; }
.card-title { font-size: 15px; font-weight: var(--font-semibold); }
.card-sub { font-size: var(--font-xs); color: var(--text-muted); }

.chart { display: flex; align-items: flex-end; gap: 3px; height: 140px; padding: var(--space-lg) var(--space-lg) var(--space-sm); }
.bar-wrap { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.bar { width: 100%; background: var(--accent); border-radius: 3px 3px 0 0;
  transition: height 0.3s var(--ease-in-out); min-height: 2px; }
.bar.empty { background: var(--border-light); }
.chart-axis { display: flex; justify-content: space-between; padding: 0 var(--space-lg) var(--space-md);
  font-size: var(--font-xs); color: var(--text-muted); }

.scene-list { padding: var(--space-lg); display: flex; flex-direction: column; gap: var(--space-md); }
.scene-row { display: flex; align-items: center; gap: var(--space-md); }
.scene-name { width: 64px; font-size: var(--font-sm); color: var(--text-primary); }
.scene-track { flex: 1; height: 10px; background: var(--bg-secondary); border-radius: 5px; overflow: hidden; }
.scene-fill { height: 100%; background: var(--accent); border-radius: 5px; }
.scene-num { width: 80px; text-align: right; font-size: var(--font-xs); color: var(--text-secondary); }

.empty-hint { text-align: center; color: var(--text-muted); padding: var(--space-xl); font-size: var(--font-sm); }

@media (max-width: 720px) { .stat-cards { grid-template-columns: repeat(2, 1fr); } }
</style>
