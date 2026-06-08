import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface FundEst {
  fund_code: string
  fund_name: string
  fund_price: number
  fund_change_pct: number
  underlying_code: string
  underlying_price: number
  est_nav: number
  premium: number
  official_nav: number
  official_nav_date: string
  position: number
  usdcny_rate: number
  update_time: string
}

export default function FundEstPage() {
  const [funds, setFunds] = useState<FundEst[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [usdcnyRate, setUsdcnyRate] = useState(0)
  const [sortBy, setSortBy] = useState<'premium' | 'code'>('premium')
  const [filterMinPremium, setFilterMinPremium] = useState(-10)
  const [filterMaxPremium, setFilterMaxPremium] = useState(50)

  // 加载EST数据
  const loadEstData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/fund-est/est-list`)
      setFunds(res.data.funds || [])
      setUpdateTime(res.data.update_time || '')
      setUsdcnyRate(res.data.usdcny_rate || 0)
    } catch (e) {
      console.error('获取EST数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadEstData() }, [loadEstData])

  // 过滤和排序
  const filteredFunds = funds
    .filter(f => f.premium >= filterMinPremium && f.premium <= filterMaxPremium)
    .sort((a, b) => {
      if (sortBy === 'premium') return b.premium - a.premium
      return a.fund_code.localeCompare(b.fund_code)
    })

  const getPremiumColor = (premium: number) => {
    if (premium > 5) return '#f85149'
    if (premium > 2) return '#faad14'
    if (premium > -2) return '#666'
    if (premium > -5) return '#1890ff'
    return '#52c41a'
  }

  const getPremiumBg = (premium: number) => {
    if (premium > 10) return 'rgba(248, 81, 73, 0.15)'
    if (premium > 5) return 'rgba(250, 173, 20, 0.15)'
    if (premium < -5) return 'rgba(82, 196, 26, 0.15)'
    return 'transparent'
  }

  return (
    <div className="fund-est-page">
      {/* 页面标题 */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>LOF基金EST净值估算</h2>
            <span className="stock-code">
              基于Palmmicro技术方案 - 实时估算QDII LOF基金净值
            </span>
          </div>
        </div>
      </div>

      {/* 说明区域 */}
      <div className="arb-notes" style={{ margin: '16px 20px' }}>
        <h3>EST净值估算原理</h3>
        <div className="arb-notes-content">
          <div className="arb-risk-section">
            <h4>数据来源</h4>
            <ul>
              <li><strong>基金实时价格</strong>：新浪财经API</li>
              <li><strong>底层资产价格</strong>：美股ETF（QQQ、SPY等）、期货、港股指数</li>
              <li><strong>汇率数据</strong>：美元人民币中间价（中国外汇交易中心）</li>
              <li><strong>基金净值</strong>：东方财富（T-1或T-2日，见净值日期列）</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>计算公式</h4>
            <p style={{ fontFamily: 'monospace', fontSize: '14px', color: 'var(--accent-blue)' }}>
              EST净值 = 底层资产价格 × 汇率 × 仓位比例 × 校准值
            </p>
          </div>
          <div className="arb-risk-section">
            <h4>净值日期说明</h4>
            <ul>
              <li><strong>净值日期</strong>：场外基金官方净值的公布日期</li>
              <li><strong>交易日</strong>：通常为T-1日（如周五公布周四的净值）</li>
              <li><strong>非交易日</strong>：周末和节假日会延迟公布</li>
              <li><strong>QDII基金</strong>：由于涉及跨境资产，净值公布可能延迟至T-2</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>溢价率含义</h4>
            <ul>
              <li><strong>正溢价（红色）</strong>：场内价格高于估算净值，申购可能获利</li>
              <li><strong>负溢价（绿色）</strong>：场内价格低于估算净值，赎回可能获利</li>
              <li><strong>套利机会</strong>：溢价率超过2%或低于-2%时值得关注</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 筛选条件 */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '12px', margin: '16px 20px',
        padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
        border: '1px solid var(--border-primary)',
      }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            排序方式
          </label>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as any)}
            style={{
              padding: '6px 12px', border: '1px solid var(--border-primary)',
              borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
            }}
          >
            <option value="premium">按溢价率排序</option>
            <option value="code">按基金代码排序</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            最低溢价率(%)
          </label>
          <select
            value={filterMinPremium}
            onChange={e => setFilterMinPremium(Number(e.target.value))}
            style={{
              padding: '6px 12px', border: '1px solid var(--border-primary)',
              borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
            }}
          >
            <option value={-10}>-10%</option>
            <option value={-5}>-5%</option>
            <option value={-2}>-2%</option>
            <option value={0}>0%</option>
            <option value={2}>2%</option>
            <option value={5}>5%</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            最高溢价率(%)
          </label>
          <select
            value={filterMaxPremium}
            onChange={e => setFilterMaxPremium(Number(e.target.value))}
            style={{
              padding: '6px 12px', border: '1px solid var(--border-primary)',
              borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
            }}
          >
            <option value={10}>10%</option>
            <option value={20}>20%</option>
            <option value={50}>50%</option>
            <option value={100}>100%</option>
          </select>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button
            onClick={loadEstData}
            style={{
              padding: '6px 16px', background: 'var(--accent-blue)', color: '#fff',
              border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
            }}
          >
            刷新数据
          </button>
        </div>
      </div>

      {/* 数据信息 */}
      <div className="data-freshness" style={{ margin: '0 20px 16px' }}>
        <span className="freshness-tag">更新时间: {updateTime}</span>
        <span className="freshness-tag">美元人民币中间价: {usdcnyRate.toFixed(4)}</span>
        <span className="freshness-tag">基金数量: {filteredFunds.length}</span>
        <span className="freshness-tag">
          场外净值日期: {(() => {
            const dates = filteredFunds.map(f => f.official_nav_date).filter(d => d)
            if (dates.length === 0) return '无数据'
            const uniqueDates = [...new Set(dates)].sort()
            return uniqueDates.length === 1 ? uniqueDates[0] : `${uniqueDates[0]} ~ ${uniqueDates[uniqueDates.length - 1]}`
          })()}
        </span>
      </div>

      {/* 数据表格 */}
      {loading ? (
        <div className="loading">
          <div className="spinner"></div>
          加载中...
        </div>
      ) : (
        <div className="table-container" style={{ margin: '0 20px' }}>
          <table className="arb-table">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>场内价格</th>
                <th>涨跌幅</th>
                <th>底层资产</th>
                <th>底层价格</th>
                <th>EST净值</th>
                <th>溢价率</th>
                <th>官方净值(日期)</th>
              </tr>
            </thead>
            <tbody>
              {filteredFunds.map((fund) => (
                <tr key={fund.fund_code} style={{ background: getPremiumBg(fund.premium) }}>
                  <td style={{ fontWeight: 600 }}>{fund.fund_code}</td>
                  <td>{fund.fund_name}</td>
                  <td style={{ fontWeight: 600 }}>{fund.fund_price.toFixed(3)}</td>
                  <td style={{
                    color: fund.fund_change_pct >= 0 ? '#f85149' : '#3fb950',
                  }}>
                    {fund.fund_change_pct >= 0 ? '+' : ''}{fund.fund_change_pct.toFixed(2)}%
                  </td>
                  <td style={{ fontSize: '12px' }}>{fund.underlying_code}</td>
                  <td>{fund.underlying_price.toFixed(2)}</td>
                  <td style={{ fontWeight: 600, color: 'var(--accent-blue)' }}>
                    {fund.est_nav.toFixed(4)}
                  </td>
                  <td style={{
                    color: getPremiumColor(fund.premium),
                    fontWeight: 700,
                    fontSize: '15px',
                  }}>
                    {fund.premium > 0 ? '+' : ''}{fund.premium.toFixed(2)}%
                  </td>
                  <td>
                    <div>{fund.official_nav.toFixed(4)}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {fund.official_nav_date || '无数据'}
                    </div>
                  </td>
                </tr>
              ))}
              {filteredFunds.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    暂无符合条件的基金数据
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 套利策略说明 */}
      <div className="arb-notes" style={{ margin: '16px 20px' }}>
        <h3>LOF基金套利策略</h3>
        <div className="arb-notes-grid">
          <div className="arb-note-item">
            <span className="arb-note-label">溢价套利</span>
            <span className="arb-note-value">场内价格 {'>'} EST净值</span>
            <span className="arb-note-desc">
              1. 场内卖出基金份额
              2. 同时申购等量基金
              3. 等待T+2日份额到账
              4. 赚取溢价差价
            </span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">折价套利</span>
            <span className="arb-note-value">场内价格 {'<'} EST净值</span>
            <span className="arb-note-desc">
              1. 场内买入基金份额
              2. 同时赎回等量基金
              3. 等待T+2日资金到账
              4. 赚取折价差价
            </span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">注意事项</span>
            <span className="arb-note-value">风险提示</span>
            <span className="arb-note-desc">
              1. EST净值是估算值，可能有误差
              2. 基金申购赎回有手续费
              3. 跨境QDII基金有汇率风险
              4. 套利需要足够的资金和份额
            </span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">数据来源</span>
            <span className="arb-note-value">Palmmicro技术方案</span>
            <span className="arb-note-desc">
              1. 底层资产：新浪财经实时数据
              2. 汇率：中国外汇交易中心中间价
              3. 基金净值：东方财富T-1日数据
              4. 计算公式：底层价格 × 汇率 × 仓位
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
