import { useState, useEffect, useCallback, useMemo } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { PageSection, TabBar, LoadingSpinner, EmptyState, StatusBadge, Tag } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

interface IndexData {
  code: string
  name: string
  name_en: string
  category: string
  country: string
  pe: number | null
  pe_percentile: number | null
  pb: number | null
  pb_percentile: number | null
  roe: number | null
  dividend_yield: number | null
  dividend_percentile: number | null
  fund_code: string
  fund_name: string
  fund_type: string
  fund_channel: string
  fund_fee: string | null
  fund_purchase_fee: string | null
  fund_holdings_url: string
  return_1y: number | null
  return_3y: number | null
  return_5y: number | null
  cagr: number | null
  max_drawdown: number | null
  risk_premium?: number | null
  investment_signal?: { score: number | null; signal: string; color: string } | null
}

// ============ Module-level helpers (stable references, never recreated) ============

const COUNTRY_FLAGS: Record<string, string> = {
  '中国': '🇨🇳', '中国香港': '🇭🇰', '美国': '🇺🇸', '日本': '🇯🇵',
  '德国': '🇩🇪', '印度': '🇮🇳', '越南': '🇻🇳', '澳大利亚': '🇦🇺', '全球': '🌍',
}

const getColor = (v: number | null) => {
  if (v === null) return 'var(--text-muted)'
  if (v < 30) return '#3fb950'
  if (v <= 70) return 'var(--text-secondary)'
  return '#f85149'
}

const getBg = (v: number | null) => {
  if (v === null) return 'transparent'
  if (v < 30) return 'rgba(63,185,80,0.1)'
  if (v <= 70) return 'transparent'
  return 'rgba(248,81,73,0.1)'
}

const getValuationLabel = (pe_p: number | null, pb_p: number | null) => {
  const scores = [pe_p, pb_p].filter(v => v !== null) as number[]
  if (scores.length === 0) return { text: '数据不足', color: 'var(--text-muted)' }
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length
  if (avg < 20) return { text: '极度低估', color: '#238636' }
  if (avg < 35) return { text: '低估', color: '#3fb950' }
  if (avg <= 55) return { text: '合理', color: 'var(--text-secondary)' }
  if (avg <= 70) return { text: '偏高', color: '#d29922' }
  return { text: '高估', color: '#f85149' }
}

const getCountryFlag = (country: string) => COUNTRY_FLAGS[country] || '🌐'

const formatReturn = (v: number | null) => {
  if (v === null) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
}

const getReturnColor = (v: number | null) => {
  if (v === null) return 'var(--text-muted)'
  return v >= 0 ? '#3fb950' : '#f85149'
}

// ============ Component ============

