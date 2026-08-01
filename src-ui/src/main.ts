/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'  // element-plus 深色变量
import './styles/design-system.css'
import App from './App.vue'

// 跟随系统深/浅色：element-plus 组件靠 html.dark 类切换（我们自己的 token 靠 @media 自动切）
const mq = window.matchMedia('(prefers-color-scheme: dark)')
const applyTheme = (dark: boolean) => document.documentElement.classList.toggle('dark', dark)
applyTheme(mq.matches)
mq.addEventListener('change', (e) => applyTheme(e.matches))

const app = createApp(App)
app.use(ElementPlus)
app.mount('#app')
