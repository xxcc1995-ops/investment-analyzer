import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import type { BondYieldPoint } from '../services/api'
import { StatCard, StatCardGroup, PageSection, DataTable, TabBar, LoadingSpinner, StatusBadge } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

// ============ 类型定义 ============

interface MacroDataItem {
  latest: Record<string, string | number | null | undefined>
  series: Record<string, string | number | null | undefined>[]
}

interface MacroOverview {
  gdp?: MacroDataItem; cpi?: MacroDataItem; pmi?: MacroDataItem; money_supply?: MacroDataItem
  social_financing?: MacroDataItem; lpr?: MacroDataItem; consumer_confidence?: MacroDataItem
  ppi?: MacroDataItem; retail_sales?: MacroDataItem; housing_price?: MacroDataItem
  unemployment?: MacroDataItem; industrial_production?: MacroDataItem; trade_balance?: MacroDataItem
  us_fed_rate?: MacroDataItem; us_gdp?: MacroDataItem; us_ism_pmi?: MacroDataItem
  us_non_farm?: MacroDataItem; us_yield_spread?: MacroDataItem; cn_yield_spread?: MacroDataItem
}

interface SignalDriver { name?: string; value?: string | number; desc?: string; level?: string; type?: string; [key: string]: unknown }
interface SignalItem { id?: string; name?: string; score?: number; level?: string; detail?: string; probability?: string; drivers?: SignalDriver[]; indicator_type?: string; [key: string]: unknown }
interface AssetSignal { name?: string; direction?: string; confidence?: number; reason?: string; [key: string]: unknown }
interface DataQualityItem { name?: string; source?: string; freshness?: string; confidence?: string; [key: string]: unknown }
interface CrossValidation { pmi?: string; fred_available?: boolean; fred_indicators?: number; akshare_indicators?: number; [key: string]: unknown }
interface Methodology { data_sources?: { name?: string; priority?: number; desc?: string; [key: string]: unknown }[]; limitations?: string[]; indicator_classification?: string; cycle_detection?: string; [key: string]: unknown }
interface MacroCycle { stage?: string; label?: string; confidence?: number; evidence?: string[]; recommendation?: string; asset_bias?: string; [key: string]: unknown }
interface MacroSignals {
  signals?: SignalItem[]; assets?: AssetSignal[]; data_quality?: DataQualityItem[]
  cross_validation?: CrossValidation; methodology?: Methodology; macro_cycle?: MacroCycle
  indicator_types?: { summary?: { leading?: number; coincident?: number; lagging?: number }; legend?: Record<string, string> }
  radar?: { dimensions?: string[]; values?: number[] }; updated_at?: string; [key: string]: unknown
}
interface MacroDetailData { [key: string]: Record<string, string | number | null | undefined>[] | undefined }

interface LeadingIndicator {
  name?: string; type?: string; country?: string; value?: number; date?: string
  trend?: { direction?: string; momentum?: number; change_pct?: number }
  signal?: string; desc?: string; lead_months?: string; source?: string; [key: string]: unknown
}
interface LeadingIndicatorsData {
  indicators?: LeadingIndicator[]
  composite?: { score?: number; level?: string; expansion_signals?: number; total_signals?: number; interpretation?: string }
  updated_at?: string
}

// ============ 辅助函数 ============

const fmt = (v: number | null | undefined, digits = 2) => v == null ? '-' : v.toFixed(digits)
const fmtBig = (v: number | null | undefined) => {
  if (v == null) return '-'
  return Math.abs(v) >= 10000 ? (v / 10000).toFixed(2) + '万亿' : v.toFixed(0) + '亿'
}
const levelColor = (level: string) => ({ danger: '#f85149', warning: '#d29922', neutral: '#58a6ff', healthy: '#3fb950' }[level] || '#8b949e')
const levelBg = (level: string) => ({ danger: 'rgba(248,81,73,0.15)', warning: 'rgba(210,153,34,0.15)', neutral: 'rgba(88,166,255,0.15)', healthy: 'rgba(63,185,80,0.15)' }[level] || 'rgba(136,148,158,0.1)')
const levelLabel = (level: string) => ({ danger: '危险', warning: '警告', neutral: '中性', healthy: '健康' }[level] || '-')
const dirIcon = (d: string) => d === '看涨' ? '▲' : d === '看跌' ? '▼' : '●'
const dirColor = (d: string) => d === '看涨' ? '#3fb950' : d === '看跌' ? '#f85149' : '#8b949e'

