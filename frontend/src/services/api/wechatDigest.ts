/**
 * 微信公众号日报 - API 客户端
 */
import api from './client'

const BASE = '/wechat-digest'

export const wechatDigestApi = {
  // 登录
  loginStart: () => api.post(`${BASE}/login/start`),
  loginCheck: (uuid: string) => api.get(`${BASE}/login/check/${uuid}`),
  getLoginStatus: () => api.get(`${BASE}/status`),
  logout: () => api.post(`${BASE}/logout`),
  getQrUrl: (uuid: string) => `${BASE}/login/qr/${uuid}`,

  // 公众号
  getAccounts: () => api.get(`${BASE}/accounts`),
  syncAccounts: () => api.post(`${BASE}/accounts/sync`),

  // 文章同步
  syncArticles: (params?: { mp_id?: string; days?: number }) =>
    api.post(`${BASE}/sync`, params || {}),

  // 文章查询
  getArticles: (params?: { days?: number; mp_id?: string }) =>
    api.get(`${BASE}/articles`, { params }),

  // 日报
  getDigest: (days?: number) =>
    api.get(`${BASE}/digest`, { params: { days } }),

  // 配置
  getConfig: () => api.get(`${BASE}/config`),
  updateConfig: (config: Record<string, any>) =>
    api.post(`${BASE}/config`, config),
}
