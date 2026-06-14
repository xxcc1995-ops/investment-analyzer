/**
 * 价值投资标签页
 * 财讯快讯 + 策略研报 + 热门概念板块
 */
import { useState, useEffect, useCallback } from 'react'
import { dailyInfoApi } from '../../services/api'
import type { ValueInvestingData } from './types'
import { formatPct, getChangeColor, relativeTime } from './utils'

interface Props {
  briefingData?: ValueInvestingData | null
}

export default function ValueInvestingTab({ briefingData }: Props) {
  const [data, setData] = useState<ValueInvestingData | null>(briefingData || null)
  const [loading, setLoading] = useState(!briefingData)

  const loadData = useCallback(async () => {
    if (briefingData) return
    setLoading(true)
    try {
      const res = await dailyInfoApi.getValueInvesting()
      setData(res.data as unknown as ValueInvestingData)
    } catch {} finally {
      setLoading(false)
    }
  }, [briefingData])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>加载中...</div>
  if (!data) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>暂无数据</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 财讯快讯 */}
      <Section title="📰 财讯快讯" count={data.announcements?.length}>
        {data.announcements?.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {data.announcements.map((a, i) => (
              <div key={i} style={{
                padding: '8px 0', borderBottom: '1px solid rgba(48,54,61,0.3)',
                display: 'flex', gap: 8, fontSize: 12,
              }}>
                <span style={{
                  fontSize: 10, padding: '0 4px', borderRadius: 3, flexShrink: 0,
                  background: 'var(--bg-tertiary)', color: 'var(--text-muted)', alignSelf: 'center',
                }}>{a.type}</span>
                <span style={{ flex: 1, color: 'var(--text-primary)', lineHeight: 1.5 }}>{a.title}</span>
                {a.code && <span style={{ color: 'var(--accent-blue)', fontSize: 11, flexShrink: 0 }}>{a.code}</span>}
              </div>
            ))}
          </div>
        ) : <Empty msg="暂无快讯" />}
      </Section>

      {/* 策略研报 */}
      <Section title="📊 策略研报" count={data.analyst_reports?.length}>
        {data.analyst_reports?.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 8 }}>
            {data.analyst_reports.map((r, i) => (
              <div key={i} style={{
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-sm)', padding: 10,
              }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4 }}>{r.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  {r.institution || '东方财富'}
                </div>
              </div>
            ))}
          </div>
        ) : <Empty msg="暂无研报" />}
      </Section>

      {/* 热门概念板块 */}
      <Section title="🔥 热门概念板块" count={data.concept_boards?.length}>
        {data.concept_boards?.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
            {data.concept_boards.map((b, i) => (
              <div key={i} style={{
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-sm)', padding: 10, textAlign: 'center',
              }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>{b.name}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: getChangeColor(b.change_pct) }}>
                  {formatPct(b.change_pct)}
                </div>
              </div>
            ))}
          </div>
        ) : <Empty msg="暂无概念板块数据" />}
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
