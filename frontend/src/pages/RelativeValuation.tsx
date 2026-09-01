import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { PageSection, TabBar, DataTable, Tag, LoadingSpinner, EmptyState, type Column } from '../components/ui'
import {
  relativeValuationApi,
  type SectorInfo,
  type StockMetric,
  type CompareResult,
  type UniverseStock,
} from '../services/api/relativeValuation'

type Market = 'A' | 'HK'
type TabKey = 'pick' | 'browse'

const RATING_COLOR: Record<string, string> = {
  cheap_plus: 'var(--accent-green)',
  cheap: 'var(--accent-green)',
  fair: 'var(--accent-blue)',
  rich: 'var(--accent-orange)',
  rich_plus: 'var(--accent-red)',
  na: 'var(--text-muted)',
}

const fmt = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined ? '-' : Number(v).toFixed(d)

const fmtPct = (v: number | null | undefined) =>
  v === null || v === undefined ? '-' : `${Number(v) >= 0 ? '+' : ''}${v.toFixed(1)}%`

/** 红涨绿跌：A股/港股惯例 */
const changeColor = (v: number | null | undefined) => {
  if (v === null || v === undefined) return undefined
  if (v > 0) return 'var(--accent-red)'
  if (v < 0) return 'var(--accent-green)'
  return undefined
}

/** 指标条颜色：effective 越高越便宜/越有吸引力 */
function metricColor(pct: number | null | undefined, higherBetter = false): string {
  if (pct === null || pct === undefined) return 'var(--text-muted)'
  const effective = higherBetter ? pct : 100 - pct
  if (effective >= 66) return 'var(--accent-green)'
  if (effective >= 33) return 'var(--accent-blue)'
  return 'var(--accent-red)'
}

/** 横向对比条形图（无依赖，CSS 渲染），含中位数参考线 */
function MetricBarChart({
  stocks,
  metric,
  higherBetter,
  median,
}: {
  stocks: StockMetric[]
  metric: 'pe' | 'pb' | 'ps'
  higherBetter: boolean
  median: number | null
}) {
  const rows = stocks.filter(s => s[metric] !== null && s[metric] !== undefined) as Required<
    Pick<StockMetric, 'code' | 'name' | typeof metric>
  >[]
  if (rows.length === 0) return <EmptyState icon="📉" title="该指标组内暂无有效数据" />
  const vals = rows.map(r => r[metric] as number)
  const max = Math.max(...vals, median || 0)
  if (max <= 0) return <EmptyState icon="📉" title="该指标组内数据无效" />

  return (
    <div style={{ marginTop: 12 }}>
      {rows.map(r => {
        const v = r[metric] as number
        const pct = (r as unknown as StockMetric)[`${metric}_pct`] as number | null
        const widthPct = (v / max) * 100
        const medianLeft = median ? (median / max) * 100 : null
        return (
          <div key={r.code} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div
              style={{
                width: 92,
                fontSize: 12,
                color: 'var(--text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title={r.name}
            >
              {r.name}
            </div>
            <div style={{ position: 'relative', flex: 1, height: 18, background: 'var(--bg-secondary)', borderRadius: 4 }}>
              <div
                style={{
                  width: `${widthPct}%`,
                  height: '100%',
                  background: metricColor(pct, higherBetter),
                  borderRadius: 4,
                  opacity: 0.85,
                }}
              />
              {medianLeft !== null && (
                <div
                  style={{
                    position: 'absolute',
                    left: `${medianLeft}%`,
                    top: -2,
                    bottom: -2,
                    width: 2,
                    background: 'var(--text-muted)',
                  }}
                  title={`组内中位数 ${median?.toFixed(2)}`}
                />
              )}
            </div>
            <div style={{ width: 64, textAlign: 'right', fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
              {fmt(v)}
            </div>
          </div>
        )
      })}
      {median !== null && median !== undefined && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
          竖线 = 组内中位数（{fmt(median)}）
        </div>
      )}
    </div>
  )
}

const COLUMNS: Column<Record<string, unknown>>[] = [
  { key: 'name', title: '个股', dataIndex: 'name', width: 110 },
  {
    key: 'price',
    title: '现价',
    dataIndex: 'price',
    align: 'right',
    render: (_v: unknown, record: Record<string, unknown>) => {
      const r = record as unknown as StockMetric
      return (
        <span>
          {fmt(r.price)}
          {r.change_pct !== null && r.change_pct !== undefined && (
            <span style={{ color: changeColor(r.change_pct), fontSize: 11, marginLeft: 4 }}>
              {fmtPct(r.change_pct)}
            </span>
          )}
        </span>
      )
    },
  },
  {
    key: 'pe',
    title: 'PE(TTM)',
    dataIndex: 'pe',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).pe),
  },
  {
    key: 'pe_pct',
    title: 'PE分位',
    dataIndex: 'pe_pct',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).pe_pct, 0),
  },
  {
    key: 'pb',
    title: 'PB',
    dataIndex: 'pb',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).pb),
  },
  {
    key: 'pb_pct',
    title: 'PB分位',
    dataIndex: 'pb_pct',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).pb_pct, 0),
  },
  {
    key: 'ps',
    title: 'PS(估)',
    dataIndex: 'ps',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).ps),
  },
  {
    key: 'dividend_yield',
    title: '股息率%',
    dataIndex: 'dividend_yield',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).dividend_yield),
  },
  {
    key: 'roe',
    title: 'ROE%',
    dataIndex: 'roe',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).roe),
  },
  {
    key: 'profit_growth',
    title: '净利增速%',
    dataIndex: 'profit_growth',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).profit_growth),
  },
  {
    key: 'attractiveness',
    title: '综合吸引力',
    dataIndex: 'attractiveness',
    align: 'right',
    render: (_v: unknown, r: Record<string, unknown>) => fmt((r as unknown as StockMetric).attractiveness, 0),
  },
  {
    key: 'rating',
    title: '评级',
    dataIndex: 'rating',
    align: 'center',
    render: (_v: unknown, r: Record<string, unknown>) => {
      const rec = r as unknown as StockMetric
      return <Tag color={RATING_COLOR[rec.rating_level || 'na'] || 'var(--text-muted)'}>{rec.rating || '-'}</Tag>
    },
  },
]

