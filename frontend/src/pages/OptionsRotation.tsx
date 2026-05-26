import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface OptionCandidate {
  option_type: string
  strike: number
  dte: number
  premium: number
  annual_yield: number
  delta: number
  gamma: number
  theta: number
  vega: number
  otm_pct: number
  breakeven: number
  iv: number
  hv: number
  score: number
  detail: string
  pop: number
  max_profit: number
  max_loss: number | string
}

interface OptionsAnalysis {
  spot_price: number
  stock_name: string
  hv: number
  iv: number
  option_type: string
  candidates: OptionCandidate[]
  best_put: OptionCandidate | null
  best_call: OptionCandidate | null
  best_yield: OptionCandidate | null
  safest: OptionCandidate | null
  total: number
  update_time: string
  error?: string
}

interface Philosophy {
  title: string
  subtitle: string
  concepts: { name: string; desc: string; suitable: string }[]
  scoring: {
    title: string
    dimensions: { name: string; weight: number; desc: string }[]
  }
  risks: string[]
  rules: string[]
}

interface GreeksResult {
  spot: number
  strike: number
  days: number
  sigma: number
  option_type: string
  greeks: {
    price: number
    delta: number
    gamma: number
    theta: number
    vega: number
  }
}

interface SearchResult {
  code: string
  name: string
}

