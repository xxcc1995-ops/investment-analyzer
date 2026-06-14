/**
 * 可转债 + 加密 + 空投标签页
 * 双低策略 + 可转债事件 + 币圈行情 + DeFi 空投
 */
import { useState, useEffect, useCallback } from 'react'
import { dailyInfoApi } from '../../services/api'
import type { ConvertibleBondData, CryptoData, AirdropData, CryptoCoin } from './types'
import { formatPct, formatPrice, formatUSD, getChangeColor } from './utils'

interface Props {
  cbData?: ConvertibleBondData | null
  cryptoData?: CryptoData | null
  airdropData?: AirdropData | null
}

export default function CryptoTab({ cbData, cryptoData, airdropData }: Props) {
  const [cb, setCb] = useState<ConvertibleBondData | null>(cbData || null)
  const [crypto, setCrypto] = useState<CryptoData | null>(cryptoData || null)
  const [airdrops, setAirdrops] = useState<AirdropData | null>(airdropData || null)
  const [loading, setLoading] = useState(!cbData && !cryptoData && !airdropData)
  const [section, setSection] = useState<'cb' | 'crypto' | 'airdrop'>('crypto')

  const loadData = useCallback(async () => {
    if (cbData && cryptoData && airdropData) return
    setLoading(true)
    try {
      await Promise.allSettled([
        !cbData && dailyInfoApi.getConvertibleBonds().then(r => setCb(r.data as unknown as ConvertibleBondData)),
        !cryptoData && dailyInfoApi.getCrypto().then(r => setCrypto(r.data as unknown as CryptoData)),
        !airdropData && dailyInfoApi.getAirdrops().then(r => setAirdrops(r.data as unknown as AirdropData)),
      ].filter(Boolean))
    } catch {} finally {
      setLoading(false)
    }
  }, [cbData, cryptoData, airdropData])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>加载中...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 切换 */}
      <div style={{ display: 'flex', gap: 8 }}>
        {([['crypto', '₿ 加密市场'], ['cb', '📄 可转债'], ['airdrop', '🪙 空投机会']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setSection(key)} style={{
            padding: '6px 16px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
            border: section === key ? '1px solid var(--accent-blue)' : '1px solid var(--border-primary)',
            background: section === key ? 'rgba(88,166,255,0.15)' : 'var(--bg-secondary)',
            color: section === key ? 'var(--accent-blue)' : 'var(--text-secondary)',
            fontWeight: section === key ? 600 : 400,
          }}>{label}</button>
        ))}
      </div>

      {section === 'crypto' && crypto && <CryptoSection data={crypto} />}
      {section === 'cb' && cb && <CBSection data={cb} />}
      {section === 'airdrop' && airdrops && <AirdropSection data={airdrops} />}
    </div>
  )
}

// ==================== 加密市场 ====================

function CryptoSection({ data }: { data: CryptoData }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 稳定币市值 */}
      {data.stablecoin_mcap && (
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-md)', padding: 12,
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{ fontSize: 14 }}>💵</span>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>稳定币总市值</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
            ${data.stablecoin_mcap.toFixed(1)}B
          </span>
        </div>
      )}

      {/* 市值 Top 10 */}
      <TableSection title="🪙 市值 Top 10">
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              <th style={thStyle}>#</th>
              <th style={thStyle}>币种</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>价格</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>24h</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>市值</th>
            </tr>
          </thead>
          <tbody>
            {data.market_overview?.map((coin, i) => (
              <CoinRow key={coin.symbol} coin={coin} rank={i + 1} />
            ))}
          </tbody>
        </table>
      </TableSection>

      {/* 涨幅 Top 10 */}
      <TableSection title="🚀 24h 涨幅 Top 10">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 8 }}>
          {data.top_gainers?.map((coin, i) => (
            <div key={coin.symbol || i} style={{
              background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-sm)', padding: 10,
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{coin.name}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{coin.symbol}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: getChangeColor(coin.change_24h), marginTop: 4 }}>
                {formatPct(coin.change_24h)}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{formatPrice(coin.price)}</div>
            </div>
          ))}
        </div>
      </TableSection>
    </div>
  )
}

function CoinRow({ coin, rank }: { coin: CryptoCoin; rank: number }) {
  return (
    <tr style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
      <td style={tdStyle}>{rank}</td>
      <td style={tdStyle}>
        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{coin.name}</span>
        <span style={{ color: 'var(--text-muted)', marginLeft: 4, fontSize: 10 }}>{coin.symbol}</span>
      </td>
      <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPrice(coin.price)}</td>
      <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, color: getChangeColor(coin.change_24h) }}>
        {formatPct(coin.change_24h)}
      </td>
      <td style={{ ...tdStyle, textAlign: 'right', color: 'var(--text-secondary)' }}>{formatUSD(coin.market_cap)}</td>
    </tr>
  )
}

