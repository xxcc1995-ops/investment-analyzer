import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface GridLevel {
  price: number
  index: number
  distance_pct: number
  type: 'buy' | 'sell' | 'current'
}

interface Trade {
  date: string
  action: string
  price: number
  level: number
  shares: number
  pnl?: number
  cost?: number
  revenue?: number
}

interface Simulation {
  trades: Trade[]
  total_trades: number
  num_buys: number
  num_sells: number
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  total_return_pct: number
  win_rate: number
  max_drawdown: number
  equity_curve: { date: string; equity: number }[]
  open_positions: number
  position_details: { level: number; shares: number; entry: number; unrealized: number }[]
}

interface GridAnalysis {
  stock_name: string
  current_price: number
  high_52w: number
  low_52w: number
  atr: number
  atr_pct: number
  grid_type: string
  grid_width: number
  grid_width_pct: number
  grid_levels: GridLevel[]
  shares_per_grid: number
  capital_per_grid: number
  total_levels: number
  simulation: Simulation
  status: { current_price: number; nearest_level: GridLevel; next_buy: GridLevel; next_sell: GridLevel }
  breakeven: { min_grid_width: number; min_grid_pct: number; profit_per_trade: number; is_profitable: boolean; trading_cost_per_share: number }
  cagr: number
  hist_days: number
  update_time: string
  error?: string
}

interface Philosophy {
  title: string
  subtitle: string
  concepts: { name: string; desc: string; formula: string }[]
  scoring: { title: string; dimensions: { name: string; desc: string }[] }
  risks: string[]
  rules: string[]
}

interface SearchResult {
  code: string
  name: string
}

