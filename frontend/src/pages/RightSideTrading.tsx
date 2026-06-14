import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { Tooltip } from 'antd'
import { PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState, ProgressBar } from '../components/ui'
import { useTradingInterceptor } from '../hooks/useTradingInterceptor'
import RationalCheckpoint from '../components/RationalCheckpoint'

const API_BASE = '/api'

/** 悬停提示组件 */
const Tip = ({ text }: { text: string }) => (
  <Tooltip title={text} overlayStyle={{ maxWidth: 300 }}>
    <span className="tip-trigger">?</span>
  </Tooltip>
)

/** 指标说明数据 */
const DIMENSION_DESC: Record<string, string> = {
  ma: '看价格是否在各均线上方、均线是否多头排列（短期>中期>长期）。均线就像"趋势轨道"，价格稳稳站在上方=趋势向上，跌破=趋势转弱。多头排列越多，趋势越强。',
  macd: 'MACD由快线(DIF)和慢线(DEA)组成。金叉=快线上穿慢线=看涨；死叉=看跌。柱状图由负转正=动量转强。在零轴上方金叉比下方更可靠。',
  volume: '成交量是价格的"燃料"。放量上涨=真突破（大家都在买）；缩量上涨=动力不足要小心。上涨时量大、下跌时量小=健康的量价配合。',
  pattern: '寻找经典的底部突破图形：W底（两次探底后突破颈线）、杯柄形态（U型底+小回调）、旗形突破（快速拉升后整理再突破）。这些是大师们验证过的高胜率形态。',
  rsi_kdj: '衡量短期涨跌力度的"温度计"。RSI<30=超卖区（跌过头了，可能反弹）；RSI>70=超买区（涨过头了，可能回调）。KDJ金叉=短期看涨信号。',
  new_indicators: '多指标综合验证：布林带（价格通道）突破上轨=强势；OBV能量潮确认资金流入；CCI突破+100=动量强；抛物线SAR在价格下方=趋势向上。',
  momentum: '判断上涨"力气"够不够大。KST是多周期动量的加权综合，上穿信号线=动量转强。Williams %R衡量超买超卖。多周期变动率(ROC)全部为正=动量共振，趋势更可靠。',
  adaptive_trend: 'KAMA是"聪明的均线"——趋势市时紧跟价格（反应快），震荡市时自动远离价格（减少假信号）。Elder三重滤网要求周线→日线→入场方向一致才给高分。',
  td_sequential: 'DeMark发明的"数K线"系统。连续9根K线收盘高于4天前=趋势可能"累了"要休息（卖出Setup）。连续13根确认=更强的衰竭信号。用作风险提示，防止追在顶部。',
}

const REGIME_DESC: Record<string, string> = {
  trending: 'ADX≥25，市场有明确趋势方向。此时均线/MACD等趋势指标更可靠，适合趋势跟随策略。',
  developing: 'ADX在20-25之间，趋势初步形成但尚未确立。可以关注但需谨慎，等ADX突破25再加仓。',
  ranging: 'ADX<20，市场无明确方向，在区间内来回震荡。此时右侧信号假突破多，可靠性较低，建议观望。',
}

const STAGE_DESC: Record<string, string> = {
  '1': '底部蓄势期：价格横盘整理，成交量低迷，30周均线走平。耐心等待突破，不要提前入场。',
  '2': '★ 上升趋势（买入区间）：价格突破盘整区+站上30周均线+均线向上+成交量放大。这是大师们公认的"安全入场区"。',
  '3': '顶部派发期：价格高位横盘，成交量异常放大但涨不动。聪明钱在出货，考虑减仓或卖出。',
  '4': '下降趋势：价格跌破30周均线，均线向下。远离，不要抄底，"接飞刀"很危险。',
}

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
    profit_loss_ratio?: number
    avg_trailing_return?: number
    win_rate_trailing?: number
  }
  code: string
}

interface MarketTiming {
  status: string
  signal: string
  reason: string
  index_close: number
  index_ma60: number
  index_ma60_slope: number
}

interface SectorStrength {
  sector_name: string
  sector_signal: string
  reason: string
  sector_change_pct: number
  top_sector: string
  top_sector_change: number
}

interface FundamentalHealth {
  eps_growth: number | null
  roe: number | null
  revenue_growth: number | null
  signal: string
  reason: string
  report_date: string
}

interface EntryPlan {
  entry_type: string
  entry_price: number
  stop_loss_price: number
  risk_per_share: number
  position_size_pct: number
  position_shares?: number
  position_value?: number
  target_2r: number
  target_3r: number
  reason: string
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
    momentum: DimensionResult
    adaptive_trend: DimensionResult
    td_sequential: DimensionResult
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
  market_timing: MarketTiming
  sector_strength: SectorStrength
  fundamental_health: FundamentalHealth
  entry_plan: EntryPlan
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
    kama: (number|null)[]
    kst: { kst: (number|null)[]; signal: (number|null)[] }
    williams_r: (number|null)[]
    rsi: (number|null)[]
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
  const [activeTab, setActiveTab] = useState<'analysis' | 'backtest' | 'scan' | 'sector' | 'watchlist'>('analysis')

