import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface ConcessionInfo {
  total_years: number
  elapsed_years: number
  remaining_years: number
  remaining_pct: number
  warning: string
}

interface ScoreBreakdown {
  distribution: number
  valuation: number
  asset_quality: number
  financial: number
  liquidity: number
}

interface REIT {
  code: string
  name: string
  asset_type: string
  underlying: string
  location: string
  price: number
  pre_close: number
  change_pct: number
  daily_turnover: number
  volume: number
  // NAV
  unit_nav: number | null
  p_nav: number | null
  premium_pct: number | null
  nav_assessment: string
  nav_date: string
  // 分派率
  dividend_yield: number
  total_distributions: number
  distribution_method: string
  years_listed: number
  // 资产质量
  occupancy_rate: number
  asset_description: string
  // 财务
  debt_ratio: number
  leverage_level: string
  interest_burden: string
  leverage_headroom: number
  // 利率敏感性
  rate_sensitivity: string
  rate_yield_impact_bps: number
  rate_price_impact_pct: number
  current_spread: number
  spread_assessment: string
  // 经营期限
  concession: ConcessionInfo | null
  // 评分
  score: number
  score_breakdown: ScoreBreakdown
  score_grade: string
  // 风险
  risk_level: string
  risk_notes: string[]
}

interface MarketOverview {
  total: number
  avg_yield: number
  avg_p_nav: number
  avg_occupancy: number
  type_distribution: Record<string, { count: number; avg_yield: number }>
  rate_environment: {
    current_lpr_5y: number
    description: string
    implication: string
    high_sensitivity_count: number
  }
}

interface RiskGuideItem {
  title: string
  description: string
  solution: string
  severity: string
}

interface Filters {
  min_dividend_yield: number
  max_p_nav: number
  min_occupancy: number
  max_debt_ratio: number
  min_turnover: number
  asset_type: string
}

