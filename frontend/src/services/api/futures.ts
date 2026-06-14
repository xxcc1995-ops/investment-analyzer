import api from './client'
import type { FuturesCommodityItem } from './types'

// ============ 期货数据API ============

export const futuresApi = {
  /** 获取商品快照 */
  getCommodities: () => api.get<{ items: FuturesCommodityItem[]; fetch_time?: string }>('/futures/commodities'),

  /** 获取期货列表 */
  getList: () => api.get<{ items: FuturesCommodityItem[]; fetch_time?: string }>('/futures/list'),

  /** 获取行业数据 */
  getIndustry: () => api.get<{ industries: unknown[]; fetch_time?: string }>('/futures/industry'),

  /** 获取资金流向 */
  getFundFlow: () => api.get<{ flows: unknown[]; fetch_time?: string }>('/futures/fund-flow'),

  /** 获取北向资金 */
  getNorthFlow: () => api.get<{ flows: unknown[]; fetch_time?: string }>('/futures/north-flow'),

  // ---- 期货洞察新增 ----

  /** 获取全球商品分类数据 */
  getGlobalCommodities: () => api.get('/futures/global-commodities'),

  /** 获取COT持仓排名 */
  getCotRanking: (params?: { vars?: string; date?: string }) =>
    api.get('/futures/cot-ranking', { params }),

  /** 获取基差分析数据 */
  getBasis: (params?: { vars?: string }) =>
    api.get('/futures/basis', { params }),

  /** 获取展期收益率 */
  getRollYield: (params?: { var?: string; start_day?: string; end_day?: string }) =>
    api.get('/futures/roll-yield', { params }),

  /** 获取库存数据 */
  getInventory: (params?: { symbols?: string }) =>
    api.get('/futures/inventory', { params }),

  /** 获取商品指数 */
  getCommodityIndices: () => api.get('/futures/commodity-indices'),

  /** 获取机构配置模型 */
  getInstitutionalAllocation: () => api.get('/futures/institutional-allocation'),

  // ---- 金融期货 + 期限结构 + 套利分析 ----

  /** 获取金融期货快照（股指+国债） */
  getFinancialFutures: () => api.get('/futures/financial-futures'),

  /** 获取期限结构数据 */
  getTermStructure: (params?: { var?: string }) =>
    api.get('/futures/term-structure', { params }),

  /** 获取跨期套利信号 */
  getSpreadSignals: () => api.get('/futures/spread-signals'),

  /** 获取持仓量-价格分析 */
  getOIAnalysis: (params?: { vars?: string }) =>
    api.get('/futures/oi-analysis', { params }),
}

// Re-export type for convenience
export type { FuturesCommodityItem }
