import { useState, useEffect, useCallback, Fragment } from 'react'
import axios from 'axios'
import { PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState, DataTable } from '../components/ui'
import type { Column } from '../components/ui'
import { useTradingInterceptor } from '../hooks/useTradingInterceptor'
import RationalCheckpoint from '../components/RationalCheckpoint'

const API_BASE = '/api/t-trading'

// ============================================================
// Types
// ============================================================

interface TIndicators {
  rsi: number
  kdj: { k: number; d: number; j: number; signal: string }
  macd: { dif: number; dea: number; hist: number; signal: string; divergence: string }
  bollinger: { upper: number; middle: number; lower: number; signal: string; position_pct: number; bandwidth_pct: number }
  vwap_deviation: number
  volume_ratio: number
  trend?: { trend: string; ma20: number; ma60: number; deviation_pct: number; filter_pass: boolean }
  buy_weight?: number
  sell_weight?: number
  round_trip_cost_pct?: number
  min_profit_threshold?: number
}

interface BacktestResult {
  valid: boolean
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  avg_win: number
  avg_loss: number
  profit_factor: number | string
  max_drawdown: number
  round_trip_cost_pct: number
  trade_log: { date: string; action: string; price: number; shares: number; pnl?: number; reason: string }[]
  backtest_period: string
  current_trend?: { trend: string; ma20: number; ma60: number; deviation_pct: number }
  cost_info?: { round_trip_cost_pct: number; market: string }
}

interface RiskItem {
  code: string
  name: string
  market: string
  t_ratio: number
  today_trades: number
  total_fee: number
  risk_level: string
  risk_reasons: string[]
}

interface TSignalItem {
  code: string
  name: string
  market: 'A' | 'HK' | 'US'
  current_price: number
  signal_type: 'buy' | 'sell' | 'hold'
  signal_strength: 'strong' | 'medium' | 'weak' | 'neutral'
  buy_point: number
  sell_point: number
  suggested_t_shares: number
  expected_profit_pct: number
  atr: number
  atr_pct: number
  indicators: TIndicators
  reasoning: string[]
}

interface CostAnalysis {
  per_share_cost: number
  is_negative: boolean
  original_cost: number
  cost_reduction: number
  cost_reduction_pct: number
  net_cost: number
  total_invested: number
  total_sold: number
  t_net_profit: number
  total_fee: number
  buy_t_count: number
  sell_t_count: number
  recovery_pct: number
  gap_to_negative: number
  negative_cost_label: string
}

interface Position {
  code: string
  name: string
  market: string
  total_shares: number
  base_shares: number
  t_shares: number
  avg_cost: number
  original_cost: number
  total_invested: number
  total_sold: number
  t_trades: any[]
  cost_analysis: CostAnalysis
}

interface PyramidOrder {
  level: number
  drop_pct: number
  target_price: number
  shares: number
  capital: number
  label: string
  new_avg_cost: number
}

// ============================================================
// Component
// ============================================================

