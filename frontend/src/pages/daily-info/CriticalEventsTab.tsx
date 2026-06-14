/**
 * 重大事件标签页
 * 自动检测的 critical events + 多源交叉验证新闻
 */
import type { DailyBriefing, CriticalEvent, CrossValidatedNews } from './types'
import { getEventIcon, getEventLevelColor, relativeTime, truncate } from './utils'

interface Props {
  data: DailyBriefing | null
  loading: boolean
}

export default function CriticalEventsTab({ data, loading }: Props) {
  if (loading) return <div className="ui-loading">加载中...</div>
  if (!data) return <div className="ui-empty">暂无数据</div>

  const events = data.critical_events || []
  const crossValidated = data.cross_validated_news || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 重大事件 */}
      <Section title="⚡ 重大事件自动检测" subtitle={events.length > 0 ? `${events.length} 条` : '暂无重大事件'}>
        {events.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {events.map((e, i) => <EventCard key={i} event={e} />)}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            ✅ 未检测到重大异动事件，市场运行平稳
          </div>
        )}
      </Section>

      {/* 交叉验证新闻 */}
      <Section title="🔍 多源交叉验证新闻" subtitle={crossValidated.length > 0 ? `${crossValidated.length} 条高置信度` : '暂无'}>
        {crossValidated.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {crossValidated.map((n, i) => <CrossValidatedCard key={i} news={n} />)}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0', textAlign: 'center' }}>
            暂无多源交叉验证新闻
          </div>
        )}
      </Section>
    </div>
  )
}

// ==================== 子组件 ====================

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
        {subtitle && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{subtitle}</span>}
      </div>
      {children}
    </div>
  )
}

function EventCard({ event }: { event: CriticalEvent }) {
  const levelColor = getEventLevelColor(event.level)
  const icon = getEventIcon(event.type)

  return (
    <div style={{
      background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-sm)', padding: 12,
      borderLeft: `3px solid ${levelColor}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <span style={{ fontSize: 18, flexShrink: 0 }}>{icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              fontSize: 11, padding: '1px 6px', borderRadius: 10,
              background: `${levelColor}22`, color: levelColor, fontWeight: 600, textTransform: 'uppercase',
            }}>
              {event.level}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{event.source}</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{relativeTime(event.time)}</span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
            {event.title}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {event.description}
          </div>
          {event.link && (
            <a href={event.link} target="_blank" rel="noopener noreferrer" style={{
              fontSize: 12, color: 'var(--accent-blue)', textDecoration: 'none', marginTop: 4, display: 'inline-block',
            }}>
              查看原文 →
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

function CrossValidatedCard({ news }: { news: CrossValidatedNews }) {
  const confColor = news.confidence === 'high' ? '#f85149' : '#d29922'

  return (
    <div style={{
      background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-sm)', padding: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{
          fontSize: 10, padding: '1px 6px', borderRadius: 10,
          background: `${confColor}22`, color: confColor, fontWeight: 600,
        }}>
          {news.confidence === 'high' ? '高置信' : '中置信'}
        </span>
        <span style={{
          fontSize: 10, padding: '1px 6px', borderRadius: 10,
          background: 'var(--bg-secondary)', color: 'var(--text-secondary)',
        }}>
          {news.source_count} 个信源
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {news.sources?.join(' / ')}
        </span>
      </div>
      <a href={news.link} target="_blank" rel="noopener noreferrer" style={{
        fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', textDecoration: 'none',
        lineHeight: 1.4,
      }}>
        {news.title}
      </a>
      {news.summary && (
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
          {truncate(news.summary, 150)}
        </div>
      )}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
        {relativeTime(news.published)} · {news.category === 'us_stock' ? '美股' : '加密'}
      </div>
    </div>
  )
}
