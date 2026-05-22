import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface InfoSource {
  name: string
  url: string
  desc: string
  lang: string
  hot: boolean
  tips?: string
}

interface InfoTip {
  title: string
  items: string[]
}

const CATEGORY_META: Record<string, { label: string; icon: string; desc: string }> = {
  news: { label: '新闻媒体', icon: '📰', desc: '加密货币新闻快讯，追踪行业动态' },
  research: { label: '研究分析', icon: '📊', desc: '链上数据、研报、专业分析工具' },
  onchain: { label: '链上数据', icon: '🔗', desc: '区块浏览器、钱包追踪、DEX数据' },
  social: { label: '社区社交', icon: '💬', desc: 'Twitter、Reddit、Discord社区' },
  education: { label: '学习教育', icon: '📚', desc: '入门教程、深度课程、播客' },
  tools: { label: '实用工具', icon: '🛠️', desc: '行情数据、图表分析、监控工具' },
}

export default function CryptoScreener() {
  const [sources, setSources] = useState<Record<string, InfoSource[]>>({})
  const [tips, setTips] = useState<InfoTip[]>([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('news')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [srcRes, tipsRes] = await Promise.all([
        axios.get(`${API_BASE}/crypto/sources`),
        axios.get(`${API_BASE}/crypto/tips`),
      ])
      setSources(srcRes.data)
      setTips(tipsRes.data.tips || [])
    } catch (e) {
      console.error('获取信息源失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const currentSources = sources[activeTab] || []

  return (
    <div>
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>币圈信息源汇总</h2>
            <span className="stock-code">高质量信息渠道 · 过滤噪音 · 只留精华</span>
          </div>
          <button className="btn-add" onClick={loadData}>刷新</button>
        </div>
      </div>

      {/* 分类Tab */}
      <div className="list-tabs" style={{ marginBottom: '16px', flexWrap: 'wrap' }}>
        {Object.entries(CATEGORY_META).map(([key, meta]) => (
          <button
            key={key}
            className={`list-tab ${activeTab === key ? 'active' : ''}`}
            onClick={() => setActiveTab(key)}
          >
            {meta.icon} {meta.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading"><div className="spinner"></div>加载中...</div>
      ) : (
        <>
          {/* 分类说明 */}
          <div className="arb-notes" style={{ marginBottom: '16px' }}>
            <h3>{CATEGORY_META[activeTab]?.icon} {CATEGORY_META[activeTab]?.label}</h3>
            <div style={{ color: 'var(--text-muted)', fontSize: '14px' }}>{CATEGORY_META[activeTab]?.desc}</div>
          </div>

          {/* 信息源列表 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '12px', marginBottom: '20px' }}>
            {currentSources.map((src, i) => (
              <div key={i} className="arb-note-item" style={{ padding: '16px', position: 'relative' }}>
                {src.hot && (
                  <span style={{
                    position: 'absolute', top: '8px', right: '8px',
                    background: '#ff4d4f', color: '#fff', fontSize: '11px',
                    padding: '2px 6px', borderRadius: '4px', fontWeight: 600,
                  }}>
                    推荐
                  </span>
                )}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 700, fontSize: '16px' }}>{src.name}</span>
                  <span style={{
                    fontSize: '11px', padding: '1px 6px', borderRadius: '3px',
                    background: src.lang === 'CN' ? '#fff1f0' : '#f0f5ff',
                    color: src.lang === 'CN' ? '#cf1322' : '#1d39c4',
                  }}>
                    {src.lang}
                  </span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', lineHeight: '1.5' }}>
                  {src.desc}
                </div>
                {src.tips && (
                  <div style={{
                    fontSize: '12px', color: 'var(--accent)',
                    background: 'var(--bg-tertiary)', padding: '6px 10px', borderRadius: '4px',
                    marginBottom: '8px',
                  }}>
                    💡 {src.tips}
                  </div>
                )}
                {src.url && (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: '13px', color: 'var(--accent-blue)', textDecoration: 'none' }}
                  >
                    {src.url.replace('https://', '').replace('http://', '')}
                  </a>
                )}
              </div>
            ))}
          </div>

          {/* 信息筛选方法论 */}
          <div className="arb-notes">
            <h3>信息筛选方法论</h3>
            <div className="arb-notes-grid">
              {tips.map((tip, i) => (
                <div key={i} className="arb-note-item">
                  <span className="arb-note-label">{tip.title}</span>
                  <div style={{ marginTop: '8px' }}>
                    {tip.items.map((item, j) => (
                      <div key={j} style={{ fontSize: '13px', color: 'var(--text-muted)', padding: '3px 0', lineHeight: '1.5' }}>
                        · {item}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 风险提示 */}
          <div className="arb-notes" style={{ marginTop: '16px' }}>
            <h3>风险提示</h3>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <h4>信息≠投资建议</h4>
                <ul>
                  <li><strong>信息源≠推荐</strong>：列出的信息源仅供参考，不代表对其内容的背书</li>
                  <li><strong>独立判断</strong>：任何投资决策都应基于自己的研究和判断</li>
                  <li><strong>高风险资产</strong>：加密货币波动极大，做好归零的心理准备</li>
                  <li><strong>控制仓位</strong>：高风险投资不超过总资产的10%</li>
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
