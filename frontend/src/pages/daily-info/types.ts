/**
 * 每日资讯 - 类型定义
 * 对应后端 /api/daily-info/* 各接口的返回结构
 */

// ==================== 市场行情 ====================

export interface MarketIndex {
  code?: string
  name: string
  close: number
  change: number
  change_pct: number
  volume?: number
  date?: string
}

export interface ChinaMarket {
  a_share: MarketIndex[]
  hk: MarketIndex[]
  update_time: string
}

export interface UsMarket {
  indices: MarketIndex[]
  update_time: string
}

// ==================== 板块资金 ====================

export interface SectorItem {
  code: string
  name: string
  change_pct: number
  up_count: number
  down_count: number
  leader: string
  leader_change: number
}

export interface FundFlowItem {
  name: string
  main_net_inflow: number
  main_net_pct: number
  super_large_net: number
  large_net: number
  medium_net: number
  small_net: number
}

export interface TopMovers {
  gainers: MoverItem[]
  losers: MoverItem[]
  active?: MoverItem[]
}

export interface MoverItem {
  code: string
  name: string
  price: number
  change_pct: number
}

// ==================== 市场情绪 ====================

export interface MarketSentiment {
  sentiment: string
  description: string
  a_share: { up: number; down: number; avg_change: number }
  us: { up: number; down: number; avg_change: number }
  sectors: { up: number; down: number; total: number; max_change: number; min_change: number }
  sentiment_v3?: SentimentV3
}

export interface SentimentV3 {
  momentum: number
  breadth: number
  fund_flow: number
  volatility: number
  composite: number
  level: string
  color: string
  description: string
}

// ==================== 重大事件 ====================

export interface CriticalEvent {
  type: 'market_shock' | 'sector_divergence' | 'fund_flow_shock' | 'macro_alert' | 'overseas_event'
  level: 'critical' | 'high' | 'medium'
  title: string
  description: string
  source: string
  time: string
  link?: string
}

export interface CrossValidatedNews {
  title: string
  summary: string
  link: string
  source_count: number
  sources: string[]
  confidence: 'high' | 'medium'
  impact: 'high' | 'medium' | 'low'
  category: string
  published: string
}

// ==================== 海外新闻 ====================

export interface SourceStatus {
  name: string
  name_cn: string
  tier: number
  count: number
}

export interface OverseasNewsItem {
  title: string
  summary: string
  link: string
  published: string
  source: string
  category: string
  impact: 'high' | 'medium' | 'low'
  key_points: string[]
}

export interface OverseasCategoryData {
  items: OverseasNewsItem[]
  sources_ok: SourceStatus[]
  sources_failed: string[]
  count?: number
  high_impact_count?: number
  medium_impact_count?: number
  update_time?: string
}

export interface OverseasNewsData {
  us_stock: OverseasCategoryData
  crypto: OverseasCategoryData
  update_time: string
}

// ==================== 宏观数据 ====================

export interface ChinaMacroData {
  gdp?: { date: string; gdp: number; gdp_growth: number }
  cpi?: { date: string; cpi_yoy: number }
  pmi?: { date: string; manufacturing: number; non_manufacturing: number }
  money_supply?: { date: string; m2: number; m2_growth: number }
}

export interface FredIndicator {
  value: number
  date: string
  series: { date: string; value: number }[]
  series_id: string
}

export interface UsMacroData {
  indicators: Record<string, FredIndicator>
  source: string
  available: boolean
  reason?: string
  update_time: string
}

// ==================== 价值投资 ====================

export interface ValueInvestingData {
  announcements: { title: string; code: string; date: string; type: string }[]
  analyst_reports: { name: string; institution: string; score: number; recommend_count: number }[]
  concept_boards: { name: string; change_pct: number; turnover: number; amount: number }[]
  update_time: string
}

// ==================== 套利 ====================

export interface ArbitrageData {
  merger_arbitrage: { code: string; name: string; status: string; progress: string }[]
  cross_market_spreads: { name: string; a_price: number; h_price: number; premium: number }[]
  etf_premium: { code: string; name: string; price: number; nav: number; premium: number }[]
  update_time: string
}

// ==================== 可转债 ====================

export interface ConvertibleBondData {
  hot_bonds: Record<string, unknown>[]
  low_premium: Record<string, unknown>[]
  high_yield: Record<string, unknown>[]
  events: { code: string; name: string; event: string; date: string }[]
  update_time: string
}

// ==================== 加密货币 ====================

export interface CryptoCoin {
  name: string
  symbol: string
  price: number
  change_24h: number
  market_cap?: number
  volume?: number
}

export interface CryptoData {
  market_overview: CryptoCoin[]
  top_gainers: CryptoCoin[]
  stablecoin_mcap: number | null
  defi_tvl: unknown[]
  update_time: string
}

export interface AirdropData {
  potential_airdrops: { name: string; chain: string; status: string; description: string; url: string }[]
  active_campaigns: unknown[]
  defi_protocols: { name: string; chain: string; tvl: number; category: string; url: string }[]
  update_time: string
}

// ==================== 投资摘要 ====================

export interface InvestmentSummary {
  advices: string[]
  risks: string[]
  sentiment: string
}

// ==================== 完整简报 ====================

export interface DailyBriefing {
  title: string
  market_overview: {
    china: ChinaMarket
    us: UsMarket
  }
  sector_performance: SectorItem[]
  top_movers: TopMovers
  fund_flow: FundFlowItem[]
  macro_indicators: { china: ChinaMacroData }
  market_sentiment: MarketSentiment
  market_sentiment_v3: SentimentV3
  investment_summary: InvestmentSummary
  critical_events: CriticalEvent[]
  cross_validated_news: CrossValidatedNews[]
  value_investing: ValueInvestingData
  arbitrage: ArbitrageData
  convertible_bonds: ConvertibleBondData
  crypto: CryptoData
  airdrops: AirdropData
  overseas_news: OverseasNewsData
  update_time: string
}
