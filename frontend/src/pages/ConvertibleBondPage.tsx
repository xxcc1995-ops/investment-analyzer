import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { cbApi, type ConvertibleBond } from '../services/api'
import { PageSection, DataTable, LoadingSpinner, EmptyState, StatCard, StatCardGroup } from '../components/ui'
import type { Column } from '../components/ui'

export default function ConvertibleBondPage() {
  const navigate = useNavigate()
  const [cbBonds, setCbBonds] = useState<ConvertibleBond[]>([])
  const [cbLoading, setCbLoading] = useState(false)
  const [cbFetchTime, setCbFetchTime] = useState('')
  const [cbTotalBefore, setCbTotalBefore] = useState(0)
  const [cbTotal, setCbTotal] = useState(0)
  const [cbMaxDoubleLow, setCbMaxDoubleLow] = useState(130)
  const [cbTopN, setCbTopN] = useState(20)
  const [sortBy, setSortBy] = useState('double_low')
  const [minYtm, setMinYtm] = useState(-999)
  const [riskSummary, setRiskSummary] = useState<Record<string, number>>({})
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [dataSource, setDataSource] = useState('')

  const loadCB = useCallback(async (overrides?: {
    maxDoubleLow?: number
    topN?: number
    sortBy?: string
    minYtm?: number
  }) => {
    setCbLoading(true)
    try {
      const res = await cbApi.getDoubleLow({
        max_double_low: overrides?.maxDoubleLow ?? cbMaxDoubleLow,
        top_n: overrides?.topN ?? cbTopN,
        sort_by: overrides?.sortBy ?? sortBy,
        min_ytm: overrides?.minYtm ?? minYtm,
        min_turnover: 100,
        min_year_left: 1,
        exclude_st: true,
        exclude_force_redeem: true,
      })
      setCbBonds(res.data.bonds || [])
      setCbFetchTime(res.data.fetch_time || '')
      setCbTotalBefore(res.data.total_before_filter || 0)
      setCbTotal(res.data.total || 0)
      setRiskSummary(res.data.risk_summary || {})
      setDataSource(res.data.data_source || '')
    } catch (err) {
      console.error('加载可转债数据失败:', err)
    } finally {
      setCbLoading(false)
    }
  }, [cbMaxDoubleLow, cbTopN, sortBy, minYtm])

  useEffect(() => { loadCB() }, [loadCB])

  const handleSortChange = (newSort: string) => {
    setSortBy(newSort)
    loadCB({ sortBy: newSort })
  }

  const handleYtmChange = (newYtm: number) => {
    setMinYtm(newYtm)
    loadCB({ minYtm: newYtm })
  }

  const handleMaxDoubleLowChange = (val: number) => {
    setCbMaxDoubleLow(val)
    loadCB({ maxDoubleLow: val })
  }

  const handleTopNChange = (val: number) => {
    setCbTopN(val)
    loadCB({ topN: val })
  }

  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case 'A': return '#52c41a'
      case 'B': return '#1890ff'
      case 'C': return '#faad14'
      case 'D': return '#ff4d4f'
      default: return '#999'
    }
  }

  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case 'high': return '#ff4d4f'
      case 'medium': return '#faad14'
      default: return '#999'
    }
  }

  // 统计各评级数量
  const verdictCounts = cbBonds.reduce((acc, b) => {
    acc[b.verdict] = (acc[b.verdict] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // 风险标签汇总
  const riskEntries = Object.entries(riskSummary).sort((a, b) => b[1] - a[1])

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>可转债机构级分析（增强版）</h2>
            <span className="stock-code">5维度评分 + 纯债价值 + 税后YTM + 强赎量化 + 多源容错</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={sortBy} onChange={e => handleSortChange(e.target.value)}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value="double_low">按双低值排序</option>
              <option value="triple_low">按三低值排序</option>
              <option value="quality_score">按质量评分排序</option>
              <option value="ytm">按到期收益率排序</option>
              <option value="ytm_after_tax">按税后YTM排序</option>
              <option value="pure_bond_value">按纯债价值排序</option>
            </select>
            <select value={cbMaxDoubleLow} onChange={e => handleMaxDoubleLowChange(Number(e.target.value))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={120}>双低 ≤ 120</option>
              <option value={130}>双低 ≤ 130</option>
              <option value={140}>双低 ≤ 140</option>
              <option value={150}>双低 ≤ 150</option>
              <option value={999}>不限</option>
            </select>
            <select value={minYtm} onChange={e => handleYtmChange(Number(e.target.value))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={-999}>到期收益率不限</option>
              <option value={0}>YTM ≥ 0%（保本）</option>
              <option value={1}>YTM ≥ 1%</option>
              <option value={2}>YTM ≥ 2%</option>
              <option value={3}>YTM ≥ 3%</option>
            </select>
            <select value={cbTopN} onChange={e => handleTopNChange(Number(e.target.value))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={10}>前10只</option>
              <option value={20}>前20只</option>
              <option value={30}>前30只</option>
              <option value={50}>前50只</option>
            </select>
            <button className="btn-add" onClick={() => loadCB()}>刷新数据</button>
          </div>
        </div>
        <div className="data-freshness">
          <span className="freshness-tag">更新时间: {cbFetchTime}</span>
          <span className="freshness-tag">原始数据: {cbTotalBefore} 只</span>
          <span className="freshness-tag">筛选后: {cbTotal} 只</span>
          <span className="freshness-tag">显示: {cbBonds.length} 只</span>
          {dataSource && (
            <span className="freshness-tag" style={{
              background: dataSource === 'jisilu' ? 'rgba(82,196,26,0.1)' : 'rgba(250,173,20,0.1)',
              color: dataSource === 'jisilu' ? '#52c41a' : '#faad14',
            }}>
              数据源: {dataSource === 'jisilu' ? '集思录' : dataSource === 'akshare' ? 'AKShare(东方财富)' : '无'}
            </span>
          )}
        </div>
      </div>

      {/* 质量分布统计 */}
      {cbBonds.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '16px' }}>
          <div className="bond-yield-card" style={{ borderLeft: '4px solid #52c41a' }}>
            <div className="bond-yield-label">A级（优秀）</div>
            <div className="bond-yield-value" style={{ color: '#52c41a' }}>{verdictCounts['A'] || 0} 只</div>
            <div className="bond-yield-desc">总分 ≥ 80</div>
          </div>
          <div className="bond-yield-card" style={{ borderLeft: '4px solid #1890ff' }}>
            <div className="bond-yield-label">B级（良好）</div>
            <div className="bond-yield-value" style={{ color: '#1890ff' }}>{verdictCounts['B'] || 0} 只</div>
            <div className="bond-yield-desc">总分 65~79</div>
          </div>
          <div className="bond-yield-card" style={{ borderLeft: '4px solid #faad14' }}>
            <div className="bond-yield-label">C级（一般）</div>
            <div className="bond-yield-value" style={{ color: '#faad14' }}>{verdictCounts['C'] || 0} 只</div>
            <div className="bond-yield-desc">总分 50~64</div>
          </div>
          <div className="bond-yield-card" style={{ borderLeft: '4px solid #ff4d4f' }}>
            <div className="bond-yield-label">D级（较差）</div>
            <div className="bond-yield-value" style={{ color: '#ff4d4f' }}>{verdictCounts['D'] || 0} 只</div>
            <div className="bond-yield-desc">总分 &lt; 50</div>
          </div>
        </div>
      )}

      {/* 风险标签统计 */}
      {riskEntries.length > 0 && (
        <div style={{ marginBottom: '16px', padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border)' }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', fontSize: '13px' }}>⚠️ 风险标签分布</div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {riskEntries.map(([tag, count]) => (
              <span key={tag} style={{
                padding: '4px 10px', borderRadius: '12px', fontSize: '12px',
                background: tag.includes('高') || count > 5 ? 'rgba(255,77,79,0.1)' : 'rgba(250,173,20,0.1)',
                color: tag.includes('高') || count > 5 ? '#ff4d4f' : '#faad14',
                border: `1px solid ${tag.includes('高') || count > 5 ? 'rgba(255,77,79,0.3)' : 'rgba(250,173,20,0.3)'}`,
              }}>
                {tag}: {count}只
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 策略说明 */}
      <div className="arb-notes">
        <h3>机构级可转债分析体系</h3>
        <div className="arb-notes-grid">
          <div className="arb-note-item">
            <span className="arb-note-label">双低估值</span>
            <span className="arb-note-value">25分</span>
            <span className="arb-note-desc">价格 + 溢价率，越低越好，兼顾债性和股性</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">债底保护</span>
            <span className="arb-note-value">25分</span>
            <span className="arb-note-desc">纯债价值溢价率 + 税后YTM，双重验证债底安全边际</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">信用质量</span>
            <span className="arb-note-value">20分</span>
            <span className="arb-note-desc">评级 + 正股PE/PB，排除信用风险和基本面差的标的</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">转股潜力</span>
            <span className="arb-note-value">15分</span>
            <span className="arb-note-desc">转股价值越高、距强赎越近，转股退出概率越大</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">流动性</span>
            <span className="arb-note-value">15分</span>
            <span className="arb-note-desc">规模、成交额、剩余年限，确保可交易性</span>
          </div>
        </div>
        <div className="arb-notes-grid" style={{ marginTop: '12px' }}>
          <div className="arb-note-item">
            <span className="arb-note-label">纯债价值</span>
            <span className="arb-note-value">新增</span>
            <span className="arb-note-desc">现金流折现计算的理论债底，价格低于纯债价值即为"破净"</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">税后YTM</span>
            <span className="arb-note-value">新增</span>
            <span className="arb-note-desc">扣除20%利息税后的真实到期收益率，更准确反映持有到期收益</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">强赎风险量化</span>
            <span className="arb-note-value">新增</span>
            <span className="arb-note-desc">量化强赎触发距离和时间线，评估被强赎的价格影响</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">多源容错</span>
            <span className="arb-note-value">新增</span>
            <span className="arb-note-desc">集思录优先，AKShare(东方财富)兜底，60秒冷却自动恢复</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">下修概率</span>
            <span className="arb-note-value">新增</span>
            <span className="arb-note-desc">基于回售压力、转股价值、剩余期限评估下修可能性</span>
          </div>
        </div>
      </div>

      {/* 双低排名表格 */}
      {cbLoading ? (
        <div className="loading">
          <div className="spinner"></div>
          加载中...
        </div>
      ) : (
        <div className="table-container">
          <div className="arb-section-title">
            可转债排名（
            {sortBy === 'double_low' && '按双低值升序'}
            {sortBy === 'triple_low' && '按三低值升序'}
            {sortBy === 'quality_score' && '按质量评分降序'}
            {sortBy === 'ytm' && '按到期收益率降序'}
            {sortBy === 'ytm_after_tax' && '按税后YTM降序'}
            {sortBy === 'pure_bond_value' && '按纯债价值升序'}
            ）
          </div>
          <table className="arb-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>代码</th>
                <th>转债名称</th>
                <th>现价</th>
                <th>溢价率(%)</th>
                <th>双低值</th>
                <th>纯债价值</th>
                <th>YTM(%)</th>
                <th>税后YTM(%)</th>
                <th>质量评分</th>
                <th>强赎风险</th>
                <th>风险标签</th>
                <th>正股</th>
                <th>评级</th>
                <th>剩余年限</th>
              </tr>
            </thead>
            <tbody>
              {cbBonds.map((b, i) => (
                <React.Fragment key={b.bond_id}>
                  <tr onClick={() => setExpandedRow(expandedRow === b.bond_id ? null : b.bond_id)}
                    style={{ cursor: 'pointer' }}>
                    <td>{i + 1}</td>
                    <td>{b.bond_id}</td>
                    <td>{b.bond_nm}</td>
                    <td>{b.price.toFixed(2)}</td>
                    <td className={b.premium_rt <= 0 ? 'down' : ''}>{b.premium_rt.toFixed(2)}</td>
                    <td style={{ fontWeight: 700, color: b.double_low <= 120 ? '#52c41a' : b.double_low <= 130 ? '#1890ff' : '#faad14' }}>
                      {b.double_low.toFixed(2)}
                    </td>
                    <td style={{ fontSize: '12px', color: b.pure_bond_value > 0 && b.price <= b.pure_bond_value ? '#52c41a' : 'inherit' }}>
                      {b.pure_bond_value > 0 ? b.pure_bond_value.toFixed(2) : '-'}
                    </td>
                    <td style={{ fontWeight: 600, color: b.ytm_rt >= 0 ? '#52c41a' : '#ff4d4f' }}>
                      {b.ytm_rt.toFixed(2)}
                    </td>
                    <td style={{ fontWeight: 600, color: b.ytm_after_tax >= 0 ? '#52c41a' : '#ff4d4f', fontSize: '12px' }}>
                      {b.ytm_after_tax != null ? b.ytm_after_tax.toFixed(2) : '-'}
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        padding: '2px 8px', borderRadius: '10px', fontSize: '12px', fontWeight: 700,
                        background: `${getVerdictColor(b.verdict)}15`,
                        color: getVerdictColor(b.verdict),
                        border: `1px solid ${getVerdictColor(b.verdict)}30`,
                      }}>
                        {b.quality_score}
                        <span style={{ fontSize: '10px', opacity: 0.8 }}>{b.verdict}</span>
                      </span>
                    </td>
                    <td>
                      {b.redeem_risk ? (
                        <span style={{
                          padding: '2px 6px', borderRadius: '8px', fontSize: '10px', fontWeight: 600,
                          color: b.redeem_risk.redeem_risk_level === 'high' ? '#ff4d4f'
                            : b.redeem_risk.redeem_risk_level === 'medium' ? '#faad14'
                            : '#52c41a',
                          background: b.redeem_risk.redeem_risk_level === 'high' ? 'rgba(255,77,79,0.1)'
                            : b.redeem_risk.redeem_risk_level === 'medium' ? 'rgba(250,173,20,0.1)'
                            : 'rgba(82,196,26,0.1)',
                        }}>
                          {b.redeem_risk.redeem_risk_level === 'high' ? '高风险'
                            : b.redeem_risk.redeem_risk_level === 'medium' ? '中风险'
                            : b.redeem_risk.redeem_risk_level === 'low' ? '低风险'
                            : '安全'}
                        </span>
                      ) : '-'}
                    </td>
                    <td>
                      {b.risk_tags && b.risk_tags.length > 0 ? (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          {b.risk_tags.slice(0, 2).map((tag, j) => (
                            <span key={j} style={{
                              padding: '1px 6px', borderRadius: '8px', fontSize: '10px',
                              color: getRiskLevelColor(tag.level),
                              background: `${getRiskLevelColor(tag.level)}15`,
                              border: `1px solid ${getRiskLevelColor(tag.level)}30`,
                            }}>
                              {tag.tag}
                            </span>
                          ))}
                          {b.risk_tags.length > 2 && (
                            <span style={{ fontSize: '10px', color: '#999' }}>+{b.risk_tags.length - 2}</span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: '#52c41a', fontSize: '12px' }}>无风险</span>
                      )}
                    </td>
                    <td>{b.stock_nm}</td>
                    <td>{b.rating_cd}</td>
                    <td>{b.year_left.toFixed(1)}</td>
                  </tr>
                  {expandedRow === b.bond_id && (
                    <tr key={`${b.bond_id}-detail`} style={{ background: 'var(--bg-secondary)' }}>
                      <td colSpan={15} style={{ padding: '12px 20px' }}>
                        {/* 五维度评分雷达 */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                          {b.quality_scores && Object.entries(b.quality_scores).map(([key, val]) => {
                            const dimNames: Record<string, string> = {
                              valuation: '双低估值',
                              bond_floor: '债底保护',
                              credit: '信用质量',
                              convert: '转股潜力',
                              liquidity: '流动性',
                            }
                            const pct = val.max > 0 ? (val.score / val.max * 100) : 0
                            return (
                              <div key={key} style={{ fontSize: '12px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                  <span style={{ fontWeight: 600 }}>{dimNames[key] || key}</span>
                                  <span style={{ color: pct >= 60 ? '#52c41a' : pct >= 40 ? '#faad14' : '#ff4d4f' }}>
                                    {val.score}/{val.max} {val.label}
                                  </span>
                                </div>
                                <div style={{ height: '4px', background: 'var(--border)', borderRadius: '2px' }}>
                                  <div style={{
                                    height: '100%', borderRadius: '2px', width: `${pct}%`,
                                    background: pct >= 60 ? '#52c41a' : pct >= 40 ? '#faad14' : '#ff4d4f',
                                  }} />
                                </div>
                              </div>
                            )
                          })}
                        </div>
                        {/* 机构级详细指标 */}
                        <div style={{ marginTop: '10px', padding: '10px', background: 'var(--bg-primary)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px', fontSize: '12px' }}>
                            <div><strong>转股价值:</strong> {b.convert_value.toFixed(2)}</div>
                            <div><strong>纯债价值:</strong> {b.pure_bond_value > 0 ? b.pure_bond_value.toFixed(2) : '-'}
                              {b.pure_bond_value > 0 && (
                                <span style={{ color: b.price <= b.pure_bond_value ? '#52c41a' : '#faad14', marginLeft: 4 }}>
                                  ({b.price <= b.pure_bond_value ? '破净' : `溢价${((b.price - b.pure_bond_value) / b.pure_bond_value * 100).toFixed(1)}%`})
                                </span>
                              )}
                            </div>
                            <div><strong>税前YTM:</strong> <span style={{ color: b.ytm_rt >= 0 ? '#52c41a' : '#ff4d4f' }}>{b.ytm_rt.toFixed(2)}%</span></div>
                            <div><strong>税后YTM:</strong> <span style={{ color: b.ytm_after_tax >= 0 ? '#52c41a' : '#ff4d4f' }}>{b.ytm_after_tax?.toFixed(2) ?? '-'}%</span></div>
                            <div><strong>距强赎距离:</strong> {b.redeem_distance.toFixed(1)}%</div>
                            <div><strong>正股PE:</strong> {b.stock_pe > 0 ? b.stock_pe.toFixed(1) : '亏损'}</div>
                            <div><strong>正股PB:</strong> {b.stock_pb > 0 ? b.stock_pb.toFixed(2) : '-'}</div>
                            <div><strong>回售YTM:</strong> {b.put_ytm_rt.toFixed(2)}%</div>
                            <div><strong>三低值:</strong> {b.triple_low?.toFixed(2) ?? '-'}</div>
                          </div>
                          {/* 强赎风险详情 */}
                          {b.redeem_risk && b.redeem_risk.redeem_timeline && (
                            <div style={{ marginTop: '8px', padding: '6px 10px', borderRadius: '4px', fontSize: '12px',
                              background: b.redeem_risk.redeem_risk_level === 'high' ? 'rgba(255,77,79,0.08)' : 'rgba(250,173,20,0.08)',
                              color: b.redeem_risk.redeem_risk_level === 'high' ? '#ff4d4f' : '#faad14',
                            }}>
                              强赎: {b.redeem_risk.redeem_timeline}
                              {b.redeem_risk.redeem_price_impact !== 0 && (
                                <span> (若被强赎，价格变动约 {b.redeem_risk.redeem_price_impact > 0 ? '+' : ''}{b.redeem_risk.redeem_price_impact.toFixed(2)} 元)</span>
                              )}
                            </div>
                          )}
                          {/* 下修概率 */}
                          {b.revision_prob && b.revision_prob.revision_probability > 0 && (
                            <div style={{ marginTop: '6px', padding: '6px 10px', borderRadius: '4px', fontSize: '12px',
                              background: 'rgba(24,144,255,0.08)', color: '#1890ff',
                            }}>
                              下修概率: {b.revision_prob.revision_probability}%
                              {b.revision_prob.revision_factors.length > 0 && (
                                <span> ({b.revision_prob.revision_factors.join('，')})</span>
                              )}
                            </div>
                          )}
                          {/* 风险标签详情 */}
                          {b.risk_tags && b.risk_tags.length > 0 && (
                            <div style={{ marginTop: '6px', fontSize: '12px', color: '#ff4d4f' }}>
                              风险: {b.risk_tags.map(t => t.desc).join('；')}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {cbBonds.length === 0 && (
                <tr>
                  <td colSpan={15} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    暂无符合条件的可转债
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 注意事项 */}
      <div className="arb-notes">
        <h3>可转债策略全景与注意事项</h3>
        <div className="arb-notes-content">
          <div className="arb-risk-section">
            <h4>📚 策略选择决策树（小白必看）</h4>
            <div style={{ padding: '12px', background: 'var(--bg-secondary)', borderRadius: '8px', marginBottom: '12px', fontSize: '13px', lineHeight: 2 }}>
              <div><strong>你是小白吗？</strong></div>
              <div style={{ paddingLeft: '20px' }}>
                <div>├── <strong>是</strong> → <span style={{ color: '#52c41a' }}>安道全面值策略</span>（最简单，1万起步）</div>
                <div style={{ paddingLeft: '40px' }}>└── 想更省心？→ <span style={{ color: '#faad14' }}>摊大饼策略</span>（类指数）</div>
                <div>└── <strong>否</strong> → 你追求什么？（对应下方八大战法）</div>
                <div style={{ paddingLeft: '40px' }}>
                  ├── 稳健+持续优胜 → <span style={{ color: '#1890ff' }}>双低策略</span>（经典量化）/ <span style={{ color: '#13c2c2' }}>轮动策略</span>（双低进阶，定期趋优）<br/>
                  ├── 绝对保本 → <span style={{ color: '#722ed1' }}>YTM保本策略</span>（即「正收益策略」，最保守）<br/>
                  ├── 临近到期做差价 → <span style={{ color: '#fa8c16' }}>临期债网格策略</span>（到期前1.5年内高抛低吸）<br/>
                  ├── 高弹性 → <span style={{ color: '#13c2c2' }}>三低策略</span>（低价格+低溢价+低规模，波动大）<br/>
                  └── 博弈收益 →<br/>
                  <span style={{ paddingLeft: '40px' }}>
                    ├── <span style={{ color: '#f5222d' }}>下修博弈</span>（赌公司下修转股价）<br/>
                    ├── <span style={{ color: '#ff4d4f' }}>强赎博弈</span>（赌公司促转股）<br/>
                    ├── <span style={{ color: '#a0d911' }}>问题债博弈</span>（博弈困境反转/小额清偿）<br/>
                    └── <span style={{ color: '#eb2f96' }}>负溢价套利</span>（高级操作，T+1转股）
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="arb-risk-section">
            <div style={{
              display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
              padding: '16px 20px', background: 'linear-gradient(135deg, rgba(88,166,255,0.08), rgba(114,46,209,0.08))',
              border: '1px solid #30363d', borderRadius: '10px',
            }}>
              <div style={{ fontSize: 32 }}>📖</div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontWeight: 700, fontSize: 15, color: '#e6edf3' }}>可转债八大战法（实战手册）</div>
                <div style={{ fontSize: 12.5, color: '#8b949e', marginTop: 2 }}>
                  依据《可转债：从入门到精通的八大战法》整理，每个战法可直接运行实时筛选。含双低、轮动、临期债网格、下修/强赎/问题债博弈、负溢价套利等。
                </div>
              </div>
              <button
                className="btn-add"
                onClick={() => navigate('/cb-strategies')}
                style={{ background: '#58a6ff', color: '#0d1117', border: 'none', padding: '8px 18px', borderRadius: '6px', cursor: 'pointer', fontSize: '13px', fontWeight: 600 }}
              >
                打开八大战法界面 →
              </button>
            </div>
          </div>

          <div className="arb-risk-section">
            <h4>⚠️ 所有策略通用的避坑清单</h4>
            <ul>
              <li><strong>永远不要单只重仓</strong>：再看好也要分散，10只以上</li>
              <li><strong>强赎公告必须看</strong>：不看就亏钱，设置提醒</li>
              <li><strong>不要追涨杀跌</strong>：策略纪律比判断更重要</li>
              <li><strong>理解你的策略</strong>：不理解就不要用</li>
              <li><strong>用闲钱投资</strong>：可转债可能被锁定很久</li>
              <li><strong>定期复盘</strong>：每周看看持仓，检查风险标签</li>
              <li><strong>不要借钱买转债</strong>：杠杆放大风险</li>
              <li><strong>市场恐慌时是机会</strong>：别人恐惧我贪婪（但要分散）</li>
            </ul>
          </div>

          <div className="arb-risk-section">
            <h4>🏗️ 机构级分析要点</h4>
            <ul>
              <li><strong>纯债价值是真正的底线</strong>：价格低于纯债价值（破净）意味着即使违约也有较高回收率</li>
              <li><strong>税后YTM才是真实收益</strong>：利息扣20%税后，税后YTM为正才真正保本</li>
              <li><strong>强赎风险要量化</strong>：关注距强赎触发距离和时间线，避免被低价赎回</li>
              <li><strong>信用评级只是起点</strong>：评级AA以下需格外谨慎，搜特转债首例违约打破了"零违约"信仰</li>
              <li><strong>质量评分 &gt; 双低值</strong>：单纯追求低双低可能踩雷，综合评分更能反映投资价值</li>
            </ul>
          </div>

          <div className="arb-risk-section">
            <h4>🔄 轮动操作指南</h4>
            <ul>
              <li>每1~2周按最新排名调仓一次（可按质量评分、双低值或三低值排序）</li>
              <li>卖出排名跌出前N的转债，买入新进入前N的转债</li>
              <li>转债触发强赎或到期时及时卖出</li>
              <li>建议等权持有10~20只分散风险</li>
              <li>遇到高风险标签标的，优先卖出或降低仓位</li>
            </ul>
          </div>

          <div className="arb-risk-section">
            <h4>🚨 风险提示</h4>
            <ul>
              <li><strong>信用风险</strong>：低评级转债可能存在违约风险，建议选择AA-以上评级</li>
              <li><strong>到期赎回风险</strong>：正股长期低迷、转股价值远低于转股价，公司可能选择到期还钱</li>
              <li><strong>强赎风险</strong>：关注强赎公告，避免被低价赎回（通常100-103元）</li>
              <li><strong>流动性风险</strong>：成交额过小的转债难以按预期价格买卖</li>
              <li><strong>市场风险</strong>：极端熊市中双低策略仍有回撤，但通常小于正股</li>
              <li><strong>数据源风险</strong>：AKShare兜底数据缺少部分字段（YTM、强赎信息等），投资决策应以集思录数据为准</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
