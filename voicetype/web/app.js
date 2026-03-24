/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

const API = '';
let ws = null;

/* ==================== Tab Navigation ==================== */

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');

  if (tab === 'kb') {
    loadKBDocs();
    loadKBStats();
  }
}

/* ==================== Config ==================== */

async function loadConfig() {
  try {
    const r = await fetch(`${API}/api/config`);
    const c = await r.json();

    // ASR Provider
    const provider = c.asr_provider || 'aliyun';
    document.getElementById('asrProvider').value = provider;
    
    // ASR Keys
    document.getElementById('asrApiKey').value = c.asr_api_key || '';
    document.getElementById('asrSecretKey').value = c.asr_secret_key || '';
    document.getElementById('asrModel').value = c.asr_model || 'qwen3-asr-flash-realtime';
    
    // Update UI based on provider
    updateAsrProviderUI(provider);
    
    // LLM
    document.getElementById('llmApiKey').value = c.llm_api_key || '';
    document.getElementById('llmBaseUrl').value = c.llm_base_url || '';
    document.getElementById('llmModel').value = c.llm_model || 'qwen-turbo';

    const s = document.getElementById('asrMaxSilence');
    s.value = c.asr_max_silence_ms || 1200;
    document.getElementById('silenceVal').textContent = s.value;

    const t = document.getElementById('llmTemperature');
    t.value = c.llm_temperature || 0.3;
    document.getElementById('tempVal').textContent = t.value;

    const rg = document.getElementById('ragScoreThreshold');
    rg.value = c.rag_score_threshold || 0.5;
    document.getElementById('ragVal').textContent = rg.value;

    document.getElementById('hotkey').value = c.hotkey || '<f9>';
    document.getElementById('autoStartAsr').checked = c.auto_start_asr || false;
  } catch (e) {
    console.error('loadConfig:', e);
  }
}

