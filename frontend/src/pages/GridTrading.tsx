/**
 * 网格交易页面
 * =============
 *
 * 功能概述：
 * 1. 网格理念 — 什么是网格交易、适合什么股票、有什么风险
 * 2. 网格分析 — 设置参数、查看网格层级、盈亏平衡分析
 * 3. 回测模拟 — 用历史数据模拟网格策略，查看收益曲线和风险指标
 * 4. 当前状态 — 当前价在网格中的位置、下一买入/卖出触发价
 * 5. 参数优化 — 自动扫描最优网格参数组合
 *
 * 支持市场：A股、港股（自动识别）
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { Tooltip } from 'antd'
import { StatCard, StatCardGroup, PageSection, DataTable, TabBar, ProgressBar, LoadingSpinner, Tag } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

// ============================================================
// 类型定义
// ============================================================

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
  num_stop_loss: number
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  total_return_pct: number
  win_rate: number
  profit_loss_ratio: number
  max_drawdown: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  annual_volatility: number
  max_consecutive_losses: number
  capital_utilization: number
  total_fees_paid?: number
  equity_curve: { date: string; equity: number }[]
  open_positions: number
  position_details: { level: number; shares: number; entry: number; unrealized: number }[]
  stop_loss_triggered: boolean
}

interface GridAnalysis {
  stock_name: string
  stock_code: string
  market: string
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
  stop_loss_pct: number
  enable_stop_loss: boolean
  stop_loss_price: number | null
  atr_multiplier?: number
  chart_data: { dates: string[]; opens: number[]; highs: number[]; lows: number[]; closes: number[]; volumes: number[] }
  update_time: string
  error?: string
}

interface Philosophy {
  title: string
  subtitle: string
  concepts: { name: string; desc: string; formula: string; example?: string }[]
  scoring: { title: string; dimensions: { name: string; desc: string }[] }
  risks: string[]
  rules: string[]
  best_for: string[]
  not_for: string[]
}

interface SearchResult {
  code: string
  name: string
  market?: string
}

interface OptimizeResult {
  top_combinations: { width_pct: number; num_grids: number; sizing: string; total_return: number; sharpe: number; max_drawdown: number; win_rate: number; score: number }[]
  atr: number
  current_price: number
  error?: string
}

// ============================================================
// 辅助函数
// ============================================================

const fmt = (n: number) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '-'

const Tip = ({ text, children }: { text: string; children?: React.ReactNode }) => (
  <Tooltip title={text} overlayStyle={{ maxWidth: 300 }}>
    <span className="tip-trigger">{children || '?'}</span>
  </Tooltip>
)

// ============================================================
// 主页面组件
// ============================================================

export default function GridTrading() {
  // ===== 状态管理 =====
  const [activeTab, setActiveTab] = useState<'philosophy' | 'analysis' | 'simulation' | 'status' | 'optimize'>('philosophy')
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)
  const [analysis, setAnalysis] = useState<GridAnalysis | null>(null)
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [optimizeLoading, setOptimizeLoading] = useState(false)

  const [stockCode, setStockCode] = useState('00700')
  const [stockSearch, setStockSearch] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const searchTimerRef = useRef<number | null>(null)

  const [gridType, setGridType] = useState<'equal_distance' | 'equal_ratio'>('equal_distance')
  const [gridsUp, setGridsUp] = useState('10')
  const [gridsDown, setGridsDown] = useState('10')
  const [gridWidthPct, setGridWidthPct] = useState('')
  const [capital, setCapital] = useState('1000000')
  const [histDays, setHistDays] = useState('252')
  const [sizing, setSizing] = useState<'equal' | 'pyramid'>('equal')
  const [enableStopLoss, setEnableStopLoss] = useState(true)
  const [stopLossPct, setStopLossPct] = useState('0.10')
  const [atrMultiplier, setAtrMultiplier] = useState('1.0')

  // 货币符号辅助函数
  const getCurrency = (market?: string) => market === 'A' ? '¥' : 'HK$'

  // ===== 股票搜索 =====
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
    setAnalysis(null)
  }

  // ===== 数据加载 =====
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
        stock_code: stockCode, grid_type: gridType,
        num_grids_up: parseInt(gridsUp), num_grids_down: parseInt(gridsDown),
        capital: parseFloat(capital), hist_days: parseInt(histDays),
        sizing, enable_stop_loss: enableStopLoss, stop_loss_pct: parseFloat(stopLossPct),
        atr_multiplier: parseFloat(atrMultiplier),
      }
      if (gridWidthPct) params.grid_width_pct = parseFloat(gridWidthPct)
      const res = await axios.get(`${API_BASE}/grid/analysis`, { params })
      setAnalysis(res.data)
    } catch (e) { console.error(e) }
    setLoading(false)
  }, [stockCode, gridType, gridsUp, gridsDown, gridWidthPct, capital, histDays, sizing, enableStopLoss, stopLossPct, atrMultiplier])

  const loadOptimize = useCallback(async () => {
    setOptimizeLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/grid/optimize`, {
        params: { stock_code: stockCode, capital: parseFloat(capital), hist_days: parseInt(histDays) }
      })
      setOptimizeResult(res.data)
    } catch (e) { console.error(e) }
    setOptimizeLoading(false)
  }, [stockCode, capital, histDays])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])

  useEffect(() => {
    if (activeTab === 'analysis' || activeTab === 'simulation' || activeTab === 'status') loadAnalysis()
    if (activeTab === 'optimize') loadOptimize()
  }, [activeTab, loadAnalysis, loadOptimize])

  // ===== ECharts 图表配置 =====
  const klineOption = useMemo(() => {
    if (!analysis?.chart_data) return {}
    const { dates, opens, highs, lows, closes } = analysis.chart_data
    const klineData = dates.map((_, i) => [opens[i], closes[i], lows[i], highs[i]])
    const markLines = analysis.grid_levels.map(lv => ({
      yAxis: lv.price,
      lineStyle: {
        color: lv.type === 'buy' ? '#22c55e' : lv.type === 'sell' ? '#ef4444' : '#d4a76a',
        type: lv.type === 'current' ? 'solid' : 'dashed',
        width: lv.type === 'current' ? 2 : 1, opacity: 0.6,
      },
      label: { formatter: `${lv.price}`, fontSize: 9, color: '#9ca3af' },
    }))
    const stopLossLine = analysis.stop_loss_price ? [{
      yAxis: analysis.stop_loss_price,
      lineStyle: { color: '#ff4d4f', type: 'dotted', width: 2 },
      label: { formatter: `止损 ${analysis.stop_loss_price}`, fontSize: 10, color: '#ff4d4f' },
    }] : []
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: dates, axisLabel: { color: '#9ca3af', fontSize: 10 } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [{
        type: 'candlestick', data: klineData, barWidth: '60%',
        itemStyle: { color: '#ef5350', color0: '#26a69a', borderColor: '#ef5350', borderColor0: '#26a69a' },
        markLine: { silent: true, symbol: 'none', data: [...markLines, ...stopLossLine] },
      }],
      dataZoom: [
        { type: 'inside', start: 60, end: 100 },
        { type: 'slider', start: 60, end: 100, height: 20, bottom: 5 },
      ],
    }
  }, [analysis])

  const equityChartOption = useMemo(() => {
    if (!analysis?.simulation?.equity_curve?.length) return null
    const curve = analysis.simulation.equity_curve
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: curve.map(c => c.date), axisLabel: { color: '#9ca3af', fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151' } } },
      series: [{
        type: 'line', data: curve.map(c => c.equity), showSymbol: false,
        lineStyle: { color: '#d4a76a', width: 2 },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(212,167,106,0.3)' }, { offset: 1, color: 'rgba(212,167,106,0)' }] } },
        markLine: { silent: true, symbol: 'none', data: [{ yAxis: parseFloat(capital), lineStyle: { color: '#6b7280', type: 'dashed' }, label: { formatter: '初始资金', color: '#6b7280' } }] },
      }],
      dataZoom: [{ type: 'inside', start: 0, end: 100 }, { type: 'slider', start: 0, end: 100, height: 20, bottom: 5 }],
    }
  }, [analysis, capital])

  // ===== 表格列定义 =====
  const gridLevelColumns: Column<GridLevel>[] = [
    { key: 'price', title: '价格', dataIndex: 'price', align: 'right', render: v => fmt(v) },
    { key: 'distance', title: '距现价%', dataIndex: 'distance_pct', align: 'right', render: v => <span style={{ color: v < 0 ? '#52c41a' : v > 0 ? '#ff4d4f' : '#d4a76a' }}>{v > 0 ? '+' : ''}{v}%</span> },
    { key: 'type', title: '类型', align: 'center', render: (_, r) => <span style={{ color: r.type === 'buy' ? '#52c41a' : r.type === 'sell' ? '#ff4d4f' : '#d4a76a', fontWeight: 600 }}>{r.type === 'buy' ? '买入' : r.type === 'sell' ? '卖出' : '当前'}</span> },
    { key: 'shares', title: '每格股数', align: 'right', render: () => analysis?.shares_per_grid },
    { key: 'capital', title: '每格资金', align: 'right', render: () => analysis ? `${getCurrency(analysis.market)}${fmt(analysis.capital_per_grid)}` : '-' },
  ]

  const tradeColumns: Column<Trade>[] = [
    { key: 'date', title: '日期', dataIndex: 'date', render: v => <span style={{ fontSize: 12 }}>{v}</span> },
    { key: 'action', title: '操作', align: 'center', render: (_, r) => <span style={{ color: r.action === 'buy' ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>{r.action === 'buy' ? '买入' : r.action === 'stop_loss' ? '止损' : '卖出'}</span> },
    { key: 'price', title: '价格', dataIndex: 'price', align: 'right', render: v => fmt(v) },
    { key: 'level', title: '网格层级', dataIndex: 'level', align: 'right', render: v => fmt(v) },
    { key: 'shares', title: '股数', dataIndex: 'shares', align: 'right' },
    { key: 'pnl', title: '盈亏', align: 'right', render: (_, r) => <span style={{ color: (r.pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f' }}>{r.pnl ? `${getCurrency(analysis?.market)}${fmt(r.pnl)}` : '-'}</span> },
  ]

  const positionColumns: Column<any>[] = [
    { key: 'level', title: '网格层级', dataIndex: 'level', align: 'right', render: v => fmt(v) },
    { key: 'shares', title: '股数', dataIndex: 'shares', align: 'right' },
    { key: 'entry', title: '买入价', dataIndex: 'entry', align: 'right', render: v => fmt(v) },
    { key: 'unrealized', title: '未实现盈亏', dataIndex: 'unrealized', align: 'right', render: v => <span style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f' }}>{getCurrency(analysis?.market)}${fmt(v)}</span> },
  ]

  const optimizeColumns: Column<any>[] = [
    { key: 'rank', title: '排名', align: 'center', render: (_, __, i) => i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}` },
    { key: 'width_pct', title: '网格宽度%', dataIndex: 'width_pct', align: 'right', render: v => `${v}%` },
    { key: 'num_grids', title: '网格数', dataIndex: 'num_grids', align: 'right' },
    { key: 'sizing', title: '仓位方法', dataIndex: 'sizing', render: v => v === 'equal' ? '等额' : '金字塔' },
    { key: 'total_return', title: '总收益%', dataIndex: 'total_return', align: 'right', colorize: true, render: v => `${v}%` },
    { key: 'sharpe', title: '夏普比率', dataIndex: 'sharpe', align: 'right', render: v => <span style={{ color: v > 1 ? '#52c41a' : '#faad14' }}>{v}</span> },
    { key: 'max_drawdown', title: '最大回撤%', dataIndex: 'max_drawdown', align: 'right', render: v => <span style={{ color: '#ff4d4f' }}>{v}%</span> },
    { key: 'win_rate', title: '胜率%', dataIndex: 'win_rate', align: 'right' },
    { key: 'score', title: '综合评分', dataIndex: 'score', align: 'right', render: v => <span style={{ color: '#d4a76a', fontWeight: 700 }}>{v}</span> },
  ]

  // ===== Tab定义 =====
  const tabs = [
    { key: 'philosophy', label: '网格理念' },
    { key: 'analysis', label: '网格分析' },
    { key: 'simulation', label: '回测模拟' },
    { key: 'status', label: '当前状态' },
    { key: 'optimize', label: '参数优化' },
  ]

  // ===== 渲染 =====
  return (
    <div className="cb-page">
      {/* 页面标题 */}
      <PageSection title={`网格交易 - ${analysis?.stock_name || stockCode}`} compact>
        <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: 13 }}>
          自动生成网格 · 历史回测 · 风险指标 · 参数优化
          {analysis?.market && (
            <Tag color={analysis.market === 'A' ? '#52c41a' : '#1890ff'} style={{ marginLeft: 8 }}>
              {analysis.market === 'A' ? 'A股' : '港股'}
            </Tag>
          )}
        </p>
      </PageSection>

      {/* 股票搜索框 */}
      <div ref={searchRef} style={{ position: 'relative', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>股票代码:</span>
          <input
            value={showSearch ? stockSearch : stockCode}
            onFocus={() => { setShowSearch(true); setStockSearch('') }}
            onChange={e => { setStockSearch(e.target.value); setShowSearch(true) }}
            placeholder="输入代码或名称（如 00700、600519）"
            className="grid-params"
            style={{ width: 200 }}
          />
          {showSearch && searchResults.length > 0 && (
            <div className="search-results" style={{ position: 'absolute', top: '100%', left: 60, zIndex: 100, width: 280 }}>
              {searchResults.map(r => (
                <div key={r.code} onClick={() => selectStock(r.code)} className="search-item">
                  <span style={{ color: '#d4a76a', fontWeight: 600 }}>{r.code}</span> {r.name}
                  {r.market && <Tag color={r.market === 'A' ? '#52c41a' : '#1890ff'} style={{ marginLeft: 6 }}>{r.market === 'A' ? 'A股' : '港股'}</Tag>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tab导航栏 */}
      <TabBar
        tabs={tabs}
        activeKey={activeTab}
        onChange={k => setActiveTab(k as any)}
        style={{ marginBottom: 16 }}
      />

      {/* ===== Tab 1: 网格理念 ===== */}
      {activeTab === 'philosophy' && philosophy && (
        <div>
          <PageSection title={philosophy.title}>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 16 }}>{philosophy.subtitle}</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
              {philosophy.concepts.map((c, i) => (
                <div key={i} className="grid-concept-card">
                  <h4>{c.name}</h4>
                  <p>{c.desc}</p>
                  <code>{c.formula}</code>
                  {c.example && <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>例：{c.example}</p>}
                </div>
              ))}
            </div>
          </PageSection>

          <PageSection title={philosophy.scoring.title}>
            {philosophy.scoring.dimensions.map((d, i) => (
              <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <span style={{ color: '#d4a76a', fontWeight: 600 }}>{d.name}: </span>
                <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{d.desc}</span>
              </div>
            ))}
          </PageSection>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <PageSection title="✓ 适合网格交易的标的">
              {(philosophy.best_for || []).map((r, i) => <p key={i} style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '4px 0' }}>• {r}</p>)}
            </PageSection>
            <PageSection title="✗ 不适合网格交易的标的">
              {(philosophy.not_for || []).map((r, i) => <p key={i} style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '4px 0' }}>• {r}</p>)}
            </PageSection>
          </div>

          <PageSection title="⚠ 风险提示">
            {philosophy.risks.map((r, i) => <p key={i} style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '4px 0' }}>• {r}</p>)}
          </PageSection>

          <PageSection title="📋 交易规则">
            {philosophy.rules.map((r, i) => <p key={i} style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '4px 0' }}>• {r}</p>)}
          </PageSection>
        </div>
      )}

      {/* ===== Tab 2: 网格分析 ===== */}
      {activeTab === 'analysis' && (
        <div>
          <PageSection title="网格参数">
            <div className="grid-params">
              <label>网格类型 <Tip text="等距：每格宽度相同，适合窄幅震荡。等比：每格比例相同，适合大幅波动。动态：基于布林带自适应，波动大时网格宽，波动小时网格窄。" />
                <select value={gridType} onChange={e => setGridType(e.target.value as any)}>
                  <option value="equal_distance">等距网格</option>
                  <option value="equal_ratio">等比网格</option>
                  <option value="dynamic">动态网格(布林带)</option>
                </select>
              </label>
              <label>上行格数 <Tip text="当前价格以上画几条卖出线。越多覆盖范围越广，但每格资金越少。" />
                <input type="number" value={gridsUp} onChange={e => setGridsUp(e.target.value)} min="3" max="30" />
              </label>
              <label>下行格数 <Tip text="当前价格以下画几条买入线。越多能买越便宜，但需要更多资金。" />
                <input type="number" value={gridsDown} onChange={e => setGridsDown(e.target.value)} min="3" max="30" />
              </label>
              <label>网格宽度% <Tip text="每格之间的价格差。留空=自动用ATR计算（推荐）。手动设置建议1%-5%。" />
                <input type="number" value={gridWidthPct} onChange={e => setGridWidthPct(e.target.value)} placeholder="ATR自动" step="0.5" min="0.5" />
              </label>
              <label>ATR倍数 <Tip text="网格宽度=ATR×倍数。0.8=偏窄（频繁交易），1.0=标准，1.5=偏宽（少交易但利润大）。仅在网格宽度留空时生效。" />
                <input type="number" value={atrMultiplier} onChange={e => setAtrMultiplier(e.target.value)} step="0.1" min="0.3" max="3.0" />
              </label>
              <label>总资金 <Tip text="准备投入网格交易的总金额。港股用HKD，A股用CNY。" />
                <input type="number" value={capital} onChange={e => setCapital(e.target.value)} />
              </label>
              <label>回测天数 <Tip text="用多少天的历史数据模拟。252天≈1年，504天≈2年。越多越能覆盖不同行情。" />
                <input type="number" value={histDays} onChange={e => setHistDays(e.target.value)} />
              </label>
              <label>仓位方法 <Tip text="等额：每格买一样多。金字塔：越跌买越多，降低平均成本但需要更多资金。" />
                <select value={sizing} onChange={e => setSizing(e.target.value as any)}>
                  <option value="equal">等额分配</option>
                  <option value="pyramid">金字塔加仓</option>
                </select>
              </label>
              <label>止损比例 <Tip text="跌破最下方网格多少百分比时清仓止损。建议10%-15%。防止单边下跌无限买入。" />
                <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginTop: 4 }}>
                  <input type="checkbox" checked={enableStopLoss} onChange={e => setEnableStopLoss(e.target.checked)} />
                  <input type="number" value={stopLossPct} onChange={e => setStopLossPct(e.target.value)} step="0.05" min="0.05" max="0.30" disabled={!enableStopLoss} style={{ flex: 1 }} />
                </div>
              </label>
            </div>
            <button onClick={loadAnalysis} disabled={loading} className="grid-btn-primary">
              {loading ? '加载中...' : '开始分析'}
            </button>
          </PageSection>

          {loading && <LoadingSpinner />}

          {analysis && !analysis.error && (
            <>
              <StatCardGroup columns={3}>
                <StatCard label={`${analysis.stock_name} 现价`} value={`${getCurrency(analysis.market)}${fmt(analysis.current_price)}`} color="#d4a76a" />
                <StatCard label="ATR(14)" value={`${fmt(analysis.atr)} (${analysis.atr_pct}%)`} color="#1890ff" />
                <StatCard label="网格宽度" value={`${fmt(analysis.grid_width)} (${analysis.grid_width_pct}%)`} color="#faad14" />
                <StatCard label="回测年化" value={`${analysis.cagr}%`} color={analysis.cagr > 0 ? '#52c41a' : '#ff4d4f'} />
                <StatCard label="胜率" value={`${analysis.simulation.win_rate}%`} color="#52c41a" />
                <StatCard label="最大回撤" value={`${analysis.simulation.max_drawdown}%`} color="#ff4d4f" />
              </StatCardGroup>

              {/* 52周价格区间 */}
              <PageSection title="52周价格区间">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>52周低: <span style={{ color: '#52c41a' }}>{getCurrency(analysis.market)}${fmt(analysis.low_52w)}</span></span>
                  <div className="grid-52w-bar">
                    <div className="grid-52w-dot" style={{ left: `${((analysis.current_price - analysis.low_52w) / (analysis.high_52w - analysis.low_52w)) * 100}%` }} />
                  </div>
                  <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>52周高: <span style={{ color: '#ff4d4f' }}>{getCurrency(analysis.market)}${fmt(analysis.high_52w)}</span></span>
                </div>
              </PageSection>

              {/* K线图 */}
              <PageSection title="K线图 + 网格线">
                <ReactECharts
                  key={`kline-${stockCode}-${analysis.chart_data?.dates?.length}`}
                  option={klineOption}
                  style={{ height: 380, width: '100%' }}
                  notMerge={true}
                  onChartReady={(chart) => { setTimeout(() => chart.resize(), 100) }}
                />
              </PageSection>

              {/* 网格层级表格 */}
              <PageSection title={`网格层级 (${analysis.total_levels}格)`}>
                <DataTable
                  columns={gridLevelColumns}
                  data={analysis.grid_levels}
                  rowKey={(_, i) => String(i)}
                  striped
                />
              </PageSection>

              {/* 盈亏平衡分析 */}
              <PageSection title="盈亏平衡分析">
                <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>最小网格宽度: {fmt(analysis.breakeven.min_grid_width)} ({analysis.breakeven.min_grid_pct}%)</p>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>每笔交易成本: {fmt(analysis.breakeven.trading_cost_per_share)}/股</p>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>每格利润: {getCurrency(analysis.market)}${fmt(analysis.breakeven.profit_per_trade)}</p>
                <p style={{ color: analysis.breakeven.is_profitable ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
                  {analysis.breakeven.is_profitable ? '✓ 网格宽度足够覆盖交易成本' : '✗ 网格宽度过窄，利润被手续费侵蚀！请加大网格宽度'}
                </p>
              </PageSection>
            </>
          )}
          {analysis?.error && <p style={{ color: '#ff4d4f' }}>{analysis.error}</p>}
        </div>
      )}

      {/* ===== Tab 3: 回测模拟 ===== */}
      {activeTab === 'simulation' && analysis && !analysis.error && (
        <div>
          <StatCardGroup columns={3}>
            <StatCard label="总收益" value={`${getCurrency(analysis.market)}${fmt(analysis.simulation.total_pnl)}`} color={analysis.simulation.total_pnl >= 0 ? '#52c41a' : '#ff4d4f'} />
            <StatCard label="收益率" value={`${analysis.simulation.total_return_pct}%`} color={analysis.simulation.total_return_pct >= 0 ? '#52c41a' : '#ff4d4f'} />
            <StatCard label="已实现盈亏" value={`${getCurrency(analysis.market)}${fmt(analysis.simulation.realized_pnl)}`} color="#1890ff" />
            <StatCard label="未实现盈亏" value={`${getCurrency(analysis.market)}${fmt(analysis.simulation.unrealized_pnl)}`} color="#faad14" />
            <StatCard label="交易次数" value={analysis.simulation.total_trades} color="#d4a76a" />
            <StatCard label="持仓数" value={analysis.simulation.open_positions} color="#722ed1" />
            <StatCard label="累计手续费" value={`${getCurrency(analysis.market)}${fmt(analysis.simulation.total_fees_paid || 0)}`} color="#ff4d4f" />
          </StatCardGroup>

          <PageSection title="风险指标">
            <StatCardGroup columns={3}>
              <StatCard label="夏普比率" value={analysis.simulation.sharpe_ratio} color={analysis.simulation.sharpe_ratio > 1 ? '#52c41a' : '#faad14'} />
              <StatCard label="索提诺比率" value={analysis.simulation.sortino_ratio} color={analysis.simulation.sortino_ratio > 1 ? '#52c41a' : '#faad14'} />
              <StatCard label="卡尔玛比率" value={analysis.simulation.calmar_ratio} color={analysis.simulation.calmar_ratio > 1 ? '#52c41a' : '#faad14'} />
              <StatCard label="盈亏比" value={analysis.simulation.profit_loss_ratio} color={analysis.simulation.profit_loss_ratio > 1 ? '#52c41a' : '#faad14'} />
              <StatCard label="年化波动率" value={`${analysis.simulation.annual_volatility}%`} color="#1890ff" />
              <StatCard label="资金使用率" value={`${analysis.simulation.capital_utilization}%`} color="#722ed1" />
            </StatCardGroup>
          </PageSection>

          {analysis.simulation.stop_loss_triggered && (
            <div className="grid-stoploss-alert">
              <span style={{ color: '#ff4d4f', fontWeight: 600 }}>⚠ 回测期间触发了止损</span>
              <span style={{ color: 'var(--text-secondary)', fontSize: 13, marginLeft: 8 }}>止损次数: {analysis.simulation.num_stop_loss}</span>
            </div>
          )}

          {equityChartOption && (
            <PageSection title="📈 资金曲线">
              <ReactECharts
                key={`equity-${stockCode}-${analysis.simulation.equity_curve?.length}`}
                option={equityChartOption}
                style={{ height: 300, width: '100%' }}
                notMerge={true}
              />
            </PageSection>
          )}

          <PageSection title="交易记录 (最近50笔)">
            <DataTable columns={tradeColumns} data={analysis.simulation.trades.slice(0, 50)} rowKey={(_, i) => String(i)} striped />
          </PageSection>
        </div>
      )}

      {/* ===== Tab 4: 当前状态 ===== */}
      {activeTab === 'status' && analysis && !analysis.error && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <PageSection title="当前位置">
              <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                现价: <span style={{ color: '#d4a76a', fontWeight: 700 }}>{getCurrency(analysis.market)}${fmt(analysis.current_price)}</span>
              </p>
              <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                最近网格: <span style={{ color: '#1890ff' }}>{fmt(analysis.status.nearest_level?.price)}</span>
                ({analysis.status.nearest_level?.distance_pct}%)
              </p>
              {analysis.stop_loss_price && (
                <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                  止损价: <span style={{ color: '#ff4d4f' }}>{fmt(analysis.stop_loss_price)}</span>
                </p>
              )}
            </PageSection>
            <PageSection title="触发价位">
              {analysis.status.next_buy && (
                <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                  下一买入: <span style={{ color: '#52c41a', fontWeight: 700 }}>{getCurrency(analysis.market)}${fmt(analysis.status.next_buy.price)}</span>
                  ({analysis.status.next_buy.distance_pct}%)
                </p>
              )}
              {analysis.status.next_sell && (
                <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                  下一卖出: <span style={{ color: '#ff4d4f', fontWeight: 700 }}>{getCurrency(analysis.market)}${fmt(analysis.status.next_sell.price)}</span>
                  (+{analysis.status.next_sell.distance_pct}%)
                </p>
              )}
            </PageSection>
          </div>

          {analysis.simulation.position_details.length > 0 && (
            <PageSection title={`持仓明细 (${analysis.simulation.open_positions}个)`}>
              <DataTable columns={positionColumns} data={analysis.simulation.position_details} rowKey={(_, i) => String(i)} striped />
            </PageSection>
          )}

          <PageSection title="资金利用率">
            <ProgressBar
              value={analysis.simulation.open_positions}
              max={analysis.total_levels}
              label={`已用: ${analysis.simulation.open_positions}/${analysis.total_levels}格`}
              color={analysis.simulation.open_positions / analysis.total_levels > 0.8 ? '#ff4d4f' : '#d4a76a'}
            />
          </PageSection>
        </div>
      )}

      {/* ===== Tab 5: 参数优化 ===== */}
      {activeTab === 'optimize' && (
        <div>
          <PageSection title="参数优化">
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 12 }}>
              使用当前股票代码和资金设置，自动扫描最优参数组合
            </p>
            <button onClick={loadOptimize} disabled={optimizeLoading} className="grid-btn-primary">
              {optimizeLoading ? '优化中...' : '开始优化'}
            </button>
          </PageSection>

          {optimizeLoading && <LoadingSpinner text="参数优化中..." />}

          {optimizeResult && !optimizeResult.error && (
            <>
              <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 12 }}>
                ATR: {optimizeResult.atr} | 当前价: {fmt(optimizeResult.current_price)} | 扫描了 {optimizeResult.top_combinations?.length > 0 ? '多种' : '0种'} 参数组合
              </p>

              <PageSection title="🏆 Top 5 最优参数组合">
                <DataTable columns={optimizeColumns} data={optimizeResult.top_combinations} rowKey={(_, i) => String(i)} striped />
              </PageSection>

              {optimizeResult.top_combinations.length > 0 && (
                <div className="grid-tip-box">
                  <span style={{ color: '#52c41a', fontWeight: 600 }}>💡 提示：</span>
                  <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                    最优参数为 网格宽度{optimizeResult.top_combinations[0].width_pct}%，
                    {optimizeResult.top_combinations[0].num_grids}格，
                    {optimizeResult.top_combinations[0].sizing === 'equal' ? '等额分配' : '金字塔加仓'}。
                    可以在"网格分析"Tab中手动设置这些参数重新分析。
                  </span>
                </div>
              )}
            </>
          )}
          {optimizeResult?.error && <p style={{ color: '#ff4d4f' }}>{optimizeResult.error}</p>}
        </div>
      )}
    </div>
  )
}
