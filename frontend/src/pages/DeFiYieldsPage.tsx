import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'

const API_BASE = '/api'

// --- Types ---

interface Pool {
  project: string
  chain: string
  symbol: string
  tvlUsd: number
  apy: number
  apyBase: number
  apyReward: number
  pool: string
  stablecoin: boolean
  ilRisk: string
}

interface Protocol {
  name: string
  tvl: number
  chain: string
  category: string
  change_1d: number | null
  change_7d: number | null
  change_1m: number | null
}

interface OverviewData {
  summary: {
    total_tvl: number
    total_pools: number
    avg_apy: number
    chain_count: number
  }
  top5_high_apy: Pool[]
  top5_tvl_protocols: Protocol[]
}

// --- Helpers ---

const formatTVL = (tvl: number): string => {
  if (tvl >= 1e9) return `$${(tvl / 1e9).toFixed(2)}B`
  if (tvl >= 1e6) return `$${(tvl / 1e6).toFixed(2)}M`
  if (tvl >= 1e3) return `$${(tvl / 1e3).toFixed(1)}K`
  return `$${tvl.toFixed(0)}`
}

const getApyColor = (apy: number): string => {
  if (apy >= 50) return '#f85149'
  if (apy >= 20) return '#faad14'
  if (apy >= 10) return 'var(--accent-blue)'
  return 'var(--text-primary)'
}

const getChangeColor = (val: number | null): string => {
  if (val == null) return 'var(--text-muted)'
  if (val > 0) return '#f85149'
  if (val < 0) return '#3fb950'
  return 'var(--text-muted)'
}

const formatChange = (val: number | null): string => {
  if (val == null) return '-'
  const sign = val > 0 ? '+' : ''
  return `${sign}${val.toFixed(2)}%`
}

// --- Shared style constants ---

const selectStyle: React.CSSProperties = {
  padding: '6px 12px',
  border: '1px solid var(--border-primary)',
  borderRadius: '4px',
  background: 'var(--bg-primary)',
  color: 'var(--text-primary)',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '12px',
  color: 'var(--text-muted)',
  marginBottom: '4px',
}

const filterContainerStyle: React.CSSProperties = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: '12px',
  margin: '16px 20px',
  padding: '16px',
  background: 'var(--bg-secondary)',
  borderRadius: '8px',
  border: '1px solid var(--border-primary)',
}

const badgeStyle: React.CSSProperties = {
  padding: '2px 8px',
  borderRadius: '4px',
  fontSize: '12px',
  background: 'var(--bg-tertiary, rgba(100,100,100,0.15))',
  color: 'var(--text-secondary)',
}

const refreshButtonStyle: React.CSSProperties = {
  padding: '6px 16px',
  background: 'var(--accent-blue)',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 600,
}

const statCardStyle: React.CSSProperties = {
  padding: '16px',
  borderRadius: '8px',
  background: 'var(--bg-secondary)',
  border: '1px solid var(--border-primary)',
  textAlign: 'center',
}

const emptyRowStyle: React.CSSProperties = {
  textAlign: 'center',
  padding: '40px',
  color: 'var(--text-muted)',
}

// --- Component ---

