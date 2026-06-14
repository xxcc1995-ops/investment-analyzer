/**
 * 海外资讯标签页
 * 美股 + 加密市场新闻，保留原有 UI 风格
 */
import { useState, useEffect, useCallback } from 'react'
import { dailyInfoApi } from '../../services/api'
import type { OverseasNewsData, OverseasCategoryData, OverseasNewsItem, SourceStatus } from './types'

const SOURCE_INFO = {
  us_stock: {
    label: '美股市场', icon: '🇺🇸',
    sources: [
      { name: 'Reuters', tier: 1, desc: '路透社 — 全球最大通讯社', url: 'https://www.reuters.com' },
      { name: 'MarketWatch', tier: 1, desc: '道琼斯旗下，美股市场深度报道', url: 'https://www.marketwatch.com' },
      { name: 'Yahoo Finance', tier: 1, desc: '综合财经门户，覆盖面广', url: 'https://finance.yahoo.com' },
      { name: 'Seeking Alpha', tier: 2, desc: '深度分析社区，机构级研报', url: 'https://seekingalpha.com' },
    ]
  },
  crypto: {
    label: '加密市场', icon: '₿',
    sources: [
      { name: 'CoinDesk', tier: 1, desc: '领先加密媒体', url: 'https://www.coindesk.com' },
      { name: 'The Block', tier: 1, desc: '研究导向，机构级加密分析', url: 'https://www.theblock.co' },
      { name: 'CoinTelegraph', tier: 2, desc: '综合加密新闻', url: 'https://cointelegraph.com' },
      { name: 'Decrypt', tier: 2, desc: 'Web3/DeFi 聚焦', url: 'https://decrypt.co' },
    ]
  }
}

interface Props {
  briefingData?: OverseasNewsData | null
}

export default function OverseasNewsTab({ briefingData }: Props) {
  const [data, setData] = useState<OverseasNewsData | null>(briefingData || null)
  const [loading, setLoading] = useState(!briefingData)
  const [error, setError] = useState<string | null>(null)
  const [showSources, setShowSources] = useState(false)

  const fetchNews = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await dailyInfoApi.getOverseasNews()
      setData(res.data as unknown as OverseasNewsData)
    } catch (err: any) {
      setError(err.message || '获取海外资讯失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!briefingData) fetchNews()
  }, [briefingData, fetchNews])

  if (loading) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>加载中...</div>
  if (error) return (
    <div style={{ textAlign: 'center', padding: 40 }}>
      <div style={{ color: 'var(--accent-red)', marginBottom: 8 }}>{error}</div>
      <button onClick={fetchNews} style={btnStyle}>重试</button>
    </div>
  )
  if (!data) return <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>暂无数据</div>

  const totalItems = (data.us_stock?.count || 0) + (data.crypto?.count || 0)
  const totalHigh = (data.us_stock?.high_impact_count || 0) + (data.crypto?.high_impact_count || 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 统计栏 */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <StatChip label="资讯总量" value={totalItems} />
        <StatChip label="重要资讯" value={totalHigh} color="#f85149" />
        <button onClick={() => setShowSources(!showSources)} style={{
          ...btnStyle, fontSize: 12,
        }}>📡 {showSources ? '隐藏' : '查看'}信息源</button>
        <button onClick={fetchNews} style={{ ...btnStyle, fontSize: 12 }}>🔄 刷新</button>
      </div>

      {showSources && <SourcesPanel />}

      {/* 美股 */}
      {data.us_stock && <NewsCategory title="美股市场" icon="🇺🇸" data={data.us_stock} />}

      {/* 加密 */}
      {data.crypto && <NewsCategory title="加密市场" icon="₿" data={data.crypto} />}
    </div>
  )
}

// ==================== 子组件 ====================

function StatChip({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-sm)', padding: '6px 12px',
    }}>
      <span style={{ fontSize: 16, fontWeight: 700, color: color || 'var(--text-primary)' }}>{value}</span>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>{label}</span>
    </div>
  )
}

