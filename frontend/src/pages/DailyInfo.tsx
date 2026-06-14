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
import { relativeTime, formatPct } from './daily-info/utils'

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

// ==================== 数据源健康检查 ====================

interface SourceHealth {
  name: string
  status: 'ok' | 'empty' | 'error'
  detail: string
}

function getSourceHealth(b: DailyBriefing): SourceHealth[] {
  const sources: SourceHealth[] = []

  // 市场行情
  const aCount = b.market_overview?.china?.a_share?.length || 0
  const usCount = b.market_overview?.us?.indices?.length || 0
  sources.push({
    name: '新浪财经（行情）',
    status: aCount + usCount > 0 ? 'ok' : 'empty',
    detail: `A股${aCount} 美股${usCount}`,
  })

  // 板块
  const sectorCount = b.sector_performance?.length || 0
  sources.push({
    name: '东方财富（板块）',
    status: sectorCount > 0 ? 'ok' : 'empty',
    detail: `${sectorCount} 个板块`,
  })

  // 资金流向
  const flowCount = b.fund_flow?.length || 0
  sources.push({
    name: '东方财富（资金流）',
    status: flowCount > 0 ? 'ok' : 'empty',
    detail: `${flowCount} 行业`,
  })

  // 海外新闻
  const newsCount = (b.overseas_news?.us_stock?.count || 0) + (b.overseas_news?.crypto?.count || 0)
  const newsSources = (b.overseas_news?.us_stock?.sources_ok?.length || 0) +
    (b.overseas_news?.crypto?.sources_ok?.length || 0)
  sources.push({
    name: '海外新闻（RSS/HTML）',
    status: newsCount > 0 ? 'ok' : 'empty',
    detail: `${newsCount} 条 / ${newsSources} 源`,
  })

  // 价值投资
  const viCount = (b.value_investing?.announcements?.length || 0) +
    (b.value_investing?.analyst_reports?.length || 0)
  sources.push({
    name: '价值投资（RSSHub+东财）',
    status: viCount > 0 ? 'ok' : 'empty',
    detail: `${viCount} 条`,
  })

  // 可转债
  const cbCount = (b.convertible_bonds?.hot_bonds?.length || 0) +
    (b.convertible_bonds?.events?.length || 0)
  sources.push({
    name: '可转债（集思录）',
    status: cbCount > 0 ? 'ok' : 'empty',
    detail: `${cbCount} 条`,
  })

  // 加密
  const cryptoOk = (b.crypto?.market_overview?.length || 0) > 0 || (b.crypto?.stablecoin_mcap || 0) > 0
  sources.push({
    name: '加密市场（CoinGecko）',
    status: cryptoOk ? 'ok' : 'empty',
    detail: b.crypto?.stablecoin_mcap ? `稳定币 $${b.crypto.stablecoin_mcap}B` : '无数据',
  })

  // 空投
  const airdropCount = b.airdrops?.defi_protocols?.length || 0
  sources.push({
    name: 'DeFi 空投（DefiLlama）',
    status: airdropCount > 0 ? 'ok' : 'empty',
    detail: `${airdropCount} 协议`,
  })

  return sources
}

function SourceHealthPanel({ sources }: { sources: SourceHealth[] }) {
  const okCount = sources.filter(s => s.status === 'ok').length
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16, marginTop: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
          🔍 数据源健康状态
        </span>
        <span style={{ fontSize: 12, color: okCount === sources.length ? '#3fb950' : '#d29922' }}>
          {okCount}/{sources.length} 正常
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 6 }}>
        {sources.map((s, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px',
            borderRadius: 'var(--radius-sm)', fontSize: 11,
            background: s.status === 'ok' ? 'rgba(63,185,80,0.08)' : 'rgba(210,153,34,0.08)',
          }}>
            <span style={{ color: s.status === 'ok' ? '#3fb950' : '#d29922', fontSize: 10 }}>
              {s.status === 'ok' ? '●' : '○'}
            </span>
            <span style={{ flex: 1, color: 'var(--text-secondary)' }}>{s.name}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{s.detail}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ==================== 主组件 ====================

export default function DailyInfo() {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState('overview')
  const [showHealth, setShowHealth] = useState(false)

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

  const sourceHealth = briefing ? getSourceHealth(briefing) : []

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
          <button onClick={() => setShowHealth(!showHealth)} style={{
            padding: '4px 10px', borderRadius: 6, fontSize: 11,
            border: '1px solid var(--border-primary)', background: showHealth ? 'rgba(88,166,255,0.15)' : 'var(--bg-secondary)',
            color: showHealth ? 'var(--accent-blue)' : 'var(--text-muted)', cursor: 'pointer',
          }}>🔍 数据源</button>
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

      {/* 数据源健康面板 */}
      {showHealth && <SourceHealthPanel sources={sourceHealth} />}
    </PageSection>
  )
}
