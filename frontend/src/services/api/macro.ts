import api from './client'
import type {
  BondYieldsResponse,
  IndexValuationItem,
  MacroIndicator,
  MacroOverview,
  ChinaMacroData,
  UsMacroData,
} from './types'

// ============ 指数估值API ============

export const indexValuationApi = {
  /** 获取指数估值数据 */
  getData: () =>
    api.get<{ indices: IndexValuationItem[]; update_time: string }>('/index-valuation/data'),
}

// ============ 宏观数据API ============

export const macroApi = {
  /** 获取宏观概览 */
  getOverview: () => api.get<MacroOverview>('/macro/overview'),

  /** 获取中国宏观数据 */
  getChina: () => api.get<ChinaMacroData>('/macro/china'),

  /** 获取美国宏观数据 */
  getUs: () => api.get<UsMacroData>('/macro/us'),

  /** 获取收益率曲线 */
  getYieldCurve: () => api.get<BondYieldsResponse>('/macro/yield-curve'),
}

// Re-export macro types for convenience
export type { MacroIndicator, MacroOverview, ChinaMacroData, UsMacroData }
