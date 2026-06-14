// ============ 类型定义 ============

export interface SearchItem {
  code: string
  name: string
  market?: string
}

export interface StockBasic {
  code: string
  name: string
  market?: string
  price: number
  open: number
  high: number
  low: number
  pre_close: number
  change_pct: number
  volume: number
  amount: number
  pe: number | null
  pb: number | null
  dividend_yield?: number | null
  market_cap: number
  trade_date?: string
  trade_time?: string
  fetch_time?: string
}

export interface FinancialReport {
  date: string
  report_name: string
  eps: number | null
  bps: number | null
  roe: number | null
  revenue: number | null
  net_profit: number | null
  revenue_growth: number | null
  profit_growth: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
}

export interface ValuationPoint {
  date: string
  value: number
}

export interface ValuationStats {
  current: number
  min: number
  max: number
  median: number
  p25: number
  p75: number
  percentile: number
  count: number
}

export interface ValuationHistory {
  pe_history: ValuationPoint[]
  pb_history: ValuationPoint[]
  div_history: ValuationPoint[]
  stats: {
    pe: ValuationStats | null
    pb: ValuationStats | null
    div: ValuationStats | null
  } | null
  message?: string
}

export interface IncomeStatement {
  report_date: string
  report_name: string
  report_type: string
  total_revenue: number | null
  operating_cost: number | null
  sell_expense: number | null
  manage_expense: number | null
  research_expense: number | null
  finance_expense: number | null
  operate_profit: number | null
  total_profit: number | null
  income_tax: number | null
  net_profit: number | null
  parent_net_profit: number | null
  sell_expense_ratio: number | null
  manage_expense_ratio: number | null
  research_expense_ratio: number | null
  finance_expense_ratio: number | null
  gross_margin: number | null
  net_margin: number | null
  operating_margin: number | null
}

export interface BalanceSheet {
  report_date: string
  report_name: string
  report_type: string
  monetary_funds: number | null
  accounts_receivable: number | null
  inventory: number | null
  total_current_assets: number | null
  total_non_current_assets: number | null
  total_assets: number | null
  short_term_borrowing: number | null
  long_term_borrowing: number | null
  total_current_liabilities: number | null
  total_non_current_liabilities: number | null
  total_liabilities: number | null
  total_equity: number | null
  parent_equity: number | null
  debt_ratio: number | null
  current_ratio: number | null
  quick_ratio: number | null
}

export interface CashFlowStatement {
  report_date: string
  report_name: string
  report_type: string
  netcash_operate: number | null
  netcash_invest: number | null
  netcash_finance: number | null
  cash_begin: number | null
  cash_end: number | null
  free_cashflow: number | null
  operating_to_profit_ratio: number | null
  capex: number | null
  depreciation_amortization: number | null
}

export interface FinancialStatementsData {
  code: string
  income: IncomeStatement[]
  balance: BalanceSheet[]
  cashflow: CashFlowStatement[]
  fetch_time: string
}

export interface DerivedMetrics {
  code: string
  fetch_time?: string
  ev?: number
  ebitda?: number
  ev_ebitda?: number
  ev_ebitda_level?: string
  free_cashflow?: number
  fcf_yield?: number
  fcf_yield_level?: string
  dupont?: {
    net_margin: number
    asset_turnover: number
    equity_multiplier: number
    roe: number
  }
  error?: string
}

export interface FinancialAnalysisResult {
  code: string
  score: number
  grade: string
  conclusion: string
  strengths: string[]
  risks: string[]
  dimensions: {
    earnings: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
    growth: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
    safety: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
    efficiency: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
    cashflow: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
    moat: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
    management: { score: number; metrics: Record<string, unknown>; strengths: string[]; risks: string[] }
  }
  dimension_scores: {
    earnings: number
    growth: number
    safety: number
    efficiency: number
    cashflow: number
    moat: number
    management: number
  }
}

// ============ 交叉分析类型 ============

export interface CrossAnalysisResult {
  stock: {
    code: string
    name: string
    price: number
    pe: number | null
    pb: number | null
    market_cap: number | null
  }
  vertical_analysis: {
    lifecycle: {
      stage: string
      confidence: number
      trend_signal: string
      details: {
        avg_revenue_growth: number
        avg_profit_growth: number
        avg_roe: number
        revenue_trend: number | null
        profit_trend: number | null
      }
    }
    timeline: Array<{
      date: string
      report_name: string
      roe: number | null
      gross_margin: number | null
      net_margin: number | null
      revenue_growth: number | null
      profit_growth: number | null
      debt_ratio: number | null
    }>
    roe_trend: number[]
    gross_margin_trend: number[]
    revenue_growth_trend: number[]
    latest_metrics: {
      roe: number | null
      gross_margin: number | null
      net_margin: number | null
      revenue_growth: number | null
      profit_growth: number | null
      debt_ratio: number | null
    }
  }
  horizontal_analysis: {
    industry: string
    peers: Array<{
      code: string
      name: string
      price: number
      pe: number | null
      pb: number | null
      roe: number | null
      gross_margin: number | null
      net_margin: number | null
      revenue_growth: number | null
      profit_growth: number | null
      debt_ratio: number | null
    }>
    industry_avg: Record<string, number>
    competitive_position: {
      score: number
      rankings: Record<string, { rank: number; total: number }>
      details: string[]
    }
  }
  dupont: {
    roe: number | null
    net_margin: number | null
    gross_margin: number | null
    asset_turnover: number | null
    equity_multiplier: number | null
    roe_quality: string
    roe_quality_score: number
  }
  cross_validation: {
    consistency_score: number
    flags: string[]
    details: Array<{ check: string; status: string }>
  }
  three_dimension: {
    valuation: { score: number; level: string; details: string[] }
    profitability: { score: number; level: string; details: string[] }
    momentum: { score: number; level: string; details: string[] }
  }
  dimension_scores: Record<string, { score: number; details: string[] }>
  correlation_analysis: {
    pairs: Array<{
      metric1: string
      metric2: string
      correlation: number
      strength: string
      direction: string
    }>
    summary: string
  }
  insights: {
    summary: string
    strengths: string[]
    weaknesses: string[]
    opportunities: string[]
    threats: string[]
    key_risks: string[]
    conclusion: string
  }
  rating: {
    score: number
    grade: string
    recommendation: string
    details: Array<{
      item: string
      score: number
      weight: string
      weighted_score: number
    }>
    top_factor: string
    worst_factor: string
    dimension_scores: Record<string, number>
  }
  update_time: string
}