/** 对比结果展示（目标卡 + 同业表 + 条形图 + 说明） */
function ResultView({
  result,
  chartMetric,
  setChartMetric,
  title,
}: {
  result: CompareResult
  chartMetric: 'pe' | 'pb' | 'ps'
  setChartMetric: (m: 'pe' | 'pb' | 'ps') => void
  title?: string
}) {
  const dataRows = useMemo(
    () => (result.stocks || []) as unknown as Record<string, unknown>[],
    [result],
  )
  return (
    <>
      {title && <h4 style={{ fontSize: 14, margin: '8px 0 12px' }}>{title}</h4>}

      {result.target && (
        <div
          style={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
            padding: 16,
            marginBottom: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 16, fontWeight: 600 }}>{result.target.name}</span>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{result.target.code}</span>
            <Tag color={RATING_COLOR[result.target.rating_level || 'na'] || 'var(--text-muted)'}>
              {result.target.rating}
            </Tag>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              综合吸引力 {fmt(result.target.attractiveness, 0)} · 行业 {result.sector_label}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 13 }}>
            <span>
              PE {fmt(result.target.pe)}（分位 {fmt(result.target.pe_pct, 0)}，偏离 {fmtPct(result.target.pe_dev)}）
            </span>
            <span>
              PB {fmt(result.target.pb)}（分位 {fmt(result.target.pb_pct, 0)}，偏离 {fmtPct(result.target.pb_dev)}）
            </span>
            <span>PS {fmt(result.target.ps)}（分位 {fmt(result.target.ps_pct, 0)}）</span>
            <span>股息率 {fmt(result.target.dividend_yield)}%</span>
            <span>ROE {fmt(result.target.roe)}%</span>
            <span>净利增速 {fmt(result.target.profit_growth)}%</span>
          </div>
        </div>
      )}

      {result.note && <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{result.note}</p>}

      <DataTable columns={COLUMNS} data={dataRows} rowKey="code" striped compact />

      <div style={{ marginTop: 20 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          {(['pe', 'pb', 'ps'] as const).map(m => (
            <button
              key={m}
              onClick={() => setChartMetric(m)}
              style={{
                background: chartMetric === m ? 'var(--accent-blue)' : 'var(--bg-secondary)',
                color: chartMetric === m ? '#fff' : 'var(--text-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                padding: '4px 12px',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              {m === 'pe' ? 'PE 对比' : m === 'pb' ? 'PB 对比' : 'PS 对比'}
            </button>
          ))}
        </div>
        <MetricBarChart
          stocks={result.stocks}
          metric={chartMetric}
          higherBetter={false}
          median={result.medians[chartMetric] as number | null}
        />
      </div>

      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 16, lineHeight: 1.6 }}>
        {result.data_note}
        <br />
        说明：分位=该指标在组内由低到高的位置（PE/PB/PS 越低越靠前=越便宜）；综合吸引力=PE/PB/PS 分位的反向均值与股息率分位的综合评分，越高越便宜。仅供参考，非投资建议。
      </p>
    </>
  )
}

