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

  /** 出口冠军筛选 */
  getExportChampions: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/export-champions/screener', { params }),

  /** 出口冠军理念 */
  getExportChampionsPhilosophy: () =>
    api.get<Record<string, unknown>>('/export-champions/philosophy'),

  /** JC筛选 */
  getJC: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/jc/screener', { params }),

  /** JC理念 */
  getJCPhilosophy: () =>
    api.get<Record<string, unknown>>('/jc/philosophy'),

  /** JC买入信号 */
  getJCBuySignals: (params?: Record<string, unknown>) =>
    api.get<ScreenerResult>('/jc/buy-signals', { params }),
}

// Re-export type for convenience
export type { ScreenerResult }
