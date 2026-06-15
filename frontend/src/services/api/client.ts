import axios from 'axios'
import { getBackendUrl, isNativePlatform } from '../capacitorConfig'

// 创建统一的axios实例（Web模式使用相对路径，APP模式动态获取后端地址）
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 在APP模式下动态设置baseURL
if (isNativePlatform()) {
  getBackendUrl().then(baseURL => {
    api.defaults.baseURL = baseURL
  })
}

// ========== 响应拦截器：统一错误处理 ==========
api.interceptors.response.use(
  response => response,
  error => {
    // 网络错误（后端未启动/断网）
    if (!error.response) {
      const msg = error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '网络连接失败，请检查后端服务是否启动'
      console.error(`[API] ${msg}`, error.config?.url)
      return Promise.reject(new Error(msg))
    }

    const { status, data } = error.response
    const url = error.config?.url || ''

    // 根据状态码统一处理
    switch (status) {
      case 404:
        console.warn(`[API] 404 接口不存在: ${url}`)
        break
      case 500:
        console.error(`[API] 500 服务器错误: ${url}`, data?.error || '')
        break
      case 502:
      case 503:
        console.error(`[API] ${status} 服务不可用: ${url}`)
        break
      case 504:
        console.error(`[API] 504 网关超时: ${url}`)
        break
      default:
        console.error(`[API] ${status} 请求失败: ${url}`)
    }

    return Promise.reject(error)
  }
)

export default api
