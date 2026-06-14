import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { PageSection, TabBar, DataTable, LoadingSpinner, EmptyState, StatCard, StatCardGroup, Tag } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

interface RiskTag {
  tag: string
  level: 'high' | 'medium' | 'low'
  desc: string
  mitigation?: string
  recent_policy?: string
}

interface ExchangeRateData {
  latest_rate: number
  latest_date: string
  change_7d_pct: number
  change_30d_pct: number
  change_90d_pct: number
  trend: string
  trend_desc: string
  export_impact: 'positive' | 'negative' | 'neutral'
  high_fx_sensitivity_stocks: { code: string; name: string; est_overseas_pct: number; revenue_fx_impact_pct: number }[]
  update_time: string
  data_source: string
}

interface PeerRanking {
  roe_rank?: number
  roe_total?: number
  dividend_rank?: number
  dividend_total?: number
  pe_rank?: number
  pe_total?: number
  overseas_rank?: number
  overseas_total?: number
}

interface TariffRiskInfo {
  risk_level?: string
  score?: number
  detail?: string
  mitigation?: string
  recent_policy?: string
}

interface ExportStock {
  code: string
  name: string
  market: 'A' | 'HK'
  price: number
  change_pct: number
  pe: number | null
  pb: number | null
  market_cap: number | null
  roe: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
  revenue_growth: number | null
  profit_growth: number | null
  dividend_yield: number | null
  consecutive_years: number | null
  dividend_ratio: number | null
  report_period: string
  industry: string
  export_intensity: string
  est_overseas_pct: number
  export_score: number
  export_detail: string
  buffett_score: number
  buffett_detail: string
  munger_score: number
  munger_detail: string
  li_lu_score: number
  li_lu_detail: string
  duan_score: number
  duan_detail: string
  vi_avg_score: number
  combined_score: number
  risk_adjusted_score: number
  risk_tags: RiskTag[]
  risk_penalty: number
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
  peer_rankings?: PeerRanking
  peer_stats?: Record<string, { mean: number; median: number; min: number; max: number }>
  peer_count?: number
  tariff_risk?: TariffRiskInfo
  main_export_markets?: string[]
  competitive_advantage?: string
}

interface ScoringDimension {
  dimension: string
  description: string
  criteria: string[]
  japan_parallel?: string
}

interface IndustryCategory {
  name: string
  examples: string
  global_note?: string
}

interface ValueMaster {
  name: string
  focus: string
  framework: string
  key_insight: string
  criteria: string[]
}

interface ValueIntegration {
  title: string
  description: string
  scoring_model: string
  masters: ValueMaster[]
  match_levels: Record<string, string>
  risks: string[]
}

interface Philosophy {
  name: string
  title: string
  core_thesis: string
  core_idea: string
  japan_mirror: { title: string; content: string; lesson: string }
  china_context: { title: string; content: string; implication: string }
  why_export_why_dividend: { title: string; reasons: string[] }
  scoring_dimensions: ScoringDimension[]
  hard_filters: string[]
  industry_categories: IndustryCategory[]
  value_investing_integration?: ValueIntegration
  risk_tags_system?: {
    title: string
    description: string
    tags: { tag: string; level: string; desc: string }[]
    scoring_impact: string
    new_features?: string[]
  }
  tariff_risk_matrix?: {
    title: string
    description: string
    disclaimer: string
    critical_risks: { industry: string; score: number; detail: string }[]
    high_risks: { industry: string; score: number; detail: string }[]
    low_risks: { industry: string; score: number; detail: string }[]
  }
  exchange_rate_monitoring?: {
    title: string
    description: string
    data_source: string
    update_frequency: string
    metrics: string[]
    impact_logic: string
  }
  peer_comparison?: {
    title: string
    description: string
    dimensions: string[]
    additional_info: string
  }
}

