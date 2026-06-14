import api from './client'
import type {
  SearchItem,
  StockBasic,
  FinancialReport,
  ValuationHistory,
  DividendHistory,
  FragilityResult,
  FinancialStatementsData,
  DerivedMetrics,
  FinancialAnalysisResult,
  CrossAnalysisResult,
} from './types'

// ============ 股票相关API ============

export const stockApi = {
  /** 搜索股票 */
  search: (keyword: string) =>
    api.get<{ results: SearchItem[] }>('/stocks/search', { params: { keyword } }),

  /** 获取股票基本信息 */
  getBasic: (code: string) =>
    api.get<StockBasic>(`/stocks/${code}/basic`),

  /** 获取财务数据 */
  getFinancials: (code: string) =>
    api.get<{ reports: FinancialReport[]; latest_report_date: string }>(`/stocks/${code}/financials`),

  /** 获取估值历史 */
  getValuationHistory: (code: string) =>
    api.get<ValuationHistory>(`/stocks/${code}/valuation-history`),

  /** 获取分红历史 */
  getDividendHistory: (code: string) =>
    api.get<DividendHistory>(`/stocks/${code}/dividend-history`),

  /** 获取脆弱性分析 */
  getFragility: (code: string) =>
    api.get<FragilityResult>(`/stocks/${code}/fragility`),

  /** 获取三大报表（利润表/资产负债表/现金流量表） */
  getFinancialStatements: (code: string) =>
    api.get<FinancialStatementsData>(`/stocks/${code}/financial-statements`),

  /** 获取派生指标（EV/EBITDA、FCF Yield、杜邦分解） */
  getDerivedMetrics: (code: string) =>
    api.get<DerivedMetrics>(`/stocks/${code}/derived-metrics`),

  /** 自动财务分析 */
  getFinancialAnalysis: (code: string) =>
    api.get<FinancialAnalysisResult>(`/stocks/${code}/financial-analysis`),

  /** 交叉分析（多维度机构级分析） */
  getCrossAnalysis: (code: string) =>
    api.get<CrossAnalysisResult>(`/cross-analysis/analyze/${code}`),
}

// ============ 国债收益率API ============

export const bondApi = {
  /** 获取国债收益率（返回类型与App.tsx本地BondYield类型兼容） */
  getYields: () =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    api.get<any>('/bonds/yields'),
}
