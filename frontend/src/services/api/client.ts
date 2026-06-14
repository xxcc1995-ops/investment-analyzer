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

export default api
