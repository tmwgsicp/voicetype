<!--
  Copyright (C) 2026 VoiceType Contributors
  Licensed under AGPL-3.0

  文本动作编辑器：增删改「文本编辑菜单」（选中文字按 F8）里的预设动作。
  每个动作 = 名称 + 说明 + 给 AI 的改写指令（prompt）。存进 config.text_actions，保存即时生效。
-->
<template>
  <div class="ta-manager">
    <div class="card-hint-block">
      💡 这些动作会出现在「文本编辑菜单」里（选中文字按 <b>F8</b>）。可自由增删改：动作名、一句话说明，以及给 AI 的改写指令。改完点<b>保存</b>即时生效。
    </div>

    <div class="ta-list">
      <div v-for="(a, i) in actions" :key="a.id" class="ta-card">
        <div class="ta-card-head">
          <div class="ta-fields">
            <input class="ta-input ta-label" v-model="a.label" placeholder="动作名（如 翻译）" maxlength="8" />
            <input class="ta-input ta-hint" v-model="a.hint" placeholder="一句话说明（如 中英互译）" maxlength="20" />
          </div>
          <div class="ta-ops">
            <button class="icon-btn" :disabled="i === 0" @click="move(i, -1)" title="上移">↑</button>
            <button class="icon-btn" :disabled="i === actions.length - 1" @click="move(i, 1)" title="下移">↓</button>
            <button class="icon-btn danger" @click="remove(i)" title="删除">✕</button>
          </div>
        </div>
        <textarea
          class="ta-input ta-prompt"
          v-model="a.prompt"
          rows="2"
          placeholder="给 AI 的改写指令，例如：把下面的文本翻译成英文，保持原意…"
        ></textarea>
      </div>
      <p v-if="actions.length === 0" class="ta-empty">还没有动作，点下方「添加动作」或「恢复默认」。</p>
    </div>

    <div class="ta-actions-row">
      <button class="btn" @click="add">＋ 添加动作</button>
      <button class="btn" @click="resetDefault">恢复默认</button>
      <span class="spacer"></span>
      <span v-if="msg" class="ta-msg" :class="msgType">{{ msg }}</span>
      <button class="btn btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../composables/useApi'

interface TA { id: string; label: string; hint: string; prompt: string }

const api = useApi()
const actions = ref<TA[]>([])
let defaults: TA[] = []
const saving = ref(false)
const msg = ref('')
const msgType = ref<'ok' | 'err'>('ok')

function uid() {
  return 'act-' + Math.random().toString(36).slice(2, 8) + Date.now().toString(36).slice(-4)
}

function flash(m: string, t: 'ok' | 'err' = 'ok') {
  msg.value = m
  msgType.value = t
  setTimeout(() => { if (msg.value === m) msg.value = '' }, 3200)
}

async function load() {
  try {
    const r = await api.get<{ actions: TA[]; defaults: TA[] }>('/api/edit/actions/full')
    actions.value = (r.actions || []).map(a => ({ ...a }))
    defaults = (r.defaults || []).map(a => ({ ...a }))
  } catch {
    flash('加载失败', 'err')
  }
}

function add() {
  actions.value.push({ id: uid(), label: '', hint: '', prompt: '' })
}
function remove(i: number) {
  actions.value.splice(i, 1)
}
function move(i: number, d: number) {
  const j = i + d
  if (j < 0 || j >= actions.value.length) return
  const arr = actions.value
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}
function resetDefault() {
  actions.value = defaults.map(a => ({ ...a }))
  flash('已载入默认，记得点保存', 'ok')
}

async function save() {
  const clean = actions.value
    .map(a => ({ id: a.id, label: (a.label || '').trim(), hint: (a.hint || '').trim(), prompt: (a.prompt || '').trim() }))
    .filter(a => a.label && a.prompt)
  if (!clean.length) {
    flash('至少保留一个填了「名称」和「指令」的动作', 'err')
    return
  }
  const dropped = actions.value.length - clean.length
  saving.value = true
  try {
    await api.saveConfig({ text_actions: clean })
    await load()
    flash(dropped > 0 ? `已保存（跳过 ${dropped} 个未填完整的）` : '已保存，菜单即时生效', 'ok')
  } catch {
    flash('保存失败', 'err')
  }
  saving.value = false
}

onMounted(load)
</script>

<style scoped>
.ta-manager { display: flex; flex-direction: column; gap: var(--space-lg); }

.card-hint-block {
  padding: var(--space-md);
  background: var(--accent-tint);
  border-left: 4px solid var(--accent);
  border-radius: var(--radius-small);
  font-size: var(--text-subhead);
  color: var(--label-secondary);
  line-height: 1.6;
}
.card-hint-block b { color: var(--label); font-weight: var(--font-semibold); }

.ta-list { display: flex; flex-direction: column; gap: var(--space-md); }

.ta-card {
  background: var(--bg-card);
  border: 1px solid var(--separator);
  border-radius: var(--radius-card);
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.ta-card-head { display: flex; align-items: flex-start; gap: var(--space-sm); }
.ta-fields { display: flex; gap: var(--space-sm); flex: 1; min-width: 0; }

.ta-input {
  border: 1px solid var(--separator-opaque);
  border-radius: var(--radius-control);
  padding: 7px 10px;
  font-size: var(--text-body);
  color: var(--label);
  background: var(--bg-card);
  font-family: inherit;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.ta-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-tint);
}
.ta-label { width: 120px; flex-shrink: 0; font-weight: var(--font-medium); }
.ta-hint { flex: 1; min-width: 0; }
.ta-prompt { width: 100%; resize: vertical; line-height: 1.5; }

.ta-ops { display: flex; gap: 4px; flex-shrink: 0; }

.ta-empty { color: var(--label-tertiary); font-size: var(--text-subhead); padding: var(--space-lg); text-align: center; }

.ta-actions-row { display: flex; align-items: center; gap: var(--space-sm); }
.spacer { flex: 1; }

.ta-msg { font-size: var(--text-subhead); }
.ta-msg.ok { color: var(--green); }
.ta-msg.err { color: var(--red); }
</style>