export default function OptionsRotation() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'analysis' | 'simulation' | 'rolling'>('philosophy')
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)
  const [analysis, setAnalysis] = useState<OptionsAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [optionType, setOptionType] = useState<'put' | 'call'>('put')
  const [ivOverride, setIvOverride] = useState<string>('')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  // Stock search state
  const [stockCode, setStockCode] = useState('00700')
  const [stockSearch, setStockSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const searchTimerRef = useRef<number | null>(null)

  // Simulation state
  const [simSpot, setSimSpot] = useState('500')
  const [simStrike, setSimStrike] = useState('470')
  const [simPremium, setSimPremium] = useState('10')
  const [simDte, setSimDte] = useState('30')
  const [simType, setSimType] = useState<'put' | 'call'>('put')
  const [simSigma, setSimSigma] = useState('30')
  const [simResult, setSimResult] = useState<GreeksResult | null>(null)
  const [simLoading, setSimLoading] = useState(false)
  const [simError, setSimError] = useState('')

  // Rolling state
  const [rollSpot, setRollSpot] = useState('500')
  const [rollStrike, setRollStrike] = useState('470')
  const [rollPremium, setRollPremium] = useState('10')
  const [rollDteLeft, setRollDteLeft] = useState('15')
  const [rollEntryDte, setRollEntryDte] = useState('30')
  const [rollType, setRollType] = useState<'put' | 'call'>('put')
  const [rollResult, setRollResult] = useState<any>(null)
  const [rollLoading, setRollLoading] = useState(false)
  const [rollError, setRollError] = useState('')

  // Stock search
  const handleSearch = useCallback(async (keyword: string) => {
    if (!keyword.trim()) {
      setSearchResults([])
      return
    }
    try {
      const res = await axios.get(`${API_BASE}/stocks/search`, { params: { keyword } })
      setSearchResults(res.data.results || [])
    } catch { setSearchResults([]) }
  }, [])

  useEffect(() => {
    if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current)
    if (stockSearch.trim()) {
      searchTimerRef.current = window.setTimeout(() => handleSearch(stockSearch), 300)
    } else {
      setSearchResults([])
    }
    return () => { if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current) }
  }, [stockSearch, handleSearch])

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearch(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const selectStock = (code: string) => {
    setStockCode(code)
    setStockSearch('')
    setShowSearch(false)
    setSearchResults([])
    setAnalysis(null)
  }

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/options/philosophy`)
      setPhilosophy(res.data)
    } catch (e) { console.error(e) }
  }, [])

  const loadAnalysis = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = { stock_code: stockCode, option_type: optionType }
      if (ivOverride) params.iv_override = parseFloat(ivOverride) / 100
      const res = await axios.get(`${API_BASE}/options/analysis`, { params })
      setAnalysis(res.data)
    } catch (e) { console.error(e) }
    setLoading(false)
  }, [stockCode, optionType, ivOverride])

  const runSimulation = useCallback(async () => {
    setSimLoading(true)
    setSimError('')
    setSimResult(null)
    try {
      const res = await axios.get(`${API_BASE}/options/greeks`, {
        params: {
          spot: parseFloat(simSpot), strike: parseFloat(simStrike),
          days: parseInt(simDte), sigma: parseFloat(simSigma) / 100, option_type: simType,
        },
      })
      setSimResult(res.data)
    } catch (e) {
      setSimError('计算失败，请检查参数')
      console.error(e)
    }
    setSimLoading(false)
  }, [simSpot, simStrike, simDte, simType, simSigma])

  const runRolling = useCallback(async () => {
    setRollLoading(true)
    setRollError('')
    setRollResult(null)
    try {
      const res = await axios.get(`${API_BASE}/options/rolling`, {
        params: {
          spot: parseFloat(rollSpot), strike: parseFloat(rollStrike),
          premium: parseFloat(rollPremium), dte_left: parseInt(rollDteLeft),
          entry_dte: parseInt(rollEntryDte), option_type: rollType,
        },
      })
      setRollResult(res.data)
    } catch (e) {
      setRollError('分析失败，请检查参数')
      console.error(e)
    }
    setRollLoading(false)
  }, [rollSpot, rollStrike, rollPremium, rollDteLeft, rollEntryDte, rollType])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])
  useEffect(() => { if (activeTab === 'analysis') loadAnalysis() }, [activeTab, loadAnalysis])

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 65) return '#1890ff'
    if (score >= 50) return '#faad14'
    return '#ff4d4f'
  }

  const getActionColor = (action: string) => {
    if (action === 'hold') return '#52c41a'
    if (action === 'roll') return '#1890ff'
    return '#ff4d4f'
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <h2>期权轮动 - {analysis?.stock_name || stockCode}</h2>
        <p style={{ color: '#999', margin: '4px 0 0' }}>卖期权评分系统 · BSM定价 · 轮动推荐</p>
      </div>

      {/* Stock Search */}
      <div ref={searchRef} style={{ position: 'relative', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>港股代码:</span>
          <input
            value={showSearch ? stockSearch : stockCode}
            onFocus={() => { setShowSearch(true); setStockSearch('') }}
            onChange={e => { setStockSearch(e.target.value); setShowSearch(true) }}
            placeholder="输入代码或名称搜索"
            style={{ width: 160, padding: '4px 8px', background: '#1a1a2e', color: '#fff', border: '1px solid #444', borderRadius: 4 }}
          />
          {showSearch && searchResults.length > 0 && (
            <div style={{ position: 'absolute', top: '100%', left: 60, zIndex: 100, background: '#1a1a2e', border: '1px solid #444', borderRadius: 4, maxHeight: 200, overflow: 'auto', width: 240 }}>
              {searchResults.map(r => (
                <div key={r.code} onClick={() => selectStock(r.code)}
                  style={{ padding: '6px 10px', cursor: 'pointer', color: '#ccc', fontSize: 13, borderBottom: '1px solid #222' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#2a2a4e')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <span style={{ color: '#d4a76a', fontWeight: 600 }}>{r.code}</span> {r.name}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="tab-bar" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {(['philosophy', 'analysis', 'simulation', 'rolling'] as const).map(tab => (
          <button key={tab} className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}>
            {tab === 'philosophy' ? '卖期权理念' : tab === 'analysis' ? '期权分析' : tab === 'simulation' ? '模拟卖出' : '轮动建议'}
          </button>
        ))}
      </div>

      {/* Philosophy Tab */}
      {activeTab === 'philosophy' && philosophy && (
        <div>
          <h3 style={{ color: '#d4a76a' }}>{philosophy.title}</h3>
          <p style={{ color: '#ccc', marginBottom: 16 }}>{philosophy.subtitle}</p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
            {philosophy.concepts.map((c, i) => (
              <div key={i} style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333' }}>
                <h4 style={{ color: '#d4a76a', marginBottom: 8 }}>{c.name}</h4>
                <p style={{ color: '#ccc', fontSize: 14, marginBottom: 8 }}>{c.desc}</p>
                <p style={{ color: '#999', fontSize: 12 }}>适用: {c.suitable}</p>
              </div>
            ))}
          </div>

          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 20 }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>{philosophy.scoring.title}</h4>
            {philosophy.scoring.dimensions.map((d, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #222' }}>
                <span style={{ color: '#ccc' }}>{d.name} <span style={{ color: '#d4a76a' }}>({d.weight}分)</span></span>
                <span style={{ color: '#999', fontSize: 13 }}>{d.desc}</span>
              </div>
            ))}
          </div>

          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 20 }}>
            <h4 style={{ color: '#ff4d4f', marginBottom: 12 }}>风险提示</h4>
            {philosophy.risks.map((r, i) => (
              <p key={i} style={{ color: '#ccc', fontSize: 13, margin: '4px 0' }}>• {r}</p>
            ))}
          </div>

          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333' }}>
            <h4 style={{ color: '#52c41a', marginBottom: 12 }}>交易规则</h4>
            {philosophy.rules.map((r, i) => (
              <p key={i} style={{ color: '#ccc', fontSize: 13, margin: '4px 0' }}>• {r}</p>
            ))}
          </div>
        </div>
      )}

      {/* Analysis Tab */}
      {activeTab === 'analysis' && (
        <div>
          {/* Filter Bar */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ color: '#ccc' }}>类型:
              <select value={optionType} onChange={e => setOptionType(e.target.value as any)}
                style={{ marginLeft: 6, padding: '4px 8px', background: '#1a1a2e', color: '#fff', border: '1px solid #444', borderRadius: 4 }}>
                <option value="put">Put (看跌)</option>
                <option value="call">Call (看涨)</option>
              </select>
            </label>
            <label style={{ color: '#ccc' }}>自定义IV%:
              <input type="number" value={ivOverride} onChange={e => setIvOverride(e.target.value)}
                placeholder="自动" step="1" min="5" max="100"
                style={{ marginLeft: 6, width: 70, padding: '4px 8px', background: '#1a1a2e', color: '#fff', border: '1px solid #444', borderRadius: 4 }} />
            </label>
            <button onClick={loadAnalysis} disabled={loading}
              style={{ padding: '6px 16px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {loading ? '加载中...' : '刷新'}
            </button>
          </div>

          {analysis && !analysis.error && (
            <>
              {/* Summary Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 16 }}>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>{analysis.stock_name} 现价</div>
                  <div style={{ color: '#d4a76a', fontSize: 22, fontWeight: 700 }}>HK${analysis.spot_price}</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>历史波动率 (HV)</div>
                  <div style={{ color: '#1890ff', fontSize: 22, fontWeight: 700 }}>{analysis.hv}%</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>隐含波动率 (IV)</div>
                  <div style={{ color: '#faad14', fontSize: 22, fontWeight: 700 }}>{analysis.iv}%</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>候选合约数</div>
                  <div style={{ color: '#52c41a', fontSize: 22, fontWeight: 700 }}>{analysis.total}</div>
                </div>
              </div>

              {/* Best Picks */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 16 }}>
                {analysis.best_put && (
                  <div style={{ background: '#1a2e1a', padding: 14, borderRadius: 8, border: '1px solid #52c41a' }}>
                    <div style={{ color: '#52c41a', fontSize: 13, fontWeight: 600 }}>最佳Put</div>
                    <div style={{ color: '#fff', fontSize: 15 }}>K={analysis.best_put.strike} | {analysis.best_put.dte}天 | 年化{analysis.best_put.annual_yield}%</div>
                  </div>
                )}
                {analysis.best_call && (
                  <div style={{ background: '#1a2e1a', padding: 14, borderRadius: 8, border: '1px solid #1890ff' }}>
                    <div style={{ color: '#1890ff', fontSize: 13, fontWeight: 600 }}>最佳Call</div>
                    <div style={{ color: '#fff', fontSize: 15 }}>K={analysis.best_call.strike} | {analysis.best_call.dte}天 | 年化{analysis.best_call.annual_yield}%</div>
                  </div>
                )}
                {analysis.best_yield && (
                  <div style={{ background: '#2e2e1a', padding: 14, borderRadius: 8, border: '1px solid #faad14' }}>
                    <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>最高收益</div>
                    <div style={{ color: '#fff', fontSize: 15 }}>K={analysis.best_yield.strike} | 年化{analysis.best_yield.annual_yield}% | 胜率{analysis.best_yield.pop}%</div>
                  </div>
                )}
              </div>

              {/* Candidates Table */}
              <table className="arb-table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>类型</th><th>行权价</th><th>到期天数</th><th>权利金</th>
                    <th>年化收益%</th><th>Delta</th><th>OTM%</th><th>盈利概率</th>
                    <th>评分</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.candidates.slice(0, 30).map((c) => {
                    const key = `${c.option_type}_${c.strike}_${c.dte}`
                    return (
                      <tr key={key} onClick={() => setExpandedRow(expandedRow === key ? null : key)}
                        style={{ cursor: 'pointer', background: expandedRow === key ? '#1a1a2e' : 'transparent' }}>
                        <td><span style={{ color: c.option_type === 'put' ? '#52c41a' : '#1890ff', fontWeight: 600 }}>
                          {c.option_type.toUpperCase()}</span></td>
                        <td style={{ fontWeight: 600 }}>{c.strike}</td>
                        <td>{c.dte}天</td>
                        <td>{c.premium.toFixed(2)}</td>
                        <td style={{ color: c.annual_yield >= 10 ? '#52c41a' : '#faad14' }}>{c.annual_yield}%</td>
                        <td>{c.delta.toFixed(3)}</td>
                        <td>{c.otm_pct}%</td>
                        <td>{c.pop}%</td>
                        <td><span style={{ color: getScoreColor(c.score), fontWeight: 700, fontSize: 16 }}>{c.score}</span></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>

              {/* Expanded detail below table */}
              {expandedRow && (() => {
                const c = analysis.candidates.find(x => `${x.option_type}_${x.strike}_${x.dte}` === expandedRow)
                if (!c) return null
                return (
                  <div style={{ padding: '12px 20px', background: '#111', marginTop: -1, borderRadius: '0 0 8px 8px', border: '1px solid #333' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
                      <div>
                        <p style={{ color: '#d4a76a', fontWeight: 600 }}>BSM Greeks</p>
                        <p style={{ color: '#ccc' }}>Gamma: {c.gamma.toFixed(6)}</p>
                        <p style={{ color: '#ccc' }}>Theta: {c.theta.toFixed(4)}/天</p>
                        <p style={{ color: '#ccc' }}>Vega: {c.vega.toFixed(4)}</p>
                        <p style={{ color: '#ccc' }}>盈亏平衡: {c.breakeven}</p>
                      </div>
                      <div>
                        <p style={{ color: '#d4a76a', fontWeight: 600 }}>评分详情</p>
                        <p style={{ color: '#ccc', whiteSpace: 'pre-wrap' }}>{c.detail}</p>
                        <p style={{ color: '#ccc' }}>最大盈利: ${c.max_profit}/手</p>
                        <p style={{ color: '#ccc' }}>最大亏损: {typeof c.max_loss === 'number' ? `$${c.max_loss}` : c.max_loss}</p>
                      </div>
                    </div>
                  </div>
                )
              })()}
            </>
          )}
          {analysis?.error && <p style={{ color: '#ff4d4f' }}>{analysis.error}</p>}
        </div>
      )}

      {/* Simulation Tab */}
      {activeTab === 'simulation' && (
        <div>
          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>BSM期权计算器</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
              <label style={{ color: '#ccc', fontSize: 13 }}>标的价格
                <input type="number" value={simSpot} onChange={e => setSimSpot(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>行权价
                <input type="number" value={simStrike} onChange={e => setSimStrike(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>到期天数
                <input type="number" value={simDte} onChange={e => setSimDte(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>波动率%
                <input type="number" value={simSigma} onChange={e => setSimSigma(e.target.value)}
                  step="1" min="1" max="200"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>类型
                <select value={simType} onChange={e => setSimType(e.target.value as any)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }}>
                  <option value="put">Put</option><option value="call">Call</option>
                </select>
              </label>
            </div>
            <button onClick={runSimulation} disabled={simLoading}
              style={{ marginTop: 12, padding: '8px 24px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {simLoading ? '计算中...' : '计算'}
            </button>
          </div>

          {simError && <p style={{ color: '#ff4d4f', marginBottom: 12 }}>{simError}</p>}

          {simResult && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>期权价格</div>
                <div style={{ color: '#d4a76a', fontSize: 20, fontWeight: 700 }}>{simResult.greeks.price.toFixed(4)}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Delta</div>
                <div style={{ color: '#1890ff', fontSize: 20, fontWeight: 700 }}>{simResult.greeks.delta.toFixed(4)}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Gamma</div>
                <div style={{ color: '#faad14', fontSize: 20, fontWeight: 700 }}>{simResult.greeks.gamma.toFixed(6)}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Theta/天</div>
                <div style={{ color: '#ff4d4f', fontSize: 20, fontWeight: 700 }}>{simResult.greeks.theta.toFixed(4)}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Vega (1%变动)</div>
                <div style={{ color: '#722ed1', fontSize: 20, fontWeight: 700 }}>{simResult.greeks.vega.toFixed(4)}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>盈利概率</div>
                <div style={{ color: '#52c41a', fontSize: 20, fontWeight: 700 }}>{((1 - Math.abs(simResult.greeks.delta)) * 100).toFixed(0)}%</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rolling Tab */}
      {activeTab === 'rolling' && (
        <div>
          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>轮动建议</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
              <label style={{ color: '#ccc', fontSize: 13 }}>标的价格
                <input type="number" value={rollSpot} onChange={e => setRollSpot(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>行权价
                <input type="number" value={rollStrike} onChange={e => setRollStrike(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>开仓权利金
                <input type="number" value={rollPremium} onChange={e => setRollPremium(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>剩余天数
                <input type="number" value={rollDteLeft} onChange={e => setRollDteLeft(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>开仓天数
                <input type="number" value={rollEntryDte} onChange={e => setRollEntryDte(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>类型
                <select value={rollType} onChange={e => setRollType(e.target.value as any)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }}>
                  <option value="put">Put</option><option value="call">Call</option>
                </select>
              </label>
            </div>
            <button onClick={runRolling} disabled={rollLoading}
              style={{ marginTop: 12, padding: '8px 24px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {rollLoading ? '分析中...' : '分析'}
            </button>
          </div>

          {rollError && <p style={{ color: '#ff4d4f', marginBottom: 12 }}>{rollError}</p>}

          {rollResult && (
            <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <span style={{ color: '#999', fontSize: 14 }}>建议操作:</span>
                <span style={{ color: getActionColor(rollResult.action), fontSize: 24, fontWeight: 700, textTransform: 'uppercase' }}>
                  {rollResult.action === 'hold' ? '持有' : rollResult.action === 'roll' ? '展期' : '平仓'}
                </span>
              </div>
              <p style={{ color: '#ccc', fontSize: 14, marginBottom: 12 }}>{rollResult.reason}</p>
              <div style={{ display: 'flex', gap: 20 }}>
                <div>
                  <span style={{ color: '#999', fontSize: 12 }}>当前OTM: </span>
                  <span style={{ color: '#d4a76a' }}>{rollResult.current_otm}%</span>
                </div>
                <div>
                  <span style={{ color: '#999', fontSize: 12 }}>当前Delta: </span>
                  <span style={{ color: '#1890ff' }}>{rollResult.current_delta?.toFixed(3)}</span>
                </div>
              </div>

              {rollResult.new_contract && (
                <div style={{ marginTop: 16, padding: 12, background: '#0d2e0d', borderRadius: 8, border: '1px solid #52c41a' }}>
                  <p style={{ color: '#52c41a', fontWeight: 600, marginBottom: 8 }}>推荐新合约</p>
                  <p style={{ color: '#ccc' }}>行权价: {rollResult.new_contract.strike} | 到期: {rollResult.new_contract.dte}天 | 年化: {rollResult.new_contract.annual_yield}%</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
