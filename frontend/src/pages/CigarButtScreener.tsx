import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface CigarButtStock {
  code: string
  name: string
  price: number
  change_pct: number
  pe: number | null
  pb: number | null
  market_cap: number
  dividend_yield: number
  graham_score: number
  buffett_score: number
  schloss_score: number
  score: number
  criteria_met: number
  match_level: 'excellent' | 'good' | 'fair' | 'poor'
}

interface Philosophy {
  graham: {
    name: string
    title: string
    core_idea: string
    criteria: string[]
    net_net_rule: string
    classic_quote: string
  }
  buffett: {
    name: string
    title: string
    core_idea: string
    criteria: string[]
    transition: string
    classic_quote: string
  }
  schloss: {
    name: string
    title: string
    core_idea: string
    criteria: string[]
    performance: string
    classic_quote: string
  }
  risks: string[]
}

export default function CigarButtScreener() {
  const [activeTab, setActiveTab] = useState<'screener' | 'philosophy'>('philosophy')
  const [stocks, setStocks] = useState<CigarButtStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [total, setTotal] = useState(0)

  // 筛选参数
  const [master, setMaster] = useState<'combined' | 'graham' | 'buffett' | 'schloss'>('combined')
  const [minScore, setMinScore] = useState(50)
  const [minMarketCap, setMinMarketCap] = useState(5)
  const [maxPE, setMaxPE] = useState(15)
  const [maxPB, setMaxPB] = useState(1.5)
  const [topN, setTopN] = useState(50)

  // 投资哲学
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)

  // 加载筛选数据
  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/screener`, {
        params: {
          master,
          min_score: minScore,
          min_market_cap: minMarketCap,
          max_pe: maxPE,
          max_pb: maxPB,
          top_n: topN,
        }
      })
      setStocks(res.data.stocks || [])
      setUpdateTime(res.data.update_time || '')
      setTotal(res.data.total || 0)
    } catch (e) {
      console.error('获取烟蒂股数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [master, minScore, minMarketCap, maxPE, maxPB, topN])

  // 加载投资哲学
  const loadPhilosophy = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/philosophy`)
      setPhilosophy(res.data)
    } catch (e) {
      console.error('获取投资哲学失败:', e)
    }
  }, [])

  useEffect(() => { loadPhilosophy() }, [loadPhilosophy])

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 65) return '#1890ff'
    if (score >= 50) return '#faad14'
    return '#ff4d4f'
  }

  const getMatchLevelText = (level: string) => {
    switch (level) {
      case 'excellent': return '优秀'
      case 'good': return '良好'
      case 'fair': return '一般'
      case 'poor': return '较差'
      default: return '-'
    }
  }

  const getMatchLevelColor = (level: string) => {
    switch (level) {
      case 'excellent': return '#52c41a'
      case 'good': return '#1890ff'
      case 'fair': return '#faad14'
      case 'poor': return '#ff4d4f'
      default: return '#666'
    }
  }

  return (
    <div className="cb-page">
      {/* 页面标题 */}
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>港股烟蒂股筛选器</h2>
            <span className="stock-code">
              格雷厄姆 / 巴菲特 / 施洛斯 烟蒂投资策略
            </span>
          </div>
        </div>
      </div>

      {/* Tab切换 */}
      <div style={{
        display: 'flex', gap: '8px', padding: '12px 20px',
        borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)',
      }}>
        {(['philosophy', 'screener'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
          >
            {tab === 'philosophy' ? '烟蒂投资哲学' : '港股烟蒂筛选'}
          </button>
        ))}
      </div>

      {/* 投资哲学页面 */}
      {activeTab === 'philosophy' && philosophy && (
        <div style={{ padding: '20px' }}>
          {/* 三位大师 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px', marginBottom: '20px' }}>
            {/* 格雷厄姆 */}
            <div className="arb-notes" style={{ margin: 0, borderLeft: '3px solid #58a6ff' }}>
              <h3 style={{ color: '#58a6ff', marginBottom: '12px' }}>{philosophy.graham.name}</h3>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                {philosophy.graham.title}
              </div>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心思想</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{philosophy.graham.core_idea}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    {philosophy.graham.criteria.map((c, i) => (
                      <li key={i} style={{ fontSize: '13px' }}>{c}</li>
                    ))}
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>NCAV规则</h4>
                  <p style={{ fontSize: '13px', color: '#58a6ff', fontWeight: 600 }}>{philosophy.graham.net_net_rule}</p>
                </div>
                <div style={{ marginTop: '12px', padding: '8px', background: 'rgba(88,166,255,0.1)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    "{philosophy.graham.classic_quote}"
                  </div>
                </div>
              </div>
            </div>

            {/* 巴菲特 */}
            <div className="arb-notes" style={{ margin: 0, borderLeft: '3px solid #3fb950' }}>
              <h3 style={{ color: '#3fb950', marginBottom: '12px' }}>{philosophy.buffett.name}</h3>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                {philosophy.buffett.title}
              </div>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心思想</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{philosophy.buffett.core_idea}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    {philosophy.buffett.criteria.map((c, i) => (
                      <li key={i} style={{ fontSize: '13px' }}>{c}</li>
                    ))}
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>投资转变</h4>
                  <p style={{ fontSize: '13px', color: '#3fb950' }}>{philosophy.buffett.transition}</p>
                </div>
                <div style={{ marginTop: '12px', padding: '8px', background: 'rgba(63,185,80,0.1)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    "{philosophy.buffett.classic_quote}"
                  </div>
                </div>
              </div>
            </div>

            {/* 施洛斯 */}
            <div className="arb-notes" style={{ margin: 0, borderLeft: '3px solid #d29922' }}>
              <h3 style={{ color: '#d29922', marginBottom: '12px' }}>{philosophy.schloss.name}</h3>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                {philosophy.schloss.title}
              </div>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心思想</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{philosophy.schloss.core_idea}</p>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    {philosophy.schloss.criteria.map((c, i) => (
                      <li key={i} style={{ fontSize: '13px' }}>{c}</li>
                    ))}
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>历史业绩</h4>
                  <p style={{ fontSize: '13px', color: '#d29922', fontWeight: 600 }}>{philosophy.schloss.performance}</p>
                </div>
                <div style={{ marginTop: '12px', padding: '8px', background: 'rgba(210,153,34,0.1)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '12px', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    "{philosophy.schloss.classic_quote}"
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 风险提示 */}
          <div className="arb-notes" style={{ margin: 0 }}>
            <h3 style={{ color: '#f85149' }}>烟蒂投资风险提示</h3>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <h4>主要风险</h4>
                <ul>
                  {philosophy.risks.map((risk, i) => (
                    <li key={i} style={{ fontSize: '13px' }}>{risk}</li>
                  ))}
                </ul>
              </div>
              <div className="arb-risk-section">
                <h4>如何避免价值陷阱</h4>
                <ul>
                  <li>检查公司是否有持续经营能力</li>
                  <li>关注负债率，避免高负债公司</li>
                  <li>查看现金流，确保有正向经营现金流</li>
                  <li>分析行业前景，避免夕阳行业</li>
                  <li>关注管理层是否在增持</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 筛选页面 */}
      {activeTab === 'screener' && (
        <div style={{ padding: '16px 20px' }}>
          {/* 筛选条件 */}
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px',
            padding: '16px', background: 'var(--bg-secondary)', borderRadius: '8px',
            border: '1px solid var(--border-primary)',
          }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                筛选标准
              </label>
              <select
                value={master}
                onChange={e => setMaster(e.target.value as any)}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value="combined">综合标准</option>
                <option value="graham">格雷厄姆</option>
                <option value="buffett">巴菲特</option>
                <option value="schloss">施洛斯</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最低评分
              </label>
              <select
                value={minScore}
                onChange={e => setMinScore(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={40}>40分</option>
                <option value={50}>50分</option>
                <option value={60}>60分</option>
                <option value={70}>70分</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最低市值(亿港元)
              </label>
              <select
                value={minMarketCap}
                onChange={e => setMinMarketCap(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={2}>2亿</option>
                <option value={5}>5亿</option>
                <option value={10}>10亿</option>
                <option value={20}>20亿</option>
                <option value={50}>50亿</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最大PE
              </label>
              <select
                value={maxPE}
                onChange={e => setMaxPE(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={8}>8</option>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最大PB
              </label>
              <select
                value={maxPB}
                onChange={e => setMaxPB(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={0.8}>0.8</option>
                <option value={1.0}>1.0</option>
                <option value={1.2}>1.2</option>
                <option value={1.5}>1.5</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                显示数量
              </label>
              <select
                value={topN}
                onChange={e => setTopN(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={30}>前30只</option>
                <option value={50}>前50只</option>
                <option value={100}>前100只</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                onClick={loadStocks}
                style={{
                  padding: '6px 16px', background: 'var(--accent-blue)', color: '#fff',
                  border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
                }}
              >
                筛选
              </button>
            </div>
          </div>

          {/* 数据信息 */}
          <div className="data-freshness" style={{ marginBottom: '16px' }}>
            <span className="freshness-tag">筛选标准: {master === 'combined' ? '综合' : master === 'graham' ? '格雷厄姆' : master === 'buffett' ? '巴菲特' : '施洛斯'}</span>
            <span className="freshness-tag">更新时间: {updateTime}</span>
            <span className="freshness-tag">符合条件: {total} 只</span>
          </div>

          {/* 筛选结果表格 */}
          {loading ? (
            <div className="loading">
              <div className="spinner"></div>
              加载中...
            </div>
          ) : (
            <div className="table-container">
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>排名</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>现价(HKD)</th>
                    <th>涨跌幅</th>
                    <th>PE</th>
                    <th>PB</th>
                    <th>市值(亿)</th>
                    <th>股息率</th>
                    <th>格雷厄姆</th>
                    <th>巴菲特</th>
                    <th>施洛斯</th>
                    <th>综合评分</th>
                    <th>匹配度</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((stock, i) => (
                    <tr key={stock.code}>
                      <td>{i + 1}</td>
                      <td style={{ fontWeight: 600 }}>{stock.code}</td>
                      <td>{stock.name}</td>
                      <td>{stock.price.toFixed(3)}</td>
                      <td style={{
                        color: stock.change_pct >= 0 ? '#f85149' : '#3fb950',
                      }}>
                        {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                      </td>
                      <td style={{
                        color: (stock.pe ?? 999) <= 8 ? '#52c41a' : (stock.pe ?? 999) <= 10 ? '#1890ff' : '#faad14',
                        fontWeight: 600,
                      }}>
                        {stock.pe?.toFixed(2) ?? '--'}
                      </td>
                      <td style={{
                        color: (stock.pb ?? 999) <= 0.7 ? '#52c41a' : (stock.pb ?? 999) <= 1.0 ? '#1890ff' : '#faad14',
                        fontWeight: 600,
                      }}>
                        {stock.pb?.toFixed(3) ?? '--'}
                      </td>
                      <td>{stock.market_cap.toFixed(1)}</td>
                      <td style={{
                        color: stock.dividend_yield >= 5 ? '#52c41a' : stock.dividend_yield >= 3 ? '#1890ff' : '#faad14',
                      }}>
                        {stock.dividend_yield > 0 ? `${stock.dividend_yield.toFixed(2)}%` : '--'}
                      </td>
                      <td style={{ color: getScoreColor(stock.graham_score), fontWeight: 600 }}>
                        {stock.graham_score}
                      </td>
                      <td style={{ color: getScoreColor(stock.buffett_score), fontWeight: 600 }}>
                        {stock.buffett_score}
                      </td>
                      <td style={{ color: getScoreColor(stock.schloss_score), fontWeight: 600 }}>
                        {stock.schloss_score}
                      </td>
                      <td>
                        <span style={{
                          color: getScoreColor(stock.score),
                          fontWeight: 700,
                          fontSize: '15px',
                        }}>
                          {stock.score}
                        </span>
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: 600,
                          background: `${getMatchLevelColor(stock.match_level)}20`,
                          color: getMatchLevelColor(stock.match_level),
                        }}>
                          {getMatchLevelText(stock.match_level)}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {stocks.length === 0 && (
                    <tr>
                      <td colSpan={14} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        暂无符合条件的烟蒂股
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* 评分说明 */}
          <div className="arb-notes" style={{ marginTop: '16px' }}>
            <h3>评分标准说明</h3>
            <div className="arb-notes-grid">
              <div className="arb-note-item">
                <span className="arb-note-label">格雷厄姆</span>
                <span className="arb-note-value">PB&lt;1为核心</span>
                <span className="arb-note-desc">PE&lt;10(25分) + PB&lt;1(30分) + 股息(20分) + 市值(15分) + 盈利(10分)</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">巴菲特</span>
                <span className="arb-note-value">净营运资本2/3</span>
                <span className="arb-note-desc">PE&lt;10(25分) + PB&lt;1.2(25分) + 盈利(20分) + 股息(15分) + 市值(15分)</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">施洛斯</span>
                <span className="arb-note-value">PB&lt;1绝对核心</span>
                <span className="arb-note-desc">PB&lt;1(35分) + PE&lt;10(25分) + 股息(20分) + 市值(20分)</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">综合评分</span>
                <span className="arb-note-value">加权平均</span>
                <span className="arb-note-desc">格雷厄姆40% + 巴菲特30% + 施洛斯30%</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
