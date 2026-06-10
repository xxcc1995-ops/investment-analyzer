import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'

const API_BASE = '/api/polymarket'

// Reused style constants
const STYLE = {
  actionBtn: {
    padding: '2px 8px' as const,
    borderRadius: 4,
    background: '#58a6ff20',
    color: '#58a6ff',
    border: '1px solid #58a6ff40',
    cursor: 'pointer' as const,
    fontSize: 12,
  },
  card: {
    background: 'var(--bg-secondary)',
    borderRadius: 8,
    padding: 16,
    border: '1px solid var(--border-primary)',
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    borderRadius: 6,
    background: 'var(--bg-secondary)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-primary)',
  },
  select: {
    padding: '6px 10px',
    borderRadius: 6,
    background: 'var(--bg-secondary)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-primary)',
  },
  primaryBtn: {
    padding: '6px 16px',
    borderRadius: 6,
    background: '#58a6ff',
    color: '#fff',
    border: 'none',
    cursor: 'pointer' as const,
    fontWeight: 600,
  },
  greenBtn: {
    padding: '6px 16px',
    borderRadius: 6,
    background: '#3fb950',
    color: '#fff',
    border: 'none',
    cursor: 'pointer' as const,
    fontWeight: 600,
  },
  errorBox: {
    color: '#f85149',
    padding: 16,
    background: '#f8514920',
    borderRadius: 8,
  },
} as const

