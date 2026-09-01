import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Switch, Table } from 'antd'
import {
  PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState, Tag,
} from '../components/ui'
import {
  indexEarningsApi,
  type IndexEarningsData,
  type IndexEarningsMeta,
  type IndexEarningsRow,
} from '../services/api'

// 配色（红涨绿跌，A股习惯；与用户 Excel 中 EPS 周期红/绿着色一致）
const C = {
  close: '#2563eb',
  fair: '#f59e0b',
  epsUp: '#d43f3a',
  epsDown: '#2e9e5b',
  pe: '#7c3aed',
  dev: '#0891b2',
  premium: '#dc2626',
  bond: '#64748b',
}

const fmt = (v: number | null | undefined, digits = 2): string =>
  v === null || v === undefined ? '-' : Number(v.toFixed(digits)).toLocaleString('zh-CN')

function IndexEarnings() {
  const [indices, setIndices] = useState<IndexEarningsMeta[]>([])
  const [code, setCode] = useState<string>('')
  const [data, setData] = useState<IndexEarningsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [logScale, setLogScale] = useState(true)

  // 加载指数列表
  useEffect(() => {
    indexEarningsApi.getList()
      .then(res => {
        const list = res.data.indices.filter(i => !i.error)
        setIndices(res.data.indices)
        if (list.length > 0) setCode(list[0].code)
      })
      .catch(e => setError(e.message || '加载指数列表失败'))
  }, [])

  // 加载选中指数数据
  const loadData = useCallback((c: string) => {
    if (!c) return
    setLoading(true)
    setError('')
    indexEarningsApi.getData(c)
      .then(res => setData(res.data))
      .catch(e => setError(e.message || '加载数据失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData(code) }, [code, loadData])

  const meta = data?.meta
  const rows = useMemo(() => data?.rows ?? [], [data])
  const dates = useMemo(() => rows.map(r => r.date), [rows])
  const has = useCallback((f: keyof IndexEarningsRow) => rows.some(r => r[f] !== null && r[f] !== undefined), [rows])

  const series = useCallback((f: keyof IndexEarningsRow) => rows.map(r => r[f] ?? null), [rows])

  // ============ 图表配置 ============

  const zoom = [
    { type: 'inside' as const },
    { type: 'slider' as const, height: 18, bottom: 6 },
  ]
  const baseGrid = { left: 60, right: 60, top: 40, bottom: 60 }
  const baseTooltip = { trigger: 'axis' as const }

  // 图1：收盘价 vs 合理收盘价
  const priceOption = useMemo(() => ({
    tooltip: baseTooltip,
    legend: { data: ['收盘价', '合理收盘价'] },
    grid: baseGrid,
    xAxis: { type: 'category' as const, data: dates },
    yAxis: { type: logScale ? 'log' as const : 'value' as const, scale: true, name: logScale ? '对数轴' : '' },
    dataZoom: zoom,
    series: [
      { name: '收盘价', type: 'line' as const, data: series('close'), showSymbol: false, lineStyle: { width: 1.5 }, itemStyle: { color: C.close } },
      { name: '合理收盘价', type: 'line' as const, data: series('fair_close'), showSymbol: false, lineStyle: { width: 1.5, type: 'dashed' as const }, itemStyle: { color: C.fair } },
    ],
  }), [dates, series, logScale])  // eslint-disable-line react-hooks/exhaustive-deps

  // 图2：EPS 盈利周期（红涨绿跌）
  const epsOption = useMemo(() => ({
    tooltip: baseTooltip,
    legend: { data: ['EPS上涨周期', 'EPS下降周期'] },
    grid: baseGrid,
    xAxis: { type: 'category' as const, data: dates },
    yAxis: { type: 'value' as const, scale: true, name: '隐含EPS(点)' },
    dataZoom: zoom,
    series: [
      { name: 'EPS上涨周期', type: 'line' as const, data: series('eps_up'), showSymbol: false, lineStyle: { width: 1.8 }, itemStyle: { color: C.epsUp } },
      { name: 'EPS下降周期', type: 'line' as const, data: series('eps_down'), showSymbol: false, lineStyle: { width: 1.8 }, itemStyle: { color: C.epsDown } },
    ],
  }), [dates, series])  // eslint-disable-line react-hooks/exhaustive-deps

  // 图3：PE-TTM + 估值中枢偏移率（含基准线）
  const peOption = useMemo(() => ({
    tooltip: baseTooltip,
    legend: { data: ['PE-TTM', '估值中枢偏移率'] },
    grid: baseGrid,
    xAxis: { type: 'category' as const, data: dates },
    yAxis: [
      { type: 'value' as const, scale: true, name: 'PE-TTM' },
      { type: 'value' as const, scale: true, name: '偏移率' },
    ],
    dataZoom: zoom,
    series: [
      { name: 'PE-TTM', type: 'line' as const, data: series('pe'), showSymbol: false, lineStyle: { width: 1.5 }, itemStyle: { color: C.pe } },
      {
        name: '估值中枢偏移率', type: 'line' as const, yAxisIndex: 1, data: series('valuation_dev'),
        showSymbol: false, lineStyle: { width: 1.5 }, itemStyle: { color: C.dev },
        markLine: meta?.baseline !== undefined ? {
          symbol: 'none',
          lineStyle: { color: '#999', type: 'dashed' as const },
          label: { formatter: `基准线 ${meta.baseline}` },
          data: [{ yAxis: meta.baseline }],
        } : undefined,
      },
    ],
  }), [dates, series, meta])  // eslint-disable-line react-hooks/exhaustive-deps

  // 图4：风险溢价 + 国债收益率
  const bondField: keyof IndexEarningsRow = has('cn10y') ? 'cn10y' : 'us10y'
  const premiumOption = useMemo(() => ({
    tooltip: baseTooltip,
    legend: { data: ['风险溢价(百分点)', meta?.bond_name ?? '国债收益率'] },
    grid: baseGrid,
    xAxis: { type: 'category' as const, data: dates },
    yAxis: [
      { type: 'value' as const, scale: true, name: '风险溢价' },
      { type: 'value' as const, scale: true, name: '国债%' },
    ],
    dataZoom: zoom,
    series: [
      {
        name: '风险溢价(百分点)', type: 'line' as const, data: series('risk_premium'),
        showSymbol: false, lineStyle: { width: 1.5 }, itemStyle: { color: C.premium },
        markLine: { symbol: 'none', lineStyle: { color: '#bbb', type: 'solid' as const, width: 0.8 }, label: { show: false }, data: [{ yAxis: 0 }] },
      },
      { name: meta?.bond_name ?? '国债收益率', type: 'line' as const, yAxisIndex: 1, data: series(bondField), showSymbol: false, lineStyle: { width: 1.2 }, itemStyle: { color: C.bond } },
    ],
  }), [dates, series, meta, bondField])  // eslint-disable-line react-hooks/exhaustive-deps

  // 图5（仅自动版有）：PE 口径对比 Wind(手工) vs 乐咕(自动)
  const compare = data?.compare
  const compareOption = useMemo(() => {
    const s = compare?.series ?? []
    return {
      tooltip: baseTooltip,
      legend: { data: ['PE-TTM · Wind(手工)', 'PE · 乐咕(自动)'] },
      grid: baseGrid,
      xAxis: { type: 'category' as const, data: s.map(p => p.date) },
      yAxis: { type: 'value' as const, scale: true, name: 'PE' },
      dataZoom: zoom,
      series: [
        { name: 'PE-TTM · Wind(手工)', type: 'line' as const, data: s.map(p => p.pe_wind ?? null), showSymbol: false, lineStyle: { width: 1.5 }, itemStyle: { color: C.pe } },
        { name: 'PE · 乐咕(自动)', type: 'line' as const, data: s.map(p => p.pe_auto ?? null), showSymbol: false, lineStyle: { width: 1.5, type: 'dashed' as const }, itemStyle: { color: C.fair } },
      ],
    }
  }, [compare])  // eslint-disable-line react-hooks/exhaustive-deps

  // ============ 表格 ============

  const tableColumns = useMemo(() => (data?.columns ?? []).map(col => ({
    title: col.label,
    dataIndex: col.key,
    key: col.key,
    width: col.key === 'date' ? 110 : 120,
    render: (v: unknown) => col.key === 'date'
      ? String(v)
      : typeof v === 'number' ? fmt(v) : '-',
  })), [data])

  const tableData = useMemo(
    () => [...rows].reverse().map(r => ({ ...r, key: r.date })),
    [rows]
  )

  const cycleColumns = [
    { title: '开始', dataIndex: 'start', key: 'start', width: 110 },
    { title: '结束', dataIndex: 'end', key: 'end', width: 110 },
    {
      title: '方向', dataIndex: 'direction', key: 'direction', width: 80,
      render: (v: string) => (
        <span style={{ color: v === '上涨' ? C.epsUp : C.epsDown, fontWeight: 600 }}>{v}</span>
      ),
    },
    { title: '持续(月)', dataIndex: 'months', key: 'months', width: 100 },
    { title: '持续(周)', dataIndex: 'weeks', key: 'weeks', width: 100 },
  ]
  const cycleData = useMemo(
    () => [...(data?.cycles ?? [])].reverse().map((c, i) => ({ ...c, key: i })),
    [data]
  )

  // ============ 渲染 ============

  if (error && !data) {
    return <EmptyState title="加载失败" description={error} />
  }

  const latest = meta?.latest
  const discountTag = latest?.close && latest?.fair_close
    ? latest.close < latest.fair_close
      ? <Tag color="green">低于合理价 {fmt((1 - latest.close / latest.fair_close) * 100, 1)}%</Tag>
      : <Tag color="red">高于合理价 {fmt((latest.close / latest.fair_close - 1) * 100, 1)}%</Tag>
    : null

  return (
    <div className="page-container">
      <PageSection
        title="指数盈利与估值（手工维护数据 · 周度）"
        extra={meta && (
          <span style={{ fontSize: 12, color: '#888' }}>
            {meta.file_updated ? `Excel更新于 ${meta.file_updated}` : ''} · 数据区间 {meta.start_date} ~ {meta.end_date} · 共 {meta.row_count} 周
          </span>
        )}
        onRefresh={() => loadData(code)}
        refreshing={loading}
      >
        <TabBar
          tabs={indices.map(i => ({ key: i.code, label: i.name }))}
          activeKey={code}
          onChange={setCode}
        />

        {loading && <LoadingSpinner />}

        {!loading && data && meta && (
          <>
            <StatCardGroup columns={6} style={{ marginTop: 12 }}>
              <StatCard label={`最新收盘（${latest?.date ?? '-'}）`} value={fmt(latest?.close)} />
              <StatCard label="PE-TTM" value={fmt(latest?.pe)} suffix=" 倍" />
              <StatCard
                label="风险溢价"
                value={fmt(latest?.risk_premium)}
                suffix=" pct"
                color={(latest?.risk_premium ?? 0) > 0 ? C.epsUp : C.epsDown}
              />
              <StatCard
                label={`估值中枢偏移率（基准${meta.baseline}）`}
                value={fmt(latest?.valuation_dev)}
                color={(latest?.valuation_dev ?? 0) < (meta.baseline ?? 0) ? C.epsUp : C.epsDown}
              />
              <StatCard label="合理收盘价" value={fmt(latest?.fair_close)} />
              <StatCard
                label="实际 vs 合理"
                value={discountTag ?? '-'}
              />
            </StatCardGroup>

            <PageSection
              title="收盘价 vs 合理收盘价"
              extra={
                <span style={{ fontSize: 12, color: '#666' }}>
                  对数轴 <Switch size="small" checked={logScale} onChange={setLogScale} />
                </span>
              }
              compact
            >
              <ReactECharts option={priceOption} style={{ height: 380 }} notMerge />
            </PageSection>

            <PageSection
              title="EPS 盈利周期（红涨绿跌 · 隐含EPS 4周平滑 + 4% zigzag）"
              extra={
                <span style={{ fontSize: 12, color: '#888' }}>
                  盈利上涨累计 {fmt(meta.up_total_time, 0)} 周 / 下降累计 {fmt(meta.down_total_time, 0)} 周
                </span>
              }
              compact
            >
              <ReactECharts option={epsOption} style={{ height: 320 }} notMerge />
            </PageSection>

            <PageSection title={`PE-TTM 与估值中枢偏移率（基准线 ${meta.baseline}，低于=折价）`} compact>
              <ReactECharts option={peOption} style={{ height: 320 }} notMerge />
            </PageSection>

            <PageSection title={`风险溢价（100÷PE − ${meta.bond_name ?? '国债'}）`} compact>
              <ReactECharts option={premiumOption} style={{ height: 300 }} notMerge />
            </PageSection>

            {compare && compare.series.length > 0 && (
              <PageSection
                title="PE 口径对比：Wind（手工）vs 乐咕（自动）"
                extra={
                  <span style={{ fontSize: 12, color: '#888' }}>
                    重叠 {compare.stats.overlap_weeks} 周 · 平均偏差 {compare.stats.pe_mean_diff_pct}% · 最新偏差 {compare.stats.pe_latest_diff_pct}%
                    {compare.csindex_check?.n ? ` · 中证官网对照：均值差 ${compare.csindex_check.mean_diff_pct}%（${compare.csindex_check.n}日）` : ''}
                  </span>
                }
                compact
              >
                <ReactECharts option={compareOption} style={{ height: 300 }} notMerge />
              </PageSection>
            )}

            <PageSection title={`EPS 盈利周期区间（共 ${data.cycles.length} 段）`} compact>
              <Table
                columns={cycleColumns}
                dataSource={cycleData}
                size="small"
                pagination={{ pageSize: 10, showTotal: t => `共 ${t} 段` }}
              />
            </PageSection>

            <PageSection title="周度数据表（最新在前）" compact>
              <Table
                columns={tableColumns}
                dataSource={tableData}
                size="small"
                scroll={{ x: 'max-content' }}
                pagination={{ pageSize: 50, showSizeChanger: true, pageSizeOptions: [50, 100, 500], showTotal: t => `共 ${t} 周` }}
              />
            </PageSection>

            {(data.notes || data.summary_lines.length > 0) && (
              <PageSection title="口径与数据来源说明" compact>
                {data.notes && (
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#555', margin: 0 }}>{data.notes}</pre>
                )}
                {data.summary_lines.length > 0 && (
                  <ul style={{ fontSize: 12, color: '#555', marginTop: 8 }}>
                    {data.summary_lines.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                )}
              </PageSection>
            )}
          </>
        )}
      </PageSection>
    </div>
  )
}

export default IndexEarnings