async function saveConfig() {
  const el = document.getElementById('saveStatus');
  el.textContent = '保存中...';
  el.style.color = '';

  const data = {
    asr_provider: document.getElementById('asrProvider').value,
    asr_api_key: document.getElementById('asrApiKey').value,
    asr_secret_key: document.getElementById('asrSecretKey').value,
    asr_model: document.getElementById('asrModel').value,
    llm_api_key: document.getElementById('llmApiKey').value,
    llm_base_url: document.getElementById('llmBaseUrl').value,
    llm_model: document.getElementById('llmModel').value,
    asr_max_silence_ms: parseInt(document.getElementById('asrMaxSilence').value),
    llm_temperature: parseFloat(document.getElementById('llmTemperature').value),
    rag_score_threshold: parseFloat(document.getElementById('ragScoreThreshold').value),
    hotkey: document.getElementById('hotkey').value,
    auto_start_asr: document.getElementById('autoStartAsr').checked,
  };

  try {
    await fetch(`${API}/api/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    el.textContent = '已保存';
    el.style.color = 'var(--success-color)';
    setTimeout(() => { el.textContent = ''; }, 2500);
  } catch (e) {
    el.textContent = '保存失败';
    el.style.color = 'var(--error-color)';
  }
}

async function testConnection() {
  const el = document.getElementById('saveStatus');
  el.textContent = '测试中...';
  el.style.color = '';

  try {
    const r = await fetch(`${API}/api/config/test`, { method: 'POST' });
    const res = await r.json();
    const parts = [];
    if (res.llm) parts.push('LLM: ' + (res.llm.status === 'ok' ? 'OK' : 'FAIL'));
    if (res.asr) parts.push('ASR: ' + (res.asr.status === 'ok' ? 'OK' : 'FAIL'));
    const ok = res.llm?.status === 'ok' && res.asr?.status === 'ok';
    el.textContent = parts.join(' | ');
    el.style.color = ok ? 'var(--success-color)' : 'var(--warning-color)';
    setTimeout(() => { el.textContent = ''; }, 5000);
  } catch (e) {
    el.textContent = '测试失败';
    el.style.color = 'var(--error-color)';
  }
}

/* ==================== Recording ==================== */

async function toggleRecording() {
  try {
    const r = await fetch(`${API}/api/toggle`, { method: 'POST' });
    const res = await r.json();
    updateRecordingUI(res.recording);
  } catch (e) {
    console.error('toggle:', e);
  }
}

function updateRecordingUI(on) {
  const dot = document.getElementById('recordingDot');
  const st = document.getElementById('recordingStatus');
  const btn = document.getElementById('toggleBtn');

  if (on) {
    dot.classList.add('active');
    st.textContent = '录音中';
    btn.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg><span>停止</span>';
    btn.classList.add('recording');
  } else {
    dot.classList.remove('active');
    st.textContent = '待命';
    btn.innerHTML = '<svg class="btn-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/><path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg><span>开始录音</span>';
    btn.classList.remove('recording');
  }
}

function toggleShow(id) {
  const el = document.getElementById(id);
  const btn = el.parentElement.querySelector('.btn');
  if (el.type === 'password') {
    el.type = 'text';
    btn.textContent = '隐藏';
  } else {
    el.type = 'password';
    btn.textContent = '显示';
  }
}

/* ==================== Knowledge Base ==================== */

async function loadKBStats() {
  try {
    const r = await fetch(`${API}/api/kb/stats`);
    const s = await r.json();
    document.getElementById('kbDocCount').textContent = s.total_documents;
    document.getElementById('kbChunkCount').textContent = s.total_chunks;
    document.getElementById('kbModel').textContent = s.embedding_model || 'bge-small-zh-v1.5';
  } catch (e) {
    console.error('loadKBStats:', e);
  }
}

async function loadKBDocs() {
  const el = document.getElementById('kbDocList');
  try {
    const r = await fetch(`${API}/api/kb/documents`);
    const data = await r.json();
    const docs = data.documents || [];

    if (docs.length === 0) {
      el.innerHTML = '<p class="placeholder">暂无文档，请添加知识条目或上传文件</p>';
      return;
    }

    el.innerHTML = docs.map(d => `
      <div class="kb-doc-item" data-id="${d.id}">
        <div class="kb-doc-info">
          <div class="kb-doc-title">${escHtml(d.title)}</div>
          <div class="kb-doc-meta">
            <span class="kb-doc-status ${d.status}">${statusText(d.status)}</span>
            &middot; ${d.chunks_count} 片段
            &middot; ${d.source === 'file' ? '文件' : '文本'}
            &middot; ${fmtDate(d.created_at)}
          </div>
        </div>
        <button class="btn btn-sm btn-danger" onclick="deleteKBDoc('${d.id}')">删除</button>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = '<p class="placeholder">加载失败</p>';
    console.error('loadKBDocs:', e);
  }
}

async function addKBText() {
  const title = document.getElementById('kbTitle').value.trim();
  const content = document.getElementById('kbContent').value.trim();
  const el = document.getElementById('kbStatus');

  if (!content) {
    el.textContent = '请输入内容';
    el.style.color = 'var(--error-color)';
    return;
  }

  el.textContent = '添加中...';
  el.style.color = '';

  try {
    await fetch(`${API}/api/kb/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    });
    el.textContent = '已添加';
    el.style.color = 'var(--success-color)';
    document.getElementById('kbTitle').value = '';
    document.getElementById('kbContent').value = '';
    setTimeout(() => { el.textContent = ''; }, 2000);
    setTimeout(() => { loadKBDocs(); loadKBStats(); }, 3000);
  } catch (e) {
    el.textContent = '添加失败';
    el.style.color = 'var(--error-color)';
  }
}

async function uploadKBFile(input) {
  const file = input.files[0];
  if (!file) return;
  input.value = '';

  const el = document.getElementById('kbStatus');
  el.textContent = '上传中...';
  el.style.color = '';

  const fd = new FormData();
  fd.append('file', file);

  try {
    await fetch(`${API}/api/kb/upload`, { method: 'POST', body: fd });
    el.textContent = '已上传: ' + file.name;
    el.style.color = 'var(--success-color)';
    setTimeout(() => { el.textContent = ''; }, 2500);
    setTimeout(() => { loadKBDocs(); loadKBStats(); }, 3000);
  } catch (e) {
    el.textContent = '上传失败';
    el.style.color = 'var(--error-color)';
  }
}

async function deleteKBDoc(id) {
  if (!confirm('确定删除此文档？')) return;

  try {
    await fetch(`${API}/api/kb/documents/${id}`, { method: 'DELETE' });
    loadKBDocs();
    loadKBStats();
  } catch (e) {
    console.error('deleteKBDoc:', e);
  }
}

function statusText(s) {
  return { pending: '等待中', processing: '处理中', completed: '已完成', failed: '失败' }[s] || s;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function fmtDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString('zh-CN'); } catch (e) { return iso; }
}

/* ==================== WebSocket ==================== */

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/api/ws`);
  ws.onopen = () => { pollStatus(); };
  ws.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.type === 'recording') updateRecordingUI(d.active);
    if (d.type === 'scene_change') document.getElementById('currentScene').textContent = d.display_name;
  };
  ws.onclose = () => { setTimeout(connectWS, 3000); };
  ws.onerror = () => {};
}

async function pollStatus() {
  try {
    const r = await fetch(`${API}/api/status`);
    const s = await r.json();
    updateRecordingUI(s.is_recording);
    document.getElementById('currentScene').textContent = s.scene_display_name;
    document.getElementById('activeWindow').textContent = s.active_window || '-';
  } catch (e) {}
}

/* ==================== Startup ==================== */

