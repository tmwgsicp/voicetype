/**
 * Copyright (C) 2026 VoiceType Contributors
 * Licensed under AGPL-3.0
 */

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: {
        main: './index.html',
        floating: './floating.html',
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
