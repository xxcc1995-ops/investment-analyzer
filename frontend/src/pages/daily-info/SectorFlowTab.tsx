/**
 * 板块资金标签页
 * 行业涨跌排名 + 主力资金流向 + 涨跌榜
 */
import { useState } from 'react'
import type { DailyBriefing, SectorItem, FundFlowItem, MoverItem } from './types'
import { formatPct, formatAmount, getChangeColor } from './utils'

interface Props {
  data: DailyBriefing | null
  loading: boolean
}

function isTradingDay(): boolean {
  const now = new Date()
  const day = now.getDay()
  return day >= 1 && day <= 5
}

export default function SectorFlowTab({ data, loading }: Props) {
  const [view, setView] = useState<'sectors' | 'flow' | 'movers'>('sectors')

  if (loading) return <div className="ui-loading">加载中...</div>
  if (!data) return <div className="ui-empty">暂无数据</div>

  const sectors = data.sector_performance || []
  const fundFlow = data.fund_flow || []
  const movers = data.top_movers

  // 非交易日且数据为空时显示提示
  const isEmpty = sectors.length === 0 && fundFlow.length === 0 &&
    (!movers || (movers.gainers?.length === 0 && movers.losers?.length === 0))
  if (isEmpty && !isTradingDay()) {
    return (
      <div style={{
        background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-md)', padding: 40, textAlign: 'center',
      }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>📅</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
          今日非交易日
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
          板块涨跌、资金流向、涨跌榜数据在交易日（周一至周五）实时更新。<br />
          下一个交易日开盘后将自动恢复。
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 视图切换 */}
      <div style={{ display: 'flex', gap: 8 }}>
        {([['sectors', '🏭 行业排名'], ['flow', '💰 资金流向'], ['movers', '📊 涨跌榜']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setView(key)} style={{
            padding: '6px 16px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
            border: view === key ? '1px solid var(--accent-blue)' : '1px solid var(--border-primary)',
            background: view === key ? 'rgba(88,166,255,0.15)' : 'var(--bg-secondary)',
            color: view === key ? 'var(--accent-blue)' : 'var(--text-secondary)',
            fontWeight: view === key ? 600 : 400,
          }}>{label}</button>
        ))}
      </div>

      {/* 行业排名 */}
      {view === 'sectors' && <SectorRanking sectors={sectors} />}

      {/* 资金流向 */}
      {view === 'flow' && <FundFlowChart fundFlow={fundFlow} />}

      {/* 涨跌榜 */}
      {view === 'movers' && movers && <TopMoversTable movers={movers} />}
    </div>
  )
}

// ==================== 行业排名 ====================

function SectorRanking({ sectors }: { sectors: SectorItem[] }) {
  if (!sectors.length) return <div style={{ color: 'var(--text-muted)' }}>暂无板块数据</div>

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', overflow: 'hidden',
    }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
            <th style={thStyle}>#</th>
            <th style={thStyle}>板块</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>涨跌幅</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>上涨/下跌</th>
            <th style={thStyle}>领涨股</th>
            <th style={{ ...thStyle, textAlign: 'right' }}>领涨幅度</th>
          </tr>
        </thead>
        <tbody>
          {sectors.map((s, i) => {
            const color = getChangeColor(s.change_pct)
            return (
              <tr key={s.code || i} style={{ borderBottom: '1px solid rgba(48,54,61,0.5)' }}>
                <td style={tdStyle}>{i + 1}</td>
                <td style={{ ...tdStyle, fontWeight: 500, color: 'var(--text-primary)' }}>{s.name}</td>
                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, color }}>
                  {formatPct(s.change_pct)}
                </td>
                <td style={{ ...tdStyle, textAlign: 'right' }}>
                  <span style={{ color: '#f85149' }}>{s.up_count}</span>
                  <span style={{ color: 'var(--text-muted)' }}> / </span>
                  <span style={{ color: '#3fb950' }}>{s.down_count}</span>
                </td>
                <td style={tdStyle}>{s.leader || '--'}</td>
                <td style={{ ...tdStyle, textAlign: 'right', color: getChangeColor(s.leader_change) }}>
                  {formatPct(s.leader_change)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ==================== 资金流向 ====================

function FundFlowChart({ fundFlow }: { fundFlow: FundFlowItem[] }) {
  if (!fundFlow.length) return <div style={{ color: 'var(--text-muted)' }}>暂无资金流向数据</div>

  // 取前15个行业
  const top = fundFlow.slice(0, 15)

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', padding: 16,
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
        主力资金净流入（前15行业）
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {top.map((f, i) => {
          const netYi = f.main_net_inflow / 1e8
          const color = netYi > 0 ? '#f85149' : '#3fb950'
          const maxAbs = Math.max(...top.map(x => Math.abs(x.main_net_inflow / 1e8)))
          const widthPct = maxAbs > 0 ? Math.min(100, (Math.abs(netYi) / maxAbs) * 100) : 0

          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              <span style={{ width: 80, color: 'var(--text-secondary)', textAlign: 'right', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {f.name}
              </span>
              <div style={{ flex: 1, height: 16, background: 'var(--bg-tertiary)', borderRadius: 3, overflow: 'hidden', position: 'relative' }}>
                {/* 中线 */}
                <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--border-primary)' }} />
                <div style={{
                  position: 'absolute', top: 0, bottom: 0,
                  [netYi > 0 ? 'left' : 'right']: '50%',
                  width: `${widthPct / 2}%`,
                  background: color,
                  opacity: 0.7,
                  borderRadius: 3,
                }} />
              </div>
              <span style={{ width: 70, textAlign: 'right', fontWeight: 500, color, flexShrink: 0 }}>
                {netYi > 0 ? '+' : ''}{netYi.toFixed(1)}亿
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ==================== 涨跌榜 ====================

function TopMoversTable({ movers }: { movers: { gainers: MoverItem[]; losers: MoverItem[] } }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <MoverList title="🔥 涨幅榜" items={movers.gainers} color="#f85149" />
      <MoverList title="💧 跌幅榜" items={movers.losers} color="#3fb950" />
    </div>
  )
}

function MoverList({ title, items, color }: { title: string; items: MoverItem[]; color: string }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)', overflow: 'hidden',
    }}>
      <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border-primary)', fontSize: 13, fontWeight: 600, color }}>
        {title}
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <tbody>
          {items?.map((item, i) => (
            <tr key={item.code || i} style={{ borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
              <td style={{ ...tdStyle, width: 30 }}>{i + 1}</td>
              <td style={{ ...tdStyle, fontWeight: 500 }}>
                <span style={{ color: 'var(--text-primary)' }}>{item.name}</span>
                <span style={{ color: 'var(--text-muted)', marginLeft: 6, fontSize: 11 }}>{item.code}</span>
              </td>
              <td style={{ ...tdStyle, textAlign: 'right', color: 'var(--text-secondary)' }}>
                {item.price?.toFixed(2)}
              </td>
              <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, color, width: 80 }}>
                {formatPct(item.change_pct)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ==================== 样式 ====================

const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'left', fontWeight: 600, fontSize: 12,
  color: 'var(--text-secondary)', background: 'var(--bg-tertiary)',
}

const tdStyle: React.CSSProperties = {
  padding: '6px 12px', color: 'var(--text-secondary)',
}