export default function GridTrading() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'analysis' | 'simulation' | 'status'>('philosophy')
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)
  const [analysis, setAnalysis] = useState<GridAnalysis | null>(null)
  const [loading, setLoading] = useState(false)

  // Stock search state
  const [stockCode, setStockCode] = useState('00700')
  const [stockSearch, setStockSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const searchTimerRef = useRef<number | null>(null)

  // Parameters
  const [gridType, setGridType] = useState<'equal_distance' | 'equal_ratio'>('equal_distance')
  const [gridsUp, setGridsUp] = useState('10')
  const [gridsDown, setGridsDown] = useState('10')
  const [gridWidthPct, setGridWidthPct] = useState('')
  const [capital, setCapital] = useState('1000000')
  const [histDays, setHistDays] = useState('252')
  const [sizing, setSizing] = useState<'equal' | 'pyramid'>('equal')

  const [expandedTrade, setExpandedTrade] = useState<number | null>(null)

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
      const res = await axios.get(`${API_BASE}/grid/philosophy`)
      setPhilosophy(res.data)
    } catch (e) { console.error(e) }
  }, [])

  const loadAnalysis = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = {
        stock_code: stockCode,
        grid_type: gridType,
        num_grids_up: parseInt(gridsUp),
        num_grids_down: parseInt(gridsDown),
        capital: parseFloat(capital),
        hist_days: parseInt(histDays),
        sizing,
      }
      if (gridWidthPct) params.grid_width_pct = parseFloat(gridWidthPct)
      const res = await axios.get(`${API_BASE}/grid/analysis`, { params })
      setAnalysis(res.data)
    } catch (e) { console.error(e) }
    setLoading(false)
  }, [stockCode, gridType, gridsUp, gridsDown, gridWidthPct, capital, histDays, sizing])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])
  useEffect(() => { if (activeTab === 'analysis' || activeTab === 'simulation' || activeTab === 'status') loadAnalysis() }, [activeTab, loadAnalysis])

  const fmt = (n: number) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '-'

  return (
    <div className="cb-page">
      <div className="stock-header">
        <h2>网格交易 - {analysis?.stock_name || stockCode}</h2>
        <p style={{ color: '#999', margin: '4px 0 0' }}>自动生成网格 · 历史回测 · 仓位管理</p>
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
        {(['philosophy', 'analysis', 'simulation', 'status'] as const).map(tab => (
          <button key={tab} className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}>
            {tab === 'philosophy' ? '网格理念' : tab === 'analysis' ? '网格分析' : tab === 'simulation' ? '回测模拟' : '当前状态'}
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
                <code style={{ color: '#1890ff', fontSize: 12 }}>{c.formula}</code>
              </div>
            ))}
          </div>

          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 20 }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>{philosophy.scoring.title}</h4>
            {philosophy.scoring.dimensions.map((d, i) => (
              <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #222' }}>
                <span style={{ color: '#d4a76a', fontWeight: 600 }}>{d.name}: </span>
                <span style={{ color: '#ccc', fontSize: 13 }}>{d.desc}</span>
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
          {/* Parameter Panel */}
          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>网格参数</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
              <label style={{ color: '#ccc', fontSize: 13 }}>网格类型
                <select value={gridType} onChange={e => setGridType(e.target.value as any)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }}>
                  <option value="equal_distance">等距网格</option>
                  <option value="equal_ratio">等比网格</option>
                </select>
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>上行格数
                <input type="number" value={gridsUp} onChange={e => setGridsUp(e.target.value)} min="3" max="30"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>下行格数
                <input type="number" value={gridsDown} onChange={e => setGridsDown(e.target.value)} min="3" max="30"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>网格宽度% (空=自动)
                <input type="number" value={gridWidthPct} onChange={e => setGridWidthPct(e.target.value)}
                  placeholder="ATR自动" step="0.5" min="0.5"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>总资金 (HKD)
                <input type="number" value={capital} onChange={e => setCapital(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>回测天数
                <input type="number" value={histDays} onChange={e => setHistDays(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>仓位方法
                <select value={sizing} onChange={e => setSizing(e.target.value as any)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }}>
                  <option value="equal">等额分配</option>
                  <option value="pyramid">金字塔加仓</option>
                </select>
              </label>
            </div>
            <button onClick={loadAnalysis} disabled={loading}
              style={{ marginTop: 12, padding: '8px 24px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {loading ? '加载中...' : '分析'}
            </button>
          </div>

          {analysis && !analysis.error && (
            <>
              {/* Summary Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>{analysis.stock_name} 现价</div>
                  <div style={{ color: '#d4a76a', fontSize: 22, fontWeight: 700 }}>HK${fmt(analysis.current_price)}</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>ATR(14)</div>
                  <div style={{ color: '#1890ff', fontSize: 22, fontWeight: 700 }}>{fmt(analysis.atr)} ({analysis.atr_pct}%)</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>网格宽度</div>
                  <div style={{ color: '#faad14', fontSize: 22, fontWeight: 700 }}>{fmt(analysis.grid_width)} ({analysis.grid_width_pct}%)</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>回测年化</div>
                  <div style={{ color: analysis.cagr > 0 ? '#52c41a' : '#ff4d4f', fontSize: 22, fontWeight: 700 }}>{analysis.cagr}%</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>胜率</div>
                  <div style={{ color: '#52c41a', fontSize: 22, fontWeight: 700 }}>{analysis.simulation.win_rate}%</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>最大回撤</div>
                  <div style={{ color: '#ff4d4f', fontSize: 22, fontWeight: 700 }}>{analysis.simulation.max_drawdown}%</div>
                </div>
              </div>

              {/* 52-week range */}
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: '#999', fontSize: 13 }}>52周低: <span style={{ color: '#52c41a' }}>HK${fmt(analysis.low_52w)}</span></span>
                  <div style={{ flex: 1, margin: '0 16px', height: 8, background: '#333', borderRadius: 4, position: 'relative' }}>
                    <div style={{
                      position: 'absolute', left: `${((analysis.current_price - analysis.low_52w) / (analysis.high_52w - analysis.low_52w)) * 100}%`,
                      top: -4, width: 16, height: 16, background: '#d4a76a', borderRadius: '50%', transform: 'translateX(-50%)',
                    }} />
                  </div>
                  <span style={{ color: '#999', fontSize: 13 }}>52周高: <span style={{ color: '#ff4d4f' }}>HK${fmt(analysis.high_52w)}</span></span>
                </div>
              </div>

              {/* Grid Levels Table */}
              <h4 style={{ color: '#d4a76a', marginBottom: 8 }}>网格层级 ({analysis.total_levels}格)</h4>
              <table className="arb-table" style={{ width: '100%', marginBottom: 16 }}>
                <thead>
                  <tr>
                    <th>价格</th><th>距现价%</th><th>类型</th><th>每格股数</th><th>每格资金</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.grid_levels.map((lv, i) => (
                    <tr key={i} style={{
                      background: lv.type === 'current' ? '#2a2a1a' : 'transparent',
                      borderLeft: lv.type === 'current' ? '3px solid #d4a76a' : 'none',
                    }}>
                      <td style={{ fontWeight: lv.type === 'current' ? 700 : 400 }}>{fmt(lv.price)}</td>
                      <td style={{ color: lv.distance_pct < 0 ? '#52c41a' : lv.distance_pct > 0 ? '#ff4d4f' : '#d4a76a' }}>
                        {lv.distance_pct > 0 ? '+' : ''}{lv.distance_pct}%
                      </td>
                      <td><span style={{
                        color: lv.type === 'buy' ? '#52c41a' : lv.type === 'sell' ? '#ff4d4f' : '#d4a76a',
                        fontWeight: 600,
                      }}>{lv.type === 'buy' ? '买入' : lv.type === 'sell' ? '卖出' : '当前'}</span></td>
                      <td>{analysis.shares_per_grid}</td>
                      <td>HK${fmt(analysis.capital_per_grid)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Breakeven */}
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <h4 style={{ color: '#d4a76a', marginBottom: 8 }}>盈亏平衡分析</h4>
                <p style={{ color: '#ccc', fontSize: 13 }}>最小网格宽度: {fmt(analysis.breakeven.min_grid_width)} ({analysis.breakeven.min_grid_pct}%)</p>
                <p style={{ color: '#ccc', fontSize: 13 }}>每笔交易成本: {fmt(analysis.breakeven.trading_cost_per_share)}/股</p>
                <p style={{ color: '#ccc', fontSize: 13 }}>每格利润: HK${fmt(analysis.breakeven.profit_per_trade)}</p>
                <p style={{ color: analysis.breakeven.is_profitable ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
                  {analysis.breakeven.is_profitable ? '✓ 网格宽度足够覆盖交易成本' : '✗ 网格宽度过窄，利润被手续费侵蚀'}
                </p>
              </div>
            </>
          )}
          {analysis?.error && <p style={{ color: '#ff4d4f' }}>{analysis.error}</p>}
        </div>
      )}

      {/* Simulation Tab */}
      {activeTab === 'simulation' && analysis && !analysis.error && (
        <div>
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
            <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ color: '#999', fontSize: 12 }}>总收益</div>
              <div style={{ color: analysis.simulation.total_pnl >= 0 ? '#52c41a' : '#ff4d4f', fontSize: 20, fontWeight: 700 }}>
                HK${fmt(analysis.simulation.total_pnl)}
              </div>
            </div>
            <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ color: '#999', fontSize: 12 }}>收益率</div>
              <div style={{ color: analysis.simulation.total_return_pct >= 0 ? '#52c41a' : '#ff4d4f', fontSize: 20, fontWeight: 700 }}>
                {analysis.simulation.total_return_pct}%
              </div>
            </div>
            <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ color: '#999', fontSize: 12 }}>已实现盈亏</div>
              <div style={{ color: '#1890ff', fontSize: 20, fontWeight: 700 }}>HK${fmt(analysis.simulation.realized_pnl)}</div>
            </div>
            <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ color: '#999', fontSize: 12 }}>未实现盈亏</div>
              <div style={{ color: '#faad14', fontSize: 20, fontWeight: 700 }}>HK${fmt(analysis.simulation.unrealized_pnl)}</div>
            </div>
            <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ color: '#999', fontSize: 12 }}>交易次数</div>
              <div style={{ color: '#d4a76a', fontSize: 20, fontWeight: 700 }}>{analysis.simulation.total_trades}</div>
            </div>
            <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ color: '#999', fontSize: 12 }}>持仓数</div>
              <div style={{ color: '#722ed1', fontSize: 20, fontWeight: 700 }}>{analysis.simulation.open_positions}</div>
            </div>
          </div>

          {/* Equity Curve */}
          {analysis.simulation.equity_curve.length > 0 && (
            <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
              <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>资金曲线</h4>
              <div style={{ height: 200, position: 'relative', overflow: 'hidden' }}>
                {(() => {
                  const curve = analysis.simulation.equity_curve
                  const eqs = curve.map(c => c.equity)
                  const minEq = Math.min(...eqs)
                  const maxEq = Math.max(...eqs)
                  const range = maxEq - minEq || 1
                  const points = curve.map((c, i) => {
                    const x = (i / (curve.length - 1)) * 100
                    const y = 100 - ((c.equity - minEq) / range) * 90
                    return `${x},${y}`
                  }).join(' ')
                  return (
                    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
                      <polyline points={points} fill="none" stroke="#d4a76a" strokeWidth="0.3" />
                      <text x="1" y="10" fill="#999" fontSize="3">{fmt(maxEq)}</text>
                      <text x="1" y="95" fill="#999" fontSize="3">{fmt(minEq)}</text>
                    </svg>
                  )
                })()}
              </div>
            </div>
          )}

          {/* Trade Log */}
          <h4 style={{ color: '#d4a76a', marginBottom: 8 }}>交易记录 (最近50笔)</h4>
          <table className="arb-table" style={{ width: '100%' }}>
            <thead>
              <tr><th>日期</th><th>操作</th><th>价格</th><th>网格层级</th><th>股数</th><th>盈亏</th></tr>
            </thead>
            <tbody>
              {analysis.simulation.trades.map((t, i) => (
                <tr key={i}>
                  <td style={{ fontSize: 12 }}>{t.date}</td>
                  <td><span style={{ color: t.action === 'buy' ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
                    {t.action === 'buy' ? '买入' : '卖出'}</span></td>
                  <td>{fmt(t.price)}</td>
                  <td>{fmt(t.level)}</td>
                  <td>{t.shares}</td>
                  <td style={{ color: (t.pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f' }}>
                    {t.pnl ? `HK$${fmt(t.pnl)}` : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Status Tab */}
      {activeTab === 'status' && analysis && !analysis.error && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333' }}>
              <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>当前位置</h4>
              <p style={{ color: '#ccc', fontSize: 14 }}>
                现价: <span style={{ color: '#d4a76a', fontWeight: 700 }}>HK${fmt(analysis.current_price)}</span>
              </p>
              <p style={{ color: '#ccc', fontSize: 14 }}>
                最近网格: <span style={{ color: '#1890ff' }}>{fmt(analysis.status.nearest_level?.price)}</span>
                ({analysis.status.nearest_level?.distance_pct}%)
              </p>
            </div>
            <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333' }}>
              <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>触发价位</h4>
              {analysis.status.next_buy && (
                <p style={{ color: '#ccc', fontSize: 14 }}>
                  下一买入: <span style={{ color: '#52c41a', fontWeight: 700 }}>HK${fmt(analysis.status.next_buy.price)}</span>
                  ({analysis.status.next_buy.distance_pct}%)
                </p>
              )}
              {analysis.status.next_sell && (
                <p style={{ color: '#ccc', fontSize: 14 }}>
                  下一卖出: <span style={{ color: '#ff4d4f', fontWeight: 700 }}>HK${fmt(analysis.status.next_sell.price)}</span>
                  (+{analysis.status.next_sell.distance_pct}%)
                </p>
              )}
            </div>
          </div>

          {/* Open Positions */}
          {analysis.simulation.position_details.length > 0 && (
            <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
              <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>持仓明细 ({analysis.simulation.open_positions}个)</h4>
              <table className="arb-table" style={{ width: '100%' }}>
                <thead>
                  <tr><th>网格层级</th><th>股数</th><th>买入价</th><th>未实现盈亏</th></tr>
                </thead>
                <tbody>
                  {analysis.simulation.position_details.map((p, i) => (
                    <tr key={i}>
                      <td>{fmt(p.level)}</td>
                      <td>{p.shares}</td>
                      <td>{fmt(p.entry)}</td>
                      <td style={{ color: p.unrealized >= 0 ? '#52c41a' : '#ff4d4f' }}>HK${fmt(p.unrealized)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Capital Utilization */}
          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333' }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>资金利用率</h4>
            <div style={{ background: '#333', height: 24, borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                background: '#d4a76a', height: '100%', borderRadius: 4,
                width: `${Math.min((analysis.simulation.open_positions / analysis.total_levels) * 100, 100)}%`,
              }} />
            </div>
            <p style={{ color: '#ccc', fontSize: 13, marginTop: 8 }}>
              已用: {analysis.simulation.open_positions}/{analysis.total_levels}格
              ({((analysis.simulation.open_positions / analysis.total_levels) * 100).toFixed(0)}%)
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