// 指标类型标签
const indicatorTypeLabel = (t?: string) => ({ leading: '领先', coincident: '同步', lagging: '滞后' }[t || ''] || '')
const indicatorTypeColor = (t?: string) => ({ leading: '#a371f7', coincident: '#58a6ff', lagging: '#8b949e' }[t || ''] || '#8b949e')
const indicatorTypeBg = (t?: string) => ({ leading: 'rgba(163,113,247,0.12)', coincident: 'rgba(88,166,255,0.12)', lagging: 'rgba(139,148,158,0.12)' }[t || ''] || 'rgba(139,148,158,0.08)')

// 趋势箭头
const trendIcon = (d?: string) => d === 'up' ? '▲' : d === 'down' ? '▼' : '●'
const trendColor = (d?: string) => d === 'up' ? '#3fb950' : d === 'down' ? '#f85149' : '#8b949e'

// 宏观周期阶段样式
const cycleStageColor = (s?: string) => ({ expansion: '#3fb950', peak: '#d29922', contraction: '#f85149', trough: '#58a6ff' }[s || ''] || '#8b949e')
const cycleStageBg = (s?: string) => ({ expansion: 'rgba(63,185,80,0.1)', peak: 'rgba(210,153,34,0.1)', contraction: 'rgba(248,81,73,0.1)', trough: 'rgba(88,166,255,0.1)' }[s || ''] || 'rgba(139,148,158,0.05)')

// ============ 组件 ============

