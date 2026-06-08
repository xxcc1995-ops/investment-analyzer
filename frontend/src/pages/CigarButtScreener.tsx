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
  roe: number | null
  market_cap: number
  dividend_yield: number
  criteria_met: string[]
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

  // 筛选参数 - 基于大师烟蒂逻辑的核心指标
  const [maxPE, setMaxPE] = useState(10)
  const [maxPB, setMaxPB] = useState(1.0)
  const [minROE, setMinROE] = useState(8)
  const [minDividend, setMinDividend] = useState(3)
  const [minMarketCap, setMinMarketCap] = useState(10)
  const [topN, setTopN] = useState(50)

  // 投资哲学
  const [philosophy, setPhilosophy] = useState<Philosophy | null>(null)

  // 加载筛选数据
  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/cigar-butt/screener`, {
        params: {
          max_pe: maxPE,
          max_pb: maxPB,
          min_roe: minROE,
          min_dividend: minDividend,
          min_market_cap: minMarketCap,
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
  }, [maxPE, maxPB, minROE, minDividend, minMarketCap, topN])

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

  const getROEColor = (roe: number | null) => {
    if (!roe) return '#666'
    if (roe >= 15) return '#52c41a'
    if (roe >= 10) return '#1890ff'
    if (roe >= 8) return '#faad14'
    return '#ff4d4f'
  }

  const getDividendColor = (dividend: number) => {
    if (dividend >= 5) return '#52c41a'
    if (dividend >= 3) return '#1890ff'
    return '#faad14'
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
                <option value={5}>5</option>
                <option value={8}>8</option>
                <option value={10}>10（大师标准）</option>
                <option value={12}>12</option>
                <option value={15}>15</option>
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
                <option value={0.5}>0.5（深度折扣）</option>
                <option value={0.7}>0.7</option>
                <option value={0.8}>0.8</option>
                <option value={1.0}>1.0（大师标准）</option>
                <option value={1.2}>1.2</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最低ROE(%)
              </label>
              <select
                value={minROE}
                onChange={e => setMinROE(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={5}>5%</option>
                <option value={8}>8%</option>
                <option value={10}>10%</option>
                <option value={12}>12%</option>
                <option value={15}>15%</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最低股息率(%)
              </label>
              <select
                value={minDividend}
                onChange={e => setMinDividend(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={0}>不限</option>
                <option value={1}>1%</option>
                <option value={2}>2%</option>
                <option value={3}>3%</option>
                <option value={5}>5%</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                最低市值(亿)
              </label>
              <select
                value={minMarketCap}
                onChange={e => setMinMarketCap(Number(e.target.value))}
                style={{
                  padding: '6px 12px', border: '1px solid var(--border-primary)',
                  borderRadius: '4px', background: 'var(--bg-primary)', color: 'var(--text-primary)',
                }}
              >
                <option value={5}>5亿</option>
                <option value={10}>10亿</option>
                <option value={20}>20亿</option>
                <option value={50}>50亿</option>
                <option value={100}>100亿</option>
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
                <option value={200}>前200只</option>
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

          {/* 大师烟蒂标准说明 */}
          <div className="arb-notes" style={{ marginBottom: '16px', padding: '12px' }}>
            <h4 style={{ marginBottom: '8px', color: 'var(--accent-blue)' }}>大师烟蒂选股标准</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', fontSize: '13px' }}>
              <div>
                <strong>格雷厄姆：</strong>PE &lt; 10, PB &lt; 1, 连续分红, 流动比率 &gt; 2
              </div>
              <div>
                <strong>巴菲特(早期)：</strong>PE &lt; 10, PB &lt; 1.2, 价格 &lt; 净营运资本2/3
              </div>
              <div>
                <strong>施洛斯：</strong>PB &lt; 1(核心), PE &lt; 10, 负债少, 长期盈利
              </div>
            </div>
          </div>

          {/* 数据信息 */}
          <div className="data-freshness" style={{ marginBottom: '16px' }}>
            <span className="freshness-tag">筛选条件: PE≤{maxPE} | PB≤{maxPB} | ROE≥{minROE}% | 股息≥{minDividend}%</span>
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
                    <th>ROE</th>
                    <th>市值(亿)</th>
                    <th>股息率</th>
                    <th>符合标准</th>
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
                      <td style={{
                        color: getROEColor(stock.roe),
                        fontWeight: 600,
                      }}>
                        {stock.roe ? `${stock.roe.toFixed(1)}%` : '--'}
                      </td>
                      <td>{stock.market_cap.toFixed(1)}</td>
                      <td style={{
                        color: getDividendColor(stock.dividend_yield),
                        fontWeight: 600,
                      }}>
                        {stock.dividend_yield > 0 ? `${stock.dividend_yield.toFixed(2)}%` : '--'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {stock.criteria_met.map((criteria, idx) => (
                            <span key={idx} style={{
                              display: 'inline-block',
                              padding: '1px 6px',
                              borderRadius: '3px',
                              fontSize: '11px',
                              background: 'rgba(88, 166, 255, 0.15)',
                              color: '#58a6ff',
                            }}>
                              {criteria}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {stocks.length === 0 && (
                    <tr>
                      <td colSpan={11} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        暂无符合条件的烟蒂股
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* 筛选逻辑说明 */}
          <div className="arb-notes" style={{ marginTop: '16px' }}>
            <h3>筛选逻辑说明</h3>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <h4>核心指标</h4>
                <ul>
                  <li><strong>PE（市盈率）</strong>：越低越好，大师标准 PE &lt; 10</li>
                  <li><strong>PB（市净率）</strong>：越低越好，大师标准 PB &lt; 1（打7折买净资产）</li>
                  <li><strong>ROE（净资产收益率）</strong>：越高越好，代表盈利能力</li>
                  <li><strong>股息率</strong>：越高越好，代表分红能力和股东回报</li>
                </ul>
              </div>
              <div className="arb-risk-section">
                <h4>符合标准标签说明</h4>
                <ul>
                  <li><strong>PE低估</strong>：PE ≤ 设定阈值</li>
                  <li><strong>PB低估</strong>：PB ≤ 设定阈值</li>
                  <li><strong>高ROE</strong>：ROE ≥ 设定阈值</li>
                  <li><strong>高股息</strong>：股息率 ≥ 设定阈值</li>
                  <li><strong>大市值</strong>：市值 ≥ 50亿</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
