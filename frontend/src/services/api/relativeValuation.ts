import api from './client'

export interface SectorInfo {
  key: string
  label: string
}

export interface UniverseStock {
  code: string
  name: string
  sector: string
  sector_label: string
}

export interface StockMetric {
  code: string
  name: string
  market: string
  price: number
  change_pct?: number | null
  market_cap?: number | null
  pe?: number | null
  pb?: number | null
  ps?: number | null
  dividend_yield?: number | null
  roe?: number | null
  net_margin?: number | null
  revenue_growth?: number | null
  profit_growth?: number | null
  pe_pct?: number | null
  pb_pct?: number | null
  ps_pct?: number | null
  div_pct?: number | null
  pe_dev?: number | null
  pb_dev?: number | null
  ps_dev?: number | null
  div_dev?: number | null
  attractiveness?: number | null
  rating?: string
  rating_level?: string
}

export interface CompareResult {
  market: string
  sector: string
  sector_label: string
  stocks: StockMetric[]
  medians: Record<string, number | null>
  count: number
  data_note: string
  error?: string
  target?: StockMetric | null
  target_code?: string
  note?: string
}

export const relativeValuationApi = {
  /** 获取 A/H 市场可对比的行业清单 */
  getSectors: () => api.get<{ A: SectorInfo[]; HK: SectorInfo[] }>('/relative-valuation/sectors').then(r => r.data),

  /** 同一行业组内对比 */
  compareSector: (market: string, sector: string) =>
    api
      .get<CompareResult>('/relative-valuation/compare', { params: { market, sector } })
      .then(r => r.data),

  /** 单只股票 vs 其所在行业同业 */
  compareStock: (market: string, code: string, sector?: string) =>
    api
      .get<CompareResult>('/relative-valuation/stock', { params: { market, code, sector } })
      .then(r => r.data),

  /** 可搜索标的清单（代码/名称/行业），供「选一只标的」自动完成 */
  getStocks: (market: string) =>
    api
      .get<{ market: string; stocks: UniverseStock[] }>('/relative-valuation/stocks', { params: { market } })
      .then(r => r.data),
}
