import api from './client'
import type { ConvertibleBond } from './types'

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
      strategy_info: {
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
      }
      fetch_time: string
      total_before_filter: number
      total: number
      top_n: number
      risk_summary: Record<string, number>
    }>('/cb/master-strategy', { params }),

  /** 获取所有大师策略定义 */
  getStrategies: () =>
    api.get<{
      strategies: Record<string, {
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
      }>
    }>('/cb/strategies'),
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
