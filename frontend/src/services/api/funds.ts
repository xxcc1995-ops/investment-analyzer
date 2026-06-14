import api from './client'
import type { FundArbitrage } from './types'

// ============ 基金套利API（统一入口） ============

export const fundApi = {
  /** 检查登录状态 */
  getLoginStatus: () =>
    api.get<{ logged_in: boolean }>('/fund-arb/login_status'),

  /** 登录集思录 */
  login: (user_name: string, password: string) =>
    api.post('/fund-arb/login', { user_name, password }),

  /** 获取套利数据（旧版） */
  getArbitrage: (params?: {
    min_threshold?: number
    min_turnover?: number
    open_subscribe_only?: boolean
  }) =>
    api.get<{
      funds: FundArbitrage[]
      fetch_time: string
      data_source: string
      total_before_filter: number
      logged_in: boolean
    }>('/fund-arb/legacy-arbitrage', { params }),
}

// ============ 基金估值API（统一入口） ============

export const fundEstApi = {
  /** 获取估值列表（校准值法） */
  getEstList: () =>
    api.get<Record<string, unknown>>('/fund-arb/est-list'),

  /** 获取QDII估值详情（动态比率法） */
  getDetail: (fundCode: string) =>
    api.get<Record<string, unknown>>(`/fund-arb/est-detail/${fundCode}`, { timeout: 15000 }),

  /** 获取QDII估值列表（动态比率法） */
  getDetailList: () =>
    api.get<Record<string, unknown>>('/fund-arb/est-detail-list', { timeout: 15000 }),

  /** 获取基金持仓 */
  getHoldings: (fundCode: string, params?: Record<string, unknown>) =>
    api.get<Record<string, unknown>>(`/fund-holdings/fund-holdings/${fundCode}`, { params, timeout: 10000 }),

  /** 获取基金行业配置 */
  getIndustryAllocation: (fundCode: string) =>
    api.get<Record<string, unknown>>(`/fund-holdings/fund-holdings/${fundCode}/industry`, { timeout: 10000 }),

  /** 获取基金持仓变动 */
  getHoldingsChanges: (fundCode: string) =>
    api.get<Record<string, unknown>>(`/fund-holdings/fund-holdings/${fundCode}/changes`, { timeout: 15000 }),

  /** 获取基金持仓集中度 */
  getConcentration: (fundCode: string) =>
    api.get<Record<string, unknown>>(`/fund-holdings/fund-holdings/${fundCode}/concentration`, { timeout: 10000 }),

  /** 获取基金与指数偏离度 */
  getIndexDeviation: (fundCode: string, benchmark?: string) =>
    api.get<Record<string, unknown>>(`/fund-holdings/fund-holdings/${fundCode}/deviation`, { params: benchmark ? { benchmark } : {}, timeout: 15000 }),

  /** 获取基金持仓全景分析 */
  getFullAnalysis: (fundCode: string) =>
    api.get<Record<string, unknown>>(`/fund-holdings/fund-holdings/${fundCode}/full-analysis`, { timeout: 20000 }),

  /** 获取个股行情 */
  getStockQuotes: (params: Record<string, unknown>) =>
    api.get<Record<string, unknown>>('/fund-arb/stock-quotes', { params }),
}
