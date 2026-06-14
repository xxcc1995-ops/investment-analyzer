import { useState, useMemo, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { PageSection, StatCard, StatCardGroup, LoadingSpinner, EmptyState, ProgressBar } from '../components/ui'

const API_BASE = '/api'

// ============================================================
// Types
// ============================================================

interface StrategyInfo {
  key: string
  name: string
  description: string
  sell_rule: string
}

interface AttributionResult {
  total_return: number
  market_contribution: number
  selection_contribution: number
  cost_contribution: number
  excess_return: number
  monthly_attribution: Array<{ year: number; month: number; return: number }>
}

interface BacktestMetrics {
  total_return: number
  annual_return: number
  annual_return_arith: number
  max_drawdown: number
  max_drawdown_duration: number
  volatility: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  win_rate: number
  profit_loss_ratio: number
  benchmark_return: number
  excess_return: number
  alpha: number
  beta: number
  information_ratio: number
  yearly_returns: Record<string, number>
  drawdown_curve: Array<{ date: string; drawdown: number }>
  benchmark_equity_curve: Array<{ date: string; value: number }>
  total_trades: number
  total_commission: number
  total_slippage: number
  total_cost: number
  cost_ratio: number
  attribution: AttributionResult
}

interface AnalysisResult {
  is_effective: boolean
  score: number
  advantages: string[]
  disadvantages: string[]
  risks: string[]
  suggestions: string[]
}

interface TradeRecord {
  date: string
  action: string
  code: string
  name: string
  price: number
  shares: number
  value: number
  cost: number
  reason: string
}

interface BacktestResult {
  strategy_name: string
  strategy_display: string
  description: string
  start_date: string
  end_date: string
  equity_curve: Array<{ date: string; value: number; holding_count: number }>
  trade_log: TradeRecord[]
  total_trades: number
  metrics: BacktestMetrics
  analysis: AnalysisResult
}

interface CompareResult {
  strategies: Array<{
    strategy: string
    name: string
    metrics: BacktestMetrics
    analysis: AnalysisResult
    equity_curve: Array<{ date: string; value: number }>
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
    alpha: number
    beta: number
    information_ratio: number
    total_cost: number
    cost_ratio: number
    is_effective: boolean
  }>
}

// ============================================================
// Component
// ============================================================

export default function CBBacktestPage() {
  // 参数状态
  const [strategy, setStrategy] = useState('dual_low')
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2026-06-13')
  const [rebalanceFreq, setRebalanceFreq] = useState('weekly')
  const [topN, setTopN] = useState(15)
  const [initialCapital, setInitialCapital] = useState(100000)
  const [commissionRate, setCommissionRate] = useState(0.0002)
  const [slippageBps, setSlippageBps] = useState(2)

  // 高级参数展开状态
  const [showAdvanced, setShowAdvanced] = useState(false)

  // 数据状态
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'single' | 'compare'>('single')

  // 加载策略列表
  const loadStrategies = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/cb-backtest/strategies`)
      setStrategies(res.data.strategies || [])
    } catch {
      // 静默失败
    }
  }, [])

  // 运行单策略回测
  const runBacktest = async () => {
    setLoading(true)
    setError(null)
    setCompareResult(null)
    try {
      const res = await axios.get(`${API_BASE}/cb-backtest/run`, {
        params: {
          strategy,
          start_date: startDate,
          end_date: endDate,
          rebalance_freq: rebalanceFreq,
          top_n: topN,
          initial_capital: initialCapital,
          commission_rate: commissionRate,
          slippage_bps: slippageBps,
        },
      })
      setResult(res.data)
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
    setResult(null)
    try {
      const allStrategies = strategies.map(s => s.key).join(',')
      const res = await axios.get(`${API_BASE}/cb-backtest/compare`, {
        params: {
          strategies: allStrategies,
          start_date: startDate,
          end_date: endDate,
          rebalance_freq: rebalanceFreq,
          top_n: topN,
          initial_capital: initialCapital,
          commission_rate: commissionRate,
          slippage_bps: slippageBps,
        },
      })
      setCompareResult(res.data)
    } catch (e: any) {
      setError(e.response?.data?.detail || '对比失败')
    } finally {
      setLoading(false)
    }
  }

  // 初始加载
  useState(() => { loadStrategies() })

  // ============================================================
  // Charts
  // ============================================================

  const equityChartOption = useMemo(() => {
    if (!result?.equity_curve?.length) return null
    const dates = result.equity_curve.map(p => p.date)
    const values = result.equity_curve.map(p => p.value)

    const series: any[] = [{
      name: '组合净值',
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#58a6ff', width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(88,166,255,0.3)' },
            { offset: 1, color: 'rgba(88,166,255,0.02)' },
          ],
        },
      },
    }]

    const legendData = ['组合净值']

    // 叠加基准净值曲线
    if (result.metrics?.benchmark_equity_curve?.length) {
      const benchDates = result.metrics.benchmark_equity_curve.map(p => p.date)
      const benchValues = result.metrics.benchmark_equity_curve.map(p => p.value)

      // 对齐到权益曲线的时间轴
      const benchMap = new Map(benchDates.map((d, i) => [d, benchValues[i]]))
      const alignedBench = dates.map(d => benchMap.get(d) ?? null)

      series.push({
        name: '中证转债指数',
        type: 'line',
        data: alignedBench,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#d29922', width: 1.5, type: 'dashed' },
      })
      legendData.push('中证转债指数')
    }

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          let html = `${params[0].axisValue}<br/>`
          for (const p of params) {
            html += `${p.marker} ${p.seriesName}: ¥${p.value?.toLocaleString() ?? '-'}<br/>`
          }
          return html
        },
      },
      legend: { data: legendData, textStyle: { color: '#9ca3af' }, top: 0 },
      grid: { left: 70, right: 20, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#9ca3af', formatter: (v: number) => `¥${(v / 1000).toFixed(0)}k` },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(88,166,255,0.15)', handleStyle: { color: '#58a6ff' } },
      ],
      series,
    }
  }, [result])

  const drawdownChartOption = useMemo(() => {
    if (!result?.metrics?.drawdown_curve?.length) return null
    const dates = result.metrics.drawdown_curve.map(p => p.date)
    const values = result.metrics.drawdown_curve.map(p => p.drawdown)
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => `${params[0]?.axisValue}<br/>回撤: ${params[0]?.value?.toFixed(2)}%`,
      },
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: '#21262d' } }, max: 0 },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(239,68,68,0.15)', handleStyle: { color: '#ef4444' } },
      ],
      series: [{
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ef4444', width: 1.5 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239,68,68,0.02)' },
              { offset: 1, color: 'rgba(239,68,68,0.4)' },
            ],
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
    if (!result?.metrics?.yearly_returns) return null
    const entries = Object.entries(result.metrics.yearly_returns).sort(([a], [b]) => a.localeCompare(b))
    if (!entries.length) return null
    const years = entries.map(([y]) => y)
    const returns = entries.map(([, v]) => v)
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', formatter: (params: any) => `${params[0].axisValue}年: ${params[0].value.toFixed(2)}%` },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: years, axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af', formatter: (v: number) => `${v}%` }, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [{
        type: 'bar',
        data: returns.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#3fb950' : '#f85149', borderRadius: [4, 4, 0, 0] },
        })),
        barWidth: '40%',
      }],
    }
  }, [result])

  // 收益归因饼图
  const attributionChartOption = useMemo(() => {
    const attr = result?.metrics?.attribution
    if (!attr) return null

    const data = [
      { name: '市场贡献(Beta)', value: Math.abs(attr.market_contribution), color: '#58a6ff' },
      { name: '选券贡献(Alpha)', value: Math.abs(attr.selection_contribution), color: '#3fb950' },
    ]
    if (Math.abs(attr.cost_contribution) > 0.01) {
      data.push({ name: '交易成本拖累', value: Math.abs(attr.cost_contribution), color: '#f85149' })
    }

    return {
      backgroundColor: 'transparent',
      tooltip: {
        formatter: (p: any) => `${p.name}: ${p.value.toFixed(2)}%`,
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        textStyle: { color: '#9ca3af', fontSize: 12 },
      },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
        },
        data: data.map(d => ({
          value: d.value,
          name: d.name,
          itemStyle: { color: d.color },
        })),
      }],
    }
  }, [result])

  const compareChartOption = useMemo(() => {
    if (!compareResult?.strategies?.length) return null
    const colors = ['#58a6ff', '#3fb950', '#f59e0b', '#ef4444', '#a855f7', '#ec4899']
    const series = compareResult.strategies.map((s, i) => ({
      name: s.name,
      type: 'line' as const,
      data: s.equity_curve.map(p => p.value),
      smooth: true,
      symbol: 'none',
      lineStyle: { color: colors[i % colors.length], width: 2 },
    }))
    const dates = compareResult.strategies[0]?.equity_curve.map(p => p.date) || []
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: {
        data: compareResult.strategies.map(s => s.name),
        textStyle: { color: '#9ca3af' },
        top: 0,
      },
      grid: { left: 70, right: 20, top: 40, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 }, axisLine: { lineStyle: { color: '#374151' } } },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#9ca3af', formatter: (v: number) => `¥${(v / 1000).toFixed(0)}k` },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20, bottom: 10, borderColor: '#374151', backgroundColor: '#161b22', fillerColor: 'rgba(88,166,255,0.15)', handleStyle: { color: '#58a6ff' } },
      ],
      series,
    }
  }, [compareResult])

  // ============================================================
  // Helpers
  // ============================================================

  const getReturnColor = (v: number) => v > 0 ? '#3fb950' : v < 0 ? '#f85149' : '#8b949e'
  const getScoreColor = (score: number) => score >= 70 ? '#3fb950' : score >= 50 ? '#d29922' : '#f85149'

  // ============================================================
  // Render
  // ============================================================

  return (
    <div className="cb-page">
      {/* Header */}
      <div className="stock-header">
        <h1 style={{ margin: 0, fontSize: 20 }}>可转债策略回测</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="data-freshness" style={{ fontSize: 12, color: '#8b949e' }}>
            机构级回测引擎 · 含手续费滑点 · 收益归因 · 基准对比
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
              cursor: 'pointer',
              fontSize: 14,
              fontWeight: activeTab === tab ? 600 : 400,
            }}
          >
            {tab === 'single' ? '单策略回测' : '多策略对比'}
          </button>
        ))}
      </div>

      {/* 参数面板 */}
      <div style={{
        background: '#1f2937', borderRadius: 10, padding: 16, marginBottom: 16,
      }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-end' }}>
          {activeTab === 'single' && (
            <div>
              <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>策略</label>
              <select
                value={strategy}
                onChange={e => setStrategy(e.target.value)}
                style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}
              >
                {strategies.map(s => (
                  <option key={s.key} value={s.key}>{s.name}</option>
                ))}
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
            <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>调仓频率</label>
            <select value={rebalanceFreq} onChange={e => setRebalanceFreq(e.target.value)}
              style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}>
              <option value="weekly">每周</option>
              <option value="biweekly">每两周</option>
              <option value="monthly">每月</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>持仓数量</label>
            <input type="number" value={topN} min={5} max={50} onChange={e => setTopN(Number(e.target.value))}
              style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13, width: 80 }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>初始资金</label>
            <input type="number" value={initialCapital} min={10000} step={10000} onChange={e => setInitialCapital(Number(e.target.value))}
              style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13, width: 120 }} />
          </div>
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

        {/* 高级参数 */}
        <div style={{ marginTop: 12 }}>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer',
              fontSize: 12, padding: 0,
            }}
          >
            {showAdvanced ? '收起高级参数' : '展开高级参数（手续费/滑点）'}
          </button>
          {showAdvanced && (
            <div style={{ display: 'flex', gap: 16, marginTop: 8, alignItems: 'flex-end' }}>
              <div>
                <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>
                  佣金费率（单边）
                </label>
                <select
                  value={commissionRate}
                  onChange={e => setCommissionRate(Number(e.target.value))}
                  style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}
                >
                  <option value={0}>免佣</option>
                  <option value={0.0001}>万1</option>
                  <option value={0.0002}>万2（默认）</option>
                  <option value={0.0003}>万3</option>
                  <option value={0.0005}>万5</option>
                  <option value={0.001}>千1</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>
                  滑点（基点）
                </label>
                <select
                  value={slippageBps}
                  onChange={e => setSlippageBps(Number(e.target.value))}
                  style={{ background: '#161b22', color: '#f3f4f6', border: '1px solid #30363d', borderRadius: 6, padding: '6px 12px', fontSize: 13 }}
                >
                  <option value={0}>无滑点</option>
                  <option value={1}>1bp (0.01%)</option>
                  <option value={2}>2bp (0.02%)</option>
                  <option value={5}>5bp (0.05%)</option>
                  <option value={10}>10bp (0.1%)</option>
                </select>
              </div>
              <div style={{ fontSize: 11, color: '#6b7280', maxWidth: 300, lineHeight: 1.5 }}>
                佣金默认万2（单边），可转债免印花税。滑点模拟实际成交与理论价的偏差。
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div style={{ background: '#2d1b1b', border: '1px solid #f85149', borderRadius: 8, padding: 12, marginBottom: 16, color: '#f85149', fontSize: 13 }}>
          {error}
        </div>
      )}

      {/* 加载状态 */}
      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          正在获取历史数据并执行回测，首次运行需要几分钟...
        </div>
      )}

      {/* ====== 单策略结果 ====== */}
      {result && activeTab === 'single' && !loading && (
        <>
          {/* 策略信息 */}
          <div style={{
            background: '#1f2937', borderRadius: 10, padding: 16, marginBottom: 16,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#f3f4f6' }}>
                {result.strategy_display}
              </div>
              <div style={{ fontSize: 13, color: '#8b949e', marginTop: 4 }}>
                {result.description}
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
                回测区间: {result.start_date} ~ {result.end_date} · 总交易 {result.total_trades} 次
                {result.metrics?.total_cost > 0 && (
                  <span> · 交易成本 ¥{result.metrics.total_cost.toLocaleString()}（占初始资金 {result.metrics.cost_ratio}%）</span>
                )}
              </div>
            </div>
            {result.analysis && (
              <div style={{ textAlign: 'right' }}>
                <div style={{
                  fontSize: 28, fontWeight: 700,
                  color: getScoreColor(result.analysis.score),
                }}>
                  {result.analysis.score}分
                </div>
                <div style={{ fontSize: 12, color: result.analysis.is_effective ? '#3fb950' : '#f85149' }}>
                  {result.analysis.is_effective ? '策略有效' : '策略待优化'}
                </div>
              </div>
            )}
          </div>

          {/* 核心指标卡片 - 第一行：收益指标 */}
          <div style={{ fontSize: 13, fontWeight: 600, color: '#9ca3af', marginBottom: 8, marginTop: 4 }}>收益指标</div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 12, marginBottom: 16,
          }}>
            {[
              { label: '年化收益(几何)', value: `${result.metrics.annual_return}%`, color: getReturnColor(result.metrics.annual_return) },
              { label: '总收益', value: `${result.metrics.total_return}%`, color: getReturnColor(result.metrics.total_return) },
              { label: '超额收益', value: `${result.metrics.excess_return}%`, color: getReturnColor(result.metrics.excess_return) },
              { label: '基准收益', value: `${result.metrics.benchmark_return}%`, color: getReturnColor(result.metrics.benchmark_return) },
              { label: 'Alpha(年化)', value: `${result.metrics.alpha}%`, color: getReturnColor(result.metrics.alpha) },
            ].map(item => (
              <div key={item.label} style={{
                background: '#1f2937', borderRadius: 8, padding: '12px 16px',
                border: '1px solid #374151',
              }}>
                <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>

          {/* 核心指标卡片 - 第二行：风险指标 */}
          <div style={{ fontSize: 13, fontWeight: 600, color: '#9ca3af', marginBottom: 8 }}>风险指标</div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 12, marginBottom: 16,
          }}>
            {[
              { label: '最大回撤', value: `${result.metrics.max_drawdown}%`, color: '#f85149' },
              { label: '回撤持续', value: `${result.metrics.max_drawdown_duration}天`, color: '#8b949e' },
              { label: '年化波动率', value: `${result.metrics.volatility}%`, color: '#8b949e' },
              { label: 'Beta', value: result.metrics.beta.toFixed(2), color: result.metrics.beta > 1 ? '#f59e0b' : '#3fb950' },
            ].map(item => (
              <div key={item.label} style={{
                background: '#1f2937', borderRadius: 8, padding: '12px 16px',
                border: '1px solid #374151',
              }}>
                <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>

          {/* 核心指标卡片 - 第三行：风险调整收益 */}
          <div style={{ fontSize: 13, fontWeight: 600, color: '#9ca3af', marginBottom: 8 }}>风险调整收益</div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 12, marginBottom: 16,
          }}>
            {[
              { label: '夏普比率', value: result.metrics.sharpe_ratio.toFixed(2), color: result.metrics.sharpe_ratio > 1 ? '#3fb950' : '#d29922' },
              { label: 'Sortino比率', value: result.metrics.sortino_ratio.toFixed(2), color: result.metrics.sortino_ratio > 1.5 ? '#3fb950' : '#d29922' },
              { label: 'Calmar比率', value: result.metrics.calmar_ratio.toFixed(2), color: result.metrics.calmar_ratio > 0.5 ? '#3fb950' : '#d29922' },
              { label: '信息比率', value: result.metrics.information_ratio.toFixed(2), color: result.metrics.information_ratio > 0.5 ? '#3fb950' : '#d29922' },
              { label: '胜率(月)', value: `${result.metrics.win_rate}%`, color: result.metrics.win_rate > 50 ? '#3fb950' : '#d29922' },
              { label: '盈亏比', value: result.metrics.profit_loss_ratio.toFixed(2), color: result.metrics.profit_loss_ratio > 1 ? '#3fb950' : '#d29922' },
            ].map(item => (
              <div key={item.label} style={{
                background: '#1f2937', borderRadius: 8, padding: '12px 16px',
                border: '1px solid #374151',
              }}>
                <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>

          {/* 分年度收益 */}
          {result.metrics.yearly_returns && Object.keys(result.metrics.yearly_returns).length > 0 && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${Object.keys(result.metrics.yearly_returns).length}, 1fr)`,
              gap: 8, marginBottom: 16,
            }}>
              {Object.entries(result.metrics.yearly_returns)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([year, ret]) => (
                  <div key={year} style={{
                    background: '#1f2937', borderRadius: 8, padding: '10px 12px',
                    border: '1px solid #374151', textAlign: 'center',
                  }}>
                    <div style={{ fontSize: 12, color: '#8b949e' }}>{year}年</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: getReturnColor(ret) }}>
                      {ret > 0 ? '+' : ''}{ret.toFixed(1)}%
                    </div>
                  </div>
                ))}
            </div>
          )}

          {/* 权益曲线（含基准） */}
          {equityChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>权益曲线 vs 基准</div>
              <ReactECharts option={equityChartOption} style={{ height: 350 }} notMerge />
            </div>
          )}

          {/* 回撤曲线 */}
          {drawdownChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>回撤曲线</div>
              <ReactECharts option={drawdownChartOption} style={{ height: 280 }} notMerge />
            </div>
          )}

          {/* 年度收益柱状图 */}
          {yearlyChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>分年度收益</div>
              <ReactECharts option={yearlyChartOption} style={{ height: 250 }} notMerge />
            </div>
          )}

          {/* 收益归因 */}
          {result.metrics.attribution && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              {/* 归因图表 */}
              {attributionChartOption && (
                <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>收益归因分解</div>
                  <ReactECharts option={attributionChartOption} style={{ height: 250 }} notMerge />
                </div>
              )}

              {/* 归因详情 */}
              <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>归因明细</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    { label: '总收益', value: result.metrics.attribution.total_return, suffix: '%' },
                    { label: '市场贡献(Beta)', value: result.metrics.attribution.market_contribution, suffix: '%' },
                    { label: '选券贡献(Alpha)', value: result.metrics.attribution.selection_contribution, suffix: '%' },
                    { label: '交易成本拖累', value: result.metrics.attribution.cost_contribution, suffix: '%' },
                    { label: '超额收益', value: result.metrics.attribution.excess_return, suffix: '%' },
                  ].map(item => (
                    <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 13, color: '#9ca3af' }}>{item.label}</span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: getReturnColor(item.value) }}>
                        {item.value > 0 ? '+' : ''}{item.value.toFixed(2)}{item.suffix}
                      </span>
                    </div>
                  ))}
                </div>

                {/* 交易成本明细 */}
                {result.metrics.total_cost > 0 && (
                  <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #374151' }}>
                    <div style={{ fontSize: 12, color: '#8b949e', marginBottom: 8 }}>交易成本明细</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#d1d5db', marginBottom: 4 }}>
                      <span>累计佣金</span>
                      <span>¥{result.metrics.total_commission?.toLocaleString()}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#d1d5db', marginBottom: 4 }}>
                      <span>累计滑点</span>
                      <span>¥{result.metrics.total_slippage?.toLocaleString()}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#f85149', fontWeight: 600 }}>
                      <span>合计</span>
                      <span>¥{result.metrics.total_cost?.toLocaleString()}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 策略分析 */}
          {result.analysis && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
              {/* 优势 */}
              <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#3fb950', marginBottom: 8 }}>优势</div>
                {result.analysis.advantages.length > 0 ? result.analysis.advantages.map((a, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #3fb950' }}>
                    {a}
                  </div>
                )) : <div style={{ fontSize: 13, color: '#6b7280' }}>暂无明显优势</div>}
              </div>

              {/* 劣势 */}
              <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f85149', marginBottom: 8 }}>劣势</div>
                {result.analysis.disadvantages.length > 0 ? result.analysis.disadvantages.map((d, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #f85149' }}>
                    {d}
                  </div>
                )) : <div style={{ fontSize: 13, color: '#6b7280' }}>无明显劣势</div>}
              </div>

              {/* 风险标签 */}
              {result.analysis.risks.length > 0 && (
                <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f59e0b', marginBottom: 8 }}>风险标签</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {result.analysis.risks.map((r, i) => (
                      <span key={i} style={{ fontSize: 12, color: '#f59e0b', background: 'rgba(245,158,11,0.1)', padding: '4px 10px', borderRadius: 4 }}>
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 建议 */}
              <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#58a6ff', marginBottom: 8 }}>建议</div>
                {result.analysis.suggestions.map((s, i) => (
                  <div key={i} style={{ fontSize: 13, color: '#d1d5db', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #58a6ff' }}>
                    {s}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 交易日志 */}
          {result.trade_log.length > 0 && (
            <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>
                交易日志（最近{Math.min(result.trade_log.length, 50)}条）
              </div>
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                <table className="arb-table" style={{ width: '100%' }}>
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>操作</th>
                      <th>代码</th>
                      <th>名称</th>
                      <th>价格</th>
                      <th>数量</th>
                      <th>金额</th>
                      <th>成本</th>
                      <th>原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trade_log.slice(0, 50).map((t, i) => (
                      <tr key={i}>
                        <td style={{ fontSize: 12 }}>{t.date}</td>
                        <td style={{ color: t.action === 'buy' ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                          {t.action === 'buy' ? '买入' : '卖出'}
                        </td>
                        <td style={{ fontSize: 12 }}>{t.code}</td>
                        <td style={{ fontSize: 12 }}>{t.name}</td>
                        <td style={{ fontSize: 12 }}>¥{t.price}</td>
                        <td style={{ fontSize: 12 }}>{t.shares}张</td>
                        <td style={{ fontSize: 12 }}>¥{t.value.toLocaleString()}</td>
                        <td style={{ fontSize: 12, color: '#f85149' }}>{t.cost > 0 ? `¥${t.cost}` : '-'}</td>
                        <td style={{ fontSize: 12, color: '#8b949e' }}>{t.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* ====== 多策略对比 ====== */}
      {compareResult && activeTab === 'compare' && !loading && (
        <>
          {/* 对比图表 */}
          {compareChartOption && (
            <div style={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 10, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>多策略净值对比</div>
              <ReactECharts option={compareChartOption} style={{ height: 400 }} notMerge />
            </div>
          )}

          {/* 对比表格 */}
          <div style={{ background: '#1f2937', borderRadius: 10, padding: 16, border: '1px solid #374151', marginBottom: 16, overflowX: 'auto' }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6', marginBottom: 12 }}>策略对比排名</div>
            <table className="arb-table" style={{ width: '100%', minWidth: 900 }}>
              <thead>
                <tr>
                  <th>排名</th>
                  <th>策略</th>
                  <th>年化收益</th>
                  <th>总收益</th>
                  <th>最大回撤</th>
                  <th>夏普</th>
                  <th>Sortino</th>
                  <th>Alpha</th>
                  <th>Beta</th>
                  <th>信息比率</th>
                  <th>交易成本</th>
                  <th>结论</th>
                </tr>
              </thead>
              <tbody>
                {compareResult.comparison.map((row, i) => (
                  <tr key={row.strategy}>
                    <td style={{ fontWeight: 700, color: i === 0 ? '#3fb950' : '#8b949e' }}>
                      {i === 0 ? '#1' : i === 1 ? '#2' : i === 2 ? '#3' : `#${i + 1}`}
                    </td>
                    <td style={{ fontWeight: 600 }}>{row.name}</td>
                    <td style={{ color: getReturnColor(row.annual_return), fontWeight: 600 }}>
                      {row.annual_return > 0 ? '+' : ''}{row.annual_return.toFixed(2)}%
                    </td>
                    <td style={{ color: getReturnColor(row.total_return) }}>
                      {row.total_return > 0 ? '+' : ''}{row.total_return.toFixed(2)}%
                    </td>
                    <td style={{ color: '#f85149' }}>{row.max_drawdown.toFixed(2)}%</td>
                    <td style={{ color: row.sharpe > 1 ? '#3fb950' : '#d29922' }}>{row.sharpe.toFixed(2)}</td>
                    <td style={{ color: row.sortino > 1.5 ? '#3fb950' : '#d29922' }}>{row.sortino.toFixed(2)}</td>
                    <td style={{ color: getReturnColor(row.alpha) }}>
                      {row.alpha > 0 ? '+' : ''}{row.alpha.toFixed(2)}%
                    </td>
                    <td style={{ color: row.beta > 1 ? '#f59e0b' : '#3fb950' }}>{row.beta.toFixed(2)}</td>
                    <td style={{ color: row.information_ratio > 0.5 ? '#3fb950' : '#d29922' }}>
                      {row.information_ratio.toFixed(2)}
                    </td>
                    <td style={{ color: '#f85149', fontSize: 12 }}>
                      ¥{row.total_cost?.toLocaleString() ?? 0}
                    </td>
                    <td style={{ color: row.is_effective ? '#3fb950' : '#d29922' }}>
                      {row.is_effective ? '有效' : '待优化'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 每个策略的详细指标 */}
          {compareResult.strategies.map(s => (
            <div key={s.strategy} style={{
              background: '#1f2937', borderRadius: 10, padding: 16, marginBottom: 12,
              border: '1px solid #374151',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#f3f4f6' }}>{s.name}</div>
                <div style={{
                  fontSize: 20, fontWeight: 700,
                  color: getScoreColor(s.analysis?.score || 0),
                }}>
                  {s.analysis?.score || 0}分
                </div>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
                {s.analysis?.advantages?.map((a, i) => (
                  <span key={i} style={{ fontSize: 12, color: '#3fb950', background: 'rgba(63,185,80,0.1)', padding: '2px 8px', borderRadius: 4 }}>
                    {a}
                  </span>
                ))}
                {s.analysis?.disadvantages?.map((d, i) => (
                  <span key={i} style={{ fontSize: 12, color: '#f85149', background: 'rgba(248,81,73,0.1)', padding: '2px 8px', borderRadius: 4 }}>
                    {d}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {/* 策略说明（初始状态） */}
      {!result && !compareResult && !loading && !error && (
        <div style={{
          background: '#1f2937', borderRadius: 10, padding: 24, border: '1px solid #374151',
          textAlign: 'center', color: '#8b949e',
        }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>&#128202;</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#f3f4f6', marginBottom: 8 }}>
            可转债大师策略回测
          </div>
          <div style={{ fontSize: 13, maxWidth: 600, margin: '0 auto', lineHeight: 1.8 }}>
            使用真实历史K线数据（AKShare），验证6种可转债大师策略的历史表现。<br />
            支持安道全面值、双低、摊大饼、YTM保本、下修博弈、强赎博弈策略。<br />
            <span style={{ color: '#d29922' }}>首次运行需获取大量历史数据，可能需要3-5分钟。后续运行将使用缓存。</span>
          </div>
          <div style={{ marginTop: 16, fontSize: 12, color: '#6b7280', maxWidth: 500, margin: '16px auto 0', lineHeight: 1.6 }}>
            机构级特性：含佣金+滑点模拟 | 收益归因（Alpha/Beta分解） | 基准对比（中证转债指数）
            <br />
            风险指标：夏普/Sortino/Calmar比率 | 最大回撤持续天数 | 信息比率
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
