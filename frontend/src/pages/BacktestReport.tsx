import { useState, useMemo, useCallback, useEffect } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { PageSection, StatCard, StatCardGroup, LoadingSpinner, EmptyState } from '../components/ui'

const API_BASE = '/api'

// ============================================================
// Types
// ============================================================

interface StrategyInfo {
  key: string
  name: string
  description: string
}

interface BenchmarkInfo {
  key: string
  name: string
}

interface EquityPoint {
  date: string
  total_value: number
  cash: number
  holdings_value: number
}

interface DrawdownPoint {
  date: string
  drawdown: number
}

interface TradeRecord {
  date: string
  action: 'buy' | 'sell'
  code: string
  price: number
  shares: number
  gross_amount: number
  cost: number
  net_amount: number
}

interface Holding {
  code: string
  name: string
  shares: number
  price: number
  value: number
  industry: string
}

interface BacktestResult {
  strategy_name: string
  strategy_key: string
  description: string
  start_date: string
  end_date: string
  initial_capital: number
  rebalance_frequency: string
  top_n: number
  benchmark_key: string
  benchmark_name: string
  cost_config: { commission_rate: number; slippage_rate: number; round_trip_cost_pct: number }
  // 收益
  total_return: number
  annual_return: number
  cumulative_return: number
  benchmark_return: number
  benchmark_annual_return: number
  excess_return: number
  // 风险
  max_drawdown: number
  max_drawdown_duration: number
  volatility: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  // 交易
  win_rate: number
  profit_loss_ratio: number
  total_trades: number
  total_cost: number
  cost_ratio: number
  // 希腊字母
  alpha: number
  beta: number
  information_ratio: number
  tracking_error: number
  // 分年度
  yearly_returns: Record<string, number>
  yearly_excess_returns: Record<string, number>
  // 市场环境
  bull_market_return: number
  bear_market_return: number
  sideways_market_return: number
  // 曲线数据
  equity_curve: EquityPoint[]
  drawdown_curve: DrawdownPoint[]
  monthly_returns: number[]
  monthly_benchmark_returns: number[]
  // 持仓
  top_holdings: Holding[]
  sector_allocation: Record<string, number>
}

interface ValidityAnalysis {
  is_effective: boolean
  score: number
  strengths: string[]
  weaknesses: string[]
  conditions: string[]
  recommendations: string[]
}

interface IneffectivenessAnalysis {
  ineffective_scenarios: Array<{ scenario: string; description: string; implication: string }>
  risk_factors: Array<{ factor: string; description: string; impact: string }>
  market_regime_sensitivity: Array<{ regime: string; description: string; implication: string }>
  data_quality_issues: Array<{ issue: string; description: string; mitigation: string }>
}

interface BacktestResponse {
  backtest_result: BacktestResult
  validity_analysis: ValidityAnalysis
  ineffectiveness_analysis: IneffectivenessAnalysis
}

interface CompareResult {
  strategies: Array<{
    strategy: string
    name: string
    metrics: Record<string, number>
    analysis: ValidityAnalysis
    equity_curve: EquityPoint[]
    drawdown_curve: DrawdownPoint[]
  }>
  comparison: Array<{
    strategy: string
    name: string
    annual_return: number
    total_return: number
    max_drawdown: number
    sharpe: number
    sortino: number
    calmar: number
    volatility: number
    win_rate: number
    excess_return: number
    is_effective: boolean
    score: number
  }>
}

// ============================================================
// Helpers
// ============================================================

const getReturnColor = (v: number) => v > 0 ? '#3fb950' : v < 0 ? '#f85149' : '#8b949e'
const getScoreColor = (score: number) => score >= 70 ? '#3fb950' : score >= 50 ? '#d29922' : '#f85149'
const metricLabel = (key: string) => {
  const map: Record<string, string> = {
    annual_return: '年化收益', total_return: '总收益', max_drawdown: '最大回撤',
    sharpe_ratio: '夏普比率', sortino_ratio: 'Sortino', calmar_ratio: 'Calmar',
    volatility: '波动率', win_rate: '胜率(月)', excess_return: '超额收益',
    information_ratio: '信息比率', benchmark_return: '基准收益',
  }
  return map[key] || key
}

// ============================================================
// Component
// ============================================================

