import { useState, useEffect, useCallback } from 'react'
import { cbNearMatureApi, type NearMatureBond } from '../services/api'

// 三个表：双条件精选 / 钝化区 / 临期全表
type TabKey = 'double_condition' | 'floor_zone' | 'all_linqi'

const TABS: { key: TabKey; label: string; desc: string }[] = [
  { key: 'double_condition', label: '双条件精选', desc: '钝化区 + 溢价率≤阈值 + 未公告强赎' },
  { key: 'floor_zone', label: '钝化区', desc: '现价贴税后保本价 ±1 元' },
  { key: 'all_linqi', label: '临期全表', desc: '剩余 < 1 年的全部在交易转债（观察区）' },
]

function fmt(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return v.toFixed(digits)
}

function fmtSigned(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  return (v > 0 ? '+' : '') + v.toFixed(digits)
}

export default function NearMaturityPage() {
  const [tab, setTab] = useState<TabKey>('double_condition')
  const [data, setData] = useState<NearMatureBond[]>([])
  const [summary, setSummary] = useState<{ all_count: number; floor_count: number; double_condition_count: number; as_of: string; note?: string } | null>(null)
  const [fetchTime, setFetchTime] = useState('')
  const [dataSource, setDataSource] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // 参数
  const [maxRemainYears, setMaxRemainYears] = useState(1)
  const [priceTol, setPriceTol] = useState(1)
  const [maxPremium, setMaxPremium] = useState(20)
  const [includeElasticity, setIncludeElasticity] = useState(false)

  const load = useCallback(async (overrides?: {
    maxRemainYears?: number
    priceTol?: number
    maxPremium?: number
    includeElasticity?: boolean
  }) => {
    setLoading(true)
    setError('')
    try {
      const res = await cbNearMatureApi.getNearMature({
        include_elasticity: overrides?.includeElasticity ?? includeElasticity,
        max_remain_years: overrides?.maxRemainYears ?? maxRemainYears,
        price_tol: overrides?.priceTol ?? priceTol,
        max_premium: overrides?.maxPremium ?? maxPremium,
      })
      setSummary(res.data.summary || null)
      setFetchTime(res.data.fetch_time || '')
      setDataSource(res.data.data_source || '')
      const all: Record<TabKey, NearMatureBond[]> = {
        double_condition: res.data.double_condition || [],
        floor_zone: res.data.floor_zone || [],
        all_linqi: res.data.all_linqi || [],
      }
      setData(all[tab] || [])
    } catch (err: any) {
      console.error('加载临期债数据失败:', err)
      setError(err?.response?.data?.detail || err?.message || '加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [maxRemainYears, priceTol, maxPremium, includeElasticity, tab])

  useEffect(() => { load() }, [load])

  const switchTab = (key: TabKey) => {
    setTab(key)
    // 切换后按新 tab 重新拉一次（后端一次返回三表，这里复用最近一次响应更高效，
    // 但为保持参数一致，直接触发 load；load 依赖 tab，会带上当前 tab 渲染）
  }

  return (
    <div className="cb-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>临期债筛选（税后保本价安全垫）</h2>
            <span className="stock-code">剩余&lt;1年 · 现价贴税后保本价 · 低转股溢价 · 数据源 akshare 直连</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={maxRemainYears} onChange={e => { setMaxRemainYears(Number(e.target.value)); load({ maxRemainYears: Number(e.target.value) }) }}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={0.5}>剩余 ≤ 0.5 年</option>
              <option value={1}>剩余 ≤ 1 年</option>
              <option value={1.5}>剩余 ≤ 1.5 年</option>
            </select>
            <select value={priceTol} onChange={e => { setPriceTol(Number(e.target.value)); load({ priceTol: Number(e.target.value) }) }}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={0.5}>保本价容忍 ±0.5 元</option>
              <option value={1}>保本价容忍 ±1 元</option>
              <option value={2}>保本价容忍 ±2 元</option>
            </select>
            <select value={maxPremium} onChange={e => { setMaxPremium(Number(e.target.value)); load({ maxPremium: Number(e.target.value) }) }}
              style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
              <option value={10}>溢价率 ≤ 10%</option>
              <option value={20}>溢价率 ≤ 20%</option>
              <option value={30}>溢价率 ≤ 30%</option>
            </select>
            <label style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
              <input type="checkbox" checked={includeElasticity} onChange={e => { setIncludeElasticity(e.target.checked); load({ includeElasticity: e.target.checked }) }} />
              正股弹性
            </label>
            <button className="btn-add" onClick={() => load()}>刷新数据</button>
          </div>
        </div>
        <div className="data-freshness">
          <span className="freshness-tag">更新时间: {fetchTime}</span>
          <span className="freshness-tag">基准日: {summary?.as_of || '-'}</span>
          {dataSource && (
            <span className="freshness-tag" style={{ background: 'rgba(250,173,20,0.1)', color: '#faad14' }}>
              数据源: {dataSource === 'akshare' ? 'AKShare(东方财富)' : dataSource}
            </span>
          )}
        </div>
      </div>

      {/* 概览统计 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        <div className="bond-yield-card" style={{ borderLeft: '4px solid #52c41a' }}>
          <div className="bond-yield-label">双条件精选（主表）</div>
          <div className="bond-yield-value" style={{ color: '#52c41a' }}>{summary?.double_condition_count ?? '-'} 只</div>
          <div className="bond-yield-desc">钝化 + 低溢价 + 未强赎</div>
        </div>
        <div className="bond-yield-card" style={{ borderLeft: '4px solid #1890ff' }}>
          <div className="bond-yield-label">钝化区</div>
          <div className="bond-yield-value" style={{ color: '#1890ff' }}>{summary?.floor_count ?? '-'} 只</div>
          <div className="bond-yield-desc">现价贴税后保本价 ±{priceTol} 元</div>
        </div>
        <div className="bond-yield-card" style={{ borderLeft: '4px solid #faad14' }}>
          <div className="bond-yield-label">临期全表（观察区）</div>
          <div className="bond-yield-value" style={{ color: '#faad14' }}>{summary?.all_count ?? '-'} 只</div>
          <div className="bond-yield-desc">剩余 &lt; {maxRemainYears} 年在交易转债</div>
        </div>
      </div>

      {/* Tab 切换 */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => switchTab(t.key)}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: tab === t.key ? 700 : 500,
              background: tab === t.key ? '#58a6ff' : 'var(--bg-secondary)',
              color: tab === t.key ? '#0d1117' : 'var(--text-primary)',
              border: tab === t.key ? '1px solid #58a6ff' : '1px solid var(--border)',
            }}
          >
            {t.label}
          </button>
        ))}
        <span style={{ alignSelf: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
          {TABS.find(t => t.key === tab)?.desc}
        </span>
      </div>

      {error && (
        <div style={{ marginBottom: '16px', padding: '12px 16px', background: 'rgba(255,77,79,0.08)', border: '1px solid rgba(255,77,79,0.3)', borderRadius: '8px', color: '#ff4d4f', fontSize: '13px' }}>
          ⚠️ {error}
        </div>
      )}

      {/* 表格 */}
      {loading ? (
        <div className="loading"><div className="spinner"></div>加载中...</div>
      ) : (
        <div className="table-container">
          <div className="arb-section-title">
            {TABS.find(t => t.key === tab)?.label}（{data.length} 只）
          </div>
          <table className="arb-table">
            <thead>
              <tr>
                <th>代码</th>
                <th>转债名称</th>
                <th>现价</th>
                <th>税后保本价</th>
                <th>距保本价</th>
                <th>溢价率(%)</th>
                <th>剩余年限</th>
                <th>到期日</th>
                <th>评级</th>
                <th>强赎状态</th>
                <th>正股</th>
                {includeElasticity && <th>正股20日涨幅</th>}
                {includeElasticity && <th>正股20日振幅</th>}
              </tr>
            </thead>
            <tbody>
              {data.map((b, i) => {
                const dist = b.dist_to_floor
                const distColor = dist === null || dist === undefined ? 'inherit'
                  : Math.abs(dist) <= 1 ? '#52c41a' : dist < 0 ? '#52c41a' : '#faad14'
                return (
                  <tr key={`${b.bond_id}-${i}`}>
                    <td>{b.bond_id}</td>
                    <td>{b.bond_nm}</td>
                    <td style={{ fontWeight: 600 }}>{fmt(b.price)}</td>
                    <td>{fmt(b.after_tax_floor)}</td>
                    <td style={{ fontWeight: 700, color: distColor }}>{fmtSigned(dist)}</td>
                    <td className={b.premium_rt != null && b.premium_rt <= 20 ? 'down' : ''}>{fmt(b.premium_rt)}</td>
                    <td>{fmt(b.year_left, 2)}</td>
                    <td style={{ fontSize: '12px' }}>{b.maturity_dt || '-'}</td>
                    <td>{b.rating_cd || '-'}</td>
                    <td>{b.force_redeem || '-'}</td>
                    <td>{b.stock_nm || '-'}</td>
                    {includeElasticity && <td>{fmtSigned(b.stock_20d_chg)}</td>}
                    {includeElasticity && <td>{fmt(b.stock_20d_amp)}</td>}
                  </tr>
                )
              })}
              {data.length === 0 && (
                <tr>
                  <td colSpan={includeElasticity ? 13 : 11} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    暂无符合条件的临期转债
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 策略说明 */}
      <div className="arb-notes">
        <h3>临期债筛选逻辑与注意事项</h3>
        <div className="arb-notes-grid">
          <div className="arb-note-item">
            <span className="arb-note-label">税后保本价</span>
            <span className="arb-note-value">安全垫</span>
            <span className="arb-note-desc">= 100 + (到期赎回价 - 100) × (1 - 20%)，利息税 20% 后的持有到期底线</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">钝化区</span>
            <span className="arb-note-value">条件1</span>
            <span className="arb-note-desc">剩余 &lt; 1 年且现价贴税后保本价 ±1 元，向下有底、信用风险已定价</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">双条件精选</span>
            <span className="arb-note-value">条件2</span>
            <span className="arb-note-desc">钝化区 + 转股溢价率 ≤ 20% + 未公告强赎，保留看涨期权价值</span>
          </div>
          <div className="arb-note-item">
            <span className="arb-note-label">数据源</span>
            <span className="arb-note-value">akshare</span>
            <span className="arb-note-desc">bond_zh_hs_cov_spot + bond_zh_cov + bond_cb_redeem_jsl，无需集思录登录</span>
          </div>
        </div>
        <ul style={{ marginTop: '8px', fontSize: '13px', lineHeight: 1.9 }}>
          <li><strong>到期赎回价</strong>由单只债条款正则解析（含最后一期利息），解析失败则该债税后保本价置空、不进入钝化区。</li>
          <li><strong>强赎状态</strong>来自集思录强赎表，已公告强赎的标的从双条件精选剔除，避免被低价赎回。</li>
          <li><strong>信用风险</strong>：本表按「债底已定价」逻辑筛选，但低评级（如 A+ 及以下）标的仍需单独核查违约风险。</li>
          <li><strong>非买卖建议</strong>：本页为筛选工具，具体买卖决策请结合正股基本面与自身风险承受能力。</li>
        </ul>
      </div>
    </div>
  )
}