// Utility functions (stable references, no component dependency)
const formatPrice = (p: number) => `$${p.toFixed(2)}`
const formatVolume = (v: number) => {
  if (v >= 1000000) return `$${(v / 1000000).toFixed(1)}M`
  if (v >= 1000) return `$${(v / 1000).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}
const formatLiq = (l: number) => {
  if (l >= 1000000) return `$${(l / 1000000).toFixed(1)}M`
  if (l >= 1000) return `$${(l / 1000).toFixed(0)}K`
  return `$${l.toFixed(0)}`
}
const getTrendColor = (v: number) => {
  if (v > 5) return '#3fb950'
  if (v < -5) return '#f85149'
  return '#8b949e'
}
const getRiskColor = (level: string) => {
  switch (level) {
    case 'negative_edge': return '#f85149'
    case 'low': return '#d29922'
    case 'medium': return '#58a6ff'
    case 'high': return '#3fb950'
    case 'very_high': return '#f0883e'
    default: return '#8b949e'
  }
}

type TabKey = 'markets' | 'arbitrage' | 'crossArb' | 'allocation' | 'value' | 'trending' | 'kelly' | 'detail'

interface Market {
  id: string
  question: string
  outcomes: string[]
  prices: number[]
  price_sum: number
  has_arbitrage: boolean
  arbitrage_profit: number
  tokens: Record<string, string>
  volume: number
  liquidity: number
  end_date: string
  tag: string
  slug: string
  description: string
  image: string
  neg_risk: boolean
  price_change_7d?: number
  price_direction?: string
  signal?: string
  potential_return?: number
}

interface ValueMarkets {
  cheap_yes: Market[]
  cheap_no: Market[]
  near_certain: Market[]
  high_volume_low_price: Market[]
}

interface KellyResult {
  price: number
  estimated_prob: number
  implied_prob: number
  edge: number
  edge_pct: number
  ev_per_dollar: number
  ev_pct: number
  kelly_full: number
  kelly_full_pct: number
  kelly_fractional: number
  kelly_fractional_pct: number
  bankroll: number
  fraction: number
  position_full: number
  position_fractional: number
  risk_level: string
  risk_msg: string
  potential_profit: number
  error?: string
}

interface MarketAnalysis {
  market: Market
  history: { timestamp: string; price: number }[]
  order_book: any
  analysis: {
    trend: string
    price_change_7d: number
    price_change_30d: number
    liquidity_score: string
    volume_liquidity_ratio: number
  }
}

// 跨平台套利相关接口
interface StrategyDetail {
  description: string
  opinion_yes_price?: number
  opinion_no_price?: number
  polymarket_yes_price?: number
  polymarket_no_price?: number
  price_sum: number
  fee: number
}

interface AllocationResult {
  budget: number
  yes_price: number
  no_price: number
  yes_fee_rate: number
  no_fee_rate: number
  yes_amount: number
  no_amount: number
  yes_ratio: number
  no_ratio: number
  profit_if_yes: number
  profit_if_no: number
  guaranteed_profit: number
  profit_rate: number
  yes_fee: number
  no_fee: number
  total_fee: number
  yes_net_return: number
  no_net_return: number
  error?: string
}

interface CrossArbOpportunity {
  question: string
  match_type: string
  strategy_1: StrategyDetail
  strategy_2: StrategyDetail
  best_strategy: string
  best_sum: number
  total_fee: number
  guaranteed_profit: number
  profit_rate: number
  allocation: AllocationResult
  polymarket: {
    id: string
    yes_price: number
    no_price: number
    volume: number
    liquidity: number
  }
  opinion: {
    id: string
    yes_price: number
    no_price: number
    volume: number
    liquidity: number
  }
  end_date: string
  volume: number
}

export default function PolymarketPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('markets')

  // Markets
  const [markets, setMarkets] = useState<Market[]>([])
  const [marketsLoading, setMarketsLoading] = useState(false)
  const [marketsError, setMarketsError] = useState<string | null>(null)
  const [marketsTotal, setMarketsTotal] = useState(0)
  const [marketOrder, setMarketOrder] = useState('volume')
  const [marketTag, setMarketTag] = useState('')

  // Arbitrage
  const [arbOpps, setArbOpps] = useState<Market[]>([])
  const [arbLoading, setArbLoading] = useState(false)
  const [arbError, setArbError] = useState<string | null>(null)
  const [minProfit, setMinProfit] = useState(0.5)

  // Cross-platform Arbitrage
  const [crossArbOpps, setCrossArbOpps] = useState<CrossArbOpportunity[]>([])
  const [crossArbLoading, setCrossArbLoading] = useState(false)
  const [crossArbError, setCrossArbError] = useState<string | null>(null)
  const [crossArbMinProfit, setCrossArbMinProfit] = useState(0.5)
  const [crossArbBudget, setCrossArbBudget] = useState('100')

  // Allocation Calculator
  const [allocYesPrice, setAllocYesPrice] = useState('')
  const [allocNoPrice, setAllocNoPrice] = useState('')
  const [allocBudget, setAllocBudget] = useState('100')
  const [allocYesFee, setAllocYesFee] = useState('0')
  const [allocNoFee, setAllocNoFee] = useState('0')
  const [allocResult, setAllocResult] = useState<AllocationResult | null>(null)
  const [allocLoading, setAllocLoading] = useState(false)

  // Value
  const [valueData, setValueData] = useState<ValueMarkets | null>(null)
  const [valueLoading, setValueLoading] = useState(false)
  const [valueError, setValueError] = useState<string | null>(null)

  // Trending
  const [trending, setTrending] = useState<Market[]>([])
  const [trendingLoading, setTrendingLoading] = useState(false)
  const [trendingError, setTrendingError] = useState<string | null>(null)

  // Kelly
  const [kellyPrice, setKellyPrice] = useState('')
  const [kellyProb, setKellyProb] = useState('')
  const [kellyBankroll, setKellyBankroll] = useState('1000')
  const [kellyResult, setKellyResult] = useState<KellyResult | null>(null)

  // Detail
  const [detailData, setDetailData] = useState<MarketAnalysis | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const loadMarkets = useCallback(async () => {
    setMarketsLoading(true)
    setMarketsError(null)
    try {
      const params: Record<string, string | number> = { limit: 100, order: marketOrder }
      if (marketTag) params.tag = marketTag
      const res = await axios.get(`${API_BASE}/markets`, { params })
      setMarkets(res.data.markets || [])
      setMarketsTotal(res.data.total || 0)
    } catch (e) {
      console.error('获取市场失败:', e)
      setMarketsError('获取市场数据失败，请检查网络连接或稍后重试')
    } finally {
      setMarketsLoading(false)
    }
  }, [marketOrder, marketTag])

  const loadArbitrage = useCallback(async () => {
    setArbLoading(true)
    setArbError(null)
    try {
      const res = await axios.get(`${API_BASE}/arbitrage`, { params: { min_profit: minProfit } })
      setArbOpps(res.data.opportunities || [])
    } catch (e) {
      console.error('获取套利机会失败:', e)
      setArbError('获取套利数据失败，请检查网络连接或稍后重试')
    } finally {
      setArbLoading(false)
    }
  }, [minProfit])

  const loadValue = useCallback(async () => {
    setValueLoading(true)
    setValueError(null)
    try {
      const res = await axios.get(`${API_BASE}/value`)
      setValueData(res.data)
    } catch (e) {
      console.error('获取价值发现失败:', e)
      setValueError('获取价值发现数据失败，请检查网络连接或稍后重试')
    } finally {
      setValueLoading(false)
    }
  }, [])

  const loadTrending = useCallback(async () => {
    setTrendingLoading(true)
    setTrendingError(null)
    try {
      const res = await axios.get(`${API_BASE}/trending`)
      setTrending(res.data.markets || [])
    } catch (e) {
      console.error('获取趋势失败:', e)
      setTrendingError('获取趋势数据失败，请检查网络连接或稍后重试')
    } finally {
      setTrendingLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (marketId: string) => {
    setDetailLoading(true)
    setDetailError(null)
    setActiveTab('detail')
    try {
      const res = await axios.get(`${API_BASE}/markets/${marketId}`)
      setDetailData(res.data)
    } catch (e) {
      console.error('获取市场详情失败:', e)
      setDetailError('获取市场详情失败，请检查网络连接或稍后重试')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  // 跨平台套利扫描
  const loadCrossArbitrage = useCallback(async () => {
    setCrossArbLoading(true)
    setCrossArbError(null)
    try {
      const res = await axios.get(`${API_BASE}/cross-arbitrage`, {
        params: {
          min_profit: crossArbMinProfit,
          budget: parseFloat(crossArbBudget) || 100,
        }
      })
      setCrossArbOpps(res.data.opportunities || [])
    } catch (e) {
      console.error('获取跨平台套利机会失败:', e)
      setCrossArbError('获取跨平台套利数据失败，请检查网络连接或稍后重试')
    } finally {
      setCrossArbLoading(false)
    }
  }, [crossArbMinProfit, crossArbBudget])

  // 配资计算器
  const calcAllocation = useCallback(async () => {
    const yesPrice = parseFloat(allocYesPrice)
    const noPrice = parseFloat(allocNoPrice)
    const budget = parseFloat(allocBudget) || 100
    const yesFee = parseFloat(allocYesFee) / 100 || 0
    const noFee = parseFloat(allocNoFee) / 100 || 0

    if (isNaN(yesPrice) || isNaN(noPrice)) return

    setAllocLoading(true)
    try {
      const res = await axios.post(`${API_BASE}/allocation-calculator`, {
        yes_price: yesPrice,
        no_price: noPrice,
        budget: budget,
        yes_fee_rate: yesFee,
        no_fee_rate: noFee,
      })
      setAllocResult(res.data)
    } catch (e) {
      console.error('配资计算失败:', e)
    } finally {
      setAllocLoading(false)
    }
  }, [allocYesPrice, allocNoPrice, allocBudget, allocYesFee, allocNoFee])

  const calcKelly = useCallback(async () => {
    const price = parseFloat(kellyPrice)
    const prob = parseFloat(kellyProb)
    const bankroll = parseFloat(kellyBankroll) || 1000
    if (isNaN(price) || isNaN(prob)) return
    try {
      const res = await axios.post(`${API_BASE}/kelly`, {
        price, estimated_prob: prob, bankroll, fraction: 0.25,
      })
      setKellyResult(res.data)
    } catch (e) {
      console.error('Kelly计算失败:', e)
    }
  }, [kellyPrice, kellyProb, kellyBankroll])

  useEffect(() => {
    if (activeTab === 'markets') loadMarkets()
    if (activeTab === 'arbitrage') loadArbitrage()
    if (activeTab === 'crossArb') loadCrossArbitrage()
    if (activeTab === 'value') loadValue()
    if (activeTab === 'trending') loadTrending()
  }, [activeTab, loadMarkets, loadArbitrage, loadCrossArbitrage, loadValue, loadTrending])

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>Polymarket 智能分析</h2>
            <span className="stock-code">预测市场套利 · 价值发现 · 趋势追踪 · Kelly仓位</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { key: 'markets', label: '市场扫描' },
          { key: 'arbitrage', label: '套利机会' },
          { key: 'crossArb', label: '跨平台套利' },
          { key: 'allocation', label: '配资计算器' },
          { key: 'value', label: '价值发现' },
          { key: 'trending', label: '趋势追踪' },
          { key: 'kelly', label: 'Kelly计算器' },
          { key: 'detail', label: '市场详情' },
        ].map(t => (
          <button key={t.key} className={`tab-btn ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key as TabKey)}>{t.label}</button>
        ))}
      </div>

      {/* Markets Tab */}
      {activeTab === 'markets' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <select value={marketOrder} onChange={e => setMarketOrder(e.target.value)}
              style={STYLE.select}>
              <option value="volume">按成交量</option>
              <option value="liquidity">按流动性</option>
              <option value="startDate">按开始时间</option>
            </select>
            <select value={marketTag} onChange={e => setMarketTag(e.target.value)}
              style={STYLE.select}>
              <option value="">全部标签</option>
              <option value="Politics">政治</option>
              <option value="Crypto">加密货币</option>
              <option value="Sports">体育</option>
              <option value="Business">商业</option>
              <option value="Science">科学</option>
              <option value="Tech">科技</option>
            </select>
            <button onClick={loadMarkets}
              style={STYLE.primaryBtn}>
              刷新
            </button>
            <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>共 {marketsTotal} 个市场</span>
          </div>

          {marketsLoading ? (
            <div className="loading"><div className="spinner"></div>加载中...</div>
          ) : marketsError ? (
            <div style={STYLE.errorBox}>{marketsError}</div>
          ) : (
            <table className="arb-table">
              <thead>
                <tr>
                  <th>市场</th>
                  <th>标签</th>
                  <th>Yes价格</th>
                  <th>No价格</th>
                  <th>合计</th>
                  <th>成交量</th>
                  <th>流动性</th>
                  <th>到期</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {markets.map(m => (
                  <tr key={m.id}>
                    <td style={{ maxWidth: 300, fontSize: 13 }}>{m.question}</td>
                    <td><span style={{ fontSize: 11, color: '#d29922' }}>{m.tag || '-'}</span></td>
                    <td style={{ color: m.prices[0] > 0.5 ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                      {formatPrice(m.prices[0] || 0)}
                    </td>
                    <td style={{ color: m.prices[1] > 0.5 ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                      {formatPrice(m.prices[1] || 0)}
                    </td>
                    <td style={{
                      color: m.price_sum < 0.98 ? '#3fb950' : m.price_sum > 1.02 ? '#f85149' : '#8b949e',
                      fontWeight: 600
                    }}>
                      {m.price_sum.toFixed(4)}
                    </td>
                    <td>{formatVolume(m.volume)}</td>
                    <td>{formatLiq(m.liquidity)}</td>
                    <td style={{ fontSize: 11 }}>{m.end_date ? new Date(m.end_date).toLocaleDateString() : '-'}</td>
                    <td>
                      <button onClick={() => loadDetail(m.id)}
                        style={STYLE.actionBtn}>
                        分析
                      </button>
                    </td>
                  </tr>
                ))}
                {markets.length === 0 && (
                  <tr><td colSpan={9} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>暂无数据</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Arbitrage Tab */}
      {activeTab === 'arbitrage' && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">套利原理</div>
              <div className="note-value" style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>核心逻辑：</strong>预测市场的二元结果（YES/NO）在结算时，有且仅有一方兑付 $1.00，另一方归零。因此无论事件发生与否，同时持有 YES + NO 的总回款恒为 $1.00。</p>
                <p><strong>套利条件：</strong>当同一市场的 YES 价格 + NO 价格 &lt; $1.00 时，同时买入双方即可锁定无风险利润。</p>
                <p><strong>利润公式：</strong>利润 = $1.00 - (YES价格 + NO价格)，利润率 = 利润 / (YES价格 + NO价格) × 100%</p>
                <p><strong>举例：</strong>Yes=$0.55, No=$0.40, 合计=$0.95 → 无论结果如何都回款 $1.00，净利润=$0.05 (5.26%)</p>
                <p><strong>注意：</strong>需考虑交易手续费和滑点。Polymarket 手续费基本为 0%，但仍需注意链上 Gas 费和流动性不足导致的滑点。阈值设太低可能被手续费和滑点吃掉利润。</p>
                <p><strong>Neg-risk 市场：</strong>多结果市场（如选举候选人）中，所有结果价格之和可能偏离 1.0，也可检测套利机会。</p>
              </div>
            </div>
            <div className="arb-note-item">
              <div className="note-label">最低利润</div>
              <div className="note-value">
                <select value={minProfit} onChange={e => setMinProfit(Number(e.target.value))}
                  style={STYLE.select}>
                  <option value={0.1}>0.1%</option>
                  <option value={0.5}>0.5%</option>
                  <option value={1}>1%</option>
                  <option value={2}>2%</option>
                  <option value={5}>5%</option>
                </select>
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <button onClick={loadArbitrage}
              style={STYLE.greenBtn}>
              扫描套利机会
            </button>
            <span style={{ color: 'var(--text-secondary)', fontSize: 12, marginLeft: 12 }}>
              找到 {arbOpps.length} 个机会
            </span>
          </div>

          {arbLoading ? (
            <div className="loading"><div className="spinner"></div>扫描中...</div>
          ) : (
            <table className="arb-table">
              <thead>
                <tr>
                  <th>市场</th>
                  <th>Yes价格</th>
                  <th>No价格</th>
                  <th>合计</th>
                  <th>套利利润</th>
                  <th>成交量</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {arbOpps.map(m => (
                  <tr key={m.id}>
                    <td style={{ maxWidth: 400, fontSize: 13 }}>{m.question}</td>
                    <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[0] || 0)}</td>
                    <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[1] || 0)}</td>
                    <td style={{ color: '#3fb950', fontWeight: 700 }}>{m.price_sum.toFixed(4)}</td>
                    <td style={{ color: '#3fb950', fontWeight: 700, fontSize: 16 }}>+{m.arbitrage_profit.toFixed(2)}%</td>
                    <td>{formatVolume(m.volume)}</td>
                    <td>
                      <button onClick={() => loadDetail(m.id)}
                        style={STYLE.actionBtn}>
                        详情
                      </button>
                    </td>
                  </tr>
                ))}
                {arbOpps.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                    暂无套利机会（阈值: {minProfit}%）
                  </td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Cross-Platform Arbitrage Tab */}
      {activeTab === 'crossArb' && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">跨平台套利原理</div>
              <div className="note-value" style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>核心逻辑：</strong>同一个现实事件（如"Trump是否当选"）在 Polymarket 和 Opinion 两个平台都有交易，但市场价格可能不同。利用价差可以实现跨平台无风险套利。</p>
                <p><strong>两种策略：</strong></p>
                <p>　• <strong>策略1：</strong>在 Opinion 买 YES + 在 Polymarket 买 NO → 事件发生时 Opinion 兑付 $1，事件不发生时 Polymarket 兑付 $1</p>
                <p>　• <strong>策略2：</strong>在 Opinion 买 NO + 在 Polymarket 买 YES → 反向操作</p>
                <p><strong>套利条件：</strong>两平台的对应方向价格之和 &lt; $1.00（扣除手续费后），即可锁定利润。</p>
                <p><strong>利润公式：</strong>净利润 = $1.00 - (平台A价格 + 平台B价格) - 手续费</p>
                <p><strong>手续费模型：</strong>Polymarket 手续费 ≈ 0%；Opinion 采用二次函数模型：费率 = 2% × (1 - 2×|价格-0.5|)²，价格越接近 50% 费率越高（最高 2%），越接近极端越低（接近 0%），最低 0.5U/笔。</p>
                <p><strong>市场匹配：</strong>系统通过精确匹配 → 子串包含 → 关键词 70% 重叠三级模糊匹配，自动关联两个平台的同一事件。</p>
                <p><strong>附带收益：</strong>同时在两个平台交易可积累交易量，有助于获取空投积分。</p>
              </div>
            </div>
            <div className="arb-note-item">
              <div className="note-label">最低利润</div>
              <div className="note-value">
                <select value={crossArbMinProfit} onChange={e => setCrossArbMinProfit(Number(e.target.value))}
                  style={STYLE.select}>
                  <option value={0.1}>0.1%</option>
                  <option value={0.5}>0.5%</option>
                  <option value={1}>1%</option>
                  <option value={2}>2%</option>
                  <option value={5}>5%</option>
                </select>
              </div>
            </div>
            <div className="arb-note-item">
              <div className="note-label">总预算 (U)</div>
              <div className="note-value">
                <input type="number" min="10" step="10" placeholder="100"
                  value={crossArbBudget} onChange={e => setCrossArbBudget(e.target.value)}
                  style={{ padding: '4px 8px', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', width: 100 }} />
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <button onClick={loadCrossArbitrage}
              style={STYLE.greenBtn}>
              扫描跨平台套利
            </button>
            <span style={{ color: 'var(--text-secondary)', fontSize: 12, marginLeft: 12 }}>
              找到 {crossArbOpps.length} 个机会
            </span>
          </div>

          {crossArbLoading ? (
            <div className="loading"><div className="spinner"></div>扫描中...</div>
          ) : (
            <>
              {crossArbOpps.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {crossArbOpps.map((opp, idx) => (
                    <div key={idx} style={{
                      background: 'var(--bg-secondary)', borderRadius: 12, padding: 16,
                      border: opp.profit_rate > 2 ? '2px solid #3fb950' : '1px solid var(--border-primary)',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{opp.question}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                            匹配方式: {opp.match_type === 'exact' ? '精确匹配' : opp.match_type === 'contains' ? '包含匹配' : '关键词匹配'}
                          </div>
                        </div>
                        <div style={{
                          background: opp.profit_rate > 2 ? '#3fb95020' : '#58a6ff20',
                          padding: '8px 16px', borderRadius: 8, textAlign: 'center',
                        }}>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>保底利润</div>
                          <div style={{ fontSize: 20, fontWeight: 700, color: '#3fb950' }}>
                            +${opp.guaranteed_profit.toFixed(2)}
                          </div>
                          <div style={{ fontSize: 14, fontWeight: 600, color: '#3fb950' }}>
                            {opp.profit_rate.toFixed(2)}%
                          </div>
                        </div>
                      </div>

                      {/* 策略对比 */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                        <div style={{
                          padding: 12, borderRadius: 8,
                          background: opp.best_strategy === 'strategy_1' ? '#3fb95010' : 'var(--bg-tertiary)',
                          border: opp.best_strategy === 'strategy_1' ? '1px solid #3fb950' : '1px solid transparent',
                        }}>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                            策略1 {opp.best_strategy === 'strategy_1' && '✅ 最优'}
                          </div>
                          <div style={{ fontSize: 13, marginBottom: 4 }}>Opinion买YES + PM买NO</div>
                          <div style={{ fontSize: 12 }}>
                            OP YES: {formatPrice(opp.strategy_1.opinion_yes_price || 0)} +
                            PM NO: {formatPrice(opp.strategy_1.polymarket_no_price || 0)}
                          </div>
                          <div style={{ fontSize: 14, fontWeight: 600, color: '#3fb950', marginTop: 4 }}>
                            合计: {opp.strategy_1.price_sum.toFixed(4)} | 手续费: ${opp.strategy_1.fee.toFixed(2)}
                          </div>
                        </div>
                        <div style={{
                          padding: 12, borderRadius: 8,
                          background: opp.best_strategy === 'strategy_2' ? '#3fb95010' : 'var(--bg-tertiary)',
                          border: opp.best_strategy === 'strategy_2' ? '1px solid #3fb950' : '1px solid transparent',
                        }}>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                            策略2 {opp.best_strategy === 'strategy_2' && '✅ 最优'}
                          </div>
                          <div style={{ fontSize: 13, marginBottom: 4 }}>Opinion买NO + PM买YES</div>
                          <div style={{ fontSize: 12 }}>
                            OP NO: {formatPrice(opp.strategy_2.opinion_no_price || 0)} +
                            PM YES: {formatPrice(opp.strategy_2.polymarket_yes_price || 0)}
                          </div>
                          <div style={{ fontSize: 14, fontWeight: 600, color: '#3fb950', marginTop: 4 }}>
                            合计: {opp.strategy_2.price_sum.toFixed(4)} | 手续费: ${opp.strategy_2.fee.toFixed(2)}
                          </div>
                        </div>
                      </div>

                      {/* 配资建议 */}
                      {opp.allocation && !opp.allocation.error && (
                        <div style={{ background: 'var(--bg-tertiary)', borderRadius: 8, padding: 12 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📊 最优配资方案</div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                            <div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>YES投入</div>
                              <div style={{ fontSize: 16, fontWeight: 700 }}>${opp.allocation.yes_amount.toFixed(2)}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{opp.allocation.yes_ratio.toFixed(1)}%</div>
                            </div>
                            <div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>NO投入</div>
                              <div style={{ fontSize: 16, fontWeight: 700 }}>${opp.allocation.no_amount.toFixed(2)}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{opp.allocation.no_ratio.toFixed(1)}%</div>
                            </div>
                            <div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>事件发生利润</div>
                              <div style={{ fontSize: 16, fontWeight: 700, color: opp.allocation.profit_if_yes > 0 ? '#3fb950' : '#f85149' }}>
                                ${opp.allocation.profit_if_yes.toFixed(2)}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>事件不发生利润</div>
                              <div style={{ fontSize: 16, fontWeight: 700, color: opp.allocation.profit_if_no > 0 ? '#3fb950' : '#f85149' }}>
                                ${opp.allocation.profit_if_no.toFixed(2)}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* 空投提示 */}
                      <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                        💡 此操作同时积累两个平台的交易量，有助于获取空投积分
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                  暂无跨平台套利机会
                  <div style={{ fontSize: 13, marginTop: 8 }}>
                    请确保已配置 OPINION_API_URL 环境变量
                  </div>
                </div>
              )}
            </>
          )}

          {/* 空投积分指南 */}
          <div style={{ marginTop: 24, background: 'var(--bg-secondary)', borderRadius: 12, padding: 16 }}>
            <h4 style={{ marginBottom: 12 }}>🎯 空投积分获取指南</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, color: '#58a6ff' }}>Opinion 积分策略</div>
                <ul style={{ fontSize: 13, lineHeight: 1.8, paddingLeft: 16 }}>
                  <li>每周交易量 ≥ 200U 才算合格</li>
                  <li>多挂限价单做市，提供流动性</li>
                  <li>新市场、流动性少时进场有额外加成</li>
                  <li>持仓时间越长，积分越多</li>
                </ul>
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8, color: '#3fb950' }}>Polymarket 积分策略</div>
                <ul style={{ fontSize: 13, lineHeight: 1.8, paddingLeft: 16 }}>
                  <li>挂限价单靠近中间价，得分更高</li>
                  <li>双边挂单（买+卖）获得更高权重</li>
                  <li>长期持仓有约4%年化收益</li>
                  <li>保持真实活跃，避免频繁对冲</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Allocation Calculator Tab */}
      {activeTab === 'allocation' && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">配资计算器 — 最优资金分配</div>
              <div className="note-value" style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>解决的问题：</strong>跨平台套利时，YES 和 NO 的价格不同，如何分配预算才能让两种结果下的回款相等，实现真正的"无论结果如何都赚同样多"？</p>
                <p><strong>核心公式：</strong></p>
                <p>　• 净回报率 = 1/价格 - 1 - 手续费率（即每投入 $1 在该方向上的净回报）</p>
                <p>　• YES投入 = 预算 × NO净回报率 / (YES净回报率 + NO净回报率)</p>
                <p>　• NO投入 = 预算 - YES投入</p>
                <p><strong>结果计算：</strong></p>
                <p>　• 事件发生（YES赢）：利润 = YES数量×$1 - 总投入 - 手续费</p>
                <p>　• 事件不发生（NO赢）：利润 = NO数量×$1 - 总投入 - 手续费</p>
                <p>　• 保底利润 = min(YES赢利润, NO赢利润)</p>
                <p><strong>费率参考：</strong>Polymarket ≈ 0%；Opinion = 2%×(1-2×|价格-0.5|)²，最低 0.5U/笔</p>
              </div>
            </div>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12, marginBottom: 16,
          }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>YES 价格</label>
              <input type="number" min="0.01" max="0.99" step="0.01" placeholder="如 0.05"
                value={allocYesPrice} onChange={e => setAllocYesPrice(e.target.value)}
                style={STYLE.input} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>NO 价格</label>
              <input type="number" min="0.01" max="0.99" step="0.01" placeholder="如 0.90"
                value={allocNoPrice} onChange={e => setAllocNoPrice(e.target.value)}
                style={STYLE.input} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>总预算 (U)</label>
              <input type="number" min="10" step="10" placeholder="100"
                value={allocBudget} onChange={e => setAllocBudget(e.target.value)}
                style={STYLE.input} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>YES 平台费率 (%)</label>
              <input type="number" min="0" max="5" step="0.1" placeholder="0"
                value={allocYesFee} onChange={e => setAllocYesFee(e.target.value)}
                style={STYLE.input} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>NO 平台费率 (%)</label>
              <input type="number" min="0" max="5" step="0.1" placeholder="0"
                value={allocNoFee} onChange={e => setAllocNoFee(e.target.value)}
                style={STYLE.input} />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={calcAllocation}
                style={{ ...STYLE.primaryBtn, padding: '8px 24px', width: '100%' }}>
                计算配资
              </button>
            </div>
          </div>

          {allocResult && !allocResult.error && (
            <>
              {/* 配资方案 */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: 12, marginBottom: 16,
              }}>
                <div style={STYLE.card}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>YES 投入</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#3fb950' }}>
                    ${allocResult.yes_amount.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{allocResult.yes_ratio.toFixed(1)}% 的资金</div>
                </div>
                <div style={STYLE.card}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>NO 投入</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#f85149' }}>
                    ${allocResult.no_amount.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{allocResult.no_ratio.toFixed(1)}% 的资金</div>
                </div>
                <div style={STYLE.card}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>事件发生利润</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: allocResult.profit_if_yes > 0 ? '#3fb950' : '#f85149' }}>
                    ${allocResult.profit_if_yes.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>YES赢</div>
                </div>
                <div style={STYLE.card}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>事件不发生利润</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: allocResult.profit_if_no > 0 ? '#3fb950' : '#f85149' }}>
                    ${allocResult.profit_if_no.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>NO赢</div>
                </div>
                <div style={{
                  background: '#3fb95020', borderRadius: 8, padding: 16,
                  border: '2px solid #3fb950',
                }}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>保底利润</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#3fb950' }}>
                    ${allocResult.guaranteed_profit.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#3fb950' }}>
                    {allocResult.profit_rate.toFixed(2)}%
                  </div>
                </div>
                <div style={STYLE.card}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>总手续费</div>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#d29922' }}>
                    ${allocResult.total_fee.toFixed(2)}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    YES: ${allocResult.yes_fee.toFixed(2)} | NO: ${allocResult.no_fee.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* 计算说明 */}
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 8, padding: 16 }}>
                <h4 style={{ marginBottom: 8 }}>📐 计算说明</h4>
                <div style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text-secondary)' }}>
                  <p>• <strong>最优配资</strong>：让两种结果下的回款金额完全相等，实现真正的无风险套利</p>
                  <p>• <strong>事件发生</strong>：YES每份兑付$1，NO归零 → 利润 = YES回款 - 总投入 - 手续费</p>
                  <p>• <strong>事件不发生</strong>：NO每份兑付$1，YES归零 → 利润 = NO回款 - 总投入 - 手续费</p>
                  <p>• <strong>保底利润</strong>：取两种结果利润的最小值，确保无论结果如何都盈利</p>
                  <p>• <strong>费率参考</strong>：Polymarket基本为0%，Opinion为0%~2%（价格越接近50%越高，最低0.5U）</p>
                </div>
              </div>
            </>
          )}

          {allocResult?.error && (
            <div style={STYLE.errorBox}>
              {allocResult.error}
            </div>
          )}
        </div>
      )}

      {/* Value Tab */}
      {activeTab === 'value' && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">价值发现逻辑</div>
              <div className="note-value" style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>核心思路：</strong>从不同维度筛选可能被市场错误定价的合约，寻找"低买高卖"的机会。</p>
                <p><strong>四类筛选：</strong></p>
                <p>　• <strong>低价YES（&lt;15%）：</strong>市场认为几乎不会发生，但如果你有信息认为概率被低估，潜在回报可达数倍（买入价 $0.05，结算兑付 $1 = 20倍回报）</p>
                <p>　• <strong>低价NO（&lt;15%）：</strong>市场认为几乎确定发生，反向思考——如果你认为事件不会发生，低价NO是高赔率机会</p>
                <p>　• <strong>接近确定（&gt;90%）：</strong>高确定性事件，适合低风险"捡钱"——YES价格 $0.95 买入，结算赚 $0.05（5.3%），但需注意事件不发生的尾部风险</p>
                <p>　• <strong>高成交量+低价格：</strong>异常信号——大量资金涌入低价合约，可能有人知道某些信息，值得关注但需独立验证</p>
              </div>
            </div>
          </div>

          {valueLoading ? (
            <div className="loading"><div className="spinner"></div>分析中...</div>
          ) : valueData && (
            <>
              {/* Cheap Yes */}
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ color: '#3fb950', marginBottom: 8 }}>低价Yes（&lt;15%）- 潜在高回报</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 12 }}>
                  这些市场Yes价格很低，如果你认为事件发生的概率被低估，可能获得数倍回报
                </p>
                <table className="arb-table">
                  <thead>
                    <tr>
                      <th>市场</th>
                      <th>Yes价格</th>
                      <th>潜在回报</th>
                      <th>成交量</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valueData.cheap_yes.map(m => (
                      <tr key={m.id}>
                        <td style={{ maxWidth: 400, fontSize: 13 }}>{m.question}</td>
                        <td style={{ color: '#3fb950', fontWeight: 700, fontSize: 16 }}>{formatPrice(m.prices[0] || 0)}</td>
                        <td style={{ color: '#f0883e', fontWeight: 700 }}>+{m.potential_return?.toFixed(0)}%</td>
                        <td>{formatVolume(m.volume)}</td>
                        <td>
                          <button onClick={() => loadDetail(m.id)}
                            style={STYLE.actionBtn}>
                            分析
                          </button>
                        </td>
                      </tr>
                    ))}
                    {valueData.cheap_yes.length === 0 && (
                      <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>暂无</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Cheap No */}
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ color: '#58a6ff', marginBottom: 8 }}>低价No（&lt;15%）- 反向机会</h3>
                <table className="arb-table">
                  <thead>
                    <tr>
                      <th>市场</th>
                      <th>No价格</th>
                      <th>潜在回报</th>
                      <th>成交量</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valueData.cheap_no.map(m => (
                      <tr key={m.id}>
                        <td style={{ maxWidth: 400, fontSize: 13 }}>{m.question}</td>
                        <td style={{ color: '#58a6ff', fontWeight: 700, fontSize: 16 }}>{formatPrice(m.prices[1] || 0)}</td>
                        <td style={{ color: '#f0883e', fontWeight: 700 }}>+{m.potential_return?.toFixed(0)}%</td>
                        <td>{formatVolume(m.volume)}</td>
                        <td>
                          <button onClick={() => loadDetail(m.id)}
                            style={STYLE.actionBtn}>
                            分析
                          </button>
                        </td>
                      </tr>
                    ))}
                    {valueData.cheap_no.length === 0 && (
                      <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>暂无</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Near Certain */}
              <div style={{ marginBottom: 24 }}>
                <h3 style={{ color: '#d29922', marginBottom: 8 }}>接近确定（&gt;90%）</h3>
                <table className="arb-table">
                  <thead>
                    <tr>
                      <th>市场</th>
                      <th>Yes价格</th>
                      <th>No价格</th>
                      <th>成交量</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valueData.near_certain.map(m => (
                      <tr key={m.id}>
                        <td style={{ maxWidth: 400, fontSize: 13 }}>{m.question}</td>
                        <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[0] || 0)}</td>
                        <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[1] || 0)}</td>
                        <td>{formatVolume(m.volume)}</td>
                        <td>
                          <button onClick={() => loadDetail(m.id)}
                            style={STYLE.actionBtn}>
                            分析
                          </button>
                        </td>
                      </tr>
                    ))}
                    {valueData.near_certain.length === 0 && (
                      <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>暂无</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* High Volume Low Price */}
              <div>
                <h3 style={{ color: '#f0883e', marginBottom: 8 }}>高成交量+低价格 - 关注信号</h3>
                <table className="arb-table">
                  <thead>
                    <tr>
                      <th>市场</th>
                      <th>Yes价格</th>
                      <th>No价格</th>
                      <th>成交量</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {valueData.high_volume_low_price.map(m => (
                      <tr key={m.id}>
                        <td style={{ maxWidth: 400, fontSize: 13 }}>{m.question}</td>
                        <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[0] || 0)}</td>
                        <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[1] || 0)}</td>
                        <td>{formatVolume(m.volume)}</td>
                        <td>
                          <button onClick={() => loadDetail(m.id)}
                            style={STYLE.actionBtn}>
                            分析
                          </button>
                        </td>
                      </tr>
                    ))}
                    {valueData.high_volume_low_price.length === 0 && (
                      <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>暂无</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Trending Tab */}
      {activeTab === 'trending' && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">趋势追踪逻辑</div>
              <div className="note-value" style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>核心思路：</strong>价格是信息的反映。7天内价格变动超过5%的市场，通常意味着有新的重要信息流入（如政策变化、事件进展、大资金入场）。</p>
                <p><strong>上涨信号：</strong>YES价格上涨 → 市场认为事件更可能发生 → 可能有内幕信息或共识形成</p>
                <p><strong>下跌信号：</strong>YES价格下跌 → 市场认为事件更不可能发生 → 关注是否有反向机会</p>
                <p><strong>使用建议：</strong>结合成交量判断——高成交量+大幅变动 = 强信号；低成交量+大幅变动 = 可能是少数大户操作，需谨慎。</p>
              </div>
            </div>
          </div>

          {trendingLoading ? (
            <div className="loading"><div className="spinner"></div>扫描中...</div>
          ) : (
            <table className="arb-table">
              <thead>
                <tr>
                  <th>市场</th>
                  <th>Yes价格</th>
                  <th>No价格</th>
                  <th>7天变动</th>
                  <th>方向</th>
                  <th>成交量</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {trending.map(m => (
                  <tr key={m.id}>
                    <td style={{ maxWidth: 350, fontSize: 13 }}>{m.question}</td>
                    <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[0] || 0)}</td>
                    <td style={{ fontWeight: 600 }}>{formatPrice(m.prices[1] || 0)}</td>
                    <td style={{ color: getTrendColor(m.price_change_7d || 0), fontWeight: 700, fontSize: 15 }}>
                      {(m.price_change_7d || 0) > 0 ? '+' : ''}{(m.price_change_7d || 0).toFixed(2)}%
                    </td>
                    <td style={{ color: m.price_direction === 'up' ? '#3fb950' : '#f85149' }}>
                      {m.price_direction === 'up' ? '↑ 上涨' : '↓ 下跌'}
                    </td>
                    <td>{formatVolume(m.volume)}</td>
                    <td>
                      <button onClick={() => loadDetail(m.id)}
                        style={STYLE.actionBtn}>
                        分析
                      </button>
                    </td>
                  </tr>
                ))}
                {trending.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>暂无趋势市场</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Kelly Tab */}
      {activeTab === 'kelly' && (
        <div>
          <div className="arb-notes" style={{ marginBottom: 16 }}>
            <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
              <div className="note-label">Kelly仓位计算 — 最优下注比例</div>
              <div className="note-value" style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>解决问题：</strong>当你认为市场价格低估了某事件的真实概率时，应该下注多少？下太少浪费机会，下太多可能爆仓。</p>
                <p><strong>Kelly公式：</strong>f* = (b×p - q) / b</p>
                <p>　• p = 你估计的真实概率，q = 1-p，b = 赔率 = (1/市场价格 - 1)</p>
                <p>　• f* = 最优下注比例（占总资金的百分比）</p>
                <p><strong>举例：</strong>市场价 $0.40（隐含概率 40%），你认为真实概率 55%，赔率 b = 1.5 → Kelly = (1.5×0.55-0.45)/1.5 = 25%</p>
                <p><strong>Fractional Kelly：</strong>默认使用 1/4 Kelly，牺牲部分期望收益换取更低的波动和回撤，更适合实际操作。</p>
                <p><strong>风险提醒：</strong>Kelly公式假设你的概率估计是准确的。如果过度自信（高估真实概率），公式会建议过度下注。建议结合多种信息源验证你的判断。</p>
              </div>
            </div>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 12, marginBottom: 16,
          }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>市场价格 (0.01-0.99)</label>
              <input type="number" min="0.01" max="0.99" step="0.01" placeholder="如 0.40"
                value={kellyPrice} onChange={e => setKellyPrice(e.target.value)}
                style={STYLE.input} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>你估计的概率 (0.01-0.99)</label>
              <input type="number" min="0.01" max="0.99" step="0.01" placeholder="如 0.55"
                value={kellyProb} onChange={e => setKellyProb(e.target.value)}
                style={STYLE.input} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>总资金 ($)</label>
              <input type="number" min="1" step="100" placeholder="1000"
                value={kellyBankroll} onChange={e => setKellyBankroll(e.target.value)}
                style={STYLE.input} />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={calcKelly}
                style={{ ...STYLE.primaryBtn, padding: '8px 24px', width: '100%' }}>
                计算
              </button>
            </div>
          </div>

          {kellyResult && !kellyResult.error && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 12, marginBottom: 16,
            }}>
              <div style={STYLE.card}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>优势 (Edge)</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: kellyResult.edge > 0 ? '#3fb950' : '#f85149' }}>
                  {kellyResult.edge_pct > 0 ? '+' : ''}{kellyResult.edge_pct.toFixed(2)}%
                </div>
              </div>
              <div style={STYLE.card}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>期望值 (EV)</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: kellyResult.ev_pct > 0 ? '#3fb950' : '#f85149' }}>
                  {kellyResult.ev_pct > 0 ? '+' : ''}{kellyResult.ev_pct.toFixed(2)}%
                </div>
              </div>
              <div style={STYLE.card}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>Kelly比例</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#58a6ff' }}>
                  {kellyResult.kelly_fractional_pct.toFixed(2)}%
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Full Kelly: {kellyResult.kelly_full_pct.toFixed(2)}%</div>
              </div>
              <div style={STYLE.card}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>建议仓位</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#3fb950' }}>
                  ${kellyResult.position_fractional.toFixed(2)}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>资金: ${kellyResult.bankroll}</div>
              </div>
              <div style={STYLE.card}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>潜在利润</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#f0883e' }}>
                  ${kellyResult.potential_profit.toFixed(2)}
                </div>
              </div>
              <div style={STYLE.card}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>风险评级</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: getRiskColor(kellyResult.risk_level) }}>
                  {kellyResult.risk_msg}
                </div>
              </div>
            </div>
          )}

          {kellyResult?.error && (
            <div style={STYLE.errorBox}>
              {kellyResult.error}
            </div>
          )}

          <div className="arb-risk-section" style={{ marginTop: 16 }}>
            <h4>Kelly公式说明</h4>
            <ul>
              <li><strong>Full Kelly</strong>: f* = (b*p - q) / b，其中 b = 赔率, p = 你估计的概率, q = 1-p</li>
              <li><strong>Fractional Kelly</strong>: 使用1/4 Kelly，牺牲部分收益换取更低的波动</li>
              <li><strong>优势(Edge)</strong>: 你估计的概率 - 市场隐含概率，正数表示你认为市场低估了</li>
              <li><strong>期望值(EV)</strong>: 每投入$1的预期收益</li>
              <li>Kelly公式假设你的概率估计是准确的，过度自信会导致过度下注</li>
            </ul>
          </div>
        </div>
      )}

      {/* Detail Tab */}
      {activeTab === 'detail' && (
        <div>
          {detailLoading ? (
            <div className="loading"><div className="spinner"></div>分析中...</div>
          ) : detailData ? (
            <>
              <div className="arb-notes" style={{ marginBottom: 16 }}>
                <div className="arb-note-item" style={{ gridColumn: 'span 2' }}>
                  <div className="note-label">市场问题</div>
                  <div className="note-value" style={{ fontSize: 15, fontWeight: 600 }}>
                    {detailData.market.question}
                  </div>
                </div>
                <div className="arb-note-item">
                  <div className="note-label">Yes价格</div>
                  <div className="note-value" style={{ fontSize: 18, fontWeight: 700, color: '#3fb950' }}>
                    {formatPrice(detailData.market.prices[0] || 0)}
                  </div>
                </div>
                <div className="arb-note-item">
                  <div className="note-label">No价格</div>
                  <div className="note-value" style={{ fontSize: 18, fontWeight: 700, color: '#f85149' }}>
                    {formatPrice(detailData.market.prices[1] || 0)}
                  </div>
                </div>
                <div className="arb-note-item">
                  <div className="note-label">趋势</div>
                  <div className="note-value" style={{
                    fontSize: 16, fontWeight: 700,
                    color: detailData.analysis.trend === 'bullish' ? '#3fb950' : detailData.analysis.trend === 'bearish' ? '#f85149' : '#8b949e'
                  }}>
                    {detailData.analysis.trend === 'bullish' ? '看涨' : detailData.analysis.trend === 'bearish' ? '看跌' : '中性'}
                  </div>
                </div>
                <div className="arb-note-item">
                  <div className="note-label">7天变动</div>
                  <div className="note-value" style={{
                    fontSize: 16, fontWeight: 700,
                    color: getTrendColor(detailData.analysis.price_change_7d)
                  }}>
                    {detailData.analysis.price_change_7d > 0 ? '+' : ''}{detailData.analysis.price_change_7d.toFixed(2)}%
                  </div>
                </div>
                <div className="arb-note-item">
                  <div className="note-label">流动性</div>
                  <div className="note-value" style={{ fontSize: 16, fontWeight: 700 }}>
                    {detailData.analysis.liquidity_score === 'high' ? '高' : detailData.analysis.liquidity_score === 'medium' ? '中' : '低'}
                  </div>
                </div>
              </div>

              {/* Price History */}
              {detailData.history && detailData.history.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>价格历史</h3>
                  <div style={{
                    display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'flex-end',
                    height: 120, padding: '8px 0',
                  }}>
                    {detailData.history.map((p, i) => {
                      const maxP = Math.max(...detailData.history.map(h => h.price))
                      const minP = Math.min(...detailData.history.map(h => h.price))
                      const range = maxP - minP || 1
                      const height = ((p.price - minP) / range) * 100 + 10
                      return (
                        <div key={i} style={{
                          flex: 1, minWidth: 4, maxWidth: 20,
                          height: `${height}%`,
                          background: p.price > 0.5 ? '#3fb95080' : '#f8514980',
                          borderRadius: 2,
                          position: 'relative',
                        }} title={`${new Date(p.timestamp).toLocaleDateString()}: $${p.price.toFixed(2)}`} />
                      )
                    })}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)' }}>
                    <span>{detailData.history[0] ? new Date(detailData.history[0].timestamp).toLocaleDateString() : ''}</span>
                    <span>{detailData.history[detailData.history.length - 1] ? new Date(detailData.history[detailData.history.length - 1].timestamp).toLocaleDateString() : ''}</span>
                  </div>
                </div>
              )}

              {/* Market Info */}
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>市场信息</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>成交量</div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>{formatVolume(detailData.market.volume)}</div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>流动性</div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>{formatLiq(detailData.market.liquidity)}</div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>到期日</div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>{detailData.market.end_date ? new Date(detailData.market.end_date).toLocaleDateString() : '-'}</div>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', padding: 12, borderRadius: 8 }}>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>标签</div>
                    <div style={{ fontSize: 16, fontWeight: 700 }}>{detailData.market.tag || '-'}</div>
                  </div>
                </div>
              </div>

              {/* Description */}
              {detailData.market.description && (
                <div className="arb-risk-section">
                  <h4>市场描述</h4>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {detailData.market.description}
                  </p>
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
              点击市场列表中的"分析"按钮查看详情
            </div>
          )}
        </div>
      )}
    </div>
  )
}
