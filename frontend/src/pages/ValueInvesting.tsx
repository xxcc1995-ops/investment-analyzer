import { LoadingSpinner, PageSection, TabBar, StatCard, StatCardGroup } from '../components/ui'
import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'

const API_BASE = '/api'

interface ScoreDetail {
  score: number
  detail: string
}

interface VIStock {
  code: string
  name: string
  market: 'A' | 'HK' | 'US'
  price: number
  change_pct: number
  pe: number | null
  pb: number | null
  market_cap: number | null
  roe: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
  revenue_growth: number | null
  profit_growth: number | null
  dividend_yield: number | null
  report_period: string
  buffett_score: number
  munger_score: number
  li_lu_score: number
  duan_score: number
  score: number
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
  score_details: {
    buffett: ScoreDetail
    munger: ScoreDetail
    li_lu: ScoreDetail
    duan_yongping: ScoreDetail
  }
}

interface FrameworkDimension {
  dimension: string
  description: string
  criteria: string[]
  key_insight: string
}

interface MasterPhilosophy {
  name: string
  title: string
  era: string
  core_philosophy: string
  investment_framework: FrameworkDimension[]
  classic_quotes: string[]
  key_cases: string
}

interface VIPhilosophy {
  buffett: MasterPhilosophy
  munger: MasterPhilosophy
  li_lu: MasterPhilosophy
  duan_yongping: MasterPhilosophy
  scoring_system: {
    name: string
    description: string
    masters: { name: string; focus: string; weight: string }[]
    match_levels: Record<string, string>
  }
  risks: string[]
}

interface DCFResult {
  intrinsic_value: number
  buy_price: number
  enterprise_value: number
  equity_value?: number
  net_debt?: number
  fcf_projections: number[]
  terminal_value: number
  pv_fcf: number
  pv_terminal: number
  terminal_pct?: number
  current_price?: number
  upside_pct?: number
  buy_upside_pct?: number
  is_undervalued?: boolean
  is_buy_zone?: boolean
  discount_rate: number
  growth_rate: number
  terminal_growth_rate: number
  safety_margin: number
  projection_years?: number
  data_source?: {
    fcf_source: string
    fcf_raw: number | null
    growth_rate_source: string
    discount_rate_source: string
    debt_ratio: number
    report_period: string
    report_type: string
  }
  sensitivity?: {
    growth_rates: string[]
    discount_rates: string[]
    matrix: (number | null)[][]
  }
}

interface GrahamResult {
  eps: number
  bvps: number
  graham_value: number | null
  applicable: boolean
  warnings: string[]
  implied_pe?: number
  implied_pb?: number
  current_price?: number
  upside_pct?: number
  is_undervalued?: boolean
  safety_margin_pct?: number
}

const MASTER_COLORS: Record<string, string> = {
  buffett: '#58a6ff',
  munger: '#3fb950',
  li_lu: '#d29922',
  duan_yongping: '#bc8cff',
}

const MASTER_LABELS: Record<string, string> = {
  buffett: '巴菲特',
  munger: '芒格',
  li_lu: '李录',
  duan_yongping: '段永平',
}

