import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface REIT {
  code: string
  name: string
  asset_type: string
  price: number
  change_pct: number
  daily_turnover: number
  dividend_yield: number
  p_nav: number
  occupancy_rate: number
  debt_ratio: number
  score: number
  risk_level: string
  risk_notes: string[]
}

interface RiskGuide {
  title: string
  description: string
  solution: string
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
  const [assetTypes, setAssetTypes] = useState<string[]>([])
  const [riskGuide, setRiskGuide] = useState<RiskGuide[]>([])
  const [showRiskGuide, setShowRiskGuide] = useState(false)

  const [filters, setFilters] = useState<Filters>({
    min_dividend_yield: 5,
    max_p_nav: 1.2,
    min_occupancy: 85,
    max_debt_ratio: 50,
    min_turnover: 100,
    asset_type: 'all',
  })

  // 加载资产类型
  const loadAssetTypes = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/types`)
      setAssetTypes(res.data.types || [])
    } catch (e) {
      console.error('获取资产类型失败:', e)
    }
  }, [])

  // 加载风险指南
  const loadRiskGuide = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/reit/risk-guide`)
      setRiskGuide(res.data.risks || [])
    } catch (e) {
      console.error('获取风险指南失败:', e)
    }
  }, [])

  // 加载筛选数据
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

  useEffect(() => { loadAssetTypes() }, [loadAssetTypes])
  useEffect(() => { loadRiskGuide() }, [loadRiskGuide])
  useEffect(() => { loadReits() }, [loadReits])

  // 获取评分颜色
  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 60) return '#1890ff'
    if (score >= 40) return '#faad14'
    return '#ff4d4f'
  }

  // 获取风险等级颜色
  const getRiskColor = (level: string) => {
    if (level === '低') return '#52c41a'
    if (level === '中低') return '#1890ff'
    if (level === '中') return '#faad14'
    return '#ff4d4f'
  }

  return (
    <div className="reit-page">
      {/* 页面标题 */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>REIT高分红筛选器</h2>
            <span className="stock-code">分红率≥5% · 规避投资陷阱 · 中国公募REITs</span>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn-add" onClick={loadReits}>刷新数据</button>
            <button
              className="btn-add"
              style={{ background: 'var(--accent-purple)' }}
              onClick={() => setShowRiskGuide(!showRiskGuide)}
            >
              {showRiskGuide ? '关闭风险指南' : '查看风险指南'}
            </button>
          </div>
        </div>
        <div className="data-freshness">
          <span className="freshness-tag">更新时间: {updateTime}</span>
          <span className="freshness-tag">筛选结果: {reits.length} 只</span>
        </div>
      </div>

      {/* 风险指南 */}
      {showRiskGuide && (
        <div className="arb-notes" style={{ marginBottom: '16px' }}>
          <h3>REIT投资风险指南 - 常见踩坑点</h3>
          <div className="arb-notes-grid">
            {riskGuide.map((risk, i) => (
              <div key={i} className="arb-note-item">
                <span className="arb-note-label">{risk.title}</span>
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
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '12px',
          padding: '12px 0',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低分红率(%)</label>
            <input
              type="number"
              value={filters.min_dividend_yield}
              onChange={e => setFilters(prev => ({ ...prev, min_dividend_yield: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>P/NAV上限</label>
            <input
              type="number"
              step="0.1"
              value={filters.max_p_nav}
              onChange={e => setFilters(prev => ({ ...prev, max_p_nav: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低出租率(%)</label>
            <input
              type="number"
              value={filters.min_occupancy}
              onChange={e => setFilters(prev => ({ ...prev, min_occupancy: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最高负债率(%)</label>
            <input
              type="number"
              value={filters.max_debt_ratio}
              onChange={e => setFilters(prev => ({ ...prev, max_debt_ratio: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>最低日均成交额(万)</label>
            <input
              type="number"
              value={filters.min_turnover}
              onChange={e => setFilters(prev => ({ ...prev, min_turnover: Number(e.target.value) }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>资产类型</label>
            <select
              value={filters.asset_type}
              onChange={e => setFilters(prev => ({ ...prev, asset_type: e.target.value }))}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px' }}
            >
              <option value="all">全部</option>
              {assetTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 筛选结果 */}
      {loading ? (
        <div className="loading">
          <div className="spinner"></div>
          加载中...
        </div>
      ) : (
        <div className="table-container">
          <div className="arb-section-title">筛选结果（按评分降序）</div>
          <table className="arb-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>资产类型</th>
                <th>现价</th>
                <th>涨跌幅</th>
                <th>分红率(%)</th>
                <th>P/NAV</th>
                <th>出租率(%)</th>
                <th>负债率(%)</th>
                <th>日均成交额(万)</th>
                <th>评分</th>
                <th>风险等级</th>
              </tr>
            </thead>
            <tbody>
              {reits.map((reit, i) => (
                <tr key={reit.code}>
                  <td>{i + 1}</td>
                  <td>{reit.code}</td>
                  <td style={{ fontWeight: 600 }}>{reit.name}</td>
                  <td>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      background: 'var(--bg-tertiary)',
                    }}>
                      {reit.asset_type}
                    </span>
                  </td>
                  <td>{reit.price.toFixed(3)}</td>
                  <td className={reit.change_pct >= 0 ? 'up' : 'down'}>
                    {reit.change_pct >= 0 ? '+' : ''}{reit.change_pct.toFixed(2)}%
                  </td>
                  <td style={{ fontWeight: 700, color: '#52c41a' }}>
                    {reit.dividend_yield.toFixed(1)}
                  </td>
                  <td style={{ color: reit.p_nav <= 1 ? '#52c41a' : '#faad14' }}>
                    {reit.p_nav.toFixed(2)}
                  </td>
                  <td>{reit.occupancy_rate.toFixed(0)}</td>
                  <td>{reit.debt_ratio.toFixed(0)}</td>
                  <td>{reit.daily_turnover.toFixed(0)}</td>
                  <td>
                    <span style={{
                      fontWeight: 700,
                      color: getScoreColor(reit.score),
                      fontSize: '16px',
                    }}>
                      {reit.score}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: getRiskColor(reit.risk_level) }}>
                      {reit.risk_level}
                    </span>
                  </td>
                </tr>
              ))}
              {reits.length === 0 && (
                <tr>
                  <td colSpan={13} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    暂无符合条件的REIT
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 风险提示 */}
      <div className="arb-notes" style={{ marginTop: '16px' }}>
        <h3>REIT投资注意事项</h3>
        <div className="arb-notes-content">
          <div className="arb-risk-section">
            <h4>分红相关</h4>
            <ul>
              <li><strong>分红率幻觉</strong>：部分REIT分红包含本金返还，实际收益可能低于账面分红率</li>
              <li><strong>分红稳定性</strong>：关注底层资产现金流是否稳定，分红是否可持续</li>
              <li><strong>税收影响</strong>：REIT分红需缴纳个人所得税，实际到手收益会减少</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>估值相关</h4>
            <ul>
              <li><strong>溢价风险</strong>：新上市REIT可能存在溢价炒作，建议等待价格回归理性</li>
              <li><strong>P/NAV解读</strong>：P/NAV{'<'}1表示折价交易，{'>'}1表示溢价交易</li>
              <li><strong>利率影响</strong>：利率上行时，REIT吸引力下降，估值承压</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>流动性相关</h4>
            <ul>
              <li><strong>成交量</strong>：日均成交额过低的REIT难以按预期价格卖出</li>
              <li><strong>解禁压力</strong>：战略配售份额解禁后可能集中抛售，压制价格</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>底层资产</h4>
            <ul>
              <li><strong>经营期限</strong>：高速公路类REIT有经营期限，到期后资产无偿移交</li>
              <li><strong>出租率</strong>：关注出租率变化趋势，下降可能预示运营恶化</li>
              <li><strong>资产类型</strong>：不同资产类型风险差异大，需针对性分析</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
