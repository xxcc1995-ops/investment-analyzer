import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from '../lib/ECharts'

const API_BASE = '/api'

interface DimensionResult {
  score: number
  max: number
  signals: string[]
  detail: string
}

interface AntiFakeCheck {
  type: string
  severity: 'high' | 'medium' | 'low'
  message: string
}

interface MarketRegime {
  regime: string
  adx_value: number
  di_spread: number
  trend_direction: string
  confidence: string
}

interface WeinsteinStage {
  stage: number
  stage_name: string
  confidence: number
  signals: string[]
  ma30_slope: number
  price_vs_ma30: number
}

interface RiskManagement {
  atr: number
  atr_pct: number
  volatility_level: string
  stop_loss: { tight: number; normal: number; wide: number }
  position_sizing: { risk_1pct_shares: number; risk_2pct_shares: number; risk_1pct_amount: number; risk_2pct_amount: number; suggested_pct: string }
  risk_reward: { target_1r: number; target_2r: number; target_3r: number }
  signals: string[]
}

interface TimeframeAlignment {
  aligned: boolean
  conflict: boolean
  alignment_score: number
  alignment_signals: string[]
  weekly_verdict: string
  weekly_score: number
}

interface BacktestSignal {
  date: string
  score: number
  verdict: string
  price_at_signal: number
  returns: { '5d': number | null; '10d': number | null; '20d': number | null; '60d': number | null }
}

interface BacktestResult {
  signals: BacktestSignal[]
  stats: {
    total_signals: number
    win_rate_20d: number
    avg_return_20d: number
    max_return_20d: number
    min_return_20d: number
    sharpe_like: number
  }
  code: string
}

interface RightSideResult {
  code: string
  verdict: string
  score: number
  dimensions: {
    ma: DimensionResult
    macd: DimensionResult
    volume: DimensionResult
    pattern: DimensionResult
    rsi_kdj: DimensionResult
    new_indicators: DimensionResult
  }
  anti_fake_checks: AntiFakeCheck[]
  market_regime: MarketRegime
  weinstein_stage: WeinsteinStage
  risk_management: RiskManagement
  timeframe_alignment: TimeframeAlignment
  weekly_dimensions: Record<string, DimensionResult> | null
  weekly_score: number
  weekly_verdict: string
  dynamic_weights: Record<string, number>
  chart_data: {
    dates: string[]
    kline: [string, number, number, number, number][]
    ma: { ma5: (number|null)[]; ma10: (number|null)[]; ma20: (number|null)[]; ma60: (number|null)[]; ma120: (number|null)[] }
    macd: { dif: number[]; dea: number[]; histogram: number[] }
    volume: { date: string; volume: number; color: string }[]
    bollinger: { upper: (number|null)[]; middle: (number|null)[]; lower: (number|null)[] }
    adx: { adx: (number|null)[]; plus_di: (number|null)[]; minus_di: (number|null)[] }
    cci: (number|null)[]
    obv: { obv: number[]; obv_ma20: (number|null)[] }
    sar: { sar: (number|null)[]; is_long: boolean[] }
  }
  update_time: string
  error?: string
}

interface SearchResult {
  code: string
  name: string
}

