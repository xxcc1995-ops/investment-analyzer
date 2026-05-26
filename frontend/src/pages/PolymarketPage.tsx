import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api/polymarket'

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

export default function PolymarketPage() {
  const [activeTab, setActiveTab] = useState<'markets' | 'arbitrage' | 'value' | 'trending' | 'kelly' | 'detail'>('markets')

  // Markets
  const [markets, setMarkets] = useState<Market[]>([])
  const [marketsLoading, setMarketsLoading] = useState(false)
  const [marketsTotal, setMarketsTotal] = useState(0)
  const [marketOrder, setMarketOrder] = useState('volume')
  const [marketTag, setMarketTag] = useState('')

  // Arbitrage
  const [arbOpps, setArbOpps] = useState<Market[]>([])
  const [arbLoading, setArbLoading] = useState(false)
  const [minProfit, setMinProfit] = useState(0.5)

  // Value
  const [valueData, setValueData] = useState<ValueMarkets | null>(null)
  const [valueLoading, setValueLoading] = useState(false)

  // Trending
  const [trending, setTrending] = useState<Market[]>([])
  const [trendingLoading, setTrendingLoading] = useState(false)

  // Kelly
  const [kellyPrice, setKellyPrice] = useState('')
  const [kellyProb, setKellyProb] = useState('')
  const [kellyBankroll, setKellyBankroll] = useState('1000')
  const [kellyResult, setKellyResult] = useState<KellyResult | null>(null)

  // Detail
  const [detailData, setDetailData] = useState<MarketAnalysis | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const loadMarkets = useCallback(async () => {
    setMarketsLoading(true)
    try {
      const params: Record<string, string | number> = { limit: 100, order: marketOrder }
      if (marketTag) params.tag = marketTag
      const res = await axios.get(`${API_BASE}/markets`, { params })
      setMarkets(res.data.markets || [])
      setMarketsTotal(res.data.total || 0)
    } catch (e) {
      console.error('获取市场失败:', e)
    } finally {
      setMarketsLoading(false)
    }
  }, [marketOrder, marketTag])

  const loadArbitrage = useCallback(async () => {
    setArbLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/arbitrage`, { params: { min_profit: minProfit } })
      setArbOpps(res.data.opportunities || [])
    } catch (e) {
      console.error('获取套利机会失败:', e)
    } finally {
      setArbLoading(false)
    }
  }, [minProfit])

  const loadValue = useCallback(async () => {
    setValueLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/value`)
      setValueData(res.data)
    } catch (e) {
      console.error('获取价值发现失败:', e)
    } finally {
      setValueLoading(false)
    }
  }, [])

  const loadTrending = useCallback(async () => {
    setTrendingLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/trending`)
      setTrending(res.data.markets || [])
    } catch (e) {
      console.error('获取趋势失败:', e)
    } finally {
      setTrendingLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (marketId: string) => {
    setDetailLoading(true)
    setActiveTab('detail')
    try {
      const res = await axios.get(`${API_BASE}/markets/${marketId}`)
      setDetailData(res.data)
    } catch (e) {
      console.error('获取市场详情失败:', e)
    } finally {
      setDetailLoading(false)
    }
  }, [])

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
    if (activeTab === 'value') loadValue()
    if (activeTab === 'trending') loadTrending()
  }, [activeTab, loadMarkets, loadArbitrage, loadValue, loadTrending])

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
          { key: 'value', label: '价值发现' },
          { key: 'trending', label: '趋势追踪' },
          { key: 'kelly', label: 'Kelly计算器' },
          { key: 'detail', label: '市场详情' },
        ].map(t => (
          <button key={t.key} className={`tab-btn ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key as any)}>{t.label}</button>
        ))}
      </div>

      {/* Markets Tab */}
      {activeTab === 'markets' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <select value={marketOrder} onChange={e => setMarketOrder(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value="volume">按成交量</option>
              <option value="liquidity">按流动性</option>
              <option value="startDate">按开始时间</option>
            </select>
            <select value={marketTag} onChange={e => setMarketTag(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
              <option value="">全部标签</option>
              <option value="Politics">政治</option>
              <option value="Crypto">加密货币</option>
              <option value="Sports">体育</option>
              <option value="Business">商业</option>
              <option value="Science">科学</option>
              <option value="Tech">科技</option>
            </select>
            <button onClick={loadMarkets}
              style={{ padding: '6px 16px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
              刷新
            </button>
            <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>共 {marketsTotal} 个市场</span>
          </div>

          {marketsLoading ? (
            <div className="loading"><div className="spinner"></div>加载中...</div>
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
                        style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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
            <div className="arb-note-item">
              <div className="note-label">套利原理</div>
              <div className="note-value" style={{ fontSize: 13 }}>
                当同一市场 Yes + No 价格 &lt; $1.00 时，买入双方即可锁定利润。
                例：Yes=$0.55, No=$0.40, 合计$0.95, 利润=$0.05 (5.26%)
              </div>
            </div>
            <div className="arb-note-item">
              <div className="note-label">最低利润</div>
              <div className="note-value">
                <select value={minProfit} onChange={e => setMinProfit(Number(e.target.value))}
                  style={{ padding: '4px 8px', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}>
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
              style={{ padding: '6px 16px', borderRadius: 6, background: '#3fb950', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
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
                        style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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

      {/* Value Tab */}
      {activeTab === 'value' && (
        <div>
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
                            style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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
                            style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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
                            style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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
                            style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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
            <div className="arb-note-item">
              <div className="note-label">策略思路</div>
              <div className="note-value" style={{ fontSize: 13 }}>
                价格7天内变动超过5%的市场可能有新的信息流入，值得关注。
                价格上涨说明市场认为Yes概率增加，反之亦然。
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
                        style={{ padding: '2px 8px', borderRadius: 4, background: '#58a6ff20', color: '#58a6ff', border: '1px solid #58a6ff40', cursor: 'pointer', fontSize: 12 }}>
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
              <div className="note-label">Kelly仓位计算</div>
              <div className="note-value" style={{ fontSize: 13 }}>
                Kelly公式帮你根据"优势"计算最优下注比例。输入市场价格和你估计的真实概率，
                系统会告诉你应该下注多少。默认使用1/4 Kelly（更保守）。
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
                style={{ width: '100%', padding: '8px 12px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>你估计的概率 (0.01-0.99)</label>
              <input type="number" min="0.01" max="0.99" step="0.01" placeholder="如 0.55"
                value={kellyProb} onChange={e => setKellyProb(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>总资金 ($)</label>
              <input type="number" min="1" step="100" placeholder="1000"
                value={kellyBankroll} onChange={e => setKellyBankroll(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={calcKelly}
                style={{ padding: '8px 24px', borderRadius: 6, background: '#58a6ff', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600, width: '100%' }}>
                计算
              </button>
            </div>
          </div>

          {kellyResult && !kellyResult.error && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 12, marginBottom: 16,
            }}>
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>优势 (Edge)</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: kellyResult.edge > 0 ? '#3fb950' : '#f85149' }}>
                  {kellyResult.edge_pct > 0 ? '+' : ''}{kellyResult.edge_pct.toFixed(2)}%
                </div>
              </div>
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>期望值 (EV)</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: kellyResult.ev_pct > 0 ? '#3fb950' : '#f85149' }}>
                  {kellyResult.ev_pct > 0 ? '+' : ''}{kellyResult.ev_pct.toFixed(2)}%
                </div>
              </div>
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>Kelly比例</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#58a6ff' }}>
                  {kellyResult.kelly_fractional_pct.toFixed(2)}%
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Full Kelly: {kellyResult.kelly_full_pct.toFixed(2)}%</div>
              </div>
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>建议仓位</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#3fb950' }}>
                  ${kellyResult.position_fractional.toFixed(2)}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>资金: ${kellyResult.bankroll}</div>
              </div>
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>潜在利润</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#f0883e' }}>
                  ${kellyResult.potential_profit.toFixed(2)}
                </div>
              </div>
              <div style={{
                background: 'var(--bg-secondary)', borderRadius: 8, padding: 16,
                border: '1px solid var(--border-primary)',
              }}>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>风险评级</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: getRiskColor(kellyResult.risk_level) }}>
                  {kellyResult.risk_msg}
                </div>
              </div>
            </div>
          )}

          {kellyResult?.error && (
            <div style={{ color: '#f85149', padding: 16, background: '#f8514920', borderRadius: 8 }}>
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
