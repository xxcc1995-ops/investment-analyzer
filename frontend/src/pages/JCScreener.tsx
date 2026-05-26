import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface JCStock {
  code: string
  name: string
  market: 'A' | 'HK' | 'US'
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
  report_period: string
  jc_score: number
  jc_detail: string
  industry_position: string
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
}

interface FrameworkDimension {
  dimension: string
  description: string
  criteria: string[]
  key_insight: string
}

interface JCPhilosophy {
  name: string
  title: string
  era: string
  core_philosophy: string
  investment_framework: FrameworkDimension[]
  classic_quotes: string[]
  performance: {
    '2025_return': string
    top_holders: string
    target_2026: string
    note: string
  }
}

export default function JCScreener() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'screener' | 'signals'>('philosophy')
  const [stocks, setStocks] = useState<JCStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)
  const [philosophy, setPhilosophy] = useState<JCPhilosophy | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

  // Screener params
  const [market, setMarket] = useState<'all' | 'A' | 'HK' | 'US'>('all')
  const [minScore, setMinScore] = useState(50)
  const [maxPE, setMaxPE] = useState<number | ''>('')
  const [topN, setTopN] = useState(50)

  // Buy signals
  const [signals, setSignals] = useState<JCStock[]>([])
  const [signalsLoading, setSignalsLoading] = useState(false)
  const [buyRules, setBuyRules] = useState<Record<string, string>>({})

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/jc/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取投资体系失败:', e)
    }
  }, [])

  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { market, min_score: minScore, top_n: topN }
      if (maxPE !== '') params.max_pe = maxPE
      const res = await axios.get(`${API_BASE}/jc/screener`, { params })
      setStocks(res.data.stocks || [])
      setTotal(res.data.total || 0)
      setUpdateTime(res.data.update_time || '')
    } catch (e) {
      console.error('筛选失败:', e)
    } finally {
      setLoading(false)
    }
  }, [market, minScore, maxPE, topN])

  const loadSignals = useCallback(async () => {
    setSignalsLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/jc/buy-signals`, { params: { market: 'all' } })
      setSignals(res.data.stocks || [])
      setBuyRules(res.data.buy_rules || {})
    } catch (e) {
      console.error('获取买入信号失败:', e)
    } finally {
      setSignalsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPhilosophy()
  }, [loadPhilosophy])

  useEffect(() => {
    if (activeTab === 'screener') loadStocks()
    if (activeTab === 'signals') loadSignals()
  }, [activeTab, loadStocks, loadSignals])

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
      case 'US': return { text: '美股', color: '#58a6ff' }
      default: return { text: market, color: '#8b949e' }
    }
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>金渐成投资体系</h2>
            <span className="stock-code">第一兼唯一选股法 | 天玑/机哥</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button className={`tab-btn ${activeTab === 'philosophy' ? 'active' : ''}`}
          onClick={() => setActiveTab('philosophy')}>投资体系</button>
        <button className={`tab-btn ${activeTab === 'screener' ? 'active' : ''}`}
          onClick={() => setActiveTab('screener')}>股票筛选</button>
        <button className={`tab-btn ${activeTab === 'signals' ? 'active' : ''}`}
          onClick={() => setActiveTab('signals')}>买入信号</button>
      </div>

      {/* Philosophy Tab */}
      {activeTab === 'philosophy' && philosophy && (
        <div>
          {/* Core Philosophy */}
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">核心理念</div>
              <div className="note-value" style={{ fontSize: 14, lineHeight: 1.6 }}>
                {philosophy.core_philosophy}
              </div>
            </div>
            <div className="arb-note-item">
              <div className="note-label">2025年收益</div>
              <div className="note-value" style={{ color: '#3fb950', fontSize: 18, fontWeight: 700 }}>
                {philosophy.performance?.['2025_return'] || '~73%'}
              </div>
            </div>
            <div className="arb-note-item">
              <div className="note-label">2026年目标</div>
              <div className="note-value" style={{ color: '#58a6ff', fontSize: 18, fontWeight: 700 }}>
                {philosophy.performance?.target_2026 || '6-8%'}
              </div>
            </div>
          </div>

          {/* Investment Framework */}
          <div className="arb-risk-section" style={{ marginBottom: 16 }}>
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>投资框架六大维度</h3>
            {philosophy.investment_framework.map((dim, i) => (
              <div key={i} style={{
                background: 'var(--bg-secondary)',
                borderRadius: 8,
                padding: 16,
                marginBottom: 12,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h4 style={{ color: 'var(--text-primary)', margin: 0 }}>{dim.dimension}</h4>
                </div>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13 }}>
                  {dim.description}
                </p>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {dim.criteria.map((c, j) => (
                    <li key={j} style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 4 }}>{c}</li>
                  ))}
                </ul>
                {dim.key_insight && (
                  <div style={{
                    marginTop: 8,
                    padding: '8px 12px',
                    background: 'rgba(88,166,255,0.1)',
                    borderRadius: 6,
                    borderLeft: '3px solid #58a6ff',
                    color: '#58a6ff',
                    fontSize: 13,
                    fontStyle: 'italic',
                  }}>
                    "{dim.key_insight}"
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Classic Quotes */}
          <div className="arb-risk-section">
            <h3 style={{ color: 'var(--text-primary)', marginBottom: 12 }}>经典语录</h3>
            <div className="arb-notes-grid">
              {philosophy.classic_quotes.map((q, i) => (
                <div key={i} className="arb-note-item">
                  <div className="note-value" style={{ fontSize: 13, lineHeight: 1.5 }}>
                    "{q}"
                  </div>
                </div>
              ))}
            </div>
          </div>
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
              <option value="US">美股</option>
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
            <select value={maxPE === '' ? '' : maxPE} onChange={e => setMaxPE(e.target.value === '' ? '' : Number(e.target.value))}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value="">不限PE</option>
              <option value={15}>PE&lt;15</option>
              <option value={20}>PE&lt;20</option>
              <option value={25}>PE&lt;25</option>
              <option value={30}>PE&lt;30</option>
              <option value={40}>PE&lt;40</option>
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
                  <th>行业地位</th>
                  <th>价格</th>
                  <th>PE</th>
                  <th>ROE</th>
                  <th>毛利率</th>
                  <th>股息率</th>
                  <th>机哥评分</th>
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
                        <td style={{ fontSize: 12, color: '#d29922' }}>{stock.industry_position}</td>
                        <td>{stock.price?.toFixed(2)}</td>
                        <td>{stock.pe?.toFixed(1) ?? '-'}</td>
                        <td>{stock.roe?.toFixed(1) ?? '-'}%</td>
                        <td>{stock.gross_margin?.toFixed(1) ?? '-'}%</td>
                        <td>{stock.dividend_yield?.toFixed(1) ?? '-'}%</td>
                        <td>
                          <span style={{ color: getScoreColor(stock.jc_score), fontWeight: 700, fontSize: 16 }}>
                            {stock.jc_score}
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
                          <td colSpan={11} style={{ padding: '12px 16px', background: 'var(--bg-secondary)' }}>
                            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                              <strong style={{ color: 'var(--text-primary)' }}>评分明细：</strong>
                              <br />
                              {stock.jc_detail.split(' | ').map((d, i) => (
                                <span key={i}>
                                  {d}
                                  {i < stock.jc_detail.split(' | ').length - 1 && <span style={{ color: 'var(--border-primary)' }}> → </span>}
                                </span>
                              ))}
                            </div>
                            <div style={{ marginTop: 8, display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
                              <span>净利率: {stock.net_margin?.toFixed(1) ?? '-'}%</span>
                              <span>负债率: {stock.debt_ratio?.toFixed(1) ?? '-'}%</span>
                              <span>营收增速: {stock.revenue_growth?.toFixed(1) ?? '-'}%</span>
                              <span>利润增速: {stock.profit_growth?.toFixed(1) ?? '-'}%</span>
                              <span>报告期: {stock.report_period || '-'}</span>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Buy Signals Tab */}
      {activeTab === 'signals' && (
        <div>
          {/* Buy Rules */}
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            {Object.entries(buyRules).map(([key, rule]) => (
              <div key={key} className="arb-note-item">
                <div className="note-value" style={{ fontSize: 13 }}>{rule}</div>
              </div>
            ))}
          </div>

          {/* Signals Table */}
          {signalsLoading ? (
            <div className="loading"><div className="spinner"></div>加载中...</div>
          ) : (
            <table className="arb-table">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>市场</th>
                  <th>行业地位</th>
                  <th>价格</th>
                  <th>PE</th>
                  <th>ROE</th>
                  <th>股息率</th>
                  <th>机哥评分</th>
                  <th>匹配</th>
                </tr>
              </thead>
              <tbody>
                {signals.map(stock => {
                  const mkt = getMarketTag(stock.market)
                  return (
                    <tr key={stock.code}>
                      <td style={{ fontFamily: 'monospace' }}>{stock.code}</td>
                      <td>{stock.name}</td>
                      <td><span style={{ color: mkt.color, fontSize: 12, fontWeight: 600 }}>{mkt.text}</span></td>
                      <td style={{ fontSize: 12, color: '#d29922' }}>{stock.industry_position}</td>
                      <td>{stock.price?.toFixed(2)}</td>
                      <td>{stock.pe?.toFixed(1) ?? '-'}</td>
                      <td>{stock.roe?.toFixed(1) ?? '-'}%</td>
                      <td>{stock.dividend_yield?.toFixed(1) ?? '-'}%</td>
                      <td>
                        <span style={{ color: getScoreColor(stock.jc_score), fontWeight: 700, fontSize: 16 }}>
                          {stock.jc_score}
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
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
