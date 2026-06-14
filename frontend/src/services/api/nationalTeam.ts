import api from './client'

// ============ 加密货币API ============

export const cryptoApi = {
  /** 获取信息源 */
  getSources: () => api.get<Record<string, unknown>>('/crypto/sources'),

  /** 获取建议 */
  getTips: () => api.get<Record<string, unknown>>('/crypto/tips'),
}

// ============ 国家队监控API ============

export const nationalTeamApi = {
  /** 获取持股 */
  getShareholdings: (params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/shareholdings', { params }),

  /** 获取ETF流向 */
  getETFFlows: () =>
    api.get<Record<string, unknown>>('/etf-flows'),

  /** 获取异动提醒 */
  getVolumeAlerts: (params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/volume-alerts', { params }),

  /** 龙虎榜机构席位监控 */
  getDragonTiger: (params?: { days?: number }) =>
    api.get<Record<string, unknown>>('/dragon-tiger', { params }),

  /** 大宗交易机构监控 */
  getBlockTrades: (params?: { days?: number }) =>
    api.get<Record<string, unknown>>('/block-trades', { params }),

  /** ETF份额变动追踪 */
  getETFShares: () =>
    api.get<Record<string, unknown>>('/etf-shares'),

  /** 股东人数变动监控 */
  getShareholderChanges: (params?: { codes?: string }) =>
    api.get<Record<string, unknown>>('/shareholder-changes', { params }),

  /** 综合研判评分 */
  getAssessment: () =>
    api.get<Record<string, unknown>>('/assessment'),

  /** 北向资金监控 */
  getNorthbound: () =>
    api.get<Record<string, unknown>>('/northbound'),

  /** 融资融券监控 */
  getMargin: () =>
    api.get<Record<string, unknown>>('/margin'),
}

// ============ 雪球大V API ============

export const xueqiuApi = {
  /** 获取大V列表 */
  getGurus: () => api.get<Record<string, unknown>>('/gurus'),
}
