import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { fundApi } from '../services/api'
import { PageSection, TabBar, StatCard, StatCardGroup, DataTable, LoadingSpinner, EmptyState } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

// ============ 共享类型 ============

interface FundEst {
  fund_code: string; fund_name: string; fund_price: number; fund_change_pct: number
  underlying_code: string; underlying_price: number; underlying_change_pct: number
  est_nav: number; premium: number; official_nav: number; official_nav_date: string
  underlying_type?: string; is_multi_underlying?: boolean
  holdings_detail?: Array<{ stock_code: string; stock_name: string; sina_code: string; weight: number; price: number; change_pct: number }>
}

interface AShareFund {
  fund_code: string; fund_name: string; fund_price: number; fund_change_pct: number
  underlying_type: string; underlying_code: string
}

interface FundEstDetail {
  fund_code: string; fund_name: string; est_nav: number; est_nav_traditional: number
  a_share_price: number; a_share_change_pct: number; premium_pct: number
  official_nav: number; official_nav_date: string
  underlying_code: string; underlying_name: string; underlying_price: number
  underlying_prev_close: number; underlying_change_pct: number
  underlying_open: number; underlying_high: number; underlying_low: number
  usdcny_rate: number; hkdcny_rate: number; position_ratio: number; calibration: number
  price_ratio: number; calculation_method: string; market_status: string
}

interface ArbCheck { name: string; value: string; pass: boolean; severity: 'critical' | 'warning' | 'info'; note: string }
interface HoldingDetail { code: string; name: string; weight: number; price: number; change_pct: number }
interface TFeeInfo { commission_pct: number; transfer_fee_pct: number; round_trip_fee_pct: number; slippage_pct: number; total_cost_pct: number; min_trade_amount: number }
interface TRiskInfo { stop_loss_pct: number; take_profit_pct: number; max_position_wan: number; expected_profit_pct: number; risk_reward_ratio: number }
interface TFactors { underlying_confirm: boolean | null; premium_level: string; volume_level: string; est_nav: number; premium_pct: number; underlying_change_pct: number; turnover_wan: number }
interface TOpportunity {
  fund_code: string; fund_name: string; open_price: number; prev_close: number; current_price: number
  open_change_pct: number; current_change_pct?: number; signal: string; strength: string
  probability: number; base_probability?: number; action: string; reason: string; verdict?: string
  fee?: TFeeInfo; risk?: TRiskInfo; factors?: TFactors; probability_adjustments?: { factor: string; delta: number }[]
}
interface FeeBreakdown { apply_fee: number; redeem_fee: number; trade_commission: number; transfer_fee: number; total_fee: number }
interface ArbEval {
  verdict: string; direction: string; checks: ArbCheck[]; net_profit: number; gross_profit: number
  fee_breakdown?: FeeBreakdown; settlement_risk?: number; risk_adjusted_profit?: number
  slippage_est?: number; max_position_wan?: number
}

interface FundArb {
  fund_code: string; fund_name: string; fund_price: number; fund_change_pct: number
  official_nav: number; official_nav_date: string
  est_nav_official: number; est_nav_cal: number; est_nav: number; est_confidence: string
  est_change_official: string; est_time_official: string
  underlying_code: string; underlying_name: string; underlying_type: string
  underlying_price: number; underlying_change_pct: number
  premium_pct: number; premium_official: number; premium_cal: number
  is_multi_underlying: boolean; holdings_detail: HoldingDetail[]
  turnover: number; amount: number; apply_status: string; apply_limit: string
  direction: string; arb_eval: ArbEval | null
  apply_fee?: string; redeem_fee?: string
}

interface ScanResult {
  funds: FundArb[]
  stats: { total_funds: number; filtered_count: number; avg_premium: number; max_premium: number; min_premium: number; premium_count: number; discount_count: number }
  data_source: string; market_status: string; usdcny_rate: number
}

type TabKey = 'estimation' | 'arbitrage' | 'tTrading'

// ============ 共享样式 ============

const selectStyle: React.CSSProperties = {
  padding: '10px 12px', border: '1px solid rgba(148, 163, 184, 0.2)',
  borderRadius: '10px', background: 'rgba(15, 23, 42, 0.8)', color: '#f1f5f9',
  fontSize: '14px', outline: 'none', cursor: 'pointer', minWidth: '120px',
}
const cardStyle: React.CSSProperties = {
  background: 'rgba(15, 23, 42, 0.6)', borderRadius: '12px', padding: '16px',
  border: '1px solid rgba(148, 163, 184, 0.1)',
}
const cardTitleStyle: React.CSSProperties = {
  fontSize: '14px', fontWeight: 600, color: '#f1f5f9', margin: '0 0 12px',
}

// ============ 共享工具函数 ============

const getPremiumColor = (p: number) => p > 5 ? '#ef4444' : p > 2 ? '#f97316' : p > -2 ? '#6b7280' : p > -5 ? '#3b82f6' : '#22c55e'
const getPremiumBg = (p: number) => p > 10 ? 'rgba(239,68,68,0.08)' : p > 5 ? 'rgba(249,115,22,0.06)' : p < -5 ? 'rgba(34,197,94,0.08)' : p < -2 ? 'rgba(59,130,246,0.06)' : 'transparent'
const getPremiumLabel = (p: number) => p > 10 ? '高溢价' : p > 5 ? '溢价' : p > 2 ? '小溢价' : p > -2 ? '合理' : p > -5 ? '小折价' : '折价'
const getPremiumTagColor = (p: number) => {
  if (p > 5) return { bg: 'rgba(239,68,68,0.15)', color: '#ef4444', border: 'rgba(239,68,68,0.3)' }
  if (p > 2) return { bg: 'rgba(249,115,22,0.15)', color: '#f97316', border: 'rgba(249,115,22,0.3)' }
  if (p > -2) return { bg: 'rgba(107,114,128,0.15)', color: '#6b7280', border: 'rgba(107,114,128,0.3)' }
  if (p > -5) return { bg: 'rgba(59,130,246,0.15)', color: '#3b82f6', border: 'rgba(59,130,246,0.3)' }
  return { bg: 'rgba(34,197,94,0.15)', color: '#22c55e', border: 'rgba(34,197,94,0.3)' }
}
const getVerdictColor = (v: string) => v === '可以套利' ? '#22c55e' : v === '谨慎套利' ? '#f97316' : '#ef4444'
const getVerdictBg = (v: string) => v === '可以套利' ? 'rgba(34,197,94,0.15)' : v === '谨慎套利' ? 'rgba(249,115,22,0.15)' : 'rgba(239,68,68,0.15)'

// 信心等级标签
const getConfidenceLabel = (c: string) => {
  if (c === 'high') return { text: '高可信', color: '#22c55e', bg: 'rgba(34,197,94,0.15)' }
  if (c === 'medium') return { text: '中等', color: '#f97316', bg: 'rgba(249,115,22,0.15)' }
  if (c === 'low') return { text: '低可信', color: '#ef4444', bg: 'rgba(239,68,68,0.15)' }
  if (c === 'very_low') return { text: '不可信', color: '#991b1b', bg: 'rgba(153,27,27,0.15)' }
  return { text: '未知', color: '#6b7280', bg: 'rgba(107,114,128,0.15)' }
}

// 溢价警报阈值
const PREMIUM_ALERT_HIGH = 5.0   // 高溢价警报
const PREMIUM_ALERT_LOW = -5.0   // 高折价警报

// ============ 主组件 ============

