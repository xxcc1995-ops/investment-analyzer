/**
 * 每日资讯 - 机构级投资简报仪表盘
 *
 * 8 个标签页：市场总览 / 板块资金 / 重大事件 / 海外资讯 / 宏观数据 / 价值投资 / 套利机会 / 可转债加密
 *
 * 数据策略：
 * - 首屏加载 /briefing（含市场/板块/情绪/事件/海外新闻等核心数据）
 * - 切换到其他标签时懒加载对应数据
 */
import { useState, useEffect, useCallback } from 'react'
import { PageSection, TabBar, LoadingSpinner, EmptyState } from '../components/ui'
import { dailyInfoApi } from '../services/api'
import type { DailyBriefing } from './daily-info/types'
import { relativeTime } from './daily-info/utils'

// 懒加载标签页组件
import MarketOverviewTab from './daily-info/MarketOverviewTab'
import SectorFlowTab from './daily-info/SectorFlowTab'
import CriticalEventsTab from './daily-info/CriticalEventsTab'
import OverseasNewsTab from './daily-info/OverseasNewsTab'
import MacroDataTab from './daily-info/MacroDataTab'
import ValueInvestingTab from './daily-info/ValueInvestingTab'
import ArbitrageTab from './daily-info/ArbitrageTab'
import CryptoTab from './daily-info/CryptoTab'

// ==================== 标签页配置 ====================

const TABS = [
  { key: 'overview', label: '市场总览', icon: '📊' },
  { key: 'sectors', label: '板块资金', icon: '🏭' },
  { key: 'events', label: '重大事件', icon: '⚡' },
  { key: 'overseas', label: '海外资讯', icon: '🌍' },
  { key: 'macro', label: '宏观数据', icon: '📈' },
  { key: 'value', label: '价值投资', icon: '💰' },
  { key: 'arbitrage', label: '套利机会', icon: '🔄' },
  { key: 'crypto', label: '可转债/加密', icon: '🪙' },
]

// ==================== 主组件 ====================

export default function DailyInfo() {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState('overview')

  const loadBriefing = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await dailyInfoApi.getBriefing()
      setBriefing(res.data as unknown as DailyBriefing)
    } catch (err: any) {
      setError(err.message || '获取每日简报失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadBriefing() }, [loadBriefing])

  // 计算 badge 数字
  const criticalCount = briefing?.critical_events?.length || 0
  const overseasHigh = (briefing?.overseas_news?.us_stock?.high_impact_count || 0) +
    (briefing?.overseas_news?.crypto?.high_impact_count || 0)

  const tabsWithBadge = TABS.map(t => {
    if (t.key === 'events' && criticalCount > 0) return { ...t, badge: criticalCount }
    if (t.key === 'overseas' && overseasHigh > 0) return { ...t, badge: overseasHigh }
    return t
  })

  // ==================== 渲染 ====================

  if (loading) {
    return (
      <PageSection title="📰 每日资讯">
        <LoadingSpinner text="正在加载每日投资简报（首次加载约30秒）..." />
      </PageSection>
    )
  }

  if (error) {
    return (
      <PageSection title="📰 每日资讯">
        <EmptyState
          icon="⚠️"
          title="获取每日简报失败"
          description={error}
          action={
            <button onClick={loadBriefing} style={{
              marginTop: 12, padding: '6px 16px', borderRadius: 6,
              background: 'var(--accent-blue)', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 13,
            }}>重试</button>
          }
        />
      </PageSection>
    )
  }

  return (
    <PageSection
      title="📰 每日资讯"
      extra={
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {briefing?.update_time && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              更新于 {relativeTime(briefing.update_time)}
            </span>
          )}
          <button onClick={loadBriefing} style={{
            padding: '4px 12px', borderRadius: 6, fontSize: 12,
            border: '1px solid var(--border-primary)', background: 'var(--bg-secondary)',
            color: 'var(--text-secondary)', cursor: 'pointer',
          }}>🔄 刷新</button>
        </div>
      }
    >
      <TabBar
        tabs={tabsWithBadge}
        activeKey={tab}
        onChange={setTab}
        style={{ marginBottom: 16 }}
      />

      {/* 标签页内容 */}
      {tab === 'overview' && <MarketOverviewTab data={briefing} loading={false} />}
      {tab === 'sectors' && <SectorFlowTab data={briefing} loading={false} />}
      {tab === 'events' && <CriticalEventsTab data={briefing} loading={false} />}
      {tab === 'overseas' && <OverseasNewsTab briefingData={briefing?.overseas_news || null} />}
      {tab === 'macro' && <MacroDataTab chinaMacro={briefing?.macro_indicators?.china} />}
      {tab === 'value' && <ValueInvestingTab briefingData={briefing?.value_investing || null} />}
      {tab === 'arbitrage' && <ArbitrageTab briefingData={briefing?.arbitrage || null} />}
      {tab === 'crypto' && (
        <CryptoTab
          cbData={briefing?.convertible_bonds || null}
          cryptoData={briefing?.crypto || null}
          airdropData={briefing?.airdrops || null}
        />
      )}
    </PageSection>
  )
}
