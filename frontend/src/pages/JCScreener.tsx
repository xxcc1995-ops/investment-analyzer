import { LoadingSpinner, PageSection, TabBar, StatCard, StatCardGroup, DataTable, EmptyState } from '../components/ui'
import type { Column } from '../components/ui'
import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface JCStock {
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
  jc_score: number
  jc_detail: string
  industry_position: string
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
}

interface FrameworkDimension {
  dimension: string
  description: string
  criteria: string[]
  key_insight: string
}

interface JCPhilosophy {
  name: string
  title: string
  era: string
  core_philosophy: string
  investment_framework: FrameworkDimension[]
  classic_quotes: string[]
  performance: {
    '2025_return': string
    top_holders: string
    target_2026: string
    note: string
  }
}

const getScoreColor = (score: number) => {
  if (score >= 80) return '#3fb950'
  if (score >= 65) return '#58a6ff'
  if (score >= 50) return '#d29922'
  return '#f85149'
}

const getMatchLevelText = (level: string) => {
  switch (level) {
    case 'excellent': return '优秀'
    case 'good': return '良好'
    case 'fair': return '一般'
    case 'poor': return '较差'
    default: return level
  }
}

const getMatchLevelColor = (level: string) => {
  switch (level) {
    case 'excellent': return '#3fb950'
    case 'good': return '#58a6ff'
    case 'fair': return '#d29922'
    case 'poor': return '#f85149'
    default: return '#8b949e'
  }
}

const getMarketTag = (market: string) => {
  switch (market) {
    case 'A': return { text: 'A股', color: '#f85149' }
    case 'HK': return { text: '港股', color: '#d29922' }
    case 'US': return { text: '美股', color: '#58a6ff' }
    default: return { text: market, color: '#8b949e' }
  }
}

