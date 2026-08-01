/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

import { createApp } from 'vue'
import ReplyComposer from './components/ReplyComposer.vue'
import './styles/design-system.css'  // 全局按钮系统 + token（本窗按钮要用）

createApp(ReplyComposer).mount('#app')
