import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { PageSection, TabBar, DataTable, LoadingSpinner } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

interface CigarButtStock {
  code: string
  name: string
  price: number
  change_pct: number | null
  pe: number | null
  pb: number | null
  roe: number | null
  market_cap: number | null
  dividend_yield?: number | null
  ncav_per_share: number | null
  ncav_discount: number | null
  liquidation_per_share: number | null
  liquidation_discount: number | null
  graham_number: number | null
  f_score: number
  composite_score: number
  criteria_met: string[]
  quality_pass: boolean
  quality_issues: string[]
  eps?: number | null
  bps?: number | null
  gross_margin?: number | null
  net_margin?: number | null
  debt_ratio?: number | null
  report_date?: string
}

interface StockDetail {
  code: string
  name: string
  price: number
  pe: number | null
  pb: number | null
  report_date: string
  ncav: {
    total: number | null
    per_share: number | null
    discount_pct: number | null
    graham_rule: boolean
  }
  liquidation: {
    total: number | null
    per_share: number | null
    discount_pct: number | null
    breakdown: Record<string, number> | null
  }
  graham_number: number | null
  f_score: {
    total: number
    details: Record<string, boolean | null>
    grade: string
  }
  roe: number | null
  eps: number | null
  bps: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
  asset_structure: {
    current_assets_pct: number | null
    cash_pct: number | null
    receivables_pct: number | null
    inventory_pct: number | null
    fixed_assets_pct: number | null
  }
  current_ratio: number | null
  quick_ratio: number | null
  composite_score: number
  quality_pass: boolean
  quality_issues: string[]
}

interface Philosophy {
  graham: {
    name: string; title: string; core_idea: string; criteria: string[]
    ncav_explanation: string; liquidation_explanation: string
    graham_number: string; classic_quote: string
  }
  schloss: {
    name: string; title: string; core_idea: string; criteria: string[]
    performance: string; classic_quote: string
  }
  f_score_explanation: {
    name: string; description: string
    categories: { name: string; items: string[] }[]
    interpretation: string
  }
  risks: string[]
}

interface BacktestResult {
  backtest: {
    start_date: string; end_date: string; rebalance: string
    max_pb: number; top_n: number
    total_return_pct: number; annualized_return_pct: number
    benchmark_return_pct: number; excess_return_pct: number
    num_rebalances: number; stocks_in_pool: number
  }
  selected_stocks: { code: string; name: string; pb: number; pe: number }[]
  update_time: string
}