export default function IndexValuation() {
  const [activeTab, setActiveTab] = useState<'overview' | 'chart' | 'returns' | 'funds'>('overview')
  const [indices, setIndices] = useState<IndexData[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [filterCategory, setFilterCategory] = useState<'all' | '宽基' | '红利'>('all')
  const [countryFilter, setCountryFilter] = useState<string>('all')
  const [sortField, setSortField] = useState<string>('')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [selectedCode, setSelectedCode] = useState<string>('')
  const [historyData, setHistoryData] = useState<any>(null)
  const [historyLoading, setHistoryLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/index-valuation/data`)
      setIndices(res.data.indices || [])
      setUpdateTime(res.data.update_time || '')
    } catch (e) {
      console.error('获取指数估值数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const loadHistory = useCallback(async (code: string) => {
    if (!code) return
    setHistoryLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/index-valuation/history/${code}`)
      setHistoryData(res.data)
    } catch (e) {
      console.error('获取历史数据失败:', e)
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const handleSort = useCallback((field: string) => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('asc')
    }
  }, [sortField])

  const SortIcon = ({ field }: { field: string }) => {
    if (sortField !== field) return <span style={{ opacity: 0.3, marginLeft: 2, fontSize: 10 }}>↕</span>
    return <span style={{ marginLeft: 2, fontSize: 10 }}>{sortOrder === 'asc' ? '↑' : '↓'}</span>
  }

  const filtered = useMemo(() => {
    let result = indices.filter(idx =>
      (filterCategory === 'all' || idx.category === filterCategory) &&
      (countryFilter === 'all' || idx.country === countryFilter)
    )
    if (sortField) {
      result = [...result].sort((a, b) => {
        const aVal = (a as any)[sortField]
        const bVal = (b as any)[sortField]
        if (aVal === null && bVal === null) return 0
        if (aVal === null) return 1
        if (bVal === null) return -1
        const diff = aVal - bVal
        return sortOrder === 'asc' ? diff : -diff
      })
    }
    return result
  }, [indices, filterCategory, countryFilter, sortField, sortOrder])

  const filteredWithCagr = useMemo(() =>
    filtered.filter(idx => idx.cagr !== null).sort((a, b) => (b.cagr || 0) - (a.cagr || 0)),
    [filtered]
  )

  const countries = useMemo(() => {
    const set = new Set(indices.map(idx => idx.country))
    return Array.from(set).sort()
  }, [indices])

  return (
    <div className="cb-page">
      <PageSection
        title="全球指数估值"
        extra={
          <span className="stock-code">
            {indices.length}个指数 · PE/PB/ROE/股息率/历史收益
            {loading && <LoadingSpinner size="small" text="" style={{ display: 'inline-flex', marginLeft: 8 }} />}
          </span>
        }
        onRefresh={loadData}
        compact
      >
        <span />
      </PageSection>

      {/* Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '0 20px', borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
        <TabBar
          tabs={[
            { key: 'overview', label: '估值总览' },
            { key: 'chart', label: '估值走势' },
            { key: 'returns', label: '历史收益' },
            { key: 'funds', label: '基金对比' },
          ]}
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'overview' | 'chart' | 'returns' | 'funds')}
          size="small"
        />
        <div style={{ flex: 1 }} />
        <select value={filterCategory} onChange={e => setFilterCategory(e.target.value as any)}
          style={{ padding: '4px 8px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', fontSize: 12 }}>
          <option value="all">全部类型</option>
          <option value="宽基">宽基指数</option>
          <option value="红利">红利指数</option>
        </select>
        <select value={countryFilter} onChange={e => setCountryFilter(e.target.value)}
          style={{ padding: '4px 8px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', fontSize: 12, marginLeft: 6 }}>
          <option value="all">全部国家</option>
          {countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* ==================== Tab 1: 估值总览 ==================== */}
      {activeTab === 'overview' && (
        <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>指数</th>
                <th>国家</th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('pe')}>PE <SortIcon field="pe" /></th>
                <th title="百分位越低越便宜" style={{ cursor: 'pointer', borderBottom: '2px dashed var(--border-primary)' }} onClick={() => handleSort('pe_percentile')}>PE百分位 <SortIcon field="pe_percentile" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('pb')}>PB <SortIcon field="pb" /></th>
                <th title="百分位越低越便宜" style={{ cursor: 'pointer', borderBottom: '2px dashed var(--border-primary)' }} onClick={() => handleSort('pb_percentile')}>PB百分位 <SortIcon field="pb_percentile" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('roe')}>ROE <SortIcon field="roe" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('dividend_yield')}>股息率 <SortIcon field="dividend_yield" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('risk_premium')} title="股权风险溢价 = 盈利收益率 - 国债收益率">风险溢价 <SortIcon field="risk_premium" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('return_1y')}>近1年 <SortIcon field="return_1y" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('return_3y')}>近3年 <SortIcon field="return_3y" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('cagr')}>年化 <SortIcon field="cagr" /></th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('max_drawdown')}>最大回撤 <SortIcon field="max_drawdown" /></th>
                <th>估值信号</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(idx => {
                const sig = idx.investment_signal
                return (
                  <tr key={idx.code}>
                    <td style={{ fontWeight: 600, textAlign: 'left' }}>
                      <div>{idx.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{idx.name_en}</div>
                    </td>
                    <td style={{ fontSize: 16 }}>{getCountryFlag(idx.country)}</td>
                    <td>{idx.pe?.toFixed(1) ?? '--'}</td>
                    <td style={{ padding: '6px 8px' }}>
                      {idx.pe_percentile !== null ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ flex: 1, height: 6, background: 'var(--bg-secondary)', borderRadius: 3, position: 'relative', minWidth: 50 }}>
                            <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${Math.min(idx.pe_percentile, 100)}%`, borderRadius: 3, background: getColor(idx.pe_percentile), transition: 'width 0.3s' }} />
                          </div>
                          <span style={{ color: getColor(idx.pe_percentile), fontWeight: 600, fontSize: 12, minWidth: 30 }}>{idx.pe_percentile.toFixed(0)}%</span>
                        </div>
                      ) : '--'}
                    </td>
                    <td>{idx.pb?.toFixed(2) ?? '--'}</td>
                    <td style={{ padding: '6px 8px' }}>
                      {idx.pb_percentile !== null ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ flex: 1, height: 6, background: 'var(--bg-secondary)', borderRadius: 3, position: 'relative', minWidth: 50 }}>
                            <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${Math.min(idx.pb_percentile, 100)}%`, borderRadius: 3, background: getColor(idx.pb_percentile), transition: 'width 0.3s' }} />
                          </div>
                          <span style={{ color: getColor(idx.pb_percentile), fontWeight: 600, fontSize: 12, minWidth: 30 }}>{idx.pb_percentile.toFixed(0)}%</span>
                        </div>
                      ) : '--'}
                    </td>
                    <td style={{ color: idx.roe !== null && idx.roe > 15 ? '#3fb950' : idx.roe !== null && idx.roe < 8 ? '#d29922' : 'var(--text-secondary)', fontWeight: idx.roe !== null && idx.roe > 15 ? 600 : 400 }}>
                      {idx.roe !== null ? `${idx.roe.toFixed(1)}%` : '--'}
                    </td>
                    <td style={{ color: idx.dividend_yield !== null && idx.dividend_yield > 3 ? '#3fb950' : 'var(--text-secondary)', fontWeight: idx.dividend_yield !== null && idx.dividend_yield > 3 ? 600 : 400 }}>
                      {idx.dividend_yield !== null ? `${idx.dividend_yield.toFixed(2)}%` : '--'}
                    </td>
                    <td style={{ color: idx.risk_premium !== null && idx.risk_premium > 0 ? '#3fb950' : idx.risk_premium !== null && idx.risk_premium < -2 ? '#f85149' : 'var(--text-secondary)' }}>
                      {idx.risk_premium !== null ? `${idx.risk_premium > 0 ? '+' : ''}${idx.risk_premium.toFixed(1)}%` : '--'}
                    </td>
                    <td style={{ color: getReturnColor(idx.return_1y), fontWeight: 600 }}>{formatReturn(idx.return_1y)}</td>
                    <td style={{ color: getReturnColor(idx.return_3y), fontWeight: 600 }}>{formatReturn(idx.return_3y)}</td>
                    <td style={{ color: getReturnColor(idx.cagr), fontWeight: 600 }}>{formatReturn(idx.cagr)}</td>
                    <td style={{ color: idx.max_drawdown && idx.max_drawdown > 30 ? '#f85149' : 'var(--text-secondary)' }}>
                      {idx.max_drawdown !== null ? `-${idx.max_drawdown.toFixed(1)}%` : '--'}
                    </td>
                    <td>
                      {sig && sig.score !== null ? (
                        <span style={{ color: sig.color, fontWeight: 600, fontSize: 12, padding: '2px 8px', borderRadius: 10, background: `${sig.color}20`, whiteSpace: 'nowrap' }}>
                          {sig.signal} {sig.score}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>--</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {filtered.length === 0 && !loading && (
            <EmptyState title="暂无数据" />
          )}

          {/* 说明 */}
          <div style={{ marginTop: 16 }} className="info-box">
            <div className="info-box-title">估值指标说明</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, fontSize: 13 }}>
              <div><strong>PE（市盈率）</strong>：越低越便宜，适合盈利稳定的宽基指数</div>
              <div><strong>PB（市净率）</strong>：越低越便宜，适合重资产行业和周期股</div>
              <div><strong>ROE</strong>：PB/PE×100，衡量盈利能力，越高越好（绿色&gt;15%）</div>
              <div><strong>股息率</strong>：越高分红越多，红利指数的核心指标（绿色&gt;3%）</div>
              <div><strong>风险溢价</strong>：盈利收益率-国债收益率，正值表示股票比债券有吸引力</div>
              <div><strong>估值信号</strong>：综合PE/PB百分位+股息率+风险溢价的加权评分</div>
            </div>
            <div style={{ marginTop: 8, padding: '8px 12px', background: 'rgba(88,166,255,0.08)', borderRadius: 6, border: '1px solid rgba(88,166,255,0.15)' }}>
              <div style={{ fontWeight: 600, color: '#58a6ff', marginBottom: 4 }}>估值信号评分（越低越低估）</div>
              <div style={{ marginTop: 4 }}>
                <span style={{ color: '#238636', fontWeight: 600 }}>极度低估</span>&lt;20 ·
                <span style={{ color: '#3fb950', fontWeight: 600 }}> 低估</span>20-35 ·
                <span style={{ fontWeight: 600 }}> 合理</span>35-55 ·
                <span style={{ color: '#d29922', fontWeight: 600 }}> 偏高</span>55-70 ·
                <span style={{ color: '#f85149', fontWeight: 600 }}> 高估</span>&gt;70
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-muted)' }}>百分位柱状条：绿色&lt;30%低估，灰色30-70%合理，红色&gt;70%高估</div>
            </div>
            <div style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 12 }}>
              数据来源：中证指数 · multpl.com · yfinance · 富途OpenAPI · 乐咕乐股 · 东方财富 | 更新：{updateTime}
            </div>
          </div>
        </div>
      )}

      {/* ==================== Tab 2: 估值走势 ==================== */}
      {activeTab === 'chart' && (
        <div style={{ padding: '16px 20px' }}>
          <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>选择指数：</span>
            <select value={selectedCode} onChange={e => {
              setSelectedCode(e.target.value)
              if (e.target.value) loadHistory(e.target.value)
            }}
              style={{ padding: '6px 12px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', fontSize: 13, minWidth: 200 }}>
              <option value="">请选择指数</option>
              {indices.map(idx => <option key={idx.code} value={idx.code}>{idx.name} ({idx.name_en})</option>)}
            </select>
          </div>

          {historyLoading && <LoadingSpinner size="small" text="加载历史数据..." />}

          {historyData && !historyLoading && (historyData.pe_series?.length > 0 || historyData.pb_series?.length > 0) ? (
            <div>
              {/* 统计摘要 */}
              <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                {historyData.pe_stats?.current && (
                  <div style={{ padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 13 }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>当前PE</div>
                    <div style={{ fontWeight: 700, fontSize: 18 }}>{historyData.pe_stats.current}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      历史区间 {historyData.pe_stats.min} ~ {historyData.pe_stats.max}，均值 {historyData.pe_stats.avg}
                    </div>
                  </div>
                )}
                {historyData.pb_stats?.current && (
                  <div style={{ padding: '8px 16px', background: 'var(--bg-secondary)', borderRadius: 8, fontSize: 13 }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>当前PB</div>
                    <div style={{ fontWeight: 700, fontSize: 18 }}>{historyData.pb_stats.current}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      历史区间 {historyData.pb_stats.min} ~ {historyData.pb_stats.max}，均值 {historyData.pb_stats.avg}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: historyData.pe_series?.length > 0 && historyData.pb_series?.length > 0 ? '1fr 1fr' : '1fr', gap: 16 }}>
                {historyData.pe_series?.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>PE 历史走势（近10年）</div>
                    <ReactECharts option={{
                      tooltip: { trigger: 'axis' },
                      xAxis: { type: 'category', data: historyData.pe_series.map((d: any) => d.date), axisLabel: { fontSize: 10, rotate: 30 } },
                      yAxis: { type: 'value', name: 'PE', nameTextStyle: { fontSize: 11 } },
                      series: [{
                        data: historyData.pe_series.map((d: any) => d.value),
                        type: 'line', smooth: true, lineStyle: { width: 2, color: '#58a6ff' },
                        areaStyle: { color: 'rgba(88,166,255,0.08)' },
                        markLine: {
                          data: [
                            { type: 'average', name: '均值', label: { formatter: '均值: {c}', fontSize: 10 } },
                          ],
                          lineStyle: { color: '#d29922', type: 'dashed' },
                        },
                      }],
                      grid: { left: 50, right: 20, top: 30, bottom: 40 },
                    }} style={{ height: 300 }} />
                  </div>
                )}
                {historyData.pb_series?.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}>PB 历史走势（近10年）</div>
                    <ReactECharts option={{
                      tooltip: { trigger: 'axis' },
                      xAxis: { type: 'category', data: historyData.pb_series.map((d: any) => d.date), axisLabel: { fontSize: 10, rotate: 30 } },
                      yAxis: { type: 'value', name: 'PB', nameTextStyle: { fontSize: 11 } },
                      series: [{
                        data: historyData.pb_series.map((d: any) => d.value),
                        type: 'line', smooth: true, lineStyle: { width: 2, color: '#d29922' },
                        areaStyle: { color: 'rgba(210,153,34,0.08)' },
                        markLine: {
                          data: [
                            { type: 'average', name: '均值', label: { formatter: '均值: {c}', fontSize: 10 } },
                          ],
                          lineStyle: { color: '#58a6ff', type: 'dashed' },
                        },
                      }],
                      grid: { left: 50, right: 20, top: 30, bottom: 40 },
                    }} style={{ height: 300 }} />
                  </div>
                )}
              </div>
            </div>
          ) : selectedCode && !historyLoading ? (
            <EmptyState title="暂无历史数据" />
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 14 }}>
              请选择一个指数查看PE/PB历史走势
            </div>
          )}
        </div>
      )}

      {/* ==================== Tab 3: 历史收益 ==================== */}
      {activeTab === 'returns' && (
        <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>指数</th>
                <th>国家</th>
                <th>近1年</th>
                <th>近3年</th>
                <th>近5年</th>
                <th>年化收益</th>
                <th>最大回撤</th>
                <th>收益/回撤比</th>
              </tr>
            </thead>
            <tbody>
              {filteredWithCagr.map(idx => {
                const ratio = idx.cagr && idx.max_drawdown && idx.max_drawdown > 0
                  ? (idx.cagr / idx.max_drawdown).toFixed(2) : '--'
                return (
                  <tr key={idx.code}>
                    <td style={{ fontWeight: 600, textAlign: 'left' }}>{idx.name}</td>
                    <td>{getCountryFlag(idx.country)}</td>
                    <td style={{ color: getReturnColor(idx.return_1y), fontWeight: 600 }}>{formatReturn(idx.return_1y)}</td>
                    <td style={{ color: getReturnColor(idx.return_3y), fontWeight: 600 }}>{formatReturn(idx.return_3y)}</td>
                    <td style={{ color: getReturnColor(idx.return_5y), fontWeight: 600 }}>{formatReturn(idx.return_5y)}</td>
                    <td style={{ color: getReturnColor(idx.cagr), fontWeight: 700, fontSize: 15 }}>{formatReturn(idx.cagr)}</td>
                    <td style={{ color: idx.max_drawdown && idx.max_drawdown > 30 ? '#f85149' : 'var(--text-secondary)' }}>
                      {idx.max_drawdown !== null ? `-${idx.max_drawdown.toFixed(1)}%` : '--'}
                    </td>
                    <td style={{ fontWeight: 600 }}>{ratio}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {filteredWithCagr.length === 0 && (
            <EmptyState title="暂无历史收益数据" />
          )}
        </div>
      )}

      {/* ==================== Tab 4: 基金对比 ==================== */}
      {activeTab === 'funds' && (
        <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>指数</th>
                <th style={{ textAlign: 'left' }}>推荐基金</th>
                <th>类型</th>
                <th>管理费</th>
                <th>申购费</th>
                <th>购买渠道</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(idx => (
                <tr key={idx.code}>
                  <td style={{ fontWeight: 600, textAlign: 'left' }}>
                    <div>{getCountryFlag(idx.country)} {idx.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{idx.name_en}</div>
                  </td>
                  <td style={{ textAlign: 'left' }}>
                    <div style={{ fontWeight: 600 }}>{idx.fund_name || idx.fund_code}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{idx.fund_code}</div>
                  </td>
                  <td>
                    <span style={{
                      fontSize: 11, padding: '2px 6px', borderRadius: 4,
                      background: idx.fund_type === '场内ETF' ? 'rgba(63,185,80,0.15)' :
                        idx.fund_type === '场外LOF' ? 'rgba(88,166,255,0.15)' : 'var(--bg-secondary)',
                      color: idx.fund_type === '场内ETF' ? '#3fb950' :
                        idx.fund_type === '场外LOF' ? '#58a6ff' : 'var(--text-secondary)',
                    }}>
                      {idx.fund_type || '--'}
                    </span>
                  </td>
                  <td>{idx.fund_fee || '--'}</td>
                  <td>{idx.fund_purchase_fee || '场内免申购费'}</td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{idx.fund_channel || '--'}</td>
                  <td>
                    {idx.fund_code && (
                      <a href={idx.fund_holdings_url} target="_blank" rel="noopener noreferrer"
                        style={{ color: '#58a6ff', textDecoration: 'none', fontSize: 12 }}>
                        持仓详情 →
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* 购买渠道说明 */}
          <div style={{ marginTop: 16 }} className="info-box">
            <div className="info-box-title">购买渠道对比</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, fontSize: 13 }}>
              <div style={{ padding: 10, background: 'rgba(63,185,80,0.08)', borderRadius: 6 }}>
                <div style={{ fontWeight: 600, color: '#3fb950' }}>场内ETF（券商APP）</div>
                <div>佣金万2.5，无申购费，实时交易</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>适合：有券商账户的投资者，费率最低</div>
              </div>
              <div style={{ padding: 10, background: 'rgba(88,166,255,0.08)', borderRadius: 6 }}>
                <div style={{ fontWeight: 600, color: '#58a6ff' }}>场外基金（支付宝/天天基金）</div>
                <div>申购费0.1%-1.5%，T+1确认</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>适合：定投、无券商账户的投资者</div>
              </div>
              <div style={{ padding: 10, background: 'rgba(210,153,34,0.08)', borderRadius: 6 }}>
                <div style={{ fontWeight: 600, color: '#d29922' }}>QDII基金</div>
                <div>投资海外市场，申购费0.1%-1.5%</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>适合：投资无直接ETF的海外市场</div>
              </div>
              <div style={{ padding: 10, background: 'rgba(248,81,73,0.08)', borderRadius: 6 }}>
                <div style={{ fontWeight: 600, color: '#f85149' }}>无直接ETF的市场</div>
                <div>越南、澳洲等需通过QDII或港股通</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>门槛较高，费率较高</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
