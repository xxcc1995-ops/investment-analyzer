import { useState, useCallback, useEffect, lazy, Suspense, useMemo, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import { stockApi } from '../services/api'
import type { StockBasic, FinancialReport, ValuationHistory, DividendHistory, FragilityResult, DerivedMetrics, CrossAnalysisResult } from '../services/api'
import { StatCard, StatCardGroup, PageSection, DataTable, TabBar, LoadingSpinner, EmptyState, StatusBadge, Tag } from '../components/ui'
import type { Column } from '../components/ui'
import { AIAnalysisPanel } from '../components/AIAnalysisPanel'

const FinancialStatements = lazy(() => import('./FinancialStatements'))

// ============ 辅助函数 ============

const formatNum = (num: number | null | undefined, suffix = '') => {
  if (num === null || num === undefined) return '-'
  return num.toFixed(2) + suffix
}

const formatAmount = (num: number | null | undefined) => {
  if (num === null || num === undefined) return '-'
  if (num >= 10000) return (num / 10000).toFixed(2) + '亿'
  return num.toFixed(2) + '万'
}

const formatVolume = (num: number | null | undefined) => {
  if (num === null || num === undefined) return '-'
  if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿股'
  if (num >= 10000) return (num / 10000).toFixed(2) + '万股'
  return num + '股'
}

const getValuationLevel = (type: 'pe' | 'pb' | 'div', valuationHistory: ValuationHistory | null) => {
  const stats = valuationHistory?.stats?.[type]
  if (!stats) return { level: '-', color: 'var(--text-muted)', percentile: null }
  const p = stats.percentile
  if (type === 'div') {
    if (p >= 70) return { level: '高股息', color: '#3fb950', percentile: p }
    if (p >= 30) return { level: '适中', color: '#1890ff', percentile: p }
    return { level: '低股息', color: '#ff4d4f', percentile: p }
  }
  if (p <= 20) return { level: '极度低估', color: '#3fb950', percentile: p }
  if (p <= 40) return { level: '低估', color: '#58a6ff', percentile: p }
  if (p <= 60) return { level: '合理', color: '#8b949e', percentile: p }
  if (p <= 80) return { level: '偏高', color: '#d29922', percentile: p }
  return { level: '高估', color: '#f85149', percentile: p }
}

const getScoreColor = (score: number, max: number) => {
  const ratio = score / max
  if (ratio >= 0.75) return '#16a34a'
  if (ratio >= 0.5) return '#ca8a04'
  return '#dc2626'
}

const getDebtStatus = (ratio?: number | null) => {
  if (!ratio) return { text: '-', color: 'var(--text-muted)' }
  if (ratio < 40) return { text: '健康', color: '#52c41a' }
  if (ratio < 60) return { text: '适中', color: '#faad14' }
  return { text: '偏高', color: '#ff4d4f' }
}

// ============ 局部接口 ============

interface StockAnalysisProps {
  code: string
}

// ============ 交叉分析面板 ============

function CrossAnalysisPanel({ data, loading }: { data: CrossAnalysisResult | null; loading: boolean }) {
  if (loading) return <LoadingSpinner text="加载交叉分析数据..." />
  if (!data) return <EmptyState icon="🔍" title="暂无交叉分析数据" />

  const { rating, insights, cross_validation, three_dimension, dupont, horizontal_analysis, vertical_analysis, correlation_analysis, dimension_scores } = data

  const getScoreColor = (score: number) => {
    if (score >= 75) return '#16a34a'
    if (score >= 55) return '#ca8a04'
    return '#dc2626'
  }

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return '#16a34a'
    if (grade.startsWith('B')) return '#ca8a04'
    return '#dc2626'
  }

  return (
    <>
      {/* 综合评级 */}
      <PageSection title="综合评级">
        <div style={{ display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{
            width: 80, height: 80, borderRadius: '50%',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            background: `${getGradeColor(rating.grade)}18`, border: `3px solid ${getGradeColor(rating.grade)}`,
          }}>
            <span style={{ fontSize: 24, fontWeight: 800, color: getGradeColor(rating.grade) }}>{rating.grade}</span>
            <span style={{ fontSize: 11, color: getGradeColor(rating.grade) }}>{rating.score}分</span>
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{rating.recommendation}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
              最强因子: <span style={{ color: '#16a34a' }}>{rating.top_factor}</span>
              {' | '}
              最弱因子: <span style={{ color: '#dc2626' }}>{rating.worst_factor}</span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {rating.details.map((d, i) => (
                <span key={i} style={{
                  padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                  background: `${getScoreColor(d.score)}15`, color: getScoreColor(d.score),
                  border: `1px solid ${getScoreColor(d.score)}30`,
                }}>
                  {d.item} {d.score}
                </span>
              ))}
            </div>
          </div>
        </div>
      </PageSection>

      {/* 三维分析：估值-盈利-动量 */}
      <PageSection title="估值-盈利-动量 三维分析">
        <StatCardGroup columns={3}>
          <StatCard
            label="估值"
            value={`${three_dimension.valuation.score}分`}
            suffix={three_dimension.valuation.level}
            color={getScoreColor(three_dimension.valuation.score)}
          />
          <StatCard
            label="盈利能力"
            value={`${three_dimension.profitability.score}分`}
            suffix={three_dimension.profitability.level}
            color={getScoreColor(three_dimension.profitability.score)}
          />
          <StatCard
            label="动量"
            value={`${three_dimension.momentum.score}分`}
            suffix={three_dimension.momentum.level}
            color={getScoreColor(three_dimension.momentum.score)}
          />
        </StatCardGroup>
      </PageSection>

      {/* 交叉验证 */}
      <PageSection title="多指标交叉验证">
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{
            width: 60, height: 60, borderRadius: '50%', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: `${getScoreColor(cross_validation.consistency_score)}18`,
            border: `2px solid ${getScoreColor(cross_validation.consistency_score)}`,
          }}>
            <span style={{ fontSize: 18, fontWeight: 800, color: getScoreColor(cross_validation.consistency_score) }}>
              {cross_validation.consistency_score}
            </span>
          </div>
          <div style={{ flex: 1 }}>
            {cross_validation.flags.length > 0 ? (
              <div style={{ marginBottom: 8 }}>
                {cross_validation.flags.map((flag, i) => (
                  <div key={i} style={{ fontSize: 12, color: '#dc2626', marginBottom: 4 }}>⚠ {flag}</div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: '#16a34a', marginBottom: 8 }}>各指标一致性良好，无异常信号</div>
            )}
            {cross_validation.details.length > 0 && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {cross_validation.details.map((d, i) => (
                  <span key={i} style={{
                    padding: '2px 8px', borderRadius: 10, fontSize: 11,
                    background: d.status === 'excellent' ? '#16a34a15' : d.status === 'pass' ? '#58a6ff15' : '#d2992215',
                    color: d.status === 'excellent' ? '#16a34a' : d.status === 'pass' ? '#58a6ff' : '#d29922',
                  }}>
                    {d.check}: {d.status === 'excellent' ? '优秀' : d.status === 'pass' ? '通过' : '警告'}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </PageSection>

      {/* 杜邦分析 */}
      {dupont.roe !== null && (
        <PageSection title="杜邦分析（ROE质量）">
          <StatCardGroup columns={4}>
            <StatCard label="ROE" value={dupont.roe?.toFixed(1) + '%'} color={getScoreColor(dupont.roe_quality_score)} />
            <StatCard label="净利率" value={(dupont.net_margin ?? 0).toFixed(1) + '%'} />
            <StatCard label="资产周转率" value={dupont.asset_turnover?.toFixed(3) ?? '-'} />
            <StatCard label="权益乘数" value={dupont.equity_multiplier?.toFixed(2) ?? '-'} />
          </StatCardGroup>
          <div style={{ marginTop: 8, fontSize: 13 }}>
            <span style={{ fontWeight: 600 }}>ROE质量评估: </span>
            <span style={{ color: getScoreColor(dupont.roe_quality_score) }}>{dupont.roe_quality}</span>
            {dupont.roe_quality_score !== undefined && (
              <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>({dupont.roe_quality_score}分)</span>
            )}
          </div>
        </PageSection>
      )}

      {/* 生命周期 */}
      <PageSection title="生命周期分析">
        <StatCardGroup columns={3}>
          <StatCard
            label="当前阶段"
            value={vertical_analysis.lifecycle.stage}
            color={vertical_analysis.lifecycle.stage.includes('成长') ? '#16a34a' :
              vertical_analysis.lifecycle.stage.includes('衰退') ? '#dc2626' : '#ca8a04'}
          />
          <StatCard label="判断置信度" value={vertical_analysis.lifecycle.confidence + '%'} />
          <StatCard
            label="趋势信号"
            value={vertical_analysis.lifecycle.trend_signal}
            color={vertical_analysis.lifecycle.trend_signal === '加速' ? '#16a34a' :
              vertical_analysis.lifecycle.trend_signal === '减速' ? '#dc2626' : '#ca8a04'}
          />
        </StatCardGroup>
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          近3年均值: 营收增长 {vertical_analysis.lifecycle.details.avg_revenue_growth.toFixed(1)}%
          | 利润增长 {vertical_analysis.lifecycle.details.avg_profit_growth.toFixed(1)}%
          | ROE {vertical_analysis.lifecycle.details.avg_roe.toFixed(1)}%
        </div>
      </PageSection>

      {/* 行业竞争力 */}
      {horizontal_analysis.peers.length > 0 && (
        <PageSection title={`行业竞争力（${horizontal_analysis.industry}）`}>
          <div style={{ marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>竞争力评分: </span>
            <span style={{ color: getScoreColor(horizontal_analysis.competitive_position.score), fontWeight: 700 }}>
              {horizontal_analysis.competitive_position.score}分
            </span>
          </div>
          {Object.keys(horizontal_analysis.competitive_position.rankings).length > 0 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
              {Object.entries(horizontal_analysis.competitive_position.rankings).map(([key, val]) => (
                <span key={key} style={{
                  padding: '4px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                  background: val.rank === 1 ? '#16a34a15' : '#58a6ff15',
                  color: val.rank === 1 ? '#16a34a' : '#58a6ff',
                  border: `1px solid ${val.rank === 1 ? '#16a34a30' : '#58a6ff30'}`,
                }}>
                  {key}: 第{val.rank}/{val.total}
                </span>
              ))}
            </div>
          )}
          {/* 同行对比表 */}
          <DataTable
            columns={[
              { key: 'name', title: '公司', dataIndex: 'name' },
              { key: 'roe', title: 'ROE(%)', dataIndex: 'roe', align: 'right' },
              { key: 'gross_margin', title: '毛利率(%)', dataIndex: 'gross_margin', align: 'right' },
              { key: 'net_margin', title: '净利率(%)', dataIndex: 'net_margin', align: 'right' },
              { key: 'revenue_growth', title: '营收增长(%)', dataIndex: 'revenue_growth', align: 'right', colorize: true },
              { key: 'debt_ratio', title: '负债率(%)', dataIndex: 'debt_ratio', align: 'right' },
            ]}
            data={horizontal_analysis.peers as any[]}
            rowKey={(r: any) => r.code}
            emptyText="暂无同行数据"
            striped
          />
          {Object.keys(horizontal_analysis.industry_avg).length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
              行业均值: ROE {horizontal_analysis.industry_avg.roe?.toFixed(1)}%
              | 毛利率 {horizontal_analysis.industry_avg.gross_margin?.toFixed(1)}%
              | 负债率 {horizontal_analysis.industry_avg.debt_ratio?.toFixed(1)}%
            </div>
          )}
        </PageSection>
      )}

      {/* 相关性分析 */}
      {correlation_analysis.pairs.length > 0 && (
        <PageSection title="指标相关性分析">
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{correlation_analysis.summary}</div>
          <DataTable
            columns={[
              { key: 'metric1', title: '指标1', dataIndex: 'metric1' },
              { key: 'metric2', title: '指标2', dataIndex: 'metric2' },
              { key: 'correlation', title: '相关系数', dataIndex: 'correlation', align: 'right',
                render: (v: number) => <span style={{ fontWeight: 600 }}>{v}</span> },
              { key: 'strength', title: '强度', dataIndex: 'strength', align: 'center',
                render: (v: string) => (
                  <span style={{
                    color: v === '强' ? '#16a34a' : v === '中' ? '#ca8a04' : '#8b949e',
                    fontWeight: 600,
                  }}>{v}</span>
                ) },
              { key: 'direction', title: '方向', dataIndex: 'direction', align: 'center' },
            ]}
            data={correlation_analysis.pairs as any[]}
            rowKey={(_: any, i: number) => String(i)}
            emptyText="暂无相关性数据"
            striped
          />
        </PageSection>
      )}

      {/* 综合洞察 */}
      <PageSection title="投资洞察">
        <div style={{ marginBottom: 12, fontSize: 14, lineHeight: 1.8 }}>{insights.summary}</div>

        {insights.strengths.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#16a34a', marginBottom: 4 }}>优势</div>
            {insights.strengths.map((s, i) => (
              <div key={i} style={{ fontSize: 12, color: '#16a34a', paddingLeft: 12 }}>+ {s}</div>
            ))}
          </div>
        )}

        {insights.weaknesses.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#dc2626', marginBottom: 4 }}>劣势</div>
            {insights.weaknesses.map((w, i) => (
              <div key={i} style={{ fontSize: 12, color: '#dc2626', paddingLeft: 12 }}>- {w}</div>
            ))}
          </div>
        )}

        {insights.key_risks.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#d29922', marginBottom: 4 }}>风险信号</div>
            {insights.key_risks.map((r, i) => (
              <div key={i} style={{ fontSize: 12, color: '#d29922', paddingLeft: 12 }}>⚠ {r}</div>
            ))}
          </div>
        )}

        {insights.opportunities.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#58a6ff', marginBottom: 4 }}>机会</div>
            {insights.opportunities.map((o, i) => (
              <div key={i} style={{ fontSize: 12, color: '#58a6ff', paddingLeft: 12 }}>◆ {o}</div>
            ))}
          </div>
        )}

        {insights.threats.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#8b949e', marginBottom: 4 }}>威胁</div>
            {insights.threats.map((t, i) => (
              <div key={i} style={{ fontSize: 12, color: '#8b949e', paddingLeft: 12 }}>◇ {t}</div>
            ))}
          </div>
        )}

        <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 6, fontSize: 13, fontWeight: 600 }}>
          结论: {insights.conclusion}
        </div>
      </PageSection>

      {/* 更新时间 */}
      <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
        交叉分析更新时间: {data.update_time}
      </div>
    </>
  )
}