export default function CigarButtScreener() {
  const [activeTab, setActiveTab] = useState<'screener' | 'philosophy' | 'backtest'>('philosophy')
  const [stocks, setStocks] = useState<CigarButtStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)
  const [elapsed, setElapsed] = useState(0)

  // 筛选参数
  const [market, setMarket] = useState<'A' | 'HK'>('A')
  const [maxPB, setMaxPB] = useState(1.0)
  const [maxPE, setMaxPE] = useState(15)
  const [minFScore, setMinFScore] = useState(0)
  const [minMarketCap, setMinMarketCap] = useState(10)
  const [topN, setTopN] = useState(50)
  const [includeQualityFail, setIncludeQualityFail] = useState(false)

  // 投资哲学
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)

  // 详情弹窗
  const [detailStock, setDetailStock] = useState<StockDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 回测
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [btMaxPB, setBtMaxPB] = useState(0.8)
  const [btTopN, setBtTopN] = useState(10)
  const [btRebalance, setBtRebalance] = useState('quarterly')

  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/screener`, {
        params: {
          market,
          max_pb: maxPB,
          max_pe: maxPE,
          min_f_score: minFScore,
          min_market_cap: minMarketCap,
          include_quality_fail: includeQualityFail,
          top_n: topN,
        }
      })
      setStocks(res.data.stocks || [])
      setUpdateTime(res.data.update_time || '')
      setTotal(res.data.total || 0)
      setElapsed(res.data.elapsed_seconds || 0)
    } catch (e) {
      console.error('获取烟蒂股数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [market, maxPB, maxPE, minFScore, minMarketCap, includeQualityFail, topN])

  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取投资哲学失败:', e)
    }
  }, [])

  const loadDetail = useCallback(async (code: string) => {
    setDetailLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/detail/${code}`)
      setDetailStock(res.data)
    } catch (e) {
      console.error('获取详情失败:', e)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const runBacktest = useCallback(async () => {
    setBacktestLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/backtest`, {
        params: {
          market: 'A',
          max_pb: btMaxPB,
          top_n: btTopN,
          rebalance: btRebalance,
          start_date: '2020-01-01',
          end_date: '2025-12-31',
        }
      })
      setBacktestResult(res.data)
    } catch (e) {
      console.error('回测失败:', e)
    } finally {
      setBacktestLoading(false)
    }
  }, [btMaxPB, btTopN, btRebalance])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])

  const getScoreColor = (score: number) => {
    if (score >= 70) return '#52c41a'
    if (score >= 50) return '#1890ff'
    if (score >= 30) return '#faad14'
    return '#ff4d4f'
  }

  const getFScoreColor = (score: number) => {
    if (score >= 7) return '#52c41a'
    if (score >= 5) return '#1890ff'
    if (score >= 3) return '#faad14'
    return '#ff4d4f'
  }

  const getDiscountColor = (discount: number | null) => {
    if (discount === null || discount === undefined) return '#666'
    if (discount <= -50) return '#52c41a'
    if (discount <= -33) return '#1890ff'
    if (discount <= 0) return '#faad14'
    return '#ff4d4f'
  }

  const stockColumns: Column<CigarButtStock>[] = [
    { key: 'rank', title: '#', render: (_v, _r, i) => i + 1, align: 'center', width: 45 },
    {
      key: 'code', title: '代码', dataIndex: 'code', width: 75,
      render: (v, record) => (
        <span
          style={{ fontWeight: 600, color: '#58a6ff', cursor: 'pointer', textDecoration: 'underline' }}
          onClick={() => loadDetail(v)}
        >
          {v}
        </span>
      ),
    },
    { key: 'name', title: '名称', dataIndex: 'name', width: 90 },
    {
      key: 'price', title: '现价', dataIndex: 'price', align: 'right',
      render: v => v?.toFixed(2) ?? '--',
    },
    {
      key: 'ncav_discount', title: 'NCAV折价', dataIndex: 'ncav_discount', align: 'right',
      render: v => (
        <span style={{ color: getDiscountColor(v), fontWeight: 700 }}>
          {v !== null && v !== undefined ? `${v.toFixed(1)}%` : '--'}
        </span>
      ),
    },
    {
      key: 'ncav_per_share', title: 'NCAV/股', dataIndex: 'ncav_per_share', align: 'right',
      render: v => v != null ? v.toFixed(2) : '--',
    },
    {
      key: 'liquidation_per_share', title: '清算/股', dataIndex: 'liquidation_per_share', align: 'right',
      render: v => v != null ? v.toFixed(2) : '--',
    },
    {
      key: 'graham_number', title: 'Graham#', dataIndex: 'graham_number', align: 'right',
      render: (v, record) => {
        if (!v) return '--'
        const isBelow = record.price < v
        return (
          <span style={{ color: isBelow ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
            {v.toFixed(2)}
          </span>
        )
      },
    },
    {
      key: 'f_score', title: 'F-Score', dataIndex: 'f_score', align: 'center',
      render: v => (
        <span style={{ color: getFScoreColor(v), fontWeight: 700, fontSize: '14px' }}>
          {v}/9
        </span>
      ),
    },
    {
      key: 'pe', title: 'PE', dataIndex: 'pe', align: 'right',
      render: v => v != null ? v.toFixed(1) : '--',
    },
    {
      key: 'pb', title: 'PB', dataIndex: 'pb', align: 'right',
      render: v => (
        <span style={{ color: (v ?? 999) <= 0.7 ? '#52c41a' : (v ?? 999) <= 1.0 ? '#1890ff' : '#faad14', fontWeight: 600 }}>
          {v?.toFixed(2) ?? '--'}
        </span>
      ),
    },
    {
      key: 'market_cap', title: '市值(亿)', dataIndex: 'market_cap', align: 'right',
      render: v => v != null ? v.toFixed(0) : '--',
    },
    {
      key: 'composite_score', title: '综合分', dataIndex: 'composite_score', align: 'center',
      render: v => (
        <span style={{ color: getScoreColor(v), fontWeight: 700, fontSize: '14px' }}>
          {v.toFixed(0)}
        </span>
      ),
    },
    {
      key: 'quality_pass', title: '质量', dataIndex: 'quality_pass', align: 'center', width: 50,
      render: (v, record) => (
        <span
          title={!v ? record.quality_issues?.join('; ') : '质量过滤通过'}
          style={{
            color: v ? '#52c41a' : '#ff4d4f',
            fontSize: '16px',
            cursor: v ? 'default' : 'help',
          }}
        >
          {v ? '✓' : '✗'}
        </span>
      ),
    },
    {
      key: 'criteria_met', title: '符合标准', dataIndex: 'criteria_met',
      render: (v: string[]) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
          {v?.slice(0, 3).map((criteria, idx) => (
            <span key={idx} style={{
              display: 'inline-block', padding: '1px 5px', borderRadius: '3px',
              fontSize: '10px',
              background: criteria.includes('NCAV') ? 'rgba(82,196,26,0.15)' : 'rgba(88,166,255,0.15)',
              color: criteria.includes('NCAV') ? '#52c41a' : '#58a6ff',
            }}>
              {criteria}
            </span>
          ))}
          {v && v.length > 3 && <span style={{ fontSize: '10px', color: '#666' }}>+{v.length - 3}</span>}
        </div>
      ),
    },
  ]

  // F-Score 详情面板
  const renderFScoreDetails = (details: Record<string, boolean | null>) => {
    const items = [
      { key: 'roa_positive', label: 'ROA > 0', cat: '盈利能力' },
      { key: 'ocf_positive', label: '经营现金流 > 0', cat: '盈利能力' },
      { key: 'roa_improving', label: 'ROA 同比增长', cat: '盈利能力' },
      { key: 'accrual_quality', label: '现金流 > 净利润', cat: '盈利能力' },
      { key: 'leverage_decreasing', label: '长期负债率下降', cat: '杠杆/流动性' },
      { key: 'liquidity_improving', label: '流动比率上升', cat: '杠杆/流动性' },
      { key: 'no_dilution', label: '未发行新股', cat: '杠杆/流动性' },
      { key: 'gross_margin_improving', label: '毛利率上升', cat: '运营效率' },
      { key: 'asset_turnover_improving', label: '资产周转率上升', cat: '运营效率' },
    ]
    return items.map(item => ({
      ...item,
      value: details[item.key],
    }))
  }

  return (
    <div className="cb-page">
      {/* 页面标题 */}
      <PageSection title="格雷厄姆烟蒂股筛选器" compact>
        <span className="stock-code">
          NCAV / 清算价值 / Graham Number / Piotroski F-Score 机构级筛选
        </span>
      </PageSection>

      {/* Tab切换 */}
      <TabBar
        tabs={[
          { key: 'philosophy', label: '投资哲学' },
          { key: 'screener', label: '烟蒂筛选' },
          { key: 'backtest', label: '策略回测' },
        ]}
        activeKey={activeTab}
        onChange={key => setActiveTab(key as typeof activeTab)}
      />

      {/* ========= 投资哲学 ========= */}
      {activeTab === 'philosophy' && philosophy && (
        <div style={{ padding: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
            {/* 格雷厄姆 */}
            <PageSection title={philosophy.graham.name} style={{ margin: 0, borderLeft: '3px solid #58a6ff' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                {philosophy.graham.title}
              </div>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心思想</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{philosophy.graham.core_idea}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    {philosophy.graham.criteria.map((c, i) => (
                      <li key={i} style={{ fontSize: '13px' }}>{c}</li>
                    ))}
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>NCAV 定义</h4>
                  <p style={{ fontSize: '13px', color: '#58a6ff', fontWeight: 600 }}>{philosophy.graham.ncav_explanation}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>清算价值</h4>
                  <p style={{ fontSize: '13px', color: '#58a6ff' }}>{philosophy.graham.liquidation_explanation}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>Graham Number</h4>
                  <p style={{ fontSize: '13px', color: '#58a6ff' }}>{philosophy.graham.graham_number}</p>
                </div>
                <div style={{ marginTop: '12px', padding: '8px', background: 'rgba(88,166,255,0.1)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    "{philosophy.graham.classic_quote}"
                  </div>
                </div>
              </div>
            </PageSection>

            {/* 施洛斯 */}
            <PageSection title={philosophy.schloss.name} style={{ margin: 0, borderLeft: '3px solid #d29922' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                {philosophy.schloss.title}
              </div>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心思想</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{philosophy.schloss.core_idea}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    {philosophy.schloss.criteria.map((c, i) => (
                      <li key={i} style={{ fontSize: '13px' }}>{c}</li>
                    ))}
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>历史业绩</h4>
                  <p style={{ fontSize: '13px', color: '#d29922', fontWeight: 600 }}>{philosophy.schloss.performance}</p>
                </div>
                <div style={{ marginTop: '12px', padding: '8px', background: 'rgba(210,153,34,0.1)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    "{philosophy.schloss.classic_quote}"
                  </div>
                </div>
              </div>
            </PageSection>
          </div>

          {/* Piotroski F-Score */}
          <PageSection title={philosophy.f_score_explanation.name} style={{ marginBottom: '20px', borderLeft: '3px solid #3fb950' }}>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              {philosophy.f_score_explanation.description}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
              {philosophy.f_score_explanation.categories.map((cat, i) => (
                <div key={i}>
                  <h4 style={{ fontSize: '13px', marginBottom: '8px', color: '#3fb950' }}>{cat.name}</h4>
                  <ul style={{ margin: 0, paddingLeft: '16px' }}>
                    {cat.items.map((item, j) => (
                      <li key={j} style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '12px' }}>
              {philosophy.f_score_explanation.interpretation}
            </p>
          </PageSection>

          {/* 风险提示 */}
          <PageSection title="烟蒂投资风险提示" style={{ margin: 0, borderLeft: '3px solid #f85149' }}>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <h4>主要风险</h4>
                <ul>
                  {philosophy.risks.map((risk, i) => (
                    <li key={i} style={{ fontSize: '13px' }}>{risk}</li>
                  ))}
                </ul>
              </div>
            </div>
          </PageSection>
        </div>
      )}

      {/* ========= 筛选页面 ========= */}
      {activeTab === 'screener' && (
        <div style={{ padding: '16px 20px' }}>
          {/* 筛选条件 */}
          <div style={{ marginBottom: '16px', padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-primary)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>市场</label>
                <select value={market} onChange={e => setMarket(e.target.value as 'A' | 'HK')} style={{ width: '100%' }}>
                  <option value="A">A股（完整NCAV计算）</option>
                  <option value="HK">港股（PB/PE筛选）</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最大PB</label>
                <select value={maxPB} onChange={e => setMaxPB(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={0.5}>0.5（深度折价）</option>
                  <option value={0.7}>0.7</option>
                  <option value={0.8}>0.8</option>
                  <option value={1.0}>1.0（净资产价）</option>
                  <option value={1.2}>1.2</option>
                  <option value={1.5}>1.5</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最大PE</label>
                <select value={maxPE} onChange={e => setMaxPE(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={5}>5</option>
                  <option value={8}>8</option>
                  <option value={10}>10（大师标准）</option>
                  <option value={15}>15</option>
                  <option value={20}>20</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低F-Score</label>
                <select value={minFScore} onChange={e => setMinFScore(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={0}>不限</option>
                  <option value={3}>3分以上</option>
                  <option value={5}>5分以上（良好）</option>
                  <option value={7}>7分以上（优秀）</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', alignItems: 'end' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低市值(亿)</label>
                <select value={minMarketCap} onChange={e => setMinMarketCap(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={5}>5亿</option>
                  <option value={10}>10亿</option>
                  <option value={20}>20亿</option>
                  <option value={50}>50亿</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>显示数量</label>
                <select value={topN} onChange={e => setTopN(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={30}>前30只</option>
                  <option value={50}>前50只</option>
                  <option value={100}>前100只</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)' }}>
                  <input
                    type="checkbox"
                    checked={includeQualityFail}
                    onChange={e => setIncludeQualityFail(e.target.checked)}
                  />
                  含质量未通过
                </label>
              </div>
              <div>
                <button
                  onClick={loadStocks}
                  disabled={loading}
                  style={{
                    padding: '8px 20px', background: 'var(--accent-blue)', color: '#fff',
                    border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
                    width: '100%', opacity: loading ? 0.6 : 1,
                  }}
                >
                  {loading ? '筛选中...' : '开始筛选'}
                </button>
              </div>
            </div>
          </div>

          {/* 大师标准说明 */}
          <PageSection title="格雷厄姆烟蒂选股标准" compact style={{ marginBottom: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '12px', fontSize: '13px' }}>
              <div>
                <strong>NCAV规则：</strong>价格 &lt; NCAV * 2/3
              </div>
              <div>
                <strong>Graham#：</strong>价格 &lt; sqrt(22.5*EPS*BPS)
              </div>
              <div>
                <strong>施洛斯：</strong>PB &lt; 1, 负债少, 持续盈利
              </div>
              <div>
                <strong>F-Score：</strong>&ge; 7 优秀, &ge; 5 良好
              </div>
            </div>
          </PageSection>

          {/* 数据信息 */}
          <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <span className="freshness-tag">更新: {updateTime}</span>
            <span className="freshness-tag">符合条件: {total} 只</span>
            {elapsed > 0 && <span className="freshness-tag">耗时: {elapsed}s</span>}
            <span className="freshness-tag">PB&le;{maxPB} | PE&le;{maxPE} | F-Score&ge;{minFScore} | 市值&ge;{minMarketCap}亿</span>
          </div>

          {/* 筛选结果 */}
          {loading ? (
            <LoadingSpinner text="正在获取财务数据、计算NCAV和F-Score（可能需要1-2分钟）..." />
          ) : (
            <DataTable<CigarButtStock>
              columns={stockColumns}
              data={stocks}
              rowKey="code"
              emptyText="暂无符合条件的烟蒂股。尝试放宽PB或PE阈值。"
              striped
            />
          )}

          {/* 筛选逻辑说明 */}
          <PageSection title="筛选逻辑说明" style={{ marginTop: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心估值指标</h4>
                  <ul>
                    <li><strong>NCAV（净流动资产价值）</strong>= 流动资产 - 全部负债。格雷厄姆要求价格 &lt; NCAV * 2/3</li>
                    <li><strong>清算价值</strong> = 现金 + 0.75*应收 + 0.5*存货 + 0.7*固定资产 - 全部负债。比NCAV更保守</li>
                    <li><strong>Graham Number</strong> = sqrt(22.5 * EPS * BPS)。合理价格上限</li>
                    <li><strong>NCAV折价率</strong> = (价格-NCAV)/NCAV。负数表示折价，越大越好</li>
                  </ul>
                </div>
              </div>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>质量评分（Piotroski F-Score）</h4>
                  <ul>
                    <li><strong>盈利能力(4分)</strong>：ROA{'>'}0、经营现金流{'>'}0、ROA增长、现金流{'>'}净利润</li>
                    <li><strong>杠杆流动性(3分)</strong>：负债率下降、流动比率上升、未增发</li>
                    <li><strong>运营效率(2分)</strong>：毛利率上升、资产周转率上升</li>
                    <li><strong>综合评分</strong>：NCAV折价30% + 清算折价20% + F-Score 25% + PE 15% + PB 10%</li>
                  </ul>
                </div>
              </div>
            </div>
          </PageSection>
        </div>
      )}

      {/* ========= 策略回测 ========= */}
      {activeTab === 'backtest' && (
        <div style={{ padding: '16px 20px' }}>
          <div style={{ marginBottom: '16px', padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-primary)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', alignItems: 'end' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最大PB</label>
                <select value={btMaxPB} onChange={e => setBtMaxPB(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={0.5}>0.5</option>
                  <option value={0.7}>0.7</option>
                  <option value={0.8}>0.8</option>
                  <option value={1.0}>1.0</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>持仓数</label>
                <select value={btTopN} onChange={e => setBtTopN(Number(e.target.value))} style={{ width: '100%' }}>
                  <option value={5}>5只</option>
                  <option value={10}>10只</option>
                  <option value={20}>20只</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>调仓频率</label>
                <select value={btRebalance} onChange={e => setBtRebalance(e.target.value)} style={{ width: '100%' }}>
                  <option value="monthly">月度</option>
                  <option value="quarterly">季度</option>
                  <option value="annual">年度</option>
                </select>
              </div>
              <div>
                <button
                  onClick={runBacktest}
                  disabled={backtestLoading}
                  style={{
                    padding: '8px 20px', background: 'var(--accent-blue)', color: '#fff',
                    border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
                    width: '100%', opacity: backtestLoading ? 0.6 : 1,
                  }}
                >
                  {backtestLoading ? '回测中...' : '运行回测'}
                </button>
              </div>
            </div>
          </div>

          {backtestLoading && <LoadingSpinner text="正在获取历史数据并计算回测收益..." />}

          {backtestResult && (
            <div>
              <PageSection title="回测结果 (2020-01-01 至 2025-12-31)" style={{ marginBottom: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '16px' }}>
                  <div style={{ padding: '16px', background: 'rgba(82,196,26,0.1)', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>策略总收益</div>
                    <div style={{ fontSize: '24px', fontWeight: 700, color: backtestResult.backtest.total_return_pct >= 0 ? '#52c41a' : '#ff4d4f' }}>
                      {backtestResult.backtest.total_return_pct.toFixed(1)}%
                    </div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(88,166,255,0.1)', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>年化收益</div>
                    <div style={{ fontSize: '24px', fontWeight: 700, color: backtestResult.backtest.annualized_return_pct >= 0 ? '#58a6ff' : '#ff4d4f' }}>
                      {backtestResult.backtest.annualized_return_pct.toFixed(1)}%
                    </div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(210,153,34,0.1)', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>基准收益(沪深300)</div>
                    <div style={{ fontSize: '24px', fontWeight: 700, color: backtestResult.backtest.benchmark_return_pct >= 0 ? '#d29922' : '#ff4d4f' }}>
                      {backtestResult.backtest.benchmark_return_pct.toFixed(1)}%
                    </div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(248,81,73,0.1)', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>超额收益</div>
                    <div style={{ fontSize: '24px', fontWeight: 700, color: backtestResult.backtest.excess_return_pct >= 0 ? '#52c41a' : '#ff4d4f' }}>
                      {backtestResult.backtest.excess_return_pct >= 0 ? '+' : ''}{backtestResult.backtest.excess_return_pct.toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  参数: PB &le; {backtestResult.backtest.max_pb} | 持仓 {backtestResult.backtest.top_n} 只 |
                  调仓 {backtestResult.backtest.rebalance} | 调仓 {backtestResult.backtest.num_rebalances} 次 |
                  股票池 {backtestResult.backtest.stocks_in_pool} 只
                </div>
              </PageSection>

              {/* 当前选股池 */}
              <PageSection title="当前低PB选股池" style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {backtestResult.selected_stocks.map(s => (
                    <span key={s.code} style={{
                      padding: '4px 10px', borderRadius: '4px', fontSize: '12px',
                      background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
                    }}>
                      {s.code} {s.name} PB:{s.pb?.toFixed(2)} PE:{s.pe?.toFixed(1)}
                    </span>
                  ))}
                </div>
              </PageSection>

              {/* 回测说明 */}
              <PageSection title="回测方法论">
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  <ul>
                    <li>策略: 每个调仓日选取 PB 最低且 PE &lt; 15 的股票，等权持有</li>
                    <li>基准: 沪深300指数（sh000300）</li>
                    <li>使用前复权数据，考虑分红再投资</li>
                    <li>注意: 实际交易需考虑交易成本（佣金约0.03%、印花税0.1%）、冲击成本</li>
                    <li>本回测基于当前低PB股票池的历史表现，存在幸存者偏差</li>
                  </ul>
                </div>
              </PageSection>
            </div>
          )}
        </div>
      )}

      {/* ========= 股票详情弹窗 ========= */}
      {detailStock && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '20px',
        }} onClick={() => setDetailStock(null)}>
          <div style={{
            background: 'var(--bg-primary)', borderRadius: '12px', padding: '24px',
            maxWidth: '900px', width: '100%', maxHeight: '85vh', overflow: 'auto',
          }} onClick={e => e.stopPropagation()}>
            {detailLoading ? <LoadingSpinner text="加载详情..." /> : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h2 style={{ margin: 0 }}>
                    {detailStock.code} {detailStock.name}
                    <span style={{ fontSize: '14px', color: 'var(--text-muted)', marginLeft: '12px' }}>
                      价格: {detailStock.price?.toFixed(2)} | 报告期: {detailStock.report_date}
                    </span>
                  </h2>
                  <button onClick={() => setDetailStock(null)} style={{
                    background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: 'var(--text-muted)',
                  }}>X</button>
                </div>

                {/* 核心估值 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                  <div style={{ padding: '16px', background: detailStock.ncav.graham_rule ? 'rgba(82,196,26,0.1)' : 'rgba(248,81,73,0.1)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>NCAV/股</div>
                    <div style={{ fontSize: '20px', fontWeight: 700 }}>
                      {detailStock.ncav.per_share?.toFixed(2) ?? '--'}
                    </div>
                    <div style={{ fontSize: '12px', color: getDiscountColor(detailStock.ncav.discount_pct) }}>
                      折价: {detailStock.ncav.discount_pct?.toFixed(1) ?? '--'}%
                      {detailStock.ncav.graham_rule && ' (满足2/3规则)'}
                    </div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(88,166,255,0.1)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>清算价值/股</div>
                    <div style={{ fontSize: '20px', fontWeight: 700 }}>
                      {detailStock.liquidation.per_share?.toFixed(2) ?? '--'}
                    </div>
                    <div style={{ fontSize: '12px', color: getDiscountColor(detailStock.liquidation.discount_pct) }}>
                      折价: {detailStock.liquidation.discount_pct?.toFixed(1) ?? '--'}%
                    </div>
                  </div>
                  <div style={{ padding: '16px', background: 'rgba(210,153,34,0.1)', borderRadius: '8px' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Graham Number</div>
                    <div style={{ fontSize: '20px', fontWeight: 700 }}>
                      {detailStock.graham_number?.toFixed(2) ?? '--'}
                    </div>
                    <div style={{ fontSize: '12px', color: detailStock.graham_number && detailStock.price < detailStock.graham_number ? '#52c41a' : '#ff4d4f' }}>
                      {detailStock.graham_number && detailStock.price < detailStock.graham_number ? '低于上限' : '高于上限'}
                    </div>
                  </div>
                </div>

                {/* F-Score 和财务指标 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                  <PageSection title="Piotroski F-Score" compact>
                    <div style={{ textAlign: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '32px', fontWeight: 700, color: getFScoreColor(detailStock.f_score.total) }}>
                        {detailStock.f_score.total}
                      </span>
                      <span style={{ fontSize: '16px', color: 'var(--text-muted)' }}>/9</span>
                      <span style={{ marginLeft: '8px', fontSize: '14px', color: getFScoreColor(detailStock.f_score.total) }}>
                        ({detailStock.f_score.grade})
                      </span>
                    </div>
                    {renderFScoreDetails(detailStock.f_score.details).map(item => (
                      <div key={item.key} style={{
                        display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                        fontSize: '12px', borderBottom: '1px solid var(--border-primary)',
                      }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                        <span style={{
                          color: item.value === true ? '#52c41a' : item.value === false ? '#ff4d4f' : '#666',
                          fontWeight: 600,
                        }}>
                          {item.value === true ? '+1' : item.value === false ? '0' : 'N/A'}
                        </span>
                      </div>
                    ))}
                  </PageSection>

                  <PageSection title="财务指标" compact>
                    {[
                      { label: 'ROE', value: detailStock.roe, suffix: '%' },
                      { label: 'EPS', value: detailStock.eps, suffix: '' },
                      { label: 'BPS', value: detailStock.bps, suffix: '' },
                      { label: '毛利率', value: detailStock.gross_margin, suffix: '%' },
                      { label: '净利率', value: detailStock.net_margin, suffix: '%' },
                      { label: '资产负债率', value: detailStock.debt_ratio, suffix: '%' },
                      { label: '流动比率', value: detailStock.current_ratio, suffix: '' },
                      { label: '速动比率', value: detailStock.quick_ratio, suffix: '' },
                    ].map(item => (
                      <div key={item.label} style={{
                        display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                        fontSize: '13px', borderBottom: '1px solid var(--border-primary)',
                      }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                        <span style={{ fontWeight: 600 }}>
                          {item.value !== null && item.value !== undefined ? `${item.value.toFixed(2)}${item.suffix}` : '--'}
                        </span>
                      </div>
                    ))}
                  </PageSection>
                </div>

                {/* 资产结构 */}
                <PageSection title="资产结构" compact style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {[
                      { label: '流动资产', value: detailStock.asset_structure.current_assets_pct },
                      { label: '货币资金', value: detailStock.asset_structure.cash_pct },
                      { label: '应收款项', value: detailStock.asset_structure.receivables_pct },
                      { label: '存货', value: detailStock.asset_structure.inventory_pct },
                      { label: '固定资产', value: detailStock.asset_structure.fixed_assets_pct },
                    ].map(item => (
                      <span key={item.label} style={{
                        padding: '6px 12px', borderRadius: '4px', fontSize: '12px',
                        background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
                      }}>
                        {item.label}: {item.value?.toFixed(1) ?? '--'}%
                      </span>
                    ))}
                  </div>
                </PageSection>

                {/* 质量评估 */}
                {!detailStock.quality_pass && detailStock.quality_issues.length > 0 && (
                  <PageSection title="质量风险警告" style={{ borderLeft: '3px solid #ff4d4f' }}>
                    <ul style={{ margin: 0 }}>
                      {detailStock.quality_issues.map((issue, i) => (
                        <li key={i} style={{ fontSize: '13px', color: '#ff4d4f' }}>{issue}</li>
                      ))}
                    </ul>
                  </PageSection>
                )}

                {/* 清算价值明细 */}
                {detailStock.liquidation.breakdown && (
                  <PageSection title="清算价值计算明细" compact style={{ marginTop: '16px' }}>
                    <div style={{ fontSize: '13px' }}>
                      {Object.entries(detailStock.liquidation.breakdown).map(([key, val]) => {
                        const labels: Record<string, string> = {
                          cash: '货币资金 (100%)',
                          notes_receivable_discounted: '应收票据 (80%)',
                          accounts_receivable_discounted: '应收账款 (75%)',
                          other_receivables_discounted: '其他应收款 (50%)',
                          inventory_discounted: '存货 (50%)',
                          fixed_assets_discounted: '固定资产 (70%)',
                          total_liabilities: '减: 全部负债',
                        }
                        return (
                          <div key={key} style={{
                            display: 'flex', justifyContent: 'space-between', padding: '3px 0',
                            borderBottom: '1px solid var(--border-primary)',
                          }}>
                            <span style={{ color: 'var(--text-secondary)' }}>{labels[key] || key}</span>
                            <span style={{ fontWeight: key === 'total_liabilities' ? 600 : 400 }}>
                              {typeof val === 'number' ? (val / 1e8).toFixed(2) + '亿' : '--'}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </PageSection>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
