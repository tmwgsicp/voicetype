/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')