export default function TTrading() {
  const [activeTab, setActiveTab] = useState<'signals' | 'position' | 'cost' | 'backtest' | 'risk' | 'philosophy'>('signals')

  // Signals state
  const [signals, setSignals] = useState<TSignalItem[]>([])
  const [signalsLoading, setSignalsLoading] = useState(false)
  const [signalSummary, setSignalSummary] = useState<any>({})
  const [filterMarket, setFilterMarket] = useState<'all' | 'A' | 'HK' | 'US'>('all')
  const [filterSignal, setFilterSignal] = useState<'all' | 'buy' | 'sell' | 'hold'>('all')
  const [expandedSignal, setExpandedSignal] = useState<string | null>(null)
  const [updateTime, setUpdateTime] = useState('')

  // Position state
  const [positions, setPositions] = useState<Position[]>([])
  const [posSummary, setPosSummary] = useState<any>({})
  const [showInitForm, setShowInitForm] = useState(false)
  const [initForm, setInitForm] = useState({ code: '', name: '', market: 'A', shares: '', cost_price: '' })
  const [showTradeForm, setShowTradeForm] = useState<string | null>(null)
  const [tradeForm, setTradeForm] = useState({ action: 'sell_t', shares: '', price: '', note: '' })

  // Pyramid state
  const [pyramidData, setPyramidData] = useState<any>(null)
  const [pyramidStock, setPyramidStock] = useState<string | null>(null)
  const [pyramidLoading, setPyramidLoading] = useState(false)

  // Philosophy state
  const [philosophy, setPhilosophy] = useState<any>(null)

  // 交易拦截器
  const { intercept, checkpointOpen, checkpointMeta, handlePass, handleCancel } = useTradingInterceptor()

  // Backtest state
  const [backtestData, setBacktestData] = useState<BacktestResult | null>(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [backtestForm, setBacktestForm] = useState({ code: '', market: 'A' })

  // Risk state
  const [riskData, setRiskData] = useState<any>(null)
  const [riskLoading, setRiskLoading] = useState(false)

  // ============================================================
  // Data Loading
  // ============================================================

  const loadSignals = useCallback(async () => {
    setSignalsLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/signals`, { params: { market: filterMarket } })
      setSignals(res.data.signals || [])
      setSignalSummary(res.data.summary || {})
      setUpdateTime(res.data.update_time || '')
    } catch (e) {
      console.error('加载做T信号失败:', e)
    } finally {
      setSignalsLoading(false)
    }
  }, [filterMarket])

  const loadPositions = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/position`)
      setPositions(res.data.positions || [])
      setPosSummary(res.data.summary || {})
    } catch (e) {
      console.error('加载仓位失败:', e)
    }
  }, [])

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('加载方法论失败:', e)
    }
  }, [])

  const loadBacktest = useCallback(async () => {
    if (!backtestForm.code.trim()) {
      alert('请输入股票代码')
      return
    }
    setBacktestLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/backtest/${backtestForm.code}`, {
        params: { market: backtestForm.market },
      })
      setBacktestData(res.data)
    } catch (e) {
      console.error('回测失败:', e)
      setBacktestData(null)
    } finally {
      setBacktestLoading(false)
    }
  }, [backtestForm])

  const loadRisk = useCallback(async () => {
    setRiskLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/risk-summary`)
      setRiskData(res.data)
    } catch (e) {
      console.error('加载风险数据失败:', e)
    } finally {
      setRiskLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'signals') loadSignals()
    if (activeTab === 'position' || activeTab === 'cost') loadPositions()
    if (activeTab === 'philosophy' && !philosophy) loadPhilosophy()
    if (activeTab === 'backtest') { /* user triggers manually */ }
    if (activeTab === 'risk') loadRisk()
  }, [activeTab, loadSignals, loadPositions, loadPhilosophy, loadRisk])

  // ============================================================
  // Handlers
  // ============================================================

  const doInitPosition = async () => {
    if (!initForm.code.trim() || !initForm.name.trim()) {
      alert('请填写股票代码和名称')
      return
    }
    if (!initForm.shares || Number(initForm.shares) <= 0) {
      alert('请填写有效的股数')
      return
    }
    if (!initForm.cost_price || Number(initForm.cost_price) <= 0) {
      alert('请填写有效的成本价')
      return
    }
    try {
      await axios.post(`${API_BASE}/position/init`, {
        code: initForm.code,
        name: initForm.name,
        market: initForm.market,
        shares: Number(initForm.shares),
        cost_price: Number(initForm.cost_price),
      })
      setShowInitForm(false)
      setInitForm({ code: '', name: '', market: 'A', shares: '', cost_price: '' })
      loadPositions()
    } catch (e: any) {
      alert(e.response?.data?.detail || '初始化失败')
    }
  }

  const handleInitPosition = () => {
    intercept(doInitPosition, {
      actionType: 'buy',
      target: initForm.name || initForm.code,
    })
  }

  const doExecuteTrade = async (code: string, market: string) => {
    if (!tradeForm.shares || Number(tradeForm.shares) <= 0) {
      alert('请填写有效的股数')
      return
    }
    if (!tradeForm.price || Number(tradeForm.price) <= 0) {
      alert('请填写有效的价格')
      return
    }
    try {
      const res = await axios.post(`${API_BASE}/execute`, {
        code,
        market,
        action: tradeForm.action,
        shares: Number(tradeForm.shares),
        price: Number(tradeForm.price),
        note: tradeForm.note,
      })
      alert(`${res.data.message}\n本次盈亏: ¥${res.data.trade_pnl ?? '-'}\n最新成本: ¥${res.data.position?.avg_cost ?? '-'}`)
      setShowTradeForm(null)
      setTradeForm({ action: 'sell_t', shares: '', price: '', note: '' })
      loadPositions()
    } catch (e: any) {
      alert(e.response?.data?.error || '交易失败')
    }
  }

  const handleExecuteTrade = (code: string, market: string) => {
    const posName = positions.find(p => p.code === code)?.name || code
    intercept(() => doExecuteTrade(code, market), {
      actionType: tradeForm.action === 'buy_t' ? 'buy' : 'sell',
      target: posName,
    })
  }

  const loadPyramid = async (code: string, market: string) => {
    if (pyramidStock === code) {
      setPyramidData(null)
      setPyramidStock(null)
      return
    }
    setPyramidLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/pyramid`, { params: { code, market, t_capital: 300000 } })
      setPyramidData(res.data)
      setPyramidStock(code)
    } catch (e) {
      console.error('加载金字塔方案失败:', e)
    } finally {
      setPyramidLoading(false)
    }
  }

  // ============================================================
  // Helpers
  // ============================================================

  const getSignalColor = (type: string) => {
    if (type === 'buy') return '#3fb950'
    if (type === 'sell') return '#f85149'
    return '#8b949e'
  }

  const getSignalText = (type: string) => {
    if (type === 'buy') return '买入T点'
    if (type === 'sell') return '卖出T点'
    return '观望'
  }

  const getStrengthColor = (strength: string) => {
    if (strength === 'strong') return '#3fb950'
    if (strength === 'medium') return '#58a6ff'
    if (strength === 'weak') return '#d29922'
    return '#8b949e'
  }

  const getStrengthText = (strength: string) => {
    if (strength === 'strong') return '强信号'
    if (strength === 'medium') return '中信号'
    if (strength === 'weak') return '弱信号'
    return '无信号'
  }

  const getMarketTag = (market: string) => {
    switch (market) {
      case 'A': return { text: 'A股', color: '#f85149' }
      case 'HK': return { text: '港股', color: '#d29922' }
      case 'US': return { text: '美股', color: '#58a6ff' }
      default: return { text: market, color: '#8b949e' }
    }
  }

  const getKdjColor = (signal: string) => {
    if (signal === 'golden_cross' || signal === 'oversold') return '#3fb950'
    if (signal === 'dead_cross' || signal === 'overbought') return '#f85149'
    return '#8b949e'
  }

  const getMacdColor = (signal: string, divergence: string) => {
    if (signal === 'golden_cross' || divergence === 'bottom') return '#3fb950'
    if (signal === 'dead_cross' || divergence === 'top') return '#f85149'
    return '#8b949e'
  }

  const filteredSignals = signals.filter(s => {
    if (filterSignal !== 'all' && s.signal_type !== filterSignal) return false
    return true
  })

  // ============================================================
  // Render
  // ============================================================

  return (
    <>
    <div className="cb-page">
      <PageSection title="金渐成做T交易系统" compact>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>三重确认 · ATR自适应 · 负成本持股</div>
      </PageSection>

      {/* Tabs */}
      <TabBar
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as typeof activeTab)}
        tabs={[
          { key: 'signals', label: '做T信号' },
          { key: 'position', label: '仓位管理' },
          { key: 'cost', label: '成本追踪' },
          { key: 'backtest', label: '回测验证' },
          { key: 'risk', label: '风险监控' },
          { key: 'philosophy', label: '做T方法论' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {/* ==================== Tab 1: 做T信号 ==================== */}
      {activeTab === 'signals' && (
        <div>
          {/* Filter Bar */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <select value={filterMarket} onChange={e => setFilterMarket(e.target.value as any)}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value="all">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
              <option value="US">美股</option>
            </select>
            <select value={filterSignal} onChange={e => setFilterSignal(e.target.value as any)}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value="all">全部信号</option>
              <option value="buy">买入信号</option>
              <option value="sell">卖出信号</option>
              <option value="hold">观望</option>
            </select>
            <button onClick={loadSignals}
              style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              扫描信号
            </button>
            {updateTime && (
              <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                更新: {updateTime}
              </span>
            )}
          </div>

          {/* Summary Cards */}
          <StatCardGroup columns={4} style={{ marginBottom: 16 }}>
            <StatCard label="买入信号" value={signalSummary.buy_signals || 0} color="#3fb950" />
            <StatCard label="卖出信号" value={signalSummary.sell_signals || 0} color="#f85149" />
            <StatCard label="强信号" value={signalSummary.strong_signals || 0} color="#58a6ff" />
            <StatCard label="总扫描" value={signalSummary.total || 0} />
          </StatCardGroup>

          {/* Signals Table */}
          {signalsLoading ? (
            <LoadingSpinner text="扫描做T信号中..." />
          ) : (
            <table className="arb-table">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>市场</th>
                  <th>价格</th>
                  <th>信号</th>
                  <th>强度</th>
                  <th>买入T点</th>
                  <th>卖出T点</th>
                  <th>做T股数</th>
                  <th>预期收益</th>
                  <th>ATR</th>
                </tr>
              </thead>
              <tbody>
                {filteredSignals.map(sig => {
                  const mkt = getMarketTag(sig.market)
                  const isExpanded = expandedSignal === sig.code
                  return (
                    <Fragment key={sig.code}>
                      <tr
                        onClick={() => setExpandedSignal(isExpanded ? null : sig.code)}
                        style={{ cursor: 'pointer' }}>
                        <td style={{ fontFamily: 'monospace' }}>{sig.code}</td>
                        <td>{sig.name}</td>
                        <td><span style={{ color: mkt.color, fontSize: 12, fontWeight: 600 }}>{mkt.text}</span></td>
                        <td>{sig.current_price?.toFixed(2)}</td>
                        <td>
                          <span style={{
                            color: getSignalColor(sig.signal_type), fontWeight: 700,
                            padding: '2px 8px', borderRadius: 10,
                            background: `${getSignalColor(sig.signal_type)}20`,
                          }}>
                            {getSignalText(sig.signal_type)}
                          </span>
                        </td>
                        <td>
                          <span style={{
                            color: getStrengthColor(sig.signal_strength), fontWeight: 600, fontSize: 12,
                            padding: '2px 6px', borderRadius: 8,
                            background: `${getStrengthColor(sig.signal_strength)}20`,
                          }}>
                            {getStrengthText(sig.signal_strength)}
                          </span>
                        </td>
                        <td style={{ color: '#3fb950' }}>{sig.buy_point?.toFixed(2)}</td>
                        <td style={{ color: '#f85149' }}>{sig.sell_point?.toFixed(2)}</td>
                        <td>{sig.suggested_t_shares}</td>
                        <td style={{ color: '#d29922' }}>{sig.expected_profit_pct}%</td>
                        <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{sig.atr} ({sig.atr_pct}%)</td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${sig.code}-detail`}>
                          <td colSpan={11} style={{ padding: '16px', background: 'var(--bg-secondary)' }}>
                            {/* Indicators Grid */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>RSI</div>
                                <div style={{ fontSize: 18, fontWeight: 700, color: sig.indicators.rsi < 30 ? '#3fb950' : sig.indicators.rsi > 70 ? '#f85149' : 'var(--text-primary)' }}>
                                  {sig.indicators.rsi}
                                </div>
                                <div style={{ fontSize: 11, color: sig.indicators.rsi < 30 ? '#3fb950' : sig.indicators.rsi > 70 ? '#f85149' : '#8b949e' }}>
                                  {sig.indicators.rsi < 30 ? '超卖' : sig.indicators.rsi > 70 ? '超买' : '中性'}
                                </div>
                              </div>
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>KDJ</div>
                                <div style={{ fontSize: 14, fontWeight: 600 }}>
                                  K:{sig.indicators.kdj.k} D:{sig.indicators.kdj.d} J:{sig.indicators.kdj.j}
                                </div>
                                <div style={{ fontSize: 11, color: getKdjColor(sig.indicators.kdj.signal) }}>
                                  {sig.indicators.kdj.signal === 'golden_cross' ? '金叉' :
                                   sig.indicators.kdj.signal === 'dead_cross' ? '死叉' :
                                   sig.indicators.kdj.signal === 'oversold' ? '超卖' :
                                   sig.indicators.kdj.signal === 'overbought' ? '超买' : '中性'}
                                </div>
                              </div>
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>MACD</div>
                                <div style={{ fontSize: 12, fontWeight: 600 }}>
                                  DIF:{sig.indicators.macd.dif} DEA:{sig.indicators.macd.dea}
                                </div>
                                <div style={{ fontSize: 11, color: getMacdColor(sig.indicators.macd.signal, sig.indicators.macd.divergence) }}>
                                  {sig.indicators.macd.divergence === 'bottom' ? '底背离' :
                                   sig.indicators.macd.divergence === 'top' ? '顶背离' :
                                   sig.indicators.macd.signal === 'golden_cross' ? '金叉' :
                                   sig.indicators.macd.signal === 'dead_cross' ? '死叉' : '中性'}
                                </div>
                              </div>
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>布林带</div>
                                <div style={{ fontSize: 12 }}>
                                  上:{sig.indicators.bollinger.upper} 中:{sig.indicators.bollinger.middle} 下:{sig.indicators.bollinger.lower}
                                </div>
                                <div style={{ fontSize: 11, color: sig.indicators.bollinger.position_pct < 20 ? '#3fb950' : sig.indicators.bollinger.position_pct > 80 ? '#f85149' : '#8b949e' }}>
                                  位置 {sig.indicators.bollinger.position_pct}%
                                </div>
                              </div>
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>VWAP偏离</div>
                                <div style={{ fontSize: 18, fontWeight: 700, color: sig.indicators.vwap_deviation < -2 ? '#3fb950' : sig.indicators.vwap_deviation > 2 ? '#f85149' : 'var(--text-primary)' }}>
                                  {sig.indicators.vwap_deviation}%
                                </div>
                              </div>
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>量比</div>
                                <div style={{ fontSize: 18, fontWeight: 700, color: sig.indicators.volume_ratio > 1.5 ? '#d29922' : 'var(--text-primary)' }}>
                                  {sig.indicators.volume_ratio}
                                </div>
                              </div>
                            </div>

                            {/* Trend & Weighted Score Row */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                              {sig.indicators.trend && (
                                <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>趋势过滤器</div>
                                  <div style={{ fontSize: 14, fontWeight: 700, color: sig.indicators.trend.trend === 'uptrend' ? '#3fb950' : sig.indicators.trend.trend === 'downtrend' ? '#f85149' : '#d29922' }}>
                                    {sig.indicators.trend.trend === 'uptrend' ? '上升趋势' : sig.indicators.trend.trend === 'downtrend' ? '下降趋势' : '震荡'}
                                  </div>
                                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                    MA20:{sig.indicators.trend.ma20} MA60:{sig.indicators.trend.ma60}
                                  </div>
                                </div>
                              )}
                              <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>加权评分</div>
                                <div style={{ display: 'flex', gap: 12 }}>
                                  <div>
                                    <span style={{ fontSize: 11, color: '#3fb950' }}>买入点 </span>
                                    <span style={{ fontSize: 18, fontWeight: 700, color: '#3fb950' }}>{sig.buy_point?.toFixed(2)}</span>
                                  </div>
                                  <div>
                                    <span style={{ fontSize: 11, color: '#f85149' }}>卖出点 </span>
                                    <span style={{ fontSize: 18, fontWeight: 700, color: '#f85149' }}>{sig.sell_point?.toFixed(2)}</span>
                                  </div>
                                </div>
                              </div>
                              {sig.indicators.round_trip_cost_pct !== undefined && (
                                <div style={{ padding: 10, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>交易成本</div>
                                  <div style={{ fontSize: 14, fontWeight: 700, color: '#d29922' }}>
                                    {sig.indicators.round_trip_cost_pct}%
                                  </div>
                                  <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                    最低利润: {sig.indicators.min_profit_threshold}
                                  </div>
                                </div>
                              )}
                            </div>
                            {/* Reasoning */}
                            <div style={{ padding: 10, background: 'rgba(88,166,255,0.08)', borderRadius: 6, borderLeft: '3px solid #58a6ff' }}>
                              <div style={{ fontSize: 12, fontWeight: 600, color: '#58a6ff', marginBottom: 4 }}>信号依据</div>
                              {sig.reasoning.map((r, i) => (
                                <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 2 }}>{r}</div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ==================== Tab 2: 仓位管理 ==================== */}
      {activeTab === 'position' && (
        <div>
          {/* Action Bar */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            <button onClick={() => setShowInitForm(!showInitForm)}
              style={{ padding: '6px 16px', borderRadius: 6, background: '#3fb950', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              + 初始化持仓
            </button>
          </div>

          {/* Init Form */}
          {showInitForm && (
            <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 16, border: '1px solid var(--border-primary)' }}>
              <h4 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>初始化持仓（自动分层：7成底仓 + 3成做T仓）</h4>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <input placeholder="股票代码" value={initForm.code} onChange={e => setInitForm({...initForm, code: e.target.value})}
                  style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 100 }} />
                <input placeholder="股票名称" value={initForm.name} onChange={e => setInitForm({...initForm, name: e.target.value})}
                  style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 120 }} />
                <select value={initForm.market} onChange={e => setInitForm({...initForm, market: e.target.value})}
                  style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
                  <option value="A">A股</option>
                  <option value="HK">港股</option>
                  <option value="US">美股</option>
                </select>
                <input placeholder="总股数" type="number" value={initForm.shares} onChange={e => setInitForm({...initForm, shares: e.target.value})}
                  style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 100 }} />
                <input placeholder="成本价" type="number" step="0.01" value={initForm.cost_price} onChange={e => setInitForm({...initForm, cost_price: e.target.value})}
                  style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 100 }} />
                <button onClick={handleInitPosition}
                  style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                  确认初始化
                </button>
              </div>
            </div>
          )}

          {/* Positions */}
          {positions.length === 0 ? (
            <EmptyState title="暂无持仓记录" description="点击「初始化持仓」开始" />
          ) : (
            <div>
              {/* Summary */}
              <StatCardGroup columns={4} style={{ marginBottom: 16 }}>
                <StatCard label="总持仓" value={`${posSummary.total_positions || 0} 只`} />
                <StatCard label="累计投入" value={`¥${(posSummary.total_invested || 0).toLocaleString()}`} />
                <StatCard label="累计回收" value={`¥${(posSummary.total_sold || 0).toLocaleString()}`} color="#3fb950" />
                <StatCard label="负成本股票" value={`${posSummary.negative_cost_count || 0} 只`} color="#58a6ff" />
              </StatCardGroup>

              {/* Position Cards */}
              {positions.map(pos => {
                const mkt = getMarketTag(pos.market)
                return (
                  <div key={`${pos.market}_${pos.code}`} style={{
                    background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 12,
                    border: `1px solid ${pos.cost_analysis.is_negative ? '#3fb950' : 'var(--border-primary)'}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <div>
                        <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{pos.code}</span>
                        <span style={{ fontWeight: 600, marginRight: 8 }}>{pos.name}</span>
                        <span style={{ color: mkt.color, fontSize: 12, fontWeight: 600 }}>{mkt.text}</span>
                        {pos.cost_analysis.is_negative && (
                          <span style={{ marginLeft: 8, color: '#3fb950', fontSize: 12, fontWeight: 600 }}>✓ 负成本</span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button onClick={() => {
                          setShowTradeForm(showTradeForm === pos.code ? null : pos.code)
                          setTradeForm({ ...tradeForm, price: String(pos.avg_cost) })
                        }}
                          style={{ padding: '4px 12px', borderRadius: 4, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 12 }}>
                          做T操作
                        </button>
                        <button onClick={() => loadPyramid(pos.code, pos.market)}
                          style={{ padding: '4px 12px', borderRadius: 4, background: '#d29922', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 12 }}>
                          金字塔方案
                        </button>
                      </div>
                    </div>

                    {/* Position Stats */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8, fontSize: 13 }}>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>总持仓: </span>
                        <span style={{ fontWeight: 600 }}>{pos.total_shares}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>底仓: </span>
                        <span style={{ fontWeight: 600, color: '#58a6ff' }}>{pos.base_shares}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>做T仓: </span>
                        <span style={{ fontWeight: 600, color: '#d29922' }}>{pos.t_shares}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>当前成本: </span>
                        <span style={{ fontWeight: 600, color: pos.cost_analysis.is_negative ? '#3fb950' : 'var(--text-primary)' }}>
                          ¥{pos.avg_cost.toFixed(2)}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>初始成本: </span>
                        <span style={{ fontWeight: 600 }}>¥{pos.cost_analysis.original_cost.toFixed(2)}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>成本降幅: </span>
                        <span style={{ fontWeight: 600, color: '#3fb950' }}>{pos.cost_analysis.cost_reduction_pct}%</span>
                      </div>
                    </div>

                    {/* Recovery Progress Bar */}
                    <div style={{ marginTop: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                        <span>做T回收进度</span>
                        <span>{pos.cost_analysis.recovery_pct}%</span>
                      </div>
                      <div style={{ height: 6, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', borderRadius: 3,
                          width: `${Math.min(pos.cost_analysis.recovery_pct, 100)}%`,
                          background: pos.cost_analysis.is_negative
                            ? 'linear-gradient(90deg, #3fb950, #2ea043)'
                            : 'linear-gradient(90deg, #58a6ff, #388bfd)',
                        }} />
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                        {pos.cost_analysis.negative_cost_label}
                      </div>
                    </div>

                    {/* Trade Form */}
                    {showTradeForm === pos.code && (
                      <div style={{ marginTop: 12, padding: 12, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                          <select value={tradeForm.action} onChange={e => setTradeForm({...tradeForm, action: e.target.value})}
                            style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
                            <option value="buy_t">买入做T（加仓）</option>
                            <option value="sell_t">卖出做T（减仓）</option>
                          </select>
                          <input placeholder="股数" type="number" value={tradeForm.shares} onChange={e => setTradeForm({...tradeForm, shares: e.target.value})}
                            style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 80 }} />
                          <input placeholder="价格" type="number" step="0.01" value={tradeForm.price} onChange={e => setTradeForm({...tradeForm, price: e.target.value})}
                            style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 100 }} />
                          <input placeholder="备注" value={tradeForm.note} onChange={e => setTradeForm({...tradeForm, note: e.target.value})}
                            style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 150 }} />
                          <button onClick={() => handleExecuteTrade(pos.code, pos.market)}
                            style={{ padding: '6px 16px', borderRadius: 6, background: tradeForm.action === 'sell_t' ? '#f85149' : '#3fb950', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                            确认{tradeForm.action === 'sell_t' ? '卖出' : '买入'}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Pyramid Orders */}
                    {pyramidStock === pos.code && pyramidData && pyramidData.current_price && (
                      <div style={{ marginTop: 12, padding: 12, background: 'var(--bg-primary)', borderRadius: 6, border: '1px solid var(--border-primary)' }}>
                        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#d29922' }}>金字塔加仓方案</div>
                        <table style={{ width: '100%', fontSize: 12 }}>
                          <thead>
                            <tr style={{ color: 'var(--text-secondary)' }}>
                              <th style={{ textAlign: 'left', padding: '4px 8px' }}>下跌幅度</th>
                              <th style={{ textAlign: 'left', padding: '4px 8px' }}>目标价</th>
                              <th style={{ textAlign: 'left', padding: '4px 8px' }}>买入股数</th>
                              <th style={{ textAlign: 'left', padding: '4px 8px' }}>投入资金</th>
                              <th style={{ textAlign: 'left', padding: '4px 8px' }}>新均价</th>
                              <th style={{ textAlign: 'left', padding: '4px 8px' }}>标签</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pyramidData.orders?.map((order: PyramidOrder) => (
                              <tr key={order.level}>
                                <td style={{ padding: '4px 8px', color: '#f85149' }}>-{order.drop_pct}%</td>
                                <td style={{ padding: '4px 8px' }}>¥{order.target_price}</td>
                                <td style={{ padding: '4px 8px' }}>{order.shares}</td>
                                <td style={{ padding: '4px 8px' }}>¥{order.capital.toLocaleString()}</td>
                                <td style={{ padding: '4px 8px' }}>¥{order.new_avg_cost}</td>
                                <td style={{ padding: '4px 8px', color: '#d29922' }}>{order.label}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ==================== Tab 3: 成本追踪 ==================== */}
      {activeTab === 'cost' && (
        <div>
          {positions.length === 0 ? (
            <EmptyState title="暂无持仓记录" />
          ) : (
            <div>
              <h3 style={{ color: 'var(--text-primary)', marginBottom: 16 }}>负成本持股进度</h3>
              {[...positions]
                .sort((a, b) => b.cost_analysis.recovery_pct - a.cost_analysis.recovery_pct)
                .map(pos => {
                  const mkt = getMarketTag(pos.market)
                  return (
                    <div key={`${pos.market}_${pos.code}`} style={{
                      background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 12,
                      border: `1px solid ${pos.cost_analysis.is_negative ? '#3fb950' : 'var(--border-primary)'}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div>
                          <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{pos.code}</span>
                          <span style={{ fontWeight: 600, marginRight: 8 }}>{pos.name}</span>
                          <span style={{ color: mkt.color, fontSize: 12 }}>{mkt.text}</span>
                        </div>
                        <div style={{
                          padding: '4px 12px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                          background: pos.cost_analysis.is_negative ? '#3fb95020' : '#58a6ff20',
                          color: pos.cost_analysis.is_negative ? '#3fb950' : '#58a6ff',
                        }}>
                          {pos.cost_analysis.is_negative ? '✓ 已负成本' : `回收 ${pos.cost_analysis.recovery_pct}%`}
                        </div>
                      </div>

                      <StatCardGroup columns={4} style={{ marginBottom: 12 }}>
                        <StatCard label="初始成本" value={`¥${pos.cost_analysis.original_cost.toFixed(2)}`} />
                        <StatCard label="当前成本" value={`¥${pos.avg_cost.toFixed(2)}`} color={pos.cost_analysis.is_negative ? '#3fb950' : undefined} />
                        <StatCard label="做T净收益" value={`¥${pos.cost_analysis.t_net_profit.toLocaleString()}`} color={pos.cost_analysis.t_net_profit >= 0 ? '#3fb950' : '#f85149'} />
                        <StatCard label="手续费累计" value={`¥${pos.cost_analysis.total_fee}`} color="#d29922" />
                      </StatCardGroup>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                        <div>买入次数: {pos.cost_analysis.buy_t_count}</div>
                        <div>卖出次数: {pos.cost_analysis.sell_t_count}</div>
                        <div>净成本: ¥{pos.cost_analysis.net_cost.toLocaleString()}</div>
                      </div>

                      {/* Progress bar */}
                      <div style={{ marginTop: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                          <span>回收进度</span>
                          <span>{pos.cost_analysis.recovery_pct}%</span>
                        </div>
                        <div style={{ height: 8, background: 'var(--bg-primary)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', borderRadius: 4,
                            width: `${Math.min(pos.cost_analysis.recovery_pct, 100)}%`,
                            background: pos.cost_analysis.is_negative
                              ? 'linear-gradient(90deg, #3fb950, #2ea043)'
                              : pos.cost_analysis.recovery_pct > 80
                                ? 'linear-gradient(90deg, #d29922, #e3b341)'
                                : 'linear-gradient(90deg, #58a6ff, #388bfd)',
                            transition: 'width 0.5s ease',
                          }} />
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                          {pos.cost_analysis.negative_cost_label}
                        </div>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      )}

      {/* ==================== Tab 4: 回测验证 ==================== */}
      {activeTab === 'backtest' && (
        <div>
          <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 16, border: '1px solid var(--border-primary)' }}>
            <h4 style={{ margin: '0 0 12px', color: 'var(--text-primary)' }}>历史回测验证</h4>
            <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>
              使用最近60个交易日数据模拟做T策略，验证信号有效性。回测包含滑点和手续费。
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <input placeholder="股票代码" value={backtestForm.code} onChange={e => setBacktestForm({...backtestForm, code: e.target.value})}
                style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 120 }} />
              <select value={backtestForm.market} onChange={e => setBacktestForm({...backtestForm, market: e.target.value})}
                style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
                <option value="A">A股</option>
                <option value="HK">港股</option>
                <option value="US">美股</option>
              </select>
              <button onClick={loadBacktest} disabled={backtestLoading}
                style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                {backtestLoading ? '回测中...' : '开始回测'}
              </button>
            </div>
          </div>

          {backtestData && backtestData.valid && (
            <div>
              <StatCardGroup columns={4} style={{ marginBottom: 16 }}>
                <StatCard label="胜率" value={`${backtestData.win_rate}%`} color={backtestData.win_rate > 50 ? '#3fb950' : '#f85149'} />
                <StatCard label="总盈亏" value={`¥${backtestData.total_pnl.toLocaleString()}`} color={backtestData.total_pnl >= 0 ? '#3fb950' : '#f85149'} />
                <StatCard label="盈亏比" value={String(backtestData.profit_factor)} color={Number(backtestData.profit_factor) > 1 ? '#3fb950' : '#f85149'} />
                <StatCard label="最大回撤" value={`¥${backtestData.max_drawdown.toLocaleString()}`} color="#f85149" />
              </StatCardGroup>

              <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 16, border: '1px solid var(--border-primary)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, fontSize: 13 }}>
                  <div><span style={{ color: 'var(--text-secondary)' }}>回测区间: </span><span style={{ fontWeight: 600 }}>{backtestData.backtest_period}</span></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>总交易次数: </span><span style={{ fontWeight: 600 }}>{backtestData.total_trades}</span></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>Round-trip成本: </span><span style={{ fontWeight: 600, color: '#d29922' }}>{backtestData.round_trip_cost_pct}%</span></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>盈利次数: </span><span style={{ fontWeight: 600, color: '#3fb950' }}>{backtestData.winning_trades}</span></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>亏损次数: </span><span style={{ fontWeight: 600, color: '#f85149' }}>{backtestData.losing_trades}</span></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>平均盈利: </span><span style={{ fontWeight: 600, color: '#3fb950' }}>¥{backtestData.avg_win}</span></div>
                </div>
              </div>

              {backtestData.current_trend && (
                <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 16, border: '1px solid var(--border-primary)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>当前趋势分析</div>
                  <div style={{ display: 'flex', gap: 16, fontSize: 13 }}>
                    <span>
                      趋势: <span style={{
                        fontWeight: 700,
                        color: backtestData.current_trend.trend === 'uptrend' ? '#3fb950' :
                               backtestData.current_trend.trend === 'downtrend' ? '#f85149' : '#d29922'
                      }}>
                        {backtestData.current_trend.trend === 'uptrend' ? '上升' :
                         backtestData.current_trend.trend === 'downtrend' ? '下降' : '震荡'}
                      </span>
                    </span>
                    <span>MA20: {backtestData.current_trend.ma20}</span>
                    <span>MA60: {backtestData.current_trend.ma60}</span>
                    <span>偏离度: {backtestData.current_trend.deviation_pct}%</span>
                  </div>
                </div>
              )}

              {backtestData.trade_log && backtestData.trade_log.length > 0 && (
                <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, border: '1px solid var(--border-primary)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>交易日志（最近10笔）</div>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ color: 'var(--text-secondary)' }}>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>日期</th>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>操作</th>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>价格</th>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>股数</th>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>盈亏</th>
                        <th style={{ textAlign: 'left', padding: '4px 8px' }}>原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {backtestData.trade_log.map((t, i) => (
                        <tr key={i}>
                          <td style={{ padding: '4px 8px' }}>{t.date}</td>
                          <td style={{ padding: '4px 8px', color: t.action === 'buy' ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                            {t.action === 'buy' ? '买入' : '卖出'}
                          </td>
                          <td style={{ padding: '4px 8px' }}>¥{t.price.toFixed(2)}</td>
                          <td style={{ padding: '4px 8px' }}>{t.shares}</td>
                          <td style={{ padding: '4px 8px', color: (t.pnl || 0) >= 0 ? '#3fb950' : '#f85149' }}>
                            {t.pnl !== undefined ? `¥${t.pnl}` : '-'}
                          </td>
                          <td style={{ padding: '4px 8px', color: 'var(--text-secondary)' }}>{t.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {backtestData && !backtestData.valid && (
            <EmptyState title="回测数据不足" description="需要至少60个交易日数据" />
          )}
        </div>
      )}

      {/* ==================== Tab 5: 风险监控 ==================== */}
      {activeTab === 'risk' && (
        <div>
          {riskLoading ? (
            <LoadingSpinner text="加载风险数据..." />
          ) : riskData ? (
            <div>
              {/* Overall Risk */}
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 16,
                border: `2px solid ${riskData.overall.risk_level === 'high' ? '#f85149' : riskData.overall.risk_level === 'medium' ? '#d29922' : '#3fb950'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <h4 style={{ margin: 0, color: 'var(--text-primary)' }}>整体风险评估</h4>
                  <span style={{
                    padding: '4px 12px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                    background: riskData.overall.risk_level === 'high' ? '#f8514920' : riskData.overall.risk_level === 'medium' ? '#d2992220' : '#3fb95020',
                    color: riskData.overall.risk_level === 'high' ? '#f85149' : riskData.overall.risk_level === 'medium' ? '#d29922' : '#3fb950',
                  }}>
                    {riskData.overall.risk_level === 'high' ? '高风险' : riskData.overall.risk_level === 'medium' ? '中风险' : '低风险'}
                  </span>
                </div>
                <StatCardGroup columns={3} style={{ marginBottom: 0 }}>
                  <StatCard label="总持仓市值" value={`¥${riskData.overall.total_exposure.toLocaleString()}`} />
                  <StatCard label="做T仓市值" value={`¥${riskData.overall.t_exposure.toLocaleString()}`} color="#d29922" />
                  <StatCard label="做T仓占比" value={`${riskData.overall.t_ratio}%`}
                    color={riskData.overall.t_ratio > 40 ? '#f85149' : riskData.overall.t_ratio > 30 ? '#d29922' : '#3fb950'} />
                </StatCardGroup>
              </div>

              {/* Rules */}
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 16, border: '1px solid var(--border-primary)' }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>风控规则</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                  <div>每日最大交易: {riskData.rules.max_daily_trades}次</div>
                  <div>做T仓安全线: {riskData.rules.max_t_ratio}%</div>
                  <div>A股滑点: {(riskData.rules.slippage_model.A * 100).toFixed(2)}%</div>
                </div>
              </div>

              {/* Per-position Risk */}
              {riskData.positions.length > 0 ? (
                <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, border: '1px solid var(--border-primary)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>持仓风险明细</div>
                  <table style={{ width: '100%', fontSize: 12 }}>
                    <thead>
                      <tr style={{ color: 'var(--text-secondary)' }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>代码</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>名称</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>做T仓占比</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>今日交易</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>累计手续费</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>风险等级</th>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>风险原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {riskData.positions.map((item: RiskItem) => (
                        <tr key={item.code}>
                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{item.code}</td>
                          <td style={{ padding: '6px 8px' }}>{item.name}</td>
                          <td style={{ padding: '6px 8px', color: item.t_ratio > 40 ? '#f85149' : item.t_ratio > 30 ? '#d29922' : '#3fb950' }}>
                            {item.t_ratio}%
                          </td>
                          <td style={{ padding: '6px 8px', color: item.today_trades >= riskData.rules.max_daily_trades ? '#f85149' : 'var(--text-primary)' }}>
                            {item.today_trades}
                          </td>
                          <td style={{ padding: '6px 8px', color: '#d29922' }}>¥{item.total_fee}</td>
                          <td style={{ padding: '6px 8px' }}>
                            <span style={{
                              padding: '2px 8px', borderRadius: 8, fontSize: 11, fontWeight: 600,
                              background: item.risk_level === 'high' ? '#f8514920' : item.risk_level === 'medium' ? '#d2992220' : '#3fb95020',
                              color: item.risk_level === 'high' ? '#f85149' : item.risk_level === 'medium' ? '#d29922' : '#3fb950',
                            }}>
                              {item.risk_level === 'high' ? '高' : item.risk_level === 'medium' ? '中' : '低'}
                            </span>
                          </td>
                          <td style={{ padding: '6px 8px', color: '#f85149', fontSize: 11 }}>
                            {item.risk_reasons.join('; ') || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="暂无持仓风险数据" description="请先初始化持仓" />
              )}
            </div>
          ) : (
            <EmptyState title="暂无风险数据" description="点击「风险监控」标签加载" />
          )}
        </div>
      )}

      {/* ==================== Tab 6: 做T方法论 ==================== */}
      {activeTab === 'philosophy' && philosophy && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">核心原则</div>
              <div className="note-value" style={{ fontSize: 14, lineHeight: 1.6 }}>
                {philosophy.core_principle}
              </div>
            </div>
          </div>

          {philosophy.methodology?.map((dim: any, i: number) => (
            <div key={i} style={{
              background: 'var(--bg-secondary)', borderRadius: 8, padding: 16, marginBottom: 12,
              border: '1px solid var(--border-primary)',
            }}>
              <h4 style={{ color: 'var(--text-primary)', margin: '0 0 8px' }}>{dim.dimension}</h4>
              <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13 }}>{dim.description}</p>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {dim.rules?.map((rule: string, j: number) => (
                  <li key={j} style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 4 }}>{rule}</li>
                ))}
              </ul>
              {dim.key_insight && (
                <div style={{
                  marginTop: 8, padding: '8px 12px',
                  background: 'rgba(88,166,255,0.1)', borderRadius: 6,
                  borderLeft: '3px solid #58a6ff', color: '#58a6ff',
                  fontSize: 13, fontStyle: 'italic',
                }}>
                  "{dim.key_insight}"
                </div>
              )}
            </div>
          ))}

          {/* Risk Warnings */}
          <div style={{
            background: 'rgba(248,81,73,0.08)', borderRadius: 8, padding: 16,
            border: '1px solid rgba(248,81,73,0.2)',
          }}>
            <h4 style={{ color: '#f85149', margin: '0 0 8px' }}>⚠️ 风险提示</h4>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {philosophy.risk_warnings?.map((w: string, i: number) => (
                <li key={i} style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 4 }}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
    <RationalCheckpoint
      open={checkpointOpen}
      actionType={checkpointMeta.actionType}
      target={checkpointMeta.target}
      onPass={handlePass}
      onCancel={handleCancel}
    />
    </>
  )
}
