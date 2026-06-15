import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState } from '../components/ui'
import { useTradingInterceptor } from '../hooks/useTradingInterceptor'
import RationalCheckpoint from '../components/RationalCheckpoint'

const API_BASE = '/api'

interface OptionContract {
  symbol: string
  code: string
  option_type: string
  strike: number
  expiry: string
  dte: number
  contract_size: number
  bid: number
  ask: number
  mid: number
  last: number
  volume: number
  open_interest: number
  delta: number
  gamma: number
  theta: number
  vega: number
  rho?: number
  iv: number
  intrinsic: number
  time_value: number
  otm_pct: number
  breakeven: number
  pop: number
  annual_yield: number
  score: number
  detail: string
  max_profit: number
  max_loss: number | null
  spread?: number
  spread_pct?: number
  liquidity_score?: number
  can_trade?: boolean
  spot?: number
}

interface OptionChain {
  spot_price: number
  stock_name: string
  stock_code: string
  hv: number
  contract_size: number
  option_type: string
  chain: OptionContract[]
  expiries: string[]
  strikes: number[]
  best_put: OptionContract | null
  best_call: OptionContract | null
  best_yield: OptionContract | null
  safest: OptionContract | null
  total: number
  update_time: string
  data_source: string
  error?: string
  iv_analysis?: {
    current_iv?: number
    hv?: number
    iv_rank?: number
    iv_percentile?: number
    iv_hv_ratio?: number
    term_structure?: string
    skew?: string
    recommendation?: string
    signal?: string
    interpretation?: string
    min_iv?: number
    max_iv?: number
  }
}

interface ConnectionStatus {
  connected: boolean
  error?: string
  solution?: string
  host?: string
  port?: string
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

interface SearchResult {
  code: string
  name: string
}

export default function FutuOptionChain() {
  const [activeTab, setActiveTab] = useState<'chain' | 'philosophy' | 'calculator' | 'rolling' | 'strategy' | 'iv_surface' | 'pnl' | 'screening'>('chain')
  const [chain, setChain] = useState<OptionChain | null>(null)
  const [loading, setLoading] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus | null>(null)
  const [selectedExpiry, setSelectedExpiry] = useState<string>('all')
  const [selectedType, setSelectedType] = useState<'all' | 'put' | 'call'>('all')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'table' | 'strike'>('table')
  const [error, setError] = useState<string>('')
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)