export default function BacktestReport() {
  // 策略/基准列表
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([])

  // 参数
  const [strategy, setStrategy] = useState('export_champion')
  const [startDate, setStartDate] = useState('2020-01-01')
  const [endDate, setEndDate] = useState('2025-01-01')
  const [rebalanceFreq, setRebalanceFreq] = useState('quarterly')
  const [topN, setTopN] = useState(10)
  const [initialCapital, setInitialCapital] = useState(1000000)
  const [benchmark, setBenchmark] = useState('hs300')
  const [commissionRate, setCommissionRate] = useState(0.0003)
  const [slippageRate, setSlippageRate] = useState(0.001)

  // 数据
  const [data, setData] = useState<BacktestResponse | null>(null)
  const [compareData, setCompareData] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'single' | 'compare'>('single')
  const [showTradeLog, setShowTradeLog] = useState(false)

  // 加载策略列表
  useEffect(() => {
    axios.get(`${API_BASE}/backtest/strategies`).then(res => {
      setStrategies(res.data.strategies || [])
      setBenchmarks(res.data.benchmarks || [])
    }).catch(() => {})
  }, [])

  // 运行单策略回测
  const runBacktest = async () => {
    setLoading(true)
    setError(null)
    setCompareData(null)
    try {
      const res = await axios.get(`${API_BASE}/backtest/backtest`, {
        params: {
          strategy, start_date: startDate, end_date: endDate,
          rebalance_frequency: rebalanceFreq, top_n: topN,
          initial_capital: initialCapital, benchmark,
          commission_rate: commissionRate, slippage_rate: slippageRate,
        },
      })
      setData(res.data)
    } catch (e: any) {
      setError(e.response?.data?.detail || '回测失败')
    } finally {
      setLoading(false)
    }
  }

  // 运行多策略对比
  const runCompare = async () => {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const allStrategies = strategies.map(s => s.key).join(',')
      const res = await axios.get(`${API_BASE}/backtest/compare`, {
        params: {
          strategies: allStrategies,
          start_date: startDate, end_date: endDate,
          rebalance_frequency: rebalanceFreq, top_n: topN,
          initial_capital: initialCapital, benchmark,
        },
      })
      setCompareData(res.data)
    } catch (e: any) {
      setError(e.response?.data?.detail || '对比失败')
    } finally {
      setLoading(false)
    }
  }

  // ============================================================
  // Charts
  // ============================================================

  const result = data?.backtest_result

  const equityChartOption = useMemo(() => {
    if (!result?.equity_curve?.length) return null
    const dates = result.equity_curve.map(p => p.date)
    const values = result.equity_curve.map(p => p.total_value)
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          return `${p.axisValue}<br/>组合净值: ¥${p.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
        },
      },
      legend: { data: ['组合净值', result.benchmark_name || '基准'], textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 80, right: 20, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#9ca3af', formatter: (v: number) => `¥${(v / 10000).toFixed(0)}万` },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(88,166,255,0.15)', handleStyle: { color: '#58a6ff' } },
      ],
      series: [
        {
          name: '组合净值', type: 'line', data: values, smooth: true, symbol: 'none',
          lineStyle: { color: '#58a6ff', width: 2 },
          areaStyle: {
            color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: 'rgba(88,166,255,0.3)' }, { offset: 1, color: 'rgba(88,166,255,0.02)' }],
            },
          },
        },
      ],
    }
  }, [result])

  const drawdownChartOption = useMemo(() => {
    if (!result?.drawdown_curve?.length) return null
    const dates = result.drawdown_curve.map(p => p.date)
    const values = result.drawdown_curve.map(p => p.drawdown)
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', formatter: (params: any) => `${params[0]?.axisValue}<br/>回撤: ${params[0]?.value?.toFixed(2)}%` },
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: '#21262d' } }, max: 0 },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(239,68,68,0.15)', handleStyle: { color: '#ef4444' } },
      ],
      series: [{
        type: 'line', data: values, smooth: true, symbol: 'none',
        lineStyle: { color: '#ef4444', width: 1.5 },
        areaStyle: {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{ offset: 0, color: 'rgba(239,68,68,0.02)' }, { offset: 1, color: 'rgba(239,68,68,0.4)' }],
          },
        },
        markLine: {
          data: [
            { yAxis: -5, lineStyle: { color: '#eab308', type: 'dashed', width: 1 }, label: { formatter: '-5%', color: '#eab308', fontSize: 10 } },
            { yAxis: -10, lineStyle: { color: '#f97316', type: 'dashed', width: 1 }, label: { formatter: '-10%', color: '#f97316', fontSize: 10 } },
            { yAxis: -20, lineStyle: { color: '#ef4444', type: 'dashed', width: 1 }, label: { formatter: '-20%', color: '#ef4444', fontSize: 10 } },
          ],
        },
      }],
    }
  }, [result])

  const yearlyChartOption = useMemo(() => {
    if (!result?.yearly_returns) return null
    const entries = Object.entries(result.yearly_returns).sort(([a], [b]) => a.localeCompare(b))
    if (!entries.length) return null
    const years = entries.map(([y]) => y)
    const returns = entries.map(([, v]) => v)
    const excessEntries = result.yearly_excess_returns || {}
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', formatter: (params: any) => {
        let s = `${params[0].axisValue}年<br/>`
        params.forEach((p: any) => { s += `${p.seriesName}: ${p.value.toFixed(2)}%<br/>` })
        return s
      }},
      legend: { data: ['策略收益', '超额收益'], textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 60, right: 20, top: 35, bottom: 30 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [
        {
          name: '策略收益', type: 'bar', barWidth: '35%',
          data: returns.map(v => ({ value: v, itemStyle: { color: v >= 0 ? '#3fb950' : '#f85149', borderRadius: [4, 4, 0, 0] } })),
        },
        {
          name: '超额收益', type: 'bar', barWidth: '35%',
          data: years.map(y => {
            const ev = excessEntries[y] || 0
            return { value: ev, itemStyle: { color: ev >= 0 ? 'rgba(63,185,80,0.4)' : 'rgba(248,81,73,0.4)', borderRadius: [4, 4, 0, 0] } }
          }),
        },
      ],
    }
  }, [result])

  const monthlyHeatmapOption = useMemo(() => {
    if (!result?.monthly_returns?.length) return null
    // Build heatmap: x=month(1-12), y=year
    const eq = result.equity_curve
    if (!eq?.length) return null
    const data: Array<[number, number, number]> = []
    const years = new Set<number>()
    const monthReturns: Record<string, number> = {}

    // Group equity curve by year-month
    const grouped: Record<string, number[]> = {}
    eq.forEach(p => {
      const d = new Date(p.date)
      const key = `${d.getFullYear()}-${d.getMonth()}`
      if (!grouped[key]) grouped[key] = []
      grouped[key].push(p.total_value)
    })
    Object.entries(grouped).forEach(([key, vals]) => {
      const [yr, mo] = key.split('-')
      years.add(Number(yr))
      const ret = vals.length > 1 ? (vals[vals.length - 1] / vals[0] - 1) * 100 : 0
      data.push([Number(mo), Number(yr), Math.round(ret * 100) / 100])
    })

    const yearArr = Array.from(years).sort()
    const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

    return {
      backgroundColor: 'transparent',
      tooltip: { formatter: (p: any) => `${yearArr[p.value[1]]}年${monthNames[p.value[0]]}<br/>收益: ${p.value[2].toFixed(2)}%` },
      grid: { left: 60, right: 40, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: monthNames, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'category', data: yearArr.map(String), axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } } },
      visualMap: {
        min: -10, max: 10, calculable: false, orient: 'horizontal', left: 'center', bottom: 0,
        inRange: { color: ['#f85149', '#1f2937', '#3fb950'] },
        textStyle: { color: '#9ca3af' }, show: false,
      },
      series: [{
        type: 'heatmap', data,
        label: { show: true, color: '#f3f4f6', fontSize: 10, formatter: (p: any) => p.value[2] ? `${p.value[2].toFixed(1)}` : '' },
        itemStyle: { borderColor: '#161b22', borderWidth: 2, borderRadius: 3 },
      }],
    }
  }, [result])

  const sectorPieOption = useMemo(() => {
    if (!result?.sector_allocation || Object.keys(result.sector_allocation).length === 0) return null
    const data = Object.entries(result.sector_allocation).map(([name, value]) => ({ name, value }))
    return {
      backgroundColor: 'transparent',
      tooltip: { formatter: (p: any) => `${p.name}: ${p.value}%` },
      legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: '#9ca3af', fontSize: 11 } },
      series: [{
        type: 'pie', radius: ['40%', '70%'], center: ['40%', '50%'],
        data,
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#f3f4f6' } },
        itemStyle: { borderRadius: 6, borderColor: '#161b22', borderWidth: 2 },
      }],
    }
  }, [result])

  // Compare charts
  const compareEquityOption = useMemo(() => {
    if (!compareData?.strategies?.length) return null
    const colors = ['#58a6ff', '#3fb950', '#f59e0b', '#ef4444', '#a855f7', '#ec4899']
    const series = compareData.strategies.map((s, i) => ({
      name: s.name, type: 'line' as const,
      data: s.equity_curve.map(p => p.total_value),
      smooth: true, symbol: 'none',
      lineStyle: { color: colors[i % colors.length], width: 2 },
    }))
    const dates = compareData.strategies[0]?.equity_curve.map(p => p.date) || []
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', formatter: (params: any) => {
        let s = `${params[0].axisValue}<br/>`
        params.forEach((p: any) => { s += `${p.seriesName}: ¥${p.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}<br/>` })
        return s
      }},
      legend: { data: compareData.strategies.map(s => s.name), textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 80, right: 20, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `¥${(v / 10000).toFixed(0)}万` }, splitLine: { lineStyle: { color: '#21262d' } } },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(88,166,255,0.15)', handleStyle: { color: '#58a6ff' } },
      ],
      series,
    }
  }, [compareData])

  const compareRadarOption = useMemo(() => {
    if (!compareData?.comparison?.length) return null
    const colors = ['#58a6ff', '#3fb950', '#f59e0b', '#ef4444', '#a855f7', '#ec4899']
    const indicators = [
      { name: '年化收益', max: 30 },
      { name: '夏普比率', max: 3 },
      { name: '胜率', max: 100 },
      { name: '信息比率', max: 2 },
      { name: 'Calmar', max: 3 },
    ]
    return {
      backgroundColor: 'transparent',
      tooltip: {},
      legend: { data: compareData.comparison.map(c => c.name), textStyle: { color: '#9ca3af' }, top: 0 },
      radar: {
        indicator: indicators,
        shape: 'circle',
        axisName: { color: '#9ca3af' },
        splitArea: { areaStyle: { color: ['rgba(88,166,255,0.02)', 'rgba(88,166,255,0.05)'] } },
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      series: [{
        type: 'radar',
        data: compareData.comparison.map((c, i) => ({
          name: c.name,
          value: [
            Math.max(0, c.annual_return),
            Math.max(0, c.sharpe),
            c.win_rate,
            Math.max(0, c.sortino || 0),
            Math.max(0, c.calmar || 0),
          ],
          lineStyle: { color: colors[i % colors.length] },
          areaStyle: { color: colors[i % colors.length], opacity: 0.1 },
        })),
      }],
    }
  }, [compareData])

  // ============================================================
  // Render
  // ============================================================

  return (
    <div className="cb-page">
      {/* Header */}
      <div className="stock-header">
        <h1 style={{ margin: 0, fontSize: 20 }}>机构级策略回测引擎</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#8b949e' }}>
            5种策略 · 4种基准 · 交易成本建模 · 完整指标
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid #30363d' }}>
        {(['single', 'compare'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '10px 20px',
              background: activeTab === tab ? '#1f2937' : 'transparent',
              color: activeTab === tab ? '#f3f4f6' : '#8b949e',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid #58a6ff' : '2px solid transparent',
              cursor: 'pointer', fontSize: 14, fontWeight: activeTab === tab ? 600 : 400,
            }}
          >
            {tab === 'single' ? '单策略回测' : '多策略对比'}
          </button>
        ))}
      </div>

      {/* 参数面板 */}
      <div style={{
        background: '#1f2937', borderRadius: 10, padding: 16, marginBottom: 16,
        display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-end',
      }}>
        {activeTab === 'single' && (
          <div>
            <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>策略</label>
            <select value={strategy} onChange={e => setStrategy(e.target.value)}
              style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
              {strategies.map(s => <option key={s.key} value={s.key}>{s.name}</option>)}
            </select>
          </div>
        )}
        <div>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>开始日期</label>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>结束日期</label>
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>基准</label>
          <select value={benchmark} onChange={e => setBenchmark(e.target.value)}
            style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            {benchmarks.map(b => <option key={b.key} value={b.key}>{b.name}</option>)}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>调仓频率</label>
          <select value={rebalanceFreq} onChange={e => setRebalanceFreq(e.target.value)}
            style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
            <option value="weekly">每周</option>
            <option value="monthly">每月</option>
            <option value="quarterly">每季度</option>
            <option value="yearly">每年</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>持仓数量</label>
          <input type="number" value={topN} min={3} max={30} onChange={e => setTopN(Number(e.target.value))}
            style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13, width: 70 }} />
        </div>
        <div>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>初始资金</label>
          <input type="number" value={initialCapital} min={10000} step={100000} onChange={e => setInitialCapital(Number(e.target.value))}
            style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13, width: 120 }} />
        </div>
        {activeTab === 'single' && (
          <>
            <div>
              <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>佣金(万)</label>
              <input type="number" value={Math.round(commissionRate * 10000)} min={1} max={30} step={1}
                onChange={e => setCommissionRate(Number(e.target.value) / 10000)}
                style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13, width: 70 }} />
            </div>
            <div>
              <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>滑点(千)</label>
              <input type="number" value={Math.round(slippageRate * 1000)} min={0} max={10} step={1}
                onChange={e => setSlippageRate(Number(e.target.value) / 1000)}
                style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13, width: 70 }} />
            </div>
          </>
        )}
        <button
          onClick={activeTab === 'single' ? runBacktest : runCompare}
          disabled={loading}
          style={{
            background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6,
            padding: '8px 24px', fontSize: 14, fontWeight: 600, cursor: loading ? 'wait' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? '回测中...' : '开始回测'}
        </button>
      </div>

      {/* 错误 */}
      {error && (
        <div style={{ background: '#2d1b1b', border: '1px solid #f85149', borderRadius: 8, padding: 12, marginBottom: 16, color: '#f85149', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* 加载 */}
      {loading && (
        <div className="loading"><div className="spinner"></div>正在执行回测...</div>
      )}

      {/* ====== 单策略结果 ====== */}
      {result && data && activeTab === 'single' && !loading && (
        <>
          {/* 策略概要 + 评分 */}
          <div style={{
            background: data.validity_analysis.is_effective
              ? 'linear-gradient(135deg, rgba(63,185,80,0.12), rgba(63,185,80,0.06))'
              : 'linear-gradient(135deg, rgba(248,81,73,0.12), rgba(248,81,73,0.06))',
            borderRadius: 10, padding: 20, marginBottom: 16,
            border: `1px solid ${data.validity_analysis.is_effective ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)'}`,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#f3f4f6' }}>
                {result.strategy_name}
              </div>
              <div style={{ fontSize: 13, color: '#8b949e', marginTop: 4 }}>{result.description}</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                {result.start_date} ~ {result.end_date} | 基准: {result.benchmark_name} | 调仓: {result.rebalance_frequency}
                | 交易 {result.total_trades} 次 | 交易成本 {result.total_cost.toLocaleString()} 元 ({result.cost_ratio}%)
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 32, fontWeight: 700, color: getScoreColor(data.validity_analysis.score) }}>
                {data.validity_analysis.score}分
              </div>
              <div style={{ fontSize: 13, color: data.validity_analysis.is_effective ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                {data.validity_analysis.is_effective ? '策略有效' : '策略待优化'}
              </div>
            </div>
          </div>

          {/* 核心指标卡片 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))', gap: 12, marginBottom: 16 }}>
            {[
              { label: '年化收益', value: `${result.annual_return}%`, color: getReturnColor(result.annual_return) },
              { label: '总收益', value: `${result.total_return}%`, color: getReturnColor(result.total_return) },
              { label: '最大回撤', value: `${result.max_drawdown}%`, color: '#f85149' },
              { label: '夏普比率', value: result.sharpe_ratio.toFixed(3), color: result.sharpe_ratio > 1 ? '#3fb950' : result.sharpe_ratio > 0.5 ? '#d29922' : '#f85149' },
              { label: 'Sortino', value: result.sortino_ratio.toFixed(3), color: result.sortino_ratio > 1.5 ? '#3fb950' : '#d29922' },
              { label: 'Calmar', value: result.calmar_ratio.toFixed(3), color: result.calmar_ratio > 1 ? '#3fb950' : '#d29922' },
              { label: '超额收益', value: `${result.excess_return}%`, color: getReturnColor(result.excess_return) },
              { label: '胜率(月)', value: `${result.win_rate}%`, color: result.win_rate > 60 ? '#3fb950' : '#d29922' },
            ].map(item => (
              <div key={item.label} style={{ background: '#1f2937', borderRadius: 8, padding: '12px 16px', border: '1px solid #374151' }}>
                <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>

          {/* 权益曲线 */}
          {equityChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>权益曲线</div>
              <ReactECharts option={equityChartOption} style={{ height: 350 }} notMerge />
            </div>
          )}

          {/* 回撤曲线 */}
          {drawdownChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>
                回撤曲线 (最大回撤 {result.max_drawdown}%，持续 {result.max_drawdown_duration} 天)
              </div>
              <ReactECharts option={drawdownChartOption} style={{ height: 280 }} notMerge />
            </div>
          )}

          {/* 分年度收益柱状图 */}
          {yearlyChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>分年度收益 vs 超额收益</div>
              <ReactECharts option={yearlyChartOption} style={{ height: 280 }} notMerge />
            </div>
          )}

          {/* 月度收益热力图 + 行业配置饼图 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            {monthlyHeatmapOption && (
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>月度收益热力图</div>
                <ReactECharts option={monthlyHeatmapOption} style={{ height: 300 }} notMerge />
              </div>
            )}
            {sectorPieOption && (
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>行业配置</div>
                <ReactECharts option={sectorPieOption} style={{ height: 300 }} notMerge />
              </div>
            )}
          </div>

          {/* 详细指标面板 */}
          <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>详细指标</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', gap: 12 }}>
              {[
                { label: 'Alpha', value: `${result.alpha}%`, color: getReturnColor(result.alpha) },
                { label: 'Beta', value: result.beta.toFixed(3) },
                { label: '信息比率', value: result.information_ratio.toFixed(3) },
                { label: '跟踪误差', value: `${result.tracking_error}%` },
                { label: '年化波动率', value: `${result.volatility}%` },
                { label: '盈亏比', value: result.profit_loss_ratio.toFixed(3) },
                { label: '基准收益', value: `${result.benchmark_return}%`, color: getReturnColor(result.benchmark_return) },
                { label: '基准年化', value: `${result.benchmark_annual_return}%`, color: getReturnColor(result.benchmark_annual_return) },
                { label: '交易成本', value: `${result.total_cost.toLocaleString()}元` },
                { label: '成本占比', value: `${result.cost_ratio}%` },
                { label: '佣金费率', value: `${(result.cost_config.commission_rate * 10000).toFixed(0)}/万` },
                { label: '滑点率', value: `${(result.cost_config.slippage_rate * 1000).toFixed(0)}/千` },
              ].map(item => (
                <div key={item.label}>
                  <div style={{ fontSize: 12, color: '#8b949e' }}>{item.label}</div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: item.color || '#f3f4f6' }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 市场环境分析 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
            {[
              { label: '牛市', value: result.bull_market_return, desc: '基准涨幅 > 3%/月', color: '#3fb950', icon: '' },
              { label: '熊市', value: result.bear_market_return, desc: '基准跌幅 > 3%/月', color: '#f85149', icon: '' },
              { label: '震荡市', value: result.sideways_market_return, desc: '基准波动 ±3%/月', color: '#d29922', icon: '' },
            ].map(m => (
              <div key={m.label} style={{ background: '#1f2937', borderRadius: 10, padding: 16, borderLeft: `3px solid ${m.color}`, border: '1px solid #374151' }}>
                <div style={{ color: m.color, fontWeight: 600, marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: getReturnColor(m.value) }}>{m.value}%</div>
                <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>{m.desc}</div>
              </div>
            ))}
          </div>

          {/* 策略有效性分析 */}
          {data.validity_analysis && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#3fb950', marginBottom: 8 }}>优势</div>
                {data.validity_analysis.strengths.length > 0 ? data.validity_analysis.strengths.map((s, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #3fb950' }}>{s}</div>
                )) : <div style={{ fontSize: 13, color: '#6b7280' }}>暂无明显优势</div>}
              </div>
              <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f85149', marginBottom: 8 }}>劣势</div>
                {data.validity_analysis.weaknesses.length > 0 ? data.validity_analysis.weaknesses.map((w, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #f85149' }}>{w}</div>
                )) : <div style={{ fontSize: 13, color: '#6b7280' }}>无明显劣势</div>}
              </div>
            </div>
          )}

          {/* 建议 */}
          {data.validity_analysis?.recommendations?.length > 0 && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151', marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#58a6ff', marginBottom: 8 }}>优化建议</div>
              {data.validity_analysis.recommendations.map((r, i) => (
                <div key={i} style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #58a6ff' }}>{r}</div>
              ))}
            </div>
          )}

          {/* 持仓明细 */}
          {result.top_holdings?.length > 0 && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151', marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>
                当前持仓 ({result.top_holdings.length} 只)
              </div>
              <table className="arb-table" style={{ width: '100%' }}>
                <thead>
                  <tr><th>代码</th><th>名称</th><th>行业</th><th>持股</th><th>现价</th><th>市值</th></tr>
                </thead>
                <tbody>
                  {result.top_holdings.map((h, i) => (
                    <tr key={i}>
                      <td style={{ fontSize: 12 }}>{h.code}</td>
                      <td style={{ fontSize: 12, fontWeight: 600 }}>{h.name}</td>
                      <td style={{ fontSize: 12, color: '#8b949e' }}>{h.industry}</td>
                      <td style={{ fontSize: 12 }}>{h.shares}</td>
                      <td style={{ fontSize: 12 }}>¥{h.price}</td>
                      <td style={{ fontSize: 12 }}>¥{h.value.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 交易日志（可折叠） */}
          {result.equity_curve?.length > 0 && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151', marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>
                  交易日志 ({result.total_trades} 笔)
                </div>
                <button onClick={() => setShowTradeLog(!showTradeLog)}
                  style={{ background: '#161b22', color: '#8b949e', border: '1px solid #30363d', borderRadius: 6, padding: '4px 12px', fontSize: 12, cursor: 'pointer' }}>
                  {showTradeLog ? '收起' : '展开'}
                </button>
              </div>
              {showTradeLog && (
                <div style={{ maxHeight: 400, overflow: 'auto' }}>
                  <table className="arb-table" style={{ width: '100%' }}>
                    <thead>
                      <tr><th>日期</th><th>操作</th><th>代码</th><th>价格</th><th>数量</th><th>金额</th><th>费用</th></tr>
                    </thead>
                    <tbody>
                      {(data.backtest_result as any).trade_log?.slice(0, 100).map((t: TradeRecord, i: number) => (
                        <tr key={i}>
                          <td style={{ fontSize: 12 }}>{t.date}</td>
                          <td style={{ color: t.action === 'buy' ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                            {t.action === 'buy' ? '买入' : '卖出'}
                          </td>
                          <td style={{ fontSize: 12 }}>{t.code}</td>
                          <td style={{ fontSize: 12 }}>¥{t.price}</td>
                          <td style={{ fontSize: 12 }}>{t.shares}</td>
                          <td style={{ fontSize: 12 }}>¥{t.gross_amount.toLocaleString()}</td>
                          <td style={{ fontSize: 12, color: '#d29922' }}>¥{t.cost.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 风险因素 */}
          {data.ineffectiveness_analysis?.risk_factors?.length > 0 && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151', marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#d29922', marginBottom: 12 }}>风险因素</div>
              <div style={{ display: 'grid', gap: 8 }}>
                {data.ineffectiveness_analysis.risk_factors.map((rf, i) => (
                  <div key={i} style={{ padding: '10px 12px', background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ color: '#d29922', fontWeight: 600, fontSize: 13 }}>{rf.factor}</span>
                      <span style={{ color: '#6b7280', fontSize: 11 }}>影响: {rf.impact}</span>
                    </div>
                    <div style={{ color: '#8b949e', fontSize: 12 }}>{rf.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ====== 多策略对比 ====== */}
      {compareData && activeTab === 'compare' && !loading && (
        <>
          {/* 对比净值曲线 */}
          {compareEquityOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>多策略净值对比</div>
              <ReactECharts option={compareEquityOption} style={{ height: 400 }} notMerge />
            </div>
          )}

          {/* 雷达图 */}
          {compareRadarOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>策略能力雷达图</div>
              <ReactECharts option={compareRadarOption} style={{ height: 380 }} notMerge />
            </div>
          )}

          {/* 对比排名表 */}
          <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151', marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>策略对比排名</div>
            <div style={{ overflowX: 'auto' }}>
              <table className="arb-table" style={{ width: '100%', minWidth: 900 }}>
                <thead>
                  <tr>
                    <th>排名</th><th>策略</th><th>年化收益</th><th>总收益</th><th>最大回撤</th>
                    <th>夏普</th><th>Sortino</th><th>Calmar</th><th>波动率</th><th>胜率</th><th>超额</th><th>评分</th>
                  </tr>
                </thead>
                <tbody>
                  {compareData.comparison.map((row, i) => (
                    <tr key={row.strategy}>
                      <td style={{ fontWeight: 700, color: i === 0 ? '#3fb950' : '#8b949e' }}>
                        {i === 0 ? '1' : i === 1 ? '2' : i === 2 ? '3' : `#${i + 1}`}
                      </td>
                      <td style={{ fontWeight: 600 }}>{row.name}</td>
                      <td style={{ color: getReturnColor(row.annual_return), fontWeight: 600 }}>
                        {row.annual_return > 0 ? '+' : ''}{row.annual_return.toFixed(2)}%
                      </td>
                      <td style={{ color: getReturnColor(row.total_return) }}>
                        {row.total_return > 0 ? '+' : ''}{row.total_return.toFixed(2)}%
                      </td>
                      <td style={{ color: '#f85149' }}>{row.max_drawdown.toFixed(2)}%</td>
                      <td style={{ color: row.sharpe > 1 ? '#3fb950' : '#d29922' }}>{row.sharpe.toFixed(3)}</td>
                      <td>{row.sortino?.toFixed(3) || '-'}</td>
                      <td>{row.calmar?.toFixed(3) || '-'}</td>
                      <td>{row.volatility.toFixed(2)}%</td>
                      <td>{row.win_rate.toFixed(1)}%</td>
                      <td style={{ color: getReturnColor(row.excess_return) }}>
                        {row.excess_return > 0 ? '+' : ''}{row.excess_return.toFixed(2)}%
                      </td>
                      <td style={{ color: getScoreColor(row.score), fontWeight: 700 }}>{row.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 每个策略摘要 */}
          {compareData.strategies.map(s => (
            <div key={s.strategy} style={{
              background: '#1f2937', borderRadius: 10, padding: 16, marginBottom: 12,
              border: '1px solid #374151',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{s.name}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: getScoreColor(s.analysis?.score || 0) }}>
                  {s.analysis?.score || 0}分
                </div>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {s.analysis?.strengths?.map((a, i) => (
                  <span key={i} style={{ fontSize: 12, color: '#3fb950', background: 'rgba(63,185,80,0.1)', padding: '2px 8px', borderRadius: 4 }}>{a}</span>
                ))}
                {s.analysis?.weaknesses?.map((d, i) => (
                  <span key={i} style={{ fontSize: 12, color: '#f85149', background: 'rgba(248,81,73,0.1)', padding: '2px 8px', borderRadius: 4 }}>{d}</span>
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {/* 初始空状态 */}
      {!data && !compareData && !loading && !error && (
        <div style={{
          background: '#1f2937', borderRadius: 10, padding: 24, border: '1px solid #374151',
          textAlign: 'center', color: '#8b949e',
        }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}></div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>
            机构级策略回测引擎
          </div>
          <div style={{ fontSize: 13, maxWidth: 650, margin: '0 auto', lineHeight: 1.8 }}>
            支持 5 种策略（出口冠军 / 高股息 / 动量 / 价值 / 均衡）和 4 种基准（沪深300 / 中证500 / 中证1000 / 万得全A）。<br />
            内置交易成本模型（佣金 + 印花税 + 滑点 + 冲击成本 + 过户费），计算夏普 / Sortino / Calmar / 信息比率等完整指标。<br />
            <span style={{ color: '#d29922' }}>当前使用模拟数据，后续可接入真实行情数据源。</span>
          </div>
          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
            {strategies.map(s => (
              <span key={s.key} style={{
                background: '#161b22', border: '1px solid #30363d', borderRadius: 6,
                padding: '6px 12px', fontSize: 12, color: '#d1d5db',
              }}>
                {s.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
