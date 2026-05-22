import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'

const API_BASE = '/api'

interface ScoreDetail {
  score: number
  detail: string
}

interface VIStock {
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
  buffett_score: number
  munger_score: number
  li_lu_score: number
  duan_score: number
  score: number
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
  score_details: {
    buffett: ScoreDetail
    munger: ScoreDetail
    li_lu: ScoreDetail
    duan_yongping: ScoreDetail
  }
}

interface FrameworkDimension {
  dimension: string
  description: string
  criteria: string[]
  key_insight: string
}

interface MasterPhilosophy {
  name: string
  title: string
  era: string
  core_philosophy: string
  investment_framework: FrameworkDimension[]
  classic_quotes: string[]
  key_cases: string
}

interface VIPhilosophy {
  buffett: MasterPhilosophy
  munger: MasterPhilosophy
  li_lu: MasterPhilosophy
  duan_yongping: MasterPhilosophy
  scoring_system: {
    name: string
    description: string
    masters: { name: string; focus: string; weight: string }[]
    match_levels: Record<string, string>
  }
  risks: string[]
}

interface DCFResult {
  intrinsic_value: number
  buy_price: number
  enterprise_value: number
  fcf_projections: number[]
  terminal_value: number
  pv_fcf: number
  pv_terminal: number
  sensitivity: {
    growth_rates: string[]
    discount_rates: string[]
    matrix: number[][]
  }
}

const MASTER_COLORS: Record<string, string> = {
  buffett: '#58a6ff',
  munger: '#3fb950',
  li_lu: '#d29922',
  duan_yongping: '#bc8cff',
}

const MASTER_LABELS: Record<string, string> = {
  buffett: '巴菲特',
  munger: '芒格',
  li_lu: '李录',
  duan_yongping: '段永平',
}

