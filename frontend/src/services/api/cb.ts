import api from './client'
import type { ConvertibleBond } from './types'

// ============ 类型定义 ============

/** 单条风险应对项（来自八大战法 PDF） */
export interface CBStrategyRisk {
  name: string
  probability: string
  impact: string
  solution: string
}

/** 一个策略的对外公开信息（剔除 lambda，可安全序列化） */
export interface CBStrategy {
  key: string
  name: string
  master: string
  source: string
  philosophy: string
  risk_level: string
  complexity: string
  min_capital: string
  expected_return: string
  description: string
  rules: string[]
  suitable_for: string[]
  warnings: string[]
  risks: CBStrategyRisk[]
  pitfalls: string[]
  is_eight: boolean
  chapter: number | null
}

// ============ 可转债API ============

export const cbApi = {
  /** 获取双低可转债（增强版：支持质量评分） */
  getDoubleLow: (params?: {
    max_double_low?: number
    top_n?: number
    min_turnover?: number
    min_year_left?: number
    min_ytm?: number
    sort_by?: string
    exclude_st?: boolean
    exclude_force_redeem?: boolean
  }) =>
    api.get<{
      bonds: ConvertibleBond[]
      fetch_time: string
      total_before_filter: number
      total: number
      logged_in: boolean
      sort_by: string
      risk_summary: Record<string, number>
      data_source?: string
    }>('/cb/double-low', { params }),

  /** 获取大师策略筛选结果 */
  getMasterStrategy: (params?: {
    strategy?: string
    top_n?: number
  }) =>
    api.get<{
      bonds: ConvertibleBond[]
      strategy: string
      strategy_info: CBStrategy
      fetch_time: string
      total_before_filter: number
      total: number
      top_n: number
      risk_summary: Record<string, number>
      data_source?: string
      error?: string
    }>('/cb/master-strategy', { params }),

  /** 获取所有策略定义（含八大战法完整信息） */
  getStrategies: () =>
    api.get<{
      strategies: Record<string, CBStrategy>
      eight_order: string[]
    }>('/cb/strategies'),
}

// ============ 临期债筛选API（税后保本价安全垫） ============

/** 单只临期债字段 */
export interface NearMatureBond {
  bond_id: string
  bond_nm: string
  price: number | null
  changepct: number | null
  after_tax_floor: number | null
  redeem_price_pre: number | null
  dist_to_floor: number | null
  year_left: number | null
  maturity_dt: string
  last_trade_dt: string
  premium_rt: number | null
  convert_value: number | null
  convert_price: number | null
  stock_id: string
  stock_nm: string
  stock_price: number | null
  stock_20d_chg: number | null
  stock_20d_amp: number | null
  remain_size: number | null
  issue_size: number | null
  rating_cd: string
  force_redeem: string
  amount: number | null
  volume: number | null
}

/** 临期债筛选响应 */
export interface NearMatureResponse {
  params: {
    max_remain_years: number
    price_tol: number
    max_premium: number
    tax_rate: number
    include_elasticity: boolean
  }
  summary: {
    all_count: number
    floor_count: number
    double_condition_count: number
    as_of: string
    note?: string
  }
  data_source: string
  fetch_time: string
  double_condition: NearMatureBond[]
  floor_zone: NearMatureBond[]
  all_linqi: NearMatureBond[]
}

export const cbNearMatureApi = {
  /** 获取临期可转债筛选结果（税后保本价安全垫） */
  getNearMature: (params?: {
    include_elasticity?: boolean
    max_remain_years?: number
    price_tol?: number
    max_premium?: number
  }) => api.get<NearMatureResponse>('/cb-near-mature/near-mature', { params }),
}

// ============ 可转债回测API ============

export const cbBacktestApi = {
  /** 获取可回测的策略列表 */
  getStrategies: () =>
    api.get<{
      strategies: Array<{ key: string; name: string; description: string; sell_rule: string }>
      rebalance_options: Array<{ key: string; name: string }>
    }>('/cb-backtest/strategies'),

  /** 执行单策略回测 */
  runBacktest: (params: {
    strategy: string
    start_date?: string
    end_date?: string
    rebalance_freq?: string
    top_n?: number
    initial_capital?: number
  }) => api.get<any>('/cb-backtest/run', { params }),

  /** 多策略对比 */
  compare: (params: {
    strategies: string
    start_date?: string
    end_date?: string
    rebalance_freq?: string
    top_n?: number
    initial_capital?: number
  }) => api.get<any>('/cb-backtest/compare', { params }),
}
