/**
 * 宏观数据标签页
 * 中国宏观（AKShare）+ 美国宏观（FRED）
 */
import { useState, useEffect, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import { dailyInfoApi } from '../../services/api'
import type { ChinaMacroData, UsMacroData, FredIndicator } from './types'

interface Props {
  chinaMacro?: ChinaMacroData | null
}

export default function MacroDataTab({ chinaMacro: briefingMacro }: Props) {
  const [chinaMacro, setChinaMacro] = useState<ChinaMacroData | null>(briefingMacro || null)
  const [usMacro, setUsMacro] = useState<UsMacroData | null>(null)
  const [loading, setLoading] = useState(!briefingMacro)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const promises: Promise<any>[] = []
      if (!briefingMacro) promises.push(dailyInfoApi.getChinaMacro().then(r => setChinaMacro(r.data)))
      promises.push(dailyInfoApi.getUSMacro().then(r => setUsMacro(r.data as unknown as UsMacroData)))
      await Promise.allSettled(promises)
    } catch {} finally {
      setLoading(false)
    }
  }, [briefingMacro])

  useEffect(() => { loadData() }, [loadData])

  if (loading) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>加载中...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 中国宏观 */}
      <MacroSection title="🇨🇳 中国宏观经济">
        {chinaMacro ? <ChinaMacroPanel data={chinaMacro} /> : <Empty msg="暂无中国宏观数据" />}
      </MacroSection>

      {/* 美国宏观 */}
      <MacroSection title="🇺🇸 美国宏观经济 (FRED)">
        {usMacro?.available !== false ? <UsMacroPanel data={usMacro} /> : <Empty msg={usMacro?.reason || 'FRED_API_KEY 未设置'} />}
      </MacroSection>
    </div>
  )
}

// ==================== 子组件 ====================

function MacroSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>{title}</div>
      {children}
    </div>
  )
}

function Empty({ msg }: { msg: string }) {
  return <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '16px 0', textAlign: 'center' }}>{msg}</div>
}

function ChinaMacroPanel({ data }: { data: ChinaMacroData }) {
  const items = [
    data.gdp && {
      label: 'GDP', value: `${(data.gdp.gdp / 1e4).toFixed(1)} 万亿`,
      sub: `同比 ${data.gdp.gdp_growth?.toFixed(1)}%`, date: data.gdp.date,
    },
    data.cpi && {
      label: 'CPI', value: `${data.cpi.cpi_yoy?.toFixed(1)}%`,
      sub: '同比', date: data.cpi.date,
      color: data.cpi.cpi_yoy > 3 ? '#f85149' : data.cpi.cpi_yoy < 0 ? '#3fb950' : undefined,
    },
    data.pmi && {
      label: 'PMI', value: `${data.pmi.manufacturing?.toFixed(1)}`,
      sub: `非制造业 ${data.pmi.non_manufacturing?.toFixed(1)}`, date: data.pmi.date,
      color: data.pmi.manufacturing < 50 ? '#3fb950' : data.pmi.manufacturing >= 52 ? '#f85149' : undefined,
      tag: data.pmi.manufacturing < 50 ? '收缩' : data.pmi.manufacturing >= 52 ? '扩张' : '荣枯线附近',
    },
    data.money_supply && {
      label: 'M2', value: `${(data.money_supply.m2 / 1e4).toFixed(1)} 万亿`,
      sub: `同比 ${data.money_supply.m2_growth?.toFixed(1)}%`, date: data.money_supply.date,
    },
  ].filter(Boolean) as { label: string; value: string; sub: string; date: string; color?: string; tag?: string }[]

  if (items.length === 0) return <Empty msg="暂无数据" />

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
      {items.map((item, i) => (
        <div key={i} style={{
          background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-sm)', padding: 12,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{item.label}</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: item.color || 'var(--text-primary)' }}>
            {item.value}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            {item.sub}
            {item.tag && (
              <span style={{
                marginLeft: 6, fontSize: 10, padding: '0 4px', borderRadius: 3,
                background: item.color ? `${item.color}22` : 'var(--bg-secondary)',
                color: item.color || 'var(--text-muted)',
              }}>{item.tag}</span>
            )}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>{item.date}</div>
        </div>
      ))}
    </div>
  )
}