// ============ 主组件 ============

export default function StockAnalysis({ code }: StockAnalysisProps) {
  const [selectedStock, setSelectedStock] = useState<StockBasic | null>(null)
  const [financials, setFinancials] = useState<FinancialReport[]>([])
  const [valuationHistory, setValuationHistory] = useState<ValuationHistory | null>(null)
  const [dividendHistory, setDividendHistory] = useState<DividendHistory | null>(null)
  const [fragility, setFragility] = useState<FragilityResult | null>(null)
  const [derivedMetrics, setDerivedMetrics] = useState<DerivedMetrics | null>(null)
  const [crossAnalysis, setCrossAnalysis] = useState<CrossAnalysisResult | null>(null)
  const [crossLoading, setCrossLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [valuationLoading, setValuationLoading] = useState(false)
  const [valuationError, setValuationError] = useState<string | null>(null)
  const [fetchTime, setFetchTime] = useState('')
  const [latestReport, setLatestReport] = useState('')
  const [sectionView, setSectionView] = useState<'overview' | 'cross' | 'ai' | 'f12'>('overview')

  // 竞态条件保护：请求计数器
  const requestCounter = useRef(0)

  const loadStock = useCallback(async (stockCode: string) => {
    const requestId = ++requestCounter.current
    setLoading(true)
    setValuationHistory(null)
    setValuationError(null)
    setDerivedMetrics(null)
    setActiveTab('overview')
    try {
      const [basicRes, finRes] = await Promise.all([
        stockApi.getBasic(stockCode),
        stockApi.getFinancials(stockCode),
      ])
      setSelectedStock(basicRes.data)
      setFinancials(finRes.data.reports || [])
      setFetchTime(basicRes.data.fetch_time || new Date().toLocaleString())
      setLatestReport(finRes.data.latest_report_date || '')

      // 异步加载估值历史（带竞态保护）
      stockApi.getValuationHistory(stockCode)
        .then(res => { if (requestId === requestCounter.current) setValuationHistory(res.data) })
        .catch(() => { if (requestId === requestCounter.current) setValuationHistory(null) })

      stockApi.getDividendHistory(stockCode)
        .then(res => { if (requestId === requestCounter.current) setDividendHistory(res.data) })
        .catch(() => { if (requestId === requestCounter.current) setDividendHistory(null) })
      setFragility(null)
      stockApi.getFragility(stockCode)
        .then(res => { if (requestId === requestCounter.current) setFragility(res.data) })
        .catch(() => { if (requestId === requestCounter.current) setFragility(null) })

      // 异步加载派生指标
      stockApi.getDerivedMetrics(stockCode)
        .then(res => { if (requestId === requestCounter.current) setDerivedMetrics(res.data) })
        .catch(() => { if (requestId === requestCounter.current) setDerivedMetrics(null) })

      // 异步加载交叉分析
      if (requestId === requestCounter.current) setCrossLoading(true)
      stockApi.getCrossAnalysis(stockCode)
        .then(res => { if (requestId === requestCounter.current) setCrossAnalysis(res.data) })
        .catch(() => { if (requestId === requestCounter.current) setCrossAnalysis(null) })
        .finally(() => { if (requestId === requestCounter.current) setCrossLoading(false) })
    } catch (err) {
      console.error('加载失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { if (code) loadStock(code) }, [code, loadStock])

  const peLevel = getValuationLevel('pe', valuationHistory)
  const pbLevel = getValuationLevel('pb', valuationHistory)
  const divLevel = getValuationLevel('div', valuationHistory)
  const latestFin = financials.length > 0 ? financials[0] : null

  // PEG计算：使用最近3年利润CAGR（比单年增长率更稳定）
  const profitCAGR = useMemo(() => {
    const positiveProfits = financials.filter(f => f.net_profit && f.net_profit > 0)
    if (positiveProfits.length < 2) return null
    const newest = positiveProfits[0]
    const oldest = positiveProfits[Math.min(positiveProfits.length - 1, 2)] // 取最近3年
    if (!newest.net_profit || !oldest.net_profit || oldest.net_profit <= 0) return null
    const years = positiveProfits.indexOf(oldest)
    if (years <= 0) return null
    try {
      return (Math.pow(newest.net_profit / oldest.net_profit, 1 / years) - 1) * 100
    } catch { return null }
  }, [financials])

  const peg = selectedStock?.pe && profitCAGR && profitCAGR > 0
    ? (selectedStock.pe / profitCAGR) : null

  // ============ 图表配置 ============

  const chartBaseStyle = { color: '#8b949e', fontSize: 11 }
  const chartGrid = { left: 60, right: 30, top: 30, bottom: 60 }

  const getROEChartOption = useMemo(() => {
    if (!financials.length) return {}
    const reversed = [...financials].reverse()
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: reversed.map(f => f.date), axisLabel: { rotate: 30, ...chartBaseStyle } },
      yAxis: { type: 'value', name: '%', axisLabel: chartBaseStyle, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [{ name: 'ROE', type: 'line', data: reversed.map(f => f.roe), smooth: true, itemStyle: { color: '#58a6ff' }, areaStyle: { color: 'rgba(88,166,255,0.1)' }, label: { show: true, formatter: '{c}%' } }],
      grid: chartGrid, backgroundColor: 'transparent'
    }
  }, [financials])

  const getGrowthChartOption = useMemo(() => {
    if (!financials.length) return {}
    const reversed = [...financials].reverse()
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['营收增长率', '净利润增长率'], top: 0, textStyle: chartBaseStyle },
      xAxis: { type: 'category', data: reversed.map(f => f.date), axisLabel: { rotate: 30, ...chartBaseStyle } },
      yAxis: { type: 'value', name: '%', axisLabel: chartBaseStyle, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [
        { name: '营收增长率', type: 'bar', data: reversed.map(f => f.revenue_growth), itemStyle: { color: '#58a6ff' } },
        { name: '净利润增长率', type: 'bar', data: reversed.map(f => f.profit_growth), itemStyle: { color: '#3fb950' } }
      ],
      grid: chartGrid, backgroundColor: 'transparent'
    }
  }, [financials])

  const getProfitChartOption = useMemo(() => {
    if (!financials.length) return {}
    const reversed = [...financials].reverse()
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['毛利率', '净利率', 'ROE'], top: 0, textStyle: chartBaseStyle },
      xAxis: { type: 'category', data: reversed.map(f => f.date), axisLabel: { rotate: 30, ...chartBaseStyle } },
      yAxis: { type: 'value', name: '%', axisLabel: chartBaseStyle, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [
        { name: '毛利率', type: 'line', data: reversed.map(f => f.gross_margin), itemStyle: { color: '#f85149' } },
        { name: '净利率', type: 'line', data: reversed.map(f => f.net_margin), itemStyle: { color: '#58a6ff' } },
        { name: 'ROE', type: 'line', data: reversed.map(f => f.roe), itemStyle: { color: '#3fb950' } }
      ],
      grid: chartGrid, backgroundColor: 'transparent'
    }
  }, [financials])

  const getDebtChartOption = useMemo(() => {
    if (!financials.length) return {}
    const reversed = [...financials].reverse()
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: reversed.map(f => f.date), axisLabel: { rotate: 30, ...chartBaseStyle } },
      yAxis: { type: 'value', name: '%', axisLabel: chartBaseStyle, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [{ name: '资产负债率', type: 'bar', data: reversed.map(f => f.debt_ratio), itemStyle: { color: (params: { value: number }) => { const v = params.value; return v < 40 ? '#3fb950' : v < 60 ? '#d29922' : '#f85149' } } }],
      grid: chartGrid, backgroundColor: 'transparent'
    }
  }, [financials])

  const getValuationChartOption = useMemo(() => {
    return (type: 'pe' | 'pb' | 'div') => {
      if (!valuationHistory) return {}
      const history = type === 'pe' ? valuationHistory.pe_history : type === 'pb' ? valuationHistory.pb_history : valuationHistory.div_history
      const stats = valuationHistory.stats?.[type]
      if (!history?.length || !stats) return {}
      const dates = history.map(h => h.date)
      const values = history.map(h => h.value)
      const label = type === 'pe' ? 'PE(TTM)' : type === 'pb' ? 'PB' : '股息率(%)'
      const color = type === 'pe' ? '#58a6ff' : type === 'pb' ? '#d29922' : '#3fb950'
      return {
        tooltip: { trigger: 'axis', formatter: (params: { axisValue: string; value: number }[]) => `${params[0].axisValue}<br/>${label}: ${params[0].value}` },
        textStyle: chartBaseStyle,
        xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, ...chartBaseStyle, fontSize: 10, interval: Math.floor(dates.length / 8) }, axisLine: { lineStyle: { color: '#30363d' } } },
        yAxis: { type: 'value', name: label, axisLabel: chartBaseStyle, nameTextStyle: { ...chartBaseStyle, fontSize: 12 }, splitLine: { lineStyle: { color: '#21262d' } } },
        series: [{
          name: label, type: 'line', data: values, smooth: true, symbol: 'none',
          lineStyle: { width: 1.5, color },
          areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: `${color}26` }, { offset: 1, color: 'rgba(0,0,0,0)' }] } },
          markLine: {
            silent: true, symbol: 'none', lineStyle: { type: 'dashed', width: 1 },
            data: [
              { yAxis: stats.current, lineStyle: { color: '#f85149' }, label: { show: true, position: 'insideEndTop', formatter: `当前 ${stats.current}`, color: '#f85149', fontSize: 11 } },
              { yAxis: stats.median, lineStyle: { color: '#8b949e' }, label: { show: true, position: 'insideEndTop', formatter: `中位 ${stats.median}`, color: '#8b949e', fontSize: 11 } },
              { yAxis: stats.p25, lineStyle: { color: '#3fb950', type: 'dotted' }, label: { show: true, position: 'insideEndTop', formatter: `25% ${stats.p25}`, color: '#3fb950', fontSize: 10 } },
              { yAxis: stats.p75, lineStyle: { color: '#d29922', type: 'dotted' }, label: { show: true, position: 'insideEndTop', formatter: `75% ${stats.p75}`, color: '#d29922', fontSize: 10 } },
            ]
          }
        }],
        grid: chartGrid, backgroundColor: 'transparent'
      }
    }
  }, [valuationHistory])

  // ============ 表格列定义 ============

  const overviewColumns: Column<FinancialReport>[] = [
    { key: 'date', title: '报告期', dataIndex: 'date', render: (_, r) => r.report_name || r.date },
    { key: 'eps', title: '每股收益(元)', dataIndex: 'eps', align: 'right' },
    { key: 'bps', title: '每股净资产(元)', dataIndex: 'bps', align: 'right' },
    { key: 'roe', title: 'ROE(%)', dataIndex: 'roe', align: 'right' },
    { key: 'revenue', title: '营收(万元)', dataIndex: 'revenue', align: 'right', render: v => formatAmount(v) },
    { key: 'net_profit', title: '净利润(万元)', dataIndex: 'net_profit', align: 'right', render: v => formatAmount(v) },
    { key: 'gross_margin', title: '毛利率(%)', dataIndex: 'gross_margin', align: 'right' },
    { key: 'net_margin', title: '净利率(%)', dataIndex: 'net_margin', align: 'right' },
  ]

  const growthColumns: Column<FinancialReport>[] = [
    { key: 'date', title: '报告期', dataIndex: 'date', render: (_, r) => r.report_name || r.date },
    { key: 'revenue', title: '营收(万元)', dataIndex: 'revenue', align: 'right', render: v => formatAmount(v) },
    { key: 'revenue_growth', title: '营收增长率(%)', dataIndex: 'revenue_growth', align: 'right', colorize: true },
    { key: 'net_profit', title: '净利润(万元)', dataIndex: 'net_profit', align: 'right', render: v => formatAmount(v) },
    { key: 'profit_growth', title: '净利润增长率(%)', dataIndex: 'profit_growth', align: 'right', colorize: true },
  ]

  const profitColumns: Column<FinancialReport>[] = [
    { key: 'date', title: '报告期', dataIndex: 'date', render: (_, r) => r.report_name || r.date },
    { key: 'gross_margin', title: '毛利率(%)', dataIndex: 'gross_margin', align: 'right' },
    { key: 'net_margin', title: '净利率(%)', dataIndex: 'net_margin', align: 'right' },
    { key: 'roe', title: 'ROE(%)', dataIndex: 'roe', align: 'right' },
    { key: 'eps', title: '每股收益(元)', dataIndex: 'eps', align: 'right' },
  ]

  const debtColumns: Column<FinancialReport>[] = [
    { key: 'date', title: '报告期', dataIndex: 'date', render: (_, r) => r.report_name || r.date },
    { key: 'debt_ratio', title: '资产负债率(%)', dataIndex: 'debt_ratio', align: 'right' },
    { key: 'bps', title: '每股净资产(元)', dataIndex: 'bps', align: 'right' },
    { key: 'status', title: '状态', align: 'center', render: (_, r) => {
      const s = getDebtStatus(r.debt_ratio)
      return <span style={{ color: s.color }}>{s.text}</span>
    }},
  ]

  const dividendColumns: Column<any>[] = [
    { key: 'year', title: '年度', dataIndex: 'year' },
    { key: 'total_dps', title: '年度合计每股分红(元)', dataIndex: 'total_dps', align: 'right', render: v => v?.toFixed(4) ?? '-' },
    { key: 'eps', title: '每股收益(元)', dataIndex: 'eps', align: 'right', render: v => v?.toFixed(4) ?? '-' },
    { key: 'ratio', title: '分红比例', align: 'right', render: (_, r) => r.eps && r.total_dps ? (r.total_dps / r.eps * 100).toFixed(1) + '%' : '-' },
    { key: 'yield', title: '股息率', align: 'right', render: (_, r) => selectedStock?.price && r.total_dps ? (r.total_dps / selectedStock.price * 100).toFixed(2) + '%' : '-' },
  ]

  // ============ 渲染 ============

  if (loading) return <LoadingSpinner />
  if (!selectedStock) return <EmptyState icon="📊" title="未找到股票数据" />

  const tabs = [
    { key: 'overview', label: '财务概览' },
    { key: 'growth', label: '成长能力' },
    { key: 'profit', label: '盈利能力' },
    { key: 'debt', label: '负债分析' },
    { key: 'dividend', label: '分红' },
  ]

  return (
    <>
      {/* 股票头部 */}
      <PageSection className="stock-header" compact>
        <div className="stock-title-row">
          <div>
            <h2>{selectedStock.name}</h2>
            <span className="stock-code">{selectedStock.code}</span>
            <Tag color={selectedStock.market === 'HK' ? '#ff9800' : 'var(--accent-blue)'}>
              {selectedStock.market === 'HK' ? '港股' : 'A股'}
            </Tag>
          </div>
        </div>
        <div className="data-freshness">
          <span className="freshness-tag">行情时间: {selectedStock.trade_date} {selectedStock.trade_time}</span>
          <span className="freshness-tag">最新报告: {latestReport}</span>
          <span className="freshness-tag">数据获取: {fetchTime}</span>
        </div>
        <div className="price-section">
          <div className="current-price">
            <span className={`price-big ${selectedStock.change_pct >= 0 ? 'up' : 'down'}`}>{selectedStock.price.toFixed(2)}</span>
            <span className={`change-big ${selectedStock.change_pct >= 0 ? 'up' : 'down'}`}>
              {selectedStock.change_pct >= 0 ? '+' : ''}{selectedStock.change_pct.toFixed(2)}%
            </span>
          </div>
          <div className="price-details">
            <div className="price-item"><span className="label">今开</span><span className="value">{selectedStock.open.toFixed(2)}</span></div>
            <div className="price-item"><span className="label">最高</span><span className="value up">{selectedStock.high.toFixed(2)}</span></div>
            <div className="price-item"><span className="label">最低</span><span className="value down">{selectedStock.low.toFixed(2)}</span></div>
            <div className="price-item"><span className="label">昨收</span><span className="value">{selectedStock.pre_close.toFixed(2)}</span></div>
            <div className="price-item"><span className="label">成交量</span><span className="value">{formatVolume(selectedStock.volume)}</span></div>
            <div className="price-item"><span className="label">成交额</span><span className="value">{(selectedStock.amount / 100000000).toFixed(2)}亿</span></div>
          </div>
        </div>
      </PageSection>

      {/* 核心指标卡片 */}
      <PageSection title="核心指标">
        <StatCardGroup columns={5}>
          <StatCard label="滚动市盈率(TTM)" value={formatNum(selectedStock.pe)} />
          <StatCard label="市净率(PB)" value={formatNum(selectedStock.pb)} />
          <StatCard label="股息率" value={valuationHistory?.stats?.div?.current ? valuationHistory.stats.div.current + '%' : (selectedStock.dividend_yield ? selectedStock.dividend_yield + '%' : '-')} />
          <StatCard label="ROE" value={formatNum(latestFin?.roe, '%')} />
          <StatCard label="总市值" value={selectedStock.market_cap != null ? selectedStock.market_cap.toFixed(0) + '亿' : '-'} />
          <StatCard label="营收增长率" value={formatNum(latestFin?.revenue_growth, '%')} color={latestFin?.revenue_growth && latestFin.revenue_growth >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'} />
          <StatCard label="净利润增长率" value={formatNum(latestFin?.profit_growth, '%')} color={latestFin?.profit_growth && latestFin.profit_growth >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'} />
          <StatCard
            label="PEG"
            value={peg ? peg.toFixed(2) : '-'}
            color={peg ? (peg < 1 ? '#16a34a' : peg < 2 ? '#ca8a04' : '#dc2626') : 'var(--text-muted)'}
          />
          <StatCard label="毛利率" value={formatNum(latestFin?.gross_margin, '%')} />
          <StatCard label="资产负债率" value={formatNum(latestFin?.debt_ratio, '%')} />
        </StatCardGroup>
      </PageSection>

      {/* 机构级派生指标 */}
      {derivedMetrics && !derivedMetrics.error && (
        <PageSection title="机构级估值指标">
          <StatCardGroup columns={5}>
            {derivedMetrics.ev_ebitda !== undefined && (
              <StatCard
                label="EV/EBITDA"
                value={derivedMetrics.ev_ebitda.toFixed(1)}
                color={derivedMetrics.ev_ebitda_level === '低估' ? '#16a34a' : derivedMetrics.ev_ebitda_level === '合理' ? '#58a6ff' : derivedMetrics.ev_ebitda_level === '偏高' ? '#ca8a04' : '#dc2626'}
              />
            )}
            {derivedMetrics.fcf_yield !== undefined && (
              <StatCard
                label="自由现金流收益率"
                value={derivedMetrics.fcf_yield.toFixed(2) + '%'}
                color={derivedMetrics.fcf_yield_level === '高' ? '#16a34a' : derivedMetrics.fcf_yield_level === '适中' ? '#58a6ff' : '#ca8a04'}
              />
            )}
            {derivedMetrics.ev !== undefined && (
              <StatCard label="企业价值(EV)" value={derivedMetrics.ev.toFixed(0) + '亿'} />
            )}
            {derivedMetrics.free_cashflow !== undefined && (
              <StatCard label="自由现金流" value={derivedMetrics.free_cashflow.toFixed(2) + '亿'} color={derivedMetrics.free_cashflow > 0 ? '#16a34a' : '#dc2626'} />
            )}
            {derivedMetrics.ebitda !== undefined && (
              <StatCard label="EBITDA" value={derivedMetrics.ebitda.toFixed(2) + '亿'} />
            )}
          </StatCardGroup>
        </PageSection>
      )}

      {/* 杜邦分析分解 */}
      {derivedMetrics?.dupont && (
        <PageSection title="杜邦分析分解 (ROE)">
          <StatCardGroup columns={4}>
            <StatCard
              label="ROE (计算)"
              value={derivedMetrics.dupont.roe.toFixed(2) + '%'}
              color={derivedMetrics.dupont.roe > 15 ? '#16a34a' : derivedMetrics.dupont.roe > 8 ? '#ca8a04' : '#dc2626'}
            />
            <StatCard label="净利润率" value={derivedMetrics.dupont.net_margin.toFixed(2) + '%'} />
            <StatCard label="资产周转率" value={derivedMetrics.dupont.asset_turnover.toFixed(3)} />
            <StatCard label="权益乘数" value={derivedMetrics.dupont.equity_multiplier.toFixed(2)} />
          </StatCardGroup>
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            ROE = 净利润率 x 资产权益率 x 权益乘数 = {derivedMetrics.dupont.net_margin.toFixed(2)}% x {derivedMetrics.dupont.asset_turnover.toFixed(3)} x {derivedMetrics.dupont.equity_multiplier.toFixed(2)}
          </div>
        </PageSection>
      )}

      {/* 估值分位 */}
      {valuationLoading && (
        <PageSection title="估值分位">
          <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-muted)' }}>
            正在加载估值历史数据...
          </div>
        </PageSection>
      )}
      {valuationError && !valuationLoading && (
        <PageSection title="估值分位">
          <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--accent-red)', fontSize: 13 }}>
            {valuationError}
          </div>
        </PageSection>
      )}
      {!valuationLoading && !valuationError && peLevel.level !== '-' && (
        <PageSection title="估值分位">
          <StatCardGroup columns={4}>
            <StatCard label="PE(TTM)分位" value={peLevel.level} color={peLevel.color} />
            <StatCard label="PB分位" value={pbLevel.level} color={pbLevel.color} />
            <StatCard label="股息率分位" value={divLevel.level} color={divLevel.color} />
            <StatCard label="数据点" value={valuationHistory?.stats?.pe?.count ?? '-'} suffix="个交易日" />
          </StatCardGroup>
        </PageSection>
      )}

      {/* 巴菲特指标（考虑多年趋势而非单点快照） */}
      <PageSection title="巴菲特选股指标">
        {(() => {
          // 护城河：毛利率均值 + 稳定性
          const gmValues = financials.map(f => f.gross_margin).filter((v): v is number => v !== null && v !== undefined)
          const avgGM = gmValues.length > 0 ? gmValues.reduce((a, b) => a + b, 0) / gmValues.length : null
          const gmStable = gmValues.length >= 3 && avgGM !== null && Math.max(...gmValues) - Math.min(...gmValues) < 15
          const moatLevel = avgGM !== null && avgGM > 50 && gmStable ? '宽' : avgGM !== null && avgGM > 30 ? '窄' : '无'
          const moatColor = avgGM !== null && avgGM > 50 && gmStable ? '#16a34a' : avgGM !== null && avgGM > 30 ? '#ca8a04' : '#dc2626'

          // 盈利能力：ROE持续性（多少年>15%）
          const roeValues = financials.map(f => f.roe).filter((v): v is number => v !== null && v !== undefined)
          const highRoeCount = roeValues.filter(v => v > 15).length
          const earnLevel = highRoeCount >= roeValues.length * 0.7 ? '优秀' : highRoeCount >= roeValues.length * 0.4 ? '良好' : '一般'
          const earnColor = highRoeCount >= roeValues.length * 0.7 ? '#16a34a' : highRoeCount >= roeValues.length * 0.4 ? '#ca8a04' : '#dc2626'

          // 成长性：利润CAGR
          const growthLevel = profitCAGR !== null && profitCAGR > 15 ? '高增长' : profitCAGR !== null && profitCAGR > 0 ? '稳定' : '下滑'
          const growthColor = profitCAGR !== null && profitCAGR > 15 ? '#16a34a' : profitCAGR !== null && profitCAGR > 0 ? '#ca8a04' : '#dc2626'

          // 财务健康：资产负债率趋势
          const debtValues = financials.map(f => f.debt_ratio).filter((v): v is number => v !== null && v !== undefined)
          const latestDebt = debtValues[0]
          const debtImproving = debtValues.length >= 2 && debtValues[0] < debtValues[1]
          const healthLevel = latestDebt !== undefined && latestDebt < 40 ? '优秀' : latestDebt !== undefined && latestDebt < 60 ? '良好' : '风险'
          const healthColor = latestDebt !== undefined && latestDebt < 40 ? '#16a34a' : latestDebt !== undefined && latestDebt < 60 ? '#ca8a04' : '#dc2626'

          return (
            <StatCardGroup columns={4}>
              <StatCard label="护城河" value={moatLevel} color={moatColor} />
              <StatCard label="盈利能力" value={earnLevel} color={earnColor} />
              <StatCard label="成长性" value={growthLevel} color={growthColor} />
              <StatCard label="财务健康" value={healthLevel} color={healthColor} />
            </StatCardGroup>
          )
        })()}
      </PageSection>

      {/* 商业模式韧性分析 */}
      {fragility && !fragility.error && (
        <PageSection title="商业模式韧性分析">
          <div className="fragility-header">
            <div className="fragility-score" style={{ backgroundColor: getScoreColor(fragility.total_score, 100) }}>
              {fragility.total_score}
            </div>
            <div>
              <div className="fragility-verdict">{fragility.verdict}</div>
              <div className="fragility-desc">
                {fragility.total_score >= 75 ? '商业模式坚韧，抗风险能力强' : fragility.total_score >= 60 ? '有一定护城河，需关注薄弱环节' : fragility.total_score >= 40 ? '存在明显弱点，需谨慎投资' : '商业模式风险大，建议排除'}
              </div>
            </div>
          </div>
          <StatCardGroup columns={4}>
            {fragility.dimensions?.map((dim, i) => (
              <StatCard
                key={i}
                label={dim.name}
                value={`${dim.score}/${dim.max}`}
                color={getScoreColor(dim.score, dim.max)}
              />
            ))}
          </StatCardGroup>
          {fragility.warnings?.length > 0 && (
            <div className="fragility-warnings">
              <div className="fragility-warnings-title">风险警告</div>
              {fragility.warnings.map((w, i) => (
                <div key={i} className="fragility-warnings-item">
                  · {typeof w === 'string' ? w : w.message}
                </div>
              ))}
            </div>
          )}
        </PageSection>
      )}

      {/* 区段切换 */}
      <TabBar
        tabs={[
          { key: 'overview', label: '财务概览' },
          { key: 'cross', label: '交叉分析' },
          { key: 'ai', label: '🤖 AI分析' },
          { key: 'f12', label: '三大报表 (F12)' },
        ]}
        activeKey={sectionView}
        onChange={k => setSectionView(k as 'overview' | 'cross' | 'ai' | 'f12')}
        style={{ marginBottom: 16 }}
      />

      {sectionView === 'cross' ? (
        <CrossAnalysisPanel data={crossAnalysis} loading={crossLoading} />
      ) : sectionView === 'ai' ? (
        <AIAnalysisPanel code={code} stockName={selectedStock?.name} />
      ) : sectionView === 'f12' ? (
        <Suspense fallback={<LoadingSpinner text="加载三大报表..." />}>
          <FinancialStatements code={code} />
        </Suspense>
      ) : (
        <>
          <TabBar tabs={tabs} activeKey={activeTab} onChange={setActiveTab} style={{ marginBottom: 16 }} />

          <PageSection>
            <DataTable
              columns={
                activeTab === 'overview' ? overviewColumns :
                activeTab === 'growth' ? growthColumns :
                activeTab === 'profit' ? profitColumns :
                activeTab === 'debt' ? debtColumns :
                activeTab === 'dividend' ? dividendColumns :
                overviewColumns
              }
              data={activeTab === 'dividend' ? (dividendHistory?.dividends || []) as any[] : financials}
              rowKey={(_: any, i: number) => String(i)}
              emptyText={activeTab === 'dividend' ? '暂无分红数据' : '暂无财务数据'}
              striped
            />
          </PageSection>

          {/* 图表 */}
          <div className="charts-row">
            <div className="chart-container"><div className="chart-title">ROE趋势</div><ReactECharts option={getROEChartOption} style={{ height: 300 }} /></div>
            <div className="chart-container"><div className="chart-title">成长能力</div><ReactECharts option={getGrowthChartOption} style={{ height: 300 }} /></div>
          </div>
          <div className="charts-row">
            <div className="chart-container"><div className="chart-title">盈利能力</div><ReactECharts option={getProfitChartOption} style={{ height: 300 }} /></div>
            <div className="chart-container"><div className="chart-title">资产负债率</div><ReactECharts option={getDebtChartOption} style={{ height: 300 }} /></div>
          </div>

          {/* 历史估值走势 */}
          {valuationHistory?.stats && (
            <>
              <div className="charts-row">
                <div className="chart-container"><div className="chart-title">PE(TTM) 历史走势</div><ReactECharts option={getValuationChartOption('pe')} style={{ height: 350 }} /></div>
                <div className="chart-container"><div className="chart-title">PB 历史走势</div><ReactECharts option={getValuationChartOption('pb')} style={{ height: 350 }} /></div>
              </div>
              {valuationHistory.div_history?.length > 0 && (
                <div className="charts-row" style={{ marginTop: 16 }}>
                  <div className="chart-container"><div className="chart-title">股息率(%) 历史走势</div><ReactECharts option={getValuationChartOption('div')} style={{ height: 350 }} /></div>
                  <div className="chart-container" />
                </div>
              )}
            </>
          )}
          {valuationHistory?.message && <div className="valuation-message">{valuationHistory.message}</div>}
        </>
      )}
    </>
  )
}