export default function ValueInvesting() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'screener' | 'dcf'>('philosophy')
  const [stocks, setStocks] = useState<VIStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)
  const [philosophy, setPhilosophy] = useState<VIPhilosophy | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

  // Screener params
  const [market, setMarket] = useState<'all' | 'a' | 'hk' | 'us'>('all')
  const [master, setMaster] = useState<'combined' | 'buffett' | 'munger' | 'li_lu' | 'duan_yongping'>('combined')
  const [minScore, setMinScore] = useState(50)
  const [maxPE, setMaxPE] = useState(30)
  const [maxPB, setMaxPB] = useState(5)
  const [topN, setTopN] = useState(50)

  // DCF state
  const [dcfFcf, setDcfFcf] = useState('100')
  const [dcfGrowth, setDcfGrowth] = useState('10')
  const [dcfShares, setDcfShares] = useState('10')
  const [dcfDiscount, setDcfDiscount] = useState('10')
  const [dcfTerminal, setDcfTerminal] = useState('3')
  const [dcfSafety, setDcfSafety] = useState('30')
  const [dcfResult, setDcfResult] = useState<DCFResult | null>(null)
  const [dcfLoading, setDcfLoading] = useState(false)

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/value-investing/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取投资理念失败:', e)
    }
  }, [])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])

  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/value-investing/screener`, {
        params: { market, master, min_score: minScore, max_pe: maxPE, max_pb: maxPB, top_n: topN }
      })
      setStocks(res.data.stocks || [])
      setUpdateTime(res.data.update_time || '')
      setTotal(res.data.total || 0)
    } catch (e) {
      console.error('获取筛选数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [market, master, minScore, maxPE, maxPB, topN])

  const runDCF = useCallback(async () => {
    setDcfLoading(true)
    try {
      const res = await axios.post(`${API_BASE}/value-investing/dcf`, {
        current_fcf: parseFloat(dcfFcf) || 0,
        growth_rate: (parseFloat(dcfGrowth) || 0) / 100,
        shares: parseFloat(dcfShares) || 0,
        discount_rate: (parseFloat(dcfDiscount) || 10) / 100,
        terminal_growth_rate: (parseFloat(dcfTerminal) || 3) / 100,
        safety_margin: (parseFloat(dcfSafety) || 30) / 100,
      })
      setDcfResult(res.data)
    } catch (e) {
      console.error('DCF计算失败:', e)
    } finally {
      setDcfLoading(false)
    }
  }, [dcfFcf, dcfGrowth, dcfShares, dcfDiscount, dcfTerminal, dcfSafety])

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 65) return '#1890ff'
    if (score >= 50) return '#faad14'
    return '#ff4d4f'
  }

  const getMatchLevelText = (level: string) => {
    switch (level) {
      case 'excellent': return '优秀'
      case 'good': return '良好'
      case 'fair': return '一般'
      case 'poor': return '较差'
      default: return '-'
    }
  }

  const getMatchLevelColor = (level: string) => {
    switch (level) {
      case 'excellent': return '#52c41a'
      case 'good': return '#1890ff'
      case 'fair': return '#faad14'
      case 'poor': return '#ff4d4f'
      default: return '#666'
    }
  }

  const getMarketTag = (mkt: string) => {
    const colors: Record<string, string> = { A: '#f85149', HK: '#d29922', US: '#58a6ff' }
    return (
      <span style={{
        display: 'inline-block', padding: '1px 6px', borderRadius: '3px',
        fontSize: '11px', fontWeight: 600, background: `${colors[mkt] || '#666'}20`,
        color: colors[mkt] || '#666',
      }}>
        {mkt}
      </span>
    )
  }

  const selectStyle: React.CSSProperties = {
    padding: '6px 12px', border: '1px solid var(--border-primary)',
    borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
  }

  const masterKeys = ['buffett', 'munger', 'li_lu', 'duan_yongping'] as const

  // DCF chart option
  const getDCFChartOption = () => {
    if (!dcfResult) return {}
    const years = dcfResult.fcf_projections.map((_, i) => `第${i + 1}年`)
    return {
      tooltip: { trigger: 'axis' as const },
      xAxis: { type: 'category' as const, data: years, axisLabel: { color: '#8b949e' } },
      yAxis: { type: 'value' as const, name: 'FCF (亿元)', axisLabel: { color: '#8b949e' }, nameTextStyle: { color: '#8b949e' } },
      series: [{
        type: 'bar' as const,
        data: dcfResult.fcf_projections,
        itemStyle: { color: '#58a6ff', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top' as const, color: '#e6edf3', fontSize: 11, formatter: '{c}' },
      }],
      grid: { left: 60, right: 20, top: 30, bottom: 30 },
      backgroundColor: 'transparent',
    }
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>价值投资筛选器</h2>
            <span className="stock-code">巴菲特 / 芒格 / 李录 / 段永平 投资理念与筛选</span>
          </div>
        </div>
      </div>

      {/* Tab */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 20px',
        borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)',
      }}>
        {([['philosophy', '投资理念'], ['screener', '价投筛选'], ['dcf', 'DCF计算器']] as const).map(([tab, label]) => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}>
            {label}
          </button>
        ))}
      </div>

      {/* ===== Philosophy Tab ===== */}
      {activeTab === 'philosophy' && philosophy && (
        <div style={{ padding: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
            {masterKeys.map((key) => {
              const data = philosophy[key]
              if (!data) return null
              const color = MASTER_COLORS[key]
              return (
                <div key={key} className="arb-notes" style={{ margin: 0, borderLeft: `3px solid ${color}` }}>
                  <h3 style={{ color, marginBottom: '4px' }}>{data.name}</h3>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>{data.title}</div>
                  <div style={{ fontSize: '11px', color: color, marginBottom: '12px', opacity: 0.8 }}>{data.era}</div>
                  <div className="arb-notes-content">
                    <div className="arb-risk-section">
                      <h4>核心思想</h4>
                      <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{data.core_philosophy}</p>
                    </div>

                    {data.investment_framework.map((fw, fi) => (
                      <div key={fi} className="arb-risk-section" style={{ marginTop: '12px' }}>
                        <h4 style={{ color }}>{fw.dimension}</h4>
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>{fw.description}</p>
                        <ul>
                          {fw.criteria.map((c, ci) => (
                            <li key={ci} style={{ fontSize: '12px' }}>{c}</li>
                          ))}
                        </ul>
                        <div style={{
                          marginTop: '8px', padding: '6px 10px', background: `${color}10`,
                          borderRadius: '4px', fontSize: '12px', fontStyle: 'italic', color: 'var(--text-secondary)',
                          borderLeft: `2px solid ${color}`,
                        }}>
                          {fw.key_insight}
                        </div>
                      </div>
                    ))}

                    <div style={{ marginTop: '12px', padding: '8px', background: `${color}15`, borderRadius: '6px' }}>
                      {data.classic_quotes.map((q, qi) => (
                        <div key={qi} style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)', marginBottom: qi < data.classic_quotes.length - 1 ? '6px' : 0 }}>
                          "{q}"
                        </div>
                      ))}
                    </div>

                    <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                      代表案例: {data.key_cases}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Scoring system */}
          <div className="arb-notes" style={{ margin: 0, borderLeft: '3px solid #58a6ff' }}>
            <h3 style={{ color: '#58a6ff' }}>{philosophy.scoring_system.name}</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>{philosophy.scoring_system.description}</p>
            <div className="arb-notes-content">
              <div className="arb-notes-grid">
                {philosophy.scoring_system.masters.map((m, i) => (
                  <div key={i} className="arb-note-item" style={{ borderLeft: `2px solid ${MASTER_COLORS[masterKeys[i]]}` }}>
                    <span className="arb-note-label" style={{ color: MASTER_COLORS[masterKeys[i]] }}>{m.name}</span>
                    <span className="arb-note-value" style={{ fontSize: '12px' }}>{m.focus}</span>
                    <span className="arb-note-desc" style={{ fontSize: '11px' }}>{m.weight}</span>
                  </div>
                ))}
              </div>
              <div className="arb-notes-grid" style={{ marginTop: '12px' }}>
                {Object.entries(philosophy.scoring_system.match_levels).map(([key, desc]) => (
                  <div key={key} className="arb-note-item">
                    <span className="arb-note-label" style={{ color: getMatchLevelColor(key) }}>
                      {getMatchLevelText(key)}
                    </span>
                    <span className="arb-note-value">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Risks */}
          <div className="arb-notes" style={{ margin: '20px 0 0' }}>
            <h3 style={{ color: '#f85149' }}>风险提示</h3>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <ul>
                  {philosophy.risks.map((risk, i) => (
                    <li key={i} style={{ fontSize: '13px' }}>{risk}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===== Screener Tab ===== */}
      {activeTab === 'screener' && (
        <div style={{ padding: '16px 20px' }}>
          {/* Filters */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px',
            padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
            border: '1px solid var(--border-primary)',
          }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>市场</label>
              <select value={market} onChange={e => setMarket(e.target.value as any)} style={selectStyle}>
                <option value="all">全部市场</option>
                <option value="a">A股</option>
                <option value="hk">港股</option>
                <option value="us">美股</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>大师标准</label>
              <select value={master} onChange={e => setMaster(e.target.value as any)} style={selectStyle}>
                <option value="combined">综合</option>
                <option value="buffett">巴菲特</option>
                <option value="munger">芒格</option>
                <option value="li_lu">李录</option>
                <option value="duan_yongping">段永平</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>最低评分</label>
              <select value={minScore} onChange={e => setMinScore(Number(e.target.value))} style={selectStyle}>
                <option value={40}>40分</option>
                <option value={50}>50分</option>
                <option value={60}>60分</option>
                <option value={70}>70分</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>最大PE</label>
              <select value={maxPE} onChange={e => setMaxPE(Number(e.target.value))} style={selectStyle}>
                <option value={15}>15</option>
                <option value={20}>20</option>
                <option value={25}>25</option>
                <option value={30}>30</option>
                <option value={50}>50</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>最大PB</label>
              <select value={maxPB} onChange={e => setMaxPB(Number(e.target.value))} style={selectStyle}>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={8}>8</option>
                <option value={10}>10</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>显示数量</label>
              <select value={topN} onChange={e => setTopN(Number(e.target.value))} style={selectStyle}>
                <option value={30}>前30只</option>
                <option value={50}>前50只</option>
                <option value={100}>前100只</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={loadStocks} style={{
                padding: '6px 16px', background: 'var(--accent-blue)', color: '#fff',
                border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
              }}>
                筛选
              </button>
            </div>
          </div>

          {/* Info bar */}
          <div className="data-freshness" style={{ marginBottom: '16px' }}>
            <span className="freshness-tag">市场: {market === 'all' ? '全部' : market === 'a' ? 'A股' : market === 'hk' ? '港股' : '美股'}</span>
            <span className="freshness-tag">标准: {master === 'combined' ? '综合' : MASTER_LABELS[master]}</span>
            <span className="freshness-tag">更新: {updateTime}</span>
            <span className="freshness-tag">结果: {total} 只</span>
          </div>

          {/* Results table */}
          {loading ? (
            <div className="loading"><div className="spinner"></div>加载中...</div>
          ) : (
            <div className="table-container">
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>市场</th>
                    <th>报告期</th>
                    <th>现价</th>
                    <th>涨跌</th>
                    <th>PE</th>
                    <th>PB</th>
                    <th>ROE%</th>
                    <th>毛利率%</th>
                    <th>负债率%</th>
                    <th style={{ color: MASTER_COLORS.buffett }}>巴菲特</th>
                    <th style={{ color: MASTER_COLORS.munger }}>芒格</th>
                    <th style={{ color: MASTER_COLORS.li_lu }}>李录</th>
                    <th style={{ color: MASTER_COLORS.duan_yongping }}>段永平</th>
                    <th>综合</th>
                    <th>匹配</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((s, i) => {
                    const isExpanded = expandedStock === `${s.market}-${s.code}`
                    return (
                      <>
                        <tr
                          key={`${s.market}-${s.code}`}
                          onClick={() => setExpandedStock(isExpanded ? null : `${s.market}-${s.code}`)}
                          style={{ cursor: 'pointer' }}
                        >
                          <td>{i + 1}</td>
                          <td style={{ fontWeight: 600 }}>{s.code}</td>
                          <td>{s.name}</td>
                          <td>{getMarketTag(s.market)}</td>
                          <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{s.report_period || '--'}</td>
                          <td>{s.price.toFixed(2)}</td>
                          <td style={{ color: s.change_pct >= 0 ? '#f85149' : '#3fb950' }}>
                            {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                          </td>
                          <td style={{
                            color: (s.pe ?? 999) <= 15 ? '#52c41a' : (s.pe ?? 999) <= 25 ? '#1890ff' : '#faad14',
                            fontWeight: 600,
                          }}>{s.pe?.toFixed(1) ?? '--'}</td>
                          <td style={{
                            color: (s.pb ?? 999) <= 2 ? '#52c41a' : (s.pb ?? 999) <= 4 ? '#1890ff' : '#faad14',
                            fontWeight: 600,
                          }}>{s.pb?.toFixed(2) ?? '--'}</td>
                          <td style={{
                            color: (s.roe ?? 0) >= 15 ? '#52c41a' : (s.roe ?? 0) >= 10 ? '#1890ff' : '#faad14',
                          }}>{s.roe?.toFixed(1) ?? '--'}</td>
                          <td>{s.gross_margin?.toFixed(1) ?? '--'}</td>
                          <td style={{
                            color: (s.debt_ratio ?? 100) < 50 ? '#52c41a' : (s.debt_ratio ?? 100) < 65 ? '#faad14' : '#ff4d4f',
                          }}>{s.debt_ratio?.toFixed(1) ?? '--'}</td>
                          <td style={{ color: getScoreColor(s.buffett_score), fontWeight: 600 }}>{s.buffett_score}</td>
                          <td style={{ color: getScoreColor(s.munger_score), fontWeight: 600 }}>{s.munger_score}</td>
                          <td style={{ color: getScoreColor(s.li_lu_score), fontWeight: 600 }}>{s.li_lu_score}</td>
                          <td style={{ color: getScoreColor(s.duan_score), fontWeight: 600 }}>{s.duan_score}</td>
                          <td>
                            <span style={{ color: getScoreColor(s.score), fontWeight: 700, fontSize: '15px' }}>{s.score}</span>
                          </td>
                          <td>
                            <span style={{
                              display: 'inline-block', padding: '2px 8px', borderRadius: '4px',
                              fontSize: '12px', fontWeight: 600,
                              background: `${getMatchLevelColor(s.match_level)}20`,
                              color: getMatchLevelColor(s.match_level),
                            }}>
                              {getMatchLevelText(s.match_level)}
                            </span>
                          </td>
                        </tr>
                        {isExpanded && s.score_details && (
                          <tr key={`${s.market}-${s.code}-detail`} style={{ background: 'var(--bg-secondary)' }}>
                            <td colSpan={18} style={{ padding: '12px 20px' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                                {masterKeys.map((mk) => {
                                  const detail = s.score_details[mk]
                                  if (!detail) return null
                                  return (
                                    <div key={mk} style={{
                                      padding: '10px 14px', borderRadius: '6px',
                                      background: `${MASTER_COLORS[mk]}08`,
                                      border: `1px solid ${MASTER_COLORS[mk]}30`,
                                    }}>
                                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                        <span style={{ fontWeight: 600, color: MASTER_COLORS[mk], fontSize: '13px' }}>
                                          {MASTER_LABELS[mk]}
                                        </span>
                                        <span style={{ fontWeight: 700, fontSize: '16px', color: getScoreColor(detail.score) }}>
                                          {detail.score}
                                        </span>
                                      </div>
                                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                                        {detail.detail}
                                      </div>
                                    </div>
                                  )
                                })}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })}
                  {stocks.length === 0 && (
                    <tr>
                      <td colSpan={18} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        点击"筛选"按钮开始价值投资选股
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ===== DCF Calculator Tab ===== */}
      {activeTab === 'dcf' && (
        <div style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', gap: '20px' }}>
            {/* Input panel */}
            <div style={{
              minWidth: '320px', padding: '20px', background: 'var(--bg-secondary)',
              borderRadius: '8px', border: '1px solid var(--border-primary)',
            }}>
              <h3 style={{ marginBottom: '16px', color: 'var(--text-primary)' }}>DCF 参数输入</h3>
              {[
                { label: '当前自由现金流 (亿元)', value: dcfFcf, set: setDcfFcf, placeholder: '如: 100' },
                { label: '增长率 (%)', value: dcfGrowth, set: setDcfGrowth, placeholder: '如: 10' },
                { label: '总股本 (亿股)', value: dcfShares, set: setDcfShares, placeholder: '如: 10' },
                { label: '折现率 (%)', value: dcfDiscount, set: setDcfDiscount, placeholder: '默认 10' },
                { label: '永续增长率 (%)', value: dcfTerminal, set: setDcfTerminal, placeholder: '默认 3' },
                { label: '安全边际 (%)', value: dcfSafety, set: setDcfSafety, placeholder: '默认 30' },
              ].map(({ label, value, set, placeholder }) => (
                <div key={label} style={{ marginBottom: '12px' }}>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    {label}
                  </label>
                  <input
                    type="number"
                    value={value}
                    onChange={e => set(e.target.value)}
                    placeholder={placeholder}
                    style={{
                      width: '100%', padding: '8px 12px',
                      border: '1px solid var(--border-primary)', borderRadius: '4px',
                      background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: '14px',
                    }}
                  />
                </div>
              ))}
              <button
                onClick={runDCF}
                disabled={dcfLoading}
                style={{
                  width: '100%', padding: '10px', background: 'var(--accent-blue)', color: '#fff',
                  border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
                  fontSize: '14px', marginTop: '4px',
                }}
              >
                {dcfLoading ? '计算中...' : '计算内在价值'}
              </button>
            </div>

            {/* Results panel */}
            <div style={{ flex: 1 }}>
              {dcfResult ? (
                <>
                  {/* Summary cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '20px' }}>
                    {[
                      { label: '每股内在价值', value: `${dcfResult.intrinsic_value} 元`, color: '#58a6ff' },
                      { label: '安全买点', value: `${dcfResult.buy_price} 元`, color: '#3fb950' },
                      { label: '企业价值', value: `${dcfResult.enterprise_value} 亿`, color: '#d29922' },
                      { label: '终值', value: `${dcfResult.terminal_value} 亿`, color: '#bc8cff' },
                    ].map(({ label, value, color }) => (
                      <div key={label} style={{
                        padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                        border: `1px solid ${color}40`, borderTop: `3px solid ${color}`,
                      }}>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>{label}</div>
                        <div style={{ fontSize: '20px', fontWeight: 700, color }}>{value}</div>
                      </div>
                    ))}
                  </div>

                  {/* FCF Chart */}
                  <div style={{
                    padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                    border: '1px solid var(--border-primary)', marginBottom: '20px',
                  }}>
                    <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>未来10年FCF预测</h4>
                    <ReactECharts option={getDCFChartOption()} style={{ height: '280px' }} />
                  </div>

                  {/* FCF Projection Table */}
                  <div className="table-container" style={{ marginBottom: '20px' }}>
                    <table className="arb-table">
                      <thead>
                        <tr>
                          <th>年份</th>
                          <th>预测FCF (亿元)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dcfResult.fcf_projections.map((fcf, i) => (
                          <tr key={i}>
                            <td>第 {i + 1} 年</td>
                            <td style={{ fontWeight: 600, color: '#58a6ff' }}>{fcf.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Sensitivity Analysis */}
                  {dcfResult.sensitivity && (
                    <div style={{
                      padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                      border: '1px solid var(--border-primary)',
                    }}>
                      <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>敏感性分析（每股内在价值）</h4>
                      <div className="table-container">
                        <table className="arb-table">
                          <thead>
                            <tr>
                              <th>增长率 \ 折现率</th>
                              {dcfResult.sensitivity.discount_rates.map(dr => (
                                <th key={dr}>{dr}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {dcfResult.sensitivity.growth_rates.map((gr, gi) => (
                              <tr key={gr}>
                                <td style={{ fontWeight: 600 }}>{gr}</td>
                                {dcfResult.sensitivity.matrix[gi].map((val, di) => (
                                  <td key={di} style={{
                                    color: val >= parseFloat(dcfFcf) ? '#3fb950' : '#f85149',
                                    fontWeight: 600,
                                  }}>
                                    {val.toFixed(2)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  height: '400px', color: 'var(--text-muted)', fontSize: '14px',
                }}>
                  输入参数后点击"计算内在价值"查看DCF估值结果
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
