import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState } from '../components/ui'

const API_BASE = '/api/national-team'

interface Holding {
  code: string
  name: string
  holder_name: string
  hold_num: number
  hold_ratio: number
  hold_change: number
  hold_change_ratio: number
  hold_market_value: number
  end_date: string
  rank: number
  holder_type: string
}

interface ETFInfo {
  name: string
  price: number
  change_pct: number
  turnover: number
  super_inflow: number
  big_inflow: number
  mid_inflow: number
  small_inflow: number
  main_inflow: number
}

interface VolumeAlert {
  code: string
  name: string
  price: number
  change_pct: number
  volume_ratio: number
  volume: number
  turnover: number
  severity: 'high' | 'medium' | 'low'
  alert_type: string
  description: string
}

interface DragonTigerRecord {
  code: string
  name: string
  close_price: number
  change_pct: number
  buy_inst_count: number
  sell_inst_count: number
  inst_buy_amount: number
  inst_sell_amount: number
  inst_net_amount: number
  market_turnover: number
  inst_net_ratio: number
  turnover_rate: number
  float_market_cap: number
  reason: string
  date: string
}

interface BlockTradeRecord {
  code: string
  name: string
  trade_date: string
  price: number
  volume: number
  amount: number
  buyer: string
  seller: string
  is_inst_buy: boolean
  is_inst_sell: boolean
  inst_direction: string
}

interface ETFShareInfo {
  code: string
  name: string
  latest_date: string
  latest_shares: number
  week_ago_shares: number
  share_change: number
  share_change_pct: number
  signal: string
}

interface AssessmentSignal {
  name: string
  score: number
  direction: string
  detail: string
  weight: string
}

interface HoldingTrend {
  code: string
  name: string
  holder_type: string
  holder_name: string
  total_change: number
  total_change_pct: number
  trend_direction: string
  latest_value: number
  quarters: Record<string, { hold_num: number; hold_ratio: number; hold_market_value: number; hold_change: number }>
}

interface IndustryData {
  total_value: number
  weight: number
  stock_count: number
  holder_types: string[]
  top_stocks: { code: string; name: string; value: number; holder_type: string }[]
}

interface MarketContextSummary {
  latest_close: number
  ma5: number
  ma20: number
  ma60: number
  change_5d: number
  change_20d: number
  trend: string
  vol_change_pct: number
  vol_trend: string
}

type TabType = 'holdings' | 'etfFlows' | 'alerts' | 'dragonTiger' | 'blockTrades' | 'etfShares' | 'northbound' | 'margin' | 'assessment' | 'holdingsTrend' | 'industryAllocation'

// ============ Helper functions (module-level, never recreated) ============

const formatAmount = (val: number) => {
  if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(2) + '亿'
  if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(2) + '万'
  return val.toFixed(2)
}

const formatShares = (val: number) => {
  if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(2) + '亿股'
  if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(2) + '万股'
  return val.toFixed(0) + '股'
}

const changeColor = (val: number) => val > 0 ? '#e74c3c' : val < 0 ? '#27ae60' : '#999'
const severityColor = (s: string) => s === 'high' ? '#e74c3c' : s === 'medium' ? '#f39c12' : '#3498db'
const severityLabel = (s: string) => s === 'high' ? '严重' : s === 'medium' ? '中等' : '一般'

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  color: '#999',
  fontWeight: 500,
  fontSize: 12,
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  color: '#ddd',
  whiteSpace: 'nowrap',
}

// ============ Tab definitions (module-level, never recreated) ============

const TABS: { key: TabType; label: string; icon: string }[] = [
  { key: 'assessment', label: '综合研判', icon: ' ' },
  { key: 'northbound', label: '北向资金', icon: ' ' },
  { key: 'etfFlows', label: 'ETF资金', icon: ' ' },
  { key: 'etfShares', label: 'ETF份额', icon: ' ' },
  { key: 'dragonTiger', label: '龙虎榜', icon: ' ' },
  { key: 'blockTrades', label: '大宗交易', icon: ' ' },
  { key: 'margin', label: '融资融券', icon: ' ' },
  { key: 'holdingsTrend', label: '持仓趋势', icon: ' ' },
  { key: 'industryAllocation', label: '行业配置', icon: ' ' },
  { key: 'holdings', label: '持仓追踪', icon: ' ' },
  { key: 'alerts', label: '异动检测', icon: ' ' },
]

// ============ Component ============