export default function FundArbitragePage() {
  const [activeTab, setActiveTab] = useState<TabKey>('arbitrage')

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', padding: '24px' }}>
      {/* 页面标题 + Tab */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <div style={{
            width: '48px', height: '48px', borderRadius: '12px',
            background: 'linear-gradient(135deg, #22c55e, #3b82f6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px',
          }}>📊</div>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, color: '#f1f5f9', margin: 0 }}>基金套利</h1>
            <p style={{ fontSize: '14px', color: '#94a3b8', margin: '4px 0 0' }}>
              净值估算 · 套利扫描 · 做T机会
            </p>
          </div>
        </div>
        {/* Tab栏 */}
        <div style={{ display: 'flex', gap: '4px', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '12px', padding: '4px', width: 'fit-content' }}>
          {([
            { key: 'estimation' as TabKey, label: '📈 净值估算', desc: '全部基金' },
            { key: 'arbitrage' as TabKey, label: '🎯 套利扫描', desc: '筛选机会' },
            { key: 'tTrading' as TabKey, label: '⚡ 做T机会', desc: 'QDII T+0' },
          ]).map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                padding: '10px 20px', borderRadius: '10px', border: 'none', cursor: 'pointer',
                background: activeTab === tab.key ? 'linear-gradient(135deg, #22c55e, #16a34a)' : 'transparent',
                color: activeTab === tab.key ? '#fff' : '#94a3b8',
                fontWeight: 600, fontSize: '14px', transition: 'all 0.2s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab内容 */}
      {activeTab === 'estimation' && <EstimationTab />}
      {activeTab === 'arbitrage' && <ArbitrageTab />}
      {activeTab === 'tTrading' && <TTradingTab />}
    </div>
  )
}

// ============ Tab 1: 净值估算 ============

const CATEGORY_TABS = [
  { key: 'all', label: '全部' },
  { key: 'us_etf', label: '🇺🇸 美股QDII' },
  { key: 'hk_index', label: '🇭🇰 港股QDII' },
  { key: 'multi', label: '🌐 混合QDII' },
  { key: 'a_share', label: '🇨🇳 A股LOF' },
]

