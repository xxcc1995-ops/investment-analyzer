import api from './client'
import type {
  PortfolioTransaction,
  PortfolioSummary,
  PerformancePoint,
  RiskExposure,
  PortfolioRiskAnalysis,
} from './types'

// ============ 组合管理API ============

export const portfolioApi = {
  /** 添加交易记录 */
  addTransaction: (data: {
    code: string
    name: string
    type: 'buy' | 'sell' | 'dividend' | 'split'
    shares: number
    price: number
    fee?: number
    market?: string
    reason?: string
    decision_id?: string
  }) => api.post<PortfolioTransaction>('/portfolio/transaction', data),

  /** 获取持仓列表 */
  getPositions: () =>
    api.get<{ positions: PortfolioTransaction[]; count: number }>('/portfolio/positions'),

  /** 获取交易记录 */
  getTransactions: (code?: string, limit?: number) =>
    api.get<{ transactions: PortfolioTransaction[]; count: number }>('/portfolio/transactions', {
      params: { code, limit },
    }),

  /** 组合概览 */
  getSummary: () => api.get<PortfolioSummary>('/portfolio/summary'),

  /** 收益曲线 */
  getPerformance: () =>
    api.get<{ points: PerformancePoint[] }>('/portfolio/performance'),

  /** 风险暴露 */
  getRisk: () => api.get<RiskExposure>('/portfolio/risk'),

  /** 组合风险分析（VaR/CVaR/压力测试） */
  getRiskAnalysis: () => api.get<PortfolioRiskAnalysis>('/portfolio/risk-analysis'),

  /** 删除交易记录 */
  deleteTransaction: (txnId: string) =>
    api.delete(`/portfolio/transaction/${txnId}`),
}
