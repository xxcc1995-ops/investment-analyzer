import { useState, useEffect, useCallback, useRef, useMemo, Component, ReactNode } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'

const API_BASE = '/api'

// ─── Error Boundary ─────────────────────────────────────────────────
interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class FundEstErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('FundEstDetailPage ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px 20px', textAlign: 'center',
          background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(248,81,73,0.25)', margin: '20px',
        }}>
          <div style={{ fontSize: '28px', marginBottom: '12px', opacity: 0.6 }}>&#9888;</div>
          <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px', color: 'var(--accent-red)' }}>
            页面渲染出错
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
            {this.state.error?.message || '未知错误'}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              padding: '8px 20px', background: 'var(--accent-blue)', color: '#fff',
              border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
              fontWeight: 600, fontSize: '13px',
            }}
          >
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// ─── Types ───────────────────────────────────────────────────────────
interface FundEstItem {
  fund_code: string
  fund_name: string
  fund_price: number
  fund_change_pct: number
  underlying_code: string
  underlying_price: number
  underlying_prev_close: number
  underlying_change_pct: number
  est_nav: number
  est_nav_traditional: number
  premium: number
  official_nav: number
  official_nav_date: string
  position: number
  usdcny_rate: number
  price_ratio: number
  calculation_method: string
}

interface FundEstDetail {
  fund_code: string
  fund_name: string
  est_nav: number
  est_nav_traditional: number
  a_share_price: number
  a_share_change_pct: number
  a_share_volume: number
  a_share_amount: number
  premium_pct: number
  official_nav: number
  official_nav_date: string
  underlying_code: string
  underlying_name: string
  underlying_price: number
  underlying_prev_close: number
  underlying_change_pct: number
  underlying_open: number
  underlying_high: number
  underlying_low: number
  usdcny_rate: number
  position_ratio: number
  calibration: number
  price_ratio: number
  calculation_method: string
  market_status: string
  update_time: string
}

interface StockHolding {
  rank: number
  stock_code: string
  stock_name: string
  weight: string
  shares: string
  market_value: string
  market_code: string
  // 增强字段 - 实时行情
  realtime_price?: number
  realtime_change_pct?: number
  realtime_loaded?: boolean
}

interface FundHoldings {
  fund_code: string
  report_date: string
  current_year: number
  available_years: number[]
  holdings: StockHolding[]
  total: number
  update_time: string
  error?: string
}

type SortField = 'premium' | 'code' | 'change' | 'est_nav' | 'price'

// ─── Constants ───────────────────────────────────────────────────────
const CARD_GRADIENT_PREMIUM = 'linear-gradient(135deg, rgba(248,81,73,0.08) 0%, rgba(248,81,73,0.02) 100%)'
const CARD_GRADIENT_DISCOUNT = 'linear-gradient(135deg, rgba(63,185,80,0.08) 0%, rgba(63,185,80,0.02) 100%)'
const CARD_GRADIENT_NEUTRAL = 'linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%)'

// ─── Helpers ─────────────────────────────────────────────────────────
const formatNumber = (n: number, decimals = 2): string => {
  if (n == null || isNaN(n)) return '--'
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

const formatLargeNumber = (n: string): string => {
  const num = parseFloat(n)
  if (isNaN(num)) return n
  if (Math.abs(num) >= 10000) return (num / 10000).toFixed(2) + '亿'
  return num.toFixed(2) + '万'
}

// ─── Skeleton Components ─────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
      padding: '20px', border: '1px solid var(--border-primary)',
      animation: 'pulse 1.5s ease-in-out infinite',
    }}>
      <div style={{ width: '60%', height: '12px', background: 'var(--bg-tertiary)', borderRadius: '4px', marginBottom: '12px' }} />
      <div style={{ width: '80%', height: '28px', background: 'var(--bg-tertiary)', borderRadius: '4px', marginBottom: '8px' }} />
      <div style={{ width: '40%', height: '10px', background: 'var(--bg-tertiary)', borderRadius: '4px' }} />
    </div>
  )
}

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 10 }).map((_, i) => (
        <td key={i} style={{ padding: '12px 14px' }}>
          <div style={{ width: '70%', height: '14px', background: 'var(--bg-tertiary)', borderRadius: '4px', animation: 'pulse 1.5s ease-in-out infinite' }} />
        </td>
      ))}
    </tr>
  )
}

// ─── Trend Arrow ─────────────────────────────────────────────────────
function TrendArrow({ value, suffix = '%' }: { value: number; suffix?: string }) {
  if (value == null || isNaN(value)) return <span style={{ color: 'var(--text-muted)' }}>--</span>
  const isUp = value > 0
  const isDown = value < 0
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '3px', fontWeight: 600,
      color: isUp ? 'var(--accent-red)' : isDown ? 'var(--accent-green)' : 'var(--text-muted)',
    }}>
      {isUp && <span style={{ fontSize: '10px' }}>&#9650;</span>}
      {isDown && <span style={{ fontSize: '10px' }}>&#9660;</span>}
      {isUp ? '+' : ''}{value.toFixed(2)}{suffix}
    </span>
  )
}

// ─── Sort Icon ───────────────────────────────────────────────────────
function SortIcon({ active, direction }: { active: boolean; direction: 'asc' | 'desc' }) {
  if (!active) return <span style={{ color: 'var(--text-muted)', fontSize: '10px', marginLeft: '4px' }}>&#8597;</span>
  return <span style={{ color: 'var(--accent-blue)', fontSize: '10px', marginLeft: '4px' }}>{direction === 'desc' ? '&#9660;' : '&#9650;'}</span>
}

// ─── Chart Theme ─────────────────────────────────────────────────────
const CHART_THEME = {
  bg: 'transparent',
  textColor: '#9ca3af',
  axisLine: '#374151',
  splitLine: '#2d3748',
  tooltipBg: 'rgba(15, 23, 42, 0.95)',
  tooltipBorder: '#374151',
}

// ─── Chart 1: Premium Rate Trend ────────────────────────────────────
function PremiumTrendChart({ premium }: { premium: number }) {
  // TODO: Replace with real API data when backend endpoint is available
  // GET /api/fund-est-detail/premium-history/{fund_code}
  const chartOption = useMemo(() => {
    // Generate 30 days of simulated premium data based on current value
    const today = new Date()
    const dates: string[] = []
    const premiumData: number[] = []
    const basePremium = premium

    for (let i = 29; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      // Skip weekends
      if (d.getDay() === 0 || d.getDay() === 6) continue
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const dd = String(d.getDate()).padStart(2, '0')
      dates.push(`${mm}-${dd}`)
      // Simulate realistic premium fluctuation
      const randomWalk = (Math.random() - 0.48) * 3.5
      const meanRevert = (basePremium - (basePremium + randomWalk * 0.3)) * 0.1
      const value = basePremium + randomWalk + meanRevert
      premiumData.push(parseFloat(value.toFixed(2)))
    }
    // Ensure last point matches current premium
    if (premiumData.length > 0) {
      premiumData[premiumData.length - 1] = premium
    }

    return {
      backgroundColor: CHART_THEME.bg,
      title: {
        text: '溢价率走势（近30天）',
        left: 'center',
        textStyle: { color: '#e5e7eb', fontSize: 14, fontWeight: 600 },
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: CHART_THEME.tooltipBg,
        borderColor: CHART_THEME.tooltipBorder,
        textStyle: { color: '#e5e7eb', fontSize: 12 },
        formatter: (params: any) => {
          const p = params[0]
          const color = p.value > 2 ? '#f85149' : p.value < -2 ? '#3fb950' : '#8b949e'
          return `<div style="font-size:12px">
            <div style="margin-bottom:4px;color:#9ca3af">${p.axisValue}</div>
            <div style="font-weight:700;color:${color}">溢价率: ${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%</div>
          </div>`
        },
      },
      grid: { left: '8%', right: '5%', top: '18%', bottom: '12%' },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: CHART_THEME.textColor, fontSize: 11 },
        axisLine: { lineStyle: { color: CHART_THEME.axisLine } },
        axisTick: { lineStyle: { color: CHART_THEME.axisLine } },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: CHART_THEME.textColor, fontSize: 11,
          formatter: '{value}%',
        },
        axisLine: { lineStyle: { color: CHART_THEME.axisLine } },
        splitLine: { lineStyle: { color: CHART_THEME.splitLine, type: 'dashed' } },
      },
      series: [
        {
          name: '溢价率',
          type: 'line',
          data: premiumData,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2.5, color: '#58a6ff' },
          itemStyle: { color: '#58a6ff', borderWidth: 2 },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(88, 166, 255, 0.25)' },
                { offset: 1, color: 'rgba(88, 166, 255, 0.02)' },
              ],
            },
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { type: 'dashed', width: 1.5 },
            label: {
              position: 'insideEndTop',
              fontSize: 11,
              fontWeight: 600,
            },
            data: [
              {
                yAxis: 2,
                lineStyle: { color: 'rgba(248, 81, 73, 0.6)' },
                label: { formatter: '+2% 阈值', color: '#f85149' },
              },
              {
                yAxis: -2,
                lineStyle: { color: 'rgba(63, 185, 80, 0.6)' },
                label: { formatter: '-2% 阈值', color: '#3fb950' },
              },
            ],
          },
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          start: 0,
          end: 100,
        },
      ],
    }
  }, [premium])

  return (
    <div style={{
      background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-subtle)', padding: '16px',
    }}>
      <ReactECharts option={chartOption} style={{ height: 320 }} opts={{ renderer: 'canvas' }} />
      <div style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
        注：溢价率走势为模拟数据，待接入后端历史数据API后替换为真实数据
      </div>
    </div>
  )
}