export default function RightSideTrading() {
  const [stockCode, setStockCode] = useState('')
  const [stockSearch, setStockSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const [result, setResult] = useState<RightSideResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expandedDim, setExpandedDim] = useState<string | null>(null)
  const [showBollinger, setShowBollinger] = useState(false)
  const [backtest, setBacktest] = useState<BacktestResult | null>(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'analysis' | 'backtest'>('analysis')

  const handleSearch = useCallback(async (keyword: string) => {
    if (!keyword.trim()) { setSearchResults([]); return }
    try {
      const res = await axios.get(`${API_BASE}/stocks/search`, { params: { keyword } })
      setSearchResults(res.data?.results || [])
    } catch { setSearchResults([]) }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => { if (stockSearch) handleSearch(stockSearch) }, 300)
    return () => clearTimeout(timer)
  }, [stockSearch, handleSearch])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) setShowSearch(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectStock = (code: string) => {
    setStockCode(code)
    setStockSearch('')
    setShowSearch(false)
    setBacktest(null)
    loadAnalysis(code)
  }

  const loadAnalysis = async (code: string) => {
    if (!code) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await axios.get(`${API_BASE}/right-side/${code}`)
      setResult(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '分析失败')
    } finally {
      setLoading(false)
    }
  }

  const loadBacktest = async () => {
    if (!stockCode) return
    setBacktestLoading(true)
    setBacktest(null)
    try {
      const res = await axios.get(`${API_BASE}/right-side/${stockCode}/backtest`)
      setBacktest(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '回测失败')
    } finally {
      setBacktestLoading(false)
    }
  }

  const getVerdictStyle = (verdict: string) => {
    switch (verdict) {
      case '右侧确认': return { bg: '#16a34a', icon: '✓', text: '#fff' }
      case '疑似右侧': return { bg: '#ca8a04', icon: '⚠', text: '#fff' }
      case '非右侧': return { bg: '#6b7280', icon: '—', text: '#fff' }
      case '左侧下跌': return { bg: '#dc2626', icon: '↓', text: '#fff' }
      default: return { bg: '#374151', icon: '?', text: '#fff' }
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return '#dc2626'
      case 'medium': return '#ca8a04'
      default: return '#3b82f6'
    }
  }

  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'trending': return '#16a34a'
      case 'developing': return '#ca8a04'
      case 'ranging': return '#dc2626'
      default: return '#6b7280'
    }
  }

  const getStageColor = (stage: number) => {
    switch (stage) {
      case 2: return '#16a34a'
      case 1: case 3: return '#ca8a04'
      case 4: return '#dc2626'
      default: return '#6b7280'
    }
  }

  // K-line + MA chart (with optional Bollinger)
  const klineOption = useMemo(() => {
    if (!result?.chart_data) return {}
    const { dates, kline, ma, bollinger } = result.chart_data
    const series: any[] = [
      {
        type: 'candlestick',
        data: kline.map(d => [d[1], d[2], d[3], d[4]]),
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a',
        },
        barWidth: '60%',
      },
    ]
    const maColors: Record<string, string> = { ma5: '#f59e0b', ma10: '#3b82f6', ma20: '#8b5cf6', ma60: '#ec4899', ma120: '#14b8a6' }
    const maLabels: Record<string, string> = { ma5: 'MA5', ma10: 'MA10', ma20: 'MA20', ma60: 'MA60', ma120: 'MA120' }
    for (const key of ['ma5', 'ma10', 'ma20', 'ma60', 'ma120'] as const) {
      const data = ma[key]
      if (data) {
        series.push({
          type: 'line', name: maLabels[key], data,
          lineStyle: { width: key === 'ma120' ? 2 : 1, color: maColors[key] },
          symbol: 'none', smooth: true,
        })
      }
    }
    if (showBollinger && bollinger) {
      series.push({ type: 'line', name: 'BOLL上轨', data: bollinger.upper, lineStyle: { color: '#9333ea', width: 1, type: 'dashed' }, symbol: 'none' })
      series.push({ type: 'line', name: 'BOLL中轨', data: bollinger.middle, lineStyle: { color: '#9333ea', width: 1 }, symbol: 'none' })
      series.push({ type: 'line', name: 'BOLL下轨', data: bollinger.lower, lineStyle: { color: '#9333ea', width: 1, type: 'dashed' }, symbol: 'none' })
    }
    const legendData = ['MA5', 'MA10', 'MA20', 'MA60', 'MA120']
    if (showBollinger) legendData.push('BOLL上轨', 'BOLL中轨', 'BOLL下轨')
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          if (!Array.isArray(params) || params.length === 0) return ''
          const k = params.find((p: any) => p.seriesType === 'candlestick')
          if (!k) return ''
          const d = k.data
          return `${k.axisValue}<br/>开: ${d[1]}<br/>收: ${d[2]}<br/>低: ${d[3]}<br/>高: ${d[4]}`
        },
      },
      legend: { data: legendData, top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 30, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151' } }, axisLine: { lineStyle: { color: '#374151' } } },
      dataZoom: [{ type: 'inside', start: 60, end: 100 }, { type: 'slider', start: 60, end: 100, height: 20, bottom: 5 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data, showBollinger])

  // Volume chart
  const volumeOption = useMemo(() => {
    if (!result?.chart_data) return {}
    const { dates, volume } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 30, top: 10, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [{ type: 'bar', data: volume.map(v => ({ value: v.volume, itemStyle: { color: v.color } })) }],
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  // MACD chart
  const macdOption = useMemo(() => {
    if (!result?.chart_data) return {}
    const { dates, macd } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['DIF', 'DEA', 'MACD'], top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 25, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'DIF', data: macd.dif, lineStyle: { color: '#3b82f6', width: 1.5 }, symbol: 'none' },
        { type: 'line', name: 'DEA', data: macd.dea, lineStyle: { color: '#f59e0b', width: 1.5 }, symbol: 'none' },
        { type: 'bar', name: 'MACD', data: macd.histogram.map(v => ({ value: v, itemStyle: { color: v >= 0 ? '#ef5350' : '#26a69a' } })) },
      ],
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  // ADX chart
  const adxOption = useMemo(() => {
    if (!result?.chart_data) return {}
    const { dates, adx } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['ADX', '+DI', '-DI'], top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 25, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', min: 0, max: 80, axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'ADX', data: adx.adx, lineStyle: { color: '#ef5350', width: 2 }, symbol: 'none' },
        { type: 'line', name: '+DI', data: adx.plus_di, lineStyle: { color: '#16a34a', width: 1 }, symbol: 'none' },
        { type: 'line', name: '-DI', data: adx.minus_di, lineStyle: { color: '#dc2626', width: 1 }, symbol: 'none' },
      ],
      markLine: {
        silent: true,
        data: [
          { yAxis: 25, lineStyle: { color: '#f59e0b', type: 'dashed' }, label: { formatter: '趋势线(25)', color: '#f59e0b' } },
          { yAxis: 20, lineStyle: { color: '#6b7280', type: 'dashed' }, label: { formatter: '震荡线(20)', color: '#6b7280' } },
        ],
      },
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  // CCI chart
  const cciOption = useMemo(() => {
    if (!result?.chart_data) return {}
    const { dates, cci } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 30, top: 10, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'CCI', data: cci, lineStyle: { color: '#8b5cf6', width: 1.5 }, symbol: 'none' },
      ],
      markLine: {
        silent: true,
        data: [
          { yAxis: 100, lineStyle: { color: '#16a34a', type: 'dashed' }, label: { formatter: '+100', color: '#16a34a' } },
          { yAxis: -100, lineStyle: { color: '#dc2626', type: 'dashed' }, label: { formatter: '-100', color: '#dc2626' } },
          { yAxis: 0, lineStyle: { color: '#6b7280', type: 'dotted' }, label: { show: false } },
        ],
      },
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  // OBV chart
  const obvOption = useMemo(() => {
    if (!result?.chart_data) return {}
    const { dates, obv } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['OBV', 'OBV_MA20'], top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 25, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'OBV', data: obv.obv, lineStyle: { color: '#3b82f6', width: 1.5 }, symbol: 'none', areaStyle: { color: 'rgba(59,130,246,0.1)' } },
        { type: 'line', name: 'OBV_MA20', data: obv.obv_ma20, lineStyle: { color: '#f59e0b', width: 1 }, symbol: 'none' },
      ],
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  const dimensions = result ? [
    { key: 'ma', label: '均线系统', icon: '📊' },
    { key: 'macd', label: 'MACD确认', icon: '📈' },
    { key: 'volume', label: '成交量', icon: '📦' },
    { key: 'pattern', label: '价格形态', icon: '🔍' },
    { key: 'rsi_kdj', label: 'RSI/KDJ', icon: '⚡' },
    { key: 'new_indicators', label: '综合指标', icon: '🎯' },
  ] : []

  return (
    <div style={{ padding: 20, maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ color: '#f3f4f6', margin: 0, fontSize: 20, fontWeight: 600 }}>右侧交易判断</h2>
        <p style={{ color: '#9ca3af', margin: '4px 0 0', fontSize: 13 }}>
          六维度评分 · 多时间框架 · ADX环境判断 · Weinstein阶段 · 假右侧排除
        </p>
      </div>

      {/* Search */}
      <div ref={searchRef} style={{ position: 'relative', marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            value={stockSearch}
            onChange={e => { setStockSearch(e.target.value); setShowSearch(true) }}
            onFocus={() => setShowSearch(true)}
            placeholder="输入股票代码或名称..."
            style={{
              flex: 1, padding: '10px 14px', background: '#1f2937', border: '1px solid #374151',
              borderRadius: 8, color: '#f3f4f6', fontSize: 14, outline: 'none',
            }}
          />
          {stockCode && (
            <button
              onClick={() => { loadAnalysis(stockCode); setBacktest(null) }}
              disabled={loading}
              style={{
                padding: '10px 20px', background: '#3b82f6', border: 'none', borderRadius: 8,
                color: '#fff', fontSize: 14, cursor: loading ? 'wait' : 'pointer',
              }}
            >
              {loading ? '分析中...' : '重新分析'}
            </button>
          )}
        </div>
        {showSearch && searchResults.length > 0 && (
          <div style={{
            position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
            background: '#1f2937', border: '1px solid #374151', borderRadius: 8, marginTop: 4,
            maxHeight: 240, overflow: 'auto',
          }}>
            {searchResults.map(s => (
              <div
                key={s.code} onClick={() => selectStock(s.code)}
                style={{ padding: '8px 14px', cursor: 'pointer', color: '#f3f4f6', fontSize: 13, borderBottom: '1px solid #374151' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#374151')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <span style={{ fontWeight: 600 }}>{s.code}</span> <span style={{ color: '#9ca3af' }}>{s.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: 16, background: '#7f1d1d', borderRadius: 8, color: '#fca5a5', marginBottom: 20 }}>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af' }}>
          <div style={{ fontSize: 18, marginBottom: 8 }}>正在分析...</div>
          <div style={{ fontSize: 13 }}>获取日线+周线数据 → ADX环境判断 → 六维度评分 → 多时间框架确认</div>
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <>
          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            <button onClick={() => setActiveTab('analysis')} style={{
              padding: '8px 20px', background: activeTab === 'analysis' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>综合分析</button>
            <button onClick={() => { setActiveTab('backtest'); if (!backtest) loadBacktest() }} style={{
              padding: '8px 20px', background: activeTab === 'backtest' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>历史回测</button>
          </div>

          {activeTab === 'analysis' && (
            <>
              {/* Verdict Banner */}
              {(() => {
                const vs = getVerdictStyle(result.verdict)
                return (
                  <div style={{
                    background: vs.bg, borderRadius: 12, padding: '20px 24px', marginBottom: 16,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                      <span style={{ fontSize: 36, color: vs.text }}>{vs.icon}</span>
                      <div>
                        <div style={{ fontSize: 22, fontWeight: 700, color: vs.text }}>{result.verdict}</div>
                        <div style={{ fontSize: 13, color: vs.text, opacity: 0.85, marginTop: 2 }}>
                          {result.code} · 更新时间: {result.update_time}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 42, fontWeight: 800, color: vs.text }}>{result.score}</div>
                      <div style={{ fontSize: 12, color: vs.text, opacity: 0.8 }}>/ 100分</div>
                    </div>
                  </div>
                )
              })()}

              {/* Market Regime + Weinstein */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                {/* ADX Regime */}
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 14, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>ADX市场环境</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      padding: '4px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                      background: getRegimeColor(result.market_regime.regime), color: '#fff',
                    }}>
                      {result.market_regime.regime === 'trending' ? '趋势市' : result.market_regime.regime === 'developing' ? '趋势形成中' : '震荡市'}
                    </div>
                    <div style={{ fontSize: 14, color: '#f3f4f6' }}>
                      ADX=<span style={{ fontWeight: 700 }}>{result.market_regime.adx_value}</span>
                    </div>
                    <div style={{ fontSize: 13, color: result.market_regime.trend_direction === 'up' ? '#16a34a' : result.market_regime.trend_direction === 'down' ? '#dc2626' : '#9ca3af' }}>
                      {result.market_regime.trend_direction === 'up' ? '多头趋势' : result.market_regime.trend_direction === 'down' ? '空头趋势' : '方向不明'}
                    </div>
                  </div>
                </div>

                {/* Weinstein Stage */}
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 14, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>Weinstein阶段分析</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: getStageColor(result.weinstein_stage.stage), color: '#fff', fontSize: 18, fontWeight: 700,
                    }}>
                      {result.weinstein_stage.stage}
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{result.weinstein_stage.stage_name}</div>
                      <div style={{ fontSize: 11, color: '#9ca3af' }}>
                        MA30斜率: {result.weinstein_stage.ma30_slope}% · 价格偏离: {result.weinstein_stage.price_vs_ma30}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Timeframe Alignment + Risk */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                {/* Multi-Timeframe */}
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 14, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>多时间框架对齐</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
                    <div>
                      <div style={{ fontSize: 11, color: '#9ca3af' }}>日线</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: getVerdictStyle(result.verdict).bg === '#16a34a' ? '#16a34a' : '#f3f4f6' }}>{result.score}分</div>
                    </div>
                    <div style={{ fontSize: 20, color: result.timeframe_alignment.aligned ? '#16a34a' : result.timeframe_alignment.conflict ? '#dc2626' : '#6b7280' }}>
                      {result.timeframe_alignment.aligned ? '✓' : result.timeframe_alignment.conflict ? '✗' : '—'}
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: '#9ca3af' }}>周线</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: '#f3f4f6' }}>{result.weekly_score}分</div>
                    </div>
                    <div style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 11,
                      background: result.timeframe_alignment.alignment_score > 0 ? '#16a34a' : '#374151', color: '#fff',
                    }}>
                      +{result.timeframe_alignment.alignment_score}分
                    </div>
                  </div>
                  {result.timeframe_alignment.alignment_signals.map((s, i) => (
                    <div key={i} style={{ fontSize: 11, color: '#d1d5db', padding: '2px 0' }}>· {s}</div>
                  ))}
                </div>

                {/* Risk Management */}
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 14, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>
                    风险管理 · ATR({result.risk_management.atr_pct}%)
                    <span style={{
                      marginLeft: 8, padding: '1px 6px', borderRadius: 3, fontSize: 10,
                      background: result.risk_management.volatility_level === 'low' ? '#16a34a' :
                        result.risk_management.volatility_level === 'medium' ? '#ca8a04' : '#dc2626', color: '#fff',
                    }}>
                      {result.risk_management.volatility_level === 'low' ? '低波动' :
                        result.risk_management.volatility_level === 'medium' ? '中波动' :
                          result.risk_management.volatility_level === 'high' ? '高波动' : '极高波动'}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 10, color: '#9ca3af' }}>止损位(正常)</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#dc2626' }}>{result.risk_management.stop_loss.normal}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: '#9ca3af' }}>建议仓位</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{result.risk_management.position_sizing.suggested_pct}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: '#9ca3af' }}>2R目标</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#16a34a' }}>{result.risk_management.risk_reward.target_2r}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 6-Dimension Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                {dimensions.map(d => {
                  const dim = result.dimensions[d.key as keyof typeof result.dimensions]
                  const pct = dim.max > 0 ? (dim.score / dim.max) * 100 : 0
                  const isExpanded = expandedDim === d.key
                  return (
                    <div
                      key={d.key}
                      onClick={() => setExpandedDim(isExpanded ? null : d.key)}
                      style={{
                        background: '#1f2937', borderRadius: 10, padding: 14, cursor: 'pointer',
                        border: isExpanded ? '1px solid #3b82f6' : '1px solid #374151',
                        transition: 'border-color 0.2s',
                      }}
                    >
                      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>{d.icon} {d.label}</div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: '#f3f4f6' }}>{dim.score}<span style={{ fontSize: 12, color: '#6b7280' }}>/{dim.max}</span></div>
                      <div style={{ marginTop: 8, height: 4, background: '#374151', borderRadius: 2 }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: pct >= 60 ? '#16a34a' : pct >= 30 ? '#ca8a04' : '#dc2626', borderRadius: 2, transition: 'width 0.5s' }} />
                      </div>
                      {isExpanded && dim.signals.length > 0 && (
                        <div style={{ marginTop: 10, borderTop: '1px solid #374151', paddingTop: 8 }}>
                          {dim.signals.map((s, i) => (
                            <div key={i} style={{ fontSize: 11, color: '#d1d5db', padding: '2px 0', lineHeight: 1.4 }}>· {s}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Anti-fake Warnings */}
              {result.anti_fake_checks.length > 0 && (
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, marginBottom: 16, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 10 }}>假右侧风险提示</div>
                  {result.anti_fake_checks.map((w, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0',
                      borderBottom: i < result.anti_fake_checks.length - 1 ? '1px solid #374151' : 'none',
                    }}>
                      <span style={{
                        display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: getSeverityColor(w.severity), color: '#fff', flexShrink: 0,
                      }}>
                        {w.severity === 'high' ? '高危' : w.severity === 'medium' ? '中危' : '低危'}
                      </span>
                      <span style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.5 }}>{w.message}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Charts */}
              <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>K线图 · 成交量 · MACD</div>
                  <button onClick={() => setShowBollinger(!showBollinger)} style={{
                    padding: '4px 12px', background: showBollinger ? '#8b5cf6' : '#374151', border: 'none',
                    borderRadius: 6, color: '#fff', fontSize: 11, cursor: 'pointer',
                  }}>
                    {showBollinger ? '隐藏布林带' : '显示布林带'}
                  </button>
                </div>
                {result?.chart_data && (klineOption as any)?.series && (
                  <>
                    <ReactECharts
                      key={`kline-${result?.code}-${result?.chart_data?.dates?.length}`}
                      option={klineOption}
                      style={{ height: 380, width: '100%' }}
                      notMerge={true}
                      onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }}
                    />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>成交量</div>
                    <ReactECharts key={`vol-${result?.code}`} option={volumeOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>MACD</div>
                    <ReactECharts key={`macd-${result?.code}`} option={macdOption} style={{ height: 140, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>ADX趋势强度</div>
                    <ReactECharts key={`adx-${result?.code}`} option={adxOption} style={{ height: 140, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>CCI动量</div>
                    <ReactECharts key={`cci-${result?.code}`} option={cciOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>OBV能量潮</div>
                    <ReactECharts key={`obv-${result?.code}`} option={obvOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                  </>
                )}
              </div>
            </>
          )}

          {/* Backtest Tab */}
          {activeTab === 'backtest' && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>历史信号回测</div>
              {backtestLoading && <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>正在计算历史信号...</div>}
              {backtest && !backtestLoading && (
                <>
                  {/* Stats */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
                    {[
                      { label: '信号总数', value: backtest.stats.total_signals, color: '#f3f4f6' },
                      { label: '20日胜率', value: `${backtest.stats.win_rate_20d}%`, color: backtest.stats.win_rate_20d > 50 ? '#16a34a' : '#dc2626' },
                      { label: '20日均收益', value: `${backtest.stats.avg_return_20d}%`, color: backtest.stats.avg_return_20d > 0 ? '#16a34a' : '#dc2626' },
                      { label: '最大收益', value: `${backtest.stats.max_return_20d}%`, color: '#16a34a' },
                      { label: '夏普比率', value: backtest.stats.sharpe_like, color: backtest.stats.sharpe_like > 0 ? '#16a34a' : '#dc2626' },
                    ].map((s, i) => (
                      <div key={i} style={{ background: '#111827', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>{s.label}</div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Signals Table */}
                  {backtest.signals.length > 0 ? (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid #374151' }}>
                            {['日期', '分数', '判定', '信号价格', '5日收益', '10日收益', '20日收益', '60日收益'].map(h => (
                              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 500 }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {backtest.signals.map((s, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #1f2937' }}>
                              <td style={{ padding: '8px 12px', color: '#f3f4f6' }}>{s.date}</td>
                              <td style={{ padding: '8px 12px', color: '#f3f4f6', fontWeight: 600 }}>{s.score}</td>
                              <td style={{ padding: '8px 12px' }}>
                                <span style={{
                                  padding: '2px 8px', borderRadius: 4, fontSize: 11,
                                  background: getVerdictStyle(s.verdict).bg, color: '#fff',
                                }}>{s.verdict}</span>
                              </td>
                              <td style={{ padding: '8px 12px', color: '#f3f4f6' }}>{s.price_at_signal}</td>
                              {['5d', '10d', '20d', '60d'].map(period => {
                                const val = s.returns[period as keyof typeof s.returns]
                                return (
                                  <td key={period} style={{
                                    padding: '8px 12px',
                                    color: val === null ? '#6b7280' : val > 0 ? '#16a34a' : '#dc2626',
                                    fontWeight: val !== null ? 600 : 400,
                                  }}>
                                    {val !== null ? `${val > 0 ? '+' : ''}${val}%` : '—'}
                                  </td>
                                )
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>暂无历史信号</div>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div style={{ textAlign: 'center', padding: 80, color: '#6b7280' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
          <div style={{ fontSize: 16, marginBottom: 8 }}>输入股票代码开始分析</div>
          <div style={{ fontSize: 13 }}>支持A股和港股 · 多时间框架 · ADX环境判断 · Weinstein阶段分析</div>
        </div>
      )}
    </div>
  )
}
