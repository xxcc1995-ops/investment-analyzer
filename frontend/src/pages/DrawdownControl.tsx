/**
 * 回撤控制 — 实战级回撤管理系统
 *
 * 三大板块：
 * 1. 理念与方法 — 六大实战止损方法论，每种含公式、适用场景、技术指标确认
 * 2. 实际分析 — 接入后端API，对任意股票做回撤健康诊断
 * 3. 检查清单 — 入场前自检
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { Tooltip } from 'antd'
import { PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState, ProgressBar } from '../components/ui'

const API_BASE = '/api'

const Tip = ({ text }: { text: string }) => (
  <Tooltip title={text} overlayStyle={{ maxWidth: 300 }}>
    <span className="tip-trigger">?</span>
  </Tooltip>
)

// ============================================================
// 类型定义（与后端 API 对齐）
// ============================================================

interface DrawdownEvent {
  start_date: string
  trough_date: string
  end_date: string | null
  depth_pct: number
  duration_days: number
  recovery_days: number | null
  ongoing_days?: number
  start_equity: number
  trough_equity: number
  recovered: boolean
}

interface WarningInfo {
  level: number
  label: string
  color: string
  action: string
  max_position_pct: number
  drawdown_pct: number
  duration_days?: number
}

interface RecoveryInfo {
  avg_recovery_days: number | null
  median_recovery_days: number | null
  max_recovery_days: number | null
  estimated_recovery_days: number | null
  confidence: string
  current_ongoing_days?: number
  current_depth?: number
  heuristic_baseline?: number | null
}

interface DrawdownResult {
  code: string
  days: number
  data_count: number
  fetch_time: string
  current_drawdown_pct: number
  max_drawdown_pct: number
  is_at_peak: boolean
  current_equity: number
  current_peak: number
  calmar_ratio: number | null
  sortino_ratio: number | null
  current_volatility: number | null
  current_drawdown_days: number
  current_price?: number
  score: number
  verdict: string
  signals: string[]
  warning: WarningInfo
  position_advice: { max_position_pct: number; action: string; level: number; duration_days: number }
  position_sizing?: {
    atr_method: { shares: number; position_value: number; position_pct: number; risk_per_share: number; stop_loss_price: number } | null
    vol_inverse_method: { position_pct: number; target_vol: number; current_vol: number } | null
    kelly_method: { position_pct: number; kelly_fraction: number; note: string } | null
    recommended: { shares: number; position_pct: number; position_value: number; max_loss: number }
    total_capital: number
  }
  stop_loss?: Record<string, any>
  var_cvar?: { var_95: number | null; cvar_95: number | null; var_99: number | null; cvar_99: number | null }
  ulcer_index?: number | null
  ulcer_performance_index?: number | null
  gain_to_pain_ratio?: number | null
  current_atr?: number | null
  current_atr_pct?: number | null
  ma20?: number | null
  ma60?: number | null
  recent_high?: number
  drawdowns: DrawdownEvent[]
  drawdown_count: number
  distribution: {
    count: number
    avg_depth: number
    median_depth: number
    max_depth: number
    min_depth: number
    histogram: { range: string; count: number; label: string }[]
  }
  drawdown_percentiles?: {
    p10: number | null; p25: number | null; p50: number | null
    p75: number | null; p90: number | null; p95: number | null; p99: number | null
    count: number
  }
  recovery: RecoveryInfo
  chart: {
    equity: { dates: string[]; values: number[]; peaks: (number | null)[] }
    underwater: { dates: string[]; values: number[] }
    vol_adjusted: { date: string; raw_drawdown: number; vol_adjusted_drawdown: number; volatility: number | null }[]
    distribution: { range: string; count: number; label: string }[]
    atr?: { date: string; atr: number; atr_pct: number }[]
  }
}

// ============================================================
// 六大实战止损方法数据
// ============================================================

const STOP_METHODS = [
  {
    id: 'chandelier',
    icon: '🕯️',
    name: 'ATR吊灯止损 (Chandelier Exit)',
    origin: 'Chuck LeBeau · 海龟交易系统改良',
    formula: '止损价 = 最高价 - N × ATR（N通常取2~3）',
    formulaDetail: 'ATR = 过去14天真实波幅的均值。N=2适合短线，N=3适合中长线。止损线像吊灯一样悬挂在价格上方，随着价格上涨自动抬升，但价格下跌时不下移。',
    whenToUse: '趋势明确的个股，尤其是突破新高后的持仓保护',
    pros: '自动适应波动率；波动大时止损宽松（避免被震出），波动小时止损紧凑',
    cons: '震荡市中ATR偏大，止损可能过宽；需要每日更新止损位',
    confirmSignals: [
      'ADX > 25 确认趋势环境（止损更可靠）',
      'MACD柱状图由正转负 → 动量衰减，提前警觉',
      '跌破吊灯止损线 + 放量 → 确认离场',
      'SAR翻转到价格上方 → 趋势反转确认',
    ],
    color: '#f59e0b',
  },
  {
    id: 'ma_stop',
    icon: '📊',
    name: '均线止损法',
    origin: 'Stan Weinstein · 30周均线体系',
    formula: '收盘价跌破关键均线（MA20短线 / MA60中线 / MA120长线）',
    formulaDetail: 'Weinstein只在Stage 2（上升趋势）买入，跌破30周均线=Stage 3或4，必须离场。A股实战中，MA20适合波段，MA60适合中线，MA120适合长线。',
    whenToUse: '趋势跟随策略，尤其是已持有并在趋势中的仓位',
    pros: '简单直观；均线是共识支撑位，跌破说明共识改变',
    cons: '均线滞后，可能在跌破前已回撤较多；震荡市频繁假跌破',
    confirmSignals: [
      '连续2天收盘价在均线下方 → 确认跌破（非假突破）',
      '均线由上升转为走平或拐头 → 趋势动能衰竭',
      '成交量放大跌破 → 主力出逃，信号更强',
      'RSI从超买区快速回落至50以下 → 短期动量崩溃',
    ],
    color: '#3b82f6',
  },
  {
    id: 'sar',
    icon: '⚡',
    name: 'SAR抛物线止损',
    origin: 'J. Welles Wilder · 技术交易系统新概念',
    formula: 'SAR(t) = SAR(t-1) + AF × (EP - SAR(t-1))',
    formulaDetail: 'AF=加速因子（初始0.02，每次创新高+0.02，最大0.2）。EP=极值点（上升趋势中为最高价）。SAR点在价格下方=持有多头，翻转到上方=止损信号。AF越大，SAR越贴近价格，止损越紧。',
    whenToUse: '趋势明确且持续的行情，AF自动收紧止损锁定利润',
    pros: '完全自动化，无需主观判断；趋势越强止损越紧，天然的移动止损',
    cons: '震荡市频繁翻转，产生大量假信号；需要配合其他指标过滤',
    confirmSignals: [
      'SAR翻转到价格上方 + ADX > 20 → 趋势环境中的真反转',
      'SAR翻转 + 成交量放大 → 信号可靠性大幅提升',
      'SAR翻转 + MACD死叉 → 多重确认，果断离场',
      'SAR翻转但ADX < 15 → 震荡市假信号，可忽略',
    ],
    color: '#8b5cf6',
  },
  {
    id: 'vol_sizing',
    icon: '📐',
    name: '波动率自适应仓位 (Vol-Adjusted Sizing)',
    origin: '文艺复兴科技 · Medallion基金核心逻辑',
    formula: '仓位比例 = 风险预算 / (ATR × 股价) × 100%',
    formulaDetail: '假设总资金100万，单笔风险预算1%（即最多亏1万）。某股ATR=2元，股价=50元。则可买股数 = 10000 / 2 = 5000股。波动率越大，自动缩小仓位；波动率越小，自动放大仓位。让每笔交易的"风险贡献"相等。',
    whenToUse: '所有交易的仓位管理，尤其是组合中有多只股票时',
    pros: '科学量化；高波动股票自动降仓位，避免单笔巨亏',
    cons: 'ATR变化时需要动态调整仓位，操作频繁；极端行情ATR可能失真',
    confirmSignals: [
      '当前ATR > 20日均值的1.5倍 → 波动率异常放大，仓位减半',
      '20日年化波动率 > 50% → 高波动股票，单笔风险降至0.5%',
      '组合总波动率 > 30% → 整体仓位过高，需要减仓',
      'ADX显示震荡市（<20）→ 降低仓位或空仓等待',
    ],
    color: '#14b8a6',
  },
  {
    id: 'trailing_lock',
    icon: '🔒',
    name: '阶梯止盈锁利',
    origin: '实战交易员通用 · 海龟系统的分批止盈变体',
    formula: '盈利5% → 保本止损 | 盈利10% → 锁定5%利润 | 盈利20% → 锁定10%利润',
    formulaDetail: '核心思想：让利润奔跑，但绝不让盈利变亏损。每达到一个利润台阶，就把止损位上移到锁定的利润水平。可以灵活调整台阶（3%/8%/15%等），但原则不变：只往上移，永不往下移。',
    whenToUse: '已入场且开始盈利的持仓，尤其是波段交易',
    pros: '心理压力小（已锁利）；给趋势足够空间发展',
    cons: '可能在回调时被止盈出局，错过后续大涨；需要纪律严格执行',
    confirmSignals: [
      '盈利达到5%时，检查ADX是否>25（趋势强则放宽台阶）',
      '盈利达到10%时，观察周线是否同步（多时间框架确认）',
      '盈利达到20%时，考虑减仓1/3锁定部分利润',
      'KST动量指标出现顶背离 → 加速止盈上移',
    ],
    color: '#22c55e',
  },
  {
    id: 'time_stop',
    icon: '⏰',
    name: '时间止损',
    origin: 'Mark Minervini · SEPA趋势模板',
    formula: '持仓超过N个交易日（通常20~60天）未达预期 → 无条件退出',
    formulaDetail: 'Minervini的核心观点：如果一只股票在买入后长时间没有启动，说明你的判断可能有误。时间是有成本的——资金被占用=机会成本。20天内应该看到明显的向上运动，否则这笔交易的"故事"可能不成立。',
    whenToUse: '突破买入后的持仓管理，尤其是形态突破（杯柄、VCP等）',
    pros: '避免资金长期被套在不涨的股票中；释放资金寻找更好的机会',
    cons: '可能在刚止损后股票就启动；需要配合其他信号判断',
    confirmSignals: [
      '买入后20天内股价未创新高 → 弱势信号，准备退出',
      '买入后缩量横盘超过30天 → 市场不认可，考虑退出',
      '同期大盘上涨但个股横盘 → 相对弱势，优先退出',
      '突破后回踩超过买入价的8% → 形态失败，止损退出',
    ],
    color: '#ef4444',
  },
]

const LADDER = [
  { range: '< 3%', level: '安全', color: '#22c55e', pos: '100%', action: '正常持有，享受复利', techConfirm: '无需特别关注' },
  { range: '3-8%', level: '关注', color: '#3b82f6', pos: '100%', action: '关注走势变化，设好心理止损位', techConfirm: '检查ADX是否>20、MACD柱状图方向' },
  { range: '8-15%', level: '警戒', color: '#eab308', pos: '80%', action: '减仓至80%，设置止损线', techConfirm: '确认是否跌破MA20、SAR是否翻转' },
  { range: '15-25%', level: '危险', color: '#f97316', pos: '60%', action: '减仓至60%，严格执行止损', techConfirm: '检查是否跌破MA60、ADX趋势方向' },
  { range: '25-40%', level: '严重', color: '#ef4444', pos: '40%', action: '减仓至40%，考虑对冲或换仓', techConfirm: '确认Weinstein阶段是否转为Stage 4' },
  { range: '> 40%', level: '极端', color: '#991b1b', pos: '20%', action: '减仓至20%，等待企稳再加仓', techConfirm: '远离，等待右侧信号重新出现' },
]

const CHECKLIST = [
  { q: '这笔交易的最大回撤我能承受吗？', hint: '如果会失眠，仓位太重了。用ATR计算：每股风险=ATR×2，最大亏损=股数×每股风险', category: '仓位' },
  { q: '我设了止损位吗？止损位是基于逻辑还是情绪？', hint: '基于ATR或关键支撑位，而非"再跌一点我就卖"。止损在入场前就定好', category: '止损' },
  { q: '当前回撤是系统性的还是个股的？', hint: '大盘跌10%和个股跌10%意义完全不同。检查大盘ADX和MA60位置', category: '环境' },
  { q: '回撤已经持续多久了？', hint: '超过3个月的回撤需要重新审视基本面。时间止损：20天内未启动就该警惕', category: '时间' },
  { q: '我在加仓前确认趋势了吗？', hint: '不要在下跌中抄底，等右侧信号。检查ADX>25、MACD金叉、站上MA20', category: '趋势' },
  { q: '我的组合总波动率是多少？', hint: '组合波动率>30%说明仓位过重。用波动率自适应仓位：每只股票风险贡献相等', category: '组合' },
  { q: '这只股票的Calmar比率如何？', hint: 'Calmar=年化收益/最大回撤。>1说明回撤被充分补偿，<0.5说明风险收益比差', category: '质量' },
]

// ============================================================
// 主组件
// ============================================================

export default function DrawdownControl() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'analysis'>('philosophy')
  const [expandedMethod, setExpandedMethod] = useState<string | null>(null)

  // 分析板块状态
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState<{ code: string; name: string }[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DrawdownResult | null>(null)
  const [error, setError] = useState('')
  const [days, setDays] = useState(500)
  const [analysisTab, setAnalysisTab] = useState<'overview' | 'history' | 'recovery' | 'risk'>('overview')
  const searchTimer = useRef<any>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 搜索股票
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!search.trim()) { setSearchResults([]); return }
    searchTimer.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API_BASE}/stocks/search`, { params: { keyword: search.trim() } })
        setSearchResults(res.data.results || [])
        setShowDropdown(true)
      } catch { setSearchResults([]) }
    }, 300)
  }, [search])

  // 点击外部关闭下拉
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setShowDropdown(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleAnalyze = async (code: string) => {
    if (!code) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await axios.get(`${API_BASE}/drawdown/${code}`, { params: { days } })
      setResult(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || '分析失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectStock = (code: string, name: string) => {
    setSearch(`${name} (${code})`)
    setShowDropdown(false)
    handleAnalyze(code)
  }

  // ============================================================
  // 图表 Options
  // ============================================================

  const equityChartOption = useMemo(() => {
    if (!result?.chart?.equity) return null
    const { dates, values, peaks } = result.chart.equity
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['权益曲线', '历史最高'], textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 60, right: 20, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#21262d' } } },
      dataZoom: [{ type: 'inside', start: 50, end: 100 }, { type: 'slider', start: 50, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(88,166,255,0.15)', handleStyle: { color: '#58a6ff' } }],
      series: [
        { name: '权益曲线', type: 'line', data: values, smooth: true, symbol: 'none', lineStyle: { color: '#58a6ff', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(88,166,255,0.3)' }, { offset: 1, color: 'rgba(88,166,255,0.02)' }] } } },
        { name: '历史最高', type: 'line', data: peaks, smooth: true, symbol: 'none', lineStyle: { color: '#f59e0b', width: 1, type: 'dashed' } },
      ],
    }
  }, [result])

  const underwaterChartOption = useMemo(() => {
    if (!result?.chart?.underwater) return null
    const { dates, values } = result.chart.underwater
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', formatter: (params: any) => `${params[0]?.axisValue}<br/>回撤: ${params[0]?.value?.toFixed(2)}%` },
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: '#21262d' } }, max: 0 },
      dataZoom: [{ type: 'inside', start: 50, end: 100 }, { type: 'slider', start: 50, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(239,68,68,0.15)', handleStyle: { color: '#ef4444' } }],
      series: [{
        type: 'line', data: values, smooth: true, symbol: 'none',
        lineStyle: { color: '#ef4444', width: 1.5 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(239,68,68,0.02)' }, { offset: 1, color: 'rgba(239,68,68,0.4)' }] } },
        markLine: {
          data: [
            { yAxis: -5, lineStyle: { color: '#eab308', type: 'dashed', width: 1 }, label: { formatter: '-5%', color: '#eab308', fontSize: 10 } },
            { yAxis: -10, lineStyle: { color: '#f97316', type: 'dashed', width: 1 }, label: { formatter: '-10%', color: '#f97316', fontSize: 10 } },
            { yAxis: -15, lineStyle: { color: '#ef4444', type: 'dashed', width: 1 }, label: { formatter: '-15%', color: '#ef4444', fontSize: 10 } },
            { yAxis: -20, lineStyle: { color: '#dc2626', type: 'dashed', width: 1 }, label: { formatter: '-20%', color: '#dc2626', fontSize: 10 } },
          ],
        },
      }],
    }
  }, [result])

  const distributionChartOption = useMemo(() => {
    if (!result?.chart?.distribution?.length) return null
    const data = result.chart.distribution
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: data.map(d => d.label), axisLabel: { color: '#9ca3af', fontSize: 10, rotate: 30 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#21262d' } }, minInterval: 1 },
      series: [{
        type: 'bar', data: data.map(d => d.count),
        itemStyle: {
          color: (params: any) => {
            const colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#dc2626', '#991b1b', '#7f1d1d', '#450a0a']
            return colors[params.dataIndex] || '#ef4444'
          },
          borderRadius: [4, 4, 0, 0],
        },
        barWidth: '60%',
        label: { show: true, position: 'top', color: '#9ca3af', fontSize: 11, formatter: '{c}次' },
      }],
    }
  }, [result])

  const volAdjChartOption = useMemo(() => {
    if (!result?.chart?.vol_adjusted?.length) return null
    const data = result.chart.vol_adjusted
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['原始回撤', '波动率调整回撤'], textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 60, right: 60, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: data.map(d => d.date), axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: [
        { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: '#21262d' } } },
        { type: 'value', axisLabel: { color: '#f59e0b', formatter: (v: number) => `${v}%` }, splitLine: { show: false } },
      ],
      dataZoom: [{ type: 'inside', start: 50, end: 100 }],
      series: [
        { name: '原始回撤', type: 'line', data: data.map(d => d.raw_drawdown), smooth: true, symbol: 'none', lineStyle: { color: '#ef4444', width: 1.5 }, areaStyle: { color: 'rgba(239,68,68,0.1)' } },
        { name: '波动率调整回撤', type: 'line', data: data.map(d => d.vol_adjusted_drawdown), smooth: true, symbol: 'none', yAxisIndex: 1, lineStyle: { color: '#f59e0b', width: 1.5 } },
      ],
    }
  }, [result])

  // ============================================================
  // 辅助渲染组件
  // ============================================================

  const MetricCard = ({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) => (
    <div style={{ background: '#111827', borderRadius: 8, padding: 14, textAlign: 'center' as const }}>
      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || '#f3f4f6' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>{sub}</div>}
    </div>
  )

  const ScoreRing = ({ score, verdict }: { score: number; verdict: string }) => {
    const color = score >= 80 ? '#22c55e' : score >= 60 ? '#eab308' : score >= 40 ? '#f97316' : '#ef4444'
    const circumference = 2 * Math.PI * 45
    const offset = circumference - (score / 100) * circumference
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <svg width="120" height="120" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="45" fill="none" stroke="#374151" strokeWidth="8" />
          <circle cx="60" cy="60" r="45" fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" transform="rotate(-90 60 60)" />
          <text x="60" y="55" textAnchor="middle" fill={color} fontSize="28" fontWeight="800">{score}</text>
          <text x="60" y="75" textAnchor="middle" fill="#9ca3af" fontSize="12">{verdict}</text>
        </svg>
        <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>健康评分</div>
      </div>
    )
  }

  const WarningGauge = ({ warning }: { warning: WarningInfo }) => {
    const levels = [
      { label: '安全', color: '#22c55e', max: 3 },
      { label: '关注', color: '#3b82f6', max: 5 },
      { label: '警戒', color: '#eab308', max: 10 },
      { label: '危险', color: '#f97316', max: 15 },
      { label: '严重', color: '#ef4444', max: 20 },
      { label: '极端', color: '#991b1b', max: 100 },
    ]
    const currentLevel = levels[warning.level] || levels[0]
    return (
      <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>⚠️ 阶梯预警系统</div>
        <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
          {levels.map((lv, i) => (
            <div key={i} style={{
              flex: 1, height: 32, borderRadius: 6,
              background: i <= warning.level ? lv.color : '#111827',
              border: i === warning.level ? `2px solid ${lv.color}` : '1px solid #374151',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: i <= warning.level ? 700 : 400,
              color: i <= warning.level ? '#fff' : '#6b7280',
            }}>{lv.label}</div>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: currentLevel.color, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, fontWeight: 800, color: '#fff', boxShadow: `0 0 20px ${currentLevel.color}40`,
          }}>{warning.level}</div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: currentLevel.color }}>{currentLevel.label}</div>
            <div style={{ fontSize: 13, color: '#9ca3af' }}>当前回撤 {warning.drawdown_pct}%</div>
          </div>
        </div>
        <div style={{ background: '#111827', borderRadius: 8, padding: 14, border: `1px solid ${currentLevel.color}30` }}>
          <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 4 }}>📋 建议操作</div>
          <div style={{ fontSize: 14, color: '#f3f4f6', lineHeight: 1.6 }}>{warning.action}</div>
          <div style={{ fontSize: 13, color: currentLevel.color, marginTop: 8, fontWeight: 600 }}>
            建议最大仓位: {warning.max_position_pct}%
          </div>
        </div>
      </div>
    )
  }

  // ============================================================
  // 渲染：理念与方法 Tab
  // ============================================================

  const renderPhilosophy = () => (
    <>
      {/* 核心认知 */}
      <div style={{
        background: 'linear-gradient(135deg, #1e3a5f 0%, #1f2937 100%)',
        borderRadius: 12, padding: '28px 32px', marginBottom: 32,
        border: '1px solid #2563eb30', textAlign: 'center',
      }}>
        <div style={{ fontSize: 13, color: '#60a5fa', marginBottom: 12, letterSpacing: 2 }}>复利的敌人</div>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
          {[
            { loss: '-10%', need: '+11%', safe: true },
            { loss: '-20%', need: '+25%', safe: true },
            { loss: '-30%', need: '+43%', safe: false },
            { loss: '-50%', need: '+100%', safe: false },
            { loss: '-70%', need: '+233%', safe: false },
          ].map((d, i) => (
            <div key={i} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: d.safe ? '#eab308' : '#ef4444' }}>{d.loss}</div>
              <div style={{ fontSize: 11, color: '#6b7280', margin: '4px 0' }}>需要</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: d.safe ? '#f59e0b' : '#dc2626' }}>{d.need}</div>
              <div style={{ fontSize: 10, color: '#6b7280' }}>才能回本</div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 16 }}>
          回撤越大，回本难度呈指数级增长 —— 这就是为什么风控永远排在第一位
        </div>
      </div>

      {/* A股真实案例 */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
          📜 A股历史上的回撤教训
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {[
            { year: '2015', title: '杠杆股灾', drop: '-49.1%', days: '52个交易日', lesson: '上证从5178跌到2638。杠杆+千股跌停=流动性枯竭。教训：永远不要用杠杆，极端行情中止损单可能无法成交。', color: '#dc2626' },
            { year: '2018', title: '贸易摩擦熊市', drop: '-30.2%', days: '全年阴跌', lesson: '上证从3587跌到2493。缓跌比急跌更可怕——每天跌一点，不知不觉亏30%。教训：均线止损在缓跌中尤其重要。', color: '#f97316' },
            { year: '2022', title: '多重利空调整', drop: '-22.8%', duration: '4个月', lesson: '上证从3400跌到2646。地产+疫情+美联储加息三重打击。教训：宏观环境恶化时，技术止损也要服从基本面判断。', color: '#eab308' },
          ].map((c, i) => (
            <div key={i} style={{
              background: '#1f2937', borderRadius: 10, padding: 20,
              border: `1px solid ${c.color}40`, borderTop: `3px solid ${c.color}`,
            }}>
              <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 4 }}>{c.year}</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#f3f4f6', marginBottom: 8 }}>{c.title}</div>
              <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 11, color: '#6b7280' }}>最大跌幅</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: c.color }}>{c.drop}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#6b7280' }}>持续时间</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginTop: 4 }}>{c.days || c.duration}</div>
                </div>
              </div>
              <div style={{ fontSize: 12, color: '#d1d5db', lineHeight: 1.7 }}>{c.lesson}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 六大实战止损方法 */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
          🛠️ 六大实战止损方法
          <Tip text="每种方法都有适用场景，没有万能止损。实战中建议组合使用：ATR吊灯止损做主止损 + 阶梯止盈锁利做移动止损 + 时间止损做兜底。" />
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {STOP_METHODS.map(m => {
            const isExpanded = expandedMethod === m.id
            return (
              <div key={m.id} style={{
                background: '#1f2937', borderRadius: 10,
                border: isExpanded ? `1px solid ${m.color}` : '1px solid #374151',
                overflow: 'hidden', transition: 'border-color 0.2s',
              }}>
                {/* 标题栏 */}
                <div
                  onClick={() => setExpandedMethod(isExpanded ? null : m.id)}
                  style={{
                    padding: '16px 20px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14,
                  }}
                >
                  <span style={{ fontSize: 28 }}>{m.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, color: '#f3f4f6' }}>{m.name}</div>
                    <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{m.origin}</div>
                  </div>
                  <div style={{
                    padding: '4px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    background: `${m.color}20`, color: m.color,
                  }}>
                    {isExpanded ? '收起' : '展开详情'}
                  </div>
                </div>

                {/* 展开内容 */}
                {isExpanded && (
                  <div style={{ padding: '0 20px 20px', borderTop: '1px solid #374151' }}>
                    {/* 公式 */}
                    <div style={{
                      background: '#111827', borderRadius: 8, padding: 16, marginTop: 16, marginBottom: 16,
                      border: `1px solid ${m.color}30`,
                    }}>
                      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>📐 计算公式</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: m.color, fontFamily: 'monospace', marginBottom: 8 }}>
                        {m.formula}
                      </div>
                      <div style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.8 }}>{m.formulaDetail}</div>
                    </div>

                    {/* 适用场景 + 优缺点 */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 12 }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>🎯 适用场景</div>
                        <div style={{ fontSize: 13, color: '#f3f4f6', lineHeight: 1.6 }}>{m.whenToUse}</div>
                      </div>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 12 }}>
                        <div style={{ fontSize: 11, color: '#22c55e', marginBottom: 6 }}>✅ 优点</div>
                        <div style={{ fontSize: 13, color: '#f3f4f6', lineHeight: 1.6 }}>{m.pros}</div>
                      </div>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 12 }}>
                        <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 6 }}>⚠️ 缺点</div>
                        <div style={{ fontSize: 13, color: '#f3f4f6', lineHeight: 1.6 }}>{m.cons}</div>
                      </div>
                    </div>

                    {/* 技术指标确认信号 */}
                    <div style={{ background: '#111827', borderRadius: 8, padding: 16, border: '1px solid #374151' }}>
                      <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 10 }}>
                        📡 技术指标确认信号
                        <Tip text="止损不应仅凭单一信号，需要用其他技术指标做交叉确认，减少假信号。以下信号按可靠性从高到低排列。" />
                      </div>
                      {m.confirmSignals.map((s, i) => (
                        <div key={i} style={{
                          display: 'flex', alignItems: 'flex-start', gap: 10,
                          padding: '8px 0', borderBottom: i < m.confirmSignals.length - 1 ? '1px solid #30363d' : 'none',
                        }}>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                            width: 20, height: 20, borderRadius: '50%', background: `${m.color}30`, color: m.color,
                            fontSize: 10, fontWeight: 700, flexShrink: 0, marginTop: 1,
                          }}>{i + 1}</span>
                          <span style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.6 }}>{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 阶梯预警 + 技术确认 */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
          📐 阶梯式仓位管理 + 技术确认
          <Tip text="桥水的阶梯减仓方法论：不同回撤深度对应不同仓位上限。每一级都有技术指标做确认，避免情绪化操作。" />
        </h2>
        <div style={{ background: '#1f2937', borderRadius: 10, border: '1px solid #374151', overflow: 'hidden' }}>
          {/* Visual bar */}
          <div style={{ display: 'flex', height: 48 }}>
            {LADDER.map((l, i) => (
              <div key={i} style={{
                flex: 1, background: l.color, display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, color: '#fff',
              }}>{l.level}</div>
            ))}
          </div>
          {/* Table */}
          <div style={{ padding: 16 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #374151' }}>
                  {['回撤区间', '风险级别', '建议仓位', '操作建议', '技术确认'].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {LADDER.map((l, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #30363d' }}>
                    <td style={{ padding: '10px 12px', color: l.color, fontWeight: 600 }}>{l.range}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{
                        padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: `${l.color}20`, color: l.color,
                      }}>{l.level}</span>
                    </td>
                    <td style={{ padding: '10px 12px', color: '#f3f4f6', fontWeight: 600 }}>{l.pos}</td>
                    <td style={{ padding: '10px 12px', color: '#9ca3af' }}>{l.action}</td>
                    <td style={{ padding: '10px 12px', color: '#60a5fa', fontSize: 12 }}>{l.techConfirm}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 检查清单 */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
          ✅ 入场前检查清单
        </h2>
        <div style={{ background: '#1f2937', borderRadius: 10, padding: 20, border: '1px solid #374151' }}>
          {CHECKLIST.map((c, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 12,
              padding: '14px 0', borderBottom: i < CHECKLIST.length - 1 ? '1px solid #30363d' : 'none',
            }}>
              <div style={{
                width: 24, height: 24, borderRadius: 6, flexShrink: 0,
                border: '2px solid #4b5563', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, color: '#6b7280', marginTop: 1,
              }}>{i + 1}</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 14, color: '#f3f4f6', fontWeight: 500, lineHeight: 1.6 }}>{c.q}</span>
                  <span style={{
                    padding: '1px 6px', borderRadius: 3, fontSize: 10,
                    background: '#374151', color: '#9ca3af',
                  }}>{c.category}</span>
                </div>
                <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>💡 {c.hint}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部引用 */}
      <div style={{
        textAlign: 'center', padding: '32px 20px', color: '#6b7280', fontSize: 13, lineHeight: 1.8,
        borderTop: '1px solid #374151',
      }}>
        <div style={{ fontSize: 16, color: '#9ca3af', fontStyle: 'italic', marginBottom: 8 }}>
          "风险管理的目标不是让你赚更多，而是让你活得足够久，等到该赚的那一天。"
        </div>
        <div style={{ fontSize: 11 }}>— 所有顶级投资者的共识</div>
      </div>
    </>
  )

  // ============================================================
  // 渲染：实战分析 Tab
  // ============================================================

  const renderAnalysis = () => (
    <>
      {/* 搜索栏 */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }} ref={dropdownRef}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            onFocus={() => searchResults.length > 0 && setShowDropdown(true)}
            placeholder="输入股票代码或名称（如 000001、贵州茅台）"
            style={{
              width: '100%', padding: '10px 14px', borderRadius: 8,
              background: '#1f2937', border: '1px solid #374151', color: '#f3f4f6',
              fontSize: 14, outline: 'none',
            }}
          />
          {showDropdown && searchResults.length > 0 && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, right: 0,
              background: '#1f2937', border: '1px solid #374151', borderRadius: 8,
              marginTop: 4, zIndex: 100, maxHeight: 240, overflow: 'auto',
            }}>
              {searchResults.map((s, i) => (
                <div key={i} onClick={() => handleSelectStock(s.code, s.name)}
                  style={{ padding: '8px 14px', cursor: 'pointer', borderBottom: '1px solid #30363d', fontSize: 13 }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#374151')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <span style={{ color: '#58a6ff' }}>{s.code}</span>
                  <span style={{ color: '#f3f4f6', marginLeft: 8 }}>{s.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <select value={days} onChange={e => setDays(Number(e.target.value))}
          style={{ padding: '10px 14px', borderRadius: 8, background: '#1f2937', border: '1px solid #374151', color: '#f3f4f6', fontSize: 13 }}>
          <option value={250}>1年</option>
          <option value={500}>2年</option>
          <option value={750}>3年</option>
          <option value={1250}>5年</option>
          <option value={2000}>8年</option>
        </select>
        <button onClick={() => { const m = search.match(/(\d{5,6})/); if (m) handleAnalyze(m[1]) }}
          disabled={loading} style={{
            padding: '10px 24px', borderRadius: 8, border: 'none',
            background: loading ? '#374151' : '#3b82f6', color: '#fff',
            fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer',
          }}>
          {loading ? '分析中...' : '🔍 分析'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{ background: '#7f1d1d20', border: '1px solid #ef4444', borderRadius: 8, padding: 14, color: '#ef4444', marginBottom: 24, fontSize: 13 }}>
          ❌ {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <div>正在分析回撤数据...</div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          {/* Stock Header */}
          <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20, marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#f3f4f6' }}>{result.code}</div>
              <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>
                数据量: {result.data_count}天 | 分析周期: {result.days}天 | 获取时间: {result.fetch_time}
              </div>
            </div>
            <ScoreRing score={result.score} verdict={result.verdict} />
          </div>

          {/* Signals */}
          {result.signals.length > 0 && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>📢 风险信号</div>
              {result.signals.map((s, i) => (
                <div key={i} style={{ fontSize: 13, color: '#fbbf24', padding: '3px 0' }}>{s}</div>
              ))}
            </div>
          )}

          {/* Core Metrics Row 1 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 12 }}>
            <MetricCard label="当前回撤" value={`${result.current_drawdown_pct}%`} color={result.current_drawdown_pct > 10 ? '#ef4444' : result.current_drawdown_pct > 5 ? '#eab308' : '#22c55e'} />
            <MetricCard label="最大回撤" value={`${result.max_drawdown_pct}%`} color="#ef4444" />
            <MetricCard label="Calmar比率" value={result.calmar_ratio ?? 'N/A'} sub="年化收益/最大回撤" color={result.calmar_ratio && result.calmar_ratio > 0.5 ? '#22c55e' : '#eab308'} />
            <MetricCard label="Sortino比率" value={result.sortino_ratio ?? 'N/A'} sub="收益/下行风险" color={result.sortino_ratio && result.sortino_ratio > 1 ? '#22c55e' : '#eab308'} />
            <MetricCard label="当前波动率" value={result.current_volatility ? `${result.current_volatility}%` : 'N/A'} sub="20日年化" />
            <MetricCard label="当前ATR" value={result.current_atr ?? 'N/A'} sub={result.current_atr_pct ? `占比${result.current_atr_pct}%` : ''} />
            <MetricCard label="是否创新高" value={result.is_at_peak ? '✅ 是' : '❌ 否'} color={result.is_at_peak ? '#22c55e' : '#ef4444'} />
            <MetricCard label="回撤次数" value={result.drawdown_count} sub="历史>3%回撤" />
            <MetricCard label="建议仓位" value={`${result.position_advice.max_position_pct}%`} sub="基于当前回撤" color={result.position_advice.max_position_pct >= 70 ? '#22c55e' : result.position_advice.max_position_pct >= 30 ? '#eab308' : '#ef4444'} />
            <MetricCard label="回撤持续" value={result.current_drawdown_days > 0 ? `${result.current_drawdown_days}天` : '-'} sub={result.current_drawdown_days > 180 ? '超半年' : result.current_drawdown_days > 90 ? '超3个月' : ''} color={result.current_drawdown_days > 365 ? '#ef4444' : result.current_drawdown_days > 180 ? '#f97316' : '#9ca3af'} />
          </div>

          {/* Institutional Metrics Row 2 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 20 }}>
            <MetricCard label="VaR(95%)" value={result.var_cvar?.var_95 != null ? `${result.var_cvar.var_95}%` : 'N/A'} sub="年化最大损失" color="#f97316" />
            <MetricCard label="CVaR(95%)" value={result.var_cvar?.cvar_95 != null ? `${result.var_cvar.cvar_95}%` : 'N/A'} sub="尾部平均损失" color="#ef4444" />
            <MetricCard label="VaR(99%)" value={result.var_cvar?.var_99 != null ? `${result.var_cvar.var_99}%` : 'N/A'} sub="极端最大损失" color="#ef4444" />
            <MetricCard label="Ulcer Index" value={result.ulcer_index ?? 'N/A'} sub={result.ulcer_index && result.ulcer_index < 5 ? '优秀' : result.ulcer_index && result.ulcer_index < 10 ? '良好' : result.ulcer_index && result.ulcer_index < 20 ? '一般' : result.ulcer_index ? '差' : ''} color={result.ulcer_index && result.ulcer_index < 5 ? '#22c55e' : result.ulcer_index && result.ulcer_index < 10 ? '#eab308' : result.ulcer_index && result.ulcer_index < 20 ? '#f97316' : '#ef4444'} />
            <MetricCard label="UPI" value={result.ulcer_performance_index ?? 'N/A'} sub="收益/溃疡指数" color={result.ulcer_performance_index && result.ulcer_performance_index > 1 ? '#22c55e' : '#eab308'} />
            <MetricCard label="GPR" value={result.gain_to_pain_ratio ?? 'N/A'} sub="收益/痛苦比" color={result.gain_to_pain_ratio && result.gain_to_pain_ratio > 1 ? '#22c55e' : '#eab308'} />
          </div>

          {/* Tab Bar */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            {(['overview', 'history', 'recovery', 'risk'] as const).map(tab => (
              <button key={tab} onClick={() => setAnalysisTab(tab)}
                style={{
                  padding: '8px 20px', borderRadius: 8, border: 'none', fontSize: 13, fontWeight: 600,
                  background: analysisTab === tab ? '#3b82f6' : '#1f2937', color: analysisTab === tab ? '#fff' : '#9ca3af',
                  cursor: 'pointer',
                }}>
                {tab === 'overview' ? '📊 总览' : tab === 'history' ? '📜 历史回撤' : tab === 'recovery' ? '🔄 恢复分析' : '🛡️ 风控建议'}
              </button>
            ))}
          </div>

          {/* Tab: Overview */}
          {analysisTab === 'overview' && (
            <>
              <div style={{ marginBottom: 20 }}>
                <WarningGauge warning={result.warning} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {equityChartOption && (
                  <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>📈 权益曲线</div>
                    <ReactECharts option={equityChartOption} style={{ height: 320 }} notMerge />
                  </div>
                )}
                {underwaterChartOption && (
                  <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>🌊 水下曲线（回撤深度）</div>
                    <ReactECharts option={underwaterChartOption} style={{ height: 320 }} notMerge />
                  </div>
                )}
                {distributionChartOption && (
                  <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>📊 回撤分布</div>
                    <ReactECharts option={distributionChartOption} style={{ height: 320 }} notMerge />
                  </div>
                )}
                {volAdjChartOption && (
                  <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>📉 波动率调整回撤</div>
                    <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 8 }}>文艺复兴方法：高波动期同等回撤严重程度更低</div>
                    <ReactECharts option={volAdjChartOption} style={{ height: 320 }} notMerge />
                  </div>
                )}
              </div>
            </>
          )}

          {/* Tab: History */}
          {analysisTab === 'history' && (
            <>
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20, marginBottom: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>📊 回撤统计</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
                  <MetricCard label="回撤次数" value={result.distribution.count} />
                  <MetricCard label="平均回撤" value={`${result.distribution.avg_depth}%`} />
                  <MetricCard label="中位数回撤" value={`${result.distribution.median_depth}%`} />
                  <MetricCard label="最大回撤" value={`${result.distribution.max_depth}%`} color="#ef4444" />
                  <MetricCard label="最小回撤" value={`${result.distribution.min_depth}%`} color="#22c55e" />
                </div>
              </div>
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>📜 历史回撤明细</div>
                {result.drawdowns.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 30, color: '#6b7280' }}>未检测到显著回撤（{'>'}3%）</div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #374151' }}>
                          {['#', '开始日期', '谷底日期', '结束日期', '回撤幅度', '持续天数', '恢复天数', '状态'].map(h => (
                            <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 600 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.drawdowns.map((dd, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid #30363d' }}>
                            <td style={{ padding: '10px 12px', color: '#9ca3af' }}>{i + 1}</td>
                            <td style={{ padding: '10px 12px', color: '#f3f4f6' }}>{dd.start_date}</td>
                            <td style={{ padding: '10px 12px', color: '#f3f4f6' }}>{dd.trough_date}</td>
                            <td style={{ padding: '10px 12px', color: '#f3f4f6' }}>{dd.end_date || '进行中'}</td>
                            <td style={{ padding: '10px 12px', color: '#ef4444', fontWeight: 700 }}>-{dd.depth_pct}%</td>
                            <td style={{ padding: '10px 12px', color: '#f3f4f6' }}>{dd.duration_days}天</td>
                            <td style={{ padding: '10px 12px', color: '#f3f4f6' }}>{dd.recovery_days != null ? `${dd.recovery_days}天` : dd.ongoing_days != null ? `${dd.ongoing_days}天(进行中)` : '-'}</td>
                            <td style={{ padding: '10px 12px' }}>
                              <span style={{
                                padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                                background: dd.recovered ? '#22c55e20' : '#ef444420',
                                color: dd.recovered ? '#22c55e' : '#ef4444',
                              }}>{dd.recovered ? '已恢复' : '进行中'}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Tab: Recovery */}
          {analysisTab === 'recovery' && (
            <>
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20, marginBottom: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>🔄 恢复时间分析</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginBottom: 16 }}>
                  <MetricCard label="平均恢复时间" value={result.recovery.avg_recovery_days != null ? `${result.recovery.avg_recovery_days}天` : 'N/A'} />
                  <MetricCard label="中位数恢复时间" value={result.recovery.median_recovery_days != null ? `${result.recovery.median_recovery_days}天` : 'N/A'} />
                  <MetricCard label="最长恢复时间" value={result.recovery.max_recovery_days != null ? `${result.recovery.max_recovery_days}天` : 'N/A'} />
                  <MetricCard label="预计恢复天数" value={result.recovery.estimated_recovery_days != null ? `${result.recovery.estimated_recovery_days}天` : 'N/A'} sub={result.recovery.confidence ? `置信度: ${result.recovery.confidence}` : ''} />
                </div>
                {result.recovery.estimated_recovery_days != null && result.current_drawdown_pct > 0 && (
                  <div style={{ background: '#111827', borderRadius: 8, padding: 16, border: '1px solid #374151' }}>
                    <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>💡 回撤恢复预期</div>
                    <div style={{ fontSize: 14, color: '#f3f4f6', lineHeight: 1.8 }}>
                      当前回撤 <span style={{ color: '#ef4444', fontWeight: 700 }}>{result.current_drawdown_pct}%</span>，
                      已持续 <span style={{ color: '#f97316', fontWeight: 700 }}>{result.recovery.current_ongoing_days || result.current_drawdown_days}天</span>，
                      预计还需约
                      <span style={{ color: '#58a6ff', fontWeight: 700 }}> {result.recovery.estimated_recovery_days}天 </span>
                      恢复到前高。
                      {result.recovery.confidence && (
                        <span style={{ color: '#9ca3af', fontSize: 12 }}> （{result.recovery.confidence}）</span>
                      )}
                      {result.recovery.heuristic_baseline && (
                        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                          经验基准：同深度回撤通常需要约{result.recovery.heuristic_baseline}天恢复
                        </div>
                      )}
                      {result.current_drawdown_days > 365 && (
                        <div style={{ color: '#ef4444', marginTop: 4 }}> ⚠️ 回撤已持续超过1年，需关注基本面是否发生根本变化</div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* 仓位管理指南 */}
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>📐 仓位管理指南（桥水阶梯式）</div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #374151' }}>
                        {['回撤区间', '风险级别', '建议仓位', '操作建议'].map(h => (
                          <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 600 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { range: '< 3%', level: '安全', pos: '100%', action: '正常持有', color: '#22c55e', active: result.warning.level === 0 },
                        { range: '3-8%', level: '关注', pos: '100%', action: '关注走势变化，设好心理止损位', color: '#3b82f6', active: result.warning.level === 1 },
                        { range: '8-15%', level: '警戒', pos: '80%', action: '考虑减仓至80%，设置止损线', color: '#eab308', active: result.warning.level === 2 },
                        { range: '15-25%', level: '危险', pos: '60%', action: '减仓至60%，严格执行止损', color: '#f97316', active: result.warning.level === 3 },
                        { range: '25-40%', level: '严重', pos: '40%', action: '减仓至40%，考虑对冲或换仓', color: '#ef4444', active: result.warning.level === 4 },
                        { range: '> 40%', level: '极端', pos: '20%', action: '减仓至20%，等待企稳再加仓', color: '#991b1b', active: result.warning.level === 5 },
                      ].map((row, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid #30363d', background: row.active ? `${row.color}15` : 'transparent' }}>
                          <td style={{ padding: '10px 12px', color: row.color, fontWeight: row.active ? 700 : 400 }}>{row.range}</td>
                          <td style={{ padding: '10px 12px' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: `${row.color}20`, color: row.color }}>
                              {row.level}{row.active ? ' ← 当前' : ''}
                            </span>
                          </td>
                          <td style={{ padding: '10px 12px', color: '#f3f4f6', fontWeight: row.active ? 700 : 400 }}>{row.pos}</td>
                          <td style={{ padding: '10px 12px', color: '#9ca3af' }}>{row.action}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* Tab: Risk Management */}
          {analysisTab === 'risk' && (
            <>
              {/* 波动率自适应仓位 */}
              {result.position_sizing && (
                <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20, marginBottom: 20 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
                    📐 波动率自适应仓位（文艺复兴方法论）
                    <Tip text="三种量化方法计算最优仓位，取最保守值。ATR法基于止损距离反推仓位；波动率反比法让高波动股票自动降仓位；Kelly法基于期望值计算最优下注比例。" />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
                    {/* ATR法 */}
                    {result.position_sizing.atr_method && (
                      <div style={{ background: '#111827', borderRadius: 8, padding: 16, border: '1px solid #14b8a630' }}>
                        <div style={{ fontSize: 12, color: '#14b8a6', marginBottom: 10, fontWeight: 600 }}>方法1: ATR止损法</div>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>风险预算 / (止损倍数 × ATR)</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>可买股数</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: '#f3f4f6' }}>{result.position_sizing.atr_method.shares}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>仓位比例</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: '#f3f4f6' }}>{result.position_sizing.atr_method.position_pct}%</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>止损价</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#ef4444' }}>{result.position_sizing.atr_method.stop_loss_price}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>每股风险</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#f97316' }}>{result.position_sizing.atr_method.risk_per_share}</div>
                          </div>
                        </div>
                      </div>
                    )}
                    {/* 波动率反比法 */}
                    {result.position_sizing.vol_inverse_method && (
                      <div style={{ background: '#111827', borderRadius: 8, padding: 16, border: '1px solid #8b5cf630' }}>
                        <div style={{ fontSize: 12, color: '#8b5cf6', marginBottom: 10, fontWeight: 600 }}>方法2: 波动率反比法</div>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>目标波动率 / 当前波动率</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>建议仓位</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: '#f3f4f6' }}>{result.position_sizing.vol_inverse_method.position_pct}%</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>目标波动率</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{result.position_sizing.vol_inverse_method.target_vol}%</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>当前波动率</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#f97316' }}>{result.position_sizing.vol_inverse_method.current_vol}%</div>
                          </div>
                        </div>
                      </div>
                    )}
                    {/* Kelly法 */}
                    {result.position_sizing.kelly_method && (
                      <div style={{ background: '#111827', borderRadius: 8, padding: 16, border: '1px solid #22c55e30' }}>
                        <div style={{ fontSize: 12, color: '#22c55e', marginBottom: 10, fontWeight: 600 }}>方法3: Kelly公式</div>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 8 }}>f* = (p×b - q) / b</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>建议仓位</div>
                            <div style={{ fontSize: 18, fontWeight: 700, color: '#f3f4f6' }}>{result.position_sizing.kelly_method.position_pct}%</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>Kelly比例</div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{result.position_sizing.kelly_method.kelly_fraction}%</div>
                          </div>
                        </div>
                        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 8 }}>{result.position_sizing.kelly_method.note}</div>
                      </div>
                    )}
                  </div>
                  {/* 推荐仓位汇总 */}
                  <div style={{ background: '#111827', borderRadius: 8, padding: 16, border: '1px solid #58a6ff30' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div style={{ fontSize: 13, color: '#58a6ff', fontWeight: 600 }}>✅ 综合推荐（取三者最保守）</div>
                      <div style={{ fontSize: 11, color: '#6b7280' }}>总资金: {result.position_sizing.total_capital.toLocaleString()}</div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                      <div>
                        <div style={{ fontSize: 11, color: '#9ca3af' }}>建议仓位</div>
                        <div style={{ fontSize: 22, fontWeight: 800, color: '#58a6ff' }}>{result.position_sizing.recommended.position_pct}%</div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: '#9ca3af' }}>建议股数</div>
                        <div style={{ fontSize: 22, fontWeight: 800, color: '#f3f4f6' }}>{result.position_sizing.recommended.shares}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: '#9ca3af' }}>持仓市值</div>
                        <div style={{ fontSize: 22, fontWeight: 800, color: '#f3f4f6' }}>{result.position_sizing.recommended.position_value?.toLocaleString()}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: '#9ca3af' }}>最大亏损</div>
                        <div style={{ fontSize: 22, fontWeight: 800, color: '#ef4444' }}>{result.position_sizing.recommended.max_loss?.toLocaleString()}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 多模式止损 */}
              {result.stop_loss && Object.keys(result.stop_loss).length > 0 && (
                <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20, marginBottom: 20 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>
                    🛡️ 多模式止损价计算
                    <Tip text="基于当前价格、ATR、均线、波动率计算多种止损价位。实战建议：ATR吊灯止损做主止损 + 阶梯止盈锁利做移动止损 + 时间止损做兜底。" />
                  </div>
                  <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 16 }}>
                    当前价: <span style={{ color: '#f3f4f6', fontWeight: 600 }}>{result.current_price}</span>
                    {result.recent_high && <span style={{ marginLeft: 16 }}>近期高点: <span style={{ color: '#22c55e', fontWeight: 600 }}>{result.recent_high}</span></span>}
                    {result.ma20 && <span style={{ marginLeft: 16 }}>MA20: <span style={{ color: '#3b82f6', fontWeight: 600 }}>{result.ma20}</span></span>}
                    {result.ma60 && <span style={{ marginLeft: 16 }}>MA60: <span style={{ color: '#8b5cf6', fontWeight: 600 }}>{result.ma60}</span></span>}
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid #374151' }}>
                          {['止损方法', '止损价', '距当前', '说明'].map(h => (
                            <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#9ca3af', fontWeight: 600 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(result.stop_loss).filter(([k]) => k !== 'trailing_lock' && k !== 'time_stop').map(([key, val]: [string, any]) => {
                          const isRecommended = key === 'atr_2.5x'
                          return (
                            <tr key={key} style={{ borderBottom: '1px solid #30363d', background: isRecommended ? '#58a6ff10' : 'transparent' }}>
                              <td style={{ padding: '10px 12px', color: isRecommended ? '#58a6ff' : '#f3f4f6', fontWeight: isRecommended ? 700 : 400 }}>
                                {val.label}{isRecommended ? ' ⭐' : ''}
                              </td>
                              <td style={{ padding: '10px 12px', color: '#ef4444', fontWeight: 700, fontFamily: 'monospace' }}>
                                {val.stop_price}
                              </td>
                              <td style={{ padding: '10px 12px', color: val.loss_pct > 10 ? '#ef4444' : val.loss_pct > 5 ? '#f97316' : '#22c55e', fontWeight: 600 }}>
                                -{val.loss_pct}%
                              </td>
                              <td style={{ padding: '10px 12px', color: '#9ca3af', fontSize: 12 }}>
                                {key.startsWith('atr') ? '自动适应波动率' :
                                 key.startsWith('ma') ? '趋势支撑位' :
                                 key.startsWith('sar') ? '趋势跟踪' :
                                 key.startsWith('fixed') ? '简单直观' :
                                 key === 'vol_2std' ? '统计学2σ' : ''}
                              </td>
                            </tr>
                          )
                        })}
                        {/* 阶梯止盈 */}
                        {result.stop_loss.trailing_lock && (
                          <>
                            <tr><td colSpan={4} style={{ padding: '8px 12px', color: '#6b7280', fontSize: 11, borderTop: '1px dashed #374151' }}>阶梯止盈锁利</td></tr>
                            {result.stop_loss.trailing_lock.levels.map((lv: any, i: number) => (
                              <tr key={`tl${i}`} style={{ borderBottom: '1px solid #30363d', background: '#22c55e08' }}>
                                <td style={{ padding: '10px 12px', color: '#22c55e', fontWeight: 500 }}>盈利{lv.profit_pct}%</td>
                                <td style={{ padding: '10px 12px', color: '#22c55e', fontWeight: 700, fontFamily: 'monospace' }}>{lv.stop_price}</td>
                                <td style={{ padding: '10px 12px', color: '#9ca3af' }}>{lv.stop_type}</td>
                                <td style={{ padding: '10px 12px', color: '#9ca3af', fontSize: 12 }}>只往上移，永不往下</td>
                              </tr>
                            ))}
                          </>
                        )}
                        {/* 时间止损 */}
                        {result.stop_loss.time_stop && (
                          <tr style={{ borderBottom: '1px solid #30363d', background: result.stop_loss.time_stop.status === '已触发' ? '#ef444415' : 'transparent' }}>
                            <td style={{ padding: '10px 12px', color: '#ef4444', fontWeight: 500 }}>⏰ 时间止损</td>
                            <td style={{ padding: '10px 12px', color: '#9ca3af' }}>-</td>
                            <td style={{ padding: '10px 12px' }}>
                              <span style={{
                                padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                                background: result.stop_loss.time_stop.status === '已触发' ? '#ef444420' : '#22c55e20',
                                color: result.stop_loss.time_stop.status === '已触发' ? '#ef4444' : '#22c55e',
                              }}>{result.stop_loss.time_stop.status}（{result.stop_loss.time_stop.current_days}/{result.stop_loss.time_stop.trigger_days}天）</span>
                            </td>
                            <td style={{ padding: '10px 12px', color: '#9ca3af', fontSize: 12 }}>20天未启动应退出</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* VaR/CVaR + 回撤百分位 */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {/* VaR/CVaR */}
                {result.var_cvar && (
                  <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
                      📉 风险价值 (VaR / CVaR)
                      <Tip text="VaR=在95%/99%置信度下，年化最大损失。CVaR=超过VaR阈值时的平均损失（尾部风险）。机构级风控核心指标。" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 14 }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>VaR (95%)</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: '#f97316' }}>{result.var_cvar.var_95 ?? 'N/A'}%</div>
                        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 4 }}>95%概率年化损失不超此值</div>
                      </div>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 14 }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>CVaR (95%)</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{result.var_cvar.cvar_95 ?? 'N/A'}%</div>
                        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 4 }}>尾部平均损失（更保守）</div>
                      </div>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 14 }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>VaR (99%)</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{result.var_cvar.var_99 ?? 'N/A'}%</div>
                        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 4 }}>99%概率年化损失不超此值</div>
                      </div>
                      <div style={{ background: '#111827', borderRadius: 8, padding: 14 }}>
                        <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 6 }}>CVaR (99%)</div>
                        <div style={{ fontSize: 20, fontWeight: 700, color: '#991b1b' }}>{result.var_cvar.cvar_99 ?? 'N/A'}%</div>
                        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 4 }}>极端尾部平均损失</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 回撤百分位 */}
                {result.drawdown_percentiles && result.drawdown_percentiles.count > 0 && (
                  <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 20 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 16 }}>
                      📊 回撤深度百分位分布
                      <Tip text="历史回撤的百分位分析。P50=中位数回撤，P90/P95=尾部风险。如果当前回撤接近P90，说明已接近历史极端水平。" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                      {[
                        { label: 'P25', value: result.drawdown_percentiles.p25, color: '#22c55e' },
                        { label: 'P50(中位)', value: result.drawdown_percentiles.p50, color: '#eab308' },
                        { label: 'P75', value: result.drawdown_percentiles.p75, color: '#f97316' },
                        { label: 'P90', value: result.drawdown_percentiles.p90, color: '#ef4444' },
                        { label: 'P10(浅回撤)', value: result.drawdown_percentiles.p10, color: '#22c55e' },
                        { label: 'P95', value: result.drawdown_percentiles.p95, color: '#ef4444' },
                        { label: 'P99(极端)', value: result.drawdown_percentiles.p99, color: '#991b1b' },
                        { label: '总次数', value: result.drawdown_percentiles.count, color: '#9ca3af' },
                      ].map((item, i) => (
                        <div key={i} style={{ background: '#111827', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                          <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 4 }}>{item.label}</div>
                          <div style={{ fontSize: 16, fontWeight: 700, color: item.color }}>
                            {item.value != null ? (typeof item.value === 'number' && item.value % 1 !== 0 ? `${item.value}%` : item.value) : 'N/A'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* Empty State */}
      {!result && !loading && !error && (
        <div style={{ textAlign: 'center', padding: '80px 20px', color: '#6b7280' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🛡️</div>
          <div style={{ fontSize: 16, color: '#9ca3af', marginBottom: 8 }}>输入股票代码开始回撤分析</div>
          <div style={{ fontSize: 13 }}>支持A股和港股，分析历史回撤特征、当前风险级别和仓位建议</div>
        </div>
      )}
    </>
  )

  // ============================================================
  // 主渲染
  // ============================================================

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 8px' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#f3f4f6', margin: 0 }}>
          🛡️ 回撤控制
        </h1>
        <div style={{ fontSize: 14, color: '#9ca3af', marginTop: 6 }}>
          赚钱靠进攻，守钱靠防守。回撤控制是长期复利的核心。
          <span style={{ color: '#f59e0b' }}>亏50%需要赚100%才能回本</span>。
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        <button onClick={() => setActiveTab('philosophy')} style={{
          padding: '10px 24px', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600,
          background: activeTab === 'philosophy' ? '#3b82f6' : '#1f2937',
          color: activeTab === 'philosophy' ? '#fff' : '#9ca3af', cursor: 'pointer',
        }}>📖 理念与方法</button>
        <button onClick={() => setActiveTab('analysis')} style={{
          padding: '10px 24px', borderRadius: 8, border: 'none', fontSize: 14, fontWeight: 600,
          background: activeTab === 'analysis' ? '#3b82f6' : '#1f2937',
          color: activeTab === 'analysis' ? '#fff' : '#9ca3af', cursor: 'pointer',
        }}>🔬 实战分析</button>
      </div>

      {/* Tab Content */}
      {activeTab === 'philosophy' ? renderPhilosophy() : renderAnalysis()}
    </div>
  )
}