export default function JCScreener() {
  const [activeTab, setActiveTab] = useState<'philosophy' | 'screener' | 'signals'>('philosophy')
  const [stocks, setStocks] = useState<JCStock[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [updateTime, setUpdateTime] = useState('')
  const [elapsed, setElapsed] = useState<number | null>(null)
  const [total, setTotal] = useState(0)
  const [philosophy, setPhilosophy] = useState<JCPhilosophy | null>(null)
  const [philosophyLoading, setPhilosophyLoading] = useState(false)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

  // Race condition protection
  const screenerCounter = useRef(0)
  const signalCounter = useRef(0)

  // Screener params
  const [market, setMarket] = useState<'all' | 'A' | 'HK' | 'US'>('all')
  const [minScore, setMinScore] = useState(50)
  const [maxPE, setMaxPE] = useState<number | ''>('')
  const [maxPB, setMaxPB] = useState<number | ''>('')
  const [minROE, setMinROE] = useState<number | ''>('')
  const [minDividend, setMinDividend] = useState<number | ''>('')
  const [topN, setTopN] = useState(50)
  const [sortBy, setSortBy] = useState('jc_score')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // Buy signals
  const [signals, setSignals] = useState<JCStock[]>([])
  const [signalsLoading, setSignalsLoading] = useState(false)
  const [signalsError, setSignalsError] = useState<string | null>(null)
  const [buyRules, setBuyRules] = useState<Record<string, string>>({})

  const loadPhilosophy = useCallback(async () => {
    setPhilosophyLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/jc/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取投资体系失败:', e)
    } finally {
      setPhilosophyLoading(false)
    }
  }, [])

  const loadStocks = useCallback(async () => {
    const requestId = ++screenerCounter.current
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string | number> = {
        market, min_score: minScore, top_n: topN,
        sort_by: sortBy, sort_order: sortOrder,
      }
      if (maxPE !== '') params.max_pe = maxPE
      if (maxPB !== '') params.max_pb = maxPB
      if (minROE !== '') params.min_roe = minROE
      if (minDividend !== '') params.min_dividend = minDividend
      const res = await axios.get(`${API_BASE}/jc/screener`, { params })
      // Only apply if still the latest request
      if (requestId !== screenerCounter.current) return
      if (res.data.error) {
        setError(res.data.error)
        return
      }
      setStocks(res.data.stocks || [])
      setTotal(res.data.total || 0)
      setUpdateTime(res.data.update_time || '')
      setElapsed(res.data.elapsed ?? null)
    } catch (e: any) {
      if (requestId !== screenerCounter.current) return
      setError(e?.response?.data?.detail || e?.message || '筛选失败')
    } finally {
      if (requestId === screenerCounter.current) setLoading(false)
    }
  }, [market, minScore, maxPE, maxPB, minROE, minDividend, topN, sortBy, sortOrder])

  const loadSignals = useCallback(async () => {
    const requestId = ++signalCounter.current
    setSignalsLoading(true)
    setSignalsError(null)
    try {
      const res = await axios.get(`${API_BASE}/jc/buy-signals`, { params: { market: 'all' } })
      if (requestId !== signalCounter.current) return
      setSignals(res.data.stocks || [])
      setBuyRules(res.data.buy_rules || {})
    } catch (e: any) {
      if (requestId !== signalCounter.current) return
      setSignalsError(e?.response?.data?.detail || e?.message || '获取买入信号失败')
    } finally {
      if (requestId === signalCounter.current) setSignalsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPhilosophy()
  }, [loadPhilosophy])

  useEffect(() => {
    if (activeTab === 'screener') loadStocks()
    if (activeTab === 'signals') loadSignals()
  }, [activeTab, loadStocks, loadSignals])

  // Screener table columns
  const screenerColumns: Column<JCStock>[] = [
    { key: 'code', title: '代码', dataIndex: 'code', render: (v: string) => <span style={{ fontFamily: 'monospace' }}>{v}</span> },
    { key: 'name', title: '名称', dataIndex: 'name' },
    {
      key: 'market', title: '市场', dataIndex: 'market',
      render: (_: any, r: JCStock) => {
        const mkt = getMarketTag(r.market)
        return <span style={{ color: mkt.color, fontSize: 12, fontWeight: 600 }}>{mkt.text}</span>
      },
    },
    {
      key: 'industry_position', title: '行业地位', dataIndex: 'industry_position',
      render: (v: string) => <span style={{ fontSize: 12, color: '#d29922' }}>{v || '-'}</span>,
    },
    { key: 'price', title: '价格', dataIndex: 'price', align: 'right', sortable: true, render: (v: number) => v?.toFixed(2) },
    { key: 'pe', title: 'PE', dataIndex: 'pe', align: 'right', sortable: true, render: (v: number | null) => v?.toFixed(1) ?? '-' },
    { key: 'pb', title: 'PB', dataIndex: 'pb', align: 'right', sortable: true, render: (v: number | null) => v?.toFixed(1) ?? '-' },
    { key: 'roe', title: 'ROE', dataIndex: 'roe', align: 'right', sortable: true, render: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
    { key: 'gross_margin', title: '毛利率', dataIndex: 'gross_margin', align: 'right', render: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
    { key: 'dividend_yield', title: '股息率', dataIndex: 'dividend_yield', align: 'right', sortable: true, render: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
    { key: 'market_cap', title: '市值', dataIndex: 'market_cap', align: 'right', sortable: true, render: (v: number | null) => v != null ? `${(v / 100000000).toFixed(0)}亿` : '-' },
    {
      key: 'jc_score', title: '机哥评分', dataIndex: 'jc_score', align: 'right', sortable: true,
      render: (v: number) => <span style={{ color: getScoreColor(v), fontWeight: 700, fontSize: 16 }}>{v}</span>,
    },
    {
      key: 'match_level', title: '匹配', dataIndex: 'match_level',
      render: (_: any, r: JCStock) => (
        <span style={{
          color: getMatchLevelColor(r.match_level),
          fontSize: 12, padding: '2px 8px', borderRadius: 10,
          background: `${getMatchLevelColor(r.match_level)}20`,
        }}>
          {getMatchLevelText(r.match_level)}
        </span>
      ),
    },
  ]

  // Signals table columns
  const signalColumns: Column<JCStock>[] = [
    { key: 'code', title: '代码', dataIndex: 'code', render: (v: string) => <span style={{ fontFamily: 'monospace' }}>{v}</span> },
    { key: 'name', title: '名称', dataIndex: 'name' },
    {
      key: 'market', title: '市场', dataIndex: 'market',
      render: (_: any, r: JCStock) => {
        const mkt = getMarketTag(r.market)
        return <span style={{ color: mkt.color, fontSize: 12, fontWeight: 600 }}>{mkt.text}</span>
      },
    },
    {
      key: 'industry_position', title: '行业地位', dataIndex: 'industry_position',
      render: (v: string) => <span style={{ fontSize: 12, color: '#d29922' }}>{v || '-'}</span>,
    },
    { key: 'price', title: '价格', dataIndex: 'price', align: 'right', render: (v: number) => v?.toFixed(2) },
    { key: 'pe', title: 'PE', dataIndex: 'pe', align: 'right', render: (v: number | null) => v?.toFixed(1) ?? '-' },
    { key: 'roe', title: 'ROE', dataIndex: 'roe', align: 'right', render: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
    { key: 'dividend_yield', title: '股息率', dataIndex: 'dividend_yield', align: 'right', render: (v: number | null) => v != null ? `${v.toFixed(1)}%` : '-' },
    {
      key: 'jc_score', title: '机哥评分', dataIndex: 'jc_score', align: 'right',
      render: (v: number) => <span style={{ color: getScoreColor(v), fontWeight: 700, fontSize: 16 }}>{v}</span>,
    },
    {
      key: 'match_level', title: '匹配', dataIndex: 'match_level',
      render: (_: any, r: JCStock) => (
        <span style={{
          color: getMatchLevelColor(r.match_level),
          fontSize: 12, padding: '2px 8px', borderRadius: 10,
          background: `${getMatchLevelColor(r.match_level)}20`,
        }}>
          {getMatchLevelText(r.match_level)}
        </span>
      ),
    },
  ]

  const filterSelectStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 6,
    background: 'var(--bg-secondary)', color: 'var(--text-primary)',
    border: '1px solid var(--border-primary)',
  }

  return (
    <div className="cb-page">
      <PageSection title="金渐成投资体系" compact
        extra={<span className="stock-code">第一兼唯一选股法 | 天玑/机哥</span>}
      >
        <></>
      </PageSection>

      {/* Tabs */}
      <TabBar
        tabs={[
          { key: 'philosophy', label: '投资体系' },
          { key: 'screener', label: '股票筛选' },
          { key: 'signals', label: '买入信号' },
        ]}
        activeKey={activeTab}
        onChange={key => setActiveTab(key as typeof activeTab)}
      />

      {/* Philosophy Tab */}
      {activeTab === 'philosophy' && (
        philosophyLoading ? <LoadingSpinner text="加载投资体系..." /> :
        philosophy ? (
        <div>
          {/* Core Philosophy */}
          <PageSection title="核心理念" compact style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
              {philosophy.core_philosophy}
            </div>
          </PageSection>
          <StatCardGroup columns={2} style={{ marginBottom: 16 }}>
            <StatCard label="2025年收益" value={philosophy.performance?.['2025_return'] || '~73%'} color="#3fb950" />
            <StatCard label="2026年目标" value={philosophy.performance?.target_2026 || '6-8%'} color="#58a6ff" />
          </StatCardGroup>

          {/* Investment Framework */}
          <PageSection title="投资框架六大维度" style={{ marginBottom: 16 }}>
            {philosophy.investment_framework.map((dim, i) => (
              <div key={`dim-${i}`} style={{
                background: 'var(--bg-secondary)',
                borderRadius: 8,
                padding: 16,
                marginBottom: 12,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h4 style={{ color: 'var(--text-primary)', margin: 0 }}>{dim.dimension}</h4>
                </div>
                <p style={{ color: 'var(--text-secondary)', margin: '0 0 8px', fontSize: 13 }}>
                  {dim.description}
                </p>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {dim.criteria.map((c, j) => (
                    <li key={`crit-${j}`} style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 4 }}>{c}</li>
                  ))}
                </ul>
                {dim.key_insight && (
                  <div style={{
                    marginTop: 8,
                    padding: '8px 12px',
                    background: 'rgba(88,166,255,0.1)',
                    borderRadius: 6,
                    borderLeft: '3px solid #58a6ff',
                    color: '#58a6ff',
                    fontSize: 13,
                    fontStyle: 'italic',
                  }}>
                    "{dim.key_insight}"
                  </div>
                )}
              </div>
            ))}
          </PageSection>

          {/* Classic Quotes */}
          <PageSection title="经典语录">
            <div className="arb-notes-grid">
              {philosophy.classic_quotes.map((q, i) => (
                <div key={`quote-${i}`} className="arb-note-item">
                  <div className="note-value" style={{ fontSize: 13, lineHeight: 1.5 }}>
                    "{q}"
                  </div>
                </div>
              ))}
            </div>
          </PageSection>
        </div>
      ) : <EmptyState title="暂无数据" description="无法加载投资体系" />)}

      {/* Screener Tab */}
      {activeTab === 'screener' && (
        <div>
          {/* Filter Bar */}
          <div style={{
            display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap',
            alignItems: 'center',
          }}>
            <select value={market} onChange={e => setMarket(e.target.value as any)} style={filterSelectStyle}>
              <option value="all">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
              <option value="US">美股</option>
            </select>
            <select value={minScore} onChange={e => setMinScore(Number(e.target.value))} style={filterSelectStyle}>
              <option value={0}>全部分数</option>
              <option value={50}>50分+</option>
              <option value={60}>60分+</option>
              <option value={65}>65分+</option>
              <option value={70}>70分+</option>
              <option value={80}>80分+</option>
            </select>
            <select value={maxPE === '' ? '' : maxPE} onChange={e => setMaxPE(e.target.value === '' ? '' : Number(e.target.value))} style={filterSelectStyle}>
              <option value="">不限PE</option>
              <option value={15}>PE&lt;15</option>
              <option value={20}>PE&lt;20</option>
              <option value={25}>PE&lt;25</option>
              <option value={30}>PE&lt;30</option>
              <option value={40}>PE&lt;40</option>
            </select>
            <select value={maxPB === '' ? '' : maxPB} onChange={e => setMaxPB(e.target.value === '' ? '' : Number(e.target.value))} style={filterSelectStyle}>
              <option value="">不限PB</option>
              <option value={2}>PB&lt;2</option>
              <option value={3}>PB&lt;3</option>
              <option value={5}>PB&lt;5</option>
              <option value={8}>PB&lt;8</option>
            </select>
            <select value={minROE === '' ? '' : minROE} onChange={e => setMinROE(e.target.value === '' ? '' : Number(e.target.value))} style={filterSelectStyle}>
              <option value="">不限ROE</option>
              <option value={10}>ROE&gt;10%</option>
              <option value={15}>ROE&gt;15%</option>
              <option value={20}>ROE&gt;20%</option>
              <option value={25}>ROE&gt;25%</option>
            </select>
            <select value={minDividend === '' ? '' : minDividend} onChange={e => setMinDividend(e.target.value === '' ? '' : Number(e.target.value))} style={filterSelectStyle}>
              <option value="">不限股息</option>
              <option value={1}>股息&gt;1%</option>
              <option value={2}>股息&gt;2%</option>
              <option value={3}>股息&gt;3%</option>
              <option value={4}>股息&gt;4%</option>
            </select>
            <select value={topN} onChange={e => setTopN(Number(e.target.value))} style={filterSelectStyle}>
              <option value={20}>前20只</option>
              <option value={50}>前50只</option>
              <option value={100}>前100只</option>
              <option value={200}>全部</option>
            </select>
          </div>
          {/* Sort Bar */}
          <div style={{
            display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap',
            alignItems: 'center',
          }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>排序:</span>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={filterSelectStyle}>
              <option value="jc_score">机哥评分</option>
              <option value="pe">PE</option>
              <option value="roe">ROE</option>
              <option value="dividend_yield">股息率</option>
              <option value="price">价格</option>
              <option value="market_cap">市值</option>
              <option value="gross_margin">毛利率</option>
              <option value="profit_growth">利润增速</option>
            </select>
            <select value={sortOrder} onChange={e => setSortOrder(e.target.value as 'asc' | 'desc')} style={filterSelectStyle}>
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
            <button onClick={loadStocks}
              style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              筛选
            </button>
            {updateTime && (
              <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                更新: {updateTime} | 共{total}只{elapsed != null ? ` | 耗时${elapsed}s` : ''}
              </span>
            )}
          </div>

          {/* Error / Loading / Results */}
          {error ? (
            <EmptyState title="筛选出错" description={error} action={<button onClick={loadStocks} style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer' }}>重试</button>} />
          ) : loading ? (
            <LoadingSpinner text="筛选中..." />
          ) : stocks.length === 0 ? (
            <EmptyState title="暂无结果" description="调整筛选条件后重试" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <DataTable
                columns={screenerColumns}
                data={stocks}
                rowKey={(r) => r.code}
                striped
                compact
                onRowClick={(stock) => {
                  setExpandedStock(expandedStock === stock.code ? null : stock.code)
                }}
              />
              {/* Expanded detail rows rendered below table */}
              {expandedStock && (() => {
                const stock = stocks.find(s => s.code === expandedStock)
                if (!stock) return null
                return (
                  <div style={{
                    marginTop: 8, padding: '12px 16px',
                    background: 'var(--bg-secondary)', borderRadius: 8,
                    border: '1px solid var(--border-primary)',
                  }}>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                      <strong style={{ color: 'var(--text-primary)' }}>{stock.name} ({stock.code}) 评分明细：</strong>
                      <br />
                      {stock.jc_detail.split(' | ').map((d, i) => (
                        <span key={`detail-${i}`}>
                          {d}
                          {i < stock.jc_detail.split(' | ').length - 1 && <span style={{ color: 'var(--border-primary)' }}> → </span>}
                        </span>
                      ))}
                    </div>
                    <div style={{ marginTop: 8, display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                      <span>净利率: {stock.net_margin?.toFixed(1) ?? '-'}%</span>
                      <span>负债率: {stock.debt_ratio?.toFixed(1) ?? '-'}%</span>
                      <span>营收增速: {stock.revenue_growth?.toFixed(1) ?? '-'}%</span>
                      <span>利润增速: {stock.profit_growth?.toFixed(1) ?? '-'}%</span>
                      <span>报告期: {stock.report_period || '-'}</span>
                      <span>PB: {stock.pb?.toFixed(2) ?? '-'}</span>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      )}

      {/* Buy Signals Tab */}
      {activeTab === 'signals' && (
        <div>
          {/* Buy Rules */}
          <PageSection title="买入规则" compact style={{ marginBottom: 16 }}>
            <div className="arb-notes">
              {Object.entries(buyRules).map(([key, rule]) => (
                <div key={key} className="arb-note-item">
                  <div className="note-value" style={{ fontSize: 13 }}>{rule}</div>
                </div>
              ))}
            </div>
          </PageSection>

          {/* Signals Table */}
          {signalsError ? (
            <EmptyState title="获取失败" description={signalsError} action={<button onClick={loadSignals} style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer' }}>重试</button>} />
          ) : signalsLoading ? (
            <LoadingSpinner text="加载买入信号..." />
          ) : signals.length === 0 ? (
            <EmptyState title="暂无买入信号" description="当前市场无符合条件的标的" />
          ) : (
            <DataTable
              columns={signalColumns}
              data={signals}
              rowKey={(r) => r.code}
              striped
              compact
            />
          )}
        </div>
      )}
    </div>
  )
}
