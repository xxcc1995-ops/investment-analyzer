/**
 * 微信公众号日报 - API 客户端
 */
import api from './client'

const B = '/wechat-digest'

export const wechatDigestApi = {
  // 登录
  loginStart: () => api.post(`${B}/login/start`),
  loginCheck: (uuid: string) => api.get(`${B}/login/check/${uuid}`),
  getLoginStatus: () => api.get(`${B}/status`),
  logout: () => api.post(`${B}/logout`),

  // 公众号
  getAccounts: () => api.get(`${B}/accounts`),
  addAccount: (data: { name: string; mpId: string }) => api.post(`${B}/accounts/add`, data),
  removeAccount: (mpId: string) => api.post(`${B}/accounts/remove`, { mpId }),

  // 文章
  addArticle: (data: { url: string; mpName?: string; mpId?: string }) => api.post(`${B}/articles/add`, data),
  addArticlesBatch: (data: { urls: string[]; mpName?: string; mpId?: string }) => api.post(`${B}/articles/batch`, data),
  getArticles: (params?: { days?: number; mp_id?: string }) => api.get(`${B}/articles`, { params }),

  // 日报
  getDigest: (days?: number) => api.get(`${B}/digest`, { params: { days } }),

  // 配置
  getConfig: () => api.get(`${B}/config`),
  updateConfig: (config: Record<string, any>) => api.post(`${B}/config`, config),
}
