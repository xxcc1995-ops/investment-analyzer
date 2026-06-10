import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'

const API_BASE = '/api'

// --- Types ---

interface Holding {
  code: string
  name: string
  ticker: string
  weight: number
  price: number
  prev_close: number
  change_pct: number
  weighted_contribution: number
}

interface HoldingsData {
  fund_code: string
  fund_name: string
  currency: string
  report_date: string
  source: string
  total_weight: number
  holdings: Holding[]
  weighted_change: number
  fund_price: number
  fund_change_pct: number
  est_nav: number
  est_nav_from_api: number
  est_change: string
  official_nav: number
  official_nav_date: string
  premium: number
  usdcny_rate: number
  update_time: string
}

interface FundOption {
  fund_code: string
  fund_name: string
  currency: string
}

// --- Pure helpers (stable references, no re-creation per render) ---

function getChangeColor(val: number): string {
  if (val > 0) return '#f85149'
  if (val < 0) return '#3fb950'
  return 'var(--text-muted)'
}

function formatPrice(price: number): string {
  if (price >= 1000) return price.toFixed(2)
  if (price >= 10) return price.toFixed(3)
  return price.toFixed(4)
}

function formatSigned(value: number, decimals: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(decimals)}`
}

// --- Shared style builders ---

const CARD_BASE: React.CSSProperties = {
  padding: '16px',
  background: 'var(--bg-secondary)',
  borderRadius: '8px',
  border: '1px solid var(--border-primary)',
  textAlign: 'center',
}

const CARD_LABEL: React.CSSProperties = {
  fontSize: '12px',
  color: 'var(--text-muted)',
  marginBottom: '8px',
}

const CARD_VALUE: React.CSSProperties = {
  fontSize: '24px',
  fontWeight: 700,
}

const CARD_SUB: React.CSSProperties = {
  fontSize: '11px',
  color: 'var(--text-muted)',
  marginTop: '4px',
}

function premiumCardStyle(premium: number): React.CSSProperties {
  const bg =
    premium > 2 ? 'rgba(248,81,73,0.1)' :
    premium < -2 ? 'rgba(82,196,26,0.1)' :
    'var(--bg-secondary)'
  const borderColor =
    premium > 2 ? 'rgba(248,81,73,0.3)' :
    premium < -2 ? 'rgba(82,196,26,0.3)' :
    'var(--border-primary)'
  return { ...CARD_BASE, background: bg, border: `1px solid ${borderColor}` }
}

// --- Component ---

export default function FundHoldingsPage() {
  const [fundList, setFundList] = useState<FundOption[]>([])
  const [selectedFund, setSelectedFund] = useState('')
  const [data, setData] = useState<HoldingsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)

  // Load supported fund list
  useEffect(() => {
    axios.get(`${API_BASE}/fund-est/holdings-list`)
      .then(res => {
        const funds: FundOption[] = res.data.funds ?? []
        setFundList(funds)
        if (funds.length > 0) {
          setSelectedFund(funds[0].fund_code)
        }
      })
      .catch(() => setError('获取基金列表失败，请检查后端服务'))
  }, [])

  // Load holdings data
  const loadHoldings = useCallback(async (fundCode: string) => {
    if (!fundCode) return
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get(`${API_BASE}/fund-est/holdings/${fundCode}`)
      if (res.data.error) {
        setError(res.data.error)
        setData(null)
      } else {
        setData(res.data)
      }
    } catch {
      setError('获取持仓数据失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedFund) loadHoldings(selectedFund)
  }, [selectedFund, loadHoldings])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || !selectedFund) return
    const timer = setInterval(() => loadHoldings(selectedFund), 30000)
    return () => clearInterval(timer)
  }, [autoRefresh, selectedFund, loadHoldings])

  // Derived values
  const deviation = useMemo(
    () => (data ? data.weighted_change - data.fund_change_pct : 0),
    [data],
  )

  const navDiff = useMemo(
    () => (data && data.est_nav > 0 ? data.fund_price - data.est_nav : 0),
    [data],
  )

  const sourceLabel = useMemo(() => {
    if (!data) return '--'
    return data.source === 'eastmoney' ? '东方财富' : data.source
  }, [data])

  // --- Render helpers ---

  const renderStatCard = (
    label: string,
    value: React.ReactNode,
    sub?: React.ReactNode,
    extraStyle?: React.CSSProperties,
  ) => (
    <div style={{ ...CARD_BASE, ...extraStyle }}>
      <div style={CARD_LABEL}>{label}</div>
      <div style={CARD_VALUE}>{value}</div>
      {sub && <div style={CARD_SUB}>{sub}</div>}
    </div>
  )

  // --- Main render ---

  return (
    <div className="fund-est-page">
      {/* Page header */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>LOF基金持仓组合实时跟踪</h2>
            <span className="stock-code">
              按基金持仓比例构建组合，实时跟踪底层标的净值变化
            </span>
          </div>
        </div>
      </div>

      {/* Description */}
      <div className="arb-notes" style={{ margin: '16px 20px' }}>
        <h3>功能说明</h3>
        <div className="arb-notes-content">
          <div className="arb-risk-section">
            <h4>为什么需要持仓跟踪？</h4>
            <ul>
              <li>QDII LOF基金的底层资产在海外交易，与国内存在<strong>时差</strong></li>
              <li>基金公司公布的净值通常<strong>延迟1-2天</strong>（T-1或T-2）</li>
              <li>通过持仓组合可以<strong>实时估算</strong>底层资产的价格变动</li>
              <li>帮助判断场内价格的<strong>合理区间</strong>，辅助套利决策</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>计算方式</h4>
            <ul>
              <li>持仓数据来源：东方财富基金季报 / 基金公司公开披露</li>
              <li>实时价格来源：新浪财经API</li>
              <li>组合涨跌幅 = Σ(每只股票涨跌幅 × 持仓权重)</li>
              <li>该涨跌幅反映底层资产相对于上一个交易日收盘价的变化</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '12px', margin: '16px 20px',
        padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
        border: '1px solid var(--border-primary)', alignItems: 'flex-end',
      }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            选择基金
          </label>
          <select
            value={selectedFund}
            onChange={e => setSelectedFund(e.target.value)}
            style={{
              padding: '6px 12px', border: '1px solid var(--border-primary)',
              borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
              minWidth: '200px',
            }}
          >
            {fundList.map(f => (
              <option key={f.fund_code} value={f.fund_code}>
                {f.fund_name} ({f.fund_code})
              </option>
            ))}
          </select>
        </div>
        <div>
          <button
            onClick={() => loadHoldings(selectedFund)}
            disabled={loading || !selectedFund}
            style={{
              padding: '6px 16px', background: 'var(--accent-blue)', color: '#fff',
              border: 'none', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600, opacity: loading ? 0.6 : 1,
            }}
          >
            刷新数据
          </button>
        </div>
        <div>
          <button
            onClick={() => setAutoRefresh(prev => !prev)}
            style={{
              padding: '6px 16px',
              background: autoRefresh ? '#3fb950' : 'var(--bg-primary)',
              color: autoRefresh ? '#fff' : 'var(--text-primary)',
              border: `1px solid ${autoRefresh ? '#3fb950' : 'var(--border-primary)'}`,
              borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
            }}
          >
            {autoRefresh ? '自动刷新中 (30s)' : '开启自动刷新'}
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div style={{
          margin: '16px 20px', padding: '16px',
          background: 'rgba(248,81,73,0.08)', borderRadius: '8px',
          border: '1px solid rgba(248,81,73,0.3)', color: '#f85149',
        }}>
          {error}
        </div>
      )}

      {/* Loading state (initial load only) */}
      {loading && !data && (
        <div className="loading">
          <div className="spinner"></div>
          加载中...
        </div>
      )}

      {/* Data display */}
      {!loading && !error && !data && (
        <div style={{
          textAlign: 'center', padding: '60px', color: 'var(--text-muted)', fontSize: '16px',
        }}>
          请选择一只基金查看持仓组合
        </div>
      )}

      {data && (
        <>
          {/* Overview cards */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: '12px', margin: '16px 20px',
          }}>
            {renderStatCard(
              '组合加权涨跌幅',
              <span style={{ color: getChangeColor(data.weighted_change) }}>
                {formatSigned(data.weighted_change, 2)}%
              </span>,
            )}
            {renderStatCard(
              '基金场内价格',
              <span style={{ color: 'var(--text-primary)' }}>
                {data.fund_price > 0 ? data.fund_price.toFixed(3) : '--'}
              </span>,
              <span style={{ color: getChangeColor(data.fund_change_pct) }}>
                {formatSigned(data.fund_change_pct, 2)}%
              </span>,
            )}
            {renderStatCard(
              'EST估算净值',
              <span style={{ color: 'var(--accent-blue)' }}>
                {data.est_nav > 0 ? data.est_nav.toFixed(4) : '--'}
              </span>,
              <>
                官方净值: {data.official_nav > 0 ? data.official_nav.toFixed(4) : '--'}
                {data.official_nav_date && <span> ({data.official_nav_date})</span>}
              </>,
            )}
            {renderStatCard(
              '溢价率 (EST)',
              <span style={{
                color: data.premium > 2 ? '#f85149' : data.premium < -2 ? '#3fb950' : 'var(--text-primary)',
              }}>
                {formatSigned(data.premium, 2)}%
              </span>,
              <>
                {navDiff > 0 ? '场内 > EST' : '场内 < EST'}
                {data.est_nav > 0 && ` (${formatSigned(navDiff, 4)})`}
              </>,
              premiumCardStyle(data.premium),
            )}
            {renderStatCard(
              '底层vs场内 偏离',
              <span style={{ color: getChangeColor(deviation) }}>
                {formatSigned(deviation, 2)}%
              </span>,
              '底层涨跌 - 场内涨跌',
            )}
            {renderStatCard(
              '美元人民币中间价',
              <span style={{ color: 'var(--text-primary)' }}>
                {data.usdcny_rate > 0 ? data.usdcny_rate.toFixed(4) : '--'}
              </span>,
            )}
          </div>

          {/* Data freshness */}
          <div className="data-freshness" style={{ margin: '0 20px 16px' }}>
            <span className="freshness-tag">更新时间: {data.update_time}</span>
            <span className="freshness-tag">数据来源: {sourceLabel}</span>
            <span className="freshness-tag">报告期: {data.report_date || '--'}</span>
            <span className="freshness-tag">持仓覆盖: {(data.total_weight * 100).toFixed(1)}%</span>
            <span className="freshness-tag">持仓数量: {data.holdings.length}</span>
          </div>

          {/* Holdings table */}
          <div className="table-container" style={{ margin: '0 20px' }}>
            <table className="arb-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>代码</th>
                  <th>名称</th>
                  <th>权重</th>
                  <th>实时价格</th>
                  <th>涨跌幅</th>
                  <th>加权贡献</th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((h, i) => {
                  const hasPrice = h.price > 0
                  return (
                    <tr key={h.code}>
                      <td style={{ color: 'var(--text-muted)' }}>{i + 1}</td>
                      <td style={{ fontWeight: 600, fontSize: '12px' }}>
                        {h.ticker || h.code}
                      </td>
                      <td>{h.name}</td>
                      <td style={{ textAlign: 'center' }}>
                        {(h.weight * 100).toFixed(1)}%
                      </td>
                      <td style={{ fontWeight: 600, textAlign: 'right' }}>
                        {hasPrice ? formatPrice(h.price) : '--'}
                      </td>
                      <td style={{
                        color: getChangeColor(h.change_pct),
                        fontWeight: 600,
                        textAlign: 'right',
                      }}>
                        {hasPrice ? `${formatSigned(h.change_pct, 2)}%` : '--'}
                      </td>
                      <td style={{
                        color: getChangeColor(h.weighted_contribution),
                        fontWeight: 600,
                        textAlign: 'right',
                      }}>
                        {hasPrice ? `${formatSigned(h.weighted_contribution, 4)}%` : '--'}
                      </td>
                    </tr>
                  )
                })}
                {/* Summary row */}
                <tr style={{
                  background: 'var(--bg-secondary)',
                  fontWeight: 700,
                  borderTop: '2px solid var(--border-primary)',
                }}>
                  <td></td>
                  <td></td>
                  <td style={{ textAlign: 'right' }}>合计</td>
                  <td style={{ textAlign: 'center' }}>
                    {(data.total_weight * 100).toFixed(1)}%
                  </td>
                  <td></td>
                  <td></td>
                  <td style={{
                    color: getChangeColor(data.weighted_change),
                    fontSize: '15px',
                    textAlign: 'right',
                  }}>
                    {formatSigned(data.weighted_change, 2)}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Risk notes */}
          <div className="arb-notes" style={{ margin: '16px 20px' }}>
            <h3>风险提示</h3>
            <div className="arb-notes-grid">
              <div className="arb-note-item">
                <span className="arb-note-label">持仓数据滞后</span>
                <span className="arb-note-value">基于基金季报披露</span>
                <span className="arb-note-desc">
                  持仓数据来自最近一期基金季报，实际持仓可能已发生变化。基金可能在季度间调仓。
                </span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">权重不完全</span>
                <span className="arb-note-value">仅覆盖前十大重仓</span>
                <span className="arb-note-desc">
                  通常只展示前10-15大重仓股，剩余持仓未纳入计算。覆盖比例见上方"持仓覆盖"指标。
                </span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">汇率影响</span>
                <span className="arb-note-value">QDII基金有汇率敞口</span>
                <span className="arb-note-desc">
                  组合涨跌幅基于底层资产的美元/港币价格，未包含汇率变动对基金净值的影响。
                </span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">仅供参考</span>
                <span className="arb-note-value">不构成投资建议</span>
                <span className="arb-note-desc">
                  估算结果仅供参考，实际净值以基金公司公布为准。套利有风险，请谨慎决策。
                </span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