  // Stock search
  const [stockCode, setStockCode] = useState('00700')
  const [stockSearch, setStockSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const searchTimerRef = useRef<number | null>(null)

  // Calculator state
  const [calcSpot, setCalcSpot] = useState('500')
  const [calcStrike, setCalcStrike] = useState('470')
  const [calcDays, setCalcDays] = useState('30')
  const [calcType, setCalcType] = useState<'put' | 'call'>('put')
  const [calcSigma, setCalcSigma] = useState('30')
  const [calcResult, setCalcResult] = useState<any>(null)
  const [calcLoading, setCalcLoading] = useState(false)

  // Rolling state
  const [rollSpot, setRollSpot] = useState('500')
  const [rollStrike, setRollStrike] = useState('470')
  const [rollPremium, setRollPremium] = useState('10')
  const [rollDteLeft, setRollDteLeft] = useState('15')
  const [rollEntryDte, setRollEntryDte] = useState('30')
  const [rollType, setRollType] = useState<'put' | 'call'>('put')
  const [rollHv, setRollHv] = useState('30')
  const [rollResult, setRollResult] = useState<any>(null)
  const [rollLoading, setRollLoading] = useState(false)

  // Strategy analysis state
  const [strategyResult, setStrategyResult] = useState<any>(null)
  const [strategyLoading, setStrategyLoading] = useState(false)
  const [pnlData, setPnlData] = useState<any>(null)
  const [pnlLoading, setPnlLoading] = useState(false)
  const [maxPain, setMaxPain] = useState<any>(null)
  const [ivSurface, setIvSurface] = useState<any>(null)
  const [ivSurfaceLoading, setIvSurfaceLoading] = useState(false)

  // Screening state
  const [screenTradeFee, setScreenTradeFee] = useState('16')
  const [screenExerciseFee, setScreenExerciseFee] = useState('100')
  const [screenMinYield, setScreenMinYield] = useState('15')
  const [screenMinOtm, setScreenMinOtm] = useState('3')
  const [screenResult, setScreenResult] = useState<any>(null)
  const [screenLoading, setScreenLoading] = useState(false)

  // Stock search
  const handleSearch = useCallback(async (keyword: string) => {
    if (!keyword.trim()) { setSearchResults([]); return }
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
    setChain(null)
  }

  // Check connection
  const checkConnection = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/futu-options/connection`)
      setConnectionStatus(res.data)
    } catch {
      setConnectionStatus({ connected: false, error: '无法连接到后端服务' })
    }
  }, [])

  useEffect(() => { checkConnection() }, [checkConnection])

  // 交易拦截器
  const { intercept, checkpointOpen, checkpointMeta, handlePass, handleCancel } = useTradingInterceptor()

  // Load philosophy
  useEffect(() => {
    axios.get(`${API_BASE}/futu-options/philosophy`)
      .then(res => setPhilosophy(res.data))
      .catch(() => {})
  }, [])

  // Load max pain (must be before loadChain)
  const loadMaxPain = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/futu-options/max_pain`, { params: { stock_code: `HK.${stockCode}` } })
      setMaxPain(res.data)
    } catch { }
  }, [stockCode])

  // Load option chain
  const loadChain = useCallback(async () => {
    if (!connectionStatus?.connected) {
      setError('请先启动 Futu OpenD 并确保连接正常')
      return
    }
    setLoading(true)
    setError('')
    setMaxPain(null)
    try {
      const params = { stock_code: `HK.${stockCode}`, option_type: selectedType }
      const res = await axios.get(`${API_BASE}/futu-options/chain`, { params })
      if (res.data.error) {
        setError(res.data.error)
        setChain(null)
      } else {
        setChain(res.data)
        if (res.data.expiries?.length > 0) setSelectedExpiry('all')
        // Load max pain in background
        loadMaxPain()
      }
    } catch (e: any) {
      setError(e.response?.data?.detail || '获取数据失败')
    }
    setLoading(false)
  }, [stockCode, selectedType, connectionStatus, loadMaxPain])

  // Calculator
  const runCalc = useCallback(async () => {
    setCalcLoading(true)
    setCalcResult(null)
    try {
      const res = await axios.get(`${API_BASE}/futu-options/greeks`, {
        params: {
          spot: parseFloat(calcSpot), strike: parseFloat(calcStrike),
          days: parseInt(calcDays), sigma: parseFloat(calcSigma) / 100, option_type: calcType,
        },
      })
      setCalcResult(res.data)
    } catch { }
    setCalcLoading(false)
  }, [calcSpot, calcStrike, calcDays, calcType, calcSigma])

  // Rolling
  const runRolling = useCallback(async () => {
    setRollLoading(true)
    setRollResult(null)
    try {
      const res = await axios.get(`${API_BASE}/futu-options/rolling`, {
        params: {
          spot: parseFloat(rollSpot), strike: parseFloat(rollStrike),
          premium: parseFloat(rollPremium), dte_left: parseInt(rollDteLeft),
          entry_dte: parseInt(rollEntryDte), option_type: rollType,
          hv: parseFloat(rollHv) / 100,
        },
      })
      setRollResult(res.data)
    } catch { }
    setRollLoading(false)
  }, [rollSpot, rollStrike, rollPremium, rollDteLeft, rollEntryDte, rollType, rollHv])

  // Strategy analysis（实际执行）
  const doRunStrategy = useCallback(async (strategy: string, extra: Record<string, string> = {}) => {
    if (!connectionStatus?.connected) return
    setStrategyLoading(true)
    setStrategyResult(null)
    setPnlData(null)
    try {
      const endpoint = strategy === 'covered_call' ? '/strategy/covered_call'
        : strategy === 'csp' ? '/strategy/cash_secured_put'
        : strategy === 'credit_spread' ? '/strategy/credit_spread'
        : strategy === 'straddle' ? '/strategy/straddle'
        : strategy === 'strangle' ? '/strategy/strangle'
        : '/strategy/iron_condor'
      const params: Record<string, string> = { stock_code: `HK.${stockCode}`, ...extra }
      const res = await axios.get(`${API_BASE}/futu-options${endpoint}`, { params })
      setStrategyResult(res.data)
      // Auto-load P&L
      if (!res.data?.error) {
        loadPnl(strategy, extra)
      }
    } catch (e: any) {
      setStrategyResult({ error: e.response?.data?.detail || '分析失败' })
    }
    setStrategyLoading(false)
  }, [stockCode, connectionStatus])

  // Strategy analysis（带拦截）
  const STRATEGY_LABELS: Record<string, string> = {
    covered_call: 'Covered Call',
    csp: 'Cash Secured Put',
    credit_spread: 'Credit Spread',
    straddle: 'Straddle',
    strangle: 'Strangle',
    iron_condor: 'Iron Condor',
  }

  const runStrategy = useCallback((strategy: string, extra: Record<string, string> = {}) => {
    intercept(() => doRunStrategy(strategy, extra), {
      actionType: 'analyze',
      target: `${STRATEGY_LABELS[strategy] || strategy} (HK.${stockCode})`,
    })
  }, [intercept, doRunStrategy, stockCode])

  const loadPnl = useCallback(async (strategy: string, extra: Record<string, string> = {}) => {
    setPnlLoading(true)
    setPnlData(null)
    try {
      const params: Record<string, string> = { stock_code: `HK.${stockCode}`, strategy, ...extra }
      const res = await axios.get(`${API_BASE}/futu-options/strategy/pnl`, { params })
      setPnlData(res.data)
    } catch { }
    setPnlLoading(false)
  }, [stockCode])

  const loadIvSurface = useCallback(async () => {
    setIvSurfaceLoading(true)
    setIvSurface(null)
    try {
      const res = await axios.get(`${API_BASE}/futu-options/iv_surface`, { params: { stock_code: `HK.${stockCode}` } })
      setIvSurface(res.data)
    } catch { }
    setIvSurfaceLoading(false)
  }, [stockCode])

  // 策略筛选
  const runScreening = useCallback(async () => {
    setScreenLoading(true)
    setScreenResult(null)
    try {
      const res = await axios.get(`${API_BASE}/futu-options/screen`, {
        params: {
          stock_code: `HK.${stockCode}`,
          trade_fee: parseFloat(screenTradeFee) || 16,
          exercise_fee: parseFloat(screenExerciseFee) || 100,
          min_yield: parseFloat(screenMinYield) || 15,
          min_otm: parseFloat(screenMinOtm) || 3,
        },
      })
      setScreenResult(res.data)
    } catch (e: any) {
      setScreenResult({ error: e.response?.data?.detail || e.message || '请求失败' })
    }
    setScreenLoading(false)
  }, [stockCode, screenTradeFee, screenExerciseFee, screenMinYield, screenMinOtm])

  // Filter chain by expiry
  const filteredChain = chain?.chain?.filter(c => {
    if (selectedExpiry !== 'all' && c.expiry !== selectedExpiry) return false
    return true
  }) || []

  // Group by strike for strike view
  const groupedByStrike = viewMode === 'strike' ? (() => {
    const groups: Record<number, { put?: OptionContract; call?: OptionContract }> = {}
    filteredChain.forEach(c => {
      if (!groups[c.strike]) groups[c.strike] = {}
      if (c.option_type === 'put') groups[c.strike].put = c
      else groups[c.strike].call = c
    })
    return groups
  })() : {}

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

  const getTypeColor = (type: string) => type === 'put' ? '#52c41a' : '#1890ff'

  // ====== NOT CONNECTED: Only show connection guide ======
  if (!connectionStatus?.connected) {
    return (
      <div className="cb-page">
        <div className="stock-header">
          <h2>期权轮动（实战版）</h2>
          <p style={{ color: '#999', margin: '4px 0 0' }}>
            基于 Futu OpenD 真实市场数据 · BSM Greeks · 评分系统 · 轮动建议
          </p>
        </div>

        <div style={{
          marginBottom: 16, padding: 16,
          background: connectionStatus ? '#2e1a1a' : '#1a1a2e',
          borderRadius: 8,
          border: `1px solid ${connectionStatus ? '#ff4d4f' : '#333'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ color: '#ff4d4f', fontWeight: 600, fontSize: 18 }}>
              ❌ Futu OpenD 未连接
            </span>
            <button onClick={checkConnection}
              style={{ padding: '6px 16px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              检查连接
            </button>
          </div>
          {connectionStatus?.error && (
            <p style={{ color: '#ff4d4f', margin: '0 0 8px', fontSize: 14 }}>
              ⚠️ {connectionStatus.error}
            </p>
          )}
          {connectionStatus?.solution && (
            <p style={{ color: '#faad14', margin: '0 0 16px', fontSize: 14 }}>
              💡 {connectionStatus.solution}
            </p>
          )}
        </div>

        <div style={{ padding: 24, background: '#1a1a2e', borderRadius: 8, border: '1px solid #333' }}>
          <h3 style={{ color: '#d4a76a', marginBottom: 16 }}>📖 连接 Futu OpenD 指南</h3>
          <div style={{ color: '#ccc', fontSize: 15, lineHeight: 2 }}>
            <p><strong>本页面需要 Futu OpenD 才能显示真实数据。</strong></p>
            <p>没有 OpenD 连接时，<span style={{ color: '#ff4d4f' }}>不会显示任何模拟数据</span>，避免误导实盘交易。</p>
            <ol style={{ paddingLeft: 24, marginTop: 16 }}>
              <li>下载 <a href="https://www.futunn.com/download/OpenAPI" target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff' }}>Futu OpenD</a></li>
              <li>安装并启动 OpenD，使用富途账户登录</li>
              <li>确保 OpenD 运行在 <code style={{ background: '#333', padding: '2px 8px', borderRadius: 4 }}>127.0.0.1:11111</code></li>
              <li>点击上方"检查连接"确认状态</li>
            </ol>
          </div>
        </div>
      </div>
    )
  }

  // ====== CONNECTED: Full page ======
  return (
    <div className="cb-page">
      <div className="stock-header">
        <h2>期权轮动（实战版） - {chain?.stock_name || stockCode}</h2>
        <p style={{ color: '#999', margin: '4px 0 0' }}>
          ✅ Futu OpenD 已连接 · 真实市场数据 · BSM Greeks · 评分系统
        </p>
      </div>

      {/* Connection Status Bar */}
      <div style={{
        marginBottom: 12, padding: '8px 16px',
        background: '#1a2e1a', borderRadius: 8, border: '1px solid #52c41a',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <span style={{ color: '#52c41a', fontSize: 13, fontWeight: 600 }}>
          ✅ OpenD 已连接 ({connectionStatus.host}:{connectionStatus.port})
        </span>
        <button onClick={checkConnection}
          style={{ padding: '2px 10px', background: '#333', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
          刷新连接
        </button>
      </div>

      {/* Stock Search */}
      <div ref={searchRef} style={{ position: 'relative', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
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

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {([
          { key: 'chain', label: '期权链' },
          { key: 'strategy', label: '组合策略' },
          { key: 'screening', label: '🔍 策略筛选' },
          { key: 'pnl', label: 'P&L盈亏图' },
          { key: 'iv_surface', label: 'IV曲面' },
          { key: 'philosophy', label: '卖期权理念' },
          { key: 'calculator', label: 'BSM计算器' },
          { key: 'rolling', label: '轮动建议' },
        ] as const).map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '6px 16px',
              background: activeTab === tab.key ? '#d4a76a' : '#333',
              color: activeTab === tab.key ? '#000' : '#fff',
              border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13,
            }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ====== CHAIN TAB ====== */}
      {activeTab === 'chain' && (
        <div>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ color: '#ccc' }}>到期日:
              <select value={selectedExpiry} onChange={e => setSelectedExpiry(e.target.value)}
                style={{ marginLeft: 6, padding: '4px 8px', background: '#1a1a2e', color: '#fff', border: '1px solid #444', borderRadius: 4 }}>
                <option value="all">全部</option>
                {chain?.expiries?.map(exp => (
                  <option key={exp} value={exp}>{exp}</option>
                ))}
              </select>
            </label>
            <label style={{ color: '#ccc' }}>类型:
              <select value={selectedType} onChange={e => { setSelectedType(e.target.value as any); setChain(null) }}
                style={{ marginLeft: 6, padding: '4px 8px', background: '#1a1a2e', color: '#fff', border: '1px solid #444', borderRadius: 4 }}>
                <option value="all">全部</option>
                <option value="put">Put</option>
                <option value="call">Call</option>
              </select>
            </label>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => setViewMode('table')} disabled={viewMode === 'table'}
                style={{ padding: '4px 12px', background: viewMode === 'table' ? '#d4a76a' : '#333', color: viewMode === 'table' ? '#000' : '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                列表
              </button>
              <button onClick={() => setViewMode('strike')} disabled={viewMode === 'strike'}
                style={{ padding: '4px 12px', background: viewMode === 'strike' ? '#d4a76a' : '#333', color: viewMode === 'strike' ? '#000' : '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                行权价
              </button>
            </div>
            <button onClick={loadChain} disabled={loading}
              style={{ padding: '6px 16px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {loading ? '加载中...' : '获取期权链'}
            </button>
          </div>

          {error && (
            <div style={{ marginBottom: 16, padding: 12, background: '#2e1a1a', borderRadius: 8, border: '1px solid #ff4d4f' }}>
              <p style={{ color: '#ff4d4f', margin: 0 }}>{error}</p>
            </div>
          )}

          {chain && !chain.error && (
            <>
              {/* Summary Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 16 }}>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>{chain.stock_name} 现价</div>
                  <div style={{ color: '#d4a76a', fontSize: 22, fontWeight: 700 }}>HK${chain.spot_price}</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>历史波动率 (HV)</div>
                  <div style={{ color: '#1890ff', fontSize: 22, fontWeight: 700 }}>{chain.hv}%</div>
                </div>
                {chain.iv_analysis && (
                  <div style={{ background: (chain.iv_analysis.iv_percentile ?? 0) >= 60 ? '#1a2e1a' : '#2e2e1a', padding: 14, borderRadius: 8, border: `1px solid ${(chain.iv_analysis.iv_percentile ?? 0) >= 60 ? '#52c41a' : '#faad14'}` }}>
                    <div style={{ color: '#999', fontSize: 12 }}>IV Percentile</div>
                    <div style={{ color: (chain.iv_analysis.iv_percentile ?? 0) >= 60 ? '#52c41a' : '#faad14', fontSize: 22, fontWeight: 700 }}>{chain.iv_analysis.iv_percentile}%</div>
                    <div style={{ color: '#999', fontSize: 11 }}>{chain.iv_analysis.signal === 'sell_premium' ? '✅ 适合卖期权' : chain.iv_analysis.signal === 'sell_premium_ok' ? '可卖期权' : '⚠️ IV偏低'}</div>
                  </div>
                )}
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>合约数量</div>
                  <div style={{ color: '#722ed1', fontSize: 22, fontWeight: 700 }}>{chain.total}份</div>
                </div>
                {maxPain && !maxPain.error && (
                  <div style={{ background: '#2e2e1a', padding: 14, borderRadius: 8, border: '1px solid #faad14' }}>
                    <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>Max Pain</div>
                    <div style={{ color: '#fff', fontSize: 20, fontWeight: 700 }}>{maxPain.max_pain_strike}</div>
                    <div style={{ color: '#999', fontSize: 11 }}>
                      距现价 {maxPain.distance_pct > 0 ? '+' : ''}{maxPain.distance_pct}%
                    </div>
                  </div>
                )}
              </div>

              {/* IV Analysis */}
              {chain.iv_analysis && (
                <div style={{ marginBottom: 16, padding: 12, background: '#1a1a2e', borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ color: '#d4a76a', fontWeight: 600 }}>📊 IV 分析：</span>
                    <span style={{ color: '#ccc', fontSize: 13 }}>{chain.iv_analysis.interpretation || chain.iv_analysis.recommendation || ''}</span>
                  </div>
                  {chain.iv_analysis.min_iv != null && (
                    <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
                      IV 范围: {chain.iv_analysis.min_iv}% - {chain.iv_analysis.max_iv}% | IV Rank: {chain.iv_analysis.iv_rank}%
                    </div>
                  )}
                </div>
              )}

              {/* Best Picks */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 }}>
                {chain.best_put && (
                  <div style={{ background: '#1a2e1a', padding: 14, borderRadius: 8, border: '1px solid #52c41a' }}>
                    <div style={{ color: '#52c41a', fontSize: 13, fontWeight: 600 }}>最佳Put</div>
                    <div style={{ color: '#fff', fontSize: 14 }}>
                      K={chain.best_put.strike} | {chain.best_put.dte}天 | 评分{chain.best_put.score}
                    </div>
                    <div style={{ color: '#999', fontSize: 12 }}>
                      成交: {chain.best_put.last} | IV: {chain.best_put.iv}% | 胜率: {chain.best_put.pop}%
                    </div>
                  </div>
                )}
                {chain.best_call && (
                  <div style={{ background: '#1a2e1a', padding: 14, borderRadius: 8, border: '1px solid #1890ff' }}>
                    <div style={{ color: '#1890ff', fontSize: 13, fontWeight: 600 }}>最佳Call</div>
                    <div style={{ color: '#fff', fontSize: 14 }}>
                      K={chain.best_call.strike} | {chain.best_call.dte}天 | 评分{chain.best_call.score}
                    </div>
                    <div style={{ color: '#999', fontSize: 12 }}>
                      成交: {chain.best_call.last} | IV: {chain.best_call.iv}% | 胜率: {chain.best_call.pop}%
                    </div>
                  </div>
                )}
                {chain.best_yield && (
                  <div style={{ background: '#2e2e1a', padding: 14, borderRadius: 8, border: '1px solid #faad14' }}>
                    <div style={{ color: '#faad14', fontSize: 13, fontWeight: 600 }}>最高收益</div>
                    <div style={{ color: '#fff', fontSize: 14 }}>
                      K={chain.best_yield.strike} | 年化{chain.best_yield.annual_yield}%
                    </div>
                    <div style={{ color: '#999', fontSize: 12 }}>
                      {chain.best_yield.option_type.toUpperCase()} | 胜率: {chain.best_yield.pop}%
                    </div>
                  </div>
                )}
                {chain.safest && (
                  <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #722ed1' }}>
                    <div style={{ color: '#722ed1', fontSize: 13, fontWeight: 600 }}>最安全</div>
                    <div style={{ color: '#fff', fontSize: 14 }}>
                      K={chain.safest.strike} | OTM {chain.safest.otm_pct}%
                    </div>
                    <div style={{ color: '#999', fontSize: 12 }}>
                      胜率: {chain.safest.pop}% | {chain.safest.dte}天
                    </div>
                  </div>
                )}
              </div>

              {/* Option Chain Table */}
              {viewMode === 'table' ? (
                <div style={{ overflowX: 'auto' }}>
                  <table className="arb-table" style={{ width: '100%', minWidth: 950 }}>
                    <thead>
                      <tr>
                        <th>类型</th><th>行权价</th><th>到期</th><th>天数</th>
                        <th>买入</th><th>卖出</th><th>最新</th>
                        <th>成交量</th><th>IV%</th><th>Delta</th>
                        <th>OTM%</th><th>胜率</th><th>年化%</th><th>价差%</th><th>评分</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredChain.slice(0, 100).map((c) => {
                        const key = `${c.code}_${c.strike}_${c.expiry}`
                        return (
                          <Fragment key={key}>
                            <tr onClick={() => setExpandedRow(expandedRow === key ? null : key)}
                              style={{ cursor: 'pointer', background: expandedRow === key ? '#1a1a2e' : 'transparent' }}>
                              <td><span style={{ color: getTypeColor(c.option_type), fontWeight: 600 }}>{c.option_type.toUpperCase()}</span></td>
                              <td style={{ fontWeight: 600 }}>{c.strike}</td>
                              <td style={{ fontSize: 12 }}>{c.expiry.slice(5)}</td>
                              <td>{c.dte}天</td>
                              <td>{c.bid || '-'}</td>
                              <td>{c.ask || '-'}</td>
                              <td style={{ fontWeight: 600 }}>{c.last || '-'}</td>
                              <td>{c.volume || '-'}</td>
                              <td>{c.iv}%</td>
                              <td>{c.delta?.toFixed(3) || '-'}</td>
                              <td>{c.otm_pct}%</td>
                              <td>{c.pop}%</td>
                              <td style={{ color: c.annual_yield >= 10 ? '#52c41a' : '#faad14' }}>{c.annual_yield}%</td>
                              <td style={{ color: (c.spread_pct ?? 999) <= 5 ? '#52c41a' : (c.spread_pct ?? 999) <= 10 ? '#faad14' : '#ff4d4f' }}>{c.spread_pct ?? '-'}%</td>
                              <td><span style={{ color: getScoreColor(c.score), fontWeight: 700, fontSize: 16 }}>{c.score}</span></td>
                            </tr>
                            {expandedRow === key && (
                              <tr>
                                <td colSpan={15} style={{ padding: '12px 20px', background: '#111' }}>
                                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, fontSize: 13 }}>
                                    <div>
                                      <p style={{ color: '#d4a76a', fontWeight: 600, marginBottom: 8 }}>Greeks (BSM)</p>
                                      <p style={{ color: '#ccc' }}>Delta: {c.delta?.toFixed(4)}</p>
                                      <p style={{ color: '#ccc' }}>Gamma: {c.gamma?.toFixed(6)}</p>
                                      <p style={{ color: '#ccc' }}>Theta: {c.theta?.toFixed(4)}/天</p>
                                      <p style={{ color: '#ccc' }}>Vega: {c.vega?.toFixed(4)}</p>
                                      {c.rho != null && <p style={{ color: '#ccc' }}>Rho: {c.rho?.toFixed(4)}</p>}
                                    </div>
                                    <div>
                                      <p style={{ color: '#d4a76a', fontWeight: 600, marginBottom: 8 }}>流动性分析</p>
                                      <p style={{ color: '#ccc' }}>价差: {c.spread || '-'}</p>
                                      <p style={{ color: '#ccc' }}>价差比: {c.spread_pct || '-'}%</p>
                                      <p style={{ color: '#ccc' }}>流动性评分: {c.liquidity_score || '-'}</p>
                                      <p style={{ color: c.can_trade ? '#52c41a' : '#ff4d4f' }}>{c.can_trade ? '✅ 可交易' : '❌ 流动性差'}</p>
                                    </div>
                                    <div>
                                      <p style={{ color: '#d4a76a', fontWeight: 600, marginBottom: 8 }}>价值分析</p>
                                      <p style={{ color: '#ccc' }}>内在价值: {c.intrinsic}</p>
                                      <p style={{ color: '#ccc' }}>时间价值: {c.time_value}</p>
                                      <p style={{ color: '#ccc' }}>盈亏平衡: {c.breakeven}</p>
                                      <p style={{ color: '#ccc' }}>期权代码: {c.code}</p>
                                    </div>
                                    <div>
                                      <p style={{ color: '#d4a76a', fontWeight: 600, marginBottom: 8 }}>收益分析</p>
                                      <p style={{ color: '#ccc' }}>最大盈利: ${c.max_profit}/手</p>
                                      <p style={{ color: '#ccc' }}>最大亏损: {c.max_loss != null ? `$${c.max_loss}` : '无限'}</p>
                                      {c.detail && <p style={{ color: '#ccc', whiteSpace: 'pre-wrap', marginTop: 8 }}>{c.detail}</p>}
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                /* Strike View */
                <div style={{ overflowX: 'auto' }}>
                  <table className="arb-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th colSpan={6} style={{ textAlign: 'center', color: '#52c41a' }}>Put</th>
                        <th style={{ textAlign: 'center', background: '#2a2a4e' }}>行权价</th>
                        <th colSpan={6} style={{ textAlign: 'center', color: '#1890ff' }}>Call</th>
                      </tr>
                      <tr>
                        <th>评分</th><th>年化%</th><th>胜率</th><th>Delta</th><th>成交量</th><th>价格</th>
                        <th style={{ background: '#2a2a4e' }}></th>
                        <th>价格</th><th>成交量</th><th>Delta</th><th>胜率</th><th>年化%</th><th>评分</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(groupedByStrike)
                        .sort(([a], [b]) => Number(b) - Number(a))
                        .slice(0, 30)
                        .map(([strike, { put, call }]) => {
                          const isATM = Math.abs(Number(strike) - (chain?.spot_price || 0)) < (chain?.spot_price || 0) * 0.02
                          return (
                            <tr key={strike} style={{ background: isATM ? '#2a2a1a' : 'transparent' }}>
                              <td style={{ color: put ? getScoreColor(put.score) : '#666', fontWeight: 700 }}>{put?.score || '-'}</td>
                              <td style={{ color: put?.annual_yield && put.annual_yield >= 10 ? '#52c41a' : '#faad14' }}>{put?.annual_yield || '-'}%</td>
                              <td>{put?.pop || '-'}%</td>
                              <td>{put?.delta?.toFixed(3) || '-'}</td>
                              <td>{put?.volume || '-'}</td>
                              <td style={{ fontWeight: 600 }}>{put?.last || '-'}</td>
                              <td style={{
                                textAlign: 'center', fontWeight: 700, fontSize: 16,
                                background: isATM ? '#d4a76a' : '#2a2a4e', color: isATM ? '#000' : '#fff',
                              }}>{strike}</td>
                              <td style={{ fontWeight: 600 }}>{call?.last || '-'}</td>
                              <td>{call?.volume || '-'}</td>
                              <td>{call?.delta?.toFixed(3) || '-'}</td>
                              <td>{call?.pop || '-'}%</td>
                              <td style={{ color: call?.annual_yield && call.annual_yield >= 10 ? '#52c41a' : '#faad14' }}>{call?.annual_yield || '-'}%</td>
                              <td style={{ color: call ? getScoreColor(call.score) : '#666', fontWeight: 700 }}>{call?.score || '-'}</td>
                            </tr>
                          )
                        })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ====== STRATEGY TAB ====== */}
      {activeTab === 'strategy' && (
        <div>
          <h3 style={{ color: '#d4a76a', marginBottom: 16 }}>组合策略分析</h3>
          <p style={{ color: '#999', marginBottom: 16 }}>基于真实市场数据的期权组合策略推荐 -- 点击按钮运行分析</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 20 }}>
            {[
              { key: 'covered_call', label: 'Covered Call', color: '#52c41a', desc: '持有正股 + 卖出虚值 Call，增强收益' },
              { key: 'csp', label: 'Cash Secured Put', color: '#1890ff', desc: '卖出虚值 Put，准备资金低位接盘' },
              { key: 'credit_spread', label: 'Credit Spread', color: '#faad14', desc: '卖近价 + 买远价，限制最大亏损' },
              { key: 'straddle', label: 'Straddle (跨式)', color: '#722ed1', desc: '同K买/卖 Call+Put，博大幅波动' },
              { key: 'strangle', label: 'Strangle (宽跨式)', color: '#eb2f96', desc: 'OTM Call+Put，成本更低' },
              { key: 'iron_condor', label: 'Iron Condor (铁鹰)', color: '#13c2c2', desc: '双价差组合，横盘收租' },
            ].map(s => (
              <div key={s.key} style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <h4 style={{ color: s.color, marginBottom: 6, fontSize: 14 }}>{s.label}</h4>
                <p style={{ color: '#999', fontSize: 12, marginBottom: 10 }}>{s.desc}</p>
                <button onClick={() => runStrategy(s.key)}
                  disabled={strategyLoading || !connectionStatus?.connected}
                  style={{ padding: '5px 14px', background: s.color, color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                  {strategyLoading ? '分析中...' : '运行分析'}
                </button>
              </div>
            ))}
          </div>

          {/* Strategy Result */}
          {strategyResult && !strategyResult.error && (
            <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333', marginBottom: 20 }}>
              <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>{strategyResult.strategy || '策略分析结果'}</h4>
              {strategyResult.description && <p style={{ color: '#ccc', marginBottom: 12 }}>{strategyResult.description}</p>}

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
                {strategyResult.net_credit != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>净权利金</div>
                    <div style={{ color: '#52c41a', fontSize: 18, fontWeight: 700 }}>{strategyResult.net_credit}</div>
                  </div>
                )}
                {(strategyResult.net_debit != null) && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>净支出</div>
                    <div style={{ color: '#ff4d4f', fontSize: 18, fontWeight: 700 }}>{strategyResult.net_debit}</div>
                  </div>
                )}
                {strategyResult.max_profit != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>最大盈利</div>
                    <div style={{ color: '#52c41a', fontSize: 18, fontWeight: 700 }}>
                      {typeof strategyResult.max_profit === 'number' ? `$${strategyResult.max_profit}` : strategyResult.max_profit}
                    </div>
                  </div>
                )}
                {strategyResult.max_loss != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>最大亏损</div>
                    <div style={{ color: '#ff4d4f', fontSize: 18, fontWeight: 700 }}>
                      {typeof strategyResult.max_loss === 'number' ? `$${strategyResult.max_loss}` : strategyResult.max_loss}
                    </div>
                  </div>
                )}
                {strategyResult.breakeven != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>盈亏平衡</div>
                    <div style={{ color: '#faad14', fontSize: 18, fontWeight: 700 }}>{strategyResult.breakeven}</div>
                  </div>
                )}
                {strategyResult.breakeven_range && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>盈亏平衡区间</div>
                    <div style={{ color: '#faad14', fontSize: 16, fontWeight: 700 }}>{strategyResult.breakeven_range}</div>
                  </div>
                )}
                {strategyResult.profit_zone && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>盈利区间</div>
                    <div style={{ color: '#52c41a', fontSize: 14, fontWeight: 700 }}>{strategyResult.profit_zone}</div>
                  </div>
                )}
                {strategyResult.annual_yield != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>年化收益</div>
                    <div style={{ color: '#1890ff', fontSize: 18, fontWeight: 700 }}>{strategyResult.annual_yield}%</div>
                  </div>
                )}
                {strategyResult.pop != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>盈利概率</div>
                    <div style={{ color: '#722ed1', fontSize: 18, fontWeight: 700 }}>{strategyResult.pop}%</div>
                  </div>
                )}
                {strategyResult.risk_reward_ratio != null && (
                  <div style={{ background: '#0d0d1a', padding: 10, borderRadius: 6 }}>
                    <div style={{ color: '#999', fontSize: 11 }}>风险收益比</div>
                    <div style={{ color: '#eb2f96', fontSize: 18, fontWeight: 700 }}>1:{strategyResult.risk_reward_ratio}</div>
                  </div>
                )}
              </div>

              {strategyResult.greeks && (
                <div style={{ marginBottom: 12, padding: 10, background: '#0d0d1a', borderRadius: 6 }}>
                  <span style={{ color: '#d4a76a', fontWeight: 600, fontSize: 13 }}>组合Greeks: </span>
                  <span style={{ color: '#ccc', fontSize: 13 }}>
                    Delta={strategyResult.greeks.delta} | Gamma={strategyResult.greeks.gamma} | Theta={strategyResult.greeks.theta}/天 | Vega={strategyResult.greeks.vega}
                  </span>
                </div>
              )}

              {strategyResult.suitable_market && (
                <p style={{ color: '#999', fontSize: 12 }}>适合市场: {strategyResult.suitable_market}</p>
              )}
              {strategyResult.risk && (
                <p style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>风险: {strategyResult.risk}</p>
              )}

              {/* P&L Chart inline */}
              {pnlData && !pnlData.error && pnlData.pnl && (
                <div style={{ marginTop: 16 }}>
                  <h5 style={{ color: '#d4a76a', marginBottom: 8 }}>到期盈亏图</h5>
                  <ReactECharts
                    notMerge
                    option={{
                      tooltip: {
                        trigger: 'axis',
                        formatter: (params: any) => {
                          const p = params[0]
                          return `标的价格: ${p.axisValue}<br/>P&L: <b style="color:${p.value >= 0 ? '#52c41a' : '#ff4d4f'}">$${p.value}</b>`
                        },
                      },
                      xAxis: {
                        type: 'category',
                        data: pnlData.pnl.prices.filter((_: any, i: number) => i % 2 === 0),
                        axisLabel: { color: '#999', fontSize: 10, rotate: 30 },
                        axisLine: { lineStyle: { color: '#333' } },
                        name: '标的价格',
                        nameTextStyle: { color: '#999' },
                      },
                      yAxis: {
                        type: 'value',
                        axisLabel: { color: '#999', formatter: '${value}' },
                        splitLine: { lineStyle: { color: '#222' } },
                        name: 'P&L ($)',
                        nameTextStyle: { color: '#999' },
                      },
                      series: [{
                        type: 'line',
                        data: pnlData.pnl.pnl.filter((_: any, i: number) => i % 2 === 0),
                        lineStyle: { width: 2 },
                        areaStyle: {
                          color: {
                            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                              { offset: 0, color: 'rgba(82,196,26,0.3)' },
                              { offset: 0.5, color: 'rgba(255,255,255,0)' },
                              { offset: 1, color: 'rgba(255,77,79,0.3)' },
                            ],
                          },
                        },
                        markLine: {
                          silent: true,
                          data: [
                            { xAxis: pnlData.pnl.current_spot, lineStyle: { color: '#d4a76a', type: 'dashed' }, label: { formatter: '现价', color: '#d4a76a' } },
                            ...(pnlData.pnl.breakevens || []).map((be: number) => ({
                              xAxis: be, lineStyle: { color: '#faad14', type: 'dotted' }, label: { formatter: `BE ${be}`, color: '#faad14' },
                            })),
                          ],
                        },
                        itemStyle: { color: '#1890ff' },
                      }],
                      grid: { left: 60, right: 20, top: 30, bottom: 50 },
                    }}
                    style={{ height: 320 }}
                  />
                </div>
              )}
              {pnlLoading && <p style={{ color: '#999', fontSize: 12 }}>加载P&L图表...</p>}
            </div>
          )}
          {strategyResult?.error && (
            <div style={{ padding: 12, background: '#2e1a1a', borderRadius: 8, border: '1px solid #ff4d4f', marginBottom: 16 }}>
              <p style={{ color: '#ff4d4f', margin: 0 }}>{strategyResult.error}</p>
            </div>
          )}
          {strategyLoading && <LoadingSpinner text="正在分析策略..." />}

          <div style={{ marginTop: 8, padding: 16, background: '#1a1a2e', borderRadius: 8, border: '1px solid #333' }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>策略风险提示</h4>
            <ul style={{ color: '#ccc', fontSize: 13, paddingLeft: 20 }}>
              <li>Covered Call：股价大跌时有亏损（但有权利金缓冲）</li>
              <li>Cash Secured Put：股价大跌时需以行权价买入，可能大幅亏损</li>
              <li>Credit Spread / Iron Condor：最大亏损有限（宽度 - 净权利金）</li>
              <li>Straddle / Strangle (Long)：最大亏损=总权利金，需大幅波动才能盈利</li>
              <li>Straddle / Strangle (Short)：收取权利金，但标的大涨大跌时亏损无限</li>
              <li>所有策略：波动率骤升时浮亏增加，需做好风险管理</li>
            </ul>
          </div>
        </div>
      )}

      {/* ====== PHILOSOPHY TAB ====== */}
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

      {/* ====== CALCULATOR TAB ====== */}
      {activeTab === 'calculator' && (
        <div>
          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
            <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>BSM期权计算器</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
              <label style={{ color: '#ccc', fontSize: 13 }}>标的价格
                <input type="number" value={calcSpot} onChange={e => setCalcSpot(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>行权价
                <input type="number" value={calcStrike} onChange={e => setCalcStrike(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>到期天数
                <input type="number" value={calcDays} onChange={e => setCalcDays(e.target.value)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>波动率%
                <input type="number" value={calcSigma} onChange={e => setCalcSigma(e.target.value)} step="1" min="1" max="200"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>类型
                <select value={calcType} onChange={e => setCalcType(e.target.value as any)}
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }}>
                  <option value="put">Put</option><option value="call">Call</option>
                </select>
              </label>
            </div>
            <button onClick={runCalc} disabled={calcLoading}
              style={{ marginTop: 12, padding: '8px 24px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {calcLoading ? '计算中...' : '计算'}
            </button>
          </div>

          {calcResult && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>期权价格</div>
                <div style={{ color: '#d4a76a', fontSize: 20, fontWeight: 700 }}>{calcResult?.greeks?.price?.toFixed(4) ?? '-'}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Delta</div>
                <div style={{ color: '#1890ff', fontSize: 20, fontWeight: 700 }}>{calcResult?.greeks?.delta?.toFixed(4) ?? '-'}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Gamma</div>
                <div style={{ color: '#faad14', fontSize: 20, fontWeight: 700 }}>{calcResult?.greeks?.gamma?.toFixed(6) ?? '-'}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Theta/天</div>
                <div style={{ color: '#ff4d4f', fontSize: 20, fontWeight: 700 }}>{calcResult?.greeks?.theta?.toFixed(4) ?? '-'}</div>
              </div>
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>Vega (1%变动)</div>
                <div style={{ color: '#722ed1', fontSize: 20, fontWeight: 700 }}>{calcResult?.greeks?.vega?.toFixed(4) ?? '-'}</div>
              </div>
              {calcResult.greeks.rho != null && (
                <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 12 }}>Rho (1%利率变动)</div>
                  <div style={{ color: '#13c2c2', fontSize: 20, fontWeight: 700 }}>{calcResult.greeks.rho.toFixed(4)}</div>
                </div>
              )}
              <div style={{ background: '#1a1a2e', padding: 14, borderRadius: 8, border: '1px solid #333' }}>
                <div style={{ color: '#999', fontSize: 12 }}>盈利概率</div>
                <div style={{ color: '#52c41a', fontSize: 20, fontWeight: 700 }}>{((1 - Math.abs(calcResult.greeks.delta)) * 100).toFixed(0)}%</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ====== ROLLING TAB ====== */}
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
              <label style={{ color: '#ccc', fontSize: 13 }}>历史波动率 %
                <input type="number" value={rollHv} onChange={e => setRollHv(e.target.value)} step="1" min="5" max="200"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
            </div>
            <button onClick={runRolling} disabled={rollLoading}
              style={{ marginTop: 12, padding: '8px 24px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {rollLoading ? '分析中...' : '分析'}
            </button>
          </div>

          {rollResult && (
            <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <span style={{ color: '#999', fontSize: 14 }}>建议操作:</span>
                <span style={{ color: getActionColor(rollResult.action), fontSize: 24, fontWeight: 700, textTransform: 'uppercase' }}>
                  {rollResult.action === 'hold' ? '持有' : rollResult.action === 'roll' ? '展期' : '平仓'}
                </span>
              </div>
              <p style={{ color: '#ccc', fontSize: 14, marginBottom: 12 }}>{rollResult.reason}</p>
              <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                <div><span style={{ color: '#999', fontSize: 12 }}>当前OTM: </span><span style={{ color: '#d4a76a' }}>{rollResult.current_otm}%</span></div>
                <div><span style={{ color: '#999', fontSize: 12 }}>当前Delta: </span><span style={{ color: '#1890ff' }}>{rollResult.current_delta?.toFixed(3)}</span></div>
                {rollResult.current_value != null && <div><span style={{ color: '#999', fontSize: 12 }}>当前价值: </span><span style={{ color: '#ff7875' }}>{rollResult.current_value}</span></div>}
                {rollResult.profit_pct != null && <div><span style={{ color: '#999', fontSize: 12 }}>已获利: </span><span style={{ color: rollResult.profit_pct >= 0 ? '#52c41a' : '#ff4d4f' }}>{rollResult.profit_pct}%</span></div>}
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

      {/* ====== P&L TAB ====== */}
      {activeTab === 'pnl' && (
        <div>
          <h3 style={{ color: '#d4a76a', marginBottom: 16 }}>P&L 盈亏图</h3>
          <p style={{ color: '#999', marginBottom: 16 }}>选择策略生成到期日盈亏图</p>

          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
            {[
              { key: 'covered_call', label: 'Covered Call', color: '#52c41a' },
              { key: 'csp', label: 'CSP', color: '#1890ff' },
              { key: 'credit_spread', label: 'Credit Spread', color: '#faad14' },
              { key: 'straddle', label: 'Straddle', color: '#722ed1' },
              { key: 'strangle', label: 'Strangle', color: '#eb2f96' },
              { key: 'iron_condor', label: 'Iron Condor', color: '#13c2c2' },
            ].map(s => (
              <button key={s.key}
                onClick={() => loadPnl(s.key)}
                disabled={pnlLoading || !connectionStatus?.connected}
                style={{ padding: '6px 14px', background: s.color, color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                {s.label}
              </button>
            ))}
          </div>

          {pnlLoading && <LoadingSpinner text="生成P&L图表..." />}

          {pnlData && !pnlData.error && pnlData.pnl && (
            <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333' }}>
              <h4 style={{ color: '#d4a76a', marginBottom: 4 }}>{pnlData.strategy_info?.strategy || '盈亏分析'}</h4>
              {pnlData.strategy_info?.description && (
                <p style={{ color: '#ccc', fontSize: 13, marginBottom: 12 }}>{pnlData.strategy_info.description}</p>
              )}

              <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                <div style={{ background: '#0d0d1a', padding: '8px 14px', borderRadius: 6 }}>
                  <span style={{ color: '#999', fontSize: 11 }}>最大盈利: </span>
                  <span style={{ color: '#52c41a', fontWeight: 700 }}>${pnlData.pnl.max_profit}</span>
                </div>
                <div style={{ background: '#0d0d1a', padding: '8px 14px', borderRadius: 6 }}>
                  <span style={{ color: '#999', fontSize: 11 }}>最大亏损: </span>
                  <span style={{ color: '#ff4d4f', fontWeight: 700 }}>${pnlData.pnl.max_loss}</span>
                </div>
                {(pnlData.pnl.breakevens || []).length > 0 && (
                  <div style={{ background: '#0d0d1a', padding: '8px 14px', borderRadius: 6 }}>
                    <span style={{ color: '#999', fontSize: 11 }}>盈亏平衡: </span>
                    <span style={{ color: '#faad14', fontWeight: 700 }}>{pnlData.pnl.breakevens.join(' / ')}</span>
                  </div>
                )}
              </div>

              <ReactECharts
                notMerge
                option={{
                  tooltip: {
                    trigger: 'axis',
                    formatter: (params: any) => {
                      const p = params[0]
                      return `标的价格: ${p.axisValue}<br/>P&L: <b style="color:${p.value >= 0 ? '#52c41a' : '#ff4d4f'}">$${p.value}</b>`
                    },
                  },
                  xAxis: {
                    type: 'category',
                    data: pnlData.pnl.prices,
                    axisLabel: { color: '#999', fontSize: 10, rotate: 45, interval: 19 },
                    axisLine: { lineStyle: { color: '#333' } },
                    name: '标的价格',
                    nameTextStyle: { color: '#999' },
                  },
                  yAxis: {
                    type: 'value',
                    axisLabel: { color: '#999', formatter: '${value}' },
                    splitLine: { lineStyle: { color: '#222' } },
                    name: 'P&L ($)',
                    nameTextStyle: { color: '#999' },
                  },
                  series: [{
                    type: 'line',
                    data: pnlData.pnl.pnl,
                    smooth: false,
                    lineStyle: { width: 2, color: '#1890ff' },
                    areaStyle: {
                      color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                          { offset: 0, color: 'rgba(82,196,26,0.25)' },
                          { offset: 0.5, color: 'rgba(255,255,255,0)' },
                          { offset: 1, color: 'rgba(255,77,79,0.25)' },
                        ],
                      },
                    },
                    markLine: {
                      silent: true,
                      data: [
                        { xAxis: pnlData.pnl.current_spot, lineStyle: { color: '#d4a76a', type: 'dashed', width: 2 }, label: { formatter: `现价 ${pnlData.pnl.current_spot}`, color: '#d4a76a', fontSize: 11 } },
                        ...(pnlData.pnl.breakevens || []).map((be: number) => ({
                          xAxis: be, lineStyle: { color: '#faad14', type: 'dotted' }, label: { formatter: `BE ${be}`, color: '#faad14', fontSize: 10 },
                        })),
                      ],
                    },
                    markPoint: {
                      data: [
                        { type: 'max', name: '最大盈利', itemStyle: { color: '#52c41a' }, label: { formatter: '${value}' } },
                        { type: 'min', name: '最大亏损', itemStyle: { color: '#ff4d4f' }, label: { formatter: '${value}' } },
                      ],
                    },
                  }],
                  grid: { left: 70, right: 30, top: 40, bottom: 60 },
                }}
                style={{ height: 400 }}
              />
            </div>
          )}
          {pnlData?.error && (
            <div style={{ padding: 12, background: '#2e1a1a', borderRadius: 8, border: '1px solid #ff4d4f' }}>
              <p style={{ color: '#ff4d4f', margin: 0 }}>{pnlData.error}</p>
            </div>
          )}
        </div>
      )}

      {/* ====== IV SURFACE TAB ====== */}
      {activeTab === 'iv_surface' && (
        <div>
          <h3 style={{ color: '#d4a76a', marginBottom: 16 }}>IV 曲面分析</h3>
          <p style={{ color: '#999', marginBottom: 16 }}>隐含波动率曲面、期限结构和偏斜分析</p>

          <button onClick={loadIvSurface} disabled={ivSurfaceLoading || !connectionStatus?.connected}
            style={{ marginBottom: 16, padding: '8px 24px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>
            {ivSurfaceLoading ? '加载中...' : '加载 IV 曲面'}
          </button>

          {ivSurfaceLoading && <LoadingSpinner text="构建IV曲面..." />}

          {ivSurface && !ivSurface.error && (
            <>
              {/* ATM Term Structure */}
              {ivSurface.atm_term_structure && ivSurface.atm_term_structure.length > 0 && (
                <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>ATM 期限结构 (IV vs DTE)</h4>
                  <ReactECharts
                    notMerge
                    option={{
                      tooltip: { trigger: 'axis', formatter: (params: any) => `DTE: ${params[0].axisValue}天<br/>IV: ${params[0].value}%` },
                      xAxis: {
                        type: 'category',
                        data: ivSurface.atm_term_structure.map((t: any) => t.dte),
                        axisLabel: { color: '#999', formatter: '{value}天' },
                        axisLine: { lineStyle: { color: '#333' } },
                        name: '到期天数',
                        nameTextStyle: { color: '#999' },
                      },
                      yAxis: {
                        type: 'value',
                        axisLabel: { color: '#999', formatter: '{value}%' },
                        splitLine: { lineStyle: { color: '#222' } },
                        name: 'IV (%)',
                        nameTextStyle: { color: '#999' },
                      },
                      series: [{
                        type: 'line',
                        data: ivSurface.atm_term_structure.map((t: any) => t.iv),
                        smooth: true,
                        lineStyle: { color: '#1890ff', width: 2 },
                        areaStyle: { color: 'rgba(24,144,255,0.15)' },
                        symbol: 'circle',
                        symbolSize: 8,
                        itemStyle: { color: '#1890ff' },
                      }],
                      grid: { left: 60, right: 30, top: 30, bottom: 50 },
                    }}
                    style={{ height: 300 }}
                  />
                </div>
              )}

              {/* IV Skew */}
              {ivSurface.skew && ivSurface.skew.length > 0 && (
                <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>IV 偏斜 (Skew) -- 近月合约</h4>
                  <ReactECharts
                    notMerge
                    option={{
                      tooltip: {
                        trigger: 'axis',
                        formatter: (params: any) => {
                          let s = `行权价: ${params[0].axisValue}<br/>`
                          params.forEach((p: any) => { s += `${p.seriesName}: ${p.value}%<br/>` })
                          return s
                        },
                      },
                      legend: { data: ['Put IV', 'Call IV'], textStyle: { color: '#ccc' }, top: 0 },
                      xAxis: {
                        type: 'category',
                        data: ivSurface.skew.map((s: any) => s.strike),
                        axisLabel: { color: '#999', rotate: 30, fontSize: 10 },
                        axisLine: { lineStyle: { color: '#333' } },
                        name: '行权价',
                        nameTextStyle: { color: '#999' },
                      },
                      yAxis: {
                        type: 'value',
                        axisLabel: { color: '#999', formatter: '{value}%' },
                        splitLine: { lineStyle: { color: '#222' } },
                        name: 'IV (%)',
                        nameTextStyle: { color: '#999' },
                      },
                      series: [
                        {
                          name: 'Put IV', type: 'line',
                          data: ivSurface.skew.map((s: any) => s.put_iv ?? null),
                          lineStyle: { color: '#52c41a', width: 2 },
                          symbol: 'circle', symbolSize: 6, itemStyle: { color: '#52c41a' },
                          connectNulls: true,
                        },
                        {
                          name: 'Call IV', type: 'line',
                          data: ivSurface.skew.map((s: any) => s.call_iv ?? null),
                          lineStyle: { color: '#1890ff', width: 2 },
                          symbol: 'diamond', symbolSize: 6, itemStyle: { color: '#1890ff' },
                          connectNulls: true,
                        },
                      ],
                      grid: { left: 60, right: 30, top: 40, bottom: 60 },
                    }}
                    style={{ height: 300 }}
                  />
                </div>
              )}

              {/* IV Surface Heatmap */}
              {ivSurface.surface && ivSurface.strikes && ivSurface.expiries && (
                <div style={{ background: '#1a1a2e', padding: 20, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 12 }}>IV 曲面热力图 (Put)</h4>
                  <ReactECharts
                    notMerge
                    option={{
                      tooltip: {
                        formatter: (params: any) => {
                          const [strikeIdx, expiryIdx] = params.data
                          const strike = ivSurface.strikes[strikeIdx]
                          const expiry = ivSurface.expiries[expiryIdx]
                          return `行权价: ${strike}<br/>到期: ${expiry}<br/>IV: ${params.data[2]}%`
                        },
                      },
                      xAxis: {
                        type: 'category',
                        data: ivSurface.strikes,
                        axisLabel: { color: '#999', fontSize: 10, rotate: 30 },
                        axisLine: { lineStyle: { color: '#333' } },
                        name: '行权价',
                        nameTextStyle: { color: '#999' },
                      },
                      yAxis: {
                        type: 'category',
                        data: ivSurface.expiries.map((e: string) => e.slice(5)),
                        axisLabel: { color: '#999', fontSize: 10 },
                        axisLine: { lineStyle: { color: '#333' } },
                        name: '到期日',
                        nameTextStyle: { color: '#999' },
                      },
                      visualMap: {
                        min: 0, max: 100,
                        calculable: true,
                        orient: 'vertical',
                        right: 0,
                        top: 'center',
                        inRange: { color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#fee090', '#fdae61', '#f46d43', '#d73027'] },
                        textStyle: { color: '#ccc' },
                      },
                      series: [{
                        type: 'heatmap',
                        data: (() => {
                          const data: [number, number, number][] = []
                          const putSurface = ivSurface.surface.put
                          if (putSurface) {
                            putSurface.forEach((row: (number | null)[], expiryIdx: number) => {
                              row.forEach((val: number | null, strikeIdx: number) => {
                                if (val != null) data.push([strikeIdx, expiryIdx, Math.round(val * 10) / 10])
                              })
                            })
                          }
                          return data
                        })(),
                        label: { show: false },
                        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } },
                      }],
                      grid: { left: 80, right: 80, top: 30, bottom: 60 },
                    }}
                    style={{ height: 400 }}
                  />
                </div>
              )}
            </>
          )}
          {ivSurface?.error && (
            <div style={{ padding: 12, background: '#2e1a1a', borderRadius: 8, border: '1px solid #ff4d4f' }}>
              <p style={{ color: '#ff4d4f', margin: 0 }}>{ivSurface.error}</p>
            </div>
          )}
        </div>
      )}

      {/* ====== SCREENING TAB ====== */}
      {activeTab === 'screening' && (
        <div>
          <h3 style={{ color: '#d4a76a', marginBottom: 16 }}>🔍 策略筛选 — Covered Call & Cash Secured Put</h3>
          <p style={{ color: '#999', marginBottom: 16, fontSize: 13 }}>
            扫描全部期权链，扣除手续费后筛选年化收益达标的机会。默认按被行权的保守情况计算。
          </p>

          {/* 参数设置 */}
          <div style={{ background: '#1a1a2e', padding: 16, borderRadius: 8, border: '1px solid #333', marginBottom: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
              <label style={{ color: '#ccc', fontSize: 13 }}>交易手续费 (HK$)
                <input type="number" value={screenTradeFee} onChange={e => setScreenTradeFee(e.target.value)} min="0" step="1"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>行权手续费 (HK$)
                <input type="number" value={screenExerciseFee} onChange={e => setScreenExerciseFee(e.target.value)} min="0" step="1"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>最低年化 (%)
                <input type="number" value={screenMinYield} onChange={e => setScreenMinYield(e.target.value)} min="0" step="1"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
              <label style={{ color: '#ccc', fontSize: 13 }}>最低OTM距离 (%)
                <input type="number" value={screenMinOtm} onChange={e => setScreenMinOtm(e.target.value)} min="0" step="1"
                  style={{ width: '100%', padding: '6px', background: '#0d0d1a', color: '#fff', border: '1px solid #444', borderRadius: 4, marginTop: 4 }} />
              </label>
            </div>
            <button onClick={runScreening} disabled={screenLoading}
              style={{ marginTop: 12, padding: '10px 28px', background: '#d4a76a', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 14 }}>
              {screenLoading ? '扫描中...' : `🔍 扫描 HK.${stockCode} 期权链`}
            </button>
          </div>

          {screenLoading && <LoadingSpinner text="正在扫描全部期权链，计算扣费后年化收益..." />}

          {/* 筛选结果 */}
          {screenResult && !screenResult.error && (
            <div>
              {/* 概览 */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 16 }}>
                <div style={{ background: '#1a1a2e', padding: 12, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 11 }}>标的现价</div>
                  <div style={{ color: '#d4a76a', fontSize: 20, fontWeight: 700 }}>{screenResult.spot_price}</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 12, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 11 }}>扫描合约数</div>
                  <div style={{ color: '#fff', fontSize: 20, fontWeight: 700 }}>{screenResult.total_scanned}</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 12, borderRadius: 8, border: '1px solid #52c41a' }}>
                  <div style={{ color: '#999', fontSize: 11 }}>通过筛选</div>
                  <div style={{ color: '#52c41a', fontSize: 20, fontWeight: 700 }}>{screenResult.passed_count}</div>
                </div>
                <div style={{ background: '#1a1a2e', padding: 12, borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ color: '#999', fontSize: 11 }}>手续费</div>
                  <div style={{ color: '#ff7875', fontSize: 14, fontWeight: 600 }}>交易${screenResult.trade_fee} + 行权${screenResult.exercise_fee}</div>
                </div>
              </div>

              {screenResult.results.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', background: '#1a1a2e', borderRadius: 8, border: '1px solid #333' }}>
                  <div style={{ fontSize: 16, color: '#999' }}>没有找到年化 ≥ {screenResult.min_yield}% 的策略</div>
                  <div style={{ fontSize: 13, color: '#666', marginTop: 8 }}>尝试降低年化要求或OTM距离</div>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #d4a76a' }}>
                        <th style={futuThStyle}>策略</th>
                        <th style={futuThStyle}>行权价</th>
                        <th style={futuThStyle}>权利金</th>
                        <th style={futuThStyle}>天数</th>
                        <th style={futuThStyle}>OTM%</th>
                        <th style={{ ...futuThStyle, color: '#52c41a' }}>扣费后年化</th>
                        <th style={futuThStyle}>扣费前年化</th>
                        <th style={futuThStyle}>净利润</th>
                        <th style={futuThStyle}>盈利概率</th>
                        <th style={futuThStyle}>IV</th>
                        <th style={futuThStyle}>Delta</th>
                        <th style={futuThStyle}>成交量</th>
                        <th style={futuThStyle}>价差%</th>
                        <th style={futuThStyle}>评分</th>
                      </tr>
                    </thead>
                    <tbody>
                      {screenResult.results.map((r: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid #333', background: i % 2 === 0 ? '#0d0d1a' : '#1a1a2e' }}>
                          <td style={futuTdStyle}>
                            <span style={{
                              display: 'inline-block', padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
                              background: r.strategy === 'cc' ? 'rgba(82,196,26,0.2)' : 'rgba(24,144,255,0.2)',
                              color: r.strategy === 'cc' ? '#52c41a' : '#1890ff',
                            }}>
                              {r.strategy === 'cc' ? 'CC' : 'CSP'}
                            </span>
                          </td>
                          <td style={{ ...futuTdStyle, fontWeight: 600 }}>{r.strike}</td>
                          <td style={futuTdStyle}>{r.premium}</td>
                          <td style={futuTdStyle}>{r.dte}</td>
                          <td style={{ ...futuTdStyle, color: r.otm_pct >= 5 ? '#52c41a' : '#faad14' }}>
                            {r.otm_pct > 0 ? '+' : ''}{r.otm_pct}%
                          </td>
                          <td style={{ ...futuTdStyle, color: '#52c41a', fontWeight: 700, fontSize: 15 }}>
                            {r.net_yield}%
                          </td>
                          <td style={{ ...futuTdStyle, color: '#666' }}>{r.gross_yield}%</td>
                          <td style={{ ...futuTdStyle, color: r.net_profit >= 0 ? '#52c41a' : '#ff4d4f' }}>
                            ${r.net_profit}
                          </td>
                          <td style={{ ...futuTdStyle, color: r.pop >= 70 ? '#52c41a' : r.pop >= 50 ? '#faad14' : '#ff4d4f' }}>
                            {r.pop}%
                          </td>
                          <td style={futuTdStyle}>{r.iv}%</td>
                          <td style={futuTdStyle}>{r.delta}</td>
                          <td style={{ ...futuTdStyle, color: r.volume > 100 ? '#52c41a' : '#999' }}>{r.volume}</td>
                          <td style={{ ...futuTdStyle, color: (r.spread_pct || 0) < 10 ? '#52c41a' : '#ff4d4f' }}>
                            {r.spread_pct?.toFixed(1) || '-'}%
                          </td>
                          <td style={{ ...futuTdStyle, color: '#d4a76a', fontWeight: 600 }}>{r.score}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 说明 */}
              <div style={{ marginTop: 16, padding: 12, background: '#1a1a2e', borderRadius: 8, border: '1px solid #333' }}>
                <p style={{ color: '#999', fontSize: 12, margin: 0 }}>
                  💡 <strong style={{ color: '#d4a76a' }}>CC</strong> = Covered Call（持有正股 + 卖Call），
                  <strong style={{ color: '#1890ff' }}>CSP</strong> = Cash Secured Put（卖Put + 准备现金）。
                  扣费后年化按<strong style={{ color: '#ff7875' }}>被行权</strong>的保守情况计算。
                  OTM ≥ 5% 为佳，成交量100+流动性较好，价差10%以内交易成本低。
                </p>
              </div>
            </div>
          )}

          {screenResult?.error && (
            <div style={{ padding: 12, background: '#2e1a1a', borderRadius: 8, border: '1px solid #ff4d4f' }}>
              <p style={{ color: '#ff4d4f', margin: 0 }}>{screenResult.error}</p>
            </div>
          )}
        </div>
      )}

      {/* 理性检查点 */}
      <RationalCheckpoint
        open={checkpointOpen}
        actionType={checkpointMeta.actionType}
        target={checkpointMeta.target}
        onPass={handlePass}
        onCancel={handleCancel}
      />
    </div>
  )
}

const futuThStyle: React.CSSProperties = {
  padding: '8px 10px', textAlign: 'left', fontWeight: 600, fontSize: 12, color: '#999', whiteSpace: 'nowrap',
}
const futuTdStyle: React.CSSProperties = {
  padding: '6px 10px', verticalAlign: 'middle', color: '#ccc',
}
