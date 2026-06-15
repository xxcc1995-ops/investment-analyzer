import { LoadingSpinner } from '../components/ui'
import React, { useState, useEffect, useCallback, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { cbApi, type ConvertibleBond } from '../services/api'

// ============================================================
// Types
// ============================================================

interface StrategyInfo {
  name: string
  master: string
  source: string
  philosophy: string
  risk_level: string
  complexity: string
  min_capital: string
  expected_return: string
  description: string
  rules: string[]
  suitable_for?: string[]
  warnings?: string[]
  risks?: Array<{ name: string; probability: string; impact: string; solution: string }>
  pitfalls?: string[]
}

interface SortConfig {
  key: string
  direction: 'asc' | 'desc'
}

// ============================================================
// Constants
// ============================================================

const STRATEGY_KEYS = [
  'andaoquan', 'dual_low', 'triple_low', 'pancake',
  'ytm_defense', 'negative_premium', 'revision_game', 'redeem_game',
]

const STRATEGY_META: Record<string, { icon: string; color: string; tag: string }> = {
  andaoquan: { icon: '🛡️', color: '#52c41a', tag: '入门' },
  dual_low: { icon: '📊', color: '#1890ff', tag: '经典' },
  triple_low: { icon: '🔻', color: '#13c2c2', tag: '进阶' },
  pancake: { icon: '🥞', color: '#faad14', tag: '懒人' },
  ytm_defense: { icon: '🏦', color: '#722ed1', tag: '保守' },
  negative_premium: { icon: '💎', color: '#eb2f96', tag: '套利' },
  revision_game: { icon: '🎯', color: '#f5222d', tag: '博弈' },
  redeem_game: { icon: '🔥', color: '#ff4d4f', tag: '博弈' },
}

const DIFFICULTY_ORDER: Record<string, number> = { '简单': 1, '中等': 2, '中-高': 3, '较高': 4, '高': 5 }

// ============================================================
// Component
// ============================================================

export default function MasterStrategyPage() {
  const [activeStrategy, setActiveStrategy] = useState('andaoquan')
  const [strategies, setStrategies] = useState<Record<string, StrategyInfo>>({})
  const [bonds, setBonds] = useState<ConvertibleBond[]>([])
  const [loading, setLoading] = useState(false)
  const [fetchTime, setFetchTime] = useState('')
  const [totalBefore, setTotalBefore] = useState(0)
  const [total, setTotal] = useState(0)
  const [riskSummary, setRiskSummary] = useState<Record<string, number>>({})
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [topN, setTopN] = useState(20)
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: '', direction: 'asc' })
  const [searchText, setSearchText] = useState('')
  const [showBacktestPanel, setShowBacktestPanel] = useState(false)
  const [activeTab, setActiveTab] = useState<'screening' | 'compare' | 'insights'>('screening')

  // 加载策略定义
  useEffect(() => {
    cbApi.getStrategies().then(res => {
      setStrategies(res.data.strategies || {})
    }).catch(() => {})
  }, [])

  // 加载策略数据
  const loadStrategy = useCallback(async (strategy: string, n?: number) => {
    setLoading(true)
    try {
      const res = await cbApi.getMasterStrategy({
        strategy,
        top_n: n ?? topN,
      })
      setBonds(res.data.bonds || [])
      setFetchTime(res.data.fetch_time || '')
      setTotalBefore(res.data.total_before_filter || 0)
      setTotal(res.data.total || 0)
      setRiskSummary(res.data.risk_summary || {})
    } catch (err) {
      console.error('加载大师策略数据失败:', err)
    } finally {
      setLoading(false)
    }
  }, [topN])

  useEffect(() => { loadStrategy(activeStrategy) }, [loadStrategy, activeStrategy])

  const handleStrategyChange = (key: string) => {
    setActiveStrategy(key)
    setExpandedRow(null)
    setSortConfig({ key: '', direction: 'asc' })
    setSearchText('')
    loadStrategy(key)
  }

  const handleTopNChange = (n: number) => {
    setTopN(n)
    loadStrategy(activeStrategy, n)
  }

  const handleSort = (key: string) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }))
  }

  // ============================================================
  // Derived data
  // ============================================================

  const filteredAndSortedBonds = useMemo(() => {
    let result = [...bonds]

    // Search filter
    if (searchText) {
      const q = searchText.toLowerCase()
      result = result.filter(b =>
        b.bond_id.includes(q) ||
        b.bond_nm.toLowerCase().includes(q) ||
        b.stock_nm.toLowerCase().includes(q)
      )
    }

    // Sort
    if (sortConfig.key) {
      result.sort((a, b) => {
        let aVal: number = 0
        let bVal: number = 0
        switch (sortConfig.key) {
          case 'price': aVal = a.price; bVal = b.price; break
          case 'premium_rt': aVal = a.premium_rt; bVal = b.premium_rt; break
          case 'double_low': aVal = a.double_low; bVal = b.double_low; break
          case 'ytm_rt': aVal = a.ytm_rt; bVal = b.ytm_rt; break
          case 'convert_value': aVal = a.convert_value; bVal = b.convert_value; break
          case 'quality_score': aVal = a.quality_score; bVal = b.quality_score; break
          case 'stock_pe': aVal = a.stock_pe; bVal = b.stock_pe; break
          case 'year_left': aVal = a.year_left; bVal = b.year_left; break
          default: return 0
        }
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal
      })
    }

    return result
  }, [bonds, searchText, sortConfig])

  // ============================================================
  // Chart: Risk-Return scatter
  // ============================================================

  const riskReturnChart = useMemo(() => {
    if (!strategies || Object.keys(strategies).length === 0) return null

    const data = STRATEGY_KEYS
      .filter(k => strategies[k])
      .map(k => {
        const s = strategies[k]
        const meta = STRATEGY_META[k]
        // Parse expected return range to get midpoint
        const retMatch = s.expected_return.match(/(\d+)-(\d+)/)
        const midReturn = retMatch ? (parseInt(retMatch[1]) + parseInt(retMatch[2])) / 2 : 10
        const riskMap: Record<string, number> = { '低': 1, '低-中': 2, '中': 3, '中-高': 4, '高': 5 }
        const riskVal = riskMap[s.risk_level] || 3
        return {
          name: s.name,
          value: [riskVal, midReturn, 20],
          itemStyle: { color: meta.color },
          key: k,
        }
      })

    return {
      backgroundColor: 'transparent',
      tooltip: {
        formatter: (params: any) => {
          const d = params.data
          const riskLabels = ['', '低风险', '低-中风险', '中风险', '中-高风险', '高风险']
          return `<strong>${d.name}</strong><br/>风险: ${riskLabels[d.value[0]]}<br/>预期年化: ${d.value[1]}%`
        },
      },
      grid: { left: 60, right: 30, top: 30, bottom: 40 },
      xAxis: {
        type: 'value',
        name: '风险等级',
        nameLocation: 'middle',
        nameGap: 25,
        min: 0.5,
        max: 5.5,
        axisLabel: {
          color: '#9ca3af',
          formatter: (v: number) => {
            const labels = ['', '低', '低-中', '中', '中-高', '高']
            return labels[Math.round(v)] || ''
          },
        },
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      yAxis: {
        type: 'value',
        name: '预期年化(%)',
        nameLocation: 'middle',
        nameGap: 45,
        axisLabel: { color: '#9ca3af', formatter: '{c}%' },
        splitLine: { lineStyle: { color: '#21262d' } },
        axisLine: { lineStyle: { color: '#374151' } },
      },
      series: [{
        type: 'scatter',
        data,
        symbolSize: (val: number[]) => val[2],
        label: {
          show: true,
          formatter: (params: any) => strategies[params.data.key]?.name.replace('策略', '') || '',
          position: 'top',
          color: '#d1d5db',
          fontSize: 11,
        },
        emphasis: {
          scale: 1.5,
        },
      }],
    }
  }, [strategies])

  // ============================================================
  // Helpers
  // ============================================================

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

  const getSortIndicator = (key: string) => {
    if (sortConfig.key !== key) return ''
    return sortConfig.direction === 'asc' ? ' ↑' : ' ↓'
  }

  const exportCSV = () => {
    if (!filteredAndSortedBonds.length) return
    const headers = ['排名', '代码', '转债名称', '现价', '溢价率(%)', '双低值', 'YTM(%)', '转股价值', '质量评分', '评级', '正股', '剩余年限']
    const rows = filteredAndSortedBonds.map((b, i) => [
      i + 1, b.bond_id, b.bond_nm, b.price?.toFixed(2) ?? '', b.premium_rt?.toFixed(2) ?? '',
      b.double_low?.toFixed(2) ?? '', b.ytm_rt?.toFixed(2) ?? '', b.convert_value?.toFixed(1) ?? '',
      b.quality_score ?? '', b.rating_cd ?? '', b.stock_nm ?? '', b.year_left?.toFixed(1) ?? '',
    ])
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `大师策略_${strategies[activeStrategy]?.name || activeStrategy}_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const currentInfo = strategies[activeStrategy]

  // ============================================================
  // Render
  // ============================================================

  return (
    <div className="cb-page">
      {/* Header */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>可转债大师策略</h2>
            <span className="stock-code">8种经典策略，从入门到套利 · 一键切换视角</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select value={topN} onChange={e => handleTopNChange(Number(e.target.value))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={10}>前10只</option>
              <option value={20}>前20只</option>
              <option value={30}>前30只</option>
              <option value={50}>前50只</option>
            </select>
            <button className="btn-add" onClick={() => loadStrategy(activeStrategy)}>刷新数据</button>
            <button className="btn-add" onClick={exportCSV}
              style={{ background: '#13c2c2', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}>
              导出CSV
            </button>
            <button className="btn-add" onClick={() => setShowBacktestPanel(!showBacktestPanel)}
              style={{ background: '#722ed1', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}>
              {showBacktestPanel ? '隐藏回测' : '策略回测'}
            </button>
          </div>
        </div>
      </div>

      {/* Strategy cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px', marginBottom: '16px' }}>
        {STRATEGY_KEYS.map(key => {
          const meta = STRATEGY_META[key]
          const info = strategies[key]
          const isActive = activeStrategy === key
          return (
            <div key={key} onClick={() => handleStrategyChange(key)} style={{
              padding: '12px 14px',
              borderRadius: '8px',
              cursor: 'pointer',
              border: isActive ? `2px solid ${meta.color}` : '2px solid var(--border)',
              background: isActive ? `${meta.color}10` : 'var(--bg-secondary)',
              transition: 'all 0.2s',
              position: 'relative',
            }}>
              <div style={{ position: 'absolute', top: '6px', right: '8px', fontSize: '9px', padding: '1px 5px', borderRadius: '6px', background: `${meta.color}20`, color: meta.color, fontWeight: 600 }}>
                {meta.tag}
              </div>
              <div style={{ fontSize: '20px', marginBottom: '4px' }}>{meta.icon}</div>
              <div style={{ fontWeight: 700, fontSize: '13px', color: isActive ? meta.color : 'var(--text-primary)', lineHeight: 1.3 }}>
                {info?.name || key}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {info?.master || ''}
              </div>
              <div style={{ fontSize: '11px', marginTop: '4px', display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span style={{
                  padding: '1px 5px', borderRadius: '8px', fontSize: '9px',
                  background: info?.risk_level === '低' ? '#52c41a15' : info?.risk_level === '中' ? '#faad1415' : '#ff4d4f15',
                  color: info?.risk_level === '低' ? '#52c41a' : info?.risk_level === '中' ? '#faad14' : '#ff4d4f',
                }}>
                  {info?.risk_level || ''}
                </span>
                <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                  {info?.expected_return || ''}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Strategy detail */}
      {currentInfo && (
        <div className="arb-notes" style={{ marginBottom: '16px' }}>
          <h3>{STRATEGY_META[activeStrategy]?.icon} {currentInfo.name} — {currentInfo.master}</h3>
          <div style={{ marginBottom: '8px', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
            「{currentInfo.philosophy}」 — {currentInfo.source}
          </div>
          <div style={{ marginBottom: '12px', fontSize: '13px' }}>{currentInfo.description}</div>
          <div className="arb-notes-grid">
            <div className="arb-note-item">
              <span className="arb-note-label">风险等级</span>
              <span className="arb-note-value">{currentInfo.risk_level}</span>
            </div>
            <div className="arb-note-item">
              <span className="arb-note-label">复杂度</span>
              <span className="arb-note-value">{currentInfo.complexity}</span>
            </div>
            <div className="arb-note-item">
              <span className="arb-note-label">最低资金</span>
              <span className="arb-note-value">{currentInfo.min_capital}</span>
            </div>
            <div className="arb-note-item">
              <span className="arb-note-label">预期收益</span>
              <span className="arb-note-value">{currentInfo.expected_return}</span>
            </div>
          </div>
          <div style={{ marginTop: '12px' }}>
            <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '6px' }}>操作规则：</div>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: 1.8 }}>
              {currentInfo.rules.map((rule, i) => <li key={i}>{rule}</li>)}
            </ul>
          </div>

          {/* 适用人群 */}
          {currentInfo.suitable_for && currentInfo.suitable_for.length > 0 && (
            <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(82,196,26,0.06)', borderRadius: '8px', border: '1px solid rgba(82,196,26,0.2)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: '#52c41a' }}>
                ✅ 适合什么样的人？
              </div>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: 1.8, color: 'var(--text-secondary)' }}>
                {currentInfo.suitable_for.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </div>
          )}

          {/* 注意事项 */}
          {currentInfo.warnings && currentInfo.warnings.length > 0 && (
            <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(250,173,20,0.06)', borderRadius: '8px', border: '1px solid rgba(250,173,20,0.2)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: '#faad14' }}>
                ⚠️ 注意事项（必须知道）
              </div>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: 1.8, color: 'var(--text-secondary)' }}>
                {currentInfo.warnings.map((item, i) => <li key={i}>{item}</li>)}
              </ul>
            </div>
          )}

          {/* 潜在风险 */}
          {currentInfo.risks && currentInfo.risks.length > 0 && (
            <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(255,77,79,0.06)', borderRadius: '8px', border: '1px solid rgba(255,77,79,0.2)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: '#ff4d4f' }}>
                🔴 潜在风险
              </div>
              <div style={{ display: 'grid', gap: '8px' }}>
                {currentInfo.risks.map((risk, i) => (
                  <div key={i} style={{ padding: '8px', background: 'var(--bg-primary)', borderRadius: '6px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 600 }}>{risk.name}</span>
                      <span style={{
                        padding: '1px 6px', borderRadius: '8px', fontSize: '10px',
                        background: risk.probability === '高' ? 'rgba(255,77,79,0.15)' : risk.probability === '中等' ? 'rgba(250,173,20,0.15)' : 'rgba(82,196,26,0.15)',
                        color: risk.probability === '高' ? '#ff4d4f' : risk.probability === '中等' ? '#faad14' : '#52c41a',
                      }}>
                        概率: {risk.probability}
                      </span>
                    </div>
                    <div style={{ color: 'var(--text-muted)' }}>
                      <span>影响: {risk.impact}</span>
                      <span style={{ marginLeft: '12px' }}>应对: {risk.solution}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 小白踩坑点 */}
          {currentInfo.pitfalls && currentInfo.pitfalls.length > 0 && (
            <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(114,46,209,0.06)', borderRadius: '8px', border: '1px solid rgba(114,46,209,0.2)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: '#722ed1' }}>
                💀 小白最容易踩的坑
              </div>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', lineHeight: 2, color: 'var(--text-secondary)' }}>
                {currentInfo.pitfalls.map((item, i) => {
                  const parts = item.split('→')
                  return (
                    <li key={i}>
                      <span style={{ color: '#ff4d4f', fontWeight: 600 }}>{parts[0]}</span>
                      {parts[1] && <span style={{ color: 'var(--text-muted)' }}> → {parts[1]}</span>}
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: '16px', borderBottom: '1px solid var(--border)' }}>
        {([
          { key: 'screening', label: '策略筛选' },
          { key: 'compare', label: '策略对比' },
          { key: 'insights', label: '大师智慧' },
        ] as const).map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
            padding: '10px 20px',
            background: activeTab === tab.key ? 'var(--bg-secondary)' : 'transparent',
            color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
            border: 'none',
            borderBottom: activeTab === tab.key ? `2px solid ${STRATEGY_META[activeStrategy]?.color || '#1890ff'}` : '2px solid transparent',
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: activeTab === tab.key ? 600 : 400,
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ====== Tab: Screening ====== */}
      {activeTab === 'screening' && (
        <>
          {/* Data info bar */}
          <div className="data-freshness" style={{ marginBottom: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <span className="freshness-tag">更新时间: {fetchTime}</span>
              <span className="freshness-tag">原始数据: {totalBefore} 只</span>
              <span className="freshness-tag">符合条件: {total} 只</span>
              <span className="freshness-tag">显示: {filteredAndSortedBonds.length} 只</span>
            </div>
            <input
              type="text"
              placeholder="搜索代码/名称..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              style={{ padding: '5px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '12px', width: '160px', background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            />
          </div>

          {/* Risk summary badges */}
          {Object.keys(riskSummary).length > 0 && (
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
              {Object.entries(riskSummary).map(([tag, count]) => (
                <span key={tag} style={{
                  padding: '3px 10px', borderRadius: '12px', fontSize: '11px',
                  background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--text-secondary)',
                }}>
                  {tag}: {count}
                </span>
              ))}
            </div>
          )}

          {/* Results table */}
          {loading ? (
            <LoadingSpinner />
          ) : (
            <div className="table-container">
              <div className="arb-section-title">{currentInfo?.name || activeStrategy} 筛选结果</div>
              <table className="arb-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>#</th>
                    <th onClick={() => handleSort('bond_id')} style={{ cursor: 'pointer' }}>代码{getSortIndicator('bond_id')}</th>
                    <th>转债名称</th>
                    <th onClick={() => handleSort('price')} style={{ cursor: 'pointer' }}>现价{getSortIndicator('price')}</th>
                    <th onClick={() => handleSort('premium_rt')} style={{ cursor: 'pointer' }}>溢价率(%){getSortIndicator('premium_rt')}</th>
                    <th onClick={() => handleSort('double_low')} style={{ cursor: 'pointer' }}>双低值{getSortIndicator('double_low')}</th>
                    <th onClick={() => handleSort('ytm_rt')} style={{ cursor: 'pointer' }}>YTM(%){getSortIndicator('ytm_rt')}</th>
                    <th onClick={() => handleSort('convert_value')} style={{ cursor: 'pointer' }}>转股价值{getSortIndicator('convert_value')}</th>
                    <th onClick={() => handleSort('quality_score')} style={{ cursor: 'pointer' }}>质量评分{getSortIndicator('quality_score')}</th>
                    <th>风险标签</th>
                    <th>正股</th>
                    <th>评级</th>
                    <th onClick={() => handleSort('year_left')} style={{ cursor: 'pointer' }}>剩余年限{getSortIndicator('year_left')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAndSortedBonds.map((b, i) => (
                    <React.Fragment key={b.bond_id}>
                      <tr onClick={() => setExpandedRow(expandedRow === b.bond_id ? null : b.bond_id)}
                        style={{ cursor: 'pointer', background: expandedRow === b.bond_id ? 'var(--bg-secondary)' : undefined }}>
                        <td>{i + 1}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: '12px' }}>{b.bond_id}</td>
                        <td style={{ fontWeight: 600 }}>{b.bond_nm}</td>
                        <td>{b.price.toFixed(2)}</td>
                        <td className={b.premium_rt <= 0 ? 'down' : ''}>{b.premium_rt.toFixed(2)}</td>
                        <td style={{ fontWeight: 700, color: b.double_low <= 120 ? '#52c41a' : b.double_low <= 130 ? '#1890ff' : '#faad14' }}>
                          {b.double_low.toFixed(2)}
                        </td>
                        <td style={{ fontWeight: 600, color: b.ytm_rt >= 0 ? '#52c41a' : '#ff4d4f' }}>
                          {b.ytm_rt.toFixed(2)}
                        </td>
                        <td>{b.convert_value.toFixed(1)}</td>
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
                      {expandedRow === b.bond_id && b.quality_scores && (
                        <tr key={`${b.bond_id}-detail`} style={{ background: 'var(--bg-secondary)' }}>
                          <td colSpan={13} style={{ padding: '12px 20px' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                              {Object.entries(b.quality_scores).map(([key, val]) => {
                                const dimNames: Record<string, string> = {
                                  valuation: '双低估值', bond_floor: '债底保护',
                                  credit: '信用质量', convert: '转股潜力', liquidity: '流动性',
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
                            <div style={{ marginTop: '8px', display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                              <span>转股价值: {b.convert_value.toFixed(2)}</span>
                              <span>距强赎距离: {b.redeem_distance.toFixed(1)}%</span>
                              <span>正股PE: {b.stock_pe != null && b.stock_pe > 0 ? b.stock_pe.toFixed(1) : '亏损'}</span>
                              <span>正股PB: {b.stock_pb > 0 ? b.stock_pb.toFixed(2) : '-'}</span>
                              {b.risk_tags && b.risk_tags.length > 0 && (
                                <span style={{ color: '#ff4d4f' }}>
                                  风险: {b.risk_tags.map(t => t.desc).join('; ')}
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                  {filteredAndSortedBonds.length === 0 && (
                    <tr>
                      <td colSpan={13} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        {searchText ? '无匹配结果，请调整搜索条件' : '暂无符合条件的可转债'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ====== Tab: Compare ====== */}
      {activeTab === 'compare' && (
        <>
          {/* Risk-Return scatter chart */}
          {riskReturnChart && (
            <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '10px', padding: '16px', marginBottom: '16px' }}>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                风险-收益定位图
              </div>
              <ReactECharts option={riskReturnChart} style={{ height: 320 }} notMerge />
            </div>
          )}

          {/* Strategy comparison table (dynamic) */}
          <div className="arb-notes" style={{ marginBottom: '16px' }}>
            <h3>策略对比一览</h3>
            <div className="table-container">
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>大师</th>
                    <th>风险等级</th>
                    <th>复杂度</th>
                    <th>最低资金</th>
                    <th>预期年化</th>
                    <th>核心哲学</th>
                  </tr>
                </thead>
                <tbody>
                  {STRATEGY_KEYS.filter(k => strategies[k]).map((key) => {
                    const s = strategies[key]
                    const meta = STRATEGY_META[key]
                    const isActive = activeStrategy === key
                    return (
                      <tr key={key}
                        onClick={() => { setActiveStrategy(key); setActiveTab('screening'); loadStrategy(key) }}
                        style={{
                          background: isActive ? `${meta.color}08` : undefined,
                          cursor: 'pointer',
                        }}>
                        <td style={{ fontWeight: isActive ? 700 : 400 }}>
                          {meta.icon} {s.name}
                        </td>
                        <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{s.master}</td>
                        <td>
                          <span style={{
                            padding: '2px 8px', borderRadius: '8px', fontSize: '11px',
                            background: s.risk_level === '低' ? '#52c41a15' : s.risk_level === '中' ? '#faad1415' : '#ff4d4f15',
                            color: s.risk_level === '低' ? '#52c41a' : s.risk_level === '中' ? '#faad14' : '#ff4d4f',
                          }}>
                            {s.risk_level}
                          </span>
                        </td>
                        <td>{s.complexity}</td>
                        <td>{s.min_capital}</td>
                        <td style={{ fontWeight: 600 }}>{s.expected_return}</td>
                        <td style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '200px' }}>{s.philosophy}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Difficulty ladder */}
          <div className="arb-notes">
            <h3>策略难度阶梯</h3>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', padding: '8px 0' }}>
              {STRATEGY_KEYS
                .filter(k => strategies[k])
                .sort((a, b) => (DIFFICULTY_ORDER[strategies[a]?.complexity] || 3) - (DIFFICULTY_ORDER[strategies[b]?.complexity] || 3))
                .map((key, i) => {
                  const s = strategies[key]
                  const meta = STRATEGY_META[key]
                  return (
                    <div key={key} style={{
                      display: 'flex', alignItems: 'center', gap: '8px',
                      padding: '8px 14px', borderRadius: '8px',
                      background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                    }}>
                      <span style={{ fontSize: '18px' }}>{meta.icon}</span>
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: 600 }}>{s.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{s.complexity} · {s.risk_level}风险</div>
                      </div>
                      <span style={{
                        fontSize: '10px', padding: '1px 6px', borderRadius: '6px',
                        background: `${meta.color}20`, color: meta.color, fontWeight: 600,
                      }}>
                        Lv.{i + 1}
                      </span>
                    </div>
                  )
                })}
            </div>
          </div>
        </>
      )}

      {/* ====== Tab: Insights ====== */}
      {activeTab === 'insights' && (
        <div className="arb-notes">
          <h3>可转债投资大师共识</h3>
          <div className="arb-notes-content">
            <div className="arb-risk-section">
              <h4>核心共识</h4>
              <ul>
                <li><strong>下有保底，上不封顶</strong> -- 所有大师都认同的可转债本质</li>
                <li><strong>分散是免费的午餐</strong> -- 安道全、摊大饼都强调分散持仓</li>
                <li><strong>纪律大于判断</strong> -- 严格执行买入/卖出规则，不追涨杀跌</li>
                <li><strong>安全边际第一</strong> -- 宁稳：到期收益率 {'>'} 0 是底线</li>
              </ul>
            </div>
            <div className="arb-risk-section">
              <h4>2024年后的新共识</h4>
              <ul>
                <li><strong>信用分析不再是可选项</strong> -- 搜特转债首例违约打破"零违约"信仰</li>
                <li><strong>评级AA是安全底线</strong> -- 低于AA需格外谨慎</li>
                <li><strong>纯低价策略失效</strong> -- 需结合YTM、信用质量综合判断</li>
                <li><strong>关注公司促转股动机</strong> -- 下修/强赎博弈是超额收益来源</li>
              </ul>
            </div>
            <div className="arb-risk-section">
              <h4>策略选择指南</h4>
              <ul>
                <li><strong>新手入门</strong> -- 安道全面值策略（规则极简，105元以下买入，130卖出）</li>
                <li><strong>稳健进阶</strong> -- 双低策略（经典量化，长期年化10-15%）</li>
                <li><strong>懒人投资</strong> -- 摊大饼策略（等权持有一篮子低价转债）</li>
                <li><strong>极度保守</strong> -- YTM保本策略（到期收益率为正，持有到期不亏）</li>
                <li><strong>弹性追求</strong> -- 三低策略（低价格+低溢价+低规模，弹性最大）</li>
                <li><strong>套利机会</strong> -- 负溢价套利（溢价率为负时转股套利）</li>
                <li><strong>博弈进阶</strong> -- 下修/强赎博弈（需对正股和公司行为有判断力）</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Backtest panel */}
      {showBacktestPanel && (
        <div style={{
          marginTop: '16px', padding: '16px', borderRadius: '10px',
          background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0 }}>策略回测入口</h3>
            <button onClick={() => setShowBacktestPanel(false)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '18px' }}>
              x
            </button>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            使用真实历史K线数据（AKShare），验证大师策略的历史表现。支持单策略回测和多策略对比。
          </p>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button onClick={() => (window as any).__navigateTo?.('cbBacktest')} style={{
              padding: '8px 20px', borderRadius: '6px', border: 'none', cursor: 'pointer',
              background: '#722ed1', color: '#fff', fontSize: '14px', fontWeight: 600,
            }}>
              进入回测页面
            </button>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', alignSelf: 'center' }}>
              含佣金+滑点模拟 | 收益归因 | 基准对比（中证转债指数）
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