export default function MacroData() {
  const [overview, setOverview] = useState<MacroOverview>({})
  const [chinaData, setChinaData] = useState<MacroDetailData>({})
  const [usData, setUsData] = useState<MacroDetailData>({})
  const [yieldCurve, setYieldCurve] = useState<{ cn: BondYieldPoint[]; us: BondYieldPoint[] } | null>(null)
  const [signals, setSignals] = useState<MacroSignals | null>(null)
  const [leadingData, setLeadingData] = useState<LeadingIndicatorsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'china' | 'us' | 'yield' | 'signals' | 'leading'>('overview')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, cn, us, yc, sig, leading] = await Promise.all([
        axios.get(`${API_BASE}/macro/overview`),
        axios.get(`${API_BASE}/macro/china`),
        axios.get(`${API_BASE}/macro/us`),
        axios.get(`${API_BASE}/macro/yield-curve`).catch(() => ({ data: null })),
        axios.get(`${API_BASE}/macro/signals`).catch(() => ({ data: null })),
        axios.get(`${API_BASE}/macro/leading-indicators`).catch(() => ({ data: null })),
      ])
      setOverview(ov.data); setChinaData(cn.data); setUsData(us.data)
      setYieldCurve(yc.data); setSignals(sig.data); setLeadingData(leading.data)
    } catch (e) { console.error('获取宏观数据失败:', e) } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // ============ 图表配置 ============

  const spreadOption = useMemo(() => {
    if (!yieldCurve) return null
    const usSpread = (yieldCurve.us || []).filter(d => d.spread_10y_2y != null)
    const cnSpread = (yieldCurve.cn || []).filter(d => d.spread_10y_2y != null)
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['美债2Y-10Y利差', '中债2Y-10Y利差'], top: 0, textStyle: { color: '#8b949e' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: usSpread.map(d => d.date), axisLabel: { fontSize: 11, color: '#8b949e' } },
      yAxis: { type: 'value', axisLabel: { formatter: '{value}%', color: '#8b949e' }, splitLine: { lineStyle: { type: 'dashed' as const, color: '#21262d' } } },
      series: [
        { name: '美债2Y-10Y利差', type: 'line', data: usSpread.map(d => d.spread_10y_2y), lineStyle: { width: 2 }, itemStyle: { color: '#ff6b6b' }, markLine: { silent: true, data: [{ yAxis: 0, lineStyle: { color: '#e74c3c', type: 'dashed' as const, width: 2 }, label: { formatter: '倒挂线', position: 'end' as const } }] } },
        { name: '中债2Y-10Y利差', type: 'line', data: cnSpread.map(d => d.spread_10y_2y), lineStyle: { width: 2 }, itemStyle: { color: '#58a6ff' } },
      ],
      backgroundColor: 'transparent',
    }
  }, [yieldCurve])

  const radarOption = useMemo(() => {
    if (!signals?.radar) return null
    return {
      tooltip: {},
      radar: {
        indicator: (signals.radar?.dimensions || []).map(d => ({ name: d, max: 100 })),
        shape: 'polygon' as const,
        splitArea: { areaStyle: { color: ['rgba(59,130,246,0.03)', 'rgba(59,130,246,0.06)'] } },
        axisLine: { lineStyle: { color: '#374151' } }, splitLine: { lineStyle: { color: '#374151' } },
        axisName: { color: '#9ca3af', fontSize: 11 },
      },
      series: [{ type: 'radar' as const, data: [{ value: signals.radar?.values || [], name: '宏观信号', areaStyle: { color: 'rgba(88,166,255,0.2)' }, lineStyle: { color: '#58a6ff', width: 2 }, itemStyle: { color: '#58a6ff' } }] }],
      backgroundColor: 'transparent',
    }
  }, [signals])

  // ============ 概览数据 ============

  const overviewGroups = useMemo(() => {
    const cards: { group: string; label: string; value: string; sub: string; date: string | undefined; highlight?: boolean }[] = [
      { group: '中国经济', label: 'GDP', value: fmtBig(overview.gdp?.latest?.gdp as number), sub: overview.gdp?.latest?.gdp_growth ? `同比 ${overview.gdp.latest.gdp_growth}%` : '', date: overview.gdp?.latest?.date as string },
      { group: '中国经济', label: 'CPI(全国)', value: fmt(overview.cpi?.latest?.cpi as number), sub: overview.cpi?.latest?.cpi_yoy ? `同比 ${(overview.cpi.latest.cpi_yoy as number) > 0 ? '+' : ''}${fmt(overview.cpi.latest.cpi_yoy as number)}%` : '', date: overview.cpi?.latest?.date as string },
      { group: '中国经济', label: 'PMI制造业', value: fmt(overview.pmi?.latest?.manufacturing as number, 1), sub: (overview.pmi?.latest?.manufacturing as number) >= 50 ? '扩张' : '收缩', date: overview.pmi?.latest?.date as string },
      { group: '中国经济', label: 'M2', value: fmtBig(overview.money_supply?.latest?.m2 as number), sub: overview.money_supply?.latest?.m2_growth ? `同比 ${fmt(overview.money_supply.latest.m2_growth as number)}%` : '', date: overview.money_supply?.latest?.date as string },
      { group: '中国经济', label: 'LPR(1Y)', value: overview.lpr?.latest?.lpr_1y ? fmt(overview.lpr.latest.lpr_1y as number) + '%' : '-', sub: '', date: overview.lpr?.latest?.date as string },
      { group: '中国经济', label: '工业增加值', value: overview.industrial_production?.latest?.value != null ? `${(overview.industrial_production.latest.value as number) > 0 ? '+' : ''}${fmt(overview.industrial_production.latest.value as number)}%` : '-', sub: '', date: overview.industrial_production?.latest?.date as string },
      { group: '中国经济', label: '贸易差额', value: overview.trade_balance?.latest?.value != null ? `${fmt(overview.trade_balance.latest.value as number, 1)}亿美元` : '-', sub: '', date: overview.trade_balance?.latest?.date as string },
      { group: '消费拐点', label: '消费者信心', value: fmt(overview.consumer_confidence?.latest?.confidence as number, 1), sub: (overview.consumer_confidence?.latest?.confidence as number) >= 100 ? '乐观' : '悲观', date: overview.consumer_confidence?.latest?.date as string, highlight: true },
      { group: '消费拐点', label: 'PPI', value: fmt(overview.ppi?.latest?.value as number, 1), sub: overview.ppi?.latest?.yoy != null ? `同比 ${(overview.ppi.latest.yoy as number) > 0 ? '+' : ''}${fmt(overview.ppi.latest.yoy as number)}%` : '', date: overview.ppi?.latest?.date as string, highlight: true },
      { group: '消费拐点', label: '社零增速', value: overview.retail_sales?.latest?.yoy != null ? `${(overview.retail_sales.latest.yoy as number) > 0 ? '+' : ''}${fmt(overview.retail_sales.latest.yoy as number)}%` : '-', sub: `累计 ${fmt(overview.retail_sales?.latest?.cumulative_yoy as number)}%`, date: overview.retail_sales?.latest?.date as string, highlight: true },
      { group: '消费拐点', label: '房价同比(一线)', value: overview.housing_price?.latest?.avg_yoy != null ? `${(overview.housing_price.latest.avg_yoy as number) > 0 ? '+' : ''}${fmt(overview.housing_price.latest.avg_yoy as number)}%` : '-', sub: '', date: (overview.housing_price?.latest?.date as string)?.slice(0, 10), highlight: true },
      { group: '消费拐点', label: '失业率', value: overview.unemployment?.latest?.value ? `${fmt(overview.unemployment.latest.value as number, 1)}%` : '-', sub: (overview.unemployment?.latest?.value as number) <= 5 ? '良好' : '偏高', date: overview.unemployment?.latest?.date as string, highlight: true },
      { group: '美国经济', label: '美联储利率', value: overview.us_fed_rate?.latest?.value != null ? `${fmt(overview.us_fed_rate.latest.value as number, 2)}%` : '-', sub: '', date: overview.us_fed_rate?.latest?.date as string },
      { group: '美国经济', label: '美国GDP', value: overview.us_gdp?.latest?.value != null ? `${fmt(overview.us_gdp.latest.value as number, 1)}%` : '-', sub: '', date: overview.us_gdp?.latest?.date as string },
      { group: '美国经济', label: 'ISM制造业PMI', value: fmt(overview.us_ism_pmi?.latest?.value as number, 1), sub: (overview.us_ism_pmi?.latest?.value as number) >= 50 ? '扩张' : '收缩', date: overview.us_ism_pmi?.latest?.date as string },
      { group: '美国经济', label: '非农就业(万)', value: overview.us_non_farm?.latest?.value != null ? fmt(overview.us_non_farm.latest.value as number, 1) : '-', sub: '', date: overview.us_non_farm?.latest?.date as string },
      { group: '利率信号', label: '美债2Y-10Y利差', value: overview.us_yield_spread?.latest?.spread_10y_2y != null ? `${fmt(overview.us_yield_spread.latest.spread_10y_2y as number, 2)}%` : '-', sub: overview.us_yield_spread?.latest?.spread_10y_2y != null ? ((overview.us_yield_spread.latest.spread_10y_2y as number) < 0 ? '⚠️ 倒挂' : '正常') : '', date: overview.us_yield_spread?.latest?.date as string },
      { group: '利率信号', label: '中债2Y-10Y利差', value: overview.cn_yield_spread?.latest?.spread_10y_2y != null ? `${fmt(overview.cn_yield_spread.latest.spread_10y_2y as number, 2)}%` : '-', sub: '', date: overview.cn_yield_spread?.latest?.date as string },
    ]
    const groups: Record<string, typeof cards> = {}
    cards.forEach(c => { if (!groups[c.group]) groups[c.group] = []; groups[c.group].push(c) })
    return groups
  }, [overview])

  const yieldCurveData = useMemo(() => {
    if (!yieldCurve) return null
    const usDataPoints = (yieldCurve.us || []).filter(d => d.y10 != null)
    const cnDataPoints = (yieldCurve.cn || []).filter(d => d.y10 != null)
    const latestUsDate = usDataPoints.length > 0 ? usDataPoints[usDataPoints.length - 1].date : ''
    const latestCnDate = cnDataPoints.length > 0 ? cnDataPoints[cnDataPoints.length - 1].date : ''
    const usPoint = usDataPoints.filter(d => d.date === latestUsDate).pop() || null
    const cnPoint = cnDataPoints.filter(d => d.date === latestCnDate).pop() || null
    return { usData: usDataPoints, cnData: cnDataPoints, usPoint, cnPoint }
  }, [yieldCurve])

  // ============ 表格列定义 ============

  const makeColumns = (cols: { key: string; label: string }[]): Column<Record<string, any>>[] =>
    cols.map(c => ({ key: c.key, title: c.label, dataIndex: c.key }))

  // ============ Tab定义 ============

  const tabs = [
    { key: 'overview', label: '概览' },
    { key: 'leading', label: '领先指标' },
    { key: 'signals', label: '信号仪表盘' },
    { key: 'china', label: '中国详情' },
    { key: 'us', label: '美国' },
    { key: 'yield', label: '收益率曲线' },
  ]

  // ============ 渲染 ============

  return (
    <div>
      <PageSection title="宏观经济数据" extra={<button className="btn-add" onClick={loadData}>刷新数据</button>} compact>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>中国 + 美国 核心宏观指标 · 收益率曲线</span>
      </PageSection>

      <TabBar tabs={tabs} activeKey={activeTab} onChange={k => setActiveTab(k as any)} style={{ marginBottom: 16 }} />

      {loading ? <LoadingSpinner /> : (
        <>
          {/* 概览 */}
          {activeTab === 'overview' && Object.entries(overviewGroups).map(([group, items]) => (
            <PageSection key={group} title={group}>
              <StatCardGroup columns={4}>
                {items.map(c => (
                  <StatCard key={c.label} label={c.label} value={c.value} color={c.highlight ? 'var(--accent-blue)' : undefined} />
                ))}
              </StatCardGroup>
            </PageSection>
          ))}

          {/* 领先指标仪表盘 */}
          {activeTab === 'leading' && leadingData && (
            <>
              <PageSection title="领先指标综合评估">
                <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                  {/* 综合得分 */}
                  <div style={{ background: levelBg(leadingData.composite?.level ?? ''), border: `1px solid ${levelColor(leadingData.composite?.level ?? '')}33`, borderRadius: 'var(--radius-md)', padding: 20, minWidth: 200, textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>领先指标综合得分</div>
                    <div style={{ width: 72, height: 72, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: levelColor(leadingData.composite?.level ?? ''), color: '#fff', fontWeight: 800, fontSize: 28, margin: '0 auto 8px' }}>{leadingData.composite?.score ?? '-'}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: levelColor(leadingData.composite?.level ?? '') }}>{levelLabel(leadingData.composite?.level ?? '')}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{leadingData.composite?.expansion_signals}/{leadingData.composite?.total_signals} 指标指向扩张</div>
                  </div>
                  {/* 解读 */}
                  <div style={{ flex: 1, minWidth: 300 }}>
                    <div style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 12 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>综合解读</div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{leadingData.composite?.interpretation}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, color: indicatorTypeColor('leading'), background: indicatorTypeBg('leading'), padding: '3px 8px', borderRadius: 4 }}>领先指标: 在经济拐点前3-18个月发出信号</span>
                      <span style={{ fontSize: 11, color: indicatorTypeColor('coincident'), background: indicatorTypeBg('coincident'), padding: '3px 8px', borderRadius: 4 }}>同步指标: 确认当前状态</span>
                      <span style={{ fontSize: 11, color: indicatorTypeColor('lagging'), background: indicatorTypeBg('lagging'), padding: '3px 8px', borderRadius: 4 }}>滞后指标: 确认趋势已形成</span>
                    </div>
                  </div>
                </div>
              </PageSection>

              <PageSection title="领先指标明细">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
                  {(leadingData.indicators || []).map((ind, idx) => (
                    <div key={idx} style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', border: `1px solid ${ind.signal === 'expansion' || ind.signal === 'optimistic' || ind.signal === 'normal' || ind.signal === 'expanding' || ind.signal === 'loose' ? '#3fb95033' : '#f8514933'}`, padding: 16 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{ind.name}</span>
                          <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, color: indicatorTypeColor(ind.type), background: indicatorTypeBg(ind.type) }}>{indicatorTypeLabel(ind.type)}</span>
                          {ind.country && <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, color: 'var(--text-muted)', background: 'var(--bg-quaternary, rgba(139,148,158,0.1))' }}>{ind.country}</span>}
                        </div>
                        {ind.trend?.direction && (
                          <span style={{ fontSize: 12, color: trendColor(ind.trend.direction), fontWeight: 700 }}>
                            {trendIcon(ind.trend.direction)} {ind.trend.change_pct != null ? `${ind.trend.change_pct > 0 ? '+' : ''}${ind.trend.change_pct}%` : ''}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 6 }}>
                        {ind.value != null ? (typeof ind.value === 'number' ? ind.value.toFixed(1) : ind.value) : '-'}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, lineHeight: 1.5 }}>{ind.desc}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>领先 {ind.lead_months}</span>
                        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{ind.source}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </PageSection>
            </>
          )}

          {/* 中国详情 */}
          {activeTab === 'china' && (
            <>
              <PageSection title="GDP（国内生产总值）">
                <DataTable columns={makeColumns([{ key: 'date', label: '季度' }, { key: 'gdp', label: 'GDP(亿元)' }, { key: 'gdp_growth', label: 'GDP同比(%)' }, { key: 'primary', label: '第一产业(亿)' }, { key: 'secondary', label: '第二产业(亿)' }, { key: 'tertiary', label: '第三产业(亿)' }])} data={(chinaData.gdp || []) as any[]} rowKey="date" compact />
              </PageSection>
              <PageSection title="CPI（居民消费价格指数）">
                <DataTable columns={makeColumns([{ key: 'date', label: '月份' }, { key: 'cpi', label: '全国当月' }, { key: 'cpi_yoy', label: '同比(%)' }, { key: 'city', label: '城市当月' }, { key: 'rural', label: '农村当月' }])} data={(chinaData.cpi || []) as any[]} rowKey="date" compact />
              </PageSection>
              <PageSection title="PMI（采购经理指数）">
                <DataTable columns={makeColumns([{ key: 'date', label: '月份' }, { key: 'manufacturing', label: '制造业PMI' }, { key: 'non_manufacturing', label: '非制造业PMI' }])} data={(chinaData.pmi || []) as any[]} rowKey="date" compact />
              </PageSection>
              <PageSection title="货币供应量">
                <DataTable columns={makeColumns([{ key: 'date', label: '月份' }, { key: 'm2', label: 'M2(亿元)' }, { key: 'm2_growth', label: 'M2同比(%)' }, { key: 'm1', label: 'M1(亿元)' }, { key: 'm1_growth', label: 'M1同比(%)' }])} data={(chinaData.money_supply || []) as any[]} rowKey="date" compact />
              </PageSection>
              <PageSection title="LPR（贷款市场报价利率）">
                <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'lpr_1y', label: '1年期LPR(%)' }, { key: 'lpr_5y', label: '5年期LPR(%)' }])} data={((chinaData.lpr || []) as any[]).slice().reverse()} rowKey="date" compact />
              </PageSection>
              <PageSection title="消费拐点指标">
                <DataTable columns={makeColumns([{ key: 'date', label: '月份' }, { key: 'confidence', label: '消费者信心' }, { key: 'value', label: 'PPI当月' }, { key: 'yoy', label: 'PPI同比(%)' }])} data={(chinaData.consumer_confidence || []) as any[]} rowKey="date" compact />
              </PageSection>
            </>
          )}

          {/* 美国详情 */}
          {activeTab === 'us' && (
            <>
              <PageSection title="美联储利率决议">
                <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'value', label: '利率(%)' }, { key: 'forecast', label: '预测(%)' }, { key: 'previous', label: '前值(%)' }])} data={((usData.fed_rate || []) as any[]).slice(0, 24)} rowKey="date" compact />
              </PageSection>
              <PageSection title="美国GDP（季度年化）">
                <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'value', label: 'GDP增速(%)' }, { key: 'forecast', label: '预测(%)' }, { key: 'previous', label: '前值(%)' }])} data={((usData.gdp || []) as any[]).slice(0, 24)} rowKey="date" compact />
              </PageSection>
              <PageSection title="ISM制造业PMI">
                <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'value', label: 'PMI' }, { key: 'forecast', label: '预测' }, { key: 'previous', label: '前值' }])} data={((usData.ism_pmi || []) as any[]).slice(0, 24)} rowKey="date" compact />
              </PageSection>
              <PageSection title="非农就业人数变化（万人）">
                <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'value', label: '变化(万)' }, { key: 'forecast', label: '预测(万)' }, { key: 'previous', label: '前值(万)' }])} data={((usData.non_farm || []) as any[]).slice(0, 24)} rowKey="date" compact />
              </PageSection>
              <PageSection title="美国CPI（月度）">
                <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'value', label: 'CPI' }])} data={((usData.cpi || []) as any[]).slice(0, 24)} rowKey="date" compact />
              </PageSection>
            </>
          )}

          {/* 收益率曲线 */}
          {activeTab === 'yield' && yieldCurve && yieldCurveData && (
            <>
              <PageSection title="2Y-10Y 利差走势">
                {spreadOption && <ReactECharts option={spreadOption} style={{ height: 350 }} />}
              </PageSection>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                <PageSection title="美国国债收益率曲线（最新）">
                  {yieldCurveData.usPoint && (
                    <StatCardGroup columns={4} style={{ marginBottom: 12 }}>
                      {[
                        { label: '2年', value: yieldCurveData.usPoint.y2 },
                        { label: '5年', value: yieldCurveData.usPoint.y5 },
                        { label: '10年', value: yieldCurveData.usPoint.y10 },
                        { label: '30年', value: yieldCurveData.usPoint.y30 },
                      ].map(t => <StatCard key={t.label} label={t.label} value={t.value != null ? `${t.value}%` : '-'} />)}
                    </StatCardGroup>
                  )}
                  <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'y2', label: '2年(%)' }, { key: 'y5', label: '5年(%)' }, { key: 'y10', label: '10年(%)' }, { key: 'y30', label: '30年(%)' }, { key: 'spread_10y_2y', label: '10Y-2Y(%)' }])} data={(yieldCurve.us || []).slice(-12) as any[]} rowKey="date" compact />
                </PageSection>
                <PageSection title="中国国债收益率曲线（最新）">
                  {yieldCurveData.cnPoint && (
                    <StatCardGroup columns={4} style={{ marginBottom: 12 }}>
                      {[
                        { label: '2年', value: yieldCurveData.cnPoint.y2 },
                        { label: '5年', value: yieldCurveData.cnPoint.y5 },
                        { label: '10年', value: yieldCurveData.cnPoint.y10 },
                        { label: '30年', value: yieldCurveData.cnPoint.y30 },
                      ].map(t => <StatCard key={t.label} label={t.label} value={t.value != null ? `${t.value}%` : '-'} />)}
                    </StatCardGroup>
                  )}
                  <DataTable columns={makeColumns([{ key: 'date', label: '日期' }, { key: 'y2', label: '2年(%)' }, { key: 'y5', label: '5年(%)' }, { key: 'y10', label: '10年(%)' }, { key: 'y30', label: '30年(%)' }, { key: 'spread_10y_2y', label: '10Y-2Y(%)' }])} data={(yieldCurve.cn || []).slice(-12) as any[]} rowKey="date" compact />
                </PageSection>
              </div>
            </>
          )}

          {/* 信号仪表盘 */}
          {activeTab === 'signals' && signals && (
            <>
              {/* 宏观周期判定 */}
              {signals.macro_cycle && signals.macro_cycle.stage && signals.macro_cycle.stage !== 'unknown' && (
                <PageSection title="宏观周期判定">
                  <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <div style={{ background: cycleStageBg(signals.macro_cycle.stage), border: `2px solid ${cycleStageColor(signals.macro_cycle.stage)}44`, borderRadius: 'var(--radius-md)', padding: 20, minWidth: 180, textAlign: 'center' }}>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>当前周期阶段</div>
                      <div style={{ fontSize: 28, fontWeight: 800, color: cycleStageColor(signals.macro_cycle.stage), marginBottom: 4 }}>{signals.macro_cycle.label}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>置信度 {signals.macro_cycle.confidence}%</div>
                    </div>
                    <div style={{ flex: 1, minWidth: 300 }}>
                      <div style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 10 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>配置建议</div>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 8 }}>{signals.macro_cycle.recommendation}</div>
                        {signals.macro_cycle.asset_bias && (
                          <div style={{ fontSize: 12, color: cycleStageColor(signals.macro_cycle.stage), fontWeight: 600 }}>资产偏好: {signals.macro_cycle.asset_bias}</div>
                        )}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {(signals.macro_cycle.evidence || []).map((e, i) => (
                          <span key={i} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: 'var(--bg-quaternary, rgba(139,148,158,0.08))', color: 'var(--text-secondary)' }}>{e}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </PageSection>
              )}

              <PageSection title="宏观信号">
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                  {(signals.signals || []).map((sig, idx) => (
                    <div key={sig.id ?? idx} style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', border: `1px solid ${levelColor(sig.level ?? '')}33`, padding: 16 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{sig.name}</span>
                          {sig.indicator_type && sig.indicator_type !== 'mixed' && (
                            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, color: indicatorTypeColor(sig.indicator_type), background: indicatorTypeBg(sig.indicator_type) }}>{indicatorTypeLabel(sig.indicator_type)}</span>
                          )}
                        </div>
                        <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, color: levelColor(sig.level ?? ''), background: levelBg(sig.level ?? '') }}>{levelLabel(sig.level ?? '')}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                        <div style={{ width: 48, height: 48, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: levelColor(sig.level ?? ''), color: '#fff', fontWeight: 700, fontSize: 18, flexShrink: 0 }}>{sig.score}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 4 }}>{sig.detail}</div>
                          <div style={{ fontSize: 16, fontWeight: 700, color: levelColor(sig.level ?? '') }}>{sig.probability}</div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {(sig.drivers || []).map((d, i) => (
                          <span key={i} style={{ fontSize: 11, padding: '2px 6px', borderRadius: 4, background: levelBg(d.level ?? ''), color: levelColor(d.level ?? ''), border: `1px solid ${levelColor(d.level ?? '')}22` }}>
                            {d.type && <span style={{ fontSize: 9, color: indicatorTypeColor(d.type), marginRight: 3 }}>[{indicatorTypeLabel(d.type)}]</span>}
                            {d.name}: {d.value} {d.desc}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </PageSection>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16, marginBottom: 16 }}>
                <PageSection title="宏观雷达">
                  {radarOption && <ReactECharts option={radarOption} style={{ height: 300 }} />}
                </PageSection>
                <PageSection title="资产配置信号">
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
                    {(signals.assets || []).map((asset, idx) => (
                      <div key={asset.name ?? idx} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12, borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)', border: `1px solid ${dirColor(asset.direction ?? '')}22` }}>
                        <div style={{ width: 36, height: 36, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: `${dirColor(asset.direction ?? '')}20`, color: dirColor(asset.direction ?? ''), fontSize: 16, fontWeight: 700, flexShrink: 0 }}>{dirIcon(asset.direction ?? '')}</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{asset.name}</span>
                            <span style={{ fontSize: 14, fontWeight: 700, color: dirColor(asset.direction ?? '') }}>{asset.confidence}%</span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{asset.reason}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </PageSection>
              </div>

              {signals.cross_validation?.pmi && (
                <div style={{ background: signals.cross_validation.pmi.includes('⚠️') ? 'rgba(210,153,34,0.1)' : 'rgba(63,185,80,0.1)', border: `1px solid ${signals.cross_validation.pmi.includes('⚠️') ? '#d2992233' : '#3fb95033'}`, borderRadius: 'var(--radius-md)', padding: 12, marginBottom: 16, fontSize: 13, color: signals.cross_validation.pmi.includes('⚠️') ? '#d29922' : '#3fb950' }}>
                  <strong>PMI交叉验证：</strong>{signals.cross_validation.pmi}
                </div>
              )}

              <PageSection title="数据质量与来源">
                <div style={{ display: 'flex', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>FRED数据源: <strong style={{ color: signals.cross_validation?.fred_available ? '#3fb950' : '#f85149' }}>{signals.cross_validation?.fred_available ? '✓ 已接入' : '✗ 未配置'}</strong></span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>FRED指标数: <strong style={{ color: '#58a6ff' }}>{signals.cross_validation?.fred_indicators || 0}</strong></span>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>AKShare指标数: <strong style={{ color: '#58a6ff' }}>{signals.cross_validation?.akshare_indicators || 0}</strong></span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 6 }}>
                  {(signals.data_quality || []).map((dq, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)', fontSize: 11 }}>
                      <span style={{ flex: 1, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{dq.name}</span>
                      <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{dq.source}</span>
                      <StatusBadge status={dq.freshness === 'fresh' ? 'success' : dq.freshness === 'recent' ? 'warning' : 'error'} dot />
                      <StatusBadge status={dq.confidence === 'high' ? 'success' : dq.confidence === 'medium' ? 'warning' : 'error'} dot />
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', display: 'flex', gap: 16 }}>
                  <span>● <span style={{ color: '#3fb950' }}>绿</span>=新鲜/高置信</span>
                  <span>● <span style={{ color: '#d29922' }}>黄</span>=近期/中置信</span>
                  <span>● <span style={{ color: '#f85149' }}>红</span>=过时/低置信</span>
                </div>
              </PageSection>

              <PageSection title="方法论与免责声明">
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.8 }}>
                  <p><strong>指标分类体系：</strong></p>
                  <div style={{ display: 'flex', gap: 16, margin: '6px 0', flexWrap: 'wrap' }}>
                    <span style={{ color: indicatorTypeColor('leading'), background: indicatorTypeBg('leading'), padding: '2px 8px', borderRadius: 4 }}>领先指标 — 经济拐点前3-18个月发出信号</span>
                    <span style={{ color: indicatorTypeColor('coincident'), background: indicatorTypeBg('coincident'), padding: '2px 8px', borderRadius: 4 }}>同步指标 — 确认经济当前状态</span>
                    <span style={{ color: indicatorTypeColor('lagging'), background: indicatorTypeBg('lagging'), padding: '2px 8px', borderRadius: 4 }}>滞后指标 — 确认趋势已形成</span>
                  </div>
                  {signals.indicator_types?.summary && (
                    <p style={{ marginTop: 4, fontSize: 11 }}>当前信号包含: 领先{signals.indicator_types.summary.leading || 0}个 / 同步{signals.indicator_types.summary.coincident || 0}个 / 滞后{signals.indicator_types.summary.lagging || 0}个</p>
                  )}
                  {signals.methodology?.indicator_classification && <p style={{ marginTop: 6 }}>{signals.methodology.indicator_classification}</p>}
                  {signals.methodology?.cycle_detection && <p style={{ marginTop: 4 }}>{signals.methodology.cycle_detection}</p>}
                  <p style={{ marginTop: 8 }}><strong>数据源优先级：</strong></p>
                  <ul style={{ paddingLeft: 20, margin: '4px 0' }}>
                    {(signals.methodology?.data_sources || []).map((ds, i) => <li key={i}><strong>{ds.name}</strong>（优先级{ds.priority}）— {ds.desc}</li>)}
                  </ul>
                  <p style={{ marginTop: 8 }}><strong>局限性：</strong></p>
                  <ul style={{ paddingLeft: 20, margin: '4px 0' }}>
                    {(signals.methodology?.limitations || []).map((l, i) => <li key={i}>{l}</li>)}
                  </ul>
                </div>
              </PageSection>

              <div style={{ textAlign: 'right', fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                信号更新时间: {signals.updated_at?.replace('T', ' ').slice(0, 19) || '-'}
              </div>
            </>
          )}
        </>
      )}

      {/* 数据说明 */}
      <PageSection title="数据说明">
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          <p><strong>基础指标：</strong>数据来源 AKShare（聚合东方财富、新浪财经等），缓存5分钟。PMI以50为荣枯线，LPR每月20日更新。</p>
          <p><strong>美国核心指标：</strong>美联储利率（全球资产定价之锚）、ISM PMI（领先指标）、非农就业（美联储决策参考）。</p>
          <p><strong>收益率曲线：</strong>2Y-10Y利差倒挂是过去50年最准确的衰退预测指标。</p>
          <p><strong>消费拐点：</strong>消费者信心100为中性线，PPI 100为基准，社零增速关注3%以上，失业率关注5%以下。</p>
        </div>
      </PageSection>
    </div>
  )
}