export default function NationalTeamMonitor() {
  const [activeTab, setActiveTab] = useState<TabType>('assessment')

  // Holdings state
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [holdingsSummary, setHoldingsSummary] = useState<any>(null)
  const [holdingsEndDate, setHoldingsEndDate] = useState('')
  const [holdingsLoading, setHoldingsLoading] = useState(false)
  const [groupBy, setGroupBy] = useState<'stock' | 'institution'>('institution')

  // ETF flows state
  const [etfData, setEtfData] = useState<Record<string, ETFInfo>>({})
  const [totalMainInflow, setTotalMainInflow] = useState(0)
  const [etfLoading, setEtfLoading] = useState(false)
  const [etfDataType, setEtfDataType] = useState('')

  // Volume alerts state
  const [alerts, setAlerts] = useState<VolumeAlert[]>([])
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [alertThreshold, setAlertThreshold] = useState(2.0)
  const [scannedCount, setScannedCount] = useState(0)

  // Dragon tiger state
  const [dtRecords, setDtRecords] = useState<DragonTigerRecord[]>([])
  const [dtSummary, setDtSummary] = useState<any>(null)
  const [dtLoading, setDtLoading] = useState(false)
  const [dtDays, setDtDays] = useState(5)

  // Block trades state
  const [btRecords, setBtRecords] = useState<BlockTradeRecord[]>([])
  const [btSummary, setBtSummary] = useState<any>(null)
  const [btLoading, setBtLoading] = useState(false)
  const [btDays, setBtDays] = useState(5)

  // ETF shares state
  const [etfShares, setEtfShares] = useState<ETFShareInfo[]>([])
  const [etfSharesLoading, setEtfSharesLoading] = useState(false)

  // Assessment state
  const [assessment, setAssessment] = useState<any>(null)
  const [assessmentLoading, setAssessmentLoading] = useState(false)

  // Northbound state
  const [northbound, setNorthbound] = useState<any>(null)
  const [northboundLoading, setNorthboundLoading] = useState(false)

  // Margin state
  const [margin, setMargin] = useState<any>(null)
  const [marginLoading, setMarginLoading] = useState(false)

  // Holdings trend state
  const [holdingsTrends, setHoldingsTrends] = useState<HoldingTrend[]>([])
  const [holdingsTrendQuarters, setHoldingsTrendQuarters] = useState<string[]>([])
  const [holdingsTrendLoading, setHoldingsTrendLoading] = useState(false)

  // Industry allocation state
  const [industryData, setIndustryData] = useState<Record<string, IndustryData>>({})
  const [industryTotalValue, setIndustryTotalValue] = useState(0)
  const [industryLoading, setIndustryLoading] = useState(false)

  const loadHoldings = useCallback(async () => {
    setHoldingsLoading(true)
    try {
      const params: any = {}
      if (holdingsEndDate) params.end_date = holdingsEndDate
      const res = await axios.get(`${API_BASE}/shareholdings`, { params })
      setHoldings(res.data.holdings || [])
      setHoldingsSummary(res.data.summary || null)
      if (res.data.end_date) setHoldingsEndDate(res.data.end_date)
    } catch (e) {
      console.error('加载持仓数据失败:', e)
    }
    setHoldingsLoading(false)
  }, [holdingsEndDate])

  const loadETFFlows = useCallback(async () => {
    setEtfLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/etf-flows`)
      setEtfData(res.data.etfs || {})
      setTotalMainInflow(res.data.total_main_inflow || 0)
      setEtfDataType(res.data.data_type || '')
    } catch (e) {
      console.error('加载ETF流向失败:', e)
    }
    setEtfLoading(false)
  }, [])

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/volume-alerts`, { params: { threshold: alertThreshold } })
      setAlerts(res.data.alerts || [])
      setScannedCount(res.data.scanned || 0)
    } catch (e) {
      console.error('加载异动数据失败:', e)
    }
    setAlertsLoading(false)
  }, [alertThreshold])

  const loadDragonTiger = useCallback(async () => {
    setDtLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/dragon-tiger`, { params: { days: dtDays } })
      setDtRecords(res.data.records || [])
      setDtSummary(res.data.summary || null)
    } catch (e) {
      console.error('加载龙虎榜数据失败:', e)
    }
    setDtLoading(false)
  }, [dtDays])

  const loadBlockTrades = useCallback(async () => {
    setBtLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/block-trades`, { params: { days: btDays } })
      setBtRecords(res.data.records || [])
      setBtSummary(res.data.summary || null)
    } catch (e) {
      console.error('加载大宗交易数据失败:', e)
    }
    setBtLoading(false)
  }, [btDays])

  const loadETFShares = useCallback(async () => {
    setEtfSharesLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/etf-shares`)
      setEtfShares(res.data.etfs || [])
    } catch (e) {
      console.error('加载ETF份额数据失败:', e)
    }
    setEtfSharesLoading(false)
  }, [])

  const loadAssessment = useCallback(async () => {
    setAssessmentLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/assessment`)
      setAssessment(res.data)
    } catch (e) {
      console.error('加载综合研判失败:', e)
    }
    setAssessmentLoading(false)
  }, [])

  const loadNorthbound = useCallback(async () => {
    setNorthboundLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/northbound`)
      setNorthbound(res.data)
    } catch (e) {
      console.error('加载北向资金数据失败:', e)
    }
    setNorthboundLoading(false)
  }, [])

  const loadMargin = useCallback(async () => {
    setMarginLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/margin`)
      setMargin(res.data)
    } catch (e) {
      console.error('加载融资融券数据失败:', e)
    }
    setMarginLoading(false)
  }, [])

  const loadHoldingsTrend = useCallback(async () => {
    setHoldingsTrendLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/holdings-trend`)
      setHoldingsTrends(res.data.trends || [])
      setHoldingsTrendQuarters(res.data.quarters || [])
    } catch (e) {
      console.error('加载持仓趋势数据失败:', e)
    }
    setHoldingsTrendLoading(false)
  }, [])

  const loadIndustryAllocation = useCallback(async () => {
    setIndustryLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/industry-allocation`)
      setIndustryData(res.data.industries || {})
      setIndustryTotalValue(res.data.total_value || 0)
    } catch (e) {
      console.error('加载行业配置数据失败:', e)
    }
    setIndustryLoading(false)
  }, [])

  useEffect(() => {
    if (activeTab === 'holdings') loadHoldings()
    else if (activeTab === 'etfFlows') loadETFFlows()
    else if (activeTab === 'alerts') loadAlerts()
    else if (activeTab === 'dragonTiger') loadDragonTiger()
    else if (activeTab === 'blockTrades') loadBlockTrades()
    else if (activeTab === 'etfShares') loadETFShares()
    else if (activeTab === 'northbound') loadNorthbound()
    else if (activeTab === 'margin') loadMargin()
    else if (activeTab === 'assessment') loadAssessment()
    else if (activeTab === 'holdingsTrend') loadHoldingsTrend()
    else if (activeTab === 'industryAllocation') loadIndustryAllocation()
  }, [activeTab, loadHoldings, loadETFFlows, loadAlerts, loadDragonTiger, loadBlockTrades, loadETFShares, loadNorthbound, loadMargin, loadAssessment, loadHoldingsTrend, loadIndustryAllocation])

  // ============ Memoized chart options ============

  const etfFlowChartOption = useMemo(() => {
    const etfEntries = Object.entries(etfData)
    if (etfEntries.length === 0) return {}
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const [code, etf] = etfEntries[p.dataIndex]
          return `<b>${etf.name} (${code})</b><br/>` +
            `价格: ${etf.price.toFixed(3)} (${etf.change_pct >= 0 ? '+' : ''}${etf.change_pct.toFixed(2)}%)<br/>` +
            `成交额: ${formatAmount(etf.turnover)}<br/>` +
            `<hr style="margin:4px 0"/>` +
            `主力净流入: <span style="color:${etf.main_inflow >= 0 ? '#e74c3c' : '#27ae60'}">${formatAmount(etf.main_inflow)}</span><br/>` +
            `超大单: ${formatAmount(etf.super_inflow)}<br/>` +
            `大单: ${formatAmount(etf.big_inflow)}<br/>` +
            `中单: ${formatAmount(etf.mid_inflow)}<br/>` +
            `小单: ${formatAmount(etf.small_inflow)}`
        },
      },
      grid: { left: 80, right: 30, top: 20, bottom: 60 },
      xAxis: {
        type: 'category',
        data: etfEntries.map(([_, e]) => e.name),
        axisLabel: { fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        name: '主力净流入',
        axisLabel: {
          formatter: (v: number) => formatAmount(v),
        },
      },
      series: [{
        type: 'bar',
        data: etfEntries.map(([_, e]) => ({
          value: e.main_inflow,
          itemStyle: { color: e.main_inflow >= 0 ? '#e74c3c' : '#27ae60' },
        })),
        barWidth: '50%',
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => formatAmount(params.value),
          fontSize: 11,
        },
      }],
    }
  }, [etfData])

  const alertChartOption = useMemo(() => {
    if (alerts.length === 0) return {}
    const top10 = alerts.slice(0, 10)
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const alert = top10[p.dataIndex]
          return `<b>${alert.name}</b><br/>` +
            `量比: ${alert.volume_ratio.toFixed(2)}<br/>` +
            `涨跌幅: ${alert.change_pct.toFixed(2)}%<br/>` +
            `价格: ${alert.price.toFixed(2)}`
        },
      },
      grid: { left: 80, right: 30, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: top10.map(a => a.name),
        axisLabel: { rotate: 30, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: '量比',
      },
      series: [{
        type: 'bar',
        data: top10.map(a => ({
          value: a.volume_ratio,
          itemStyle: { color: severityColor(a.severity) },
        })),
        barWidth: '60%',
      }],
    }
  }, [alerts])

  const dtChartOption = useMemo(() => {
    if (dtRecords.length === 0) return {}
    const top10 = dtRecords.slice(0, 10)
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const r = top10[p.dataIndex]
          return `<b>${r.name} (${r.code})</b><br/>` +
            `机构净买入: ${formatAmount(r.inst_net_amount)}<br/>` +
            `买入: ${formatAmount(r.inst_buy_amount)} / 卖出: ${formatAmount(r.inst_sell_amount)}<br/>` +
            `涨跌幅: ${r.change_pct.toFixed(2)}%`
        },
      },
      grid: { left: 80, right: 30, top: 20, bottom: 60 },
      xAxis: {
        type: 'category',
        data: top10.map(r => r.name),
        axisLabel: { rotate: 30, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: '机构净买入',
        axisLabel: { formatter: (v: number) => formatAmount(v) },
      },
      series: [{
        type: 'bar',
        data: top10.map(r => ({
          value: r.inst_net_amount,
          itemStyle: { color: r.inst_net_amount >= 0 ? '#e74c3c' : '#27ae60' },
        })),
        barWidth: '60%',
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => formatAmount(params.value),
          fontSize: 10,
        },
      }],
    }
  }, [dtRecords])

  const assessmentChartOption = useMemo(() => {
    if (!assessment?.signals?.length) return {}
    const signals = assessment.signals
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          const s = signals[p.dataIndex]
          return `<b>${s.name}</b><br/>` +
            `方向: ${s.direction}<br/>` +
            `评分: ${s.score > 0 ? '+' : ''}${s.score}<br/>` +
            `${s.detail}`
        },
      },
      grid: { left: 100, right: 30, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: signals.map((s: AssessmentSignal) => s.name),
        axisLabel: { fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        name: '信号评分',
      },
      series: [{
        type: 'bar',
        data: signals.map((s: AssessmentSignal) => ({
          value: s.score,
          itemStyle: { color: s.score > 0 ? '#e74c3c' : s.score < 0 ? '#27ae60' : '#666' },
        })),
        barWidth: '50%',
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => {
            const v = params.value
            return v > 0 ? `+${v}` : `${v}`
          },
          fontSize: 12,
        },
      }],
    }
  }, [assessment])

  const northboundChartOption = useMemo(() => {
    if (!northbound?.history?.length) return {}
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 80, right: 30, top: 20, bottom: 60 },
      xAxis: {
        type: 'category',
        data: northbound.history.map((h: any) => h.date),
        axisLabel: { rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        name: '净买入(亿)',
        axisLabel: { formatter: (v: number) => v.toFixed(0) },
      },
      series: [{
        type: 'bar',
        data: northbound.history.map((h: any) => ({
          value: h.net_buy,
          itemStyle: { color: h.net_buy >= 0 ? '#e74c3c' : '#27ae60' },
        })),
      }],
    }
  }, [northbound])

  const marginChartOption = useMemo(() => {
    if (!margin?.sh_data?.length) return {}
    return {
      tooltip: { trigger: 'axis', formatter: (params: any) => `日期: ${params[0].name}<br/>融资余额: ${(params[0].value / 1e8).toFixed(2)}亿` },
      grid: { left: 100, right: 30, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: margin.sh_data.map((d: any) => d.date),
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: '融资余额',
        axisLabel: { formatter: (v: number) => (v / 1e8).toFixed(0) + '亿' },
      },
      series: [{
        type: 'line',
        data: margin.sh_data.map((d: any) => d.margin_balance),
        smooth: true,
        lineStyle: { color: '#3498db' },
        areaStyle: { color: 'rgba(52,152,219,0.1)' },
      }],
    }
  }, [margin])

  const holdingsTrendChartOption = useMemo(() => {
    if (holdingsTrends.length === 0 || holdingsTrendQuarters.length === 0) return {}
    // 取Top15变动最大的记录
    const top15 = holdingsTrends.slice(0, 15)
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const idx = params[0]?.dataIndex
          if (idx == null) return ''
          const t = top15[idx]
          let html = `<b>${t.name} (${t.code})</b><br/>`
          html += `机构: ${t.holder_type}<br/>`
          html += `趋势: ${t.trend_direction}<br/>`
          html += `总变动: ${t.total_change_pct > 0 ? '+' : ''}${t.total_change_pct.toFixed(2)}%`
          return html
        },
      },
      grid: { left: 100, right: 30, top: 20, bottom: 80 },
      xAxis: {
        type: 'category',
        data: top15.map(t => `${t.name}\n${t.holder_type}`),
        axisLabel: { rotate: 45, fontSize: 10, interval: 0 },
      },
      yAxis: {
        type: 'value',
        name: '持仓变动(%)',
        axisLabel: { formatter: (v: number) => v.toFixed(1) + '%' },
      },
      series: [{
        type: 'bar',
        data: top15.map(t => ({
          value: t.total_change_pct,
          itemStyle: { color: t.total_change_pct > 0 ? '#e74c3c' : '#27ae60' },
        })),
        barWidth: '60%',
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => `${params.value > 0 ? '+' : ''}${params.value.toFixed(1)}%`,
          fontSize: 10,
        },
      }],
    }
  }, [holdingsTrends, holdingsTrendQuarters])

  const industryChartOption = useMemo(() => {
    const entries = Object.entries(industryData)
    if (entries.length === 0) return {}
    // 取权重>=1%的行业
    const significant = entries.filter(([_, d]) => d.weight >= 1)
    const otherWeight = entries.filter(([_, d]) => d.weight < 1).reduce((s, [_, d]) => s + d.weight, 0)
    const pieData = significant.map(([name, d]) => ({
      name,
      value: d.weight,
      itemStyle: {},
    }))
    if (otherWeight > 0) {
      pieData.push({ name: '其他', value: Math.round(otherWeight * 100) / 100, itemStyle: { color: '#666' } })
    }
    return {
      tooltip: {
        formatter: (params: any) => {
          const d = industryData[params.name]
          if (!d) return `${params.name}: ${params.value}%`
          return `<b>${params.name}</b><br/>` +
            `权重: ${d.weight}%<br/>` +
            `持仓市值: ${formatAmount(d.total_value)}<br/>` +
            `股票数: ${d.stock_count}只<br/>` +
            `参与机构: ${d.holder_types.join(', ')}`
        },
      },
      legend: {
        type: 'scroll',
        bottom: 0,
        textStyle: { color: '#999', fontSize: 11 },
      },
      series: [{
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['50%', '45%'],
        data: pieData,
        label: {
          show: true,
          formatter: '{b}: {d}%',
          fontSize: 11,
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' },
        },
      }],
    }
  }, [industryData])

  // Group holdings - memoized
  const groupedHoldings = useMemo(() => {
    if (groupBy !== 'institution') return null
    const groups: Record<string, Holding[]> = {}
    holdings.forEach(h => {
      if (!groups[h.holder_type]) groups[h.holder_type] = []
      groups[h.holder_type].push(h)
    })
    return groups
  }, [holdings, groupBy])

  // ============ Render functions ============

  const renderHoldings = () => {
    if (holdingsLoading) return <LoadingSpinner />
    if (holdings.length === 0) return <EmptyState title="暂无持仓数据" />

    return (
      <div>
        {/* Summary cards */}
        {holdingsSummary && (
          <StatCardGroup columns={4} style={{ marginBottom: 16 }}>
            <StatCard label="持仓总市值" value={formatAmount(holdingsSummary.total_market_value)} color="#f39c12" />
            <StatCard label="持仓数量" value={`${holdingsSummary.total_positions} 只`} color="#3498db" />
            {Object.entries(holdingsSummary.by_type || {}).map(([type, info]: [string, any]) => (
              <StatCard key={type} label={type} value={formatAmount(info.total_value)} color="#2ecc71" />
            ))}
          </StatCardGroup>
        )}

        {/* Controls */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>报告期: {holdingsEndDate}</span>
          <div style={{ flex: 1 }} />
          <button
            onClick={() => setGroupBy(g => g === 'institution' ? 'stock' : 'institution')}
            style={{ background: '#1a1a2e', color: '#ccc', border: '1px solid #333', borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}
          >
            {groupBy === 'institution' ? '按股票分组' : '按机构分组'}
          </button>
        </div>

        {/* Table */}
        {groupBy === 'institution' && groupedHoldings ? (
          Object.entries(groupedHoldings).map(([type, items]) => (
            <div key={type} style={{ marginBottom: 16 }}>
              <div style={{ color: '#f39c12', fontSize: 14, fontWeight: 600, marginBottom: 8, borderBottom: '1px solid #333', paddingBottom: 4 }}>
                {type} ({items.length}只)
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #333' }}>
                      <th style={{ ...thStyle, width: '12%' }}>代码</th>
                      <th style={{ ...thStyle, width: '18%' }}>名称</th>
                      <th style={{ ...thStyle, width: '18%' }}>持股数</th>
                      <th style={{ ...thStyle, width: '16%' }}>占流通比</th>
                      <th style={{ ...thStyle, width: '16%' }}>变动</th>
                      <th style={{ ...thStyle, width: '20%' }}>持仓市值</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((h, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                        <td style={tdStyle}>{h.code}</td>
                        <td style={tdStyle}>{h.name}</td>
                        <td style={tdStyle}>{formatShares(h.hold_num)}</td>
                        <td style={tdStyle}>{h.hold_ratio.toFixed(2)}%</td>
                        <td style={{ ...tdStyle, color: changeColor(h.hold_change) }}>
                          {h.hold_change > 0 ? '+' : ''}{formatShares(h.hold_change)}
                        </td>
                        <td style={tdStyle}>{formatAmount(h.hold_market_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #333' }}>
                  <th style={{ ...thStyle, width: '10%' }}>代码</th>
                  <th style={{ ...thStyle, width: '10%' }}>名称</th>
                  <th style={{ ...thStyle, width: '16%' }}>机构</th>
                  <th style={{ ...thStyle, width: '8%' }}>类型</th>
                  <th style={{ ...thStyle, width: '14%' }}>持股数</th>
                  <th style={{ ...thStyle, width: '12%' }}>占流通比</th>
                  <th style={{ ...thStyle, width: '12%' }}>变动</th>
                  <th style={{ ...thStyle, width: '18%' }}>持仓市值</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    <td style={tdStyle}>{h.code}</td>
                    <td style={tdStyle}>{h.name}</td>
                    <td style={tdStyle}>{h.holder_name}</td>
                    <td style={tdStyle}>
                      <span style={{ background: '#1a1a2e', padding: '2px 6px', borderRadius: 3, fontSize: 11 }}>
                        {h.holder_type}
                      </span>
                    </td>
                    <td style={tdStyle}>{formatShares(h.hold_num)}</td>
                    <td style={tdStyle}>{h.hold_ratio.toFixed(2)}%</td>
                    <td style={{ ...tdStyle, color: changeColor(h.hold_change) }}>
                      {h.hold_change > 0 ? '+' : ''}{formatShares(h.hold_change)}
                    </td>
                    <td style={tdStyle}>{formatAmount(h.hold_market_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderETFFlows = () => {
    if (etfLoading) return <LoadingSpinner />

    const etfEntries = Object.entries(etfData)

    return (
      <div>
        {/* Summary */}
        {etfDataType === 'history' && (
          <div style={{ background: '#2a2a1e', border: '1px solid #f39c12', borderRadius: 6, padding: '8px 14px', marginBottom: 12, color: '#f39c12', fontSize: 12 }}>
            当前为盘前/盘后，显示上一交易日行情数据，资金流向数据仅交易时段可获取
          </div>
        )}
        <StatCardGroup columns={4} style={{ marginBottom: 16 }}>
          <StatCard label="今日主力净流入合计" value={`${totalMainInflow >= 0 ? '+' : ''}${formatAmount(totalMainInflow)}`} color={totalMainInflow >= 0 ? '#e74c3c' : '#27ae60'} />
          {etfEntries.map(([code, etf]) => (
            <StatCard key={code} label={etf.name} value={`${etf.main_inflow >= 0 ? '+' : ''}${formatAmount(etf.main_inflow)}`} color={etf.main_inflow >= 0 ? '#e74c3c' : '#27ae60'} />
          ))}
        </StatCardGroup>

        {/* Chart */}
        {etfEntries.length > 0 && (
          <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>大盘ETF主力资金净流入</div>
            <ReactECharts option={etfFlowChartOption} style={{ height: 300 }} />
          </div>
        )}

        {/* Detail table */}
        <div style={{ color: '#ccc', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>资金流向明细</div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #333' }}>
                <th style={{ ...thStyle, width: '14%' }}>ETF</th>
                <th style={{ ...thStyle, width: '9%' }}>价格</th>
                <th style={{ ...thStyle, width: '9%' }}>涨跌幅</th>
                <th style={{ ...thStyle, width: '11%' }}>成交额</th>
                <th style={{ ...thStyle, width: '11%' }}>主力净流入</th>
                <th style={{ ...thStyle, width: '11%' }}>超大单</th>
                <th style={{ ...thStyle, width: '11%' }}>大单</th>
                <th style={{ ...thStyle, width: '11%' }}>中单</th>
                <th style={{ ...thStyle, width: '13%' }}>小单</th>
              </tr>
            </thead>
            <tbody>
              {etfEntries.map(([code, etf]) => (
                <tr key={code} style={{ borderBottom: '1px solid #222' }}>
                  <td style={tdStyle}>
                    <div style={{ fontWeight: 600 }}>{code}</div>
                    <div style={{ fontSize: 11, color: '#999' }}>{etf.name}</div>
                  </td>
                  <td style={tdStyle}>{etf.price.toFixed(3)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.change_pct) }}>
                    {etf.change_pct >= 0 ? '+' : ''}{etf.change_pct.toFixed(2)}%
                  </td>
                  <td style={tdStyle}>{formatAmount(etf.turnover)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.main_inflow), fontWeight: 700 }}>
                    {formatAmount(etf.main_inflow)}
                  </td>
                  <td style={{ ...tdStyle, color: changeColor(etf.super_inflow) }}>{formatAmount(etf.super_inflow)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.big_inflow) }}>{formatAmount(etf.big_inflow)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.mid_inflow) }}>{formatAmount(etf.mid_inflow)}</td>
                  <td style={{ ...tdStyle, color: changeColor(etf.small_inflow) }}>{formatAmount(etf.small_inflow)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderAlerts = () => {
    if (alertsLoading) return <LoadingSpinner />

    return (
      <div>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>量比阈值:</span>
          {[1.5, 2.0, 2.5, 3.0].map(t => (
            <button key={t} onClick={() => setAlertThreshold(t)}
              style={{ background: alertThreshold === t ? '#e74c3c' : '#1a1a2e', color: '#ccc', border: '1px solid #333', borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}>
              {t}
            </button>
          ))}
          <span style={{ color: '#666', fontSize: 12 }}>扫描 {scannedCount} 只蓝筹</span>
        </div>

        {alerts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>当前无量比 &gt;= {alertThreshold} 的异动</div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>蓝筹股表现平稳</div>
          </div>
        ) : (
          <>
            {/* Chart */}
            <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>Top10 量比</div>
              <ReactECharts option={alertChartOption} style={{ height: 280 }} />
            </div>

            {/* Alert list */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #333' }}>
                    <th style={{ ...thStyle, width: '8%' }}>严重度</th>
                    <th style={{ ...thStyle, width: '10%' }}>代码</th>
                    <th style={{ ...thStyle, width: '10%' }}>名称</th>
                    <th style={{ ...thStyle, width: '9%' }}>价格</th>
                    <th style={{ ...thStyle, width: '9%' }}>涨跌幅</th>
                    <th style={{ ...thStyle, width: '8%' }}>量比</th>
                    <th style={{ ...thStyle, width: '11%' }}>成交额</th>
                    <th style={{ ...thStyle, width: '35%' }}>说明</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                      <td style={tdStyle}>
                        <span style={{
                          background: severityColor(a.severity),
                          color: '#fff',
                          padding: '2px 8px',
                          borderRadius: 3,
                          fontSize: 11,
                          fontWeight: 600,
                        }}>
                          {severityLabel(a.severity)}
                        </span>
                      </td>
                      <td style={tdStyle}>{a.code}</td>
                      <td style={tdStyle}>{a.name}</td>
                      <td style={tdStyle}>{a.price.toFixed(2)}</td>
                      <td style={{ ...tdStyle, color: changeColor(a.change_pct) }}>
                        {a.change_pct > 0 ? '+' : ''}{a.change_pct.toFixed(2)}%
                      </td>
                      <td style={{ ...tdStyle, color: severityColor(a.severity), fontWeight: 700 }}>
                        {a.volume_ratio.toFixed(2)}
                      </td>
                      <td style={tdStyle}>{formatAmount(a.turnover)}</td>
                      <td style={{ ...tdStyle, color: '#999', fontSize: 12, whiteSpace: 'normal', wordBreak: 'break-all' }}>{a.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    )
  }

  const renderDragonTiger = () => {
    if (dtLoading) return <LoadingSpinner />

    return (
      <div>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>查询天数:</span>
          {[3, 5, 10, 15].map(d => (
            <button key={d} onClick={() => setDtDays(d)}
              style={{ background: dtDays === d ? '#e74c3c' : '#1a1a2e', color: '#ccc', border: '1px solid #333', borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}>
              {d}天
            </button>
          ))}
          <div style={{ flex: 1 }} />
          {dtSummary && (
            <span style={{ color: '#666', fontSize: 12 }}>
              {dtSummary.date_range} · 共{dtSummary.total_records}条记录
            </span>
          )}
        </div>

        {/* Summary */}
        {dtSummary && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>机构净买入合计</div>
              <div style={{ color: dtSummary.total_net >= 0 ? '#e74c3c' : '#27ae60', fontSize: 20, fontWeight: 700 }}>
                {dtSummary.total_net >= 0 ? '+' : ''}{formatAmount(dtSummary.total_net)}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>机构买入总额</div>
              <div style={{ color: '#e74c3c', fontSize: 16, fontWeight: 600 }}>{formatAmount(dtSummary.total_buy)}</div>
            </div>
            <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>机构卖出总额</div>
              <div style={{ color: '#27ae60', fontSize: 16, fontWeight: 600 }}>{formatAmount(dtSummary.total_sell)}</div>
            </div>
            <div style={{ flex: 1, minWidth: 100, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>净买入/卖出</div>
              <div style={{ color: '#3498db', fontSize: 16, fontWeight: 600 }}>
                {dtSummary.net_buy_count} / {dtSummary.net_sell_count}
              </div>
            </div>
          </div>
        )}

        {dtRecords.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>近{dtDays}天无机构龙虎榜数据</div>
          </div>
        ) : (
          <>
            {/* Chart */}
            <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>机构净买入Top10</div>
              <ReactECharts option={dtChartOption} style={{ height: 300 }} />
            </div>

            {/* Table */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #333' }}>
                    <th style={{ ...thStyle, width: '8%' }}>代码</th>
                    <th style={{ ...thStyle, width: '10%' }}>名称</th>
                    <th style={{ ...thStyle, width: '8%' }}>涨跌幅</th>
                    <th style={{ ...thStyle, width: '8%' }}>买方机构</th>
                    <th style={{ ...thStyle, width: '8%' }}>卖方机构</th>
                    <th style={{ ...thStyle, width: '13%' }}>机构买入</th>
                    <th style={{ ...thStyle, width: '13%' }}>机构卖出</th>
                    <th style={{ ...thStyle, width: '13%' }}>机构净买入</th>
                    <th style={{ ...thStyle, width: '7%' }}>占比</th>
                    <th style={{ ...thStyle, width: '12%' }}>上榜原因</th>
                  </tr>
                </thead>
                <tbody>
                  {dtRecords.map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                      <td style={tdStyle}>{r.code}</td>
                      <td style={tdStyle}>{r.name}</td>
                      <td style={{ ...tdStyle, color: changeColor(r.change_pct) }}>
                        {r.change_pct >= 0 ? '+' : ''}{r.change_pct.toFixed(2)}%
                      </td>
                      <td style={tdStyle}>{r.buy_inst_count}</td>
                      <td style={tdStyle}>{r.sell_inst_count}</td>
                      <td style={{ ...tdStyle, color: '#e74c3c' }}>{formatAmount(r.inst_buy_amount)}</td>
                      <td style={{ ...tdStyle, color: '#27ae60' }}>{formatAmount(r.inst_sell_amount)}</td>
                      <td style={{ ...tdStyle, color: changeColor(r.inst_net_amount), fontWeight: 700 }}>
                        {r.inst_net_amount >= 0 ? '+' : ''}{formatAmount(r.inst_net_amount)}
                      </td>
                      <td style={tdStyle}>{r.inst_net_ratio.toFixed(2)}%</td>
                      <td style={{ ...tdStyle, color: '#999', fontSize: 11, whiteSpace: 'normal', wordBreak: 'break-all' }}>
                        {r.reason.length > 20 ? r.reason.slice(0, 20) + '...' : r.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    )
  }

  const renderBlockTrades = () => {
    if (btLoading) return <LoadingSpinner />

    return (
      <div>
        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
          <span style={{ color: '#999', fontSize: 13 }}>查询天数:</span>
          {[3, 5, 10, 15].map(d => (
            <button key={d} onClick={() => setBtDays(d)}
              style={{ background: btDays === d ? '#e74c3c' : '#1a1a2e', color: '#ccc', border: '1px solid #333', borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}>
              {d}天
            </button>
          ))}
          <div style={{ flex: 1 }} />
          {btSummary && (
            <span style={{ color: '#666', fontSize: 12 }}>
              {btSummary.date_range} · 机构交易{btSummary.inst_trade_count}笔
            </span>
          )}
        </div>

        {/* Summary */}
        {btSummary && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>机构大宗净额</div>
              <div style={{ color: btSummary.inst_net_amount >= 0 ? '#e74c3c' : '#27ae60', fontSize: 20, fontWeight: 700 }}>
                {btSummary.inst_net_amount >= 0 ? '+' : ''}{formatAmount(btSummary.inst_net_amount)}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>机构买入</div>
              <div style={{ color: '#e74c3c', fontSize: 16, fontWeight: 600 }}>{formatAmount(btSummary.inst_buy_amount)}</div>
            </div>
            <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>机构卖出</div>
              <div style={{ color: '#27ae60', fontSize: 16, fontWeight: 600 }}>{formatAmount(btSummary.inst_sell_amount)}</div>
            </div>
            <div style={{ flex: 1, minWidth: 100, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>总交易笔数</div>
              <div style={{ color: '#3498db', fontSize: 16, fontWeight: 600 }}>{btSummary.total_trade_count}</div>
            </div>
          </div>
        )}

        {btRecords.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>近{btDays}天无机构大宗交易</div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #333' }}>
                  <th style={{ ...thStyle, width: '10%' }}>交易日期</th>
                  <th style={{ ...thStyle, width: '8%' }}>代码</th>
                  <th style={{ ...thStyle, width: '10%' }}>名称</th>
                  <th style={{ ...thStyle, width: '8%' }}>方向</th>
                  <th style={{ ...thStyle, width: '8%' }}>成交价</th>
                  <th style={{ ...thStyle, width: '10%' }}>成交量</th>
                  <th style={{ ...thStyle, width: '12%' }}>成交额</th>
                  <th style={{ ...thStyle, width: '17%' }}>买方</th>
                  <th style={{ ...thStyle, width: '17%' }}>卖方</th>
                </tr>
              </thead>
              <tbody>
                {btRecords.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    <td style={tdStyle}>{r.trade_date}</td>
                    <td style={tdStyle}>{r.code}</td>
                    <td style={tdStyle}>{r.name}</td>
                    <td style={tdStyle}>
                      <span style={{
                        background: r.is_inst_buy ? '#e74c3c' : '#27ae60',
                        color: '#fff',
                        padding: '2px 8px',
                        borderRadius: 3,
                        fontSize: 11,
                        fontWeight: 600,
                      }}>
                        {r.inst_direction}
                      </span>
                    </td>
                    <td style={tdStyle}>{r.price.toFixed(2)}</td>
                    <td style={tdStyle}>{formatShares(r.volume)}</td>
                    <td style={tdStyle}>{formatAmount(r.amount)}</td>
                    <td style={{ ...tdStyle, fontSize: 11, color: '#999' }}>
                      {r.buyer.length > 15 ? r.buyer.slice(0, 15) + '...' : r.buyer}
                    </td>
                    <td style={{ ...tdStyle, fontSize: 11, color: '#999' }}>
                      {r.seller.length > 15 ? r.seller.slice(0, 15) + '...' : r.seller}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderETFShares = () => {
    if (etfSharesLoading) return <LoadingSpinner />

    return (
      <div>
        <div style={{ background: '#1a1a2e', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ color: '#f39c12', fontSize: 13, marginBottom: 4 }}>ETF份额变动追踪</div>
          <div style={{ color: '#999', fontSize: 12 }}>
            追踪主要宽基ETF的份额变动（申购/赎回）。份额大幅增加通常意味着国家队等大资金申购入场，是重要的资金信号。
          </div>
        </div>

        {etfShares.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>暂无ETF份额变动数据</div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #333' }}>
                  <th style={{ ...thStyle, width: '10%' }}>代码</th>
                  <th style={{ ...thStyle, width: '14%' }}>名称</th>
                  <th style={{ ...thStyle, width: '12%' }}>最新日期</th>
                  <th style={{ ...thStyle, width: '16%' }}>最新份额</th>
                  <th style={{ ...thStyle, width: '16%' }}>一周前份额</th>
                  <th style={{ ...thStyle, width: '14%' }}>份额变动</th>
                  <th style={{ ...thStyle, width: '10%' }}>变动率</th>
                  <th style={{ ...thStyle, width: '8%' }}>信号</th>
                </tr>
              </thead>
              <tbody>
                {etfShares.map((e, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                    <td style={tdStyle}>{e.code}</td>
                    <td style={tdStyle}>{e.name}</td>
                    <td style={tdStyle}>{e.latest_date}</td>
                    <td style={tdStyle}>{formatShares(e.latest_shares)}</td>
                    <td style={tdStyle}>{e.week_ago_shares ? formatShares(e.week_ago_shares) : '-'}</td>
                    <td style={{ ...tdStyle, color: changeColor(e.share_change) }}>
                      {e.share_change > 0 ? '+' : ''}{formatShares(e.share_change)}
                    </td>
                    <td style={{ ...tdStyle, color: changeColor(e.share_change_pct), fontWeight: 700 }}>
                      {e.share_change_pct > 0 ? '+' : ''}{e.share_change_pct.toFixed(2)}%
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        background: e.signal === '大幅申购' ? '#e74c3c' : e.signal === '申购' ? '#f39c12' : e.signal === '赎回' ? '#27ae60' : '#666',
                        color: '#fff',
                        padding: '2px 8px',
                        borderRadius: 3,
                        fontSize: 11,
                        fontWeight: 600,
                      }}>
                        {e.signal}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  const renderNorthbound = () => {
    if (northboundLoading) return <LoadingSpinner />
    if (!northbound) return <EmptyState title="暂无数据" />

    const sh = northbound.today?.sh_connect
    const sz = northbound.today?.sz_connect
    const totalNet = northbound.total_net_buy || 0

    return (
      <div>
        <div style={{ background: '#1a1a2e', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ color: '#f39c12', fontSize: 13, marginBottom: 4 }}>北向资金（沪深港通）</div>
          <div style={{ color: '#999', fontSize: 12 }}>
            北向资金是外资进入A股的主要通道，是机构最关注的资金信号之一。净买入=看好A股，净卖出=撤退。
          </div>
        </div>

        {/* Summary */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 180, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
            <div style={{ color: '#999', fontSize: 12 }}>北向资金合计</div>
            <div style={{ color: totalNet >= 0 ? '#e74c3c' : '#27ae60', fontSize: 22, fontWeight: 700 }}>
              {totalNet >= 0 ? '+' : ''}{totalNet.toFixed(2)}亿
            </div>
          </div>
          {sh && (
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>沪股通</div>
              <div style={{ color: sh.net_buy >= 0 ? '#e74c3c' : '#27ae60', fontSize: 18, fontWeight: 600 }}>
                {sh.net_buy >= 0 ? '+' : ''}{sh.net_buy.toFixed(2)}亿
              </div>
            </div>
          )}
          {sz && (
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>深股通</div>
              <div style={{ color: sz.net_buy >= 0 ? '#e74c3c' : '#27ae60', fontSize: 18, fontWeight: 600 }}>
                {sz.net_buy >= 0 ? '+' : ''}{sz.net_buy.toFixed(2)}亿
              </div>
            </div>
          )}
        </div>

        {/* History chart */}
        {northbound.history?.length > 0 && (
          <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>近30日北向资金净买入趋势</div>
            <ReactECharts option={northboundChartOption} style={{ height: 300 }} />
          </div>
        )}

        <div style={{ color: '#666', fontSize: 11, textAlign: 'center' }}>
          数据来源: {northbound.data_source} | 更新时间: {northbound.update_time}
        </div>
      </div>
    )
  }

  const renderMargin = () => {
    if (marginLoading) return <LoadingSpinner />
    if (!margin) return <EmptyState title="暂无数据" />

    const latestSh = margin.latest_sh
    const latestSz = margin.latest_sz
    const trendLabel = margin.trend === 'increasing' ? '融资增加（看多）' :
      margin.trend === 'decreasing' ? '融资减少（看空）' : '平稳'
    const trendColor = margin.trend === 'increasing' ? '#e74c3c' :
      margin.trend === 'decreasing' ? '#27ae60' : '#999'

    return (
      <div>
        <div style={{ background: '#1a1a2e', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ color: '#f39c12', fontSize: 13, marginBottom: 4 }}>融资融券监控</div>
          <div style={{ color: '#999', fontSize: 12 }}>
            融资余额增加=杠杆资金看多入场，融券余额增加=看空力量增加。关注融资余额变化趋势。
          </div>
        </div>

        {/* Summary */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 180, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
            <div style={{ color: '#999', fontSize: 12 }}>趋势判断</div>
            <div style={{ color: trendColor, fontSize: 20, fontWeight: 700 }}>{trendLabel}</div>
            <div style={{ color: '#999', fontSize: 11, marginTop: 4 }}>
              融资余额变动: {margin.margin_change >= 0 ? '+' : ''}{(margin.margin_change / 1e8).toFixed(2)}亿
            </div>
          </div>
          {latestSh && (
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>上交所融资余额</div>
              <div style={{ color: '#3498db', fontSize: 16, fontWeight: 600 }}>
                {(latestSh.margin_balance / 1e8).toFixed(2)}亿
              </div>
              <div style={{ color: '#999', fontSize: 11 }}>
                融资买入: {(latestSh.margin_buy / 1e8).toFixed(2)}亿
              </div>
            </div>
          )}
          {latestSz && (
            <div style={{ flex: 1, minWidth: 150, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
              <div style={{ color: '#999', fontSize: 12 }}>深交所融资余额</div>
              <div style={{ color: '#3498db', fontSize: 16, fontWeight: 600 }}>
                {(latestSz.margin_balance / 1e8).toFixed(2)}亿
              </div>
              <div style={{ color: '#999', fontSize: 11 }}>
                融资买入: {(latestSz.margin_buy / 1e8).toFixed(2)}亿
              </div>
            </div>
          )}
        </div>

        {/* Chart */}
        {margin.sh_data?.length > 0 && (
          <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>上交所融资余额趋势</div>
            <ReactECharts option={marginChartOption} style={{ height: 280 }} />
          </div>
        )}

        <div style={{ color: '#666', fontSize: 11, textAlign: 'center' }}>
          数据来源: {margin.data_source} | 更新时间: {margin.update_time}
        </div>
      </div>
    )
  }

  const renderAssessment = () => {
    if (assessmentLoading) return <LoadingSpinner />
    if (!assessment) return <EmptyState title="暂无数据" />

    const scoreColor = assessment.total_score > 25 ? '#e74c3c' : assessment.total_score > 0 ? '#f39c12' :
      assessment.total_score > -25 ? '#3498db' : '#27ae60'

    return (
      <div>
        {/* Overall Assessment Card */}
        <div style={{
          background: `linear-gradient(135deg, #1a1a2e 0%, ${scoreColor}22 100%)`,
          border: `1px solid ${scoreColor}44`,
          borderRadius: 12,
          padding: '24px 32px',
          marginBottom: 20,
          textAlign: 'center',
        }}>
          <div style={{ color: '#999', fontSize: 13, marginBottom: 8 }}>国家队动向综合研判</div>
          <div style={{ color: scoreColor, fontSize: 48, fontWeight: 700, lineHeight: 1.2 }}>
            {assessment.total_score > 0 ? '+' : ''}{assessment.total_score}
          </div>
          <div style={{ color: scoreColor, fontSize: 22, fontWeight: 600, marginTop: 8 }}>
            {assessment.assessment}
          </div>
          <div style={{ color: '#999', fontSize: 13, marginTop: 8 }}>
            {assessment.description}
          </div>
          <div style={{ color: '#666', fontSize: 11, marginTop: 8 }}>
            更新时间: {assessment.update_time}
          </div>
        </div>

        {/* Score Chart */}
        {assessment.signals?.length > 0 && (
          <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
            <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>各维度信号评分</div>
            <ReactECharts option={assessmentChartOption} style={{ height: 280 }} />
          </div>
        )}

        {/* Signal Details */}
        <div style={{ color: '#ccc', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>信号明细</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {assessment.signals?.map((s: AssessmentSignal, i: number) => (
            <div key={i} style={{
              background: '#1a1a2e',
              borderRadius: 8,
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 16,
            }}>
              <div style={{ width: 120, flexShrink: 0 }}>
                <div style={{ color: '#ccc', fontSize: 13, fontWeight: 600 }}>{s.name}</div>
                <div style={{ color: '#666', fontSize: 11 }}>权重: {s.weight}</div>
              </div>
              <div style={{
                width: 80,
                flexShrink: 0,
                textAlign: 'center',
              }}>
                <span style={{
                  color: s.score > 0 ? '#e74c3c' : s.score < 0 ? '#27ae60' : '#666',
                  fontSize: 20,
                  fontWeight: 700,
                }}>
                  {s.score > 0 ? '+' : ''}{s.score}
                </span>
              </div>
              <div style={{
                width: 80,
                flexShrink: 0,
                textAlign: 'center',
              }}>
                <span style={{
                  background: s.direction === '流入' || s.direction === '净买入' || s.direction === '净申购' ? '#e74c3c22' :
                    s.direction === '流出' || s.direction === '净卖出' || s.direction === '净赎回' ? '#27ae6022' : '#66666622',
                  color: s.direction === '流入' || s.direction === '净买入' || s.direction === '净申购' ? '#e74c3c' :
                    s.direction === '流出' || s.direction === '净卖出' || s.direction === '净赎回' ? '#27ae60' : '#999',
                  padding: '2px 10px',
                  borderRadius: 3,
                  fontSize: 12,
                  fontWeight: 600,
                }}>
                  {s.direction}
                </span>
              </div>
              <div style={{ flex: 1, color: '#999', fontSize: 12 }}>
                {s.detail}
              </div>
            </div>
          ))}
        </div>

        {/* Methodology */}
        <div style={{
          background: '#1a1a2e',
          borderRadius: 8,
          padding: '16px 20px',
          marginTop: 16,
          borderLeft: '3px solid #f39c12',
        }}>
          <div style={{ color: '#f39c12', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>研判方法说明</div>
          <div style={{ color: '#999', fontSize: 12, lineHeight: 1.8 }}>
            综合研判评分融合以下维度：<br />
            1. <b>ETF主力资金</b>（权重高）— 大盘ETF超大单+大单净流入，国家队常用ETF通道入场<br />
            2. <b>龙虎榜机构</b>（权重中）— 机构专用席位净买卖方向<br />
            3. <b>大宗交易机构</b>（权重中）— 机构专用席位大宗交易方向<br />
            4. <b>ETF份额变动</b>（权重高）— 宽基ETF份额申购/赎回，份额增加=大资金入场<br />
            5. <b>北向资金</b>（权重高）— 沪深港通外资净买入方向<br />
            6. <b>融资融券</b>（权重中）— 杠杆资金融资余额变动方向<br />
            7. <b>市场走势</b>（权重低）— 沪深300趋势背景，提供市场环境参考<br />
            评分范围 -100 ~ +100，多维信号共振时置信度更高。
          </div>
        </div>
      </div>
    )
  }

  const renderHoldingsTrend = () => {
    if (holdingsTrendLoading) return <LoadingSpinner />

    return (
      <div>
        <div style={{ background: '#1a1a2e', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ color: '#f39c12', fontSize: 13, marginBottom: 4 }}>国家队持仓趋势分析</div>
          <div style={{ color: '#999', fontSize: 12 }}>
            追踪最近4个季度的持仓变化，判断国家队是在持续增持还是减持。只显示有变动的记录。
          </div>
          {holdingsTrendQuarters.length > 0 && (
            <div style={{ color: '#666', fontSize: 11, marginTop: 4 }}>
              对比季度: {holdingsTrendQuarters.join(' -> ')}
            </div>
          )}
        </div>

        {holdingsTrends.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>暂无持仓趋势数据</div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>可能需要等待季报披露</div>
          </div>
        ) : (
          <>
            {/* Chart */}
            <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>Top15 持仓变动幅度</div>
              <ReactECharts option={holdingsTrendChartOption} style={{ height: 350 }} />
            </div>

            {/* Summary cards */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ color: '#999', fontSize: 12 }}>持续增持</div>
                <div style={{ color: '#e74c3c', fontSize: 20, fontWeight: 700 }}>
                  {holdingsTrends.filter(t => t.trend_direction === '持续增持').length}
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ color: '#999', fontSize: 12 }}>持续减持</div>
                <div style={{ color: '#27ae60', fontSize: 20, fontWeight: 700 }}>
                  {holdingsTrends.filter(t => t.trend_direction === '持续减持').length}
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ color: '#999', fontSize: 12 }}>总体增持</div>
                <div style={{ color: '#f39c12', fontSize: 20, fontWeight: 700 }}>
                  {holdingsTrends.filter(t => t.trend_direction === '总体增持').length}
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 120, background: '#1a1a2e', borderRadius: 8, padding: '12px 16px' }}>
                <div style={{ color: '#999', fontSize: 12 }}>总变动记录</div>
                <div style={{ color: '#3498db', fontSize: 20, fontWeight: 700 }}>
                  {holdingsTrends.length}
                </div>
              </div>
            </div>

            {/* Table */}
            <div style={{ color: '#ccc', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>持仓变动明细</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, tableLayout: 'fixed' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #333' }}>
                    <th style={{ ...thStyle, width: '8%' }}>代码</th>
                    <th style={{ ...thStyle, width: '12%' }}>名称</th>
                    <th style={{ ...thStyle, width: '10%' }}>机构类型</th>
                    <th style={{ ...thStyle, width: '10%' }}>趋势</th>
                    <th style={{ ...thStyle, width: '14%' }}>总变动幅度</th>
                    <th style={{ ...thStyle, width: '16%' }}>最新持仓市值</th>
                    <th style={{ ...thStyle, width: '30%' }}>各季度持股数</th>
                  </tr>
                </thead>
                <tbody>
                  {holdingsTrends.slice(0, 50).map((t, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                      <td style={tdStyle}>{t.code}</td>
                      <td style={tdStyle}>{t.name}</td>
                      <td style={tdStyle}>
                        <span style={{ background: '#1a1a2e', padding: '2px 6px', borderRadius: 3, fontSize: 11 }}>
                          {t.holder_type}
                        </span>
                      </td>
                      <td style={tdStyle}>
                        <span style={{
                          background: t.trend_direction.includes('增持') ? '#e74c3c22' : t.trend_direction.includes('减持') ? '#27ae6022' : '#66666622',
                          color: t.trend_direction.includes('增持') ? '#e74c3c' : t.trend_direction.includes('减持') ? '#27ae60' : '#999',
                          padding: '2px 8px', borderRadius: 3, fontSize: 11, fontWeight: 600,
                        }}>
                          {t.trend_direction}
                        </span>
                      </td>
                      <td style={{ ...tdStyle, color: changeColor(t.total_change), fontWeight: 700 }}>
                        {t.total_change_pct > 0 ? '+' : ''}{t.total_change_pct.toFixed(2)}%
                      </td>
                      <td style={tdStyle}>{formatAmount(t.latest_value)}</td>
                      <td style={{ ...tdStyle, fontSize: 11, color: '#999', whiteSpace: 'normal', wordBreak: 'break-all' }}>
                        {holdingsTrendQuarters.map(q => {
                          const qd = t.quarters[q]
                          return qd ? `${q.slice(2)}: ${formatShares(qd.hold_num)}` : `${q.slice(2)}: -`
                        }).join(' | ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    )
  }

  const renderIndustryAllocation = () => {
    if (industryLoading) return <LoadingSpinner />

    const entries = Object.entries(industryData)

    return (
      <div>
        <div style={{ background: '#1a1a2e', borderRadius: 8, padding: '12px 16px', marginBottom: 16 }}>
          <div style={{ color: '#f39c12', fontSize: 13, marginBottom: 4 }}>国家队持仓行业配置分析</div>
          <div style={{ color: '#999', fontSize: 12 }}>
            分析国家队持仓的行业分布，判断资金重点布局方向。持仓市值合计: {formatAmount(industryTotalValue)}
          </div>
        </div>

        {entries.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>-</div>
            <div>暂无行业配置数据</div>
          </div>
        ) : (
          <>
            {/* Pie chart */}
            <div style={{ background: '#1a1a2e', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ color: '#ccc', fontSize: 13, marginBottom: 8 }}>行业配置权重分布</div>
              <ReactECharts option={industryChartOption} style={{ height: 400 }} />
            </div>

            {/* Industry cards */}
            <div style={{ color: '#ccc', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>行业详情</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {entries.map(([name, data]) => (
                <div key={name} style={{
                  background: '#1a1a2e',
                  borderRadius: 8,
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                }}>
                  <div style={{ width: 80, flexShrink: 0 }}>
                    <div style={{ color: '#f39c12', fontSize: 14, fontWeight: 600 }}>{name}</div>
                    <div style={{ color: '#666', fontSize: 11 }}>{data.stock_count}只股票</div>
                  </div>
                  <div style={{ width: 80, flexShrink: 0, textAlign: 'center' }}>
                    <div style={{ color: '#3498db', fontSize: 18, fontWeight: 700 }}>{data.weight}%</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: '#999', fontSize: 12, marginBottom: 4 }}>
                      持仓市值: {formatAmount(data.total_value)} | 参与: {data.holder_types.join(', ')}
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {data.top_stocks.map(s => (
                        <span key={s.code} style={{
                          background: '#222',
                          padding: '2px 8px',
                          borderRadius: 3,
                          fontSize: 11,
                          color: '#ccc',
                        }}>
                          {s.name}({formatAmount(s.value)})
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="cb-page">
      <PageSection title="国家队监控" compact>
        <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: 13 }}>
          北向资金 · ETF资金/份额 · 龙虎榜 · 大宗交易 · 融资融券 · 持仓趋势 · 行业配置 · 综合研判
        </p>
      </PageSection>

      <TabBar
        tabs={TABS.map(t => ({ key: t.key, label: `${t.icon}${t.label}` }))}
        activeKey={activeTab}
        onChange={k => setActiveTab(k as TabType)}
        style={{ marginBottom: 16 }}
      />

      {/* Content */}
      {activeTab === 'assessment' && renderAssessment()}
      {activeTab === 'northbound' && renderNorthbound()}
      {activeTab === 'holdings' && renderHoldings()}
      {activeTab === 'etfFlows' && renderETFFlows()}
      {activeTab === 'etfShares' && renderETFShares()}
      {activeTab === 'dragonTiger' && renderDragonTiger()}
      {activeTab === 'blockTrades' && renderBlockTrades()}
      {activeTab === 'margin' && renderMargin()}
      {activeTab === 'alerts' && renderAlerts()}
      {activeTab === 'holdingsTrend' && renderHoldingsTrend()}
      {activeTab === 'industryAllocation' && renderIndustryAllocation()}
    </div>
  )
}
