import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const forwardAuthHeader = (proxyReq, req) => {
  if (req.headers['authorization']) {
    proxyReq.setHeader('authorization', req.headers['authorization'])
  }
}

const disableSseBuffering = (proxy) => {
  proxy.on('proxyRes', (proxyRes) => {
    if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
      proxyRes.headers['x-accel-buffering'] = 'no'
    }
  })
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api/v1/admin': {
        target: 'http://localhost:18081',
        changeOrigin: true,
        onProxyReq: forwardAuthHeader
      },
      '/api/v1/llm-ask/v2': {
        target: 'http://localhost:18081',
        changeOrigin: true,
        onProxyReq: forwardAuthHeader,
        configure: disableSseBuffering
      },
      '/api/v1/llm-ask/history': {
        target: 'http://localhost:18081',
        changeOrigin: true,
        onProxyReq: forwardAuthHeader
      },
      '/api': {
        target: 'http://localhost:18080',
        changeOrigin: true,
        onProxyReq: forwardAuthHeader,
        configure: disableSseBuffering
      }
    }
  }
})