export default function ValueInvesting() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'screener' | 'dcf' | 'graham' | 'ddm' | 'montecarlo'>('philosophy')
  const [stocks, setStocks] = useState<VIStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)
  const [philosophy, setPhilosophy] = useState<VIPhilosophy | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

  // Screener params
  const [market, setMarket] = useState<'all' | 'a' | 'hk' | 'us'>('all')
  const [master, setMaster] = useState<'combined' | 'buffett' | 'munger' | 'li_lu' | 'duan_yongping'>('combined')
  const [minScore, setMinScore] = useState(50)
  const [maxPE, setMaxPE] = useState(30)
  const [maxPB, setMaxPB] = useState(5)
  const [topN, setTopN] = useState(50)

  // DCF state - manual mode
  const [dcfMode, setDcfMode] = useState<'manual' | 'auto'>('auto')
  const [dcfStockCode, setDcfStockCode] = useState('')
  const [dcfMarket, setDcfMarket] = useState<'a' | 'hk' | 'us'>('a')
  const [dcfFcf, setDcfFcf] = useState('100')
  const [dcfGrowth, setDcfGrowth] = useState('10')
  const [dcfShares, setDcfShares] = useState('10')
  const [dcfDiscount, setDcfDiscount] = useState('10')
  const [dcfTerminal, setDcfTerminal] = useState('3')
  const [dcfSafety, setDcfSafety] = useState('30')
  const [dcfNetDebt, setDcfNetDebt] = useState('0')
  const [dcfCurrentPrice, setDcfCurrentPrice] = useState('')
  const [dcfResult, setDcfResult] = useState<DCFResult | null>(null)
  const [dcfLoading, setDcfLoading] = useState(false)
  const [dcfError, setDcfError] = useState('')

  // Graham state
  const [grahamEps, setGrahamEps] = useState('')
  const [grahamBvps, setGrahamBvps] = useState('')
  const [grahamPrice, setGrahamPrice] = useState('')
  const [grahamResult, setGrahamResult] = useState<GrahamResult | null>(null)
  const [grahamLoading, setGrahamLoading] = useState(false)

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/value-investing/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取投资理念失败:', e)
    }
  }, [])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])

  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/value-investing/screener`, {
        params: { market, master, min_score: minScore, max_pe: maxPE, max_pb: maxPB, top_n: topN }
      })
      setStocks(res.data.stocks || [])
      setUpdateTime(res.data.update_time || '')
      setTotal(res.data.total || 0)
    } catch (e) {
      console.error('获取筛选数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [market, master, minScore, maxPE, maxPB, topN])

  const runDCF = useCallback(async () => {
    setDcfLoading(true)
    setDcfError('')
    try {
      let res
      if (dcfMode === 'auto' && dcfStockCode.trim()) {
        res = await axios.post(`${API_BASE}/value-investing/dcf-auto`, {
          stock_code: dcfStockCode.trim(),
          market: dcfMarket,
          growth_rate: dcfGrowth ? parseFloat(dcfGrowth) / 100 : undefined,
          discount_rate: dcfDiscount ? parseFloat(dcfDiscount) / 100 : undefined,
          safety_margin: (parseFloat(dcfSafety) || 30) / 100,
        })
      } else {
        res = await axios.post(`${API_BASE}/value-investing/dcf`, {
          current_fcf: parseFloat(dcfFcf) || 0,
          growth_rate: (parseFloat(dcfGrowth) || 0) / 100,
          shares: parseFloat(dcfShares) || 0,
          discount_rate: (parseFloat(dcfDiscount) || 10) / 100,
          terminal_growth_rate: (parseFloat(dcfTerminal) || 3) / 100,
          safety_margin: (parseFloat(dcfSafety) || 30) / 100,
          net_debt: parseFloat(dcfNetDebt) || 0,
          current_price: parseFloat(dcfCurrentPrice) || 0,
        })
      }
      setDcfResult(res.data)
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'DCF计算失败'
      setDcfError(msg)
    } finally {
      setDcfLoading(false)
    }
  }, [dcfMode, dcfStockCode, dcfMarket, dcfFcf, dcfGrowth, dcfShares, dcfDiscount, dcfTerminal, dcfSafety, dcfNetDebt, dcfCurrentPrice])

  const runGraham = useCallback(async () => {
    setGrahamLoading(true)
    try {
      const res = await axios.post(`${API_BASE}/value-investing/graham`, {
        eps: parseFloat(grahamEps) || 0,
        bvps: parseFloat(grahamBvps) || 0,
        current_price: parseFloat(grahamPrice) || 0,
      })
      setGrahamResult(res.data)
    } catch (e) {
      console.error('Graham计算失败:', e)
    } finally {
      setGrahamLoading(false)
    }
  }, [grahamEps, grahamBvps, grahamPrice])

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 65) return '#1890ff'
    if (score >= 50) return '#faad14'
    return '#ff4d4f'
  }

  const getMatchLevelText = (level: string) => {
    switch (level) {
      case 'excellent': return '优秀'
      case 'good': return '良好'
      case 'fair': return '一般'
      case 'poor': return '较差'
      default: return '-'
    }
  }

  const getMatchLevelColor = (level: string) => {
    switch (level) {
      case 'excellent': return '#52c41a'
      case 'good': return '#1890ff'
      case 'fair': return '#faad14'
      case 'poor': return '#ff4d4f'
      default: return '#666'
    }
  }

  const getMarketTag = (mkt: string) => {
    const colors: Record<string, string> = { A: '#f85149', HK: '#d29922', US: '#58a6ff' }
    return (
      <span style={{
        display: 'inline-block', padding: '1px 6px', borderRadius: '3px',
        fontSize: '11px', fontWeight: 600, background: `${colors[mkt] || '#666'}20`,
        color: colors[mkt] || '#666',
      }}>
        {mkt}
      </span>
    )
  }

  const getFragility = (s: VIStock) => {
    let score = 0
    const d = s.debt_ratio
    if (d !== null && d !== undefined) {
      score += d < 30 ? 20 : d < 50 ? 15 : d < 70 ? 8 : 2
    } else score += 10
    const gm = s.gross_margin
    if (gm !== null && gm !== undefined) {
      score += gm > 50 ? 20 : gm > 30 ? 14 : gm > 15 ? 8 : 2
    } else score += 10
    const nm = s.net_margin
    if (nm !== null && nm !== undefined) {
      score += nm > 20 ? 15 : nm > 10 ? 10 : nm > 5 ? 6 : 2
    } else score += 7
    const rg = s.revenue_growth, pg = s.profit_growth
    if (rg !== null && pg !== null && rg !== undefined && pg !== undefined) {
      score += rg > 15 && pg > 15 ? 15 : rg > 5 && pg > 5 ? 10 : (rg > 0) !== (pg > 0) ? 6 : rg < 0 && pg < 0 ? 2 : 8
    } else score += 7
    const roe = s.roe
    if (roe !== null && roe !== undefined) {
      score += roe > 20 ? 15 : roe > 15 ? 11 : roe > 10 ? 7 : 3
    } else score += 7
    const pe = s.pe, pb = s.pb
    if (pe !== null && pb !== null && pe !== undefined && pb !== undefined) {
      score += pe <= 0 ? 4 : pe < 15 && pb < 2 ? 15 : pe < 25 && pb < 4 ? 10 : pe < 40 && pb < 8 ? 6 : 4
    } else score += 7
    const label = score >= 75 ? '反脆弱' : score >= 60 ? '稳健' : score >= 40 ? '脆弱' : '高度脆弱'
    const color = score >= 75 ? '#16a34a' : score >= 60 ? '#ca8a04' : score >= 40 ? '#ea580c' : '#dc2626'
    return { score, label, color }
  }

  const selectStyle: React.CSSProperties = {
    padding: '6px 12px', border: '1px solid var(--border-primary)',
    borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px',
    border: '1px solid var(--border-primary)', borderRadius: '4px',
    background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: '14px',
  }

  const masterKeys = ['buffett', 'munger', 'li_lu', 'duan_yongping'] as const

  // ============================================================
  // DCF Charts
  // ============================================================

  const getDCFChartOption = () => {
    if (!dcfResult) return {}
    const years = dcfResult.fcf_projections.map((_, i) => `第${i + 1}年`)
    return {
      tooltip: { trigger: 'axis' as const },
      xAxis: { type: 'category' as const, data: years, axisLabel: { color: '#8b949e' } },
      yAxis: { type: 'value' as const, name: 'FCF (亿元)', axisLabel: { color: '#8b949e' }, nameTextStyle: { color: '#8b949e' } },
      series: [{
        type: 'bar' as const,
        data: dcfResult.fcf_projections,
        itemStyle: { color: '#58a6ff', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top' as const, color: '#e6edf3', fontSize: 11, formatter: '{c}' },
      }],
      grid: { left: 60, right: 20, top: 30, bottom: 30 },
      backgroundColor: 'transparent',
    }
  }

  // Waterfall chart: PV(FCF) + PV(Terminal) = Enterprise Value -> Equity Value -> Per Share
  const getWaterfallChartOption = () => {
    if (!dcfResult) return {}
    const categories = ['预测期FCF现值', '终值现值', '企业价值', '减: 净负债', '股权价值', '÷ 股本', '每股内在价值']
    const values = [
      dcfResult.pv_fcf,
      dcfResult.pv_terminal,
      dcfResult.enterprise_value,
      -(dcfResult.net_debt || 0),
      dcfResult.equity_value || dcfResult.enterprise_value,
      0,  // placeholder for shares
      dcfResult.intrinsic_value,
    ]

    // Build waterfall
    const base = [0, dcfResult.pv_fcf, 0, dcfResult.enterprise_value, dcfResult.equity_value || dcfResult.enterprise_value, 0, 0]
    const bar = [
      dcfResult.pv_fcf,
      dcfResult.pv_terminal,
      dcfResult.enterprise_value,
      -(dcfResult.net_debt || 0),
      dcfResult.equity_value || dcfResult.enterprise_value,
      0,
      dcfResult.intrinsic_value,
    ]

    // Simplified: just show key values as stacked bars
    return {
      tooltip: {
        trigger: 'axis' as const,
        formatter: (params: any) => {
          const idx = params[0]?.dataIndex
          const labels = [
            `预测期FCF现值: ${dcfResult.pv_fcf.toFixed(2)}亿`,
            `终值现值: ${dcfResult.pv_terminal.toFixed(2)}亿`,
            `企业价值: ${dcfResult.enterprise_value.toFixed(2)}亿`,
            `净负债: ${(dcfResult.net_debt || 0).toFixed(2)}亿`,
            `股权价值: ${(dcfResult.equity_value || dcfResult.enterprise_value).toFixed(2)}亿`,
            `总股本`,
            `每股内在价值: ${dcfResult.intrinsic_value.toFixed(2)}元`,
          ]
          return labels[idx] || ''
        }
      },
      xAxis: {
        type: 'category' as const,
        data: categories,
        axisLabel: { color: '#8b949e', rotate: 20, fontSize: 11 },
      },
      yAxis: {
        type: 'value' as const,
        name: '亿元',
        axisLabel: { color: '#8b949e' },
        nameTextStyle: { color: '#8b949e' },
      },
      series: [
        {
          name: 'base',
          type: 'bar' as const,
          stack: 'waterfall',
          itemStyle: { color: 'transparent', borderColor: 'transparent' },
          emphasis: { itemStyle: { color: 'transparent', borderColor: 'transparent' } },
          data: base,
        },
        {
          name: 'value',
          type: 'bar' as const,
          stack: 'waterfall',
          data: bar.map((v, i) => ({
            value: v,
            itemStyle: {
              color: i === 3 ? '#f85149' : i === 6 ? '#58a6ff' : i === 4 ? '#3fb950' : '#58a6ff90',
              borderRadius: [4, 4, 0, 0],
            },
          })),
          label: {
            show: true,
            position: 'top' as const,
            color: '#e6edf3',
            fontSize: 11,
            formatter: (p: any) => {
              const idx = p.dataIndex
              if (idx === 5) return `${dcfResult.projection_years || 10}年`
              return typeof p.value === 'number' ? p.value.toFixed(2) : ''
            },
          },
        },
      ],
      grid: { left: 70, right: 20, top: 30, bottom: 50 },
      backgroundColor: 'transparent',
    }
  }

  // Sensitivity heatmap
  const getSensitivityHeatmapOption = () => {
    if (!dcfResult?.sensitivity) return {}
    const { growth_rates, discount_rates, matrix } = dcfResult.sensitivity

    const data: [number, number, number | null][] = []
    for (let gi = 0; gi < growth_rates.length; gi++) {
      for (let di = 0; di < discount_rates.length; di++) {
        data.push([di, gi, matrix[gi][di]])
      }
    }

    const validValues = data.filter(d => d[2] !== null).map(d => d[2] as number)
    const minVal = validValues.length > 0 ? Math.min(...validValues) : 0
    const maxVal = validValues.length > 0 ? Math.max(...validValues) : 100

    return {
      tooltip: {
        formatter: (params: any) => {
          const [di, gi, val] = params.data
          return `增长率${growth_rates[gi]} / 折现率${discount_rates[di]}<br/>内在价值: ${val !== null ? val.toFixed(2) + '元' : 'N/A'}`
        }
      },
      xAxis: {
        type: 'category' as const,
        data: discount_rates,
        name: '折现率',
        axisLabel: { color: '#8b949e' },
        nameTextStyle: { color: '#8b949e' },
      },
      yAxis: {
        type: 'category' as const,
        data: growth_rates,
        name: '增长率',
        axisLabel: { color: '#8b949e' },
        nameTextStyle: { color: '#8b949e' },
      },
      visualMap: {
        min: minVal,
        max: maxVal,
        calculable: true,
        orient: 'horizontal' as const,
        left: 'center',
        bottom: 0,
        inRange: {
          color: ['#f85149', '#d29922', '#3fb950', '#58a6ff'],
        },
        textStyle: { color: '#8b949e' },
      },
      series: [{
        type: 'heatmap' as const,
        data: data,
        label: {
          show: true,
          color: '#e6edf3',
          fontSize: 11,
          formatter: (p: any) => p.data[2] !== null ? p.data[2].toFixed(1) : 'N/A',
        },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
      }],
      grid: { left: 80, right: 20, top: 20, bottom: 60 },
      backgroundColor: 'transparent',
    }
  }

  // Intrinsic value vs market price comparison bar
  const getComparisonChartOption = () => {
    if (!dcfResult?.current_price) return {}
    const price = dcfResult.current_price
    const intrinsic = dcfResult.intrinsic_value
    const buy = dcfResult.buy_price

    return {
      tooltip: { trigger: 'axis' as const },
      xAxis: {
        type: 'category' as const,
        data: ['当前价格', '安全买点', '内在价值'],
        axisLabel: { color: '#8b949e' },
      },
      yAxis: {
        type: 'value' as const,
        name: '元/股',
        axisLabel: { color: '#8b949e' },
        nameTextStyle: { color: '#8b949e' },
      },
      series: [{
        type: 'bar' as const,
        data: [
          { value: price, itemStyle: { color: '#f85149' } },
          { value: buy, itemStyle: { color: '#d29922' } },
          { value: intrinsic, itemStyle: { color: '#3fb950' } },
        ],
        label: {
          show: true,
          position: 'top' as const,
          color: '#e6edf3',
          fontSize: 13,
          fontWeight: 'bold' as const,
          formatter: '{c} 元',
        },
      }],
      grid: { left: 60, right: 20, top: 30, bottom: 30 },
      backgroundColor: 'transparent',
    }
  }

  return (
    <div className="cb-page">
      <PageSection title="价值投资筛选器" extra={<span className="stock-code">巴菲特 / 芒格 / 李录 / 段永平 投资理念与筛选</span>} compact>

      <TabBar
        tabs={[
          { key: 'philosophy', label: '投资理念' },
          { key: 'screener', label: '价投筛选' },
          { key: 'dcf', label: 'DCF估值' },
          { key: 'ddm', label: 'DDM股息估值' },
          { key: 'montecarlo', label: '蒙特卡洛DCF' },
          { key: 'graham', label: '格雷厄姆' },
        ]}
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as typeof activeTab)}
      />

      {/* ===== Philosophy Tab ===== */}
      {activeTab === 'philosophy' && philosophy && (
        <div style={{ padding: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
            {masterKeys.map((key) => {
              const data = philosophy[key]
              if (!data) return null
              const color = MASTER_COLORS[key]
              return (
                <div key={key} className="arb-notes" style={{ margin: 0, borderLeft: `3px solid ${color}` }}>
                  <h3 style={{ color, marginBottom: '4px' }}>{data.name}</h3>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>{data.title}</div>
                  <div style={{ fontSize: '11px', color: color, marginBottom: '12px', opacity: 0.8 }}>{data.era}</div>
                  <div className="arb-notes-content">
                    <div className="arb-risk-section">
                      <h4>核心思想</h4>
                      <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{data.core_philosophy}</p>
                    </div>

                    {data.investment_framework.map((fw, fi) => (
                      <div key={fi} className="arb-risk-section" style={{ marginTop: '12px' }}>
                        <h4 style={{ color }}>{fw.dimension}</h4>
                        <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>{fw.description}</p>
                        <ul>
                          {fw.criteria.map((c, ci) => (
                            <li key={ci} style={{ fontSize: '12px' }}>{c}</li>
                          ))}
                        </ul>
                        <div style={{
                          marginTop: '8px', padding: '6px 10px', background: `${color}10`,
                          borderRadius: '4px', fontSize: '12px', fontStyle: 'italic', color: 'var(--text-secondary)',
                          borderLeft: `2px solid ${color}`,
                        }}>
                          {fw.key_insight}
                        </div>
                      </div>
                    ))}

                    <div style={{ marginTop: '12px', padding: '8px', background: `${color}15`, borderRadius: '6px' }}>
                      {data.classic_quotes.map((q, qi) => (
                        <div key={qi} style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)', marginBottom: qi < data.classic_quotes.length - 1 ? '6px' : 0 }}>
                          "{q}"
                        </div>
                      ))}
                    </div>

                    <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                      代表案例: {data.key_cases}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Scoring system */}
          <div className="arb-notes" style={{ margin: 0, borderLeft: '3px solid #58a6ff' }}>
            <h3 style={{ color: '#58a6ff' }}>{philosophy.scoring_system.name}</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>{philosophy.scoring_system.description}</p>
            <div className="arb-notes-content">
              <div className="arb-notes-grid">
                {philosophy.scoring_system.masters.map((m, i) => (
                  <div key={i} className="arb-note-item" style={{ borderLeft: `2px solid ${MASTER_COLORS[masterKeys[i]]}` }}>
                    <span className="arb-note-label" style={{ color: MASTER_COLORS[masterKeys[i]] }}>{m.name}</span>
                    <span className="arb-note-value" style={{ fontSize: '12px' }}>{m.focus}</span>
                    <span className="arb-note-desc" style={{ fontSize: '11px' }}>{m.weight}</span>
                  </div>
                ))}
              </div>
              <div className="arb-notes-grid" style={{ marginTop: '12px' }}>
                {Object.entries(philosophy.scoring_system.match_levels).map(([key, desc]) => (
                  <div key={key} className="arb-note-item">
                    <span className="arb-note-label" style={{ color: getMatchLevelColor(key) }}>
                      {getMatchLevelText(key)}
                    </span>
                    <span className="arb-note-value">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Risks */}
          <div className="arb-notes" style={{ margin: '20px 0 0' }}>
            <h3 style={{ color: '#f85149' }}>风险提示</h3>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <ul>
                  {philosophy.risks.map((risk, i) => (
                    <li key={i} style={{ fontSize: '13px' }}>{risk}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===== Screener Tab ===== */}
      {activeTab === 'screener' && (
        <div style={{ padding: '16px 20px' }}>
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px',
            padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
            border: '1px solid var(--border-primary)',
          }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>市场</label>
              <select value={market} onChange={e => setMarket(e.target.value as any)} style={selectStyle}>
                <option value="all">全部市场</option>
                <option value="a">A股</option>
                <option value="hk">港股</option>
                <option value="us">美股</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>大师标准</label>
              <select value={master} onChange={e => setMaster(e.target.value as any)} style={selectStyle}>
                <option value="combined">综合</option>
                <option value="buffett">巴菲特</option>
                <option value="munger">芒格</option>
                <option value="li_lu">李录</option>
                <option value="duan_yongping">段永平</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>最低评分</label>
              <select value={minScore} onChange={e => setMinScore(Number(e.target.value))} style={selectStyle}>
                <option value={40}>40分</option>
                <option value={50}>50分</option>
                <option value={60}>60分</option>
                <option value={70}>70分</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>最大PE</label>
              <select value={maxPE} onChange={e => setMaxPE(Number(e.target.value))} style={selectStyle}>
                <option value={15}>15</option>
                <option value={20}>20</option>
                <option value={25}>25</option>
                <option value={30}>30</option>
                <option value={50}>50</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>最大PB</label>
              <select value={maxPB} onChange={e => setMaxPB(Number(e.target.value))} style={selectStyle}>
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={8}>8</option>
                <option value={10}>10</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>显示数量</label>
              <select value={topN} onChange={e => setTopN(Number(e.target.value))} style={selectStyle}>
                <option value={30}>前30只</option>
                <option value={50}>前50只</option>
                <option value={100}>前100只</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={loadStocks} style={{
                padding: '6px 16px', background: 'var(--accent-blue)', color: '#fff',
                border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
              }}>
                筛选
              </button>
            </div>
          </div>

          <div className="data-freshness" style={{ marginBottom: '16px' }}>
            <span className="freshness-tag">市场: {market === 'all' ? '全部' : market === 'a' ? 'A股' : market === 'hk' ? '港股' : '美股'}</span>
            <span className="freshness-tag">标准: {master === 'combined' ? '综合' : MASTER_LABELS[master]}</span>
            <span className="freshness-tag">更新: {updateTime}</span>
            <span className="freshness-tag">结果: {total} 只</span>
          </div>

          {loading ? (
            <LoadingSpinner />
          ) : (
            <div className="table-container">
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>市场</th>
                    <th>报告期</th>
                    <th>现价</th>
                    <th>涨跌</th>
                    <th>PE</th>
                    <th>PB</th>
                    <th>PEG</th>
                    <th>ROE%</th>
                    <th>毛利率%</th>
                    <th>负债率%</th>
                    <th style={{ color: MASTER_COLORS.buffett }}>巴菲特</th>
                    <th style={{ color: MASTER_COLORS.munger }}>芒格</th>
                    <th style={{ color: MASTER_COLORS.li_lu }}>李录</th>
                    <th style={{ color: MASTER_COLORS.duan_yongping }}>段永平</th>
                    <th>综合</th>
                    <th>匹配</th>
                    <th>抗脆弱</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((s, i) => {
                    const isExpanded = expandedStock === `${s.market}-${s.code}`
                    return (
                      <>
                        <tr
                          key={`${s.market}-${s.code}`}
                          onClick={() => setExpandedStock(isExpanded ? null : `${s.market}-${s.code}`)}
                          style={{ cursor: 'pointer' }}
                        >
                          <td>{i + 1}</td>
                          <td style={{ fontWeight: 600 }}>{s.code}</td>
                          <td>{s.name}</td>
                          <td>{getMarketTag(s.market)}</td>
                          <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{s.report_period || '--'}</td>
                          <td>{s.price?.toFixed(2) ?? '--'}</td>
                          <td style={{ color: s.change_pct >= 0 ? '#f85149' : '#3fb950' }}>
                            {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                          </td>
                          <td style={{
                            color: (s.pe ?? 999) <= 15 ? '#52c41a' : (s.pe ?? 999) <= 25 ? '#1890ff' : '#faad14',
                            fontWeight: 600,
                          }}>{s.pe?.toFixed(1) ?? '--'}</td>
                          <td style={{
                            color: (s.pb ?? 999) <= 2 ? '#52c41a' : (s.pb ?? 999) <= 4 ? '#1890ff' : '#faad14',
                            fontWeight: 600,
                          }}>{s.pb?.toFixed(2) ?? '--'}</td>
                          <td style={{ fontWeight: 600, color: (() => {
                            if (s.pe && s.profit_growth && s.profit_growth > 0) {
                              const peg = s.pe / s.profit_growth;
                              return peg < 1 ? '#52c41a' : peg <= 2 ? '#1890ff' : '#ff4d4f';
                            }
                            return '#6b7280';
                          })() }}>
                            {(s.pe && s.profit_growth && s.profit_growth > 0) ? (s.pe / s.profit_growth).toFixed(2) : '--'}
                          </td>
                          <td style={{
                            color: (s.roe ?? 0) >= 15 ? '#52c41a' : (s.roe ?? 0) >= 10 ? '#1890ff' : '#faad14',
                          }}>{s.roe?.toFixed(1) ?? '--'}</td>
                          <td>{s.gross_margin?.toFixed(1) ?? '--'}</td>
                          <td style={{
                            color: (s.debt_ratio ?? 100) < 50 ? '#52c41a' : (s.debt_ratio ?? 100) < 65 ? '#faad14' : '#ff4d4f',
                          }}>{s.debt_ratio?.toFixed(1) ?? '--'}</td>
                          <td style={{ color: getScoreColor(s.buffett_score), fontWeight: 600 }}>{s.buffett_score}</td>
                          <td style={{ color: getScoreColor(s.munger_score), fontWeight: 600 }}>{s.munger_score}</td>
                          <td style={{ color: getScoreColor(s.li_lu_score), fontWeight: 600 }}>{s.li_lu_score}</td>
                          <td style={{ color: getScoreColor(s.duan_score), fontWeight: 600 }}>{s.duan_score}</td>
                          <td>
                            <span style={{ color: getScoreColor(s.score), fontWeight: 700, fontSize: '15px' }}>{s.score}</span>
                          </td>
                          <td>
                            <span style={{
                              display: 'inline-block', padding: '2px 8px', borderRadius: '4px',
                              fontSize: '12px', fontWeight: 600,
                              background: `${getMatchLevelColor(s.match_level)}20`,
                              color: getMatchLevelColor(s.match_level),
                            }}>
                              {getMatchLevelText(s.match_level)}
                            </span>
                          </td>
                          <td>
                            {(() => {
                              const f = getFragility(s)
                              return (
                                <span style={{
                                  display: 'inline-block', padding: '2px 8px', borderRadius: '4px',
                                  fontSize: '12px', fontWeight: 600,
                                  background: `${f.color}20`,
                                  color: f.color,
                                }}>
                                  {f.label} {f.score}
                                </span>
                              )
                            })()}
                          </td>
                        </tr>
                        {isExpanded && s.score_details && (
                          <tr key={`${s.market}-${s.code}-detail`} style={{ background: 'var(--bg-secondary)' }}>
                            <td colSpan={20} style={{ padding: '12px 20px' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                                {masterKeys.map((mk) => {
                                  const detail = s.score_details[mk]
                                  if (!detail) return null
                                  return (
                                    <div key={mk} style={{
                                      padding: '10px 14px', borderRadius: '6px',
                                      background: `${MASTER_COLORS[mk]}08`,
                                      border: `1px solid ${MASTER_COLORS[mk]}30`,
                                    }}>
                                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                        <span style={{ fontWeight: 600, color: MASTER_COLORS[mk], fontSize: '13px' }}>
                                          {MASTER_LABELS[mk]}
                                        </span>
                                        <span style={{ fontWeight: 700, fontSize: '16px', color: getScoreColor(detail.score) }}>
                                          {detail.score}
                                        </span>
                                      </div>
                                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                                        {detail.detail}
                                      </div>
                                    </div>
                                  )
                                })}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })}
                  {stocks.length === 0 && (
                    <tr>
                      <td colSpan={20} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        点击"筛选"按钮开始价值投资选股
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ===== DCF Calculator Tab ===== */}
      {activeTab === 'dcf' && (
        <div style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', gap: '20px' }}>
            {/* Input panel */}
            <div style={{
              minWidth: '340px', padding: '20px', background: 'var(--bg-secondary)',
              borderRadius: '8px', border: '1px solid var(--border-primary)',
            }}>
              <h3 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>DCF 估值计算器</h3>

              {/* Mode toggle */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                {(['auto', 'manual'] as const).map(mode => (
                  <button key={mode} onClick={() => setDcfMode(mode)} style={{
                    flex: 1, padding: '6px 12px', borderRadius: '4px', border: 'none',
                    cursor: 'pointer', fontWeight: 600, fontSize: '12px',
                    background: dcfMode === mode ? 'var(--accent-blue)' : 'var(--bg-primary)',
                    color: dcfMode === mode ? '#fff' : 'var(--text-secondary)',
                  }}>
                    {mode === 'auto' ? '自动获取' : '手动输入'}
                  </button>
                ))}
              </div>

              {dcfMode === 'auto' ? (
                <>
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      股票代码
                    </label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="text" value={dcfStockCode} onChange={e => setDcfStockCode(e.target.value)}
                        placeholder="如 600519"
                        style={{ ...inputStyle, flex: 1 }}
                      />
                      <select value={dcfMarket} onChange={e => setDcfMarket(e.target.value as any)} style={selectStyle}>
                        <option value="a">A股</option>
                        <option value="hk">港股</option>
                        <option value="us">美股</option>
                      </select>
                    </div>
                  </div>
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      折现率 (%) <span style={{ opacity: 0.6 }}>留空自动WACC</span>
                    </label>
                    <input type="number" value={dcfDiscount} onChange={e => setDcfDiscount(e.target.value)} placeholder="默认10" style={inputStyle} />
                  </div>
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                      增长率 (%) <span style={{ opacity: 0.6 }}>留空自动估算</span>
                    </label>
                    <input type="number" value={dcfGrowth} onChange={e => setDcfGrowth(e.target.value)} placeholder="默认8" style={inputStyle} />
                  </div>
                </>
              ) : (
                <>
                  {[
                    { label: '当前自由现金流 (亿元)', value: dcfFcf, set: setDcfFcf, placeholder: '如: 100' },
                    { label: '增长率 (%)', value: dcfGrowth, set: setDcfGrowth, placeholder: '如: 10' },
                    { label: '总股本 (亿股)', value: dcfShares, set: setDcfShares, placeholder: '如: 10' },
                    { label: '折现率 (%)', value: dcfDiscount, set: setDcfDiscount, placeholder: '默认 10' },
                    { label: '永续增长率 (%)', value: dcfTerminal, set: setDcfTerminal, placeholder: '默认 3' },
                    { label: '净负债 (亿元)', value: dcfNetDebt, set: setDcfNetDebt, placeholder: '0' },
                    { label: '当前股价 (元)', value: dcfCurrentPrice, set: setDcfCurrentPrice, placeholder: '可选' },
                  ].map(({ label, value, set, placeholder }) => (
                    <div key={label} style={{ marginBottom: '12px' }}>
                      <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>{label}</label>
                      <input type="number" value={value} onChange={e => set(e.target.value)} placeholder={placeholder} style={inputStyle} />
                    </div>
                  ))}
                </>
              )}

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>安全边际 (%)</label>
                <input type="number" value={dcfSafety} onChange={e => setDcfSafety(e.target.value)} placeholder="默认 30" style={inputStyle} />
              </div>

              <button
                onClick={runDCF}
                disabled={dcfLoading}
                style={{
                  width: '100%', padding: '10px', background: 'var(--accent-blue)', color: '#fff',
                  border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
                  fontSize: '14px', marginTop: '4px',
                }}
              >
                {dcfLoading ? '计算中...' : dcfMode === 'auto' ? '自动估值' : '计算内在价值'}
              </button>

              {dcfError && (
                <div style={{ marginTop: '12px', padding: '10px', background: '#f8514920', borderRadius: '4px', color: '#f85149', fontSize: '13px' }}>
                  {dcfError}
                </div>
              )}

              {/* Data source info for auto mode */}
              {dcfResult?.data_source && (
                <div style={{ marginTop: '16px', padding: '10px', background: 'var(--bg-primary)', borderRadius: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
                  <div style={{ fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>数据来源</div>
                  <div>FCF: {dcfResult.data_source.fcf_source === 'cashflow_statement' ? '现金流量表' : '净利润估算'}{dcfResult.data_source.fcf_raw ? ` (${dcfResult.data_source.fcf_raw}亿)` : ''}</div>
                  <div>增长率: {dcfResult.data_source.growth_rate_source === 'historical_cagr' ? '历史CAGR(保守)' : '手动输入'}</div>
                  <div>折现率: {dcfResult.data_source.discount_rate_source === 'wacc_estimated' ? 'WACC估算' : '手动输入'}</div>
                  <div>报告期: {dcfResult.data_source.report_period} ({dcfResult.data_source.report_type})</div>
                </div>
              )}
            </div>

            {/* Results panel */}
            <div style={{ flex: 1 }}>
              {dcfResult ? (
                <>
                  {/* Summary cards */}
                  <StatCardGroup columns={4} style={{ marginBottom: '16px' }}>
                    <StatCard label="每股内在价值" value={`${dcfResult.intrinsic_value} 元`} color="#58a6ff" />
                    <StatCard label="安全买点" value={`${dcfResult.buy_price} 元`} color="#3fb950" />
                    <StatCard
                      label="上行空间"
                      value={dcfResult.upside_pct !== undefined ? `${dcfResult.upside_pct > 0 ? '+' : ''}${dcfResult.upside_pct}%` : '--'}
                      color={dcfResult.upside_pct !== undefined && dcfResult.upside_pct > 0 ? '#3fb950' : '#f85149'}
                    />
                    <StatCard
                      label="终值占比"
                      value={dcfResult.terminal_pct !== undefined ? `${dcfResult.terminal_pct}%` : '--'}
                      color={dcfResult.terminal_pct !== undefined && dcfResult.terminal_pct < 60 ? '#3fb950' : '#d29922'}
                    />
                  </StatCardGroup>

                  {/* Intrinsic value vs market price */}
                  {dcfResult.current_price && dcfResult.current_price > 0 && (
                    <div style={{
                      padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                      border: '1px solid var(--border-primary)', marginBottom: '16px',
                    }}>
                      <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>
                        内在价值 vs 市场价格
                        {dcfResult.is_undervalued !== undefined && (
                          <span style={{
                            marginLeft: '12px', fontSize: '13px', padding: '2px 10px', borderRadius: '4px',
                            background: dcfResult.is_undervalued ? '#3fb95020' : '#f8514920',
                            color: dcfResult.is_undervalued ? '#3fb950' : '#f85149',
                          }}>
                            {dcfResult.is_buy_zone ? '进入买点区间' : dcfResult.is_undervalued ? '低估' : '高估'}
                          </span>
                        )}
                      </h4>
                      <ReactECharts option={getComparisonChartOption()} style={{ height: '260px' }} />
                    </div>
                  )}

                  {/* DCF Waterfall */}
                  <div style={{
                    padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                    border: '1px solid var(--border-primary)', marginBottom: '16px',
                  }}>
                    <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>估值拆解</h4>
                    <ReactECharts option={getWaterfallChartOption()} style={{ height: '300px' }} />
                  </div>

                  {/* FCF Projection Chart */}
                  <div style={{
                    padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                    border: '1px solid var(--border-primary)', marginBottom: '16px',
                  }}>
                    <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>
                      未来FCF预测（共{dcfResult.fcf_projections.length}年）
                    </h4>
                    <ReactECharts option={getDCFChartOption()} style={{ height: '260px' }} />
                  </div>

                  {/* Sensitivity Analysis Heatmap */}
                  {dcfResult.sensitivity && (
                    <div style={{
                      padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                      border: '1px solid var(--border-primary)',
                    }}>
                      <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>敏感性分析（每股内在价值）</h4>
                      <ReactECharts option={getSensitivityHeatmapOption()} style={{ height: '320px' }} />
                      {/* Table fallback */}
                      <div className="table-container" style={{ marginTop: '12px' }}>
                        <table className="arb-table">
                          <thead>
                            <tr>
                              <th>增长率 \ 折现率</th>
                              {dcfResult.sensitivity.discount_rates.map(dr => (
                                <th key={dr}>{dr}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {dcfResult.sensitivity.growth_rates.map((gr, gi) => (
                              <tr key={gr}>
                                <td style={{ fontWeight: 600 }}>{gr}</td>
                                {dcfResult.sensitivity!.matrix[gi].map((val, di) => (
                                  <td key={di} style={{
                                    color: val === null ? '#666' : dcfResult.current_price && val > dcfResult.current_price ? '#3fb950' : '#f85149',
                                    fontWeight: 600,
                                  }}>
                                    {val !== null ? val.toFixed(2) : 'N/A'}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                        {dcfResult.current_price ? `绿色 = 高于当前价${dcfResult.current_price}元 (低估) | 红色 = 低于当前价 (高估)` : '对比当前市场价格判断估值高低'}
                      </div>
                    </div>
                  )}

                  {/* Key parameters */}
                  <div style={{
                    marginTop: '16px', padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                    border: '1px solid var(--border-primary)',
                  }}>
                    <h4 style={{ marginBottom: '12px', color: 'var(--text-primary)' }}>估值参数</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                      {[
                        { label: '折现率', value: `${(dcfResult.discount_rate * 100).toFixed(1)}%` },
                        { label: '增长率', value: `${(dcfResult.growth_rate * 100).toFixed(1)}%` },
                        { label: '永续增长率', value: `${(dcfResult.terminal_growth_rate * 100).toFixed(1)}%` },
                        { label: '安全边际', value: `${(dcfResult.safety_margin * 100).toFixed(0)}%` },
                        { label: '企业价值', value: `${dcfResult.enterprise_value.toFixed(2)}亿` },
                        { label: '股权价值', value: `${(dcfResult.equity_value || dcfResult.enterprise_value).toFixed(2)}亿` },
                        { label: '净负债', value: `${(dcfResult.net_debt || 0).toFixed(2)}亿` },
                        { label: 'FCF现值', value: `${dcfResult.pv_fcf.toFixed(2)}亿` },
                      ].map(({ label, value }) => (
                        <div key={label} style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '2px' }}>{label}</div>
                          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  height: '400px', color: 'var(--text-muted)', fontSize: '14px',
                }}>
                  {dcfMode === 'auto' ? '输入股票代码，自动获取财务数据并计算DCF估值' : '输入参数后点击"计算内在价值"查看DCF估值结果'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ===== DDM Tab ===== */}
      {activeTab === 'ddm' && <DDMCalculator />}

      {/* ===== Monte Carlo Tab ===== */}
      {activeTab === 'montecarlo' && <MonteCarloDCF />}

      {/* ===== Graham Number Tab ===== */}
      {activeTab === 'graham' && (
        <div style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', gap: '20px' }}>
            {/* Input panel */}
            <div style={{
              minWidth: '320px', padding: '20px', background: 'var(--bg-secondary)',
              borderRadius: '8px', border: '1px solid var(--border-primary)',
            }}>
              <h3 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>格雷厄姆公式</h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px', lineHeight: '1.6' }}>
                公式: <code style={{ background: 'var(--bg-primary)', padding: '2px 4px', borderRadius: '2px' }}>sqrt(22.5 * EPS * BVPS)</code>
                <br />含义: 15倍PE * 1.5倍PB = 22.5，格雷厄姆认为的合理估值上限
                <br />适用: 稳定盈利的成熟企业（EPS &gt; 0, BVPS &gt; 0）
              </p>
              {[
                { label: '每股收益 EPS (元)', value: grahamEps, set: setGrahamEps, placeholder: '如: 5.0' },
                { label: '每股净资产 BVPS (元)', value: grahamBvps, set: setGrahamBvps, placeholder: '如: 30.0' },
                { label: '当前股价 (元)', value: grahamPrice, set: setGrahamPrice, placeholder: '可选' },
              ].map(({ label, value, set, placeholder }) => (
                <div key={label} style={{ marginBottom: '12px' }}>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>{label}</label>
                  <input type="number" value={value} onChange={e => set(e.target.value)} placeholder={placeholder} style={inputStyle} />
                </div>
              ))}
              <button
                onClick={runGraham}
                disabled={grahamLoading}
                style={{
                  width: '100%', padding: '10px', background: 'var(--accent-blue)', color: '#fff',
                  border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
                  fontSize: '14px', marginTop: '4px',
                }}
              >
                {grahamLoading ? '计算中...' : '计算格雷厄姆价值'}
              </button>
            </div>

            {/* Results */}
            <div style={{ flex: 1 }}>
              {grahamResult ? (
                <>
                  {!grahamResult.applicable ? (
                    <div style={{
                      padding: '20px', background: '#f8514920', borderRadius: '8px',
                      border: '1px solid #f8514940', color: '#f85149',
                    }}>
                      <h4 style={{ marginBottom: '8px' }}>不适用</h4>
                      {grahamResult.warnings.map((w, i) => (
                        <p key={i} style={{ fontSize: '13px', marginBottom: '4px' }}>{w}</p>
                      ))}
                      <p style={{ fontSize: '12px', marginTop: '12px', color: 'var(--text-muted)' }}>
                        格雷厄姆公式要求EPS和BVPS均为正数。对于亏损企业或资不抵债企业，请使用DCF模型。
                      </p>
                    </div>
                  ) : (
                    <>
                      <StatCardGroup columns={3} style={{ marginBottom: '20px' }}>
                        <StatCard label="格雷厄姆内在价值" value={`${grahamResult.graham_value} 元`} color="#58a6ff" />
                        <StatCard label="隐含PE" value={`${grahamResult.implied_pe}x`} color="#3fb950" />
                        <StatCard label="隐含PB" value={`${grahamResult.implied_pb}x`} color="#d29922" />
                      </StatCardGroup>

                      {grahamResult.current_price && (
                        <div style={{
                          padding: '20px', background: 'var(--bg-secondary)', borderRadius: '8px',
                          border: '1px solid var(--border-primary)',
                        }}>
                          <h4 style={{ marginBottom: '16px', color: 'var(--text-primary)' }}>估值对比</h4>
                          <ReactECharts option={{
                            tooltip: { trigger: 'axis' as const },
                            xAxis: {
                              type: 'category' as const,
                              data: ['当前股价', '格雷厄姆价值'],
                              axisLabel: { color: '#8b949e' },
                            },
                            yAxis: {
                              type: 'value' as const, name: '元/股',
                              axisLabel: { color: '#8b949e' },
                              nameTextStyle: { color: '#8b949e' },
                            },
                            series: [{
                              type: 'bar' as const,
                              data: [
                                { value: grahamResult.current_price, itemStyle: { color: '#f85149' } },
                                { value: grahamResult.graham_value, itemStyle: { color: '#3fb950' } },
                              ],
                              label: {
                                show: true, position: 'top' as const,
                                color: '#e6edf3', fontSize: 13, fontWeight: 'bold' as const,
                                formatter: '{c} 元',
                              },
                            }],
                            grid: { left: 60, right: 20, top: 30, bottom: 30 },
                            backgroundColor: 'transparent',
                          }} style={{ height: '280px' }} />
                          <div style={{ textAlign: 'center', marginTop: '12px' }}>
                            <span style={{
                              fontSize: '18px', fontWeight: 700, padding: '4px 16px', borderRadius: '6px',
                              background: grahamResult.is_undervalued ? '#3fb95020' : '#f8514920',
                              color: grahamResult.is_undervalued ? '#3fb950' : '#f85149',
                            }}>
                              {grahamResult.is_undervalued
                                ? `低估 ${grahamResult.safety_margin_pct}% 安全边际`
                                : `高估 (安全边际 -${Math.abs(grahamResult.safety_margin_pct || 0)}%)`
                              }
                            </span>
                          </div>
                        </div>
                      )}

                      <div style={{
                        marginTop: '16px', padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
                        border: '1px solid var(--border-primary)',
                      }}>
                        <h4 style={{ marginBottom: '8px', color: 'var(--text-primary)' }}>公式解读</h4>
                        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
                          <div>格雷厄姆价值 = sqrt(22.5 x {grahamResult.eps} x {grahamResult.bvps}) = sqrt({(22.5 * grahamResult.eps * grahamResult.bvps).toFixed(0)}) = <strong>{grahamResult.graham_value}元</strong></div>
                          <div style={{ marginTop: '8px', color: 'var(--text-muted)', fontSize: '12px' }}>
                            22.5 = PE上限15 x PB上限1.5，代表格雷厄姆认为合理估值的上限
                            <br />隐含PE={grahamResult.implied_pe}，隐含PB={grahamResult.implied_pb}
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </>
              ) : (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  height: '400px', color: 'var(--text-muted)', fontSize: '14px',
                }}>
                  输入EPS和每股净资产，计算格雷厄姆内在价值
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      </PageSection>
    </div>
  )
}


// ============ DDM 股息贴现计算器 ============

function DDMCalculator() {
  const [form, setForm] = useState({ dps: '', growthRate: '', discountRate: '10', currentPrice: '', highGrowthRate: '', highGrowthYears: '5', stableGrowthRate: '3' })
  const [mode, setMode] = useState<'gordon' | 'twostage'>('gordon')
  const [result, setResult] = useState<any>(null)
  const [sensitivity, setSensitivity] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleCalc = async () => {
    const dps = parseFloat(form.dps)
    const growthRate = parseFloat(form.growthRate) / 100
    const discountRate = parseFloat(form.discountRate) / 100
    const currentPrice = parseFloat(form.currentPrice) || 0

    if (!dps || dps <= 0) { alert('请输入每股股息'); return }
    if (isNaN(growthRate)) { alert('请输入增长率'); return }
    if (discountRate <= growthRate) { alert('折现率必须大于增长率'); return }

    setLoading(true)
    try {
      const endpoint = mode === 'gordon' ? '/value-investing/ddm' : '/value-investing/ddm-two-stage'
      const body = mode === 'gordon'
        ? { dps, dividend_growth_rate: growthRate, discount_rate: discountRate, current_price: currentPrice }
        : { dps, high_growth_rate: parseFloat(form.highGrowthRate) / 100, high_growth_years: parseInt(form.highGrowthYears), stable_growth_rate: parseFloat(form.stableGrowthRate) / 100, discount_rate: discountRate, current_price: currentPrice }

      const [res, sensRes] = await Promise.all([
        fetch(`/api${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json()),
        fetch('/api/value-investing/ddm-sensitivity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dps, dividend_growth_rate: growthRate, discount_rate: discountRate, current_price: currentPrice }) }).then(r => r.json()),
      ])
      setResult(res)
      setSensitivity(sensRes)
    } catch (e: any) {
      alert('计算失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', background: '#0d1117', border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3', fontSize: 14 }
  const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 4, color: '#8b949e', fontSize: 13 }

  return (
    <div style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button onClick={() => setMode('gordon')} style={{ padding: '6px 16px', borderRadius: 6, cursor: 'pointer', background: mode === 'gordon' ? '#58a6ff' : '#161b22', border: `1px solid ${mode === 'gordon' ? '#58a6ff' : '#30363d'}`, color: mode === 'gordon' ? '#fff' : '#8b949e' }}>Gordon DDM</button>
        <button onClick={() => setMode('twostage')} style={{ padding: '6px 16px', borderRadius: 6, cursor: 'pointer', background: mode === 'twostage' ? '#58a6ff' : '#161b22', border: `1px solid ${mode === 'twostage' ? '#58a6ff' : '#30363d'}`, color: mode === 'twostage' ? '#fff' : '#8b949e' }}>两阶段DDM</button>
      </div>

      <div style={{ display: 'flex', gap: 20 }}>
        <div style={{ minWidth: 300, padding: 20, background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
          <div style={{ display: 'grid', gap: 12 }}>
            <div><label style={labelStyle}>每股股息 (元)</label><input style={inputStyle} type="number" step="0.01" value={form.dps} onChange={e => setForm({ ...form, dps: e.target.value })} placeholder="2.00" /></div>
            {mode === 'gordon' ? (
              <div><label style={labelStyle}>股息增长率 (%)</label><input style={inputStyle} type="number" step="0.1" value={form.growthRate} onChange={e => setForm({ ...form, growthRate: e.target.value })} placeholder="5" /></div>
            ) : (
              <>
                <div><label style={labelStyle}>高增长率 (%)</label><input style={inputStyle} type="number" step="0.1" value={form.highGrowthRate} onChange={e => setForm({ ...form, highGrowthRate: e.target.value })} placeholder="10" /></div>
                <div><label style={labelStyle}>高增长年数</label><input style={inputStyle} type="number" value={form.highGrowthYears} onChange={e => setForm({ ...form, highGrowthYears: e.target.value })} placeholder="5" /></div>
                <div><label style={labelStyle}>永续增长率 (%)</label><input style={inputStyle} type="number" step="0.1" value={form.stableGrowthRate} onChange={e => setForm({ ...form, stableGrowthRate: e.target.value })} placeholder="3" /></div>
              </>
            )}
            <div><label style={labelStyle}>折现率 (%)</label><input style={inputStyle} type="number" step="0.1" value={form.discountRate} onChange={e => setForm({ ...form, discountRate: e.target.value })} placeholder="10" /></div>
            <div><label style={labelStyle}>当前股价 (元)</label><input style={inputStyle} type="number" step="0.01" value={form.currentPrice} onChange={e => setForm({ ...form, currentPrice: e.target.value })} placeholder="50" /></div>
            <button onClick={handleCalc} disabled={loading} style={{ padding: '10px 0', borderRadius: 6, cursor: 'pointer', background: '#58a6ff', border: 'none', color: '#fff', fontWeight: 600, marginTop: 8 }}>{loading ? '计算中...' : '计算DDM估值'}</button>
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {!result && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400, color: '#8b949e' }}>输入参数后计算DDM内在价值（适用于银行/公用事业/高分红股）</div>}
          {result && !result.error && (
            <div>
              <StatCardGroup columns={4}>
                <StatCard label="内在价值" value={result.intrinsic_value?.toFixed(2) + '元'} color={result.intrinsic_value > (parseFloat(form.currentPrice) || 0) ? '#3fb950' : '#f85149'} />
                <StatCard label="买点价格" value={result.buy_price?.toFixed(2) + '元'} />
                <StatCard label="安全边际" value={result.safety_margin?.toFixed(1) + '%'} color={result.safety_margin > 0 ? '#3fb950' : '#f85149'} />
                <StatCard label="上行空间" value={result.upside?.toFixed(1) + '%'} color={result.upside > 0 ? '#3fb950' : '#f85149'} />
              </StatCardGroup>

              {/* 敏感性分析矩阵 */}
              {sensitivity && (
                <div style={{ marginTop: 16, background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>敏感性分析（股息增长率 × 折现率）</div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr>
                        <th style={{ padding: '6px 8px', color: '#8b949e', textAlign: 'left' }}>增长率↓ / 折现率→</th>
                        {sensitivity.discount_rates?.map((d: string) => <th key={d} style={{ padding: '6px 8px', color: '#8b949e' }}>{d}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {sensitivity.matrix?.map((row: (number|null)[], i: number) => (
                        <tr key={i}>
                          <td style={{ padding: '6px 8px', color: '#8b949e' }}>{sensitivity.growth_rates?.[i]}</td>
                          {row.map((val: number|null, j: number) => {
                            const currentP = parseFloat(form.currentPrice) || 0
                            const bgColor = val && currentP ? (val > currentP ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)') : 'transparent'
                            return <td key={j} style={{ padding: '6px 8px', textAlign: 'center', background: bgColor, color: val ? '#e6edf3' : '#484f58' }}>{val?.toFixed(1) || '-'}</td>
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


// ============ 蒙特卡洛 DCF ============

function MonteCarloDCF() {
  const [form, setForm] = useState({ fcf: '', shares: '', netDebt: '', currentPrice: '', growthMean: '10', growthStd: '5', discountMean: '10', discountStd: '2', terminalMean: '3', terminalStd: '1' })
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleCalc = async () => {
    const fcf = parseFloat(form.fcf)
    const shares = parseFloat(form.shares)
    if (!fcf || !shares) { alert('请输入FCF和总股本'); return }

    setLoading(true)
    try {
      const body = {
        current_fcf: fcf, shares, net_debt: parseFloat(form.netDebt) || 0, current_price: parseFloat(form.currentPrice) || 0,
        growth_mean: parseFloat(form.growthMean) / 100, growth_std: parseFloat(form.growthStd) / 100,
        discount_mean: parseFloat(form.discountMean) / 100, discount_std: parseFloat(form.discountStd) / 100,
        terminal_mean: parseFloat(form.terminalMean) / 100, terminal_std: parseFloat(form.terminalStd) / 100,
        n_simulations: 1000,
      }
      const res = await fetch('/api/value-investing/monte-carlo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json())
      setResult(res)
    } catch (e: any) {
      alert('计算失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  // 分布直方图
  const getHistogramOption = () => {
    if (!result?.histogram) return {}
    const h = result.histogram
    const currentPrice = parseFloat(form.currentPrice) || 0
    return {
      tooltip: { trigger: 'axis', backgroundColor: '#1c2333', borderColor: '#30363d', textStyle: { color: '#e6edf3' } },
      grid: { top: 30, right: 20, bottom: 40, left: 50 },
      xAxis: { type: 'category', data: h.map((b: any) => b.mid.toFixed(0)), axisLabel: { color: '#8b949e', fontSize: 10, rotate: 45 }, axisLine: { lineStyle: { color: '#30363d' } } },
      yAxis: { type: 'value', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [{
        type: 'bar', data: h.map((b: any) => ({
          value: b.count,
          itemStyle: { color: currentPrice > 0 && b.mid > currentPrice ? '#3fb950' : '#ef4444', borderRadius: [2, 2, 0, 0] },
        })),
        barWidth: '90%',
      }],
      markLine: currentPrice > 0 ? {
        data: [{ xAxis: h.findIndex((b: any) => b.mid >= currentPrice), label: { formatter: '当前价格', color: '#f59e0b' }, lineStyle: { color: '#f59e0b', type: 'dashed' } }],
      } : undefined,
    }
  }

  const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', background: '#0d1117', border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3', fontSize: 14 }
  const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 4, color: '#8b949e', fontSize: 13 }

  return (
    <div style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', gap: 20 }}>
        <div style={{ minWidth: 280, padding: 20, background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>基础参数</div>
          <div style={{ display: 'grid', gap: 10 }}>
            <div><label style={labelStyle}>FCF (亿元)</label><input style={inputStyle} type="number" value={form.fcf} onChange={e => setForm({ ...form, fcf: e.target.value })} placeholder="10" /></div>
            <div><label style={labelStyle}>总股本 (亿股)</label><input style={inputStyle} type="number" value={form.shares} onChange={e => setForm({ ...form, shares: e.target.value })} placeholder="10" /></div>
            <div><label style={labelStyle}>净负债 (亿元)</label><input style={inputStyle} type="number" value={form.netDebt} onChange={e => setForm({ ...form, netDebt: e.target.value })} placeholder="0" /></div>
            <div><label style={labelStyle}>当前股价 (元)</label><input style={inputStyle} type="number" value={form.currentPrice} onChange={e => setForm({ ...form, currentPrice: e.target.value })} placeholder="50" /></div>
          </div>
          <div style={{ fontWeight: 600, marginTop: 16, marginBottom: 12 }}>概率分布参数</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div><label style={labelStyle}>增长率均值%</label><input style={inputStyle} type="number" value={form.growthMean} onChange={e => setForm({ ...form, growthMean: e.target.value })} /></div>
            <div><label style={labelStyle}>增长率标准差%</label><input style={inputStyle} type="number" value={form.growthStd} onChange={e => setForm({ ...form, growthStd: e.target.value })} /></div>
            <div><label style={labelStyle}>折现率均值%</label><input style={inputStyle} type="number" value={form.discountMean} onChange={e => setForm({ ...form, discountMean: e.target.value })} /></div>
            <div><label style={labelStyle}>折现率标准差%</label><input style={inputStyle} type="number" value={form.discountStd} onChange={e => setForm({ ...form, discountStd: e.target.value })} /></div>
            <div><label style={labelStyle}>永续增长率均值%</label><input style={inputStyle} type="number" value={form.terminalMean} onChange={e => setForm({ ...form, terminalMean: e.target.value })} /></div>
            <div><label style={labelStyle}>永续增长率标准差%</label><input style={inputStyle} type="number" value={form.terminalStd} onChange={e => setForm({ ...form, terminalStd: e.target.value })} /></div>
          </div>
          <button onClick={handleCalc} disabled={loading} style={{ width: '100%', padding: '10px 0', borderRadius: 6, cursor: 'pointer', background: '#58a6ff', border: 'none', color: '#fff', fontWeight: 600, marginTop: 12 }}>{loading ? '模拟中...' : '运行1000次蒙特卡洛模拟'}</button>
        </div>

        <div style={{ flex: 1 }}>
          {!result && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500, color: '#8b949e' }}>输入参数运行蒙特卡洛模拟，得到内在价值的概率分布</div>}
          {result && !result.error && (
            <div>
              <StatCardGroup columns={5}>
                <StatCard label="中位数估值" value={result.statistics?.median?.toFixed(2) + '元'} color="#58a6ff" />
                <StatCard label="P25-P75区间" value={`${result.statistics?.p25?.toFixed(0)}-${result.statistics?.p95?.toFixed(0)}元`} />
                <StatCard label="超越当前价概率" value={result.probabilities?.above_current_price?.toFixed(1) + '%'} color={result.probabilities?.above_current_price > 50 ? '#3fb950' : '#f85149'} />
                <StatCard label="买点价格" value={result.buy_price?.toFixed(2) + '元'} />
                <StatCard label="模拟次数" value={result.n_simulations} />
              </StatCardGroup>

              <div style={{ marginTop: 16 }}>
                <ReactECharts option={getHistogramOption()} style={{ height: 300 }} />
              </div>

              <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>价值分布</div>
                  {['p5', 'p10', 'p25', 'p50', 'p75', 'p90', 'p95'].map(p => (
                    <div key={p} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #21262d' }}>
                      <span style={{ color: '#8b949e' }}>{p.toUpperCase()}</span>
                      <span>{result.statistics?.[p]?.toFixed(2)}元</span>
                    </div>
                  ))}
                </div>
                <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>概率分析</div>
                  <div style={{ padding: '4px 0', borderBottom: '1px solid #21262d' }}><span style={{ color: '#8b949e' }}>正值概率 </span><span style={{ color: '#3fb950' }}>{result.probabilities?.positive_value}%</span></div>
                  {result.probabilities?.above_current_price != null && <div style={{ padding: '4px 0', borderBottom: '1px solid #21262d' }}><span style={{ color: '#8b949e' }}>超越当前价 </span><span style={{ color: result.probabilities.above_current_price > 50 ? '#3fb950' : '#f85149' }}>{result.probabilities.above_current_price}%</span></div>}
                  <div style={{ padding: '4px 0', borderBottom: '1px solid #21262d' }}><span style={{ color: '#8b949e' }}>均值 </span><span>{result.statistics?.mean?.toFixed(2)}元</span></div>
                  <div style={{ padding: '4px 0' }}><span style={{ color: '#8b949e' }}>标准差 </span><span>{result.statistics?.std?.toFixed(2)}元</span></div>
                </div>
              </div>
            </div>
          )}
          {result?.error && <div style={{ color: '#f85149', padding: 20 }}>{result.error}</div>}
        </div>
      </div>
    </div>
  )
}