function NewsCategory({ title, icon, data }: { title: string; icon: string; data: OverseasCategoryData }) {
  const highItems = data.items.filter(i => i.impact === 'high')
  const mediumItems = data.items.filter(i => i.impact === 'medium')
  const lowItems = data.items.filter(i => i.impact === 'low')

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', overflow: 'hidden',
    }}>
      {/* 头部 */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--border-primary)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 20 }}>{icon}</span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {data.count || 0} 条 · {data.sources_ok?.length || 0} 个信源
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {highItems.length > 0 && <span style={highBadge}>{highItems.length} 条重要</span>}
          {mediumItems.length > 0 && <span style={mediumBadge}>{mediumItems.length} 条关注</span>}
        </div>
      </div>

      {/* 重要新闻 */}
      {highItems.length > 0 && (
        <div style={{ padding: '12px 16px', background: 'rgba(248,81,73,0.05)' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#f85149', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
            ⚡ Market Moving
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {highItems.map((item, i) => <HighImpactCard key={i} item={item} sourcesOk={data.sources_ok} />)}
          </div>
        </div>
      )}

      {/* 关注新闻 */}
      {mediumItems.length > 0 && (
        <div style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#d29922', marginBottom: 8 }}>📌 值得关注</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {mediumItems.map((item, i) => <MediumItem key={i} item={item} sourcesOk={data.sources_ok} />)}
          </div>
        </div>
      )}

      {/* 一般新闻 */}
      {lowItems.length > 0 && (
        <details>
          <summary style={{
            padding: '8px 16px', cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)',
            borderTop: '1px solid var(--border-primary)',
          }}>
            📰 更多资讯 ({lowItems.length})
          </summary>
          <div style={{ padding: '0 16px 12px' }}>
            {lowItems.map((item, i) => (
              <a key={i} href={item.link} target="_blank" rel="noopener noreferrer" style={{
                display: 'flex', justifyContent: 'space-between', padding: '4px 0',
                fontSize: 12, color: 'var(--text-secondary)', textDecoration: 'none',
                borderBottom: '1px solid rgba(48,54,61,0.3)',
              }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
                <span style={{ color: 'var(--text-muted)', marginLeft: 8, flexShrink: 0 }}>{item.source}</span>
              </a>
            ))}
          </div>
        </details>
      )}

      {/* 信源状态 */}
      <div style={{
        padding: '6px 16px', background: 'var(--bg-tertiary)', borderTop: '1px solid var(--border-primary)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11,
      }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {data.sources_ok?.map((src, i) => (
            <span key={i} style={{ color: '#3fb950' }}>
              {src.name_cn}{src.tier === 1 ? '★' : ''} ✓
            </span>
          ))}
          {data.sources_failed?.map((name, i) => (
            <span key={i} style={{ color: 'var(--text-muted)', textDecoration: 'line-through' }}>{name}</span>
          ))}
        </div>
        <span style={{ color: 'var(--text-muted)' }}>
          {data.update_time ? new Date(data.update_time).toLocaleTimeString('zh-CN') : ''}
        </span>
      </div>
    </div>
  )
}

function HighImpactCard({ item, sourcesOk }: { item: OverseasNewsItem; sourcesOk: SourceStatus[] }) {
  const srcStatus = sourcesOk?.find(s => s.name === item.source)
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid rgba(248,81,73,0.3)',
      borderRadius: 'var(--radius-sm)', padding: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <span style={highImpactBadge}>🔴 重要</span>
        <div style={{ flex: 1 }}>
          <a href={item.link} target="_blank" rel="noopener noreferrer" style={{
            fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', textDecoration: 'none', lineHeight: 1.4,
          }}>
            {item.title}
          </a>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <span style={{
              fontSize: 11, padding: '1px 6px', borderRadius: 4,
              background: srcStatus?.tier === 1 ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
              color: 'var(--text-secondary)', border: '1px solid var(--border-primary)',
            }}>
              {srcStatus?.name_cn || item.source}
              {srcStatus?.tier === 1 && <span style={{ color: 'var(--accent-blue)', marginLeft: 2 }}>★</span>}
            </span>
            {item.published && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.published}</span>}
          </div>
        </div>
      </div>
      {(item.key_points?.length > 0 || item.summary) && (
        <div style={{ marginTop: 8, paddingLeft: 8 }}>
          {item.key_points?.length > 0 ? item.key_points.slice(0, 3).map((point, j) => (
            <div key={j} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 3, lineHeight: 1.5 }}>
              <span style={{ color: '#f85149', marginRight: 4 }}>▸</span>{point}
            </div>
          )) : item.summary ? (
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <span style={{ color: '#f85149', marginRight: 4 }}>▸</span>{item.summary}
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

function MediumItem({ item, sourcesOk }: { item: OverseasNewsItem; sourcesOk: SourceStatus[] }) {
  const srcStatus = sourcesOk?.find(s => s.name === item.source)
  return (
    <div style={{ padding: '6px 0', borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
      <a href={item.link} target="_blank" rel="noopener noreferrer" style={{
        display: 'flex', gap: 8, textDecoration: 'none',
      }}>
        <span style={mediumImpactBadge}>🟡</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', lineHeight: 1.4 }}>{item.title}</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{srcStatus?.name_cn || item.source}</span>
            {item.published && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{item.published}</span>}
          </div>
        </div>
      </a>
    </div>
  )
}

function SourcesPanel() {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>📡 信息源说明</div>
      {Object.entries(SOURCE_INFO).map(([key, cat]) => (
        <div key={key} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
            {cat.icon} {cat.label}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
            {cat.sources.map((src, i) => (
              <div key={i} style={{
                padding: 6, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
                fontSize: 11, border: '1px solid var(--border-primary)',
              }}>
                <span style={{
                  fontSize: 10, padding: '0 4px', borderRadius: 3,
                  background: src.tier === 1 ? 'rgba(88,166,255,0.2)' : 'var(--bg-secondary)',
                  color: src.tier === 1 ? 'var(--accent-blue)' : 'var(--text-muted)',
                  fontWeight: 700, marginRight: 4,
                }}>T{src.tier}{src.tier === 1 ? ' ★' : ''}</span>
                <a href={src.url} target="_blank" rel="noopener noreferrer" style={{
                  color: 'var(--text-primary)', fontWeight: 500, textDecoration: 'none',
                }}>{src.name}</a>
                <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{src.desc}</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ==================== 样式 ====================

const btnStyle: React.CSSProperties = {
  padding: '4px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
  border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
  color: 'var(--text-secondary)',
}

const highBadge: React.CSSProperties = {
  padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
  background: 'rgba(248,81,73,0.1)', color: '#f85149', border: '1px solid rgba(248,81,73,0.2)',
}

const mediumBadge: React.CSSProperties = {
  padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
  background: 'rgba(210,153,34,0.1)', color: '#d29922', border: '1px solid rgba(210,153,34,0.2)',
}

const highImpactBadge: React.CSSProperties = {
  display: 'inline-block', padding: '1px 6px', borderRadius: 10, fontSize: 10, fontWeight: 700,
  background: 'rgba(248,81,73,0.1)', color: '#f85149', border: '1px solid rgba(248,81,73,0.2)', flexShrink: 0,
}

const mediumImpactBadge: React.CSSProperties = {
  fontSize: 12, flexShrink: 0,
}