  // Scan state
  const [scanResults, setScanResults] = useState<any>(null)
  const [scanLoading, setScanLoading] = useState(false)
  const [scanMinScore, setScanMinScore] = useState(50)

  // Sector state
  const [sectorData, setSectorData] = useState<any>(null)
  const [sectorLoading, setSectorLoading] = useState(false)

  // Watchlist state
  const [watchlist, setWatchlist] = useState<any>(null)
  const [watchlistLoading, setWatchlistLoading] = useState(false)
  const [watchlistScan, setWatchlistScan] = useState<any>(null)
  const [watchlistScanLoading, setWatchlistScanLoading] = useState(false)

  // 交易拦截器
  const { intercept, checkpointOpen, checkpointMeta, handlePass, handleCancel } = useTradingInterceptor()

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
    doLoadAnalysis(code) // 直接分析，不触发拦截器（选择股票不是交易决策）
  }

  const doLoadAnalysis = async (code: string) => {
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

  const loadAnalysis = (code: string) => {
    intercept(() => doLoadAnalysis(code), {
      actionType: 'analyze',
      target: code,
    })
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

  const loadScan = async () => {
    setScanLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/right-side/scan/batch`, {
        params: { min_score: scanMinScore, limit: 30 },
      })
      setScanResults(res.data)
    } catch (err: any) {
      console.error('扫描失败:', err)
    } finally {
      setScanLoading(false)
    }
  }

  const loadSector = async () => {
    setSectorLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/right-side/sector/rotation`)
      setSectorData(res.data)
    } catch (err: any) {
      console.error('板块分析失败:', err)
    } finally {
      setSectorLoading(false)
    }
  }

  const loadWatchlist = async () => {
    setWatchlistLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/right-side/watchlist/list`)
      setWatchlist(res.data)
    } catch (err: any) {
      console.error('加载自选股失败:', err)
    } finally {
      setWatchlistLoading(false)
    }
  }

  const scanWatchlist = async () => {
    setWatchlistScanLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/right-side/watchlist/scan`)
      setWatchlistScan(res.data)
    } catch (err: any) {
      console.error('扫描自选股失败:', err)
    } finally {
      setWatchlistScanLoading(false)
    }
  }

  const addToWatchlist = async () => {
    if (!stockCode) return
    try {
      await axios.post(`${API_BASE}/right-side/watchlist/add`, null, {
        params: { code: stockCode, market: 'A' },
      })
      alert('已添加到自选股')
      loadWatchlist()
    } catch (err: any) {
      alert(err?.response?.data?.detail || '添加失败')
    }
  }

  const getVerdictStyle = (verdict: string) => {
    switch (verdict) {
      case '右侧确认': return { bg: '#16a34a', icon: '✓', text: '#fff' }
      case '观望等待': return { bg: '#ca8a04', icon: '⏳', text: '#fff' }
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
    const { dates, kline, ma, bollinger, kama } = result.chart_data
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
    // KAMA自适应均线
    if (kama) {
      series.push({ type: 'line', name: 'KAMA', data: kama, lineStyle: { color: '#f97316', width: 2 }, symbol: 'none', smooth: true })
    }
    const legendData = ['MA5', 'MA10', 'MA20', 'MA60', 'MA120', 'KAMA']
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
          return `${k.axisValue}<br/>开: ${d[0]}<br/>收: ${d[1]}<br/>低: ${d[2]}<br/>高: ${d[3]}`
        },
      },
      legend: { data: legendData, top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 30, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151' } }, axisLine: { lineStyle: { color: '#374151' } } },
      series,
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
      yAxis: { type: 'value', min: 0, axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'ADX', data: adx.adx, lineStyle: { color: '#ef5350', width: 2 }, symbol: 'none',
          markLine: {
            silent: true,
            data: [
              { yAxis: 25, lineStyle: { color: '#f59e0b', type: 'dashed' }, label: { formatter: '趋势线(25)', color: '#f59e0b', position: 'end' } },
              { yAxis: 20, lineStyle: { color: '#6b7280', type: 'dashed' }, label: { formatter: '震荡线(20)', color: '#6b7280', position: 'end' } },
            ],
          },
        },
        { type: 'line', name: '+DI', data: adx.plus_di, lineStyle: { color: '#16a34a', width: 1 }, symbol: 'none' },
        { type: 'line', name: '-DI', data: adx.minus_di, lineStyle: { color: '#dc2626', width: 1 }, symbol: 'none' },
      ],
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
        { type: 'line', name: 'CCI', data: cci, lineStyle: { color: '#8b5cf6', width: 1.5 }, symbol: 'none',
          markLine: {
            silent: true,
            data: [
              { yAxis: 100, lineStyle: { color: '#16a34a', type: 'dashed' }, label: { formatter: '+100', color: '#16a34a', position: 'end' } },
              { yAxis: -100, lineStyle: { color: '#dc2626', type: 'dashed' }, label: { formatter: '-100', color: '#dc2626', position: 'end' } },
              { yAxis: 0, lineStyle: { color: '#6b7280', type: 'dotted' }, label: { show: false } },
            ],
          },
        },
      ],
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

  // KST chart
  const kstOption = useMemo(() => {
    if (!result?.chart_data?.kst) return {}
    const { dates, kst } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['KST', '信号线'], top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 25, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'KST', data: kst.kst, lineStyle: { color: '#8b5cf6', width: 1.5 }, symbol: 'none' },
        { type: 'line', name: '信号线', data: kst.signal, lineStyle: { color: '#f59e0b', width: 1 }, symbol: 'none' },
      ],
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  // Williams %R chart
  const wrOption = useMemo(() => {
    if (!result?.chart_data?.williams_r) return {}
    const { dates, williams_r } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['Williams %R'], top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 25, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', min: -100, max: 0, axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: '%R', data: williams_r, lineStyle: { color: '#14b8a6', width: 1.5 }, symbol: 'none',
          markLine: {
            silent: true,
            data: [
              { yAxis: -20, lineStyle: { color: '#dc2626', type: 'dashed' }, label: { formatter: '超买', color: '#dc2626', fontSize: 10 } },
              { yAxis: -80, lineStyle: { color: '#16a34a', type: 'dashed' }, label: { formatter: '超卖', color: '#16a34a', fontSize: 10 } },
            ],
          },
        },
      ],
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  // RSI chart
  const rsiOption = useMemo(() => {
    if (!result?.chart_data?.rsi) return {}
    const { dates, rsi } = result.chart_data
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['RSI(14)'], top: 0, textStyle: { color: '#9ca3af', fontSize: 11 } },
      grid: { left: 60, right: 30, top: 25, bottom: 30 },
      xAxis: { type: 'category', data: dates, axisLabel: { show: false } },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { color: '#9ca3af', fontSize: 10 }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [
        { type: 'line', name: 'RSI(14)', data: rsi, lineStyle: { color: '#f59e0b', width: 1.5 }, symbol: 'none',
          markLine: {
            silent: true,
            data: [
              { yAxis: 70, lineStyle: { color: '#ca8a04', type: 'dashed' }, label: { formatter: '超买(70)', color: '#ca8a04', position: 'end' } },
              { yAxis: 80, lineStyle: { color: '#dc2626', type: 'dashed' }, label: { formatter: '深度超买(80)', color: '#dc2626', position: 'end' } },
              { yAxis: 30, lineStyle: { color: '#16a34a', type: 'dashed' }, label: { formatter: '超卖(30)', color: '#16a34a', position: 'end' } },
              { yAxis: 50, lineStyle: { color: '#374151', type: 'dotted' }, label: { show: false } },
            ],
          },
        },
      ],
      dataZoom: [{ type: 'inside', start: 60, end: 100 }],
      backgroundColor: 'transparent',
    }
  }, [result?.chart_data])

  const dimensions = result ? [
    { key: 'ma', label: '均线系统', icon: '📊', desc: DIMENSION_DESC.ma },
    { key: 'macd', label: 'MACD确认', icon: '📈', desc: DIMENSION_DESC.macd },
    { key: 'volume', label: '成交量', icon: '📦', desc: DIMENSION_DESC.volume },
    { key: 'pattern', label: '价格形态', icon: '🔍', desc: DIMENSION_DESC.pattern },
    { key: 'rsi_kdj', label: 'RSI/KDJ', icon: '⚡', desc: DIMENSION_DESC.rsi_kdj },
    { key: 'new_indicators', label: '综合指标', icon: '🎯', desc: DIMENSION_DESC.new_indicators },
    { key: 'momentum', label: '动量综合', icon: '🚀', desc: DIMENSION_DESC.momentum },
    { key: 'adaptive_trend', label: '自适应趋势', icon: '🧭', desc: DIMENSION_DESC.adaptive_trend },
    { key: 'td_sequential', label: 'TD序列', icon: '🔢', desc: DIMENSION_DESC.td_sequential },
  ] : []

  return (
    <div style={{ padding: 20, maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ color: '#f3f4f6', margin: 0, fontSize: 20, fontWeight: 600 }}>右侧交易判断</h2>
        <p style={{ color: '#9ca3af', margin: '4px 0 0', fontSize: 13 }}>
          九维度评分 · 多时间框架 · ADX环境判断 · Weinstein阶段 · 假右侧排除
          <Tip text="右侧交易=在趋势确认后才入场（追涨不追高）。通过9个维度的技术指标综合打分（满分100），判断股票是否处于上升趋势中。分数越高，右侧信号越强。" />
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
          <div style={{ fontSize: 13 }}>获取日线+周线数据 → ADX环境判断 → 九维度评分 → 多时间框架确认</div>
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <>
          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
            <button onClick={() => setActiveTab('analysis')} style={{
              padding: '8px 20px', background: activeTab === 'analysis' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>综合分析</button>
            <button onClick={() => { setActiveTab('backtest'); if (!backtest) loadBacktest() }} style={{
              padding: '8px 20px', background: activeTab === 'backtest' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>历史回测</button>
            <button onClick={() => { setActiveTab('scan'); if (!scanResults) loadScan() }} style={{
              padding: '8px 20px', background: activeTab === 'scan' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>🔍 批量扫描</button>
            <button onClick={() => { setActiveTab('sector'); if (!sectorData) loadSector() }} style={{
              padding: '8px 20px', background: activeTab === 'sector' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>📊 板块轮动</button>
            <button onClick={() => { setActiveTab('watchlist'); loadWatchlist() }} style={{
              padding: '8px 20px', background: activeTab === 'watchlist' ? '#3b82f6' : '#1f2937',
              border: '1px solid #374151', borderRadius: 8, color: '#f3f4f6', fontSize: 13, cursor: 'pointer',
            }}>⭐ 自选股</button>
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
                      <div style={{ fontSize: 12, color: vs.text, opacity: 0.8 }}>/ 100分
                        <Tip text="大师级判定：大盘牛市+无高危警告+≥65分=右侧确认（可入场）；其他情况=观望等待（不做）；<32分=左侧下跌（远离）。大盘熊市时一票否决。" />
                      </div>
                    </div>
                  </div>
                )
              })()}

              {/* 大师决策面板 */}
              {result.market_timing && (
                <div style={{
                  background: '#1f2937', borderRadius: 12, padding: 16, marginBottom: 16,
                  border: result.market_timing.signal === 'no_trade' ? '2px solid #dc2626' : '1px solid #374151',
                }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>
                    大师决策面板
                    <Tip text="大师们的决策流程：①先看大盘（M=Market）②再看行业③再看基本面④最后看技术面。任何一层不通过，都不入场。" />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                    {/* 大盘择时 */}
                    <div style={{
                      background: '#111827', borderRadius: 8, padding: 12,
                      border: result.market_timing.signal === 'no_trade' ? '1px solid #dc2626' : result.market_timing.signal === 'go' ? '1px solid #16a34a' : '1px solid #ca8a04',
                    }}>
                      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>① 大盘择时</div>
                      <div style={{
                        fontSize: 14, fontWeight: 700, marginBottom: 4,
                        color: result.market_timing.signal === 'go' ? '#16a34a' : result.market_timing.signal === 'no_trade' ? '#dc2626' : '#ca8a04',
                      }}>
                        {result.market_timing.signal === 'go' ? '✓ 牛市' : result.market_timing.signal === 'no_trade' ? '✗ 熊市' : '— 中性'}
                      </div>
                      <div style={{ fontSize: 10, color: '#6b7280' }}>
                        上证{result.market_timing.index_close} / MA60{result.market_timing.index_ma60}
                      </div>
                    </div>

                    {/* 行业强度 */}
                    <div style={{
                      background: '#111827', borderRadius: 8, padding: 12,
                      border: result.sector_strength.sector_signal === 'strong' ? '1px solid #16a34a' : result.sector_strength.sector_signal === 'weak' ? '1px solid #dc2626' : '1px solid #374151',
                    }}>
                      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>② 行业强度</div>
                      <div style={{
                        fontSize: 14, fontWeight: 700, marginBottom: 4,
                        color: result.sector_strength.sector_signal === 'strong' ? '#16a34a' : result.sector_strength.sector_signal === 'weak' ? '#dc2626' : '#f3f4f6',
                      }}>
                        {result.sector_strength.sector_signal === 'strong' ? '✓ 活跃' : result.sector_strength.sector_signal === 'weak' ? '✗ 偏冷' : '— 温和'}
                      </div>
                      <div style={{ fontSize: 10, color: '#6b7280' }}>
                        {result.sector_strength.top_sector ? `领涨: ${result.sector_strength.top_sector}` : result.sector_strength.reason?.slice(0, 15)}
                      </div>
                    </div>

                    {/* 基本面 */}
                    <div style={{
                      background: '#111827', borderRadius: 8, padding: 12,
                      border: result.fundamental_health.signal === 'pass' ? '1px solid #16a34a' : result.fundamental_health.signal === 'fail' ? '1px solid #dc2626' : '1px solid #374151',
                    }}>
                      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>③ 基本面</div>
                      <div style={{
                        fontSize: 14, fontWeight: 700, marginBottom: 4,
                        color: result.fundamental_health.signal === 'pass' ? '#16a34a' : result.fundamental_health.signal === 'fail' ? '#dc2626' : '#f3f4f6',
                      }}>
                        {result.fundamental_health.signal === 'pass' ? '✓ 健康' : result.fundamental_health.signal === 'fail' ? '✗ 承压' : '— 待查'}
                      </div>
                      <div style={{ fontSize: 10, color: '#6b7280' }}>
                        {result.fundamental_health.eps_growth != null ? `EPS+${result.fundamental_health.eps_growth}%` : '数据不足'}
                        {result.fundamental_health.roe != null ? ` ROE${result.fundamental_health.roe}%` : ''}
                      </div>
                    </div>

                    {/* 入场建议 */}
                    <div style={{
                      background: result.entry_plan.entry_type !== 'none' ? '#111827' : '#1f2937',
                      borderRadius: 8, padding: 12,
                      border: result.entry_plan.entry_type !== 'none' ? '1px solid #3b82f6' : '1px solid #374151',
                    }}>
                      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>④ 入场建议</div>
                      {result.entry_plan.entry_type !== 'none' ? (
                        <>
                          <div style={{ fontSize: 14, fontWeight: 700, color: '#3b82f6', marginBottom: 4 }}>
                            ¥{result.entry_plan.entry_price ?? '--'}
                          </div>
                          <div style={{ fontSize: 10, color: '#6b7280' }}>
                            止损¥{result.entry_plan.stop_loss_price ?? '--'} · {result.entry_plan.position_shares ? `${result.entry_plan.position_shares}股 · ` : ''}仓位{result.entry_plan.position_size_pct}%
                          </div>
                        </>
                      ) : (
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#6b7280', marginBottom: 4 }}>暂无</div>
                      )}
                    </div>
                  </div>

                  {/* 入场详情 */}
                  {result.entry_plan.entry_type !== 'none' && (
                    <div style={{ marginTop: 12, padding: '10px 12px', background: 'rgba(59,130,246,0.08)', borderRadius: 8, fontSize: 12, color: '#93c5fd', lineHeight: 1.8 }}>
                      💡 {result.entry_plan.reason}
                      &nbsp;|&nbsp; 2R目标: ¥{result.entry_plan.target_2r}
                      &nbsp;|&nbsp; 3R目标: ¥{result.entry_plan.target_3r}
                      &nbsp;|&nbsp; 每股风险: ¥{result.entry_plan.risk_per_share}
                      {result.entry_plan.position_shares != null && result.entry_plan.position_shares > 0 && (
                        <> &nbsp;|&nbsp; 建议{result.entry_plan.position_shares}股(约¥{result.entry_plan.position_value?.toLocaleString()})</>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Market Regime + Weinstein */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                {/* ADX Regime */}
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 14, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>ADX市场环境<Tip text={'ADX衡量趋势的“强度”（不分方向）。ADX≥25=有明确趋势，适合趋势跟随；ADX<20=震荡市，假突破多，右侧信号不可靠。'} /></div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      padding: '4px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                      background: getRegimeColor(result.market_regime.regime), color: '#fff',
                    }}>
                      {result.market_regime.regime === 'trending' ? '趋势市' : result.market_regime.regime === 'developing' ? '趋势形成中' : '震荡市'}
                      <Tip text={REGIME_DESC[result.market_regime.regime] || ''} />
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
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>Weinstein阶段分析<Tip text="Stan Weinstein的四阶段模型：①底部蓄势（观望）②上升趋势（买入！）③顶部派发（卖出）④下降趋势（远离）。只在Stage 2买入，是最安全的右侧策略。" /></div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: getStageColor(result.weinstein_stage.stage), color: '#fff', fontSize: 18, fontWeight: 700,
                    }}>
                      {result.weinstein_stage.stage}
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{result.weinstein_stage.stage_name}<Tip text={STAGE_DESC[String(result.weinstein_stage.stage)] || ''} /></div>
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
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>多时间框架对齐<Tip text="日线看短期趋势，周线看中期趋势。两者方向一致（✓）=信号强，加分；方向冲突（✗）=信号矛盾，减分。好比开车要看远近两个方向。" /></div>
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
                    <Tip text="ATR止损=基于波动率自动计算止损位。波动大时止损放宽松（避免被震出），波动小时止损收紧。2R目标=涨2倍ATR的距离，是合理的止盈参考。" />
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

              {/* 9-Dimension Cards */}
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
                      {isExpanded && (
                        <div style={{ marginTop: 10, borderTop: '1px solid #374151', paddingTop: 8 }}>
                          {/* 小白说明 */}
                          <div style={{ fontSize: 11, color: '#60a5fa', lineHeight: 1.6, marginBottom: 8, padding: '6px 8px', background: 'rgba(59,130,246,0.08)', borderRadius: 6 }}>
                            💡 {d.desc}
                          </div>
                          {/* 具体信号 */}
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
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 10 }}>假右侧风险提示<Tip text="即使分数看起来不错，也可能存在假信号。这些警告帮你识别：下跌中的反弹（死猫跳）、缩量突破（假突破）、顶部背离（涨不动了）等危险信号。有高危警告时要特别谨慎。" /></div>
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
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>K线图 · 成交量 · MACD<Tip text="K线=每日价格走势（红涨绿跌）。均线=趋势轨道。KAMA（橙线）=智能均线，震荡市自动远离减少假信号。成交量=交易活跃度。MACD=趋势方向和动量。" /></div>
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
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>ADX趋势强度<Tip text="ADX（黄线）衡量趋势强弱：>25=有趋势，<20=震荡。+DI（绿）vs -DI（红）：+DI在上方=多头占优。" /></div>
                    <ReactECharts key={`adx-${result?.code}`} option={adxOption} style={{ height: 140, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>CCI动量<Tip text={'CCI（商品通道指数）：>100=动量强势，>200=超买注意风险；<-100=动量弱势。突破+100是右侧入场的辅助确认信号。'} /></div>
                    <ReactECharts key={`cci-${result?.code}`} option={cciOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>OBV能量潮<Tip text={'OBV把成交量和价格方向结合：价涨则加成交量，价跌则减。OBV上升=资金持续流入（有人在买）。如果价格涨但OBV跌，说明"虚涨"要小心。'} /></div>
                    <ReactECharts key={`obv-${result?.code}`} option={obvOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>KST动量指标 (Pring)<Tip text="KST把4个不同周期的动量加权合并。紫色KST线上穿黄色信号线=动量转强（看涨）；下穿=动量转弱（看跌）。比单一指标更全面。" /></div>
                    <ReactECharts key={`kst-${result?.code}`} option={kstOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>Williams %R (Larry Williams)<Tip text={'Williams %R衡量短期超买超卖。>-20=超买区（涨过头了可能回调）；<-80=超卖区（跌过头了可能反弹）。从超卖区回升是右侧入场的好时机。'} /></div>
                    <ReactECharts key={`wr-${result?.code}`} option={wrOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
                    <div style={{ fontSize: 12, color: '#6b7280', margin: '8px 0 4px' }}>RSI相对强弱<Tip text={'RSI衡量涨跌力度。>70=超买（可能回调），>80=深度超买（高风险）；<30=超卖（可能反弹）。强趋势中RSI可持续在50-80区间运行。'} /></div>
                    <ReactECharts key={`rsi-${result?.code}`} option={rsiOption} style={{ height: 120, width: '100%' }} notMerge={true} onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }} />
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
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
                    {[
                      { label: '信号总数', value: backtest.stats.total_signals, color: '#f3f4f6', tip: '历史上出现"右侧确认"或"疑似右侧"信号的总次数。信号越多，统计越可靠。' },
                      { label: '20日胜率', value: `${backtest.stats.win_rate_20d}%`, color: backtest.stats.win_rate_20d > 50 ? '#16a34a' : '#dc2626', tip: '出现信号后，持有20天盈利的比例。>50%=策略有效，越高越好。这是最核心的指标。' },
                      { label: '20日均收益', value: `${backtest.stats.avg_return_20d}%`, color: backtest.stats.avg_return_20d > 0 ? '#16a34a' : '#dc2626', tip: '所有信号持有20天的平均收益率。正数=平均赚钱，负数=平均亏钱。' },
                      { label: '盈亏比', value: backtest.stats.profit_loss_ratio ?? '-', color: (backtest.stats.profit_loss_ratio ?? 0) > 1.5 ? '#16a34a' : '#dc2626', tip: '平均盈利 ÷ 平均亏损。>1.5=赚的比亏的多，策略可持续。越高越好。' },
                      { label: 'Trailing收益', value: backtest.stats.avg_trailing_return != null ? `${backtest.stats.avg_trailing_return}%` : '-', color: (backtest.stats.avg_trailing_return ?? 0) > 0 ? '#16a34a' : '#dc2626', tip: '模拟阶梯止损（盈利5%保本、10%锁5%、20%锁10%）后的实际收益，比固定持有更贴近实战。' },
                      { label: '夏普比率', value: backtest.stats.sharpe_like, color: backtest.stats.sharpe_like > 0 ? '#16a34a' : '#dc2626', tip: '收益÷波动率，衡量"性价比"。>0.5=不错，>1=很好。同样的收益，波动越小夏普越高。' },
                    ].map((s, i) => (
                      <div key={i} style={{ background: '#111827', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 4 }}>{s.label}<Tip text={s.tip} /></div>
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
                                    color: val == null ? '#6b7280' : val > 0 ? '#16a34a' : '#dc2626',
                                    fontWeight: val != null ? 600 : 400,
                                  }}>
                                    {val != null ? `${val > 0 ? '+' : ''}${val}%` : '—'}
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

          {/* Scan Tab */}
          {activeTab === 'scan' && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>批量扫描 · 全市场右侧信号</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 12, color: '#9ca3af' }}>最低分数:</span>
                  <input type="number" value={scanMinScore} onChange={e => setScanMinScore(Number(e.target.value))}
                    style={{ width: 60, padding: '4px 8px', background: '#111827', border: '1px solid #374151', borderRadius: 4, color: '#f3f4f6', fontSize: 13 }} />
                  <button onClick={loadScan} disabled={scanLoading} style={{
                    padding: '6px 16px', background: '#3b82f6', border: 'none', borderRadius: 6, color: '#fff', fontSize: 13, cursor: 'pointer',
                  }}>{scanLoading ? '扫描中...' : '重新扫描'}</button>
                </div>
              </div>

              {scanLoading && <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>正在扫描全市场...</div>}

              {scanResults && !scanLoading && (
                <>
                  <div style={{ marginBottom: 12, fontSize: 13, color: '#9ca3af' }}>
                    共发现 {scanResults.total} 只符合条件的股票 · 更新: {scanResults.update_time}
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #374151' }}>
                        {['代码', '市场', '分数', '判定', 'Weinstein阶段', '市场环境', '入场类型'].map(h => (
                          <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 500 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {scanResults.results.map((s: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid #1f2937', cursor: 'pointer' }}
                          onClick={() => { setStockCode(s.code); setActiveTab('analysis'); loadAnalysis(s.code) }}>
                          <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontWeight: 600 }}>{s.code}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <span style={{ padding: '2px 6px', borderRadius: 4, fontSize: 10, background: s.market === 'A' ? '#16a34a30' : '#3b82f630', color: s.market === 'A' ? '#16a34a' : '#3b82f6' }}>
                              {s.market === 'A' ? 'A股' : '港股'}
                            </span>
                          </td>
                          <td style={{ padding: '8px 12px', fontWeight: 700, color: s.score >= 72 ? '#16a34a' : s.score >= 52 ? '#ca8a04' : '#6b7280' }}>{s.score}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: getVerdictStyle(s.verdict).bg, color: '#fff' }}>{s.verdict}</span>
                          </td>
                          <td style={{ padding: '8px 12px', color: s.weinstein_stage === 2 ? '#16a34a' : '#9ca3af' }}>Stage {s.weinstein_stage}</td>
                          <td style={{ padding: '8px 12px', color: s.market_regime === 'trending' ? '#16a34a' : '#9ca3af' }}>
                            {s.market_regime === 'trending' ? '趋势' : s.market_regime === 'developing' ? '形成中' : '震荡'}
                          </td>
                          <td style={{ padding: '8px 12px', color: s.entry_type !== 'none' ? '#3b82f6' : '#6b7280' }}>
                            {s.entry_type !== 'none' ? '有入场建议' : '暂无'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}

          {/* Sector Tab */}
          {activeTab === 'sector' && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>板块轮动分析</div>

              {sectorLoading && <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>加载板块数据...</div>}

              {sectorData && !sectorLoading && !sectorData.error && (
                <>
                  <div style={{ marginBottom: 16, display: 'flex', gap: 16, alignItems: 'center' }}>
                    <span style={{ fontSize: 13, color: '#9ca3af' }}>市场情绪:</span>
                    <span style={{
                      padding: '4px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                      background: sectorData.market_mood === '强势' ? '#16a34a20' : sectorData.market_mood === '偏弱' ? '#dc262620' : '#ca8a0420',
                      color: sectorData.market_mood === '强势' ? '#16a34a' : sectorData.market_mood === '偏弱' ? '#dc2626' : '#ca8a04',
                    }}>{sectorData.market_mood}</span>
                    <span style={{ fontSize: 12, color: '#6b7280' }}>共 {sectorData.total} 个板块</span>
                  </div>

                  {/* Strong sectors */}
                  {sectorData.strong_sectors && sectorData.strong_sectors.length > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#16a34a', marginBottom: 8 }}>🔥 领涨板块</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
                        {sectorData.strong_sectors.map((s: any, i: number) => (
                          <div key={i} style={{ background: '#111827', borderRadius: 8, padding: 12, border: '1px solid #16a34a30' }}>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{s.name}</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a', margin: '4px 0' }}>+{s.change_pct}%</div>
                            <div style={{ fontSize: 11, color: '#6b7280' }}>
                              涨{s.up_count} / 跌{s.down_count}
                              {s.lead_stock && ` · 领涨: ${s.lead_stock}`}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Weak sectors */}
                  {sectorData.weak_sectors && sectorData.weak_sectors.length > 0 && (
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#dc2626', marginBottom: 8 }}>❄️ 领跌板块</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
                        {sectorData.weak_sectors.map((s: any, i: number) => (
                          <div key={i} style={{ background: '#111827', borderRadius: 8, padding: 12, border: '1px solid #dc262630' }}>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{s.name}</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: '#dc2626', margin: '4px 0' }}>{s.change_pct}%</div>
                            <div style={{ fontSize: 11, color: '#6b7280' }}>
                              涨{s.up_count} / 跌{s.down_count}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Full sector table */}
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>全部板块排名</div>
                  <div style={{ maxHeight: 400, overflow: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #374151', position: 'sticky', top: 0, background: '#1f2937' }}>
                          {['排名', '板块', '涨跌幅%', '涨家数', '跌家数', '领涨股'].map(h => (
                            <th key={h} style={{ padding: '6px 8px', textAlign: 'left', color: '#9ca3af', fontWeight: 500 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sectorData.sectors.map((s: any, i: number) => (
                          <tr key={i} style={{ borderBottom: '1px solid #1f2937' }}>
                            <td style={{ padding: '6px 8px', color: '#6b7280' }}>{i + 1}</td>
                            <td style={{ padding: '6px 8px', fontWeight: 600, color: '#f3f4f6' }}>{s.name}</td>
                            <td style={{ padding: '6px 8px', fontWeight: 600, color: s.change_pct > 0 ? '#16a34a' : s.change_pct < 0 ? '#dc2626' : '#6b7280' }}>
                              {s.change_pct > 0 ? '+' : ''}{s.change_pct}%
                            </td>
                            <td style={{ padding: '6px 8px', color: '#16a34a' }}>{s.up_count}</td>
                            <td style={{ padding: '6px 8px', color: '#dc2626' }}>{s.down_count}</td>
                            <td style={{ padding: '6px 8px', color: '#9ca3af' }}>{s.lead_stock || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {sectorData?.error && <p style={{ color: '#dc2626' }}>{sectorData.error}</p>}
            </div>
          )}

          {/* Watchlist Tab */}
          {activeTab === 'watchlist' && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>⭐ 自选股管理</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {stockCode && (
                    <button onClick={addToWatchlist} style={{
                      padding: '6px 16px', background: '#16a34a', border: 'none', borderRadius: 6, color: '#fff', fontSize: 13, cursor: 'pointer',
                    }}>+ 添加当前股票</button>
                  )}
                  <button onClick={scanWatchlist} disabled={watchlistScanLoading} style={{
                    padding: '6px 16px', background: '#3b82f6', border: 'none', borderRadius: 6, color: '#fff', fontSize: 13, cursor: 'pointer',
                  }}>{watchlistScanLoading ? '扫描中...' : '🔍 扫描自选股'}</button>
                </div>
              </div>

              {watchlistLoading && <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>加载中...</div>}

              {/* Watchlist items */}
              {watchlist && watchlist.watchlist && watchlist.watchlist.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>共 {watchlist.total} 只自选股</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
                    {watchlist.watchlist.map((w: any, i: number) => (
                      <div key={i} style={{ background: '#111827', borderRadius: 8, padding: 12, border: '1px solid #374151' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <span style={{ fontWeight: 700 }}>{w.code}</span>
                            {w.name && <span style={{ color: '#9ca3af', marginLeft: 6, fontSize: 12 }}>{w.name}</span>}
                          </div>
                          <button onClick={async () => {
                            await axios.delete(`${API_BASE}/right-side/watchlist/${w.code}`)
                            loadWatchlist()
                          }} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 14 }}>×</button>
                        </div>
                        {w.last_verdict && (
                          <div style={{ marginTop: 4, fontSize: 11, color: w.last_verdict === '右侧确认' ? '#16a34a' : '#9ca3af' }}>
                            {w.last_verdict} · {w.last_score}分
                          </div>
                        )}
                        {w.note && <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{w.note}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Watchlist scan results */}
              {watchlistScan && !watchlistScanLoading && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>
                    扫描结果 · {watchlistScan.summary?.confirmed || 0} 只右侧确认
                  </div>
                  {watchlistScan.results && watchlistScan.results.length > 0 ? (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #374151' }}>
                          {['代码', '分数', '判定', '阶段', '入场价', '止损价'].map(h => (
                            <th key={h} style={{ padding: '8px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 500 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {watchlistScan.results.map((s: any, i: number) => (
                          <tr key={i} style={{ borderBottom: '1px solid #1f2937', cursor: 'pointer' }}
                            onClick={() => { setStockCode(s.code); setActiveTab('analysis'); doLoadAnalysis(s.code) }}>
                            <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontWeight: 600 }}>{s.code}</td>
                            <td style={{ padding: '8px 12px', fontWeight: 700, color: s.score >= 72 ? '#16a34a' : '#9ca3af' }}>{s.score}</td>
                            <td style={{ padding: '8px 12px' }}>
                              <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, background: getVerdictStyle(s.verdict).bg, color: '#fff' }}>{s.verdict}</span>
                            </td>
                            <td style={{ padding: '8px 12px', color: s.weinstein_stage === 2 ? '#16a34a' : '#9ca3af' }}>Stage {s.weinstein_stage}</td>
                            <td style={{ padding: '8px 12px', color: '#3b82f6' }}>{s.entry_price ? `¥${s.entry_price}` : '-'}</td>
                            <td style={{ padding: '8px 12px', color: '#dc2626' }}>{s.stop_loss ? `¥${s.stop_loss}` : '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>自选股为空，请先添加股票</div>
                  )}
                </div>
              )}

              {watchlistScan?.error && <p style={{ color: '#dc2626' }}>{watchlistScan.error}</p>}
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
