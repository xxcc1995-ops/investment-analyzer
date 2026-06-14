import api from './client'

// ============ 每日信息API ============

export const dailyInfoApi = {
  /** 获取每日投资简报（首次加载较慢，超时设为120秒） */
  getBriefing: () =>
    api.get<Record<string, unknown>>('/daily-info/briefing', { timeout: 120000 }),

  /** 获取中国市场摘要 */
  getChinaMarket: () =>
    api.get<Record<string, unknown>>('/daily-info/market/china'),

  /** 获取美国市场摘要 */
  getUSMarket: () =>
    api.get<Record<string, unknown>>('/daily-info/market/us'),

  /** 获取全球市场概览 */
  getGlobalMarket: () =>
    api.get<Record<string, unknown>>('/daily-info/market/global'),

  /** 获取中国宏观经济指标 */
  getChinaMacro: () =>
    api.get<Record<string, unknown>>('/daily-info/macro/china'),

  /** 获取美国宏观经济指标 */
  getUSMacro: () =>
    api.get<Record<string, unknown>>('/daily-info/macro/us'),

  /** 获取行业板块表现 */
  getSectorPerformance: () =>
    api.get<Record<string, unknown>>('/daily-info/sectors'),

  /** 获取投资观点摘要 */
  getInvestmentInsights: () =>
    api.get<Record<string, unknown>>('/daily-info/insights'),

  /** 获取市场情绪分析 */
  getMarketSentiment: () =>
    api.get<Record<string, unknown>>('/daily-info/sentiment'),

  /** 获取每日摘要（简化版） */
  getDailySummary: () =>
    api.get<Record<string, unknown>>('/daily-info/summary'),

  /** 验证数据源可用性 */
  verifySources: () =>
    api.get<Record<string, unknown>>('/daily-info/verify-sources'),

  // ==================== 五大大师模块 API ====================

  /** 获取价值投资大师信息源 */
  getValueInvesting: () =>
    api.get<Record<string, unknown>>('/daily-info/value-investing'),

  /** 获取套利机会信息 */
  getArbitrage: () =>
    api.get<Record<string, unknown>>('/daily-info/arbitrage'),

  /** 获取可转债大师信息源 */
  getConvertibleBonds: () =>
    api.get<Record<string, unknown>>('/daily-info/convertible-bonds'),

  /** 获取币圈大师信息源 */
  getCrypto: () =>
    api.get<Record<string, unknown>>('/daily-info/crypto'),

  /** 获取空投机会信息 */
  getAirdrops: () =>
    api.get<Record<string, unknown>>('/daily-info/airdrops'),

  /** 获取海外高质量新闻（美股/加密市场） */
  getOverseasNews: () =>
    api.get<Record<string, unknown>>('/daily-info/overseas-news'),

  /** 获取重大事件列表（自动检测） */
  getCriticalEvents: () =>
    api.get<unknown[]>('/daily-info/critical-events'),

  /** 获取多源交叉验证新闻 */
  getCrossValidatedNews: () =>
    api.get<unknown[]>('/daily-info/cross-validated-news'),
}