function UsMacroPanel({ data }: { data: UsMacroData | null }) {
  if (!data?.indicators || Object.keys(data.indicators).length === 0) {
    return <Empty msg="暂无 FRED 数据，请设置 FRED_API_KEY 环境变量" />
  }

  const labels: Record<string, { label: string; format: (v: number) => string; unit?: string }> = {
    cpi: { label: 'CPI', format: v => v.toFixed(1), unit: 'Index' },
    unemployment: { label: '失业率', format: v => `${v.toFixed(1)}%` },
    fed_rate: { label: '联邦基金利率', format: v => `${v.toFixed(2)}%` },
    treasury_10y: { label: '10年期国债', format: v => `${v.toFixed(2)}%` },
    treasury_2y: { label: '2年期国债', format: v => `${v.toFixed(2)}%` },
    yield_spread_10y2y: { label: '收益率曲线(10Y-2Y)', format: v => `${v.toFixed(2)}%` },
    gdp_real: { label: '实际GDP', format: v => `${(v / 1000).toFixed(1)}T`, unit: 'B$' },
    nonfarm_payroll: { label: '非农就业', format: v => `${(v / 1000).toFixed(1)}M`, unit: 'K' },
  }

  const entries = Object.entries(data.indicators).filter(([k]) => labels[k])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {entries.map(([key, ind]) => {
          const meta = labels[key]
          if (!meta) return null
          const isYield = key.includes('treasury') || key === 'fed_rate' || key === 'yield_spread_10y2y'
          const color = isYield
            ? (ind.value > 4 ? '#f85149' : ind.value < 2 ? '#3fb950' : undefined)
            : undefined

          return (
            <div key={key} style={{
              background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
              borderRadius: 'var(--radius-sm)', padding: 12,
            }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{meta.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: color || 'var(--text-primary)' }}>
                {meta.format(ind.value)}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>{ind.date}</div>
            </div>
          )
        })}
      </div>

      {/* 走势图 */}
      {entries.length > 0 && <UsMacroCharts entries={entries} labels={labels} />}
    </div>
  )
}

function UsMacroCharts({ entries, labels }: {
  entries: [string, FredIndicator][]
  labels: Record<string, { label: string; format: (v: number) => string }>
}) {
  // 选择有 series 数据的指标画图
  const chartEntries = entries.filter(([_, ind]) => ind.series?.length > 2).slice(0, 4)

  if (chartEntries.length === 0) return null

  return (
    <div style={{ display: 'grid', gridTemplateColumns: chartEntries.length > 2 ? '1fr 1fr' : '1fr', gap: 12 }}>
      {chartEntries.map(([key, ind]) => {
        const meta = labels[key]
        const series = [...ind.series].reverse() // 按时间正序
        const option = {
          grid: { top: 20, right: 12, bottom: 24, left: 50 },
          xAxis: { type: 'category', data: series.map(s => s.date), show: false },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(48,54,61,0.5)' } }, axisLabel: { fontSize: 10, color: '#8b949e' } },
          series: [{
            type: 'line', data: series.map(s => s.value), smooth: true, symbol: 'none',
            lineStyle: { color: '#58a6ff', width: 2 },
            areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(88,166,255,0.3)' }, { offset: 1, color: 'rgba(88,166,255,0)' }] } },
          }],
          tooltip: { trigger: 'axis', formatter: (params: any) => `${params[0]?.axisValue}<br/>${meta.label}: ${params[0]?.value}` },
        }

        return (
          <div key={key} style={{
            background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
            borderRadius: 'var(--radius-sm)', padding: 8,
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>{meta.label} 走势</div>
            <ReactECharts option={option} style={{ height: 150 }} />
          </div>
        )
      })}
    </div>
  )
}