/** 可搜索标的下拉（按代码 / 名称 / 行业过滤） */
function StockSearch({
  universe,
  onSelect,
}: {
  universe: UniverseStock[]
  onSelect: (s: UniverseStock) => void
}) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => {
    const t = text.trim().toLowerCase()
    if (!t) return universe
    return universe.filter(
      u =>
        u.code.toLowerCase().includes(t) ||
        u.name.toLowerCase().includes(t) ||
        u.sector_label.toLowerCase().includes(t),
    )
  }, [text, universe])

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const pick = (u: UniverseStock) => {
    setText(`${u.name}（${u.code}）`)
    setOpen(false)
    onSelect(u)
  }

  return (
    <div ref={ref} style={{ position: 'relative', width: 340 }}>
      <input
        value={text}
        placeholder="搜索代码 / 名称 / 行业，如 600519 或 茅台"
        onChange={e => {
          setText(e.target.value)
          setOpen(true)
          setHighlight(0)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setHighlight(h => Math.min(h + 1, filtered.length - 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setHighlight(h => Math.max(h - 1, 0))
          } else if (e.key === 'Enter') {
            if (filtered[highlight]) pick(filtered[highlight])
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
        style={{
          width: '100%',
          background: 'var(--bg-secondary)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: 6,
          padding: '8px 12px',
          fontSize: 13,
        }}
      />
      {open && filtered.length > 0 && (
        <div
          style={{
            position: 'absolute',
            zIndex: 20,
            top: '110%',
            left: 0,
            right: 0,
            maxHeight: 300,
            overflowY: 'auto',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
          }}
        >
          {filtered.map((u, i) => (
            <div
              key={u.code}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={() => pick(u)}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 8,
                fontSize: 13,
                background: i === highlight ? 'var(--bg-secondary)' : 'transparent',
              }}
            >
              <span>
                <b>{u.name}</b> <span style={{ color: 'var(--text-muted)' }}>{u.code}</span>
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{u.sector_label}</span>
            </div>
          ))}
        </div>
      )}
      {open && filtered.length === 0 && (
        <div
          style={{
            position: 'absolute',
            zIndex: 20,
            top: '110%',
            left: 0,
            right: 0,
            padding: 12,
            fontSize: 13,
            color: 'var(--text-muted)',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            borderRadius: 8,
          }}
        >
          无匹配标的
        </div>
      )}
    </div>
  )
}

export default function RelativeValuation() {
  const [market, setMarket] = useState<Market>('A')
  const [tab, setTab] = useState<TabKey>('pick') // 默认进入「选标的」模式，不自动跑对比
  const [sectors, setSectors] = useState<SectorInfo[]>([])
  const [sector, setSector] = useState('')

  const [universe, setUniverse] = useState<UniverseStock[]>([])
  const [universeLoading, setUniverseLoading] = useState(false)

  // 「选标的」模式结果
  const [pickResult, setPickResult] = useState<CompareResult | null>(null)
  const [pickLoading, setPickLoading] = useState(false)
  const [pickError, setPickError] = useState<string | null>(null)

  // 「按行业浏览」模式结果
  const [browseResult, setBrowseResult] = useState<CompareResult | null>(null)
  const [browseLoading, setBrowseLoading] = useState(false)
  const [browseError, setBrowseError] = useState<string | null>(null)

  const [chartMetric, setChartMetric] = useState<'pe' | 'pb' | 'ps'>('pe')

  // 切换市场：重新加载行业清单 + 标的清单，并清空已有结果
  useEffect(() => {
    let cancelled = false
    setSectors([])
    setSector('')
    setUniverse([])
    setPickResult(null)
    setPickError(null)
    setBrowseResult(null)
    setBrowseError(null)
    setUniverseLoading(true)
    Promise.all([relativeValuationApi.getSectors(), relativeValuationApi.getStocks(market)])
      .then(([sec, uni]) => {
        if (cancelled) return
        const list = market === 'A' ? sec.A : sec.HK
        setSectors(list)
        setSector(list[0]?.key || '')
        setUniverse(uni.stocks || [])
      })
      .catch(e => {
        if (!cancelled) setPickError(e.message || '加载失败')
      })
      .finally(() => {
        if (!cancelled) setUniverseLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [market])

  // 「选标的」：选中后自动定位行业并拉同行业对比
  const runPick = useCallback(
    (code: string) => {
      setPickLoading(true)
      setPickError(null)
      relativeValuationApi
        .compareStock(market, code) // 不传 sector → 后端自动定位
        .then(data => {
          setPickResult(data)
          setPickError(data.error || null)
        })
        .catch(e => {
          setPickError(e.message || '对比失败')
        })
        .finally(() => setPickLoading(false))
    },
    [market],
  )

  // 「按行业浏览」：进入该 Tab 或切换行业时再跑（非默认、非自动开跑）
  useEffect(() => {
    if (tab !== 'browse' || !sector) return
    let cancelled = false
    setBrowseLoading(true)
    setBrowseError(null)
    relativeValuationApi
      .compareSector(market, sector)
      .then(data => {
        if (cancelled) return
        setBrowseResult(data)
        setBrowseError(data.error || null)
      })
      .catch(e => {
        if (!cancelled) setBrowseError(e.message || '加载失败')
      })
      .finally(() => {
        if (!cancelled) setBrowseLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tab, market, sector])

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>
      <PageSection title="相对估值法 · 同行业跨市场对比" compact>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 16px', lineHeight: 1.6 }}>
          先挑选一只标的，系统自动定位其行业、拉取同行业公司，并对比 PE/PB/PS 组内分位、相对中位数偏离与综合吸引力。也可切换到「按行业浏览」查看整组对比。
        </p>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16 }}>
          <TabBar
            tabs={[
              { key: 'pick', label: '选标的对比' },
              { key: 'browse', label: '按行业浏览' },
            ]}
            activeKey={tab}
            onChange={(k: string) => setTab(k as TabKey)}
          />
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>市场</span>
            <TabBar
              size="small"
              tabs={[
                { key: 'A', label: 'A股' },
                { key: 'HK', label: '港股' },
              ]}
              activeKey={market}
              onChange={(k: string) => setMarket(k as Market)}
            />
          </div>
        </div>

        {tab === 'pick' && (
          <div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
              <StockSearch universe={universe} onSelect={u => runPick(u.code)} />
              {universeLoading && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>加载标的清单…</span>}
            </div>

            {!pickResult && !pickLoading && !pickError && (
              <EmptyState
                icon="🔍"
                title="请选择一只标的开始对比"
                desc="选择后系统将自动定位其行业、拉取同行业公司并对比估值指标（PE/PB/PS/股息率/ROE/成长性）。"
              />
            )}
            {pickLoading && <LoadingSpinner text="正在定位行业并对比同业…" />}
            {pickError && !pickLoading && <EmptyState icon="⚠️" title={pickError} />}
            {!pickLoading && !pickError && pickResult && (
              <ResultView result={pickResult} chartMetric={chartMetric} setChartMetric={setChartMetric} />
            )}
          </div>
        )}

        {tab === 'browse' && (
          <div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>行业</span>
              <select
                value={sector}
                onChange={e => setSector(e.target.value)}
                style={{
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 6,
                  padding: '6px 10px',
                  fontSize: 13,
                }}
              >
                {sectors.map(s => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
              {browseResult && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  共 {browseResult.count} 只 · 中位数 PE {fmt(browseResult.medians.pe)} / PB {fmt(browseResult.medians.pb)} / PS{' '}
                  {fmt(browseResult.medians.ps)}
                </span>
              )}
            </div>

            {!browseResult && !browseLoading && !browseError && (
              <EmptyState icon="📊" title="选择行业查看组内对比" desc="在上方选择行业后将自动加载该行业全部同业对比。" />
            )}
            {browseLoading && <LoadingSpinner text="正在抓取同业估值数据…" />}
            {browseError && !browseLoading && <EmptyState icon="⚠️" title={browseError} />}
            {!browseLoading && !browseError && browseResult && (
              <ResultView result={browseResult} chartMetric={chartMetric} setChartMetric={setChartMetric} />
            )}
          </div>
        )}
      </PageSection>
    </div>
  )
}
