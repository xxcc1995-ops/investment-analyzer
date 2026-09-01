// 指数盈利与估值 API（用户手工维护的标普500/万得全A/沪深300 Excel 数据）
import api from './client'

export interface IndexEarningsMeta {
  code: string
  name: string
  market?: string
  baseline?: number
  discount?: number
  bond_name?: string
  start_date?: string
  end_date?: string
  row_count?: number
  file?: string
  file_updated?: string
  up_total_time?: number | null
  down_total_time?: number | null
  latest?: {
    date?: string
    close?: number | null
    pe?: number | null
    risk_premium?: number | null
    valuation_dev?: number | null
    fair_close?: number | null
  }
  error?: string
}

export interface IndexEarningsRow {
  date: string
  close?: number | null
  pe?: number | null
  risk_premium?: number | null
  eps_ttm?: number | null
  implied_eps?: number | null
  eps_up?: number | null
  eps_down?: number | null
  us_cn_spread?: number | null
  cn10y?: number | null
  us10y?: number | null
  valuation_dev?: number | null
  fair_close?: number | null
  pb?: number | null
  up_time?: number | null
  down_time?: number | null
}

export interface EpsCycle {
  start: string | null
  end: string | null
  direction: string
  months: string | null
  weeks: string | null
}

export interface ComparePoint {
  date: string
  pe_wind?: number | null
  pe_auto?: number | null
  close_wind?: number | null
  close_auto?: number | null
}

export interface IndexEarningsData {
  meta: IndexEarningsMeta
  notes: string
  summary_lines: string[]
  fields: string[]
  columns: { key: string; label: string }[]
  rows: IndexEarningsRow[]
  cycles: EpsCycle[]
  compare?: {
    series: ComparePoint[]
    stats: { overlap_weeks?: number; pe_mean_diff_pct?: number; pe_latest_diff_pct?: number }
    csindex_check?: { source?: string; n?: number; mean_diff_pct?: number; max_diff_pct?: number }
  }
}

export const indexEarningsApi = {
  getList: () => api.get<{ indices: IndexEarningsMeta[] }>('/index-earnings/list'),
  getData: (code: string) => api.get<IndexEarningsData>(`/index-earnings/data/${code}`),
}
