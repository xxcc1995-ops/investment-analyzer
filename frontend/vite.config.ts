import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      '/api': {
        // 默认 8022；若启动器通过 VITE_API_TARGET 指定了后端端口，则以它为准
        target: process.env.VITE_API_TARGET || 'http://localhost:8022',
        changeOrigin: true,
        ws: true,  // WebSocket 代理（实时做T信号推送 /api/t-realtime/ws）
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'echarts': ['echarts', 'echarts-for-react'],
          'react-vendor': ['react', 'react-dom'],
          'antd-vendor': ['antd', '@ant-design/icons'],
        }
      }
    }
  }
})
