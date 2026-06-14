/**
 * 套利机会标签页
 * 并购公告 + A/H溢价 + ETF溢折价
 */
import { useState, useEffect, useCallback } from 'react'
import { dailyInfoApi } from '../../services/api'
import type { ArbitrageData } from './types'
import { formatPct, formatPrice } from './utils'

interface Props {
  briefingData?: ArbitrageData | null
}

export default function ArbitrageTab({ briefingData }: Props) {
  const [data, setData] = useState<ArbitrageData | null>(briefingData || null)
  const [loading, setLoading] = useState(!briefingData)

  const loadData = useCallback(async () => {
    if (briefingData) return
    setLoading(true)
    try {
      const res = await dailyInfoApi.getArbitrage()
      setData(res.data as unknown as ArbitrageData)
    } catch {} finally {
      setLoading(false)
    }
  }, [briefingData])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>加载中...</div>
  if (!data) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>暂无数据</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 并购重组 */}
      <Section title="📋 并购重组公告" count={data.merger_arbitrage?.length}>
        {data.merger_arbitrage?.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                <th style={thStyle}>代码</th>
                <th style={thStyle}>名称</th>
                <th style={thStyle}>状态</th>
                <th style={thStyle}>进展</th>
              </tr>
            </thead>
            <tbody>
              {data.merger_arbitrage.map((m, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
                  <td style={tdStyle}>{m.code || '--'}</td>
                  <td style={{ ...tdStyle, fontWeight: 500, color: 'var(--text-primary)' }}>{m.name}</td>
                  <td style={tdStyle}>{m.status}</td>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)', fontSize: 11 }}>{m.progress}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty msg="暂无并购重组公告" />}
      </Section>

      {/* A/H 股溢价 */}
      <Section title="🔄 A/H 股溢价" count={data.cross_market_spreads?.length}>
        {data.cross_market_spreads?.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                <th style={thStyle}>名称</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>A股价格</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>H股价格</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>溢价率</th>
              </tr>
            </thead>
            <tbody>
              {data.cross_market_spreads.map((s, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
                  <td style={{ ...tdStyle, fontWeight: 500, color: 'var(--text-primary)' }}>{s.name}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPrice(s.a_price)}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPrice(s.h_price)}</td>
                  <td style={{
                    ...tdStyle, textAlign: 'right', fontWeight: 600,
                    color: s.premium > 50 ? '#f85149' : s.premium > 0 ? '#d29922' : '#3fb950',
                  }}>
                    {formatPct(s.premium)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty msg="暂无 A/H 溢价数据" />}
      </Section>

      {/* ETF 溢折价 */}
      <Section title="📊 ETF 溢折价" count={data.etf_premium?.length}>
        {data.etf_premium?.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                <th style={thStyle}>代码</th>
                <th style={thStyle}>名称</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>价格</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>净值</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>溢折价</th>
              </tr>
            </thead>
            <tbody>
              {data.etf_premium.map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
                  <td style={tdStyle}>{e.code}</td>
                  <td style={{ ...tdStyle, fontWeight: 500, color: 'var(--text-primary)' }}>{e.name}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPrice(e.price, 4)}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>{formatPrice(e.nav, 4)}</td>
                  <td style={{
                    ...tdStyle, textAlign: 'right', fontWeight: 600,
                    color: Math.abs(e.premium) > 2 ? '#f85149' : e.premium > 0 ? '#d29922' : '#3fb950',
                  }}>
                    {formatPct(e.premium)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty msg="暂无 ETF 溢折价数据" />}
      </Section>
    </div>
  )
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
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