export default function REITScreener() {
  const [reits, setReits] = useState<REIT[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [assetTypes, setAssetTypes] = useState<{ name: string; count: number; risk_level: string; description: string }[]>([])
  const [riskGuide, setRiskGuide] = useState<RiskGuideItem[]>([])
  const [showRiskGuide, setShowRiskGuide] = useState(false)
  const [overview, setOverview] = useState<MarketOverview | null>(null)
  const [showOverview, setShowOverview] = useState(false)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  const [filters, setFilters] = useState<Filters>({
    min_dividend_yield: 3,
    max_p_nav: 1.5,
    min_occupancy: 80,
    max_debt_ratio: 60,
    min_turnover: 50,
    asset_type: 'all',
  })

  const loadAssetTypes = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/types`)
      setAssetTypes(res.data.types || [])
    } catch (e) {
      console.error('获取资产类型失败:', e)
    }
  }, [])

  const loadRiskGuide = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/risk-guide`)
      setRiskGuide(res.data.risks || [])
    } catch (e) {
      console.error('获取风险指南失败:', e)
    }
  }, [])

  const loadReits = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/reit/screener`, { params: filters })
      setReits(res.data.reits || [])
      setUpdateTime(res.data.update_time || '')
    } catch (e) {
      console.error('获取REIT数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [filters])

  const loadOverview = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/overview`)
      setOverview(res.data)
    } catch (e) {
      console.error('获取市场概览失败:', e)
    }
  }, [])

  useEffect(() => { loadAssetTypes() }, [loadAssetTypes])
  useEffect(() => { loadRiskGuide() }, [loadRiskGuide])
  useEffect(() => { loadReits() }, [loadReits])
  useEffect(() => { loadOverview() }, [loadOverview])

  // 颜色工具
  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 65) return '#1890ff'
    if (score >= 50) return '#faad14'
    if (score >= 35) return '#fa8c16'
    return '#ff4d4f'
  }

  const getRiskColor = (level: string) => {
    if (level === '低') return '#52c41a'
    if (level === '中低') return '#1890ff'
    if (level === '中') return '#faad14'
    if (level === '中高') return '#fa8c16'
    return '#ff4d4f'
  }

  const getPremiumColor = (pct: number | null) => {
    if (pct === null) return 'var(--text-muted)'
    if (pct <= -10) return '#52c41a'
    if (pct <= 0) return '#73d13d'
    if (pct <= 10) return '#faad14'
    if (pct <= 20) return '#fa8c16'
    return '#ff4d4f'
  }

  const getRateColor = (sens: string) => {
    if (sens === '低') return '#52c41a'
    if (sens === '中') return '#faad14'
    if (sens === '中高') return '#fa8c16'
    return '#ff4d4f'
  }

  const getGradeStyle = (grade: string) => {
    const colors: Record<string, { bg: string; color: string }> = {
      'A': { bg: '#f6ffed', color: '#52c41a' },
      'B': { bg: '#e6f7ff', color: '#1890ff' },
      'C': { bg: '#fffbe6', color: '#faad14' },
      'D': { bg: '#fff7e6', color: '#fa8c16' },
      'E': { bg: '#fff2f0', color: '#ff4d4f' },
    }
    return colors[grade] || colors['C']
  }

  return (
    <div className="reit-page">
      {/* 页面标题 */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>REIT机构级筛选器</h2>
            <span className="stock-code">分派率 · NAV折溢价 · 杠杆分析 · 利率敏感性 · 综合评分</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button className="btn-add" onClick={loadReits}>刷新数据</button>
            <button
              className="btn-add"
              style={{ background: 'var(--accent-purple)' }}
              onClick={() => setShowOverview(!showOverview)}
            >
              {showOverview ? '关闭概览' : '市场概览'}
            </button>
            <button
              className="btn-add"
              style={{ background: 'var(--accent-purple)' }}
              onClick={() => setShowRiskGuide(!showRiskGuide)}
            >
              {showRiskGuide ? '关闭风险指南' : '风险指南'}
            </button>
          </div>
        </div>
        <div className="data-freshness">
          <span className="freshness-tag">更新时间: {updateTime}</span>
          <span className="freshness-tag">筛选结果: {reits.length} 只</span>
          <span className="freshness-tag">数据源: 新浪行情 + 东方财富NAV</span>
        </div>
      </div>

      {/* 市场概览 */}
      {showOverview && overview && (
        <div className="arb-notes" style={{ marginBottom: '16px' }}>
          <h3>REIT市场概览</h3>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: '12px', padding: '12px 0',
          }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>上市REIT数量</div>
              <div style={{ fontSize: '24px', fontWeight: 700 }}>{overview.total}</div>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>平均分派率</div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: '#52c41a' }}>{overview.avg_yield}%</div>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>平均P/NAV</div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: overview.avg_p_nav <= 1 ? '#52c41a' : '#faad14' }}>
                {overview.avg_p_nav?.toFixed(3) ?? '-'}
              </div>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>平均出租率</div>
              <div style={{ fontSize: '24px', fontWeight: 700 }}>{overview.avg_occupancy}%</div>
            </div>
            {overview.rate_environment && (
              <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>5年期LPR</div>
                <div style={{ fontSize: '24px', fontWeight: 700 }}>{overview.rate_environment.current_lpr_5y}%</div>
              </div>
            )}
          </div>
          {/* 资产类型分布 */}
          {overview.type_distribution && (
            <div style={{ marginTop: '8px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>资产类型分布</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {Object.entries(overview.type_distribution).map(([type, info]) => (
                  <span key={type} style={{
                    padding: '4px 10px', borderRadius: '4px', fontSize: '12px',
                    background: 'var(--bg-tertiary)', display: 'flex', gap: '8px',
                  }}>
                    <span>{type}</span>
                    <span style={{ color: 'var(--text-muted)' }}>{info.count}只</span>
                    <span style={{ color: '#52c41a' }}>均值{info.avg_yield}%</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 风险指南 */}
      {showRiskGuide && (
        <div className="arb-notes" style={{ marginBottom: '16px' }}>
          <h3>REIT投资风险指南</h3>
          <div className="arb-notes-grid">
            {riskGuide.map((risk, i) => (
              <div key={i} className="arb-note-item">
                <span className="arb-note-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  {risk.title}
                  <span style={{
                    fontSize: '10px', padding: '1px 6px', borderRadius: '3px',
                    background: risk.severity === '高' ? '#fff2f0' : risk.severity === '中高' ? '#fff7e6' : '#f6ffed',
                    color: risk.severity === '高' ? '#ff4d4f' : risk.severity === '中高' ? '#fa8c16' : '#52c41a',
                  }}>{risk.severity}</span>
                </span>
                <span className="arb-note-value" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {risk.description}
                </span>
                <span className="arb-note-desc">应对: {risk.solution}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 筛选条件 */}
      <div className="arb-notes" style={{ marginBottom: '16px' }}>
        <h3>筛选条件</h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: '12px', padding: '12px 0',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低分派率(%)</label>
            <input type="number" value={filters.min_dividend_yield}
              onChange={e => setFilters(prev => ({ ...prev, min_dividend_yield: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>P/NAV上限</label>
            <input type="number" step="0.1" value={filters.max_p_nav}
              onChange={e => setFilters(prev => ({ ...prev, max_p_nav: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低出租率(%)</label>
            <input type="number" value={filters.min_occupancy}
              onChange={e => setFilters(prev => ({ ...prev, min_occupancy: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最高负债率(%)</label>
            <input type="number" value={filters.max_debt_ratio}
              onChange={e => setFilters(prev => ({ ...prev, max_debt_ratio: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低日均成交额(万)</label>
            <input type="number" value={filters.min_turnover}
              onChange={e => setFilters(prev => ({ ...prev, min_turnover: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>资产类型</label>
            <select value={filters.asset_type}
              onChange={e => setFilters(prev => ({ ...prev, asset_type: e.target.value }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}>
              <option value="all">全部</option>
              {assetTypes.map(type => (
                <option key={type.name} value={type.name}>{type.name} ({type.count})</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 筛选结果 */}
      {loading ? (
        <div className="loading"><div className="spinner"></div>加载中...</div>
      ) : (
        <div className="table-container">
          <div className="arb-section-title">筛选结果（按综合评分降序）</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="arb-table" style={{ minWidth: '1400px' }}>
              <thead>
                <tr>
                  <th style={{ width: '40px' }}>#</th>
                  <th>代码</th>
                  <th style={{ minWidth: '160px' }}>名称</th>
                  <th>资产类型</th>
                  <th>现价</th>
                  <th>涨跌幅</th>
                  <th>分派率(%)</th>
                  <th>P/NAV</th>
                  <th>溢价率(%)</th>
                  <th>出租率(%)</th>
                  <th>负债率(%)</th>
                  <th>利率敏感度</th>
                  <th>利差(bp)</th>
                  <th>日均成交(万)</th>
                  <th>综合评分</th>
                  <th>等级</th>
                  <th style={{ width: '50px' }}>详情</th>
                </tr>
              </thead>
              <tbody>
                {reits.map((reit, i) => (
                  <>
                    <tr key={reit.code} style={{
                      cursor: 'pointer',
                      background: expandedRow === reit.code ? 'var(--bg-secondary)' : undefined,
                    }} onClick={() => setExpandedRow(expandedRow === reit.code ? null : reit.code)}>
                      <td>{i + 1}</td>
                      <td style={{ fontFamily: 'monospace' }}>{reit.code}</td>
                      <td style={{ fontWeight: 600 }}>{reit.name}</td>
                      <td>
                        <span style={{
                          padding: '2px 8px', borderRadius: '4px', fontSize: '11px',
                          background: 'var(--bg-tertiary)',
                        }}>{reit.asset_type}</span>
                      </td>
                      <td style={{ fontWeight: 600 }}>{reit.price.toFixed(3)}</td>
                      <td className={reit.change_pct >= 0 ? 'up' : 'down'}>
                        {reit.change_pct >= 0 ? '+' : ''}{reit.change_pct.toFixed(2)}%
                      </td>
                      <td style={{ fontWeight: 700, color: '#52c41a' }}>
                        {reit.dividend_yield.toFixed(2)}
                      </td>
                      <td style={{ color: getPremiumColor(reit.premium_pct) }}>
                        {reit.p_nav != null ? reit.p_nav.toFixed(3) : '-'}
                      </td>
                      <td style={{ color: getPremiumColor(reit.premium_pct), fontWeight: 600 }}>
                        {reit.premium_pct != null ? (
                          <>{reit.premium_pct > 0 ? '+' : ''}{reit.premium_pct.toFixed(1)}%</>
                        ) : '-'}
                      </td>
                      <td>{reit.occupancy_rate}</td>
                      <td style={{ color: reit.debt_ratio > 50 ? '#ff4d4f' : reit.debt_ratio > 40 ? '#faad14' : '#52c41a' }}>
                        {reit.debt_ratio}
                      </td>
                      <td>
                        <span style={{ color: getRateColor(reit.rate_sensitivity), fontWeight: 600 }}>
                          {reit.rate_sensitivity}
                        </span>
                      </td>
                      <td style={{ color: reit.current_spread > 0 ? '#52c41a' : '#ff4d4f' }}>
                        {reit.current_spread > 0 ? '+' : ''}{(reit.current_spread * 100).toFixed(0)}
                      </td>
                      <td>{reit.daily_turnover.toFixed(0)}</td>
                      <td>
                        <span style={{
                          fontWeight: 700, color: getScoreColor(reit.score), fontSize: '16px',
                        }}>{reit.score}</span>
                      </td>
                      <td>
                        {(() => {
                          const gs = getGradeStyle(reit.score_grade)
                          return (
                            <span style={{
                              padding: '2px 10px', borderRadius: '4px', fontWeight: 700,
                              fontSize: '14px', background: gs.bg, color: gs.color,
                            }}>{reit.score_grade}</span>
                          )
                        })()}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span style={{ fontSize: '16px', color: 'var(--text-muted)' }}>
                          {expandedRow === reit.code ? '▲' : '▼'}
                        </span>
                      </td>
                    </tr>
                    {/* 展开详情行 */}
                    {expandedRow === reit.code && (
                      <tr key={`${reit.code}-detail`} style={{ background: 'var(--bg-secondary)' }}>
                        <td colSpan={17} style={{ padding: '16px' }}>
                          <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                            gap: '16px',
                          }}>
                            {/* 基本信息 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>底层资产信息</h4>
                              <div style={{ fontSize: '12px', lineHeight: 1.8 }}>
                                <div><strong>底层资产：</strong>{reit.underlying || '-'}</div>
                                <div><strong>所在地区：</strong>{reit.location || '-'}</div>
                                <div><strong>资产描述：</strong>{reit.asset_description || '-'}</div>
                                <div><strong>上市年限：</strong>{reit.years_listed > 0 ? `${reit.years_listed}年` : '-'}</div>
                              </div>
                            </div>

                            {/* NAV分析 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>NAV折溢价分析</h4>
                              <div style={{ fontSize: '12px', lineHeight: 1.8 }}>
                                <div><strong>单位NAV：</strong>{reit.unit_nav != null ? reit.unit_nav.toFixed(4) : '-'}</div>
                                <div><strong>NAV日期：</strong>{reit.nav_date || '-'}</div>
                                <div><strong>P/NAV：</strong>
                                  <span style={{ color: getPremiumColor(reit.premium_pct), fontWeight: 600 }}>
                                    {reit.p_nav != null ? reit.p_nav.toFixed(3) : '-'}
                                  </span>
                                </div>
                                <div><strong>溢价率：</strong>
                                  <span style={{ color: getPremiumColor(reit.premium_pct), fontWeight: 600 }}>
                                    {reit.premium_pct != null ? `${reit.premium_pct > 0 ? '+' : ''}${reit.premium_pct.toFixed(2)}%` : '-'}
                                  </span>
                                </div>
                                <div><strong>估值评估：</strong>
                                  <span style={{ fontWeight: 600 }}>{reit.nav_assessment}</span>
                                </div>
                              </div>
                            </div>

                            {/* 分派率分析 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>分派率分析</h4>
                              <div style={{ fontSize: '12px', lineHeight: 1.8 }}>
                                <div><strong>年化分派率：</strong>
                                  <span style={{ color: '#52c41a', fontWeight: 700, fontSize: '14px' }}>
                                    {reit.dividend_yield.toFixed(2)}%
                                  </span>
                                </div>
                                <div><strong>累计分红(每份)：</strong>{reit.total_distributions > 0 ? reit.total_distributions.toFixed(4) : '-'}</div>
                                <div><strong>计算方法：</strong>{reit.distribution_method}</div>
                                <div><strong>当前利差(vs LPR)：</strong>
                                  <span style={{ color: reit.current_spread > 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
                                    {reit.current_spread > 0 ? '+' : ''}{reit.current_spread.toFixed(2)}%
                                  </span>
                                </div>
                                <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '4px' }}>
                                  {reit.spread_assessment}
                                </div>
                              </div>
                            </div>

                            {/* 杠杆分析 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>杠杆与负债分析</h4>
                              <div style={{ fontSize: '12px', lineHeight: 1.8 }}>
                                <div><strong>资产负债率：</strong>{reit.debt_ratio}%</div>
                                <div><strong>杠杆水平：</strong>
                                  <span style={{ color: getRiskColor(reit.leverage_level), fontWeight: 600 }}>
                                    {reit.leverage_level}
                                  </span>
                                </div>
                                <div><strong>利息负担：</strong>{reit.interest_burden}</div>
                                <div><strong>杠杆空间(距监管上限)：</strong>{reit.leverage_headroom}%</div>
                              </div>
                            </div>

                            {/* 利率敏感性 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>利率敏感性分析</h4>
                              <div style={{ fontSize: '12px', lineHeight: 1.8 }}>
                                <div><strong>敏感度等级：</strong>
                                  <span style={{ color: getRateColor(reit.rate_sensitivity), fontWeight: 600 }}>
                                    {reit.rate_sensitivity}
                                  </span>
                                </div>
                                <div><strong>LPR+100bp对分派率影响：</strong>
                                  <span style={{ color: '#ff4d4f' }}>-{reit.rate_yield_impact_bps}bp</span>
                                </div>
                                <div><strong>LPR+100bp对市价影响：</strong>
                                  <span style={{ color: '#ff4d4f' }}>{reit.rate_price_impact_pct}%</span>
                                </div>
                              </div>
                            </div>

                            {/* 经营期限 */}
                            {reit.concession && (
                              <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                                <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>经营期限分析</h4>
                                <div style={{ fontSize: '12px', lineHeight: 1.8 }}>
                                  <div><strong>总经营年限：</strong>{reit.concession.total_years}年</div>
                                  <div><strong>已过去：</strong>{reit.concession.elapsed_years}年</div>
                                  <div><strong>剩余年限：</strong>
                                    <span style={{ fontWeight: 700, color: reit.concession.remaining_years < 10 ? '#ff4d4f' : '#52c41a' }}>
                                      {reit.concession.remaining_years}年
                                    </span>
                                  </div>
                                  {/* 进度条 */}
                                  <div style={{ marginTop: '4px' }}>
                                    <div style={{
                                      height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden',
                                    }}>
                                      <div style={{
                                        width: `${100 - reit.concession.remaining_pct}%`,
                                        height: '100%', borderRadius: '3px',
                                        background: reit.concession.remaining_pct < 20 ? '#ff4d4f'
                                          : reit.concession.remaining_pct < 40 ? '#fa8c16' : '#52c41a',
                                      }} />
                                    </div>
                                  </div>
                                  <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '4px' }}>
                                    {reit.concession.warning}
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* 评分明细 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: 'var(--accent-blue)' }}>综合评分明细</h4>
                              <div style={{ fontSize: '12px', lineHeight: 2 }}>
                                {[
                                  { label: '分派率', key: 'distribution', max: 25 },
                                  { label: 'P/NAV估值', key: 'valuation', max: 20 },
                                  { label: '资产质量', key: 'asset_quality', max: 20 },
                                  { label: '财务健康', key: 'financial', max: 20 },
                                  { label: '流动性', key: 'liquidity', max: 15 },
                                ].map(dim => (
                                  <div key={dim.key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <span style={{ width: '70px' }}>{dim.label}</span>
                                    <div style={{
                                      flex: 1, height: '6px', background: 'var(--bg-tertiary)',
                                      borderRadius: '3px', overflow: 'hidden',
                                    }}>
                                      <div style={{
                                        width: `${((reit.score_breakdown as any)[dim.key] / dim.max) * 100}%`,
                                        height: '100%', borderRadius: '3px',
                                        background: getScoreColor((reit.score_breakdown as any)[dim.key] / dim.max * 100),
                                      }} />
                                    </div>
                                    <span style={{ width: '50px', textAlign: 'right', fontWeight: 600 }}>
                                      {(reit.score_breakdown as any)[dim.key]}/{dim.max}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* 风险提示 */}
                            <div style={{ background: 'var(--bg-primary)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ margin: '0 0 8px 0', fontSize: '13px', color: '#ff4d4f' }}>风险提示</h4>
                              <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', lineHeight: 1.8 }}>
                                {reit.risk_notes.map((note, idx) => (
                                  <li key={idx}>{note}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
                {reits.length === 0 && (
                  <tr>
                    <td colSpan={17} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                      暂无符合条件的REIT
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 评分体系说明 */}
      <div className="arb-notes" style={{ marginTop: '16px' }}>
        <h3>评分体系说明（100分制）</h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '12px', padding: '12px 0',
        }}>
          {[
            { dim: '分派率', weight: '25分', desc: '年化分派率越高越好，>=8%满分' },
            { dim: 'P/NAV估值', weight: '20分', desc: '折价越大越好，<=0.80满分' },
            { dim: '资产质量', weight: '20分', desc: '出租率+资产类型经济周期敏感性' },
            { dim: '财务健康', weight: '20分', desc: '杠杆率低+利率风险小为优' },
            { dim: '流动性', weight: '15分', desc: '日均成交额>=500万满分' },
          ].map(item => (
            <div key={item.dim} style={{
              background: 'var(--bg-secondary)', padding: '10px', borderRadius: '6px',
              display: 'flex', gap: '10px', alignItems: 'center',
            }}>
              <span style={{
                background: 'var(--accent-blue)', color: '#fff', padding: '4px 8px',
                borderRadius: '4px', fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap',
              }}>{item.weight}</span>
              <div>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>{item.dim}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '8px' }}>
          {[
            { grade: 'A', range: '>=80分', color: '#52c41a', desc: '优质标的' },
            { grade: 'B', range: '65-79分', color: '#1890ff', desc: '良好标的' },
            { grade: 'C', range: '50-64分', color: '#faad14', desc: '一般标的' },
            { grade: 'D', range: '35-49分', color: '#fa8c16', desc: '谨慎标的' },
            { grade: 'E', range: '<35分', color: '#ff4d4f', desc: '不建议' },
          ].map(g => (
            <span key={g.grade} style={{ fontSize: '12px', display: 'flex', gap: '4px', alignItems: 'center' }}>
              <span style={{
                padding: '1px 8px', borderRadius: '3px', fontWeight: 700,
                background: g.color + '20', color: g.color,
              }}>{g.grade}</span>
              <span style={{ color: 'var(--text-muted)' }}>{g.range} = {g.desc}</span>
            </span>
          ))}
        </div>
      </div>

      {/* 数据说明 */}
      <div className="arb-notes" style={{ marginTop: '16px' }}>
        <h3>数据说明与局限性</h3>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <p><strong>分派率计算方法：</strong>采用累计NAV差值法（累计NAV - 单位NAV = 历史累计分红），再年化计算。该方法估算值可能与实际现金分红有偏差，仅供参考。</p>
          <p><strong>NAV数据来源：</strong>东方财富基金API，更新频率为季度（季报/半年报/年报），非实时数据。NAV日期请关注"NAV日期"字段。</p>
          <p><strong>出租率/负债率：</strong>目前使用基于资产类型的行业估计值，非每只REIT的实际数据。实际数据需从各REIT定期报告获取。</p>
          <p><strong>利率敏感性：</strong>基于资产类型、杠杆率和久期特征的定性+定量分析，LPR基准假设为3.6%（5年期以上）。</p>
          <p><strong>投资建议：</strong>本工具仅供研究参考，不构成投资建议。REIT投资需关注底层资产质量、管理人能力、市场流动性等多重因素。</p>
        </div>
      </div>
    </div>
  )
}
