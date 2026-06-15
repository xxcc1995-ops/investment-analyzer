import api from './client'
const B = '/wechat-digest'

export const wechatDigestApi = {
  getLoginStatus: () => api.get(`${B}/status`),
  setCookie: (cookie: string) => api.post(`${B}/cookie`, { cookie }),
  setCookieDirect: (vid: string, skey: string) => api.post(`${B}/cookie/direct`, { vid, skey }),
  extractCookie: () => api.post(`${B}/extract-cookie`),
  logout: () => api.post(`${B}/logout`),

  getAccounts: () => api.get(`${B}/accounts`),
  sync: (params?: { mp_id?: string; limit?: number }) => api.post(`${B}/sync`, params || {}, { timeout: 90000 }),

  getArticles: (params?: { days?: number; mp_id?: string }) => api.get(`${B}/articles`, { params }),
  fetchContent: (url: string) => api.post(`${B}/articles/fetch-content`, { url }),

  getDigest: (days?: number) => api.get(`${B}/digest`, { params: { days } }),

  getConfig: () => api.get(`${B}/config`),
  updateConfig: (config: Record<string, any>) => api.post(`${B}/config`, config),
}