// ─── Chart 2: Holdings Distribution Pie ─────────────────────────────
function HoldingsPieChart({ holdings }: { holdings: FundHoldings | null }) {
  const chartOption = useMemo(() => {
    if (!holdings?.holdings?.length) {
      return {
        backgroundColor: CHART_THEME.bg,
        title: {
          text: '持仓分布（前十大）',
          left: 'center',
          textStyle: { color: '#e5e7eb', fontSize: 14, fontWeight: 600 },
        },
        graphic: {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: { text: '暂无持仓数据', fill: '#6b7280', fontSize: 14 },
        },
      }
    }

    const COLORS = [
      '#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff',
      '#79c0ff', '#56d364', '#e3b341', '#ff7b72', '#d2a8ff',
    ]

    const data = holdings.holdings.map((h, i) => ({
      name: h.stock_name,
      value: parseFloat(h.weight) || 0,
      itemStyle: { color: COLORS[i % COLORS.length] },
    }))

    // Calculate "other" weight
    const topSum = data.reduce((s, d) => s + d.value, 0)
    if (topSum < 100) {
      data.push({
        name: '其他',
        value: parseFloat((100 - topSum).toFixed(2)),
        itemStyle: { color: '#484f58' },
      })
    }

    return {
      backgroundColor: CHART_THEME.bg,
      title: {
        text: '持仓分布（前十大）',
        left: 'center',
        textStyle: { color: '#e5e7eb', fontSize: 14, fontWeight: 600 },
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: CHART_THEME.tooltipBg,
        borderColor: CHART_THEME.tooltipBorder,
        textStyle: { color: '#e5e7eb', fontSize: 12 },
        formatter: (params: any) => {
          return `<div style="font-size:12px">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${params.color};margin-right:6px;"></span>
            <strong>${params.name}</strong><br/>
            占比: ${params.value.toFixed(2)}%
          </div>`
        },
      },
      legend: {
        orient: 'vertical',
        right: '5%',
        top: 'middle',
        textStyle: { color: CHART_THEME.textColor, fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 8,
      },
      series: [
        {
          name: '持仓占比',
          type: 'pie',
          radius: ['40%', '68%'],
          center: ['38%', '55%'],
          avoidLabelOverlap: true,
          padAngle: 2,
          itemStyle: {
            borderRadius: 6,
            borderColor: '#0d1117',
            borderWidth: 2,
          },
          label: {
            show: true,
            position: 'outside',
            color: CHART_THEME.textColor,
            fontSize: 11,
            formatter: (params: any) => {
              if (params.value < 3) return ''
              return `${params.name}\n${params.value.toFixed(1)}%`
            },
          },
          emphasis: {
            label: { show: true, fontSize: 13, fontWeight: 'bold', color: '#e5e7eb' },
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
          labelLine: {
            lineStyle: { color: '#484f58' },
          },
          data,
        },
      ],
    }
  }, [holdings])

  return (
    <div style={{
      background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-subtle)', padding: '16px',
    }}>
      <ReactECharts option={chartOption} style={{ height: 360 }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}

// ─── Chart 3: Underlying Asset Comparison ───────────────────────────
function AssetComparisonChart({ fund }: { fund: FundEstDetail }) {
  const chartOption = useMemo(() => {
    const categories = ['基金净值', '底层资产']
    const estNav = fund.est_nav
    const officialNav = fund.official_nav
    const underlyingChange = fund.underlying_change_pct
    const premiumPct = fund.premium_pct

    // Calculate fund NAV change (estimated vs official)
    const navChange = officialNav > 0 ? ((estNav - officialNav) / officialNav * 100) : 0

    return {
      backgroundColor: CHART_THEME.bg,
      title: {
        text: '底层资产对比',
        left: 'center',
        textStyle: { color: '#e5e7eb', fontSize: 14, fontWeight: 600 },
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: CHART_THEME.tooltipBg,
        borderColor: CHART_THEME.tooltipBorder,
        textStyle: { color: '#e5e7eb', fontSize: 12 },
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          let html = `<div style="font-size:12px"><strong>${params[0].axisValue}</strong><br/>`
          params.forEach((p: any) => {
            const color = p.value >= 0 ? '#f85149' : '#3fb950'
            html += `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px;"></span>`
            html += `${p.seriesName}: <span style="color:${color};font-weight:600">${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%</span><br/>`
          })
          html += '</div>'
          return html
        },
      },
      legend: {
        data: ['涨跌幅', '溢价率'],
        top: 30,
        textStyle: { color: CHART_THEME.textColor, fontSize: 11 },
      },
      grid: { left: '12%', right: '8%', top: '22%', bottom: '12%' },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { color: CHART_THEME.textColor, fontSize: 12 },
        axisLine: { lineStyle: { color: CHART_THEME.axisLine } },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: 'value',
          name: '涨跌幅(%)',
          nameTextStyle: { color: CHART_THEME.textColor, fontSize: 11 },
          axisLabel: {
            color: CHART_THEME.textColor, fontSize: 11,
            formatter: '{value}%',
          },
          axisLine: { lineStyle: { color: CHART_THEME.axisLine } },
          splitLine: { lineStyle: { color: CHART_THEME.splitLine, type: 'dashed' } },
        },
        {
          type: 'value',
          name: '溢价率(%)',
          nameTextStyle: { color: CHART_THEME.textColor, fontSize: 11 },
          axisLabel: {
            color: CHART_THEME.textColor, fontSize: 11,
            formatter: '{value}%',
          },
          axisLine: { lineStyle: { color: CHART_THEME.axisLine } },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '涨跌幅',
          type: 'bar',
          barWidth: '30%',
          data: [
            {
              value: parseFloat(navChange.toFixed(2)),
              itemStyle: {
                color: navChange >= 0
                  ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(248,81,73,0.8)' }, { offset: 1, color: 'rgba(248,81,73,0.3)' }] }
                  : { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(63,185,80,0.3)' }, { offset: 1, color: 'rgba(63,185,80,0.8)' }] },
                borderRadius: [4, 4, 0, 0],
              },
            },
            {
              value: parseFloat(underlyingChange.toFixed(2)),
              itemStyle: {
                color: underlyingChange >= 0
                  ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(248,81,73,0.8)' }, { offset: 1, color: 'rgba(248,81,73,0.3)' }] }
                  : { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(63,185,80,0.3)' }, { offset: 1, color: 'rgba(63,185,80,0.8)' }] },
                borderRadius: [4, 4, 0, 0],
              },
            },
          ],
          label: {
            show: true,
            position: 'top',
            color: '#e5e7eb',
            fontSize: 12,
            fontWeight: 600,
            formatter: (p: any) => `${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%`,
          },
        },
        {
          name: '溢价率',
          type: 'bar',
          yAxisIndex: 1,
          barWidth: '30%',
          data: [
            {
              value: parseFloat(premiumPct.toFixed(2)),
              itemStyle: {
                color: premiumPct > 2
                  ? 'rgba(210, 153, 34, 0.7)'
                  : premiumPct < -2
                    ? 'rgba(88, 166, 255, 0.7)'
                    : 'rgba(139, 148, 158, 0.5)',
                borderRadius: [4, 4, 0, 0],
              },
            },
            {
              value: 0,
              itemStyle: { color: 'transparent' },
            },
          ],
          label: {
            show: true,
            position: 'top',
            color: '#e5e7eb',
            fontSize: 12,
            fontWeight: 600,
            formatter: (p: any) => {
              if (p.value === 0) return ''
              return `${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%`
            },
          },
        },
      ],
    }
  }, [fund])

  return (
    <div style={{
      background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)',
      border: '1px solid var(--border-subtle)', padding: '16px',
    }}>
      <ReactECharts option={chartOption} style={{ height: 360 }} opts={{ renderer: 'canvas' }} />
    </div>
  )
}

// ─── Main Component ──────────────────────────────────────────────────
function FundEstDetailPageInner() {
  const [funds, setFunds] = useState<FundEstItem[]>([])
  const [selectedFund, setSelectedFund] = useState<FundEstDetail | null>(null)
  const [holdings, setHoldings] = useState<FundHoldings | null>(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [holdingsLoading, setHoldingsLoading] = useState(false)
  const [error, setError] = useState('')
  const [updateTime, setUpdateTime] = useState('')
  const [usdcnyRate, setUsdcnyRate] = useState(0)
  const [marketStatus, setMarketStatus] = useState('')
  const [sortBy, setSortBy] = useState<SortField>('premium')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [filterMinPremium, setFilterMinPremium] = useState(-10)
  const [filterMaxPremium, setFilterMaxPremium] = useState(50)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [view, setView] = useState<'list' | 'detail'>('list')
  const [selectedYear, setSelectedYear] = useState<number | undefined>(undefined)
  const [hoveredRow, setHoveredRow] = useState<string | null>(null)
  const [holdingsPricesLoading, setHoldingsPricesLoading] = useState(false)

  const listRef = useRef<HTMLDivElement>(null)
  const holdingsRef = useRef<FundHoldings | null>(null)

  // Keep ref in sync with state to avoid stale closures
  useEffect(() => {
    holdingsRef.current = holdings
  }, [holdings])

  // ── Data fetching ──────────────────────────────────────────────────
  const loadListData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await axios.get(`${API_BASE}/fund-est-detail/list`, { timeout: 15000 })
      setFunds(res.data.funds || [])
      setUpdateTime(res.data.update_time || '')
      setUsdcnyRate(res.data.usdcny_rate || 0)
      setMarketStatus(res.data.market_status || '')
    } catch (e: any) {
      const msg = e.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : (e.message || '获取数据失败')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetailData = useCallback(async (fundCode: string) => {
    setDetailLoading(true)
    setError('')
    try {
      const res = await axios.get(`${API_BASE}/fund-est-detail/detail/${fundCode}`, { timeout: 15000 })
      if (res.data.error) {
        setError(res.data.error)
      } else {
        setSelectedFund(res.data)
        setView('detail')
        loadHoldingsData(fundCode.replace(/^(SH|SZ)/, ''))
      }
    } catch (e: any) {
      const msg = e.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : (e.message || '获取详情失败')
      setError(msg)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const loadHoldingsData = useCallback(async (fundCode: string, year?: number) => {
    setHoldingsLoading(true)
    try {
      const params = new URLSearchParams({ topline: '10' })
      if (year) params.append('year', String(year))
      const res = await axios.get(`${API_BASE}/fund-holdings/fund-holdings/${fundCode}?${params}`, { timeout: 10000 })
      setHoldings(res.data)
      if (res.data.available_years?.length > 0 && !year) {
        setSelectedYear(res.data.current_year)
      }
    } catch (e: any) {
      console.error('获取持仓数据失败:', e)
      setHoldings(null)
    } finally {
      setHoldingsLoading(false)
    }
  }, [])

  // 加载持仓股票的实时价格 (uses ref to avoid stale closure)
  const loadHoldingsRealtimePrices = useCallback(async () => {
    const currentHoldings = holdingsRef.current
    if (!currentHoldings?.holdings?.length) return
    setHoldingsPricesLoading(true)
    try {
      const codes = currentHoldings.holdings.map(h => {
        const raw = h.stock_code.replace(/^(SH|SZ|sh|sz)/, '')
        if (raw.startsWith('6')) return 'sh' + raw
        return 'sz' + raw
      })
      const res = await axios.get(`${API_BASE}/fund-est-detail/stock-quotes`, {
        params: { codes: codes.join(',') },
        timeout: 10000,
      })
      if (res.data?.quotes) {
        const quotes = res.data.quotes as Record<string, { price: number; change_pct: number }>
        setHoldings(prev => {
          if (!prev) return prev
          return {
            ...prev,
            holdings: prev.holdings.map(h => {
              const raw = h.stock_code.replace(/^(SH|SZ|sh|sz)/, '')
              const key = raw.startsWith('6') ? 'sh' + raw : 'sz' + raw
              const q = quotes[key]
              return {
                ...h,
                realtime_price: q?.price,
                realtime_change_pct: q?.change_pct,
                realtime_loaded: !!q,
              }
            }),
          }
        })
      }
    } catch (e) {
      console.error('获取持仓实时价格失败:', e)
    } finally {
      setHoldingsPricesLoading(false)
    }
  }, [])

  useEffect(() => { loadListData() }, [loadListData])

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh || view !== 'list') return
    const timer = setInterval(loadListData, 30000)
    return () => clearInterval(timer)
  }, [autoRefresh, view, loadListData])

  // 快捷键
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && view === 'detail') backToList()
      if (e.key === 'r' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        if (view === 'list') loadListData()
        else if (selectedFund) loadDetailData(selectedFund.fund_code)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [view, selectedFund, loadListData, loadDetailData])

  // ── Filtering / Sorting ────────────────────────────────────────────
  const handleSort = useCallback((field: SortField) => {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDir('desc')
    }
  }, [sortBy])

  const filteredFunds = useMemo(() => {
    return funds
      .filter(f => f.premium >= filterMinPremium && f.premium <= filterMaxPremium)
      .sort((a, b) => {
        const dir = sortDir === 'asc' ? 1 : -1
        if (sortBy === 'premium') return (a.premium - b.premium) * dir
        if (sortBy === 'change') return (a.underlying_change_pct - b.underlying_change_pct) * dir
        if (sortBy === 'est_nav') return (a.est_nav - b.est_nav) * dir
        if (sortBy === 'price') return (a.fund_price - b.fund_price) * dir
        return a.fund_code.localeCompare(b.fund_code) * dir
      })
  }, [funds, filterMinPremium, filterMaxPremium, sortBy, sortDir])

  // ── Color helpers (stable references) ──────────────────────────────
  const getPremiumColor = useCallback((premium: number) => {
    if (premium > 5) return 'var(--accent-red)'
    if (premium > 2) return 'var(--accent-orange)'
    if (premium > -2) return 'var(--text-secondary)'
    if (premium > -5) return 'var(--accent-blue)'
    return 'var(--accent-green)'
  }, [])

  const getPremiumBg = useCallback((premium: number) => {
    if (premium > 10) return 'rgba(248, 81, 73, 0.12)'
    if (premium > 5) return 'rgba(210, 153, 34, 0.10)'
    if (premium > 2) return 'rgba(210, 153, 34, 0.06)'
    if (premium < -5) return 'rgba(63, 185, 80, 0.12)'
    if (premium < -2) return 'rgba(63, 185, 80, 0.06)'
    return 'transparent'
  }, [])

  const getPremiumLabel = useCallback((premium: number) => {
    if (premium > 5) return '高溢价'
    if (premium > 2) return '溢价偏高'
    if (premium > -2) return '溢价合理'
    if (premium > -5) return '折价机会'
    return '深度折价'
  }, [])

  const getPremiumLabelColor = useCallback((premium: number) => {
    if (premium > 5) return 'var(--accent-red)'
    if (premium > 2) return 'var(--accent-orange)'
    if (premium > -2) return 'var(--text-muted)'
    if (premium > -5) return 'var(--accent-blue)'
    return 'var(--accent-green)'
  }, [])

  const getMarketStatusText = useCallback((status: string) => {
    switch (status) {
      case 'a_share_open': return 'A股交易中'
      case 'us_market_open': return '美股交易中'
      case 'weekend': return '周末休市'
      default: return '已收盘'
    }
  }, [])

  const getMarketStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'a_share_open': return 'var(--accent-green)'
      case 'us_market_open': return 'var(--accent-blue)'
      default: return 'var(--text-muted)'
    }
  }, [])

  const getMarketStatusDot = useCallback((status: string) => {
    const isActive = status === 'a_share_open' || status === 'us_market_open'
    return (
      <span style={{
        display: 'inline-block', width: '8px', height: '8px',
        borderRadius: '50%', marginRight: '6px',
        background: isActive ? getMarketStatusColor(status) : 'var(--text-muted)',
        boxShadow: isActive ? `0 0 6px ${status === 'a_share_open' ? 'rgba(63,185,80,0.5)' : 'rgba(88,166,255,0.5)'}` : 'none',
        animation: isActive ? 'pulse 2s infinite' : 'none',
      }} />
    )
  }, [getMarketStatusColor])

  // ── Navigation ─────────────────────────────────────────────────────
  const backToList = useCallback(() => {
    setView('list')
    setSelectedFund(null)
    setHoldings(null)
    setError('')
  }, [])

  // ── Export CSV ─────────────────────────────────────────────────────
  const exportCSV = useCallback(() => {
    const headers = ['代码', '名称', '场内价格', '底层资产', '底层价格', '底层涨跌%', 'EST净值', '溢价率%', '官方净值', '净值日期']
    const rows = filteredFunds.map(f => [
      f.fund_code, f.fund_name, f.fund_price.toFixed(3),
      f.underlying_code, f.underlying_price.toFixed(2),
      f.underlying_change_pct.toFixed(2), f.est_nav.toFixed(4),
      f.premium.toFixed(2), f.official_nav.toFixed(4), f.official_nav_date,
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const BOM = '﻿'
    const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `QDII_LOF_基金净值估算_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [filteredFunds])

  // ═══════════════════════════════════════════════════════════════════
  // DETAIL VIEW
  // ═══════════════════════════════════════════════════════════════════
  if (view === 'detail' && selectedFund) {
    const premiumLabel = getPremiumLabel(selectedFund.premium_pct)
    const premiumLabelColor = getPremiumLabelColor(selectedFund.premium_pct)

    return (
      <div className="fund-est-page" style={{ padding: '0 0 24px' }}>
        <style>{`
          @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
          @keyframes slideIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
          .fund-detail-enter { animation: slideIn 0.3s ease-out; }
          .holdings-row { transition: background 0.15s ease; cursor: default; }
          .holdings-row:hover td { background: var(--bg-hover) !important; }
          .detail-card { transition: border-color 0.2s, box-shadow 0.2s; }
          .detail-card:hover { border-color: rgba(88,166,255,0.3); box-shadow: 0 2px 12px rgba(0,0,0,0.15); }
          .back-btn { transition: all 0.2s; }
          .back-btn:hover { background: var(--accent-blue) !important; color: #fff !important; transform: translateX(-2px); }
          .refresh-btn { transition: all 0.2s; }
          .refresh-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(88,166,255,0.3); }
          .price-tag-btn { transition: all 0.2s; }
          .price-tag-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
          .kbd { display: inline-block; padding: 2px 6px; background: var(--bg-tertiary); border: 1px solid var(--border-primary); border-radius: 3px; font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); line-height: 1.4; }
        `}</style>

        {/* Breadcrumb */}
        <div style={{
          padding: '12px 20px', display: 'flex', alignItems: 'center', gap: '8px',
          fontSize: '13px', color: 'var(--text-muted)',
        }}>
          <span
            onClick={backToList}
            style={{ cursor: 'pointer', color: 'var(--accent-blue)', transition: 'color 0.2s' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#79b8ff')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--accent-blue)')}
          >
            QDII LOF基金
          </span>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{selectedFund.fund_name}</span>
        </div>

        {/* Header */}
        <div className="stock-header fund-detail-enter" style={{ margin: '0 20px 16px' }}>
          <div className="stock-title-row">
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
              <button className="back-btn" onClick={backToList} style={{
                padding: '8px 14px', background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
                border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', fontSize: '13px', fontWeight: 500, whiteSpace: 'nowrap',
                display: 'flex', alignItems: 'center', gap: '4px',
              }}>
                <span style={{ fontSize: '16px' }}>&#8592;</span> 返回
              </button>
              <div>
                <h2 style={{ fontSize: '22px' }}>{selectedFund.fund_name}</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                  <span className="stock-code" style={{ fontFamily: 'var(--font-mono)' }}>{selectedFund.fund_code}</span>
                  <span style={{
                    padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600,
                    background: 'rgba(88,166,255,0.1)', color: 'var(--accent-blue)',
                    border: '1px solid rgba(88,166,255,0.2)',
                  }}>
                    动态比率法
                  </span>
                  <span style={{
                    display: 'flex', alignItems: 'center', fontSize: '12px',
                    color: getMarketStatusColor(selectedFund.market_status),
                  }}>
                    {getMarketStatusDot(selectedFund.market_status)}
                    {getMarketStatusText(selectedFund.market_status)}
                  </span>
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                <span className="kbd">Ctrl</span>+<span className="kbd">R</span> 刷新
              </span>
              <button
                className="refresh-btn"
                onClick={() => loadDetailData(selectedFund.fund_code)}
                disabled={detailLoading}
                style={{
                  padding: '8px 20px', background: 'linear-gradient(135deg, var(--accent-blue), #1f6feb)',
                  color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', fontWeight: 600, fontSize: '13px',
                  opacity: detailLoading ? 0.6 : 1,
                }}
              >
                {detailLoading ? '刷新中...' : '刷新数据'}
              </button>
            </div>
          </div>
        </div>

        {/* Core Metrics Cards */}
        <div className="fund-detail-enter" style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px',
          margin: '0 20px 16px',
        }}>
          {/* EST Nav */}
          <div className="detail-card" style={{
            background: 'linear-gradient(135deg, rgba(88,166,255,0.08) 0%, rgba(88,166,255,0.02) 100%)',
            borderRadius: 'var(--radius-md)', padding: '20px',
            border: '1px solid rgba(88,166,255,0.2)', textAlign: 'center',
          }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              EST估算净值
            </div>
            <div style={{ fontSize: '32px', fontWeight: 700, color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
              {formatNumber(selectedFund.est_nav, 4)}
            </div>
            <div style={{
              fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px',
              padding: '2px 8px', background: 'rgba(88,166,255,0.08)', borderRadius: '10px', display: 'inline-block',
            }}>
              动态比率法
            </div>
          </div>

          {/* A Share Price */}
          <div className="detail-card" style={{
            background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', padding: '20px',
            border: '1px solid var(--border-primary)', textAlign: 'center',
          }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              场内价格（A股）
            </div>
            <div style={{ fontSize: '32px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {selectedFund.a_share_price > 0 ? formatNumber(selectedFund.a_share_price, 4) : '--'}
            </div>
            <div style={{ marginTop: '6px' }}>
              <TrendArrow value={selectedFund.a_share_change_pct} />
            </div>
          </div>

          {/* Premium */}
          <div className="detail-card" style={{
            background: selectedFund.premium_pct > 2 ? CARD_GRADIENT_PREMIUM
              : selectedFund.premium_pct < -2 ? CARD_GRADIENT_DISCOUNT : CARD_GRADIENT_NEUTRAL,
            borderRadius: 'var(--radius-md)', padding: '20px',
            border: `1px solid ${selectedFund.premium_pct > 2 ? 'rgba(248,81,73,0.25)' : selectedFund.premium_pct < -2 ? 'rgba(63,185,80,0.25)' : 'var(--border-primary)'}`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              溢价率
            </div>
            <div style={{
              fontSize: '32px', fontWeight: 700, fontFamily: 'var(--font-mono)',
              color: getPremiumColor(selectedFund.premium_pct),
            }}>
              {selectedFund.premium_pct > 0 ? '+' : ''}{formatNumber(selectedFund.premium_pct, 2)}%
            </div>
            <div style={{
              fontSize: '12px', marginTop: '6px', fontWeight: 600,
              color: premiumLabelColor,
            }}>
              {premiumLabel}
            </div>
          </div>

          {/* Market Status */}
          <div className="detail-card" style={{
            background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', padding: '20px',
            border: '1px solid var(--border-primary)', textAlign: 'center',
          }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              市场状态
            </div>
            <div style={{
              fontSize: '18px', fontWeight: 600, marginBottom: '8px',
              color: getMarketStatusColor(selectedFund.market_status),
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {getMarketStatusDot(selectedFund.market_status)}
              {getMarketStatusText(selectedFund.market_status)}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{selectedFund.update_time}</div>
          </div>
        </div>

        {/* Calculation Process */}
        <div className="fund-detail-enter" style={{
          margin: '0 20px 16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-primary)', overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            padding: '14px 20px', background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary))',
            borderBottom: '1px solid var(--border-primary)', fontWeight: 600,
            fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <span style={{ color: 'var(--accent-blue)' }}>&#9670;</span> 净值计算过程
            <span style={{
              fontSize: '11px', fontWeight: 400, color: 'var(--text-muted)',
              padding: '2px 8px', background: 'var(--bg-primary)', borderRadius: '10px',
            }}>
              动态比率法
            </span>
          </div>
          <div style={{ padding: '20px' }}>
            <div style={{
              background: 'linear-gradient(135deg, rgba(88,166,255,0.08), rgba(88,166,255,0.02))',
              borderRadius: 'var(--radius-sm)', padding: '14px 16px',
              marginBottom: '20px', fontFamily: 'var(--font-mono)', fontSize: '14px',
              color: 'var(--accent-blue)', border: '1px solid rgba(88,166,255,0.15)',
              textAlign: 'center', letterSpacing: '0.5px',
            }}>
              EST净值 = 官方净值 &times; (底层资产当前价 &divide; 底层资产昨收)
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              {/* Input Data */}
              <div>
                <div style={{
                  fontWeight: 600, marginBottom: '14px', color: 'var(--text-primary)',
                  display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px',
                }}>
                  <span style={{ color: 'var(--accent-blue)' }}>&#9660;</span> 输入数据
                </div>
                {[
                  { label: `官方净值（${selectedFund.official_nav_date}）`, value: formatNumber(selectedFund.official_nav, 4), valueColor: 'var(--text-primary)' },
                  { label: `${selectedFund.underlying_code} 昨收`, value: `$${formatNumber(selectedFund.underlying_prev_close, 2)}`, valueColor: 'var(--text-primary)' },
                  { label: `${selectedFund.underlying_code} 当前价`, value: `$${formatNumber(selectedFund.underlying_price, 2)} (${selectedFund.underlying_change_pct >= 0 ? '+' : ''}${selectedFund.underlying_change_pct.toFixed(2)}%)`, valueColor: selectedFund.underlying_change_pct >= 0 ? 'var(--accent-red)' : 'var(--accent-green)' },
                  { label: '美元人民币汇率', value: formatNumber(selectedFund.usdcny_rate, 4), valueColor: 'var(--text-primary)' },
                  { label: '仓位比例', value: `${(selectedFund.position_ratio * 100).toFixed(0)}%`, valueColor: 'var(--text-primary)' },
                ].map((item, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 0', borderBottom: '1px solid var(--border-subtle)',
                  }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>{item.label}</span>
                    <span style={{ fontWeight: 600, color: item.valueColor, fontFamily: 'var(--font-mono)', fontSize: '13px' }}>{item.value}</span>
                  </div>
                ))}
              </div>

              {/* Output Data */}
              <div>
                <div style={{
                  fontWeight: 600, marginBottom: '14px', color: 'var(--text-primary)',
                  display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px',
                }}>
                  <span style={{ color: 'var(--accent-green)' }}>&#9650;</span> 计算结果
                </div>
                {[
                  { label: '价格比率', value: selectedFund.price_ratio.toFixed(6) },
                  { label: '校准值', value: selectedFund.calibration.toFixed(6) },
                ].map((item, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 0', borderBottom: '1px solid var(--border-subtle)',
                  }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>{item.label}</span>
                    <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '13px' }}>{item.value}</span>
                  </div>
                ))}
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '14px 0', borderTop: '2px solid var(--accent-blue)', marginTop: '8px',
                }}>
                  <span style={{ fontWeight: 600, color: 'var(--accent-blue)', fontSize: '14px' }}>EST净值（动态比率法）</span>
                  <span style={{ fontWeight: 700, fontSize: '20px', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
                    {formatNumber(selectedFund.est_nav, 4)}
                  </span>
                </div>
                {[
                  { label: 'EST净值（传统方法）', value: formatNumber(selectedFund.est_nav_traditional, 4) },
                  { label: '场内价格', value: selectedFund.a_share_price > 0 ? formatNumber(selectedFund.a_share_price, 4) : '--' },
                  { label: '溢价率', value: `${selectedFund.premium_pct > 0 ? '+' : ''}${formatNumber(selectedFund.premium_pct, 2)}%`, valueColor: getPremiumColor(selectedFund.premium_pct), bold: true },
                ].map((item, i) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '10px 0', borderBottom: i < 2 ? '1px solid var(--border-subtle)' : 'none',
                  }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>{item.label}</span>
                    <span style={{
                      fontWeight: item.bold ? 700 : 600,
                      color: item.valueColor || 'var(--text-primary)',
                      fontFamily: 'var(--font-mono)', fontSize: '13px',
                    }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ═══ Charts Section ═══ */}
        <div className="fund-detail-enter" style={{
          margin: '0 20px 16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-primary)', overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            padding: '14px 20px', background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary))',
            borderBottom: '1px solid var(--border-primary)', fontWeight: 600,
            fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <span style={{ color: 'var(--accent-purple)' }}>&#9670;</span> 数据可视化
            <span style={{
              fontSize: '11px', fontWeight: 400, color: 'var(--text-muted)',
              padding: '2px 8px', background: 'var(--bg-primary)', borderRadius: '10px',
            }}>
              ECharts
            </span>
          </div>
          <div style={{ padding: '20px' }}>

            {/* Chart 1: Premium Rate Trend */}
            <PremiumTrendChart premium={selectedFund.premium_pct} />

            {/* Chart 2 & 3: Side by side */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px' }}>
              <HoldingsPieChart holdings={holdings} />
              <AssetComparisonChart fund={selectedFund} />
            </div>
          </div>
        </div>

        {/* Fund Holdings */}
        <div className="fund-detail-enter" style={{
          margin: '0 20px 16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-primary)', overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            padding: '14px 20px', background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary))',
            borderBottom: '1px solid var(--border-primary)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontWeight: 600, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--accent-purple)' }}>&#9670;</span> 基金持仓信息
              <span style={{
                fontSize: '11px', fontWeight: 400, color: 'var(--text-muted)',
                padding: '2px 8px', background: 'var(--bg-primary)', borderRadius: '10px',
              }}>前十大</span>
            </span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {holdings?.available_years && holdings.available_years.length > 0 && (
                <select
                  value={selectedYear || ''}
                  onChange={e => {
                    const year = Number(e.target.value)
                    setSelectedYear(year)
                    loadHoldingsData(selectedFund.fund_code.replace(/^(SH|SZ)/, ''), year)
                  }}
                  style={{
                    padding: '5px 10px', border: '1px solid var(--border-primary)',
                    borderRadius: 'var(--radius-sm)', background: 'var(--bg-input)',
                    color: 'var(--text-primary)', fontSize: '12px', cursor: 'pointer',
                  }}
                >
                  {holdings.available_years.map(y => (
                    <option key={y} value={y}>{y}年</option>
                  ))}
                </select>
              )}
              <button
                onClick={() => loadHoldingsData(selectedFund.fund_code.replace(/^(SH|SZ)/, ''), selectedYear)}
                disabled={holdingsLoading}
                className="price-tag-btn"
                style={{
                  padding: '5px 14px', background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
                  border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', fontSize: '12px', fontWeight: 500,
                  opacity: holdingsLoading ? 0.6 : 1,
                }}
              >
                {holdingsLoading ? '加载中...' : '刷新持仓'}
              </button>
              {holdings?.holdings && holdings.holdings.length > 0 && (
                <button
                  onClick={loadHoldingsRealtimePrices}
                  disabled={holdingsPricesLoading}
                  className="price-tag-btn"
                  style={{
                    padding: '5px 14px', background: 'linear-gradient(135deg, var(--accent-blue), #1f6feb)',
                    color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer', fontSize: '12px', fontWeight: 600,
                    opacity: holdingsPricesLoading ? 0.6 : 1,
                  }}
                >
                  {holdingsPricesLoading ? '查询中...' : '查询实时价格'}
                </button>
              )}
            </div>
          </div>

          <div style={{ padding: '20px' }}>
            {holdingsLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '32px' }}>
                <div className="spinner" />
                <span style={{ color: 'var(--text-muted)' }}>加载持仓数据...</span>
              </div>
            ) : holdings && holdings.holdings && holdings.holdings.length > 0 ? (
              <>
                <div style={{
                  marginBottom: '14px', fontSize: '12px', color: 'var(--text-muted)',
                  display: 'flex', gap: '16px', flexWrap: 'wrap',
                }}>
                  <span style={{
                    padding: '3px 10px', background: 'var(--bg-tertiary)',
                    borderRadius: '10px', border: '1px solid var(--border-subtle)',
                  }}>
                    报告期: {holdings.report_date || '未知'}
                  </span>
                  <span style={{
                    padding: '3px 10px', background: 'var(--bg-tertiary)',
                    borderRadius: '10px', border: '1px solid var(--border-subtle)',
                  }}>
                    持仓数量: {holdings.total}
                  </span>
                </div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr>
                      {['排名', '代码', '名称', '占净值比', '持股数(万)', '市值(万)',
                        ...(holdings.holdings.some(h => h.realtime_loaded) ? ['实时价', '实时涨跌'] : [])
                      ].map(h => (
                        <th key={h} style={{
                          padding: '10px 12px', textAlign: h === '排名' || h === '代码' || h === '名称' ? 'left' : 'right',
                          background: 'var(--bg-tertiary)', fontWeight: 600, color: 'var(--text-secondary)',
                          borderBottom: '2px solid var(--border-primary)', fontSize: '12px',
                          whiteSpace: 'nowrap',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {holdings.holdings.map((stock, index) => (
                      <tr
                        key={index}
                        className="holdings-row"
                        style={{
                          borderBottom: '1px solid var(--border-subtle)',
                          background: index % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                        }}
                      >
                        <td style={{ padding: '10px 12px', textAlign: 'left' }}>
                          <span style={{
                            display: 'inline-block', width: '22px', height: '22px',
                            borderRadius: '50%', textAlign: 'center', lineHeight: '22px',
                            fontSize: '11px', fontWeight: 700,
                            background: index < 3
                              ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))'
                              : 'var(--bg-tertiary)',
                            color: index < 3 ? '#fff' : 'var(--text-muted)',
                          }}>
                            {stock.rank}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                          {stock.stock_code}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'left' }}>{stock.stock_name}</td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{stock.weight}%</td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{stock.shares}</td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>{stock.market_value}</td>
                        {stock.realtime_loaded && (
                          <>
                            <td style={{
                              padding: '10px 12px', textAlign: 'right', fontWeight: 600,
                              fontFamily: 'var(--font-mono)',
                              color: (stock.realtime_change_pct ?? 0) >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
                            }}>
                              {stock.realtime_price != null ? formatNumber(stock.realtime_price, 2) : '--'}
                            </td>
                            <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                              <TrendArrow value={stock.realtime_change_pct ?? 0} />
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : holdings?.error ? (
              <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '28px', marginBottom: '12px', opacity: 0.5 }}>&#9888;</div>
                <div style={{ marginBottom: '6px', fontWeight: 500 }}>{holdings.error}</div>
                <div style={{ fontSize: '12px' }}>该基金可能未披露持仓数据（如QDII基金通过ETF投资）</div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                暂无持仓数据
              </div>
            )}
          </div>
        </div>

        {/* Underlying Asset */}
        <div className="fund-detail-enter" style={{
          margin: '0 20px 16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-primary)', overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            padding: '14px 20px', background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary))',
            borderBottom: '1px solid var(--border-primary)', fontWeight: 600,
            fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <span style={{ color: 'var(--accent-green)' }}>&#9670;</span>
            {selectedFund.underlying_code}
            <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>({selectedFund.underlying_name})</span>
            行情
          </div>
          <div style={{ padding: '20px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              {[
                {
                  label: '当前价',
                  value: `$${formatNumber(selectedFund.underlying_price, 2)}`,
                  sub: <TrendArrow value={selectedFund.underlying_change_pct} />,
                  color: selectedFund.underlying_change_pct >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
                  gradient: selectedFund.underlying_change_pct >= 0
                    ? 'linear-gradient(135deg, rgba(248,81,73,0.08), rgba(248,81,73,0.02))'
                    : 'linear-gradient(135deg, rgba(63,185,80,0.08), rgba(63,185,80,0.02))',
                },
                {
                  label: '昨收',
                  value: `$${formatNumber(selectedFund.underlying_prev_close, 2)}`,
                  color: 'var(--text-primary)',
                  gradient: CARD_GRADIENT_NEUTRAL,
                },
                {
                  label: '涨跌额',
                  value: `$${formatNumber(selectedFund.underlying_price - selectedFund.underlying_prev_close, 2)}`,
                  color: selectedFund.underlying_change_pct >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
                  gradient: selectedFund.underlying_change_pct >= 0
                    ? 'linear-gradient(135deg, rgba(248,81,73,0.08), rgba(248,81,73,0.02))'
                    : 'linear-gradient(135deg, rgba(63,185,80,0.08), rgba(63,185,80,0.02))',
                },
              ].map((item, i) => (
                <div key={i} style={{
                  textAlign: 'center', padding: '16px', background: item.gradient,
                  borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)',
                  transition: 'border-color 0.2s',
                }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>{item.label}</div>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: item.color, fontFamily: 'var(--font-mono)' }}>
                    {item.value}
                  </div>
                  {item.sub && <div style={{ marginTop: '4px' }}>{item.sub}</div>}
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginTop: '16px' }}>
              {[
                { label: '开盘', value: `$${formatNumber(selectedFund.underlying_open, 2)}`, color: 'var(--text-primary)' },
                { label: '最高', value: `$${formatNumber(selectedFund.underlying_high, 2)}`, color: 'var(--accent-red)' },
                { label: '最低', value: `$${formatNumber(selectedFund.underlying_low, 2)}`, color: 'var(--accent-green)' },
                { label: '汇率', value: formatNumber(selectedFund.usdcny_rate, 4), color: 'var(--text-primary)' },
              ].map((item, i) => (
                <div key={i} style={{
                  textAlign: 'center', padding: '10px',
                  background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>{item.label}</div>
                  <div style={{ fontWeight: 600, color: item.color, fontFamily: 'var(--font-mono)', fontSize: '13px' }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Arbitrage Advice */}
        <div className="fund-detail-enter" style={{
          margin: '0 20px 16px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-primary)', overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            padding: '14px 20px', background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary))',
            borderBottom: '1px solid var(--border-primary)', fontWeight: 600,
            fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <span style={{ color: 'var(--accent-orange)' }}>&#9670;</span> 套利建议
          </div>
          <div style={{ padding: '20px' }}>
            {selectedFund.premium_pct > 2 ? (
              <div style={{
                padding: '20px', borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, rgba(248,81,73,0.08), rgba(248,81,73,0.02))',
                border: '1px solid rgba(248,81,73,0.25)',
              }}>
                <div style={{
                  fontWeight: 700, color: 'var(--accent-red)', marginBottom: '12px',
                  fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px',
                }}>
                  <span style={{
                    display: 'inline-block', width: '10px', height: '10px',
                    borderRadius: '50%', background: 'var(--accent-red)',
                    boxShadow: '0 0 8px rgba(248,81,73,0.4)',
                  }} />
                  溢价套利机会
                </div>
                <div style={{ fontSize: '14px', lineHeight: '1.8', color: 'var(--text-secondary)' }}>
                  <div>当前溢价 <strong style={{ color: 'var(--accent-red)' }}>{formatNumber(selectedFund.premium_pct, 2)}%</strong>，超过2%阈值</div>
                  <div style={{ marginTop: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>操作步骤：</div>
                  <div style={{ paddingLeft: '12px' }}>
                    <div>1. 场内卖出基金份额</div>
                    <div>2. 同时申购等量基金</div>
                    <div>3. 等待T+2日份额到账</div>
                    <div>4. 赚取溢价差价（扣除手续费）</div>
                  </div>
                </div>
              </div>
            ) : selectedFund.premium_pct < -2 ? (
              <div style={{
                padding: '20px', borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, rgba(63,185,80,0.08), rgba(63,185,80,0.02))',
                border: '1px solid rgba(63,185,80,0.25)',
              }}>
                <div style={{
                  fontWeight: 700, color: 'var(--accent-green)', marginBottom: '12px',
                  fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px',
                }}>
                  <span style={{
                    display: 'inline-block', width: '10px', height: '10px',
                    borderRadius: '50%', background: 'var(--accent-green)',
                    boxShadow: '0 0 8px rgba(63,185,80,0.4)',
                  }} />
                  折价套利机会
                </div>
                <div style={{ fontSize: '14px', lineHeight: '1.8', color: 'var(--text-secondary)' }}>
                  <div>当前折价 <strong style={{ color: 'var(--accent-green)' }}>{formatNumber(Math.abs(selectedFund.premium_pct), 2)}%</strong>，超过2%阈值</div>
                  <div style={{ marginTop: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>操作步骤：</div>
                  <div style={{ paddingLeft: '12px' }}>
                    <div>1. 场内买入基金份额</div>
                    <div>2. 同时赎回等量基金</div>
                    <div>3. 等待T+2日资金到账</div>
                    <div>4. 赚取折价差价（扣除手续费）</div>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '28px', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '18px', marginBottom: '8px', color: 'var(--text-secondary)' }}>
                  溢价率在合理范围内
                </div>
                <div>当前溢价率 {formatNumber(selectedFund.premium_pct, 2)}%，未达到套利阈值（&plusmn;2%）</div>
              </div>
            )}

            <div style={{
              marginTop: '20px', padding: '16px', background: 'var(--bg-tertiary)',
              borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)',
              fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.8',
            }}>
              <div style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--accent-orange)', fontSize: '13px' }}>
                风险提示
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px' }}>
                <div>&bull; EST净值是估算值，可能与实际净值存在误差</div>
                <div>&bull; 基金申购赎回有手续费（通常0.1%-1.5%）</div>
                <div>&bull; QDII基金有汇率风险</div>
                <div>&bull; 套利需要T+2时间，期间市场可能变动</div>
                <div>&bull; 动态比率法假设底层资产与基金持仓高度相关</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ═══════════════════════════════════════════════════════════════════
  // LIST VIEW
  // ═══════════════════════════════════════════════════════════════════
  return (
    <div className="fund-est-page">
      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes slideIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
        .fund-list-enter { animation: slideIn 0.3s ease-out; }
        .data-row { transition: all 0.15s ease; cursor: pointer; }
        .data-row:hover td { background: var(--bg-hover) !important; }
        .data-row:hover { transform: scale(1.001); }
        .sort-header { cursor: pointer; user-select: none; transition: color 0.2s; white-space: nowrap; }
        .sort-header:hover { color: var(--accent-blue); }
        .card-hover { transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s; }
        .card-hover:hover { border-color: rgba(88,166,255,0.3); box-shadow: 0 4px 16px rgba(0,0,0,0.15); transform: translateY(-1px); }
        .btn-primary { transition: all 0.2s; }
        .btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(88,166,255,0.3); }
        .btn-ghost { transition: all 0.2s; }
        .btn-ghost:hover { background: var(--bg-hover) !important; border-color: var(--accent-blue) !important; color: var(--accent-blue) !important; }
        .kbd { display: inline-block; padding: 2px 6px; background: var(--bg-tertiary); border: 1px solid var(--border-primary); border-radius: 3px; font-size: 11px; font-family: var(--font-mono); color: 'var(--text-muted)'; line-height: 1.4; }
        .pill-tag { display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 10px; font-size: 12px; font-weight: 500; background: var(--bg-tertiary); border: 1px solid var(--border-subtle); color: var(--text-secondary); }
        .select-dark { padding: 6px 12px; border: 1px solid var(--border-primary); border-radius: var(--radius-sm); font-size: 13px; background: var(--bg-input); color: var(--text-primary); cursor: pointer; transition: border-color 0.2s; }
        .select-dark:focus { outline: none; border-color: var(--accent-blue); }
        @media (max-width: 1024px) {
          .metrics-grid-responsive { grid-template-columns: repeat(2, 1fr) !important; }
          .filters-responsive { flex-direction: column !important; }
        }
        @media (max-width: 640px) {
          .metrics-grid-responsive { grid-template-columns: 1fr !important; }
        }
      `}</style>

      {/* Header */}
      <div className="stock-header fund-list-enter" style={{ margin: '0 20px 16px' }}>
        <div className="stock-title-row">
          <div>
            <h2 style={{ fontSize: '22px' }}>QDII LOF基金净值估算</h2>
            <span className="stock-code" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              动态比率法 - 实时估算所有QDII LOF基金净值
              <span style={{
                display: 'flex', alignItems: 'center', fontSize: '12px',
                color: getMarketStatusColor(marketStatus),
              }}>
                {getMarketStatusDot(marketStatus)}
                {getMarketStatusText(marketStatus)}
              </span>
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <label style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              cursor: 'pointer', fontSize: '13px', color: 'var(--text-secondary)',
            }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
                style={{ accentColor: 'var(--accent-blue)' }}
              />
              自动刷新
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>(30s)</span>
            </label>
            <button
              className="btn-primary"
              onClick={loadListData}
              disabled={loading}
              style={{
                padding: '8px 20px', background: 'linear-gradient(135deg, var(--accent-blue), #1f6feb)',
                color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', fontWeight: 600, fontSize: '13px',
                opacity: loading ? 0.6 : 1,
              }}
            >
              {loading ? '刷新中...' : '刷新'}
            </button>
            <button
              className="btn-ghost"
              onClick={exportCSV}
              style={{
                padding: '8px 16px', background: 'var(--bg-tertiary)',
                color: 'var(--text-secondary)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '13px', fontWeight: 500,
              }}
            >
              导出CSV
            </button>
          </div>
        </div>
      </div>

      {/* Info bar */}
      <div className="fund-list-enter" style={{
        margin: '0 20px 16px', display: 'flex', gap: '10px', flexWrap: 'wrap',
      }}>
        {[
          { label: '更新时间', value: updateTime },
          { label: '美元人民币中间价', value: usdcnyRate ? formatNumber(usdcnyRate, 4) : '--' },
          { label: '基金数量', value: `${filteredFunds.length}` },
          { label: '市场状态', value: getMarketStatusText(marketStatus) },
        ].map((tag, i) => (
          <span key={i} className="pill-tag">
            <span style={{ color: 'var(--text-muted)' }}>{tag.label}:</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{tag.value}</span>
          </span>
        ))}
      </div>

      {/* Explanation */}
      <div className="card-hover fund-list-enter" style={{
        margin: '0 20px 16px', padding: '20px', background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
        boxShadow: 'var(--shadow-card)',
      }}>
        <h3 style={{ marginBottom: '14px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: 'var(--accent-blue)' }}>&#9670;</span> 动态比率法说明
        </h3>
        <div style={{ fontSize: '13px', lineHeight: '1.8', color: 'var(--text-secondary)' }}>
          <div style={{
            fontFamily: 'var(--font-mono)', background: 'linear-gradient(135deg, rgba(88,166,255,0.08), rgba(88,166,255,0.02))',
            padding: '12px 16px', borderRadius: 'var(--radius-sm)', marginBottom: '14px',
            color: 'var(--accent-blue)', border: '1px solid rgba(88,166,255,0.15)', textAlign: 'center',
            letterSpacing: '0.5px',
          }}>
            EST净值 = 官方净值 &times; (底层资产当前价 &divide; 底层资产昨收)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px' }}>
            <div>&bull; <strong style={{ color: 'var(--text-primary)' }}>优势</strong>：每次使用最新官方净值重新校准，消除累积误差</div>
            <div>&bull; <strong style={{ color: 'var(--text-primary)' }}>数据源</strong>：底层资产价格来自新浪财经，基金净值来自东方财富</div>
            <div style={{ gridColumn: '1 / -1' }}>&bull; <strong style={{ color: 'var(--text-primary)' }}>适用场景</strong>：美股收盘后（凌晨4点）到基金公司公布净值（下午）这段时间，估算净值用于判断溢价/折价</div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="filters-responsive fund-list-enter" style={{
        display: 'flex', flexWrap: 'wrap', gap: '16px', margin: '0 20px 16px',
        padding: '16px 20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-primary)', boxShadow: 'var(--shadow-card)',
        alignItems: 'flex-end',
      }}>
        <div>
          <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>排序方式</label>
          <select value={sortBy} onChange={e => handleSort(e.target.value as SortField)} className="select-dark">
            <option value="premium">按溢价率排序</option>
            <option value="change">按底层涨跌幅</option>
            <option value="est_nav">按EST净值</option>
            <option value="price">按场内价格</option>
            <option value="code">按基金代码</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>最低溢价率(%)</label>
          <select value={filterMinPremium} onChange={e => setFilterMinPremium(Number(e.target.value))} className="select-dark">
            <option value={-10}>-10%</option>
            <option value={-5}>-5%</option>
            <option value={-2}>-2%</option>
            <option value={0}>0%</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>最高溢价率(%)</label>
          <select value={filterMaxPremium} onChange={e => setFilterMaxPremium(Number(e.target.value))} className="select-dark">
            <option value={10}>10%</option>
            <option value={20}>20%</option>
            <option value={50}>50%</option>
          </select>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
          <span className="kbd">Esc</span> 返回列表
          <span className="kbd">Ctrl</span>+<span className="kbd">R</span> 刷新
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          margin: '0 20px 16px', padding: '14px 16px',
          background: 'linear-gradient(135deg, rgba(248,81,73,0.08), rgba(248,81,73,0.02))',
          borderRadius: 'var(--radius-md)', border: '1px solid rgba(248,81,73,0.25)',
          color: 'var(--accent-red)', fontSize: '13px',
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <span style={{ fontSize: '16px' }}>&#9888;</span> {error}
        </div>
      )}

      {/* Table */}
      {loading && funds.length === 0 ? (
        <div style={{ margin: '0 20px' }}>
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-primary)', overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['代码', '名称', '场内价格', '底层资产', '底层价格', '底层涨跌', 'EST净值', '溢价率', '官方净值(日期)', '操作'].map(h => (
                    <th key={h} style={{
                      padding: '12px 14px', textAlign: 'left', background: 'var(--bg-tertiary)',
                      fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '2px solid var(--border-primary)',
                      fontSize: '12px',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="fund-list-enter" style={{ margin: '0 20px', overflowX: 'auto' }}>
          <div style={{
            background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-primary)', overflow: 'hidden',
            boxShadow: 'var(--shadow-card)',
          }}>
            <table className="arb-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {([
                    { key: 'code', label: '代码', align: 'left' },
                    { key: null, label: '名称', align: 'left' },
                    { key: 'price', label: '场内价格', align: 'right' },
                    { key: null, label: '底层资产', align: 'left' },
                    { key: null, label: '底层价格', align: 'right' },
                    { key: 'change', label: '底层涨跌', align: 'right' },
                    { key: 'est_nav', label: 'EST净值', align: 'right' },
                    { key: 'premium', label: '溢价率', align: 'right' },
                    { key: null, label: '官方净值(日期)', align: 'right' },
                    { key: null, label: '操作', align: 'center' },
                  ] as const).map((col, i) => (
                    <th
                      key={i}
                      className={col.key ? 'sort-header' : ''}
                      onClick={col.key ? () => handleSort(col.key as SortField) : undefined}
                      style={{
                        padding: '12px 14px', textAlign: col.align as any,
                        background: 'var(--bg-tertiary)', fontWeight: 600,
                        color: 'var(--text-secondary)', borderBottom: '2px solid var(--border-primary)',
                        fontSize: '12px', whiteSpace: 'nowrap',
                      }}
                    >
                      {col.label}
                      {col.key && <SortIcon active={sortBy === col.key} direction={sortBy === col.key ? sortDir : 'desc'} />}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredFunds.map((fund) => (
                  <tr
                    key={fund.fund_code}
                    className="data-row"
                    onClick={() => loadDetailData(fund.fund_code)}
                    onMouseEnter={() => setHoveredRow(fund.fund_code)}
                    onMouseLeave={() => setHoveredRow(null)}
                    style={{
                      background: hoveredRow === fund.fund_code
                        ? 'var(--bg-hover)'
                        : getPremiumBg(fund.premium) || 'transparent',
                      borderLeft: hoveredRow === fund.fund_code ? '3px solid var(--accent-blue)' : '3px solid transparent',
                    }}
                  >
                    <td style={{ padding: '12px 14px', textAlign: 'left', fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                      {fund.fund_code}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'left', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {fund.fund_name}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                      {formatNumber(fund.fund_price, 3)}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'left', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {fund.underlying_code}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                      ${formatNumber(fund.underlying_price, 2)}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      <TrendArrow value={fund.underlying_change_pct} />
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: 600, color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
                      {formatNumber(fund.est_nav, 4)}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      <span style={{
                        display: 'inline-block', padding: '3px 10px', borderRadius: '12px',
                        fontSize: '13px', fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: getPremiumColor(fund.premium),
                        background: getPremiumBg(fund.premium) || 'var(--bg-tertiary)',
                      }}>
                        {fund.premium > 0 ? '+' : ''}{formatNumber(fund.premium, 2)}%
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      <div style={{ fontFamily: 'var(--font-mono)' }}>{formatNumber(fund.official_nav, 4)}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{fund.official_nav_date || '无数据'}</div>
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); loadDetailData(fund.fund_code); }}
                        className="btn-primary"
                        style={{
                          padding: '5px 14px', background: 'var(--bg-tertiary)',
                          color: 'var(--accent-blue)', border: '1px solid var(--border-primary)',
                          borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '12px',
                          fontWeight: 600,
                        }}
                      >
                        详情
                      </button>
                    </td>
                  </tr>
                ))}
                {filteredFunds.length === 0 && (
                  <tr>
                    <td colSpan={10} style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                      <div style={{ fontSize: '28px', marginBottom: '12px', opacity: 0.4 }}>&#128269;</div>
                      <div>暂无符合条件的基金数据</div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Strategy Guide */}
      <div className="card-hover fund-list-enter" style={{
        margin: '16px 20px', padding: '20px', background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-md)', border: '1px solid var(--border-primary)',
        boxShadow: 'var(--shadow-card)',
      }}>
        <h3 style={{
          marginBottom: '16px', fontSize: '15px',
          display: 'flex', alignItems: 'center', gap: '8px',
          paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)',
        }}>
          <span style={{ color: 'var(--accent-orange)' }}>&#9670;</span> LOF基金套利策略
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
          <div style={{
            padding: '16px', borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, rgba(248,81,73,0.06), rgba(248,81,73,0.01))',
            border: '1px solid rgba(248,81,73,0.15)',
          }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-red)', marginBottom: '10px', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{
                display: 'inline-block', width: '8px', height: '8px',
                borderRadius: '50%', background: 'var(--accent-red)',
              }} />
              溢价套利
            </div>
            <div style={{ fontSize: '13px', lineHeight: '1.8', color: 'var(--text-secondary)' }}>
              <div>场内价格 &gt; EST净值</div>
              <div>1. 场内卖出基金份额</div>
              <div>2. 同时申购等量基金</div>
              <div>3. 等待T+2日份额到账</div>
              <div>4. 赚取溢价差价</div>
            </div>
          </div>
          <div style={{
            padding: '16px', borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, rgba(63,185,80,0.06), rgba(63,185,80,0.01))',
            border: '1px solid rgba(63,185,80,0.15)',
          }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-green)', marginBottom: '10px', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{
                display: 'inline-block', width: '8px', height: '8px',
                borderRadius: '50%', background: 'var(--accent-green)',
              }} />
              折价套利
            </div>
            <div style={{ fontSize: '13px', lineHeight: '1.8', color: 'var(--text-secondary)' }}>
              <div>场内价格 &lt; EST净值</div>
              <div>1. 场内买入基金份额</div>
              <div>2. 同时赎回等量基金</div>
              <div>3. 等待T+2日资金到账</div>
              <div>4. 赚取折价差价</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function FundEstDetailPage() {
  return (
    <FundEstErrorBoundary>
      <FundEstDetailPageInner />
    </FundEstErrorBoundary>
  )
}
