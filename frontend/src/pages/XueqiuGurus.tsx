import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api/xueqiu'

interface Principle {
  title: string
  icon: string
  detail: string
}

interface StockSelection {
  title: string
  criteria: string[]
}

interface PositionMgmt {
  title: string
  rules: string[]
}

interface TypicalStock {
  code: string
  name: string
  reason: string
}

interface GuruData {
  uid: string
  name: string
  tagline: string
  style: string
  followers: string
  years: string
  avatar_color: string
  core_philosophy: string
  principles: Principle[]
  stock_selection: StockSelection
  position_mgmt: PositionMgmt
  quotes: string[]
  typical_stocks: TypicalStock[]
  suitable_for: string
}

export default function XueqiuGurus() {
  const [gurus, setGurus] = useState<GuruData[]>([])
  const [activeTab, setActiveTab] = useState(0)
  const [loading, setLoading] = useState(false)
  const [expandedPrinciple, setExpandedPrinciple] = useState<number | null>(null)

  const loadGurus = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/gurus`)
      setGurus(res.data)
    } catch (e) {
      console.error('Failed to load gurus:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadGurus() }, [loadGurus])

  const current = gurus[activeTab]

  return (
    <div className="cb-page">
      <div className="stock-header">
        <h2>大V投资理念</h2>
        <p style={{ color: '#999', margin: '4px 0 0' }}>
          学习顶尖投资者的选股逻辑和交易哲学
        </p>
      </div>

      {loading && gurus.length === 0 && (
        <p style={{ color: '#999', textAlign: 'center', padding: 40 }}>加载中...</p>
      )}

      {gurus.length > 0 && (
        <>
          {/* Guru Tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            {gurus.map((g, i) => (
              <button
                key={g.uid}
                className={`tab-btn ${activeTab === i ? 'active' : ''}`}
                onClick={() => { setActiveTab(i); setExpandedPrinciple(null) }}
              >
                {g.name}
              </button>
            ))}
          </div>

          {current && (
            <div>
              {/* Hero Card */}
              <div style={{
                background: `linear-gradient(135deg, ${current.avatar_color}15 0%, #1a1a2e 60%)`,
                padding: 24,
                borderRadius: 12,
                border: `1px solid ${current.avatar_color}40`,
                marginBottom: 20,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                      <div style={{
                        width: 48, height: 48, borderRadius: '50%',
                        background: current.avatar_color,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 20, fontWeight: 700, color: '#fff',
                      }}>
                        {current.name[0]}
                      </div>
                      <div>
                        <h3 style={{ color: '#fff', margin: 0, fontSize: 20 }}>{current.name}</h3>
                        <span style={{ color: current.avatar_color, fontSize: 13 }}>{current.tagline}</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontSize: 13 }}>
                    <p style={{ color: '#999', margin: '2px 0' }}>粉丝 <span style={{ color: '#d4a76a', fontWeight: 600 }}>{current.followers}</span></p>
                    <p style={{ color: '#999', margin: '2px 0' }}>投资经验 <span style={{ color: '#ccc' }}>{current.years}</span></p>
                  </div>
                </div>
                <div style={{
                  marginTop: 16, padding: '12px 16px',
                  background: 'rgba(0,0,0,0.3)', borderRadius: 8,
                  borderLeft: `3px solid ${current.avatar_color}`,
                }}>
                  <p style={{ color: '#ddd', fontSize: 14, lineHeight: 1.8, margin: 0, fontStyle: 'italic' }}>
                    "{current.core_philosophy}"
                  </p>
                </div>
              </div>

              {/* Investment Principles */}
              <div style={{ marginBottom: 20 }}>
                <h4 style={{ color: '#d4a76a', marginBottom: 14, fontSize: 16 }}>
                  核心投资原则
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12 }}>
                  {current.principles.map((p, i) => (
                    <div
                      key={i}
                      onClick={() => setExpandedPrinciple(expandedPrinciple === i ? null : i)}
                      style={{
                        background: expandedPrinciple === i ? '#1a1a2e' : '#151525',
                        padding: 16,
                        borderRadius: 8,
                        border: `1px solid ${expandedPrinciple === i ? current.avatar_color + '60' : '#333'}`,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 20 }}>{p.icon}</span>
                        <span style={{
                          color: expandedPrinciple === i ? current.avatar_color : '#ddd',
                          fontWeight: 600,
                          fontSize: 14,
                        }}>
                          {p.title}
                        </span>
                        <span style={{
                          marginLeft: 'auto', color: '#666', fontSize: 12,
                          transform: expandedPrinciple === i ? 'rotate(180deg)' : 'none',
                          transition: 'transform 0.2s',
                        }}>
                          ▼
                        </span>
                      </div>
                      {expandedPrinciple === i && (
                        <p style={{
                          color: '#bbb', fontSize: 13, lineHeight: 1.7,
                          margin: '10px 0 0', paddingTop: 10,
                          borderTop: '1px solid #333',
                        }}>
                          {p.detail}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Two columns: Stock Selection + Position Management */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {/* Stock Selection */}
                <div style={{ background: '#1a1a2e', padding: 18, borderRadius: 8, border: '1px solid #333' }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 14 }}>
                    {current.stock_selection.title}
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {current.stock_selection.criteria.map((c, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                        <span style={{
                          color: current.avatar_color, fontWeight: 700,
                          minWidth: 20, fontSize: 13,
                        }}>
                          {i + 1}.
                        </span>
                        <span style={{ color: '#ccc', fontSize: 13, lineHeight: 1.5 }}>{c}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Position Management */}
                <div style={{ background: '#1a1a2e', padding: 18, borderRadius: 8, border: '1px solid #333' }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 14 }}>
                    {current.position_mgmt.title}
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {current.position_mgmt.rules.map((r, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                        <span style={{
                          color: current.avatar_color, fontWeight: 700,
                          minWidth: 20, fontSize: 13,
                        }}>
                          {i + 1}.
                        </span>
                        <span style={{ color: '#ccc', fontSize: 13, lineHeight: 1.5 }}>{r}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Two columns: Typical Stocks + Quotes */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {/* Typical Stocks */}
                <div style={{ background: '#1a1a2e', padding: 18, borderRadius: 8, border: '1px solid #333' }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 14 }}>
                    代表持仓 <span style={{ color: '#999', fontWeight: 400, fontSize: 13 }}>({current.typical_stocks.length}只)</span>
                  </h4>
                  <table className="arb-table" style={{ width: '100%' }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left' }}>代码</th>
                        <th style={{ textAlign: 'left' }}>名称</th>
                        <th style={{ textAlign: 'left' }}>逻辑</th>
                      </tr>
                    </thead>
                    <tbody>
                      {current.typical_stocks.map((s, i) => (
                        <tr key={i}>
                          <td style={{ color: '#1890ff', fontWeight: 600, fontSize: 13 }}>{s.code}</td>
                          <td style={{ color: '#ccc', fontSize: 13 }}>{s.name}</td>
                          <td style={{ color: '#999', fontSize: 12 }}>{s.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Quotes */}
                <div style={{ background: '#1a1a2e', padding: 18, borderRadius: 8, border: '1px solid #333' }}>
                  <h4 style={{ color: '#d4a76a', marginBottom: 14 }}>
                    经典语录 <span style={{ color: '#999', fontWeight: 400, fontSize: 13 }}>({current.quotes.length}条)</span>
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {current.quotes.map((q, i) => (
                      <div key={i} style={{
                        padding: '10px 14px',
                        background: 'rgba(0,0,0,0.2)',
                        borderRadius: 6,
                        borderLeft: `3px solid ${current.avatar_color}40`,
                      }}>
                        <p style={{ color: '#ccc', fontSize: 13, lineHeight: 1.6, margin: 0, fontStyle: 'italic' }}>
                          "{q}"
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Suitable For */}
              <div style={{
                background: `linear-gradient(135deg, ${current.avatar_color}08 0%, #1a1a2e 50%)`,
                padding: 18,
                borderRadius: 8,
                border: `1px solid ${current.avatar_color}30`,
              }}>
                <h4 style={{ color: '#d4a76a', marginBottom: 8 }}>适合人群</h4>
                <p style={{ color: '#bbb', fontSize: 14, lineHeight: 1.6, margin: 0 }}>
                  {current.suitable_for}
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
