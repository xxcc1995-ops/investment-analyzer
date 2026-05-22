import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface IndexData {
  code: string
  name: string
  category: string
  pe: number | null
  pe_percentile: number | null
  pb: number | null
  pb_percentile: number | null
  roe: number | null
  dividend_yield: number | null
  dividend_percentile: number | null
  fund_code: string
  fund_name: string | null
  fund_fee: string | null
  fund_holdings_url: string
}

export default function IndexValuation() {
  const [activeTab, setActiveTab] = useState<'宽基' | '红利'>('宽基')
  const [indices, setIndices] = useState<IndexData[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')

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

  const filteredIndices = indices.filter(idx => idx.category === activeTab)

  const getPercentileColor = (value: number | null) => {
    if (value === null) return 'var(--text-muted)'
    if (value < 30) return 'var(--accent-green)'
    if (value <= 70) return 'var(--text-secondary)'
    return 'var(--accent-red)'
  }

  const getPercentileBg = (value: number | null) => {
    if (value === null) return 'transparent'
    if (value < 30) return 'rgba(63,185,80,0.1)'
    if (value <= 70) return 'transparent'
    return 'rgba(248,81,73,0.1)'
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>指数估值</h2>
            <span className="stock-code">
              主要指数PE、PB、ROE、股息率及历史百分位
              {loading && <span style={{ color: 'var(--accent-blue)', marginLeft: '8px' }}>加载中...</span>}
            </span>
          </div>
          <button className="btn-add" onClick={loadData}>
            刷新数据
          </button>
        </div>
      </div>

      {/* Tab切换 */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 20px',
        borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)',
      }}>
        {(['宽基', '红利'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
          >
            {tab === '宽基' ? '宽基指数' : '红利指数'}
          </button>
        ))}
      </div>

      {/* 表格 */}
      <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>指数</th>
              <th>PE</th>
              <th title="百分位 = 历史中≤当前值的个数 / 历史数据总个数 × 100%（A股取近10年，标普取全量历史）" style={{ cursor: 'help', borderBottom: '2px dashed var(--border-primary)' }}>PE百分位</th>
              <th>PB</th>
              <th title="百分位 = 历史中≤当前值的个数 / 历史数据总个数 × 100%（A股取近10年，标普取全量历史）" style={{ cursor: 'help', borderBottom: '2px dashed var(--border-primary)' }}>PB百分位</th>
              <th>ROE</th>
              <th>股息率</th>
              <th title="百分位 = 历史中≤当前值的个数 / 历史数据总个数 × 100%（仅标普500支持，A股暂无历史数据源）" style={{ cursor: 'help', borderBottom: '2px dashed var(--border-primary)' }}>股息率百分位</th>
              <th style={{ textAlign: 'left' }}>推荐基金</th>
            </tr>
          </thead>
          <tbody>
            {filteredIndices.map(idx => (
              <tr key={idx.code}>
                <td style={{ fontWeight: 600 }}>{idx.name}</td>
                <td>{idx.pe?.toFixed(2) ?? '--'}</td>
                <td style={{
                  color: getPercentileColor(idx.pe_percentile),
                  background: getPercentileBg(idx.pe_percentile),
                  fontWeight: 600,
                }}>
                  {idx.pe_percentile !== null ? `${idx.pe_percentile.toFixed(1)}%` : '--'}
                </td>
                <td>{idx.pb?.toFixed(2) ?? '--'}</td>
                <td style={{
                  color: getPercentileColor(idx.pb_percentile),
                  background: getPercentileBg(idx.pb_percentile),
                  fontWeight: 600,
                }}>
                  {idx.pb_percentile !== null ? `${idx.pb_percentile.toFixed(1)}%` : '--'}
                </td>
                <td>{idx.roe !== null ? `${idx.roe.toFixed(1)}%` : '--'}</td>
                <td>{idx.dividend_yield !== null ? `${idx.dividend_yield.toFixed(2)}%` : '--'}</td>
                <td style={{
                  color: getPercentileColor(idx.dividend_percentile),
                  background: getPercentileBg(idx.dividend_percentile),
                  fontWeight: 600,
                }}>
                  {idx.dividend_percentile !== null ? `${idx.dividend_percentile.toFixed(1)}%` : '--'}
                </td>
                <td>
                  <a
                    href={idx.fund_holdings_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: 'var(--accent-blue)', textDecoration: 'none' }}
                  >
                    {idx.fund_code}
                    {idx.fund_fee && <span style={{ color: 'var(--text-muted)', marginLeft: '4px', fontSize: '11px' }}>({idx.fund_fee})</span>}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredIndices.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            暂无数据
          </div>
        )}
      </div>

      {/* 说明 */}
      <div style={{ padding: '0 20px 20px' }}>
        <div className="info-box">
          <div className="info-box-title">估值指标说明</div>
          <div><strong>PE（市盈率）</strong>：股价/每股收益，越低越便宜。</div>
          <div><strong>PB（市净率）</strong>：股价/每股净资产，越低越便宜。</div>
          <div><strong>ROE（净资产收益率）</strong>：净利润/净资产，越高盈利能力越强。</div>
          <div><strong>股息率</strong>：每股分红/股价，越高分红越多。</div>
          <div style={{ marginTop: '8px', padding: '8px 12px', background: 'rgba(88,166,255,0.08)', borderRadius: '6px', border: '1px solid rgba(88,166,255,0.15)' }}>
            <div style={{ fontWeight: 600, color: 'var(--accent-blue)', marginBottom: '4px' }}>百分位计算方式</div>
            <div><strong>公式</strong>：百分位 = (历史中小于等于当前值的个数 / 历史数据总个数) × 100%</div>
            <div><strong>PE/PB历史数据</strong>：A股指数取近10年，标普500取multpl.com全量历史数据</div>
            <div><strong>股息率百分位</strong>：仅标普500有历史数据支持（来源multpl.com），A股指数因数据源限制暂无股息率历史百分位</div>
          </div>
          <div style={{ marginTop: '8px' }}>
            <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>绿色</span> = 低估（百分位&lt;30%），
            <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>灰色</span> = 合理（30-70%），
            <span style={{ color: 'var(--accent-red)', fontWeight: 600 }}>红色</span> = 高估（&gt;70%）
          </div>
          <div style={{ marginTop: '8px', color: 'var(--text-muted)' }}>
            数据来源：中证指数、multpl.com、乐咕乐股 | 更新时间：{updateTime}
          </div>
        </div>
      </div>
    </div>
  )
}
