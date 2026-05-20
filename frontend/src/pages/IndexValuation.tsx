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

  // 过滤当前tab的数据
  const filteredIndices = indices.filter(idx => idx.category === activeTab)

  // 获取百分位颜色
  const getPercentileColor = (value: number | null) => {
    if (value === null) return '#999'
    if (value < 30) return '#3f8600' // 绿色 - 低估
    if (value <= 70) return '#666'   // 灰色 - 合理
    return '#cf1322'                 // 红色 - 高估
  }

  // 获取百分位背景色
  const getPercentileBg = (value: number | null) => {
    if (value === null) return 'transparent'
    if (value < 30) return '#f6ffed'
    if (value <= 70) return '#f5f5f5'
    return '#fff2f0'
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>指数估值</h2>
            <span className="stock-code">
              主要指数PE、PB、ROE、股息率及历史百分位
              {loading && <span style={{ color: '#1890ff', marginLeft: '8px' }}>加载中...</span>}
            </span>
          </div>
          <button
            onClick={loadData}
            style={{
              padding: '8px 16px', background: '#1890ff', color: '#fff',
              border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '13px'
            }}
          >
            刷新数据
          </button>
        </div>
      </div>

      {/* Tab切换 */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 20px',
        borderBottom: '1px solid var(--border)', background: 'var(--bg)',
      }}>
        {(['宽基', '红利'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 20px', borderRadius: '6px',
              border: '1px solid ' + (activeTab === tab ? '#1e3799' : 'var(--border)'),
              background: activeTab === tab ? '#1e3799' : '#fff',
              color: activeTab === tab ? '#fff' : '#333',
              cursor: 'pointer', fontSize: '13px', fontWeight: activeTab === tab ? 600 : 400,
            }}
          >
            {tab === '宽基' ? '宽基指数' : '红利指数'}
          </button>
        ))}
      </div>

      {/* 表格 */}
      <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border)' }}>
              <th style={{ textAlign: 'left', padding: '10px 8px', color: '#666', fontWeight: 600 }}>指数</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>PE</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>PE百分位</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>PB</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>PB百分位</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>ROE</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>股息率</th>
              <th style={{ textAlign: 'right', padding: '10px 8px', color: '#666', fontWeight: 600 }}>股息率百分位</th>
              <th style={{ textAlign: 'left', padding: '10px 8px', color: '#666', fontWeight: 600 }}>推荐基金</th>
            </tr>
          </thead>
          <tbody>
            {filteredIndices.map(idx => (
              <tr key={idx.code} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '12px 8px', fontWeight: 600 }}>{idx.name}</td>
                <td style={{ textAlign: 'right', padding: '12px 8px' }}>
                  {idx.pe?.toFixed(2) ?? '--'}
                </td>
                <td style={{
                  textAlign: 'right', padding: '12px 8px',
                  color: getPercentileColor(idx.pe_percentile),
                  background: getPercentileBg(idx.pe_percentile),
                  fontWeight: 600,
                }}>
                  {idx.pe_percentile !== null ? `${idx.pe_percentile.toFixed(1)}%` : '--'}
                </td>
                <td style={{ textAlign: 'right', padding: '12px 8px' }}>
                  {idx.pb?.toFixed(2) ?? '--'}
                </td>
                <td style={{
                  textAlign: 'right', padding: '12px 8px',
                  color: getPercentileColor(idx.pb_percentile),
                  background: getPercentileBg(idx.pb_percentile),
                  fontWeight: 600,
                }}>
                  {idx.pb_percentile !== null ? `${idx.pb_percentile.toFixed(1)}%` : '--'}
                </td>
                <td style={{ textAlign: 'right', padding: '12px 8px' }}>
                  {idx.roe !== null ? `${idx.roe.toFixed(1)}%` : '--'}
                </td>
                <td style={{ textAlign: 'right', padding: '12px 8px' }}>
                  {idx.dividend_yield !== null ? `${idx.dividend_yield.toFixed(2)}%` : '--'}
                </td>
                <td style={{
                  textAlign: 'right', padding: '12px 8px',
                  color: getPercentileColor(idx.dividend_percentile),
                  background: getPercentileBg(idx.dividend_percentile),
                  fontWeight: 600,
                }}>
                  {idx.dividend_percentile !== null ? `${idx.dividend_percentile.toFixed(1)}%` : '--'}
                </td>
                <td style={{ padding: '12px 8px' }}>
                  <a
                    href={idx.fund_holdings_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#1890ff', textDecoration: 'none' }}
                  >
                    {idx.fund_code}
                    {idx.fund_fee && <span style={{ color: '#999', marginLeft: '4px', fontSize: '11px' }}>({idx.fund_fee})</span>}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredIndices.length === 0 && !loading && (
          <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
            暂无数据
          </div>
        )}
      </div>

      {/* 说明 */}
      <div style={{ padding: '0 20px 20px' }}>
        <div style={{
          background: 'var(--bg)', borderRadius: '8px', padding: '16px',
          fontSize: '12px', color: '#666', lineHeight: '1.8',
        }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: '#333' }}>估值指标说明</div>
          <div><strong>PE（市盈率）</strong>：股价/每股收益，越低越便宜。百分位表示当前PE在历史中的位置。</div>
          <div><strong>PB（市净率）</strong>：股价/每股净资产，越低越便宜。</div>
          <div><strong>ROE（净资产收益率）</strong>：净利润/净资产，越高盈利能力越强。</div>
          <div><strong>股息率</strong>：每股分红/股价，越高分红越多。</div>
          <div style={{ marginTop: '8px' }}>
            <span style={{ color: '#3f8600', fontWeight: 600 }}>绿色</span> = 低估（百分位&lt;30%），
            <span style={{ color: '#666', fontWeight: 600 }}>灰色</span> = 合理（30-70%），
            <span style={{ color: '#cf1322', fontWeight: 600 }}>红色</span> = 高估（&gt;70%）
          </div>
          <div style={{ marginTop: '8px', color: '#999' }}>
            数据来源：中证指数、multpl.com、乐咕乐股 | 更新时间：{updateTime}
          </div>
        </div>
      </div>
    </div>
  )
}