// ==================== 可转债 ====================

function CBSection({ data }: { data: ConvertibleBondData }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 双低策略 */}
      <TableSection title="📊 双低策略 Top 10" count={data.hot_bonds?.length}>
        {data.hot_bonds?.length > 0 ? (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={thStyle}>名称</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>价格</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>溢价率</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>双低值</th>
                </tr>
              </thead>
              <tbody>
                {data.hot_bonds.slice(0, 10).map((b: any, i: number) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
                    <td style={{ ...tdStyle, fontWeight: 500, color: 'var(--text-primary)' }}>{b.name || b.bond_name || '--'}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPrice(b.price || b.close)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPct(b.premium)}</td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, color: 'var(--accent-blue)' }}>
                      {b.double_low || b.double_low_value || '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty msg="暂无双低策略数据" />}
      </TableSection>

      {/* 可转债事件 */}
      <TableSection title="📌 可转债事件" count={data.events?.length}>
        {data.events?.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {data.events.map((e, i) => (
              <div key={i} style={{
                padding: '6px 0', borderBottom: '1px solid rgba(48,54,61,0.3)',
                display: 'flex', gap: 8, fontSize: 12, alignItems: 'center',
              }}>
                <span style={{
                  fontSize: 10, padding: '0 4px', borderRadius: 3, flexShrink: 0,
                  background: e.event === '强制赎回' ? 'rgba(248,81,73,0.15)' : 'var(--bg-tertiary)',
                  color: e.event === '强制赎回' ? '#f85149' : 'var(--text-muted)',
                }}>{e.event}</span>
                <span style={{ flex: 1, color: 'var(--text-primary)' }}>{e.name}</span>
                {e.code && <span style={{ color: 'var(--accent-blue)', fontSize: 11 }}>{e.code}</span>}
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{e.date}</span>
              </div>
            ))}
          </div>
        ) : <Empty msg="暂无可转债事件" />}
      </TableSection>
    </div>
  )
}

// ==================== 空投 ====================

function AirdropSection({ data }: { data: AirdropData }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 未发币高 TVL 协议 */}
      <TableSection title="🎯 未发币高 TVL 协议" count={data.defi_protocols?.length}>
        {data.defi_protocols?.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                <th style={thStyle}>协议</th>
                <th style={thStyle}>链</th>
                <th style={thStyle}>类型</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>TVL</th>
              </tr>
            </thead>
            <tbody>
              {data.defi_protocols.map((p, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
                  <td style={tdStyle}>
                    {p.url ? (
                      <a href={p.url} target="_blank" rel="noopener noreferrer" style={{
                        fontWeight: 500, color: 'var(--accent-blue)', textDecoration: 'none',
                      }}>{p.name}</a>
                    ) : <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{p.name}</span>}
                  </td>
                  <td style={tdStyle}>{p.chain}</td>
                  <td style={tdStyle}>{p.category}</td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, color: 'var(--text-primary)' }}>
                    ${p.tvl.toFixed(0)}M
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty msg="暂无空投协议数据" />}
      </TableSection>

      {/* 空投信号 */}
      {data.potential_airdrops?.length > 0 && (
        <TableSection title="📡 空投新闻信号" count={data.potential_airdrops.length}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {data.potential_airdrops.map((a, i) => (
              <div key={i} style={{
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-sm)', padding: 10,
              }}>
                <a href={a.url} target="_blank" rel="noopener noreferrer" style={{
                  fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', textDecoration: 'none',
                }}>{a.name}</a>
                {a.description && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{a.description}</div>
                )}
              </div>
            ))}
          </div>
        </TableSection>
      )}
    </div>
  )
}

// ==================== 通用组件 ====================

function TableSection({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
        {count != null && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{count} 条</span>}
      </div>
      {children}
    </div>
  )
}

function Empty({ msg }: { msg: string }) {
  return <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '12px 0', textAlign: 'center' }}>{msg}</div>
}

const thStyle: React.CSSProperties = {
  padding: '6px 8px', textAlign: 'left', fontWeight: 600, fontSize: 11,
  color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-primary)',
}
const tdStyle: React.CSSProperties = {
  padding: '6px 8px', color: 'var(--text-secondary)',
}
