import api from './client'
import type { ScreenerResult } from './types'

// ============ 筛选器API ============

export const screenerApi = {
  /** 攒股收息筛选 */
  getDividend: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/dividend/screener', { params }),

  /** 烟蒂股筛选 */
  getCigarButt: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/cigar-butt/screener', { params }),

  /** 烟蒂股理念 */
  getCigarButtPhilosophy: () =>
    api.get<Record<string, unknown>>('/cigar-butt/philosophy'),

  /** 价值投资筛选 */
  getValueInvesting: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/value-investing/screener', { params }),

  /** 价值投资理念 */
  getValueInvestingPhilosophy: () =>
    api.get<Record<string, unknown>>('/value-investing/philosophy'),

  /** 价值投资DCF */
  calculateDCF: (params: Record<string, unknown>) =>
    api.post<Record<string, unknown>>('/value-investing/dcf', params),

  /** REIT筛选 */
  getREIT: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/reit/screener', { params }),

  /** REIT类型 */
  getREITTypes: () =>
    api.get<{ types: unknown[] }>('/reit/types'),

  /** REIT风险指南 */
  getREITRiskGuide: () =>
    api.get<Record<string, unknown>>('/reit/risk-guide'),
}

// Re-export type for convenience
export type { ScreenerResult }