export default function DeFiYieldsPage() {
  // Tab state
  const [activeTab, setActiveTab] = useState<'pools' | 'protocols'>('pools')

  // Pools tab state
  const [pools, setPools] = useState<Pool[]>([])
  const [poolsLoading, setPoolsLoading] = useState(false)
  const [poolsError, setPoolsError] = useState<string | null>(null)
  const [selectedChain, setSelectedChain] = useState('all')
  const [minTvl, setMinTvl] = useState(1_000_000)
  const [stablecoinFilter, setStablecoinFilter] = useState<'all' | 'only' | 'exclude'>('all')
  const [sortBy, setSortBy] = useState<'tvl' | 'apy'>('tvl')

  // Protocols tab state
  const [protocols, setProtocols] = useState<Protocol[]>([])
  const [protocolsLoading, setProtocolsLoading] = useState(false)
  const [protocolsError, setProtocolsError] = useState<string | null>(null)

  // Shared state
  const [chains, setChains] = useState<string[]>([])
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [overviewError, setOverviewError] = useState<string | null>(null)

  // --- Load chains list ---
  const loadChains = useCallback(async () => {
    try {
      const res = await axios.get<{ chains?: string[] }>(`${API_BASE}/defi/chains`)
      setChains(res.data.chains ?? [])
    } catch {
      // chains list is non-critical; silently degrade
    }
  }, [])

  // --- Load overview ---
  const loadOverview = useCallback(async () => {
    setOverviewError(null)
    try {
      const res = await axios.get<OverviewData>(`${API_BASE}/defi/overview`)
      setOverview(res.data)
    } catch {
      setOverviewError('获取概览数据失败')
    }
  }, [])

  // --- Load pools ---
  const loadPools = useCallback(async () => {
    setPoolsLoading(true)
    setPoolsError(null)
    try {
      const params: Record<string, string | number> = {
        min_tvl: minTvl,
        sort_by: sortBy,
        limit: 100,
      }
      if (selectedChain !== 'all') params.chain = selectedChain
      if (stablecoinFilter === 'only') params.stablecoin = 'true'
      if (stablecoinFilter === 'exclude') params.stablecoin = 'false'

      const res = await axios.get<{ data?: Pool[] }>(`${API_BASE}/defi/pools`, { params })
      setPools(res.data.data ?? [])
    } catch {
      setPoolsError('获取收益率池数据失败，请稍后重试')
    } finally {
      setPoolsLoading(false)
    }
  }, [selectedChain, minTvl, stablecoinFilter, sortBy])

  // --- Load protocols ---
  const loadProtocols = useCallback(async () => {
    setProtocolsLoading(true)
    setProtocolsError(null)
    try {
      const res = await axios.get<{ data?: Protocol[] }>(`${API_BASE}/defi/protocols`)
      setProtocols(res.data.data ?? [])
    } catch {
      setProtocolsError('获取协议数据失败，请稍后重试')
    } finally {
      setProtocolsLoading(false)
    }
  }, [])

  // --- Effects ---
  useEffect(() => { loadChains() }, [loadChains])
  useEffect(() => { loadOverview() }, [loadOverview])
  useEffect(() => { loadPools() }, [loadPools])
  useEffect(() => { if (activeTab === 'protocols') loadProtocols() }, [activeTab, loadProtocols])

  // --- Memoized stats cards ---
  const statsCards = useMemo(() => {
    if (!overview) return []
    const s = overview.summary
    return [
      { label: '总池数', value: s.total_pools.toLocaleString() },
      { label: '总TVL', value: formatTVL(s.total_tvl) },
      { label: '平均APY', value: `${s.avg_apy.toFixed(2)}%` },
      {
        label: '最高APY',
        value: overview.top5_high_apy.length > 0
          ? `${overview.top5_high_apy[0].apy.toFixed(2)}%`
          : '-',
      },
      { label: '链数量', value: String(s.chain_count) },
    ]
  }, [overview])

  // --- Tab button handler factory ---
  const handleTabClick = useCallback(
    (tab: 'pools' | 'protocols') => () => setActiveTab(tab),
    [],
  )

  // --- Error banner ---
  const renderError = (msg: string | null) => {
    if (!msg) return null
    return (
      <div style={{
        margin: '16px 20px 0',
        padding: '12px 16px',
        background: 'rgba(248, 81, 73, 0.1)',
        border: '1px solid rgba(248, 81, 73, 0.3)',
        borderRadius: '6px',
        color: '#f85149',
        fontSize: '13px',
      }}>
        {msg}
      </div>
    )
  }

  return (
    <div className="fund-est-page">
      {/* Page header */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>DeFi收益率排行榜</h2>
            <span className="stock-code">基于DeFiLlama数据 - 实时追踪DeFi协议收益率</span>
          </div>
        </div>
      </div>

      {/* Tab switcher */}
      <div style={{
        display: 'flex', gap: '0', margin: '16px 20px 0',
        borderBottom: '2px solid var(--border-primary)',
      }}>
        {(['pools', 'protocols'] as const).map(tab => (
          <button
            key={tab}
            onClick={handleTabClick(tab)}
            style={{
              padding: '10px 24px',
              background: activeTab === tab ? 'var(--accent-blue)' : 'transparent',
              color: activeTab === tab ? '#fff' : 'var(--text-secondary)',
              border: 'none',
              borderRadius: '6px 6px 0 0',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '14px',
              transition: 'all 0.2s',
            }}
          >
            {tab === 'pools' ? '收益率池' : '协议排行'}
          </button>
        ))}
      </div>

      {/* ======================= Tab 1: Pools ======================= */}
      {activeTab === 'pools' && (
        <>
          {/* Stats cards */}
          {overview && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '12px',
              margin: '16px 20px',
            }}>
              {statsCards.map(item => (
                <div key={item.label} style={statCardStyle}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {item.value}
                  </div>
                </div>
              ))}
            </div>
          )}

          {renderError(overviewError)}

          {/* Filters */}
          <div style={filterContainerStyle}>
            <div>
              <label style={labelStyle}>链</label>
              <select
                value={selectedChain}
                onChange={e => setSelectedChain(e.target.value)}
                style={selectStyle}
              >
                <option value="all">All Chains</option>
                {chains.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>最低TVL</label>
              <select
                value={minTvl}
                onChange={e => setMinTvl(Number(e.target.value))}
                style={selectStyle}
              >
                <option value={100_000}>$100K</option>
                <option value={1_000_000}>$1M</option>
                <option value={5_000_000}>$5M</option>
                <option value={10_000_000}>$10M</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>稳定币</label>
              <select
                value={stablecoinFilter}
                onChange={e => setStablecoinFilter(e.target.value as 'all' | 'only' | 'exclude')}
                style={selectStyle}
              >
                <option value="all">全部</option>
                <option value="only">仅稳定币</option>
                <option value="exclude">排除稳定币</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>排序方式</label>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value as 'tvl' | 'apy')}
                style={selectStyle}
              >
                <option value="tvl">按TVL</option>
                <option value="apy">按APY</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={loadPools} style={refreshButtonStyle}>
                刷新数据
              </button>
            </div>
          </div>

          {/* Pools table */}
          {poolsLoading ? (
            <div className="loading">
              <div className="spinner"></div>
              加载中...
            </div>
          ) : renderError(poolsError) || (
            <div className="table-container" style={{ margin: '0 20px' }}>
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>协议</th>
                    <th>链</th>
                    <th>代币</th>
                    <th>TVL</th>
                    <th>APY</th>
                    <th>基础APY</th>
                    <th>奖励APY</th>
                    <th>稳定币</th>
                    <th>无常损失</th>
                  </tr>
                </thead>
                <tbody>
                  {pools.map((pool, idx) => (
                    <tr key={pool.pool}>
                      <td style={{ color: 'var(--text-muted)' }}>{idx + 1}</td>
                      <td style={{ fontWeight: 600 }}>{pool.project}</td>
                      <td><span style={badgeStyle}>{pool.chain}</span></td>
                      <td style={{ fontWeight: 500 }}>{pool.symbol}</td>
                      <td style={{ fontWeight: 600 }}>{formatTVL(pool.tvlUsd)}</td>
                      <td style={{ color: getApyColor(pool.apy), fontWeight: 700, fontSize: '15px' }}>
                        {pool.apy.toFixed(2)}%
                      </td>
                      <td>{pool.apyBase != null ? `${pool.apyBase.toFixed(2)}%` : '-'}</td>
                      <td>{pool.apyReward != null ? `${pool.apyReward.toFixed(2)}%` : '-'}</td>
                      <td style={{ textAlign: 'center' }}>
                        {pool.stablecoin ? (
                          <span style={{
                            display: 'inline-block', padding: '2px 8px', borderRadius: '4px',
                            background: 'rgba(82, 196, 26, 0.15)', color: '#3fb950',
                            fontSize: '12px', fontWeight: 600,
                          }}>
                            Yes
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>No</span>
                        )}
                      </td>
                      <td style={{
                        color: pool.ilRisk === 'yes' ? '#f85149' : 'var(--text-muted)',
                        fontWeight: pool.ilRisk === 'yes' ? 600 : 400,
                      }}>
                        {pool.ilRisk === 'yes' ? '有风险' : '低风险'}
                      </td>
                    </tr>
                  ))}
                  {pools.length === 0 && (
                    <tr>
                      <td colSpan={10} style={emptyRowStyle}>
                        暂无符合条件的收益率池数据
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ======================= Tab 2: Protocols ======================= */}
      {activeTab === 'protocols' && (
        <>
          {/* Filters for protocols */}
          <div style={filterContainerStyle}>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={loadProtocols} style={refreshButtonStyle}>
                刷新数据
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                按TVL降序排列，共 {protocols.length} 个协议
              </span>
            </div>
          </div>

          {/* Protocols table */}
          {protocolsLoading ? (
            <div className="loading">
              <div className="spinner"></div>
              加载中...
            </div>
          ) : renderError(protocolsError) || (
            <div className="table-container" style={{ margin: '0 20px' }}>
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>协议名称</th>
                    <th>类别</th>
                    <th>链</th>
                    <th>TVL</th>
                    <th>24h变化</th>
                    <th>7d变化</th>
                    <th>30d变化</th>
                  </tr>
                </thead>
                <tbody>
                  {protocols.map((proto, idx) => (
                    <tr key={proto.name}>
                      <td style={{ color: 'var(--text-muted)' }}>{idx + 1}</td>
                      <td style={{ fontWeight: 600 }}>{proto.name}</td>
                      <td><span style={badgeStyle}>{proto.category || '-'}</span></td>
                      <td><span style={badgeStyle}>{proto.chain}</span></td>
                      <td style={{ fontWeight: 600 }}>{formatTVL(proto.tvl)}</td>
                      <td style={{ color: getChangeColor(proto.change_1d), fontWeight: 600 }}>
                        {formatChange(proto.change_1d)}
                      </td>
                      <td style={{ color: getChangeColor(proto.change_7d), fontWeight: 600 }}>
                        {formatChange(proto.change_7d)}
                      </td>
                      <td style={{ color: getChangeColor(proto.change_1m), fontWeight: 600 }}>
                        {formatChange(proto.change_1m)}
                      </td>
                    </tr>
                  ))}
                  {protocols.length === 0 && (
                    <tr>
                      <td colSpan={8} style={emptyRowStyle}>
                        暂无协议数据
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Notes section */}
      <div className="arb-notes" style={{ margin: '16px 20px' }}>
        <h3>DeFi收益率数据说明</h3>
        <div className="arb-notes-grid">
          <div className="arb-note-item">
            <span className="arb-note-label">数据来源</span>
            <span className="arb-note-value">DeFiLlama</span>
            <span className="arb-note-desc">
              所有收益率和TVL数据来自DeFiLlama聚合API，覆盖主流DeFi协议和链。
            </span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">APY说明</span>
            <span className="arb-note-value">可能包含刷量</span>
            <span className="arb-note-desc">
              部分协议的APY可能被刷量虚高，建议关注TVL大于$1M的池子，数据相对可靠。
              基础APY来自借贷/交易手续费，奖励APY来自代币激励。
            </span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">稳定币池</span>
            <span className="arb-note-value">低风险低收益</span>
            <span className="arb-note-desc">
              稳定币池（USDT/USDC/DAI等）无常损失极低，适合保守型投资者。
              但APY通常低于非稳定币池，且存在智能合约和脱锚风险。
            </span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">无常损失</span>
            <span className="arb-note-value">提供流动性核心风险</span>
            <span className="arb-note-desc">
              当池中代币价格比例发生变化时，流动性提供者可能遭受无常损失。
              稳定币对的无常损失极小，而波动性代币对的无常损失可能很大。
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