function EstimationTab() {
  const [funds, setFunds] = useState<FundEst[]>([])
  const [aShareFunds, setAShareFunds] = useState<AShareFund[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [usdcnyRate, setUsdcnyRate] = useState(0)
  const [hkdcnyRate, setHkdcnyRate] = useState(0)
  const [filterMinPremium, setFilterMinPremium] = useState(-10)
  const [filterMaxPremium, setFilterMaxPremium] = useState(50)
  const [expandedFund, setExpandedFund] = useState<string | null>(null)
  const [category, setCategory] = useState('all')
  const [fundDetail, setFundDetail] = useState<FundEstDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showAlertsOnly, setShowAlertsOnly] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/fund-arb/est-list`)
      setFunds(res.data.funds || [])
      setAShareFunds(res.data.a_share_funds || [])
      setUpdateTime(res.data.update_time || '')
      setUsdcnyRate(res.data.usdcny_rate || 0)
      setHkdcnyRate(res.data.hkdcny_rate || 0)
    } catch (e) { console.error('获取EST数据失败:', e) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // 加载单基金详情
  const loadDetail = useCallback(async (fundCode: string) => {
    setDetailLoading(true)
    setFundDetail(null)
    try {
      const res = await axios.get(`${API_BASE}/fund-arb/est-detail/${fundCode}`, { timeout: 10000 })
      setFundDetail(res.data)
    } catch (e) { console.error('获取详情失败:', e) }
    finally { setDetailLoading(false) }
  }, [])

  // 展开/收起基金详情
  const toggleExpand = useCallback((fundCode: string) => {
    if (expandedFund === fundCode) {
      setExpandedFund(null)
      setFundDetail(null)
    } else {
      setExpandedFund(fundCode)
      loadDetail(fundCode)
    }
  }, [expandedFund, loadDetail])

  // 按分类筛选
  const categoryFiltered = category === 'all' ? funds
    : category === 'a_share' ? []
    : funds.filter(f => f.underlying_type === category)

  let filtered = categoryFiltered.filter(f => f.premium >= filterMinPremium && f.premium <= filterMaxPremium)

  // 溢价警报筛选
  const alertFunds = filtered.filter(f => f.premium >= PREMIUM_ALERT_HIGH || f.premium <= PREMIUM_ALERT_LOW)
  if (showAlertsOnly) {
    filtered = alertFunds
  }
  const stats = {
    total: filtered.length,
    premiumCount: filtered.filter(f => f.premium > 2).length,
    discountCount: filtered.filter(f => f.premium < -2).length,
    avgPremium: filtered.length > 0 ? filtered.reduce((s, f) => s + f.premium, 0) / filtered.length : 0,
    maxPremium: filtered.length > 0 ? Math.max(...filtered.map(f => f.premium)) : 0,
    minPremium: filtered.length > 0 ? Math.min(...filtered.map(f => f.premium)) : 0,
  }

  return (
    <>
      {/* 分类Tab */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', background: 'rgba(15,23,42,0.5)', borderRadius: '12px', padding: '4px', width: 'fit-content' }}>
        {CATEGORY_TABS.map(tab => (
          <button key={tab.key} onClick={() => setCategory(tab.key)} style={{
            padding: '8px 16px', borderRadius: '8px', border: 'none', cursor: 'pointer',
            background: category === tab.key ? 'linear-gradient(135deg,#3b82f6,#2563eb)' : 'transparent',
            color: category === tab.key ? '#fff' : '#94a3b8',
            fontWeight: 600, fontSize: '13px', transition: 'all 0.2s',
          }}>
            {tab.label}
            {tab.key !== 'all' && tab.key !== 'a_share' && (
              <span style={{ marginLeft: '6px', fontSize: '11px', opacity: 0.7 }}>
                ({funds.filter(f => f.underlying_type === tab.key).length})
              </span>
            )}
            {tab.key === 'a_share' && (
              <span style={{ marginLeft: '6px', fontSize: '11px', opacity: 0.7 }}>
                ({aShareFunds.length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* 统计卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {[
          { label: '基金总数', value: stats.total, icon: '📈', color: '#3b82f6' },
          { label: '溢价基金', value: stats.premiumCount, icon: '🔴', color: '#ef4444' },
          { label: '折价基金', value: stats.discountCount, icon: '🟢', color: '#22c55e' },
          { label: '平均溢价', value: `${stats.avgPremium.toFixed(2)}%`, icon: '📊', color: stats.avgPremium > 0 ? '#f97316' : '#3b82f6' },
          { label: '最高溢价', value: `${stats.maxPremium.toFixed(2)}%`, icon: '🔺', color: '#ef4444' },
          { label: '最低溢价', value: `${stats.minPremium.toFixed(2)}%`, icon: '🔻', color: '#22c55e' },
        ].map((s, i) => (
          <div key={i} style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '20px', border: '1px solid rgba(148,163,184,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
              <span style={{ fontSize: '12px', color: '#94a3b8' }}>{s.label}</span>
              <span style={{ fontSize: '18px' }}>{s.icon}</span>
            </div>
            <div style={{ fontSize: '24px', fontWeight: 700, color: s.color }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* 筛选 + 刷新 */}
      <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '20px', marginBottom: '24px', border: '1px solid rgba(148,163,184,0.1)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>溢价率范围</label>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <select value={filterMinPremium} onChange={e => setFilterMinPremium(Number(e.target.value))} style={selectStyle}>
                <option value={-10}>-10%</option><option value={-5}>-5%</option><option value={-2}>-2%</option><option value={0}>0%</option><option value={2}>2%</option>
              </select>
              <span style={{ color: '#64748b' }}>至</span>
              <select value={filterMaxPremium} onChange={e => setFilterMaxPremium(Number(e.target.value))} style={selectStyle}>
                <option value={10}>10%</option><option value={20}>20%</option><option value={50}>50%</option><option value={100}>100%</option>
              </select>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { label: '全部', min: -10, max: 100 },
              { label: '高溢价', min: 5, max: 100 },
              { label: '套利机会', min: 2, max: 100 },
              { label: '折价', min: -100, max: -2 },
            ].map((btn, i) => (
              <button key={i} onClick={() => { setFilterMinPremium(btn.min); setFilterMaxPremium(btn.max) }} style={{
                padding: '10px 16px', borderRadius: '10px', border: '1px solid rgba(148,163,184,0.2)', cursor: 'pointer', fontSize: '13px', fontWeight: 500,
                background: filterMinPremium === btn.min && filterMaxPremium === btn.max ? 'linear-gradient(135deg,#3b82f6,#2563eb)' : 'rgba(51,65,85,0.5)',
                color: filterMinPremium === btn.min && filterMaxPremium === btn.max ? '#fff' : '#94a3b8',
              }}>{btn.label}</button>
            ))}
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: '#64748b' }}>💱 USD/CNY {usdcnyRate.toFixed(4)}</span>
            {hkdcnyRate > 0 && <span style={{ fontSize: '12px', color: '#64748b' }}>HKD/CNY {hkdcnyRate.toFixed(4)}</span>}
            {alertFunds.length > 0 && (
              <button onClick={() => setShowAlertsOnly(!showAlertsOnly)} style={{
                padding: '6px 12px', borderRadius: '8px', border: `1px solid ${showAlertsOnly ? 'rgba(239,68,68,0.3)' : 'rgba(148,163,184,0.2)'}`,
                background: showAlertsOnly ? 'rgba(239,68,68,0.1)' : 'rgba(51,65,85,0.5)',
                color: showAlertsOnly ? '#ef4444' : '#94a3b8', cursor: 'pointer', fontSize: '12px', fontWeight: 600,
              }}>
                🔔 溢价警报 ({alertFunds.length})
              </button>
            )}
            <span style={{ fontSize: '12px', color: '#64748b' }}>🕐 {updateTime || '--'}</span>
            <button onClick={loadData} disabled={loading} style={{
              padding: '10px 20px', background: loading ? '#374151' : 'linear-gradient(135deg,#3b82f6,#2563eb)',
              color: '#fff', border: 'none', borderRadius: '10px', cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: '14px',
            }}>{loading ? '⏳ 加载中...' : '🔄 刷新'}</button>
          </div>
        </div>
      </div>

      {/* 数据表格 */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px', background: 'rgba(30,41,59,0.8)', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.1)' }}>
          <div style={{ width: '48px', height: '48px', border: '3px solid rgba(59,130,246,0.2)', borderTopColor: '#3b82f6', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '16px' }} />
          <p style={{ color: '#94a3b8' }}>正在加载基金数据...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : (
        <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.1)', overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 100px 100px 120px 100px 100px 100px 120px', gap: '1px', padding: '16px 20px', background: 'rgba(15,23,42,0.8)', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
            {['代码', '名称', '场内价', '涨跌幅', '底层资产', '底层涨跌', 'EST净值', '溢价率', '官方净值'].map((h, i) => (
              <div key={i} style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>{h}</div>
            ))}
          </div>
          {filtered.length > 0 ? (
            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {filtered.map(fund => {
                const tag = getPremiumTagColor(fund.premium)
                const isExpanded = expandedFund === fund.fund_code
                const isAlert = fund.premium >= PREMIUM_ALERT_HIGH || fund.premium <= PREMIUM_ALERT_LOW
                return (
                  <div key={fund.fund_code}>
                    <div
                      style={{
                        display: 'grid', gridTemplateColumns: '100px 1fr 100px 100px 120px 100px 100px 100px 120px', gap: '1px', padding: '14px 20px',
                        background: isAlert ? (fund.premium > 0 ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)') : getPremiumBg(fund.premium),
                        borderBottom: '1px solid rgba(148,163,184,0.05)', cursor: 'pointer',
                        borderLeft: isAlert ? `3px solid ${fund.premium > 0 ? '#ef4444' : '#22c55e'}` : '3px solid transparent',
                      }}
                      onClick={() => toggleExpand(fund.fund_code)}
                    >
                      <div style={{ fontSize: '14px', fontWeight: 600, color: '#e2e8f0', fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {isAlert && <span style={{ fontSize: '10px' }}>🔔</span>}
                        {fund.fund_code}
                      </div>
                      <div>
                        <div style={{ fontSize: '14px', color: '#f1f5f9', fontWeight: 500 }}>{fund.fund_name}</div>
                        {fund.is_multi_underlying && <span style={{ fontSize: '10px', padding: '2px 6px', background: 'rgba(139,92,246,0.2)', color: '#a78bfa', borderRadius: '4px' }}>多标的</span>}
                      </div>
                      <div style={{ fontSize: '15px', fontWeight: 600, color: '#f1f5f9', fontFamily: 'monospace' }}>{fund.fund_price?.toFixed(3) ?? '--'}</div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: fund.fund_change_pct >= 0 ? '#ef4444' : '#22c55e', fontFamily: 'monospace' }}>{fund.fund_change_pct >= 0 ? '+' : ''}{fund.fund_change_pct?.toFixed(2) ?? '--'}%</div>
                      <div style={{ fontSize: '12px', color: '#94a3b8', fontFamily: 'monospace' }}>{fund.is_multi_underlying ? '📊 加权' : fund.underlying_code}</div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: fund.underlying_change_pct >= 0 ? '#ef4444' : '#22c55e', fontFamily: 'monospace' }}>{fund.underlying_change_pct >= 0 ? '+' : ''}{fund.underlying_change_pct.toFixed(2)}%</div>
                      <div style={{ fontSize: '15px', fontWeight: 700, color: '#3b82f6', fontFamily: 'monospace' }}>{fund.est_nav.toFixed(4)}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '15px', fontWeight: 700, color: getPremiumColor(fund.premium), fontFamily: 'monospace' }}>{fund.premium > 0 ? '+' : ''}{fund.premium.toFixed(2)}%</span>
                        <span style={{ fontSize: '10px', padding: '2px 6px', background: tag.bg, color: tag.color, border: `1px solid ${tag.border}`, borderRadius: '4px' }}>{getPremiumLabel(fund.premium)}</span>
                      </div>
                      <div>
                        <div style={{ fontSize: '14px', fontWeight: 500, color: '#e2e8f0', fontFamily: 'monospace' }}>{fund.official_nav.toFixed(4)}</div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{fund.official_nav_date || ''}</div>
                      </div>
                    </div>
                    {isExpanded && (
                      <div style={{ padding: '16px 20px', background: 'rgba(15,23,42,0.6)', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
                        {detailLoading ? (
                          <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8' }}>加载详情中...</div>
                        ) : fundDetail && fundDetail.fund_code === fund.fund_code ? (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                            {/* 计算过程 */}
                            <div style={cardStyle}>
                              <h4 style={cardTitleStyle}>📐 净值计算（动态比率法）</h4>
                              <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                                <div>官方净值: <b>{fundDetail.official_nav.toFixed(4)}</b> ({fundDetail.official_nav_date})</div>
                                <div>底层资产: {fundDetail.underlying_name} ({fundDetail.underlying_code})</div>
                                <div>底层当前价: <b>${fundDetail.underlying_price.toFixed(2)}</b></div>
                                <div>底层昨收: <b>${fundDetail.underlying_prev_close.toFixed(2)}</b></div>
                                <div>价格比: <b>{fundDetail.price_ratio.toFixed(6)}</b></div>
                                <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(59,130,246,0.1)', borderRadius: '6px' }}>
                                  实时EST = {fundDetail.official_nav.toFixed(4)} × {fundDetail.price_ratio.toFixed(6)} = <b style={{ color: '#3b82f6' }}>{fundDetail.est_nav.toFixed(4)}</b>
                                </div>
                                <div style={{ padding: '8px', background: 'rgba(139,92,246,0.1)', borderRadius: '6px' }}>
                                  参考EST = <b style={{ color: '#8b5cf6' }}>{fundDetail.est_nav_traditional.toFixed(4)}</b> (校准值法)
                                </div>
                                <div>校准值: {fundDetail.calibration.toFixed(6)}</div>
                                <div>仓位比例: {(fundDetail.position_ratio * 100).toFixed(0)}%</div>
                                <div>汇率: USD/CNY {fundDetail.usdcny_rate.toFixed(4)}</div>
                                {(fundDetail as any).hkdcny_rate > 0 && <div>汇率: HKD/CNY {(fundDetail as any).hkdcny_rate.toFixed(4)}</div>}
                              </div>
                            </div>
                            {/* 底层资产行情 */}
                            <div style={cardStyle}>
                              <h4 style={cardTitleStyle}>📈 底层资产行情</h4>
                              <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                                <div>开盘: <b>${fundDetail.underlying_open.toFixed(2)}</b></div>
                                <div>最高: <b style={{ color: '#ef4444' }}>${fundDetail.underlying_high.toFixed(2)}</b></div>
                                <div>最低: <b style={{ color: '#22c55e' }}>${fundDetail.underlying_low.toFixed(2)}</b></div>
                                <div>当前: <b>${fundDetail.underlying_price.toFixed(2)}</b></div>
                                <div>昨收: <b>${fundDetail.underlying_prev_close.toFixed(2)}</b></div>
                                <div>涨跌: <b style={{ color: fundDetail.underlying_change_pct >= 0 ? '#ef4444' : '#22c55e' }}>{fundDetail.underlying_change_pct >= 0 ? '+' : ''}{fundDetail.underlying_change_pct.toFixed(2)}%</b></div>
                              </div>
                            </div>
                            {/* 溢价信息 */}
                            <div style={cardStyle}>
                              <h4 style={cardTitleStyle}>💰 溢价分析</h4>
                              <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                                <div>场内价格: <b>{fund.fund_price.toFixed(3)}</b> ({fund.fund_change_pct >= 0 ? '+' : ''}{fund.fund_change_pct.toFixed(2)}%)</div>
                                <div>实时EST: <b style={{ color: '#3b82f6' }}>{fundDetail.est_nav.toFixed(4)}</b></div>
                                <div>溢价率: <b style={{ color: getPremiumColor(fundDetail.premium_pct) }}>{fundDetail.premium_pct >= 0 ? '+' : ''}{fundDetail.premium_pct.toFixed(2)}%</b></div>
                                <div>市场状态: {fundDetail.market_status}</div>
                              </div>
                            </div>
                            {/* 多标的持仓 */}
                            {fund.is_multi_underlying && fund.holdings_detail && fund.holdings_detail.length > 0 && (
                              <div style={cardStyle}>
                                <h4 style={cardTitleStyle}>📋 持仓明细</h4>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                  {fund.holdings_detail.map((h, i) => (
                                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', padding: '6px 8px', background: 'rgba(30,41,59,0.5)', borderRadius: '6px' }}>
                                      <span style={{ color: '#f1f5f9' }}>{h.stock_name || h.sina_code}</span>
                                      <span style={{ color: '#64748b' }}>{h.weight.toFixed(1)}%</span>
                                      <span style={{ color: h.change_pct >= 0 ? '#ef4444' : '#22c55e' }}>{h.change_pct >= 0 ? '+' : ''}{h.change_pct.toFixed(2)}%</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8' }}>点击加载详情...</div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '60px' }}>
              <span style={{ fontSize: '48px', display: 'block', marginBottom: '16px' }}>📭</span>
              <p style={{ color: '#94a3b8' }}>暂无符合条件的基金数据</p>
            </div>
          )}
        </div>
      )}

      {/* A股LOF参考表 */}
      {(category === 'all' || category === 'a_share') && aShareFunds.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f1f5f9', margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            🇨🇳 A股LOF参考数据
            <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 400 }}>（无EST，仅价格参考）</span>
          </h3>
          <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.1)', overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 100px 100px 100px', gap: '1px', padding: '12px 20px', background: 'rgba(15,23,42,0.8)', borderBottom: '1px solid rgba(148,163,184,0.1)' }}>
              {['代码', '名称', '场内价', '涨跌幅', '类型'].map((h, i) => (
                <div key={i} style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>{h}</div>
              ))}
            </div>
            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              {aShareFunds.map(fund => (
                <div key={fund.fund_code} style={{ display: 'grid', gridTemplateColumns: '100px 1fr 100px 100px 100px', gap: '1px', padding: '12px 20px', borderBottom: '1px solid rgba(148,163,184,0.05)' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', fontFamily: 'monospace' }}>{fund.fund_code}</div>
                  <div style={{ fontSize: '13px', color: '#f1f5f9' }}>{fund.fund_name}</div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: '#f1f5f9', fontFamily: 'monospace' }}>{fund.fund_price.toFixed(3)}</div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: fund.fund_change_pct >= 0 ? '#ef4444' : '#22c55e', fontFamily: 'monospace' }}>{fund.fund_change_pct >= 0 ? '+' : ''}{fund.fund_change_pct.toFixed(2)}%</div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>{fund.underlying_type === 'a_index' ? '指数' : '主动'}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ============ Tab 2: 套利扫描 ============

function ArbitrageTab() {
  const [data, setData] = useState<ScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [minPremium, setMinPremium] = useState(2.0)
  const [minAmount, setMinAmount] = useState(1000)
  const [direction, setDirection] = useState('all')
  const [holdingDays, setHoldingDays] = useState(30)
  const [expandedFund, setExpandedFund] = useState<string | null>(null)
  const [showDiscipline, setShowDiscipline] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(30)
  const [lastRefresh, setLastRefresh] = useState('')

  // 集思录登录
  const [jisiluLoggedIn, setJisiluLoggedIn] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState('')

  useEffect(() => { fundApi.getLoginStatus().then(r => setJisiluLoggedIn(r.data.logged_in)).catch(() => {}) }, [])

  const handleLogin = async () => {
    if (!loginUser || !loginPass) return
    setLoginLoading(true); setLoginError('')
    try {
      await fundApi.login(loginUser, loginPass)
      setJisiluLoggedIn(true); setShowLogin(false); setLoginUser(''); setLoginPass('')
      scanArbitrage()
    } catch (e: any) { setLoginError(e.response?.data?.detail || '登录失败') }
    finally { setLoginLoading(false) }
  }

  const scanArbitrage = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/fund-arb/scan`, { params: { min_premium: minPremium, min_amount: minAmount, direction, holding_days: holdingDays } })
      setData(res.data); setLastRefresh(new Date().toLocaleTimeString())
    } catch (e) { console.error('扫描失败:', e) }
    finally { setLoading(false) }
  }, [minPremium, minAmount, direction, holdingDays])

  useEffect(() => { scanArbitrage() }, [scanArbitrage])

  useEffect(() => {
    if (!autoRefresh) return
    const t = setInterval(scanArbitrage, refreshInterval * 1000)
    return () => clearInterval(t)
  }, [autoRefresh, refreshInterval, scanArbitrage])

  return (
    <>
      {/* 集思录状态 + 操作栏 */}
      <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '20px', marginBottom: '24px', border: '1px solid rgba(148,163,184,0.1)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>最低溢价率(%)</label>
            <select value={minPremium} onChange={e => setMinPremium(Number(e.target.value))} style={selectStyle}>
              <option value={1}>1%</option><option value={2}>2%</option><option value={3}>3%</option><option value={5}>5%</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>最低成交额(万)</label>
            <select value={minAmount} onChange={e => setMinAmount(Number(e.target.value))} style={selectStyle}>
              <option value={300}>300万</option><option value={1000}>1000万</option><option value={3000}>3000万</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>套利方向</label>
            <select value={direction} onChange={e => setDirection(e.target.value)} style={selectStyle}>
              <option value="all">全部</option><option value="溢价">溢价套利</option><option value="折价">折价套利</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '6px' }}>持有天数</label>
            <select value={holdingDays} onChange={e => setHoldingDays(Number(e.target.value))} style={selectStyle}>
              <option value={7}>7天</option><option value={30}>30天</option><option value={365}>365天</option>
            </select>
          </div>
          <button onClick={() => setShowDiscipline(!showDiscipline)} style={{ padding: '10px 16px', background: showDiscipline ? 'rgba(139,92,246,0.2)' : 'rgba(51,65,85,0.5)', color: showDiscipline ? '#a78bfa' : '#94a3b8', border: '1px solid rgba(148,163,184,0.2)', borderRadius: '10px', cursor: 'pointer', fontSize: '13px' }}>📖 套利纪律</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button onClick={() => setAutoRefresh(!autoRefresh)} style={{ padding: '10px 16px', background: autoRefresh ? 'rgba(34,197,94,0.2)' : 'rgba(51,65,85,0.5)', color: autoRefresh ? '#4ade80' : '#94a3b8', border: `1px solid ${autoRefresh ? 'rgba(34,197,94,0.3)' : 'rgba(148,163,184,0.2)'}`, borderRadius: '10px', cursor: 'pointer', fontSize: '13px' }}>{autoRefresh ? '⏸ 暂停' : '▶ 自动刷新'}</button>
            {autoRefresh && <select value={refreshInterval} onChange={e => setRefreshInterval(Number(e.target.value))} style={{ ...selectStyle, minWidth: '80px' }}><option value={15}>15秒</option><option value={30}>30秒</option><option value={60}>60秒</option></select>}
            {lastRefresh && <span style={{ fontSize: '11px', color: '#64748b' }}>最后刷新: {lastRefresh}</span>}
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            <button onClick={scanArbitrage} disabled={loading} style={{ padding: '10px 20px', background: loading ? '#374151' : 'linear-gradient(135deg,#22c55e,#16a34a)', color: '#fff', border: 'none', borderRadius: '10px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '14px' }}>{loading ? '⏳ 扫描中...' : '🔄 刷新'}</button>
            {!jisiluLoggedIn && <button onClick={() => setShowLogin(!showLogin)} style={{ padding: '10px 20px', background: 'linear-gradient(135deg,#8b5cf6,#7c3aed)', color: '#fff', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: 600, fontSize: '14px' }}>🔐 登录集思录</button>}
          </div>
        </div>
        {/* 登录状态 */}
        <div style={{ marginTop: '12px', fontSize: '12px', color: '#94a3b8' }}>
          {jisiluLoggedIn ? <span style={{ color: '#4ade80' }}>● 集思录已登录</span> : <span style={{ color: '#f97316' }}>○ 未登录(数据可能不全)</span>}
          {data?.data_source && <span style={{ marginLeft: '16px' }}>数据源: {data.data_source}</span>}
        </div>
      </div>

      {/* 集思录登录表单 */}
      {showLogin && !jisiluLoggedIn && (
        <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '20px', marginBottom: '24px', border: '1px solid rgba(139,92,246,0.3)' }}>
          <div style={{ fontSize: '15px', fontWeight: 600, color: '#a78bfa', marginBottom: '16px' }}>🔐 登录集思录获取完整数据</div>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <input type="text" placeholder="手机号/用户名" value={loginUser} onChange={e => setLoginUser(e.target.value)} style={{ padding: '10px 14px', borderRadius: '10px', border: '1px solid rgba(148,163,184,0.2)', background: 'rgba(15,23,42,0.8)', color: '#f1f5f9', fontSize: '14px', outline: 'none', minWidth: '200px' }} />
            <input type="password" placeholder="密码" value={loginPass} onChange={e => setLoginPass(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleLogin()} style={{ padding: '10px 14px', borderRadius: '10px', border: '1px solid rgba(148,163,184,0.2)', background: 'rgba(15,23,42,0.8)', color: '#f1f5f9', fontSize: '14px', outline: 'none', minWidth: '200px' }} />
            <button onClick={handleLogin} disabled={loginLoading} style={{ padding: '10px 20px', background: loginLoading ? '#374151' : 'linear-gradient(135deg,#8b5cf6,#7c3aed)', color: '#fff', border: 'none', borderRadius: '10px', cursor: loginLoading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '14px' }}>{loginLoading ? '登录中...' : '登录'}</button>
          </div>
          {loginError && <div style={{ color: '#ef4444', fontSize: '13px', marginTop: '12px' }}>{loginError}</div>}
        </div>
      )}

      {/* 市场概览 */}
      {data?.stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          {[
            { label: '套利机会', value: `${data.stats.filtered_count}只`, icon: '🎯', color: '#22c55e' },
            { label: '溢价基金', value: `${data.stats.premium_count}只`, icon: '🔴', color: '#ef4444' },
            { label: '折价基金', value: `${data.stats.discount_count}只`, icon: '🟢', color: '#22c55e' },
            { label: '平均溢价', value: `${data.stats.avg_premium}%`, icon: '📊', color: data.stats.avg_premium > 0 ? '#f97316' : '#3b82f6' },
            { label: '最高溢价', value: `${data.stats.max_premium}%`, icon: '🔺', color: '#ef4444' },
            { label: '数据源', value: data.data_source, icon: '📡', color: '#8b5cf6' },
          ].map((s, i) => (
            <div key={i} style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '20px', border: '1px solid rgba(148,163,184,0.1)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>{s.label}</span>
                <span style={{ fontSize: '18px' }}>{s.icon}</span>
              </div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: s.color }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* 套利纪律手册 */}
      {showDiscipline && (
        <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '24px', marginBottom: '24px', border: '1px solid rgba(139,92,246,0.3)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#a78bfa', margin: '0 0 16px' }}>📖 套利纪律手册</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            <DisciplineCard title="🔴 溢价套利" color="#ef4444" steps={['T日: 场外申购（按净值）', 'T+2日: 份额到账，转托管至场内', 'T+3日: 场内卖出（按市价）', '收益 = 溢价率 - 申购费 - 转托管费(0.01%) - 佣金(0.03%)']} />
            <DisciplineCard title="🟢 折价套利" color="#22c55e" steps={['T日: 场内买入（按市价）', '转托管至场外', '场外赎回（按净值）', '收益 = 折价率 - 赎回费 - 转托管费(0.01%) - 佣金(0.03%)', '注意: 刚买入赎回费1.5%，需已持有基金']} />
            <DisciplineCard title="⚠️ 赎回费率表" color="#f97316" steps={['< 7天: 1.5%（禁止套利！）', '7~30天: 0.5%', '30~365天: 0.25%', '365~730天: 0.10%', '≥ 730天: 0%']} />
            <DisciplineCard title="⚠️ T+2结算风险" color="#f97316" steps={['美股QDII: 结算期波动±2.5%', '港股QDII: 结算期波动±2.0%', '期货QDII: 结算期波动±3.3%', '溢价率需 > 结算风险才有安全边际']} />
            <DisciplineCard title="💡 纪律要点" color="#3b82f6" steps={['溢价率绝对值 ≥ 2%', '成交额建议 ≥ 1000万', '确认申购状态正常', '单笔不超过日均成交额5%', '考虑T+2结算风险后的风险调整收益>0', '避免市场剧烈波动期套利']} />
          </div>
        </div>
      )}

      {/* 套利机会列表 */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px', background: 'rgba(30,41,59,0.8)', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.1)' }}>
          <div style={{ width: '48px', height: '48px', border: '3px solid rgba(34,197,94,0.2)', borderTopColor: '#22c55e', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '16px' }} />
          <p style={{ color: '#94a3b8' }}>正在扫描全部LOF基金...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {data?.funds && data.funds.length > 0 ? data.funds.map(fund => {
            const eval_ = fund.arb_eval
            const isExpanded = expandedFund === fund.fund_code
            const verdict = eval_?.verdict || '未知'
            const netProfit = eval_?.net_profit ?? 0
            return (
              <div key={fund.fund_code} style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', border: `1px solid ${verdict === '可以套利' ? 'rgba(34,197,94,0.3)' : verdict === '谨慎套利' ? 'rgba(249,115,22,0.2)' : 'rgba(148,163,184,0.1)'}`, overflow: 'hidden' }}>
                <div style={{ padding: '20px', cursor: 'pointer' }} onClick={() => setExpandedFund(isExpanded ? null : fund.fund_code)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                        <span style={{ fontSize: '16px', fontWeight: 700, color: '#f1f5f9' }}>{fund.fund_name}</span>
                        <span style={{ fontSize: '13px', color: '#64748b', fontFamily: 'monospace' }}>{fund.fund_code}</span>
                        {fund.is_multi_underlying && <span style={{ fontSize: '10px', padding: '2px 6px', background: 'rgba(139,92,246,0.2)', color: '#a78bfa', borderRadius: '4px' }}>多标的</span>}
                      </div>
                      <div style={{ display: 'flex', gap: '16px', fontSize: '13px', color: '#94a3b8', flexWrap: 'wrap' }}>
                        <span>场内 <b style={{ color: '#f1f5f9' }}>{fund.fund_price?.toFixed(3) ?? '--'}</b></span>
                        <span>官方EST <b style={{ color: '#f97316' }}>{fund.est_nav_official > 0 ? fund.est_nav_official?.toFixed(4) : '--'}</b></span>
                        <span>参考EST <b style={{ color: '#8b5cf6' }}>{fund.est_nav_cal > 0 ? fund.est_nav_cal?.toFixed(4) : '--'}</b></span>
                        <span>实时EST <b style={{ color: '#3b82f6' }}>{fund.est_nav?.toFixed(4) ?? '--'}</b></span>
                        <span style={{ color: getPremiumColor(fund.premium_pct), fontWeight: 700 }}>溢价 {fund.premium_pct >= 0 ? '+' : ''}{fund.premium_pct?.toFixed(2) ?? '--'}%</span>
                        <span>底层 {fund.underlying_name} <b style={{ color: fund.underlying_change_pct >= 0 ? '#ef4444' : '#22c55e' }}>{fund.underlying_change_pct >= 0 ? '+' : ''}{fund.underlying_change_pct?.toFixed(2) ?? '--'}%</b></span>
                        <span>成交额 <b style={{ color: '#f1f5f9' }}>{fund.turnover > 0 ? `${fund.turnover.toFixed(0)}万` : '--'}</b></span>
                      </div>
                    </div>
                    <div style={{ padding: '8px 16px', borderRadius: '10px', background: getVerdictBg(verdict), border: `1px solid ${getVerdictColor(verdict)}30` }}>
                      <div style={{ fontSize: '14px', fontWeight: 700, color: getVerdictColor(verdict) }}>{verdict}</div>
                      <div style={{ fontSize: '12px', color: '#94a3b8', textAlign: 'center' }}>净收益 {netProfit >= 0 ? '+' : ''}{netProfit.toFixed(2)}%</div>
                      {eval_?.risk_adjusted_profit != null && (
                        <div style={{ fontSize: '11px', color: eval_.risk_adjusted_profit >= 0 ? '#4ade80' : '#f87171', textAlign: 'center' }}>
                          风险调整 {eval_.risk_adjusted_profit >= 0 ? '+' : ''}{eval_.risk_adjusted_profit.toFixed(2)}%
                        </div>
                      )}
                    </div>
                  </div>
                  {eval_?.checks && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {eval_.checks.filter(c => c.severity !== 'info').map((check, i) => (
                        <span key={i} style={{ fontSize: '11px', padding: '4px 10px', borderRadius: '6px', background: check.pass ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)', color: check.pass ? '#4ade80' : '#f87171', border: `1px solid ${check.pass ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
                          {check.pass ? '✅' : '❌'} {check.name}: {check.value}
                        </span>
                      ))}
                    </div>
                  )}
                  {fund.is_multi_underlying && fund.holdings_detail.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px' }}>
                      {fund.holdings_detail.map((h, i) => (
                        <span key={i} style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '6px', background: 'rgba(51,65,85,0.5)', color: '#94a3b8' }}>
                          {h.name.replace(' ETF', '')} <b style={{ color: h.change_pct >= 0 ? '#ef4444' : '#22c55e' }}>{h.change_pct >= 0 ? '+' : ''}{h.change_pct.toFixed(2)}%</b>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                {isExpanded && (
                  <div style={{ padding: '0 20px 20px', borderTop: '1px solid rgba(148,163,184,0.1)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '16px' }}>
                      <div style={cardStyle}>
                        <h4 style={cardTitleStyle}>📐 三种EST对比</h4>
                        <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                          <div>官方净值: <b>{fund.official_nav.toFixed(4)}</b> ({fund.official_nav_date})</div>
                          <div>底层: {fund.underlying_name} ({fund.underlying_code})</div>
                          <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(249,115,22,0.1)', borderRadius: '6px' }}>官方EST: <b style={{ color: '#f97316' }}>{fund.est_nav_official > 0 ? fund.est_nav_official.toFixed(4) : '--'}</b> <span style={{ color: getPremiumColor(fund.premium_official), marginLeft: '8px' }}>{fund.premium_official >= 0 ? '+' : ''}{fund.premium_official.toFixed(2)}%</span></div>
                          <div style={{ padding: '8px', background: 'rgba(139,92,246,0.1)', borderRadius: '6px' }}>参考EST: <b style={{ color: '#8b5cf6' }}>{fund.est_nav_cal > 0 ? fund.est_nav_cal.toFixed(4) : '--'}</b> <span style={{ color: getPremiumColor(fund.premium_cal), marginLeft: '8px' }}>{fund.premium_cal >= 0 ? '+' : ''}{fund.premium_cal.toFixed(2)}%</span></div>
                          <div style={{ padding: '8px', background: 'rgba(59,130,246,0.1)', borderRadius: '6px' }}>实时EST: <b style={{ color: '#3b82f6' }}>{fund.est_nav.toFixed(4)}</b> <span style={{ color: getPremiumColor(fund.premium_pct), marginLeft: '8px' }}>{fund.premium_pct >= 0 ? '+' : ''}{fund.premium_pct.toFixed(2)}%</span></div>
                          <div>可信度: <b style={{ color: getConfidenceLabel(fund.est_confidence).color }}>{getConfidenceLabel(fund.est_confidence).text}</b></div>
                        </div>
                      </div>
                      {eval_?.checks && (
                        <div style={cardStyle}>
                          <h4 style={cardTitleStyle}>📋 纪律检查</h4>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {eval_.checks.map((check, i) => (
                              <div key={i} style={{ padding: '10px', borderRadius: '8px', background: check.pass ? 'rgba(34,197,94,0.05)' : 'rgba(239,68,68,0.05)', border: `1px solid ${check.pass ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)'}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#f1f5f9' }}>{check.pass ? '✅' : '❌'} {check.name}</span>
                                  <span style={{ fontSize: '13px', color: check.pass ? '#4ade80' : '#f87171' }}>{check.value}</span>
                                </div>
                                <div style={{ fontSize: '11px', color: '#64748b' }}>{check.note}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      <div style={cardStyle}>
                        <h4 style={cardTitleStyle}>{eval_?.direction === 'premium' ? '🔴 溢价套利步骤' : eval_?.direction === 'discount' ? '🟢 折价套利步骤' : '📊 套利建议'}</h4>
                        {eval_?.direction === 'premium' ? (
                          <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                            <div>1. 场外申购（按净值 {fund.official_nav.toFixed(4)}）</div><div>2. 等待T+2日份额到账</div><div>3. 转托管至场内</div><div>4. 场内卖出（按市价 {fund.fund_price.toFixed(3)}）</div>
                            <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(34,197,94,0.1)', borderRadius: '6px' }}><b>预估净收益: {netProfit >= 0 ? '+' : ''}{netProfit.toFixed(2)}%</b></div>
                          </div>
                        ) : eval_?.direction === 'discount' ? (
                          <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                            <div>1. 场内买入（按市价 {fund.fund_price.toFixed(3)}）</div><div>2. 转托管至场外</div><div>3. 场外赎回（按净值 {fund.official_nav.toFixed(4)}）</div>
                            <div style={{ marginTop: '8px', padding: '8px', background: 'rgba(34,197,94,0.1)', borderRadius: '6px' }}><b>预估净收益: {netProfit >= 0 ? '+' : ''}{netProfit.toFixed(2)}%</b></div>
                          </div>
                        ) : <div style={{ fontSize: '13px', color: '#94a3b8' }}>溢价率不足，暂无套利机会</div>}
                      </div>
                      {/* 费用分解 */}
                      {eval_?.fee_breakdown && (
                        <div style={cardStyle}>
                          <h4 style={cardTitleStyle}>💸 费用分解</h4>
                          <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                            {eval_.fee_breakdown.apply_fee > 0 && <div>申购费: <b style={{ color: '#f97316' }}>{eval_.fee_breakdown.apply_fee.toFixed(4)}%</b> {fund.apply_fee ? `(${fund.apply_fee})` : ''}</div>}
                            {eval_.fee_breakdown.redeem_fee > 0 && <div>赎回费: <b style={{ color: '#f97316' }}>{eval_.fee_breakdown.redeem_fee.toFixed(4)}%</b> {fund.redeem_fee ? `(${fund.redeem_fee})` : ''}</div>}
                            <div>交易佣金: <b>{eval_.fee_breakdown.trade_commission.toFixed(4)}%</b></div>
                            <div>转托管费: <b>{eval_.fee_breakdown.transfer_fee.toFixed(4)}%</b></div>
                            <div style={{ marginTop: '6px', padding: '8px', background: 'rgba(239,68,68,0.1)', borderRadius: '6px', fontWeight: 600 }}>
                              总费用: <span style={{ color: '#ef4444' }}>{eval_.fee_breakdown.total_fee.toFixed(4)}%</span>
                            </div>
                          </div>
                        </div>
                      )}
                      {/* 风险与仓位 */}
                      <div style={cardStyle}>
                        <h4 style={cardTitleStyle}>⚠️ 风险与仓位</h4>
                        <div style={{ fontSize: '13px', lineHeight: '2', color: '#d1d5db' }}>
                          {eval_?.settlement_risk != null && (
                            <div>T+2结算风险: <b style={{ color: eval_.settlement_risk > 1 ? '#ef4444' : '#f97316' }}>±{eval_.settlement_risk.toFixed(2)}%</b>
                              <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>结算期间底层资产可能波动</span>
                            </div>
                          )}
                          {eval_?.risk_adjusted_profit != null && (
                            <div>风险调整收益: <b style={{ color: eval_.risk_adjusted_profit >= 0 ? '#22c55e' : '#ef4444' }}>{eval_.risk_adjusted_profit >= 0 ? '+' : ''}{eval_.risk_adjusted_profit.toFixed(2)}%</b>
                              <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>扣除结算风险后</span>
                            </div>
                          )}
                          {eval_?.slippage_est != null && eval_.slippage_est > 0 && (
                            <div>预估滑点: <b style={{ color: eval_.slippage_est > 0.05 ? '#f97316' : '#94a3b8' }}>{eval_.slippage_est.toFixed(4)}%</b></div>
                          )}
                          {eval_?.max_position_wan != null && eval_.max_position_wan > 0 && (
                            <div>建议最大仓位: <b style={{ color: '#3b82f6' }}>{eval_.max_position_wan.toFixed(0)}万</b>
                              <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>日均成交额5%</span>
                            </div>
                          )}
                          {fund.turnover > 0 && (
                            <div>日均成交额: <b>{fund.turnover.toFixed(0)}万</b></div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          }) : (
            <div style={{ textAlign: 'center', padding: '60px', background: 'rgba(30,41,59,0.8)', borderRadius: '16px', border: '1px solid rgba(148,163,184,0.1)' }}>
              <span style={{ fontSize: '48px', display: 'block', marginBottom: '16px' }}>📭</span>
              <p style={{ color: '#94a3b8' }}>暂无满足条件的套利机会</p>
            </div>
          )}
        </div>
      )}
    </>
  )
}

// ============ Tab 3: 做T机会 (V2) ============

function TTradingTab() {
  const [opportunities, setOpportunities] = useState<TOpportunity[]>([])
  const [loading, setLoading] = useState(false)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const [backtestData, setBacktestData] = useState<Record<string, any>>({})
  const [backtestLoading, setBacktestLoading] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/fund-arb/t-opportunities`)
      setOpportunities(res.data.opportunities || [])
    } catch (e) { console.error('获取做T机会失败:', e) }
    finally { setLoading(false) }
  }, [])

  const runBacktest = useCallback(async (fundCode: string) => {
    setBacktestLoading(fundCode)
    try {
      const res = await axios.get(`${API_BASE}/fund-arb/t-backtest/${fundCode}?days=60`)
      setBacktestData(prev => ({ ...prev, [fundCode]: res.data }))
    } catch (e) { console.error('回测失败:', e) }
    finally { setBacktestLoading(null) }
  }, [])

  useEffect(() => { load() }, [load])

  const getVerdictColor = (v?: string) => {
    if (v === '强烈推荐') return { bg: 'rgba(239,68,68,0.15)', color: '#ef4444', border: 'rgba(239,68,68,0.3)' }
    if (v === '推荐') return { bg: 'rgba(249,115,22,0.15)', color: '#f97316', border: 'rgba(249,115,22,0.3)' }
    if (v === '谨慎') return { bg: 'rgba(234,179,8,0.15)', color: '#eab308', border: 'rgba(234,179,8,0.3)' }
    return { bg: 'rgba(100,116,139,0.15)', color: '#64748b', border: 'rgba(100,116,139,0.3)' }
  }

  return (
    <>
      <div style={{ background: 'rgba(30,41,59,0.8)', borderRadius: '16px', padding: '24px', marginBottom: '24px', border: '1px solid rgba(249,115,22,0.3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f97316', margin: '0 0 8px' }}>📈 做T机会 V2（多因子 + 费用 + 风控）</h3>
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>
              高开回落：高开2-3%+，回落概率35-75% | 低开反弹：低开-1~-3%+，反弹概率65-70% | 含佣金/滑点/止损/回测
            </div>
          </div>
          <button onClick={load} disabled={loading} style={{ padding: '10px 20px', background: loading ? '#374151' : 'linear-gradient(135deg,#f97316,#ea580c)', color: '#fff', border: 'none', borderRadius: '10px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '14px' }}>{loading ? '⏳' : '🔄 刷新'}</button>
        </div>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>正在扫描...</div>
        ) : opportunities.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {opportunities.map((opp, i) => {
              const isExpanded = expandedIdx === i
              const vc = getVerdictColor(opp.verdict)
              const isHigh = opp.signal === 'high_open_sell'
              const borderColor = isHigh ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'
              const bgColor = isHigh ? 'rgba(239,68,68,0.06)' : 'rgba(34,197,94,0.06)'
              return (
                <div key={i} style={{ borderRadius: '12px', background: bgColor, border: `1px solid ${borderColor}`, overflow: 'hidden' }}>
                  {/* 头部摘要 */}
                  <div style={{ padding: '16px', cursor: 'pointer' }} onClick={() => setExpandedIdx(isExpanded ? null : i)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '15px' }}>{opp.fund_name}</span>
                        <span style={{ fontSize: '12px', color: '#64748b' }}>{opp.fund_code}</span>
                        <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '6px', background: vc.bg, color: vc.color, border: `1px solid ${vc.border}`, fontWeight: 600 }}>{opp.verdict}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        {opp.factors?.est_nav ? (
                          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                            EST: <b style={{ color: '#f1f5f9' }}>{opp.factors.est_nav.toFixed(4)}</b>
                            {opp.factors.premium_pct !== 0 && (
                              <span style={{ color: opp.factors.premium_pct > 0 ? '#ef4444' : '#22c55e', marginLeft: '4px' }}>
                                ({opp.factors.premium_pct > 0 ? '+' : ''}{opp.factors.premium_pct.toFixed(2)}%)
                              </span>
                            )}
                          </span>
                        ) : null}
                        <span style={{ fontSize: '13px', color: isHigh ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                          {opp.open_change_pct >= 0 ? '+' : ''}{opp.open_change_pct}%
                        </span>
                        <span style={{ fontSize: '11px', color: '#64748b' }}>{isExpanded ? '▲' : '▼'}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
                      <span style={{ color: isHigh ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                        {isHigh ? '🔴 高开回落' : '🟢 低开反弹'} ({opp.strength === 'strong' ? '强' : '普通'})
                      </span>
                      <span style={{ color: '#94a3b8' }}>
                        概率: <b style={{ color: '#f1f5f9' }}>{(opp.probability * 100).toFixed(0)}%</b>
                        {opp.base_probability && opp.base_probability !== opp.probability && (
                          <span style={{ color: '#64748b' }}> (基础{(opp.base_probability * 100).toFixed(0)}%)</span>
                        )}
                      </span>
                      {opp.risk?.expected_profit_pct !== undefined && (
                        <span style={{ color: '#94a3b8' }}>
                          期望收益: <b style={{ color: opp.risk.expected_profit_pct > 0 ? '#22c55e' : '#ef4444' }}>
                            {opp.risk.expected_profit_pct > 0 ? '+' : ''}{opp.risk.expected_profit_pct.toFixed(2)}%
                          </b>
                        </span>
                      )}
                      {opp.fee?.total_cost_pct !== undefined && (
                        <span style={{ color: '#64748b' }}>成本: {opp.fee.total_cost_pct.toFixed(3)}%</span>
                      )}
                    </div>
                  </div>

                  {/* 展开详情 */}
                  {isExpanded && (
                    <div style={{ padding: '0 16px 16px', borderTop: '1px solid rgba(148,163,184,0.1)' }}>
                      {/* 信号理由 */}
                      <div style={{ fontSize: '12px', color: '#94a3b8', padding: '12px 0', borderBottom: '1px solid rgba(148,163,184,0.05)' }}>
                        {opp.reason}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginTop: '12px' }}>
                        {/* 费用卡片 */}
                        {opp.fee && (
                          <div style={{ background: 'rgba(15,23,42,0.5)', borderRadius: '8px', padding: '12px', border: '1px solid rgba(148,163,184,0.08)' }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#f97316', marginBottom: '8px' }}>💰 交易费用</div>
                            <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                              <span>佣金(双边): {opp.fee.round_trip_fee_pct.toFixed(3)}%</span>
                              <span>过户费: {opp.fee.transfer_fee_pct.toFixed(3)}%</span>
                              <span>滑点估算: {opp.fee.slippage_pct.toFixed(3)}%</span>
                              <span style={{ fontWeight: 600, color: '#f1f5f9', borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: '3px', marginTop: '3px' }}>
                                总成本: {opp.fee.total_cost_pct.toFixed(3)}%
                              </span>
                            </div>
                          </div>
                        )}

                        {/* 风控卡片 */}
                        {opp.risk && (
                          <div style={{ background: 'rgba(15,23,42,0.5)', borderRadius: '8px', padding: '12px', border: '1px solid rgba(148,163,184,0.08)' }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#3b82f6', marginBottom: '8px' }}>🛡️ 风险控制</div>
                            <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                              <span>止损: <b style={{ color: '#ef4444' }}>-{opp.risk.stop_loss_pct.toFixed(2)}%</b></span>
                              <span>止盈: <b style={{ color: '#22c55e' }}>+{opp.risk.take_profit_pct.toFixed(2)}%</b></span>
                              <span>仓位上限: {opp.risk.max_position_wan.toFixed(0)}万</span>
                              <span>风险收益比: {opp.risk.risk_reward_ratio.toFixed(1)}</span>
                              <span style={{ fontWeight: 600, color: opp.risk.expected_profit_pct > 0 ? '#22c55e' : '#ef4444', borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: '3px', marginTop: '3px' }}>
                                期望收益: {opp.risk.expected_profit_pct > 0 ? '+' : ''}{opp.risk.expected_profit_pct.toFixed(2)}%
                              </span>
                            </div>
                          </div>
                        )}

                        {/* 因子卡片 */}
                        {opp.factors && (
                          <div style={{ background: 'rgba(15,23,42,0.5)', borderRadius: '8px', padding: '12px', border: '1px solid rgba(148,163,184,0.08)' }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#8b5cf6', marginBottom: '8px' }}>📊 信号因子</div>
                            <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                              <span>底层资产: {opp.factors.underlying_change_pct > 0 ? '+' : ''}{opp.factors.underlying_change_pct.toFixed(2)}%
                                {opp.factors.underlying_confirm === true ? ' ✓确认' : opp.factors.underlying_confirm === false ? ' ⚠矛盾' : ''}
                              </span>
                              <span>溢价率: {opp.factors.premium_pct > 0 ? '+' : ''}{opp.factors.premium_pct.toFixed(2)}% ({opp.factors.premium_level === 'high' ? '高溢价' : opp.factors.premium_level === 'discount' ? '深度折价' : '正常'})</span>
                              <span>成交额: {opp.factors.turnover_wan.toFixed(0)}万 ({opp.factors.volume_level === 'high' ? '充足' : opp.factors.volume_level === 'low' ? '不足' : '正常'})</span>
                              <span>EST净值: {opp.factors.est_nav.toFixed(4)}</span>
                            </div>
                          </div>
                        )}

                        {/* 概率调整 */}
                        {opp.probability_adjustments && opp.probability_adjustments.length > 0 && (
                          <div style={{ background: 'rgba(15,23,42,0.5)', borderRadius: '8px', padding: '12px', border: '1px solid rgba(148,163,184,0.08)' }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#eab308', marginBottom: '8px' }}>📐 概率调整</div>
                            <div style={{ fontSize: '11px', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                              <span>基础概率: {(opp.base_probability! * 100).toFixed(0)}%</span>
                              {opp.probability_adjustments.map((adj, j) => (
                                <span key={j}>{adj.factor}: {adj.delta > 0 ? '+' : ''}{(adj.delta * 100).toFixed(0)}%</span>
                              ))}
                              <span style={{ fontWeight: 600, color: '#f1f5f9', borderTop: '1px solid rgba(148,163,184,0.1)', paddingTop: '3px', marginTop: '3px' }}>
                                调整后: {(opp.probability * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* 回测按钮 */}
                      <div style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <button
                          onClick={(e) => { e.stopPropagation(); runBacktest(opp.fund_code) }}
                          disabled={backtestLoading === opp.fund_code}
                          style={{ padding: '6px 16px', background: backtestLoading === opp.fund_code ? '#374151' : 'linear-gradient(135deg,#8b5cf6,#7c3aed)', color: '#fff', border: 'none', borderRadius: '8px', cursor: backtestLoading === opp.fund_code ? 'not-allowed' : 'pointer', fontSize: '12px', fontWeight: 600 }}
                        >
                          {backtestLoading === opp.fund_code ? '回测中...' : '📈 回测60日胜率'}
                        </button>
                        {backtestData[opp.fund_code] && !backtestData[opp.fund_code].error && (
                          <div style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', gap: '16px' }}>
                            <span>信号数: <b style={{ color: '#f1f5f9' }}>{backtestData[opp.fund_code].signal_days}</b></span>
                            <span>胜率: <b style={{ color: backtestData[opp.fund_code].overall_win_rate >= 50 ? '#22c55e' : '#ef4444' }}>{backtestData[opp.fund_code].overall_win_rate}%</b></span>
                            <span>平均收益: <b style={{ color: backtestData[opp.fund_code].avg_profit_per_trade >= 0 ? '#22c55e' : '#ef4444' }}>{backtestData[opp.fund_code].avg_profit_per_trade}%</b></span>
                            <span>最大盈利: <b style={{ color: '#22c55e' }}>{backtestData[opp.fund_code].max_profit}%</b></span>
                            <span>最大亏损: <b style={{ color: '#ef4444' }}>{backtestData[opp.fund_code].max_loss}%</b></span>
                          </div>
                        )}
                        {backtestData[opp.fund_code]?.error && (
                          <span style={{ fontSize: '12px', color: '#ef4444' }}>{backtestData[opp.fund_code].error}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>暂无做T机会</div>
        )}
      </div>
    </>
  )
}

// ============ 辅助组件 ============

function DisciplineCard({ title, color, steps }: { title: string; color: string; steps: string[] }) {
  return (
    <div style={{ background: 'rgba(15,23,42,0.6)', borderRadius: '12px', padding: '16px', border: `1px solid ${color}30` }}>
      <h4 style={{ fontSize: '14px', fontWeight: 600, color, margin: '0 0 12px' }}>{title}</h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {steps.map((s, i) => <div key={i} style={{ fontSize: '12px', color: '#d1d5db', lineHeight: '1.6' }}>• {s}</div>)}
      </div>
    </div>
  )
}
