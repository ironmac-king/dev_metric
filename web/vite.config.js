import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0',  // 监听所有网络接口，允许其他电脑访问
    proxy: {
      // LLM.V1 API 转发到 Python AI 服务
      '/api/v1/llm-ask': {
        target: 'http://localhost:8081',
        changeOrigin: true,
        // 显式转发 Authorization header
        onProxyReq: (proxyReq, req) => {
          if (req.headers['authorization']) {
            proxyReq.setHeader('authorization', req.headers['authorization'])
          }
        },
        // 禁用代理缓冲，实现实时流式
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // 确保 SSE 流不被缓冲
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        }
      },
      // 其他 API 转发到 Go 后端
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        // 显式转发 Authorization header
        onProxyReq: (proxyReq, req) => {
          if (req.headers['authorization']) {
            proxyReq.setHeader('authorization', req.headers['authorization'])
          }
        },
        // 禁用代理缓冲，实现实时流式
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // 确保 SSE 流不被缓冲
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        }
      }
    }
  }
})
