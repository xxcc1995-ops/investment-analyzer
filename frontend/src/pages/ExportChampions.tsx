import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

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
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
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
}

export default function ExportChampions() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'screener'>('philosophy')
  const [stocks, setStocks] = useState<ExportStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

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

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>出口冠军筛选</h2>
            <span className="stock-code">筛选具备全球竞争力且分红稳健的中国企业</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button className={`tab-btn ${activeTab === 'philosophy' ? 'active' : ''}`}
          onClick={() => setActiveTab('philosophy')}>筛选理念</button>
        <button className={`tab-btn ${activeTab === 'screener' ? 'active' : ''}`}
          onClick={() => setActiveTab('screener')}>股票筛选</button>
      </div>

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
          <div className="arb-risk-section" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>{philosophy.japan_mirror.title}</h3>
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
          </div>

          {/* China Context */}
          <div className="arb-risk-section" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>{philosophy.china_context.title}</h3>
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
          </div>

          {/* Why Export + Dividend */}
          <div className="arb-risk-section" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>{philosophy.why_export_why_dividend.title}</h3>
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
          </div>

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
          <div className="arb-risk-section" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>评分维度 (满分100)</h3>
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
          </div>

          {/* Industry Categories */}
          <div className="arb-risk-section">
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>覆盖行业</h3>
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
          </div>

          {/* Value Investing Integration */}
          {philosophy.value_investing_integration && (
            <div className="arb-risk-section" style={{ marginTop: 16 }}>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>
                {philosophy.value_investing_integration.title}
              </h3>
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
            </div>
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
            <div className="loading"><div className="spinner"></div>筛选中...</div>
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
                          <td colSpan={15} style={{ padding: '12px 16px', background: 'var(--bg-secondary)' }}>
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
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
                {stocks.length === 0 && !loading && (
                  <tr>
                    <td colSpan={15} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                      暂无符合条件的股票
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