export default function ExportChampions() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'screener'>('philosophy')
  const [stocks, setStocks] = useState<ExportStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)
  const [fxData, setFxData] = useState<ExchangeRateData | null>(null)
  const [peerComparison, setPeerComparison] = useState<Record<string, any> | null>(null)

  // Screener params
  const [market, setMarket] = useState<'all' | 'A' | 'HK'>('all')
  const [minScore, setMinScore] = useState(0)
  const [minDivYield, setMinDivYield] = useState(1.5)
  const [topN, setTopN] = useState(50)

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/export-champions/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取筛选理念失败:', e)
    }
  }, [])

  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        market,
        min_score: minScore,
        min_dividend_yield: minDivYield,
        top_n: topN,
      }
      const res = await axios.get(`${API_BASE}/export-champions/screener`, { params })
      setStocks(res.data.stocks || [])
      setTotal(res.data.total || 0)
      setUpdateTime(res.data.update_time || '')
      setFxData(res.data.exchange_rate || null)
      setPeerComparison(res.data.peer_comparison || null)
    } catch (e) {
      console.error('筛选失败:', e)
    } finally {
      setLoading(false)
    }
  }, [market, minScore, minDivYield, topN])

  useEffect(() => {
    loadPhilosophy()
  }, [loadPhilosophy])

  useEffect(() => {
    if (activeTab === 'screener') loadStocks()
  }, [activeTab, loadStocks])

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#3fb950'
    if (score >= 65) return '#58a6ff'
    if (score >= 50) return '#d29922'
    return '#f85149'
  }

  const getMatchLevelText = (level: string) => {
    switch (level) {
      case 'excellent': return '优秀'
      case 'good': return '良好'
      case 'fair': return '一般'
      case 'poor': return '较差'
      default: return level
    }
  }

  const getMatchLevelColor = (level: string) => {
    switch (level) {
      case 'excellent': return '#3fb950'
      case 'good': return '#58a6ff'
      case 'fair': return '#d29922'
      case 'poor': return '#f85149'
      default: return '#8b949e'
    }
  }

  const getMarketTag = (market: string) => {
    switch (market) {
      case 'A': return { text: 'A股', color: '#f85149' }
      case 'HK': return { text: '港股', color: '#d29922' }
      default: return { text: market, color: '#8b949e' }
    }
  }

  const getIntensityColor = (intensity: string) => {
    switch (intensity) {
      case 'high': return '#3fb950'
      case 'medium': return '#d29922'
      case 'low': return '#8b949e'
      default: return '#8b949e'
    }
  }

  const getIntensityText = (intensity: string) => {
    switch (intensity) {
      case 'high': return '高'
      case 'medium': return '中'
      case 'low': return '低'
      default: return intensity
    }
  }

  const getRiskTagColor = (level: string) => {
    switch (level) {
      case 'high': return '#f85149'
      case 'medium': return '#d29922'
      case 'low': return '#8b949e'
      default: return '#8b949e'
    }
  }

  return (
    <div className="cb-page">
      <PageSection title="出口冠军筛选" compact>
        <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>筛选具备全球竞争力且分红稳健的中国企业</span>
      </PageSection>

      <TabBar
        tabs={[
          { key: 'philosophy', label: '筛选理念' },
          { key: 'screener', label: '股票筛选' },
        ]}
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'philosophy' | 'screener')}
        size="small"
        style={{ marginBottom: 16 }}
      />

      {/* Philosophy Tab */}
      {activeTab === 'philosophy' && philosophy && (
        <div>
          {/* Core Thesis */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(88,166,255,0.12), rgba(63,185,80,0.08))',
            borderRadius: 10, padding: 20, marginBottom: 16,
            border: '1px solid rgba(88,166,255,0.3)',
          }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#58a6ff', marginBottom: 8 }}>
              {philosophy.title}
            </div>
            <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.7, fontWeight: 500 }}>
              {philosophy.core_thesis}
            </div>
          </div>

          {/* Core Idea */}
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">筛选逻辑</div>
              <div className="note-value" style={{ fontSize: 14, lineHeight: 1.6 }}>
                {philosophy.core_idea}
              </div>
            </div>
          </div>

          {/* Japan Mirror */}
          <PageSection title={philosophy.japan_mirror.title} style={{ marginBottom: 16 }}>
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
              border: '1px solid var(--border-primary)', marginBottom: 12,
            }}>
              <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: 13, lineHeight: 1.7 }}>
                {philosophy.japan_mirror.content}
              </p>
            </div>
            <div style={{
              padding: '10px 14px', background: 'rgba(248,81,73,0.08)', borderRadius: 8,
              borderLeft: '3px solid #f85149', color: '#f85149', fontSize: 13, fontWeight: 500,
            }}>
              {philosophy.japan_mirror.lesson}
            </div>
          </PageSection>

          {/* China Context */}
          <PageSection title={philosophy.china_context.title} style={{ marginBottom: 16 }}>
            <div style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
              border: '1px solid var(--border-primary)', marginBottom: 12,
            }}>
              <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: 13, lineHeight: 1.7 }}>
                {philosophy.china_context.content}
              </p>
            </div>
            <div style={{
              padding: '10px 14px', background: 'rgba(210,153,34,0.08)', borderRadius: 8,
              borderLeft: '3px solid #d29922', color: '#d29922', fontSize: 13, fontWeight: 500,
            }}>
              {philosophy.china_context.implication}
            </div>
          </PageSection>

          {/* Why Export + Dividend */}
          <PageSection title={philosophy.why_export_why_dividend.title} style={{ marginBottom: 16 }}>
            <div style={{ display: 'grid', gap: 8 }}>
              {philosophy.why_export_why_dividend.reasons.map((r, i) => (
                <div key={i} style={{
                  background: 'var(--bg-secondary)', borderRadius: 8, padding: '10px 14px',
                  border: '1px solid var(--border-primary)', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6,
                }}>
                  <span style={{ color: '#58a6ff', fontWeight: 700, marginRight: 8 }}>{i + 1}.</span>
                  {r}
                </div>
              ))}
            </div>
          </PageSection>

          {/* Hard Filters */}
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>硬性筛选条件</h3>
            <div className="arb-notes-grid">
              {philosophy.hard_filters.map((f, i) => (
                <div key={i} className="arb-note-item">
                  <div className="note-value" style={{ fontSize: 13 }}>{f}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Scoring Dimensions */}
          <PageSection title="评分维度 (满分100)" style={{ marginBottom: 16 }}>
            {philosophy.scoring_dimensions.map((dim, i) => (
              <div key={i} style={{
                background: 'var(--bg-secondary)',
                borderRadius: 8,
                padding: 16,
                marginBottom: 12,
                border: '1px solid var(--border-primary)',
              }}>
                <h4 style={{ color: 'var(--text-primary)', margin: '0 0 8px' }}>{dim.dimension}</h4>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13 }}>
                  {dim.description}
                </p>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {dim.criteria.map((c, j) => (
                    <li key={j} style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 4 }}>{c}</li>
                  ))}
                </ul>
                {dim.japan_parallel && (
                  <div style={{
                    marginTop: 8, padding: '6px 10px', background: 'rgba(88,166,255,0.08)',
                    borderRadius: 6, borderLeft: '2px solid #58a6ff', color: '#58a6ff', fontSize: 12,
                  }}>
                    {dim.japan_parallel}
                  </div>
                )}
              </div>
            ))}
          </PageSection>

          {/* Industry Categories */}
          <PageSection title="覆盖行业">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {philosophy.industry_categories.map((cat, i) => (
                <div key={i} style={{
                  background: 'var(--bg-secondary)',
                  borderRadius: 8,
                  padding: 14,
                  border: '1px solid var(--border-primary)',
                }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>{cat.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{cat.examples}</div>
                  {cat.global_note && (
                    <div style={{ fontSize: 12, color: '#d29922', lineHeight: 1.5 }}>{cat.global_note}</div>
                  )}
                </div>
              ))}
            </div>
          </PageSection>

          {/* Risk Tags System */}
          {philosophy.risk_tags_system && (
            <PageSection title={philosophy.risk_tags_system.title} style={{ marginTop: 16 }}>
              <div style={{
                background: 'linear-gradient(135deg, rgba(248,81,73,0.12), rgba(210,153,34,0.08))',
                borderRadius: 10, padding: 16, marginBottom: 16,
                border: '1px solid rgba(248,81,73,0.3)',
              }}>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13, lineHeight: 1.7 }}>
                  {philosophy.risk_tags_system.description}
                </p>
                <div style={{ fontSize: 13, color: '#f85149', fontWeight: 600 }}>
                  {philosophy.risk_tags_system.scoring_impact}
                </div>
              </div>

              <div style={{ display: 'grid', gap: 8 }}>
                {philosophy.risk_tags_system.tags.map((tag, i) => (
                  <div key={i} style={{
                    padding: '10px 14px',
                    background: 'var(--bg-secondary)',
                    borderRadius: 8,
                    border: '1px solid var(--border-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                  }}>
                    <span style={{
                      color: getRiskTagColor(tag.level),
                      fontWeight: 600,
                      fontSize: 12,
                      padding: '2px 8px',
                      borderRadius: 6,
                      background: `${getRiskTagColor(tag.level)}15`,
                      border: `1px solid ${getRiskTagColor(tag.level)}30`,
                      minWidth: 100,
                      textAlign: 'center',
                    }}>
                      {tag.tag}
                    </span>
                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      {tag.desc}
                    </span>
                  </div>
                ))}
              </div>
            </PageSection>
          )}

          {/* Tariff Risk Matrix */}
          {philosophy.tariff_risk_matrix && (
            <PageSection title={philosophy.tariff_risk_matrix.title} style={{ marginTop: 16 }}>
              <div style={{
                background: 'linear-gradient(135deg, rgba(248,81,73,0.12), rgba(210,153,34,0.08))',
                borderRadius: 10, padding: 16, marginBottom: 16,
                border: '1px solid rgba(248,81,73,0.3)',
              }}>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13, lineHeight: 1.7 }}>
                  {philosophy.tariff_risk_matrix.description}
                </p>
                <div style={{ fontSize: 12, color: '#d29922' }}>
                  {philosophy.tariff_risk_matrix.disclaimer}
                </div>
              </div>

              <h4 style={{ color: '#f85149', marginBottom: 8 }}>极高风险行业</h4>
              <div style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
                {philosophy.tariff_risk_matrix.critical_risks.map((r, i) => (
                  <div key={i} style={{
                    padding: '10px 14px', background: 'rgba(248,81,73,0.08)', borderRadius: 8,
                    border: '1px solid rgba(248,81,73,0.2)', display: 'flex', alignItems: 'center', gap: 12,
                  }}>
                    <span style={{
                      color: '#f85149', fontWeight: 700, fontSize: 14, padding: '2px 8px',
                      borderRadius: 6, background: 'rgba(248,81,73,0.15)', minWidth: 40, textAlign: 'center',
                    }}>
                      {r.score}
                    </span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.industry}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{r.detail}</span>
                  </div>
                ))}
              </div>

              <h4 style={{ color: '#d29922', marginBottom: 8 }}>高风险行业</h4>
              <div style={{ display: 'grid', gap: 6, marginBottom: 16 }}>
                {philosophy.tariff_risk_matrix.high_risks.map((r, i) => (
                  <div key={i} style={{
                    padding: '8px 12px', background: 'rgba(210,153,34,0.06)', borderRadius: 6,
                    border: '1px solid rgba(210,153,34,0.2)', display: 'flex', alignItems: 'center', gap: 10,
                  }}>
                    <span style={{ color: '#d29922', fontWeight: 700, fontSize: 13 }}>{r.score}</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>{r.industry}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{r.detail}</span>
                  </div>
                ))}
              </div>

              <h4 style={{ color: '#3fb950', marginBottom: 8 }}>低风险行业</h4>
              <div style={{ display: 'grid', gap: 6 }}>
                {philosophy.tariff_risk_matrix.low_risks.map((r, i) => (
                  <div key={i} style={{
                    padding: '8px 12px', background: 'rgba(63,185,80,0.04)', borderRadius: 6,
                    border: '1px solid rgba(63,185,80,0.15)', display: 'flex', alignItems: 'center', gap: 10,
                  }}>
                    <span style={{ color: '#3fb950', fontWeight: 700, fontSize: 13 }}>{r.score}</span>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>{r.industry}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{r.detail}</span>
                  </div>
                ))}
              </div>
            </PageSection>
          )}

          {/* Exchange Rate Monitoring */}
          {philosophy.exchange_rate_monitoring && (
            <PageSection title={philosophy.exchange_rate_monitoring.title} style={{ marginTop: 16 }}>
              <div style={{
                background: 'linear-gradient(135deg, rgba(88,166,255,0.12), rgba(63,185,80,0.08))',
                borderRadius: 10, padding: 16, marginBottom: 16,
                border: '1px solid rgba(88,166,255,0.3)',
              }}>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13, lineHeight: 1.7 }}>
                  {philosophy.exchange_rate_monitoring.description}
                </p>
                <div style={{ fontSize: 12, color: '#58a6ff' }}>
                  数据源: {philosophy.exchange_rate_monitoring.data_source} | 更新频率: {philosophy.exchange_rate_monitoring.update_frequency}
                </div>
              </div>
              <div style={{
                padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 8,
                border: '1px solid var(--border-primary)', marginBottom: 12,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>影响逻辑</div>
                <div style={{ fontSize: 13, color: '#d29922', lineHeight: 1.6 }}>
                  {philosophy.exchange_rate_monitoring.impact_logic}
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                {philosophy.exchange_rate_monitoring.metrics.map((m, i) => (
                  <div key={i} style={{
                    padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6,
                    border: '1px solid var(--border-primary)', fontSize: 13, color: 'var(--text-secondary)',
                  }}>
                    {m}
                  </div>
                ))}
              </div>
            </PageSection>
          )}

          {/* Peer Comparison */}
          {philosophy.peer_comparison && (
            <PageSection title={philosophy.peer_comparison.title} style={{ marginTop: 16 }}>
              <p style={{ color: 'var(--text-secondary)', margin: '0 0 12px', fontSize: 13, lineHeight: 1.7 }}>
                {philosophy.peer_comparison.description}
              </p>
              <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
                {philosophy.peer_comparison.dimensions.map((d, i) => (
                  <div key={i} style={{
                    padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6,
                    border: '1px solid var(--border-primary)', fontSize: 13, color: 'var(--text-secondary)',
                  }}>
                    {d}
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 12, color: '#58a6ff' }}>
                {philosophy.peer_comparison.additional_info}
              </div>
            </PageSection>
          )}

          {/* Value Investing Integration */}
          {philosophy.value_investing_integration && (
            <PageSection title={philosophy.value_investing_integration.title} style={{ marginTop: 16 }}>
              <div style={{
                background: 'linear-gradient(135deg, rgba(63,185,80,0.12), rgba(210,153,34,0.08))',
                borderRadius: 10, padding: 16, marginBottom: 16,
                border: '1px solid rgba(63,185,80,0.3)',
              }}>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13, lineHeight: 1.7 }}>
                  {philosophy.value_investing_integration.description}
                </p>
                <div style={{ fontSize: 13, color: '#3fb950', fontWeight: 600 }}>
                  {philosophy.value_investing_integration.scoring_model}
                </div>
              </div>

              {/* Master Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12, marginBottom: 16 }}>
                {philosophy.value_investing_integration.masters.map((master, i) => {
                  const colors = ['#58a6ff', '#d29922', '#f0883e', '#bc8cff']
                  const c = colors[i]
                  return (
                    <div key={i} style={{
                      background: 'var(--bg-secondary)',
                      borderRadius: 8, padding: 16,
                      border: `1px solid ${c}40`,
                      borderTop: `3px solid ${c}`,
                    }}>
                      <div style={{ fontWeight: 700, color: c, fontSize: 15, marginBottom: 6 }}>
                        {master.name}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                        {master.focus}
                      </div>
                      <div style={{
                        padding: '6px 10px', background: `${c}10`, borderRadius: 6,
                        borderLeft: `2px solid ${c}`, color: c, fontSize: 12, marginBottom: 8,
                        lineHeight: 1.6, fontStyle: 'italic',
                      }}>
                        {master.key_insight}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, fontWeight: 600 }}>
                        评分框架: {master.framework}
                      </div>
                      <ul style={{ margin: 0, paddingLeft: 16 }}>
                        {master.criteria.map((cr, j) => (
                          <li key={j} style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 2 }}>{cr}</li>
                        ))}
                      </ul>
                    </div>
                  )
                })}
              </div>

              {/* Match Levels */}
              <div className="arb-notes" style={{ marginBottom: 16 }}>
                <h4 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>综合匹配等级</h4>
                <div className="arb-notes-grid">
                  {Object.entries(philosophy.value_investing_integration.match_levels).map(([level, desc]) => (
                    <div key={level} className="arb-note-item">
                      <div className="note-label">{getMatchLevelText(level)}</div>
                      <div className="note-value" style={{ fontSize: 12 }}>{desc}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Risks */}
              <div className="arb-risk-section">
                <h4 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>风险提示</h4>
                <div style={{ display: 'grid', gap: 6 }}>
                  {philosophy.value_investing_integration.risks.map((r, i) => (
                    <div key={i} style={{
                      padding: '8px 12px', background: 'rgba(248,81,73,0.06)', borderRadius: 6,
                      borderLeft: '2px solid #f85149', fontSize: 12, color: 'var(--text-secondary)',
                    }}>
                      {r}
                    </div>
                  ))}
                </div>
              </div>
            </PageSection>
          )}
        </div>
      )}

      {/* Screener Tab */}
      {activeTab === 'screener' && (
        <div>
          {/* Filter Bar */}
          <div style={{
            display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap',
            alignItems: 'center',
          }}>
            {/* Exchange Rate Widget */}
            {fxData && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 12px', borderRadius: 6,
                background: fxData.export_impact === 'positive' ? 'rgba(63,185,80,0.1)' :
                           fxData.export_impact === 'negative' ? 'rgba(248,81,73,0.1)' : 'var(--bg-secondary)',
                border: `1px solid ${fxData.export_impact === 'positive' ? 'rgba(63,185,80,0.3)' :
                         fxData.export_impact === 'negative' ? 'rgba(248,81,73,0.3)' : 'var(--border-primary)'}`,
                fontSize: 12,
              }}>
                <span style={{ color: 'var(--text-secondary)' }}>USD/CNY</span>
                <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{fxData.latest_rate}</span>
                <span style={{
                  color: fxData.change_30d_pct > 0 ? '#3fb950' : fxData.change_30d_pct < 0 ? '#f85149' : 'var(--text-secondary)',
                  fontWeight: 600,
                }}>
                  {fxData.change_30d_pct > 0 ? '+' : ''}{fxData.change_30d_pct}% (30d)
                </span>
                <span style={{
                  padding: '1px 6px', borderRadius: 4, fontSize: 11,
                  background: fxData.export_impact === 'positive' ? 'rgba(63,185,80,0.15)' :
                             fxData.export_impact === 'negative' ? 'rgba(248,81,73,0.15)' : 'rgba(139,148,158,0.15)',
                  color: fxData.export_impact === 'positive' ? '#3fb950' :
                         fxData.export_impact === 'negative' ? '#f85149' : '#8b949e',
                }}>
                  {fxData.trend}
                </span>
              </div>
            )}
            <select value={market} onChange={e => setMarket(e.target.value as any)}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value="all">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
            </select>
            <select value={minScore} onChange={e => setMinScore(Number(e.target.value))}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value={0}>全部分数</option>
              <option value={50}>50分以上</option>
              <option value={60}>60分以上</option>
              <option value={65}>65分以上</option>
              <option value={70}>70分以上</option>
              <option value={80}>80分以上</option>
            </select>
            <select value={minDivYield} onChange={e => setMinDivYield(Number(e.target.value))}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value={0}>不限股息率</option>
              <option value={1}>股息率{'>'}=1%</option>
              <option value={1.5}>股息率{'>'}=1.5%</option>
              <option value={2}>股息率{'>'}=2%</option>
              <option value={3}>股息率{'>'}=3%</option>
              <option value={4}>股息率{'>'}=4%</option>
            </select>
            <select value={topN} onChange={e => setTopN(Number(e.target.value))}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value={20}>前20只</option>
              <option value={50}>前50只</option>
              <option value={100}>全部</option>
            </select>
            <button onClick={loadStocks}
              style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              筛选
            </button>
            {updateTime && (
              <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                更新: {updateTime} | 共{total}只
              </span>
            )}
          </div>

          {/* Results Table */}
          {loading ? (
            <LoadingSpinner text="筛选中..." />
          ) : (
            <table className="arb-table">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>市场</th>
                  <th>行业</th>
                  <th>出口强度</th>
                  <th>海外占比</th>
                  <th>价格</th>
                  <th>股息率</th>
                  <th>出口分</th>
                  <th>巴菲特</th>
                  <th>芒格</th>
                  <th>李录</th>
                  <th>段永平</th>
                  <th>综合</th>
                  <th>风险调整</th>
                  <th>风险标签</th>
                  <th>匹配</th>
                </tr>
              </thead>
              <tbody>
                {stocks.map(stock => {
                  const mkt = getMarketTag(stock.market)
                  const isExpanded = expandedStock === stock.code
                  return (
                    <>
                      <tr key={stock.code}
                        onClick={() => setExpandedStock(isExpanded ? null : stock.code)}
                        style={{ cursor: 'pointer' }}>
                        <td style={{ fontFamily: 'monospace' }}>{stock.code}</td>
                        <td>{stock.name}</td>
                        <td><span style={{ color: mkt.color, fontSize: 12, fontWeight: 600 }}>{mkt.text}</span></td>
                        <td style={{ fontSize: 12, color: '#d29922' }}>{stock.industry}</td>
                        <td>
                          <span style={{
                            color: getIntensityColor(stock.export_intensity),
                            fontSize: 12, fontWeight: 600,
                          }}>
                            {getIntensityText(stock.export_intensity)}
                          </span>
                        </td>
                        <td style={{ fontSize: 12 }}>{stock.est_overseas_pct}%</td>
                        <td>{stock.price?.toFixed(2)}</td>
                        <td>{stock.dividend_yield?.toFixed(1) ?? '-'}%</td>
                        <td>
                          <span style={{ color: getScoreColor(stock.export_score), fontWeight: 600 }}>
                            {stock.export_score}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: getScoreColor(stock.buffett_score), fontWeight: 600 }}>
                            {stock.buffett_score}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: getScoreColor(stock.munger_score), fontWeight: 600 }}>
                            {stock.munger_score}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: getScoreColor(stock.li_lu_score), fontWeight: 600 }}>
                            {stock.li_lu_score}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: getScoreColor(stock.duan_score), fontWeight: 600 }}>
                            {stock.duan_score}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: getScoreColor(stock.combined_score), fontWeight: 700, fontSize: 16 }}>
                            {stock.combined_score}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: getScoreColor(stock.risk_adjusted_score), fontWeight: 700, fontSize: 14 }}>
                            {stock.risk_adjusted_score}
                          </span>
                          {stock.risk_penalty > 0 && (
                            <span style={{ color: '#f85149', fontSize: 10, marginLeft: 4 }}>
                              (-{stock.risk_penalty})
                            </span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', maxWidth: 120 }}>
                            {stock.risk_tags?.slice(0, 2).map((tag, i) => (
                              <span key={i} style={{
                                color: getRiskTagColor(tag.level),
                                fontSize: 10,
                                padding: '1px 4px',
                                borderRadius: 4,
                                background: `${getRiskTagColor(tag.level)}15`,
                                border: `1px solid ${getRiskTagColor(tag.level)}30`,
                              }}>
                                {tag.tag}
                              </span>
                            ))}
                            {(stock.risk_tags?.length || 0) > 2 && (
                              <span style={{ color: '#8b949e', fontSize: 10 }}>+{stock.risk_tags!.length - 2}</span>
                            )}
                          </div>
                        </td>
                        <td>
                          <span style={{
                            color: getMatchLevelColor(stock.match_level),
                            fontSize: 12,
                            padding: '2px 8px',
                            borderRadius: 10,
                            background: `${getMatchLevelColor(stock.match_level)}20`,
                          }}>
                            {getMatchLevelText(stock.match_level)}
                          </span>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${stock.code}-detail`}>
                          <td colSpan={17} style={{ padding: '12px 16px', background: 'var(--bg-secondary)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                              <div>
                                <strong style={{ color: '#58a6ff' }}>出口竞争力 ({stock.export_score}分)</strong>
                                <br />
                                {stock.export_detail.split(' | ').map((d, i) => (
                                  <span key={i}>{d}{i < stock.export_detail.split(' | ').length - 1 && ' → '}</span>
                                ))}
                              </div>
                              <div>
                                <strong style={{ color: '#3fb950' }}>巴菲特 ({stock.buffett_score}分)</strong>
                                <br />
                                {stock.buffett_detail.split(' | ').map((d, i) => (
                                  <span key={i}>{d}{i < stock.buffett_detail.split(' | ').length - 1 && ' · '}</span>
                                ))}
                              </div>
                              <div>
                                <strong style={{ color: '#d29922' }}>芒格 ({stock.munger_score}分)</strong>
                                <br />
                                {stock.munger_detail.split(' | ').map((d, i) => (
                                  <span key={i}>{d}{i < stock.munger_detail.split(' | ').length - 1 && ' · '}</span>
                                ))}
                              </div>
                              <div>
                                <strong style={{ color: '#f0883e' }}>李录 ({stock.li_lu_score}分)</strong>
                                <br />
                                {stock.li_lu_detail.split(' | ').map((d, i) => (
                                  <span key={i}>{d}{i < stock.li_lu_detail.split(' | ').length - 1 && ' · '}</span>
                                ))}
                              </div>
                              <div>
                                <strong style={{ color: '#bc8cff' }}>段永平 ({stock.duan_score}分)</strong>
                                <br />
                                {stock.duan_detail.split(' | ').map((d, i) => (
                                  <span key={i}>{d}{i < stock.duan_detail.split(' | ').length - 1 && ' · '}</span>
                                ))}
                              </div>
                              <div>
                                <strong style={{ color: 'var(--text-primary)' }}>基本面数据</strong>
                                <div style={{ marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                  <span>ROE: {stock.roe?.toFixed(1) ?? '-'}%</span>
                                  <span>毛利率: {stock.gross_margin?.toFixed(1) ?? '-'}%</span>
                                  <span>净利率: {stock.net_margin?.toFixed(1) ?? '-'}%</span>
                                  <span>负债率: {stock.debt_ratio?.toFixed(1) ?? '-'}%</span>
                                  <span>PE: {stock.pe?.toFixed(1) ?? '-'}</span>
                                  <span>PB: {stock.pb?.toFixed(1) ?? '-'}</span>
                                  <span>连续分红: {stock.consecutive_years ?? '-'}年</span>
                                  <span>报告期: {stock.report_period || '-'}</span>
                                </div>
                              </div>

                              {/* 竞争优势 & 主要出口市场 */}
                              <div>
                                <strong style={{ color: '#58a6ff' }}>竞争优势 & 出口市场</strong>
                                <div style={{ marginTop: 4 }}>
                                  {stock.competitive_advantage && (
                                    <div style={{ marginBottom: 4 }}>
                                      <span style={{ color: '#d29922', fontWeight: 600 }}>竞争壁垒: </span>
                                      {stock.competitive_advantage}
                                    </div>
                                  )}
                                  {stock.main_export_markets && stock.main_export_markets.length > 0 && (
                                    <div>
                                      <span style={{ color: '#d29922', fontWeight: 600 }}>主要市场: </span>
                                      {stock.main_export_markets.join(' / ')}
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* 同行业对比 */}
                              {stock.peer_rankings && stock.peer_count && stock.peer_count > 1 && (
                                <div>
                                  <strong style={{ color: '#bc8cff' }}>同行业排名 ({stock.industry}, {stock.peer_count}家)</strong>
                                  <div style={{ marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                    {stock.peer_rankings.roe_rank != null && (
                                      <span>ROE排名: <b style={{ color: stock.peer_rankings.roe_rank <= Math.ceil((stock.peer_rankings.roe_total ?? 0) / 3) ? '#3fb950' : '#d29922' }}>
                                        {stock.peer_rankings.roe_rank}/{stock.peer_rankings.roe_total}
                                      </b></span>
                                    )}
                                    {stock.peer_rankings.dividend_rank != null && (
                                      <span>股息率排名: <b style={{ color: stock.peer_rankings.dividend_rank <= Math.ceil((stock.peer_rankings.dividend_total ?? 0) / 3) ? '#3fb950' : '#d29922' }}>
                                        {stock.peer_rankings.dividend_rank}/{stock.peer_rankings.dividend_total}
                                      </b></span>
                                    )}
                                    {stock.peer_rankings.pe_rank != null && (
                                      <span>估值排名: <b style={{ color: stock.peer_rankings.pe_rank <= Math.ceil((stock.peer_rankings.pe_total ?? 0) / 3) ? '#3fb950' : '#d29922' }}>
                                        {stock.peer_rankings.pe_rank}/{stock.peer_rankings.pe_total}
                                      </b> (越低越好)</span>
                                    )}
                                    {stock.peer_rankings.overseas_rank != null && (
                                      <span>海外占比排名: <b style={{ color: stock.peer_rankings.overseas_rank <= Math.ceil((stock.peer_rankings.overseas_total ?? 0) / 3) ? '#3fb950' : '#d29922' }}>
                                        {stock.peer_rankings.overseas_rank}/{stock.peer_rankings.overseas_total}
                                      </b></span>
                                    )}
                                  </div>
                                  {stock.peer_stats && (
                                    <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                                      行业均值 -- ROE: {stock.peer_stats.roe?.mean ?? '-'}% | 毛利率: {stock.peer_stats.gross_margin?.mean ?? '-'}% | 股息率: {stock.peer_stats.dividend_yield?.mean ?? '-'}%
                                    </div>
                                  )}
                                </div>
                              )}

                              {/* 关税/贸易政策风险 */}
                              {stock.tariff_risk && stock.tariff_risk.detail && (
                                <div style={{ gridColumn: 'span 2' }}>
                                  <strong style={{ color: stock.tariff_risk.risk_level === 'critical' ? '#f85149' : stock.tariff_risk.risk_level === 'high' ? '#d29922' : '#58a6ff' }}>
                                    关税/贸易政策风险评估
                                  </strong>
                                  <div style={{
                                    marginTop: 6, padding: '10px 14px', borderRadius: 8,
                                    background: stock.tariff_risk.risk_level === 'critical' ? 'rgba(248,81,73,0.08)' : 'var(--bg-primary)',
                                    border: `1px solid ${stock.tariff_risk.risk_level === 'critical' ? 'rgba(248,81,73,0.3)' : 'var(--border-primary)'}`,
                                  }}>
                                    <div style={{ marginBottom: 4 }}>
                                      <span style={{ fontWeight: 600 }}>风险等级: </span>
                                      <span style={{
                                        color: stock.tariff_risk.risk_level === 'critical' ? '#f85149' : stock.tariff_risk.risk_level === 'high' ? '#d29922' : '#8b949e',
                                        fontWeight: 700,
                                      }}>
                                        {stock.tariff_risk.risk_level === 'critical' ? '极高' : stock.tariff_risk.risk_level === 'high' ? '高' : stock.tariff_risk.risk_level === 'medium' ? '中' : '低'}
                                        ({stock.tariff_risk.score}/100)
                                      </span>
                                    </div>
                                    <div style={{ marginBottom: 4 }}>{stock.tariff_risk.detail}</div>
                                    {stock.tariff_risk.recent_policy && (
                                      <div style={{ color: '#d29922', marginBottom: 4 }}>最新政策: {stock.tariff_risk.recent_policy}</div>
                                    )}
                                    {stock.tariff_risk.mitigation && (
                                      <div style={{ color: '#3fb950' }}>应对措施: {stock.tariff_risk.mitigation}</div>
                                    )}
                                  </div>
                                </div>
                              )}

                              {stock.risk_tags && stock.risk_tags.length > 0 && (
                                <div style={{ gridColumn: 'span 2' }}>
                                  <strong style={{ color: '#f85149' }}>风险提示</strong>
                                  <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                                    {stock.risk_tags.map((tag, i) => (
                                      <div key={i} style={{
                                        padding: '8px 12px',
                                        background: `${getRiskTagColor(tag.level)}08`,
                                        borderRadius: 6,
                                        borderLeft: `3px solid ${getRiskTagColor(tag.level)}`,
                                      }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: tag.mitigation ? 4 : 0 }}>
                                          <span style={{
                                            color: getRiskTagColor(tag.level),
                                            fontWeight: 600,
                                            fontSize: 12,
                                            padding: '2px 6px',
                                            borderRadius: 4,
                                            background: `${getRiskTagColor(tag.level)}15`,
                                          }}>
                                            {tag.tag}
                                          </span>
                                          <span style={{ fontSize: 12 }}>{tag.desc}</span>
                                        </div>
                                        {tag.mitigation && (
                                          <div style={{ fontSize: 11, color: '#3fb950', paddingLeft: 8, marginTop: 2 }}>
                                            应对: {tag.mitigation}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
                {stocks.length === 0 && !loading && (
                  <tr>
                    <td colSpan={17}>
                      <EmptyState title="暂无符合条件的股票" description="请调整筛选条件后重试" />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