async function waitForReady() {
  const overlay = document.getElementById('startupOverlay');
  const statusEl = document.getElementById('startupStatus');
  const steps = {
    qdrant: document.getElementById('stepQdrant'),
    model: document.getElementById('stepModel'),
    engine: document.getElementById('stepEngine'),
  };

  function setStep(key, state) {
    const el = steps[key];
    if (!el) return;
    el.classList.remove('active', 'done');
    if (state === 'active') el.classList.add('active');
    if (state === 'done') el.classList.add('done');
  }

  setStep('qdrant', 'active');
  statusEl.textContent = '正在启动 Qdrant...';

  let ready = false;
  let attempt = 0;
  const maxAttempts = 60;

  while (!ready && attempt < maxAttempts) {
    attempt++;
    try {
      const r = await fetch(`${API}/api/status`);
      if (r.ok) {
        const s = await r.json();
        if (s.ready) {
          setStep('qdrant', 'done');
          setStep('model', 'done');
          setStep('engine', 'done');
          statusEl.textContent = '启动完成';
          ready = true;
          break;
        }
        // Server responding but engine not ready yet
        setStep('qdrant', 'done');
        setStep('model', 'active');
        statusEl.textContent = '正在加载 Embedding 模型...';
      }
    } catch (e) {
      // Server not responding yet
      if (attempt <= 8) {
        setStep('qdrant', 'active');
        statusEl.textContent = '正在启动 Qdrant...';
      } else {
        setStep('qdrant', 'done');
        setStep('model', 'active');
        statusEl.textContent = '正在加载 Embedding 模型...';
      }
    }
    await new Promise(r => setTimeout(r, 500));
  }

  if (!ready) {
    statusEl.textContent = '启动超时，请检查终端日志';
    statusEl.style.color = 'var(--error-color)';
    return;
  }

  overlay.classList.add('fade-out');
  setTimeout(() => { overlay.style.display = 'none'; }, 300);

  loadConfig();
  connectWS();
}

/* ==================== ASR Provider UI Update ==================== */

function updateAsrProviderUI(provider) {
  const secretKeyGroup = document.getElementById('asrSecretKeyGroup');
  const asrApiKeyHelp = document.getElementById('asrApiKeyHelp');
  const asrModelHelp = document.getElementById('asrModelHelp');
  const asrModelSelect = document.getElementById('asrModel');
  
  if (provider === 'tencent') {
    // 显示腾讯云 SecretKey
    secretKeyGroup.style.display = 'block';
    
    // 更新提示文本
    asrApiKeyHelp.textContent = '腾讯云 SecretId（如 AKIDxxxxx）';
    asrModelHelp.textContent = '推荐：16k_zh_en（中英混合）或 16k_zh（纯中文），每月免费 5 小时';
    
    // 显示腾讯云模型，隐藏阿里云模型
    const aliyunModels = asrModelSelect.querySelectorAll('optgroup')[0];
    const tencentModels = asrModelSelect.querySelectorAll('optgroup')[1];
    
    // 设置 disabled 属性来隐藏选项组
    Array.from(aliyunModels.options).forEach(opt => opt.disabled = true);
    Array.from(tencentModels.options).forEach(opt => opt.disabled = false);
    
    // 如果当前选择的是阿里云模型，切换到腾讯云默认模型
    const currentModel = asrModelSelect.value;
    if (!currentModel.startsWith('16k_')) {
      asrModelSelect.value = '16k_zh_en';
    }
    
  } else {
    // 隐藏腾讯云 SecretKey
    secretKeyGroup.style.display = 'none';
    
    // 更新提示文本
    asrApiKeyHelp.textContent = '阿里云 DashScope API Key（如 sk-xxxxx）';
    asrModelHelp.textContent = 'Qwen3-ASR 自带服务端 VAD，仅在说话时消耗 token，静默不计费';
    
    // 显示阿里云模型，隐藏腾讯云模型
    const aliyunModels = asrModelSelect.querySelectorAll('optgroup')[0];
    const tencentModels = asrModelSelect.querySelectorAll('optgroup')[1];
    
    Array.from(aliyunModels.options).forEach(opt => opt.disabled = false);
    Array.from(tencentModels.options).forEach(opt => opt.disabled = true);
    
    // 如果当前选择的是腾讯云模型，切换到阿里云默认模型
    const currentModel = asrModelSelect.value;
    if (currentModel.startsWith('16k_')) {
      asrModelSelect.value = 'qwen3-asr-flash-realtime';
    }
  }
}

/* ==================== Init ==================== */

document.addEventListener('DOMContentLoaded', () => {
  // 监听 ASR Provider 切换
  document.getElementById('asrProvider').addEventListener('change', (e) => {
    updateAsrProviderUI(e.target.value);
  });
  
  waitForReady();
});