export interface FundArbitrage {
  fund_id: string
  fund_nm: string
  price: number
  fund_nav: number
  nav_discount_rt: number
  increase_rt: number
  volume: number
  turnover: number
  amount: number
  direction: string
  apply_fee: string
  redeem_fee: string
  apply_status: string
  redeem_status: string
  apply_limit: string
  nav_dt: string
  price_dt: string
  issuer_nm: string
  estimated_profit: number
  est_nav?: number | null
  est_discount_rt?: number | null
  underlying_name?: string | null
  underlying_change?: number | null
  price_fetch_time?: string | null
  est_nav_date?: string | null
  ref_est_nav?: number | null
  ref_est_discount_rt?: number | null
}

// ============ 分红历史 & 脆弱性分析类型 ============

export interface DividendRecord {
  year: string
  total_dps: number
  eps: number | null
}

export interface DividendHistory {
  dividends: DividendRecord[]
}

export interface FragilityDimension {
  name: string
  score: number
  max: number
  status: string
  detail: string
  signal?: string
  label?: string
}

export interface FragilityWarning {
  level?: string
  message?: string
  name?: string
  signal?: string
}

export interface FragilityResult {
  error?: string
  total_score: number
  level: string
  verdict: string
  dimensions: FragilityDimension[]
  warnings: FragilityWarning[]
}

// ============ 国债收益率类型 ============

export interface BondYieldPoint {
  date: string
  y2?: number | null
  y5?: number | null
  y10?: number | null
  y30?: number | null
  spread_10y_2y?: number | null
}

export interface BondYieldsResponse {
  cn: BondYieldPoint[]
  us: BondYieldPoint[]
}

// ============ 指数估值类型 ============

export interface IndexValuationItem {
  code: string
  name: string
  pe?: number | null
  pb?: number | null
  dividend_yield?: number | null
  roe?: number | null
  pe_percentile?: number | null
  pb_percentile?: number | null
  category?: string
}

export interface ConvertibleBond {
  bond_id: string
  bond_nm: string
  stock_id: string
  stock_nm: string
  price: number
  convert_price: number
  convert_value: number
  premium_rt: number
  double_low: number
  maturity_dt: string
  year_left: number
  rating_cd: string
  curr_iss_amt: number
  turnover: number
  stock_price: number
  stock_change: number
  bond_change: number
  force_redeem: string
  is_matured: boolean
  // 质量评分相关
  ytm_rt: number
  put_ytm_rt: number
  stock_pe: number
  stock_pb: number
  redeem_distance: number
  convert_ratio: number
  quality_score: number
  verdict: string
  risk_tags: { tag: string; level: string; desc: string }[]
  quality_scores: Record<string, { score: number; max: number; label: string }>
  // 机构级新增字段
  pure_bond_value: number
  ytm_after_tax: number
  triple_low: number
  redeem_risk: {
    redeem_risk_level: string
    days_to_redeem_estimate: number | null
    redeem_price_impact: number
    redeem_timeline: string
    is_in_redeem_zone: boolean
  }
  revision_prob: {
    revision_probability: number
    revision_level: string
    revision_factors: string[]
  }
  // 新增字段
  next_put_dt: string
  convert_dt: string
  orig_iss_amt: number
  redeem_price: number
  dividend_yield: number
  market_cap: number
  data_source?: string
}

// ============ 宏观数据类型 ============

export interface MacroIndicator {
  latest: { date: string; value: number; unit?: string; label?: string }
  series: { date: string; value: number }[]
}

export interface MacroOverview {
  [key: string]: unknown
}

export interface ChinaMacroData {
  gdp?: MacroIndicator
  cpi?: MacroIndicator
  pmi?: MacroIndicator
  money_supply?: MacroIndicator
  social_financing?: MacroIndicator
  lpr?: MacroIndicator
  consumer_confidence?: MacroIndicator
  ppi?: MacroIndicator
  retail_sales?: MacroIndicator
  housing_price?: MacroIndicator
  unemployment?: MacroIndicator
  industrial_production?: MacroIndicator
  trade_balance?: MacroIndicator
}

export interface UsMacroData {
  us_fed_rate?: MacroIndicator
  us_gdp?: MacroIndicator
  us_ism_pmi?: MacroIndicator
  us_non_farm?: MacroIndicator
  us_yield_spread?: MacroIndicator
  cn_yield_spread?: MacroIndicator
}

// ============ 期货类型 ============

export interface FuturesCommodityItem {
  name: string
  code: string
  price: number
  change: number
  change_pct: number
  volume?: number
  open_interest?: number
}

// ============ 筛选器类型 ============

export interface ScreenerResult {
  items: Record<string, unknown>[]
  total: number
  fetch_time?: string
  [key: string]: unknown
}
