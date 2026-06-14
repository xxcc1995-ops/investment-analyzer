import api from './client'

// ============ 交易系统API ============

export const tradingApi = {
  /** 右侧交易分析 */
  getRightSide: (code: string) =>
    api.get<Record<string, unknown>>(`/right-side/${code}`),

  /** 右侧交易回测 */
  getRightSideBacktest: (code: string) =>
    api.get<Record<string, unknown>>(`/right-side/${code}/backtest`),

  /** 网格交易分析 */
  getGridAnalysis: (params: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/grid/analysis', { params }),

  /** 网格交易理念 */
  getGridPhilosophy: () =>
    api.get<Record<string, unknown>>('/grid/philosophy'),

  /** 做T信号 */
  getTSignals: (params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/t-trading/signals', { params }),

  /** 做T持仓 */
  getTPosition: () =>
    api.get<Record<string, unknown>>('/t-trading/position'),

  /** 做T理念 */
  getTPhilosophy: () =>
    api.get<Record<string, unknown>>('/t-trading/philosophy'),

  /** 做T金字塔 */
  getTPyramid: (params: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/t-trading/pyramid', { params }),

  /** 初始化持仓 */
  initTPosition: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/t-trading/position/init', params),

  /** 执行交易 */
  executeTTrade: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/t-trading/execute', params),

  /** 策略回测 */
  getBacktest: (params: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/backtest/backtest', { params }),
}

// ============ Polymarket API ============

export const polymarketApi = {
  /** 获取市场列表 */
  getMarkets: (params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/polymarket/markets', { params }),

  /** 获取套利机会 */
  getArbitrage: (params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/polymarket/arbitrage', { params }),

  /** 获取价值发现 */
  getValue: () =>
    api.get<Record<string, unknown>>('/polymarket/value'),

  /** 获取趋势 */
  getTrending: () =>
    api.get<Record<string, unknown>>('/polymarket/trending'),

  /** 获取市场详情 */
  getMarketDetail: (id: string) =>
    api.get<Record<string, unknown>>(`/polymarket/markets/${id}`),

  /** 获取跨平台套利 */
  getCrossArbitrage: (params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/polymarket/cross-arbitrage', { params }),

  /** 计算配置 */
  calculateAllocation: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/polymarket/allocation-calculator', params),

  /** Kelly公式计算 */
  calculateKelly: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/polymarket/kelly', params),
}

// ============ 决策卫士API ============

export const decisionApi = {
  /** 分析决策 */
  analyze: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/decision/analyze', params),

  /** 诊断问题 */
  diagnose: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/decision/diagnose', params),

  /** 记录结果 */
  recordOutcome: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/decision/outcome', params),

  /** 获取历史 */
  getHistory: () =>
    api.get<Record<string, unknown>>('/decision/history'),
}
