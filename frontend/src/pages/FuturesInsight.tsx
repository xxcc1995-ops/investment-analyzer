/**
 * 期货洞察 - 全面的期货分析页面
 *
 * 5个Tab:
 * 1. 商品全景 - 全球商品热力图 + 相关性
 * 2. 机构视角 - COT持仓 + 配置模型
 * 3. 期现分析 - 基差 + 展期收益率
 * 4. 库存仓单 - 库存趋势 + 逼仓风险
 * 5. 商品指数 - 指数走势 + 与股债相关性
 */
import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import { Tooltip } from 'antd'
import { PageSection, TabBar, StatCard, StatCardGroup, LoadingSpinner, EmptyState } from '../components/ui'

const API_BASE = '/api'

// ============ 类型定义 ============

interface CommodityItem {
  symbol: string
  name: string
  unit: string
  exchange: string
  price?: number
  change_pct?: number
  volume?: number
  open_interest?: number
}

interface CategoryData {
  items: CommodityItem[]
  driver: string
  color: string
}

interface COTItem {
  symbol: string
  variety: string
  date: string
  long_oi_top5?: number
  short_oi_top5?: number
  long_oi_chg_top5?: number
  short_oi_chg_top5?: number
  long_oi_top20?: number
  short_oi_top20?: number
  long_oi_chg_top20?: number
  short_oi_chg_top20?: number
  net_oi_top20?: number
  net_oi_chg_top20?: number
  vol_top5?: number
}

interface BasisItem {
  symbol: string
  date: string
  spot_price?: number
  near_contract: string
  near_contract_price?: number
  dominant_contract: string
  dominant_contract_price?: number
  near_basis?: number
  dom_basis?: number
  near_basis_rate?: number
  dom_basis_rate?: number
  state: string
  state_label: string
}

interface RollYieldItem {
  roll_yield?: number
  near_by: string
  deferred: string
}

interface InventoryItem {
  symbol: string
  name: string
  latest_inventory?: number
  latest_change?: number
  latest_date: string
  history: { date: string; inventory?: number; change?: number }[]
}

interface AllocationCategory {
  name: string
  allocation: string
  reason: string
  examples: string
  icon: string
}

interface AllocationStrategy {
  name: string
  description: string
  allocation: string
}

interface CommodityIndex {
  name: string
  latest_close?: number
  latest_change_pct?: number
  ytd_return?: number
  '1y_return'?: number
  history: { date: string; close?: number; change_pct?: number }[]
}

// ---- 金融期货 + 期限结构 + 套利分析 ----

interface FinancialFuturesCategory {
  items: CommodityItem[]
  driver: string
  color: string
}

interface TermStructureContract {
  symbol: string
  delivery_month: string
  price: number
  open_interest?: number
  volume?: number
  change_pct?: number
}

interface TermStructureData {
  var: string
  cn_name: string
  contracts: TermStructureContract[]
  near_price?: number
  far_price?: number
  spread: number
  annualized_spread: number
  structure: string
  structure_label: string
  contract_count: number
}

interface SpreadSignal {
  var: string
  cn_name: string
  type: string
  signal: string
  signal_label: string
  near_month?: string
  far_month?: string
  mid_month?: string
  near_price?: number
  far_price?: number
  spread?: number
  spread_pct?: number
  annualized_spread?: number
  strength?: string
  description: string
  near_oi?: number
  far_oi?: number
  oi_ratio?: number
  butterfly?: number
}

interface OIPriceItem {
  var: string
  cn_name: string
  symbol: string
  price: number
  change_pct: number
  open_interest: number
  volume?: number
  oi_vol_ratio?: number
  signal: string
  signal_label: string
  interpretation: string
  structure?: string
  structure_label?: string
  spread?: number
  annualized_spread?: number
}

// ============ 工具函数 ============

const fmtAmt = (v: number | undefined | null) => {
  if (v === null || v === undefined) return '-'
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

const fmtPct = (v: number | undefined | null) => {
  if (v === null || v === undefined) return '-'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

const fmtPrice = (v: number | undefined | null) => {
  if (v === null || v === undefined) return '-'
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

// ============ 小组件 ============

/** 帮助提示 - 技术术语旁的ⓘ图标 */
const HelpTip = ({ text }: { text: string }) => (
  <Tooltip title={text} placement="top">
    <span style={{ cursor: 'help', color: 'var(--text-muted)', marginLeft: 4, fontSize: 12, opacity: 0.7 }}>ⓘ</span>
  </Tooltip>
)

/** 涨跌颜色单元格 */
const ChgCell = ({ val, suffix = '%' }: { val?: number | null; suffix?: string }) => {
  if (val === null || val === undefined) return <td>-</td>
  return <td className={val >= 0 ? 'up' : 'down'}>{val >= 0 ? '+' : ''}{val.toFixed(2)}{suffix}</td>
}

/** 信息框组件 */
const InfoBox = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="info-box" style={{ marginTop: 20 }}>
    <div className="info-box-title">💡 {title}</div>
    {children}
  </div>
)

/** 加载中 */
const LoadingView = () => (
  <LoadingSpinner />
)

/** 空数据 */
const EmptyView = ({ text = '暂无数据' }: { text?: string }) => (
  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>{text}</div>
)

// ============ Tab 1: 商品全景 ============

function CommodityOverview({ categories, loading }: {
  categories: Record<string, CategoryData>
  loading: boolean
}) {
  if (loading) return <LoadingView />

  const allItems = Object.entries(categories).flatMap(([catName, cat]) =>
    cat.items.map(item => ({ ...item, category: catName, driver: cat.driver, color: cat.color }))
  )

  return (
    <>
      {/* 商品热力图 */}
      {Object.entries(categories).map(([catName, cat]) => (
        <div key={catName} style={{ marginBottom: 20 }}>
          <div className="arb-section-title">
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: cat.color, marginRight: 8 }}></span>
            {catName}
            <HelpTip text={cat.driver} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '10px' }}>
            {cat.items.map(item => (
              <div key={item.symbol} className="arb-note-item" style={{
                padding: '14px',
                borderLeft: `3px solid ${item.change_pct != null && item.change_pct >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'}`,
              }}>
                <span className="arb-note-label">{item.name}</span>
                <span style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent)' }}>
                  {fmtPrice(item.price)}
                </span>
                <span className={item.change_pct != null && item.change_pct >= 0 ? 'up' : 'down'} style={{ fontSize: '13px' }}>
                  {fmtPct(item.change_pct != null ? item.change_pct * 100 : null)}
                </span>
                <span className="arb-note-desc">{item.unit}</span>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* 驱动因素总览 */}
      <div className="arb-section-title">商品分类与驱动因素</div>
      <div className="table-container">
        <table className="arb-table">
          <thead>
            <tr><th>类别</th><th>代表品种</th><th>主要驱动因素</th></tr>
          </thead>
          <tbody>
            {Object.entries(categories).map(([catName, cat]) => (
              <tr key={catName}>
                <td style={{ fontWeight: 600 }}>
                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: cat.color, marginRight: 6 }}></span>
                  {catName}
                </td>
                <td>{cat.items.map(i => i.name).join('、')}</td>
                <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{cat.driver}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <InfoBox title="商品分类与投资逻辑">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>贵金属（黄金、白银）</strong>：抗通胀、避险资产，与美元负相关。黄金是全球央行储备资产，白银兼具工业和金融属性。</li>
          <li><strong>基本金属（铜、铝、锌）</strong>：经济晴雨表，铜被称为"铜博士"。新能源转型（电动车、光伏）推动铜铝需求。</li>
          <li><strong>黑色系（螺纹钢、铁矿石）</strong>：受中国房地产和基建投资驱动，政策敏感度高。</li>
          <li><strong>能源化工（原油、甲醇）</strong>：受OPEC产量决策、地缘政治、全球经济增长预期影响。</li>
          <li><strong>农产品（豆粕、棕榈油、棉花）</strong>：受天气、种植面积、消费季节性、进出口政策影响。</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ Tab 2: 机构视角 ============

function InstitutionalView({ cotData, allocation, loading, cotHistory, selectedVar, onSelectVar }: {
  cotData: COTItem[]
  allocation: { categories: AllocationCategory[]; strategies: AllocationStrategy[] } | null
  loading: boolean
  cotHistory: RollYieldItem[]
  selectedVar: string
  onSelectVar: (v: string) => void
}) {
  if (loading) return <LoadingView />

  // COT多空对比图
  const getCOTChartOption = () => {
    if (!cotData.length) return {}
    const vars = cotData.map(d => d.variety || d.symbol)
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['多头持仓(Top20)', '空头持仓(Top20)', '净持仓'], textStyle: { color: '#8b949e' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: vars, axisLabel: { color: '#8b949e' } },
      yAxis: { type: 'value', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
      series: [
        {
          name: '多头持仓(Top20)',
          type: 'bar',
          stack: 'total',
          data: cotData.map(d => d.long_oi_top20 || 0),
          itemStyle: { color: '#f85149' },
        },
        {
          name: '空头持仓(Top20)',
          type: 'bar',
          stack: 'total2',
          data: cotData.map(d => -(d.short_oi_top20 || 0)),
          itemStyle: { color: '#3fb950' },
        },
        {
          name: '净持仓',
          type: 'line',
          data: cotData.map(d => d.net_oi_top20 || 0),
          itemStyle: { color: '#58a6ff' },
          lineStyle: { width: 2 },
        },
      ],
    }
  }

  // 机构配置饼图
  const getAllocationChartOption = () => {
    if (!allocation?.categories?.length) return {}
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
      legend: { orient: 'vertical', right: '5%', top: 'center', textStyle: { color: '#8b949e' } },
      series: [{
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: allocation.categories.map((c, i) => ({
          name: `${c.icon} ${c.name}`,
          value: parseInt(c.allocation) || 15,
          itemStyle: { color: ['#FFD700', '#1E90FF', '#B87333', '#4A4A4A', '#32CD32', '#FF6347', '#9370DB'][i % 7] },
        })),
      }],
    }
  }

  return (
    <>
      {/* 聪明钱信号 */}
      <div className="arb-section-title">
        COT持仓数据 <HelpTip text="COT (Commitments of Traders) 是期货交易所每周发布的持仓报告，显示前20名多空持仓。商业净多头增加通常是看涨信号。" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px', marginBottom: 16 }}>
        {cotData.slice(0, 8).map(d => {
          const net = d.net_oi_top20 || 0
          const netChg = d.net_oi_chg_top20 || 0
          return (
            <div key={d.symbol} className="arb-note-item" style={{
              padding: '14px',
              borderLeft: `3px solid ${net >= 0 ? '#f85149' : '#3fb950'}`,
              cursor: 'pointer',
            }} onClick={() => onSelectVar(d.variety)}>
              <span className="arb-note-label">{d.variety}</span>
              <span style={{ fontSize: 14, fontWeight: 600, color: net >= 0 ? '#f85149' : '#3fb950' }}>
                净持仓: {fmtAmt(net)}
              </span>
              <span className={netChg >= 0 ? 'up' : 'down'} style={{ fontSize: 12 }}>
                日变化: {fmtAmt(netChg)}
              </span>
              <span className="arb-note-desc" style={{ fontSize: 11 }}>
                多头 {fmtAmt(d.long_oi_top20)} / 空头 {fmtAmt(d.short_oi_top20)}
              </span>
            </div>
          )
        })}
      </div>

      {/* COT多空对比图 */}
      {cotData.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <ReactECharts option={getCOTChartOption()} style={{ height: 350 }} />
        </div>
      )}

      {/* COT详细表格 */}
      <div className="arb-section-title">持仓排名详情</div>
      <div className="table-container" style={{ marginBottom: 20 }}>
        <table className="arb-table">
          <thead>
            <tr>
              <th>品种</th>
              <th>多头Top20 <HelpTip text="前20名多头持仓量" /></th>
              <th>空头Top20 <HelpTip text="前20名空头持仓量" /></th>
              <th>净持仓 <HelpTip text="多头-空头，正值看多，负值看空" /></th>
              <th>多头变化</th>
              <th>空头变化</th>
            </tr>
          </thead>
          <tbody>
            {cotData.map((d, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{d.variety || d.symbol}</td>
                <td>{fmtAmt(d.long_oi_top20)}</td>
                <td>{fmtAmt(d.short_oi_top20)}</td>
                <td className={(d.net_oi_top20 || 0) >= 0 ? 'up' : 'down'} style={{ fontWeight: 600 }}>
                  {fmtAmt(d.net_oi_top20)}
                </td>
                <ChgCell val={d.long_oi_chg_top20} suffix="" />
                <ChgCell val={d.short_oi_chg_top20} suffix="" />
              </tr>
            ))}
            {cotData.length === 0 && <tr><td colSpan={6}><EmptyView /></td></tr>}
          </tbody>
        </table>
      </div>

      {/* 机构配置模型 */}
      {allocation && (
        <>
          <div className="arb-section-title">
            顶级机构配置参考 <HelpTip text="基于桥水全天候策略、CTA基金公开数据整理的典型配置比例" />
          </div>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginBottom: 20 }}>
            <div style={{ flex: '1 1 350px', minWidth: 300 }}>
              <ReactECharts option={getAllocationChartOption()} style={{ height: 300 }} />
            </div>
            <div style={{ flex: '1 1 300px' }}>
              <div className="table-container">
                <table className="arb-table">
                  <thead><tr><th>类别</th><th>配置比例</th><th>逻辑</th></tr></thead>
                  <tbody>
                    {allocation.categories.map((c, i) => (
                      <tr key={i}>
                        <td>{c.icon} {c.name}</td>
                        <td style={{ fontWeight: 600, color: 'var(--accent)' }}>{c.allocation}</td>
                        <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* 策略说明 */}
          <div className="arb-section-title">常见期货策略</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px', marginBottom: 16 }}>
            {allocation.strategies.map((s, i) => (
              <div key={i} className="arb-note-item" style={{ padding: '16px' }}>
                <span className="arb-note-label">{s.name}</span>
                <span className="arb-note-value" style={{ color: 'var(--accent)' }}>{s.allocation}</span>
                <span className="arb-note-desc">{s.description}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <InfoBox title="什么是COT数据？">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>COT (Commitments of Traders)</strong> 是期货交易所每周发布的持仓报告</li>
          <li><strong>商业持仓（Commercial）</strong>：实际生产商/消费者，用于套期保值。如金矿商卖黄金期货锁定价格</li>
          <li><strong>非商业持仓（Non-Commercial）</strong>：投机者，追求利润</li>
          <li><strong>看涨信号</strong>：商业净多头大幅增加 → 产业资本认为价格被低估</li>
          <li><strong>看跌信号</strong>：投机者净多头极端 → 可能是趋势反转的前兆</li>
          <li><strong>注意</strong>：COT数据有滞后性（每周五发布），需结合其他指标使用</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ Tab 3: 期现分析 ============

function BasisStructure({ basisData, rollYieldData, selectedVar, onSelectVar, loading }: {
  basisData: BasisItem[]
  rollYieldData: RollYieldItem[]
  selectedVar: string
  onSelectVar: (v: string) => void
  loading: boolean
}) {
  if (loading) return <LoadingView />

  // 基差对比图
  const getBasisChartOption = () => {
    if (!basisData.length) return {}
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: ['基差', '基差率(%)'], textStyle: { color: '#8b949e' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: basisData.map(d => d.symbol), axisLabel: { color: '#8b949e' } },
      yAxis: [
        { type: 'value', name: '基差', axisLabel: { color: '#8b949e' }, splitLine: { lineStyle: { color: '#21262d' } } },
        { type: 'value', name: '基差率(%)', axisLabel: { color: '#8b949e' }, splitLine: { show: false } },
      ],
      series: [
        {
          name: '基差',
          type: 'bar',
          data: basisData.map(d => ({
            value: d.dom_basis || 0,
            itemStyle: { color: (d.dom_basis || 0) >= 0 ? '#f85149' : '#3fb950' },
          })),
        },
        {
          name: '基差率(%))',
          type: 'line',
          yAxisIndex: 1,
          data: basisData.map(d => d.dom_basis_rate != null ? d.dom_basis_rate * 100 : 0),
          itemStyle: { color: '#58a6ff' },
          lineStyle: { width: 2 },
        },
      ],
    }
  }

  // 展期收益率图
  const getRollYieldChartOption = () => {
    if (!rollYieldData.length) return {}
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: rollYieldData.map((_, i) => i),
        axisLabel: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#8b949e', formatter: (v: number) => (v * 100).toFixed(2) + '%' },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      series: [{
        type: 'line',
        data: rollYieldData.map(d => d.roll_yield || 0),
        itemStyle: { color: '#58a6ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(88,166,255,0.3)' },
              { offset: 1, color: 'rgba(88,166,255,0.05)' },
            ],
          },
        },
        lineStyle: { width: 2 },
      }],
    }
  }

  return (
    <>
      {/* 基差分析 */}
      <div className="arb-section-title">
        基差分析 <HelpTip text="基差 = 期货价格 - 现货价格。正值为升水(Contango)，负值为贴水(Backwardation)。贴水通常表示供应紧张。" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px', marginBottom: 16 }}>
        {basisData.slice(0, 8).map(d => (
          <div key={d.symbol} className="arb-note-item" style={{
            padding: '14px',
            borderLeft: `3px solid ${d.state === 'contango' ? '#f85149' : d.state === 'backwardation' ? '#3fb950' : '#58a6ff'}`,
          }}>
            <span className="arb-note-label">{d.symbol}</span>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              {d.state_label}
            </span>
            <span className={d.dom_basis != null && d.dom_basis >= 0 ? 'up' : 'down'} style={{ fontSize: 13 }}>
              基差: {d.dom_basis?.toFixed(2) || '-'}
            </span>
            <span className="arb-note-desc" style={{ fontSize: 11 }}>
              现货 {fmtPrice(d.spot_price)} / 期货 {fmtPrice(d.dominant_contract_price)}
            </span>
          </div>
        ))}
      </div>

      {/* 基差图表 */}
      {basisData.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <ReactECharts option={getBasisChartOption()} style={{ height: 300 }} />
        </div>
      )}

      {/* 基差详情表 */}
      <div className="table-container" style={{ marginBottom: 20 }}>
        <table className="arb-table">
          <thead>
            <tr>
              <th>品种</th>
              <th>现货价</th>
              <th>主力合约</th>
              <th>期货价</th>
              <th>基差 <HelpTip text="期货-现货，正=升水，负=贴水" /></th>
              <th>基差率</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {basisData.map((d, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{d.symbol}</td>
                <td>{fmtPrice(d.spot_price)}</td>
                <td style={{ fontFamily: 'monospace' }}>{d.dominant_contract}</td>
                <td>{fmtPrice(d.dominant_contract_price)}</td>
                <td className={(d.dom_basis || 0) >= 0 ? 'up' : 'down'}>{d.dom_basis?.toFixed(2) || '-'}</td>
                <td className={(d.dom_basis_rate || 0) >= 0 ? 'up' : 'down'}>{d.dom_basis_rate != null ? (d.dom_basis_rate * 100).toFixed(3) + '%' : '-'}</td>
                <td>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 12,
                    fontWeight: 600,
                    background: d.state === 'contango' ? 'rgba(248,81,73,0.15)' : d.state === 'backwardation' ? 'rgba(63,185,80,0.15)' : 'rgba(88,166,255,0.15)',
                    color: d.state === 'contango' ? '#f85149' : d.state === 'backwardation' ? '#3fb950' : '#58a6ff',
                  }}>
                    {d.state_label}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 展期收益率 */}
      <div className="arb-section-title">
        展期收益率 ({selectedVar}) <HelpTip text="持有近月合约到期后换仓到远月的年化收益。正值表示贴水结构有利于多头持仓。" />
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {['AU', 'CU', 'RB', 'I', 'SC', 'M', 'AL', 'ZN'].map(v => (
          <button key={v} className={`list-tab ${selectedVar === v ? 'active' : ''}`}
            onClick={() => onSelectVar(v)} style={{ padding: '4px 12px', fontSize: 12 }}>
            {v}
          </button>
        ))}
      </div>
      {rollYieldData.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <ReactECharts option={getRollYieldChartOption()} style={{ height: 280 }} />
        </div>
      )}

      <InfoBox title="基差与展期收益率">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>基差 = 期货价格 - 现货价格</strong></li>
          <li><strong>升水（Contango）</strong>：期货 &gt; 现货，通常表示供应充足或存储成本高。持有期货会"亏水"</li>
          <li><strong>贴水（Backwardation）</strong>：期货 &lt; 现货，通常表示供应紧张。持有期货可获得"便利收益"</li>
          <li><strong>展期收益率</strong>：持有近月合约到期后换仓到远月的年化收益/损失</li>
          <li><strong>实战意义</strong>：正展期收益 + 趋势向上 = 做多黄金策略；负展期收益 + 趋势向下 = 做空原油策略</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ Tab 4: 库存仓单 ============

function InventoryReceipts({ inventoryData, loading }: {
  inventoryData: Record<string, InventoryItem>
  loading: boolean
}) {
  if (loading) return <LoadingView />

  const inventoryEntries = Object.entries(inventoryData)

  // 库存趋势图
  const getInventoryChartOption = (item: InventoryItem) => {
    if (!item.history.length) return {}
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: item.history.map(h => h.date),
        axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#8b949e' },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      series: [{
        type: 'line',
        data: item.history.map(h => h.inventory),
        itemStyle: { color: '#58a6ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(88,166,255,0.3)' },
              { offset: 1, color: 'rgba(88,166,255,0.05)' },
            ],
          },
        },
        lineStyle: { width: 2 },
      }],
    }
  }

  return (
    <>
      <div className="arb-section-title">
        商品库存数据 <HelpTip text="库存变化是判断供需关系的重要指标。库存持续下降通常预示供应紧张，可能推高价格。" />
      </div>

      {/* 库存概览卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px', marginBottom: 20 }}>
        {inventoryEntries.map(([sym, item]) => (
          <div key={sym} className="arb-note-item" style={{
            padding: '14px',
            borderLeft: `3px solid ${(item.latest_change || 0) < 0 ? '#3fb950' : '#f85149'}`,
          }}>
            <span className="arb-note-label">{item.name}</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)' }}>
              {fmtAmt(item.latest_inventory)}
            </span>
            <span className={(item.latest_change || 0) < 0 ? 'up' : 'down'} style={{ fontSize: 13 }}>
              变化: {item.latest_change != null ? fmtAmt(item.latest_change) : '-'}
            </span>
            <span className="arb-note-desc">{item.latest_date}</span>
          </div>
        ))}
      </div>

      {/* 库存趋势图 */}
      {inventoryEntries.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '16px', marginBottom: 20 }}>
          {inventoryEntries.slice(0, 4).map(([sym, item]) => (
            <div key={sym}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text-primary)' }}>
                {item.name} 库存趋势
              </div>
              <ReactECharts option={getInventoryChartOption(item)} style={{ height: 250 }} />
            </div>
          ))}
        </div>
      )}

      {/* 库存详情表 */}
      <div className="arb-section-title">库存详情</div>
      <div className="table-container">
        <table className="arb-table">
          <thead>
            <tr>
              <th>品种</th>
              <th>最新库存</th>
              <th>日变化</th>
              <th>日期</th>
              <th>趋势 <HelpTip text="库存持续下降=供应紧张信号" /></th>
            </tr>
          </thead>
          <tbody>
            {inventoryEntries.map(([sym, item]) => {
              const trend = item.history.length >= 2
                ? (item.history[item.history.length - 1].inventory || 0) - (item.history[0].inventory || 0)
                : 0
              return (
                <tr key={sym}>
                  <td style={{ fontWeight: 600 }}>{item.name}</td>
                  <td>{fmtAmt(item.latest_inventory)}</td>
                  <td className={(item.latest_change || 0) < 0 ? 'up' : 'down'}>{item.latest_change != null ? fmtAmt(item.latest_change) : '-'}</td>
                  <td>{item.latest_date}</td>
                  <td>
                    <span style={{
                      padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
                      background: trend < 0 ? 'rgba(63,185,80,0.15)' : 'rgba(248,81,73,0.15)',
                      color: trend < 0 ? '#3fb950' : '#f85149',
                    }}>
                      {trend < 0 ? '↓ 下降' : trend > 0 ? '↑ 上升' : '→ 平稳'}
                    </span>
                  </td>
                </tr>
              )
            })}
            {inventoryEntries.length === 0 && <tr><td colSpan={5}><EmptyView /></td></tr>}
          </tbody>
        </table>
      </div>

      <InfoBox title="库存与逼仓">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>仓单</strong>是存放在交易所指定仓库的标准化商品凭证，代表实际可交割的商品数量</li>
          <li><strong>库存下降 + 贴水结构</strong> → 可能出现供应紧张，价格易涨难跌</li>
          <li><strong>逼仓</strong>：多方控制现货供应，迫使空方以高价平仓。历史上铜、镍等品种多次出现逼仓事件</li>
          <li><strong>逼仓风险信号</strong>：低仓单 + 近月大幅贴水 + 库存快速下降</li>
          <li><strong>注意</strong>：库存数据有滞后性，需结合基差和COT数据综合判断</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ Tab 5: 商品指数 ============

function CommodityIndicesView({ indices, loading }: {
  indices: CommodityIndex[]
  loading: boolean
}) {
  if (loading) return <LoadingView />

  // 指数走势图
  const getIndexChartOption = () => {
    if (!indices.length) return {}
    const colors = ['#58a6ff', '#f0883e']
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: indices.map(idx => idx.name), textStyle: { color: '#8b949e' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: indices[0]?.history.map(h => h.date) || [],
        axisLabel: { color: '#8b949e', rotate: 45, fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#8b949e' },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      series: indices.map((idx, i) => ({
        name: idx.name,
        type: 'line',
        data: idx.history.map(h => h.close),
        itemStyle: { color: colors[i % colors.length] },
        lineStyle: { width: 2 },
        smooth: true,
      })),
    }
  }

  return (
    <>
      {/* 指数概览 */}
      <div className="arb-section-title">
        中证商品期货指数 <HelpTip text="跟踪国内一篮子商品期货的表现，是衡量商品市场整体走势的重要基准。" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '12px', marginBottom: 20 }}>
        {indices.map((idx, i) => (
          <div key={i} className="arb-note-item" style={{ padding: '16px' }}>
            <span className="arb-note-label">{idx.name}</span>
            <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent)' }}>
              {fmtPrice(idx.latest_close)}
            </span>
            <span className={(idx.latest_change_pct || 0) >= 0 ? 'up' : 'down'} style={{ fontSize: 14 }}>
              今日: {fmtPct(idx.latest_change_pct)}
            </span>
            <span className="arb-note-desc">
              年初至今: {fmtPct(idx.ytd_return)} | 近1年: {fmtPct(idx['1y_return'])}
            </span>
          </div>
        ))}
      </div>

      {/* 指数走势图 */}
      {indices.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <ReactECharts option={getIndexChartOption()} style={{ height: 350 }} />
        </div>
      )}

      {/* 收益统计表 */}
      <div className="arb-section-title">收益统计</div>
      <div className="table-container">
        <table className="arb-table">
          <thead>
            <tr>
              <th>指数</th>
              <th>最新点位</th>
              <th>今日涨跌</th>
              <th>年初至今</th>
              <th>近1年</th>
            </tr>
          </thead>
          <tbody>
            {indices.map((idx, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{idx.name}</td>
                <td>{fmtPrice(idx.latest_close)}</td>
                <ChgCell val={idx.latest_change_pct} />
                <td className={(idx.ytd_return || 0) >= 0 ? 'up' : 'down'}>{fmtPct(idx.ytd_return)}</td>
                <td className={(idx['1y_return'] || 0) >= 0 ? 'up' : 'down'}>{fmtPct(idx['1y_return'])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <InfoBox title="商品指数与CTA策略">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>中证商品期货指数</strong>：跟踪国内一篮子商品期货的表现，分散单一品种风险</li>
          <li><strong>CTA（Commodity Trading Advisor）</strong>：管理期货策略，是全球最大的另类投资策略之一</li>
          <li><strong>趋势跟踪</strong>：约60%的CTA收益来自趋势跟踪策略。顺势而为，截断亏损，让利润奔跑</li>
          <li><strong>资产配置价值</strong>：商品与股票/债券的相关性较低（通常0.1-0.3），可有效分散组合风险</li>
          <li><strong>通胀对冲</strong>：商品是天然的通胀对冲工具，尤其在通胀上行期表现优异</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ Tab 6: 金融期货 ============

function FinancialFuturesView({ categories, loading }: {
  categories: Record<string, FinancialFuturesCategory>
  loading: boolean
}) {
  if (loading) return <LoadingView />

  const hasData = Object.keys(categories).length > 0

  return (
    <>
      {Object.entries(categories).map(([catName, cat]) => (
        <div key={catName} style={{ marginBottom: 20 }}>
          <div className="arb-section-title">
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: cat.color, marginRight: 8 }}></span>
            {catName}
            <HelpTip text={cat.driver} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
            {cat.items.map(item => (
              <div key={item.symbol} className="arb-note-item" style={{
                padding: '14px',
                borderLeft: `3px solid ${item.change_pct != null && item.change_pct >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'}`,
              }}>
                <span className="arb-note-label">{item.name}</span>
                <span style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent)' }}>
                  {fmtPrice(item.price)}
                </span>
                <span className={item.change_pct != null && item.change_pct >= 0 ? 'up' : 'down'} style={{ fontSize: '13px' }}>
                  {fmtPct(item.change_pct != null ? item.change_pct * 100 : null)}
                </span>
                <span className="arb-note-desc">
                  {item.unit} | 成交: {fmtAmt(item.volume)} | 持仓: {fmtAmt(item.open_interest)}
                </span>
              </div>
            ))}
            {cat.items.length === 0 && <EmptyView text="暂无数据" />}
          </div>
        </div>
      ))}

      {!hasData && <EmptyView text="暂无金融期货数据，请稍后刷新" />}

      <div className="table-container" style={{ marginTop: 16 }}>
        <table className="arb-table">
          <thead>
            <tr><th>品种</th><th>最新价</th><th>涨跌幅</th><th>成交量</th><th>持仓量</th><th>交易所</th></tr>
          </thead>
          <tbody>
            {Object.values(categories).flatMap(cat => cat.items).map((item, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{item.name}</td>
                <td>{fmtPrice(item.price)}</td>
                <ChgCell val={item.change_pct != null ? item.change_pct * 100 : null} />
                <td>{fmtAmt(item.volume)}</td>
                <td>{fmtAmt(item.open_interest)}</td>
                <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{item.exchange}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <InfoBox title="金融期货投资逻辑">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>股指期货</strong>: 与对应指数高度相关。升水表示市场看多，贴水表示看空。可用于对冲股票组合风险。</li>
          <li><strong>国债期货</strong>: 利率下行时价格上涨。久期越长弹性越大（十年 &gt; 五年 &gt; 二年）。可用于利率风险管理。</li>
          <li><strong>基差交易</strong>: 股指期货基差 = 期货 - 现货。深度贴水时做多基差（买期货卖ETF），升水时做空基差。</li>
          <li><strong>跨品种套利</strong>: IF-IC价差反映大盘/小盘风格切换，T-TF价差反映长短端利率变化。</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ 期限结构组件 ============

function TermStructureSection({ termStructure, termVar, onSelectVar, loading }: {
  termStructure: TermStructureData | null
  termVar: string
  onSelectVar: (v: string) => void
  loading: boolean
}) {
  const getChartOption = () => {
    if (!termStructure?.contracts?.length) return {}
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const d = params[0]
          const c = termStructure.contracts[d.dataIndex]
          return `${c.symbol} (${c.delivery_month})<br/>价格: ${c.price}<br/>持仓量: ${fmtAmt(c.open_interest)}<br/>成交量: ${fmtAmt(c.volume)}`
        },
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: termStructure.contracts.map(c => c.delivery_month),
        axisLabel: { color: '#8b949e' },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#8b949e' },
        splitLine: { lineStyle: { color: '#21262d' } },
      },
      series: [{
        type: 'line',
        data: termStructure.contracts.map(c => c.price),
        itemStyle: { color: termStructure.structure === 'backwardation' ? '#3fb950' : '#f85149' },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: termStructure.structure === 'backwardation' ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)' },
              { offset: 1, color: 'rgba(88,166,255,0.05)' },
            ],
          },
        },
        lineStyle: { width: 3 },
        smooth: true,
        markPoint: {
          data: [
            { type: 'max', name: '最高' },
            { type: 'min', name: '最低' },
          ],
        },
      }],
    }
  }

  return (
    <>
      <div className="arb-section-title">
        期限结构曲线 <HelpTip text="同一品种不同到期月份合约的价格曲线。升水(Contango)=远月>近月，贴水(Backwardation)=近月>远月。" />
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {['AU', 'CU', 'RB', 'I', 'SC', 'M', 'AL', 'ZN', 'AG', 'HC'].map(v => (
          <button key={v} className={`list-tab ${termVar === v ? 'active' : ''}`}
            onClick={() => onSelectVar(v)} style={{ padding: '4px 12px', fontSize: 12 }}>
            {v}
          </button>
        ))}
      </div>

      {termStructure && termStructure.contracts.length > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px', marginBottom: 16 }}>
            <div className="arb-note-item" style={{
              padding: '14px',
              borderLeft: `3px solid ${termStructure.structure === 'backwardation' ? '#3fb950' : termStructure.structure === 'contango' ? '#f85149' : '#58a6ff'}`,
            }}>
              <span className="arb-note-label">{termStructure.cn_name}</span>
              <span style={{ fontSize: 16, fontWeight: 700 }}>{termStructure.structure_label}</span>
              <span className="arb-note-desc">合约数: {termStructure.contract_count}</span>
            </div>
            <div className="arb-note-item" style={{ padding: '14px' }}>
              <span className="arb-note-label">近月价格</span>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)' }}>{fmtPrice(termStructure.near_price)}</span>
            </div>
            <div className="arb-note-item" style={{ padding: '14px' }}>
              <span className="arb-note-label">远月价格</span>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--accent)' }}>{fmtPrice(termStructure.far_price)}</span>
            </div>
            <div className="arb-note-item" style={{ padding: '14px' }}>
              <span className="arb-note-label">年化价差</span>
              <span className={termStructure.annualized_spread >= 0 ? 'up' : 'down'} style={{ fontSize: 16, fontWeight: 700 }}>
                {termStructure.annualized_spread >= 0 ? '+' : ''}{termStructure.annualized_spread.toFixed(2)}%
              </span>
            </div>
          </div>

          <div style={{ marginBottom: 20 }}>
            <ReactECharts option={getChartOption()} style={{ height: 300 }} />
          </div>

          <div className="table-container">
            <table className="arb-table">
              <thead>
                <tr><th>合约</th><th>到期月</th><th>价格</th><th>涨跌幅</th><th>持仓量</th><th>成交量</th></tr>
              </thead>
              <tbody>
                {termStructure.contracts.map((c, i) => (
                  <tr key={i}>
                    <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{c.symbol}</td>
                    <td>{c.delivery_month}</td>
                    <td>{fmtPrice(c.price)}</td>
                    <ChgCell val={c.change_pct != null ? c.change_pct * 100 : null} />
                    <td>{fmtAmt(c.open_interest)}</td>
                    <td>{fmtAmt(c.volume)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {(!termStructure || termStructure.contracts.length === 0) && !loading && <EmptyView text="暂无期限结构数据" />}
    </>
  )
}

// ============ 套利信号组件 ============

function SpreadSignalsSection({ signals, loading }: {
  signals: SpreadSignal[]
  loading: boolean
}) {
  if (loading) return <LoadingView />

  return (
    <>
      <div className="arb-section-title">
        跨期套利信号 <HelpTip text="自动检测极端价差、换月压力和蝶式套利机会。年化价差>5%触发信号。" />
      </div>

      {signals.length > 0 ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px', marginBottom: 16 }}>
            {signals.map((s, i) => (
              <div key={i} className="arb-note-item" style={{
                padding: '14px',
                borderLeft: `3px solid ${s.strength === 'strong' ? '#f85149' : s.type === 'rollover_pressure' ? '#f0883e' : '#58a6ff'}`,
              }}>
                <span className="arb-note-label">{s.cn_name} ({s.var})</span>
                <span style={{ fontSize: 14, fontWeight: 600 }}>{s.signal_label}</span>
                <span style={{ fontSize: 12 }}>{s.description}</span>
                {s.strength && (
                  <span style={{
                    padding: '1px 6px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: s.strength === 'strong' ? 'rgba(248,81,73,0.15)' : 'rgba(88,166,255,0.15)',
                    color: s.strength === 'strong' ? '#f85149' : '#58a6ff',
                  }}>
                    {s.strength === 'strong' ? '强信号' : '中等信号'}
                  </span>
                )}
              </div>
            ))}
          </div>

          <div className="table-container">
            <table className="arb-table">
              <thead>
                <tr><th>品种</th><th>信号类型</th><th>近月</th><th>远月</th><th>价差</th><th>年化价差</th><th>强度</th><th>说明</th></tr>
              </thead>
              <tbody>
                {signals.map((s, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{s.cn_name}</td>
                    <td>{s.signal_label}</td>
                    <td style={{ fontFamily: 'monospace' }}>{s.near_month || '-'}</td>
                    <td style={{ fontFamily: 'monospace' }}>{s.far_month || '-'}</td>
                    <td className={(s.spread || 0) >= 0 ? 'up' : 'down'}>{s.spread?.toFixed(2) || '-'}</td>
                    <td className={(s.annualized_spread || 0) >= 0 ? 'up' : 'down'}>
                      {s.annualized_spread != null ? s.annualized_spread.toFixed(2) + '%' : '-'}
                    </td>
                    <td>
                      <span style={{
                        padding: '2px 6px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: s.strength === 'strong' ? 'rgba(248,81,73,0.15)' : 'rgba(88,166,255,0.15)',
                        color: s.strength === 'strong' ? '#f85149' : '#58a6ff',
                      }}>
                        {s.strength === 'strong' ? '强' : '中'}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{s.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <EmptyView text="当前无套利信号，市场结构正常" />
      )}

      <InfoBox title="跨期套利策略">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>正向套利（买近卖远）</strong>: 当近月贴水严重时，买入近月+卖出远月，等待价差收敛</li>
          <li><strong>反向套利（卖近买远）</strong>: 当近月升水严重时，卖出近月+买入远月，等待价差收敛</li>
          <li><strong>蝶式套利</strong>: 同时交易三个到期月份，赚取中间合约相对定价偏差</li>
          <li><strong>换月压力</strong>: 近月持仓量远高于远月时，临近到期会有大量移仓，可能导致价格波动</li>
          <li><strong>注意</strong>: 套利交易需要考虑手续费、保证金和流动性，年化价差需覆盖交易成本</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ 持仓量-价格分析组件 ============

function OIPriceAnalysisSection({ analysis, loading }: {
  analysis: OIPriceItem[]
  loading: boolean
}) {
  if (loading) return <LoadingView />

  const getSignalColor = (signal: string) => {
    if (signal.includes('bullish')) return '#3fb950'
    if (signal.includes('bearish')) return '#f85149'
    return '#58a6ff'
  }

  return (
    <>
      <div className="arb-section-title">
        持仓量-价格分析 <HelpTip text="分析主力合约持仓量与价格的关系，判断多空力量对比。" />
      </div>

      {analysis.length > 0 ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px', marginBottom: 16 }}>
            {analysis.map((item, i) => (
              <div key={i} className="arb-note-item" style={{
                padding: '14px',
                borderLeft: `3px solid ${getSignalColor(item.signal)}`,
              }}>
                <span className="arb-note-label">{item.cn_name}</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: getSignalColor(item.signal) }}>{item.signal_label}</span>
                <span className={item.change_pct >= 0 ? 'up' : 'down'} style={{ fontSize: 13 }}>
                  {fmtPrice(item.price)} ({fmtPct((item.change_pct ?? 0) * 100)})
                </span>
                <span className="arb-note-desc" style={{ fontSize: 11 }}>
                  持仓: {fmtAmt(item.open_interest)} | {item.structure_label}
                </span>
              </div>
            ))}
          </div>

          <div className="table-container">
            <table className="arb-table">
              <thead>
                <tr>
                  <th>品种</th>
                  <th>主力合约</th>
                  <th>价格</th>
                  <th>涨跌幅</th>
                  <th>持仓量</th>
                  <th>成交量</th>
                  <th>仓量比</th>
                  <th>信号</th>
                  <th>解读</th>
                </tr>
              </thead>
              <tbody>
                {analysis.map((item, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{item.cn_name}</td>
                    <td style={{ fontFamily: 'monospace' }}>{item.symbol}</td>
                    <td>{fmtPrice(item.price)}</td>
                    <ChgCell val={item.change_pct * 100} />
                    <td>{fmtAmt(item.open_interest)}</td>
                    <td>{fmtAmt(item.volume)}</td>
                    <td>{item.oi_vol_ratio?.toFixed(2) || '-'}</td>
                    <td>
                      <span style={{
                        padding: '2px 6px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: `${getSignalColor(item.signal)}22`,
                        color: getSignalColor(item.signal),
                      }}>
                        {item.signal_label}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{item.interpretation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <EmptyView text="暂无持仓量分析数据" />
      )}

      <InfoBox title="持仓量-价格关系解读">
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          <li><strong>多方入场</strong>: 价格上涨+持仓量高 → 新多头入场推动上涨，信号强</li>
          <li><strong>空方入场</strong>: 价格下跌+持仓量高 → 新空头入场推动下跌，信号强</li>
          <li><strong>空头回补</strong>: 价格上涨+持仓量低 → 空头平仓推动反弹，信号弱</li>
          <li><strong>多头离场</strong>: 价格下跌+持仓量低 → 多头平仓推动下跌，信号弱</li>
          <li><strong>仓量比</strong>: 持仓量/成交量，比值高说明持仓意愿强，趋势可能延续</li>
        </ul>
      </InfoBox>
    </>
  )
}

// ============ 术语表 ============

function Glossary() {
  const [expanded, setExpanded] = useState(false)
  const terms = [
    { term: 'COT', def: 'Commitments of Traders，期货交易所每周发布的持仓报告' },
    { term: '基差', def: '期货价格 - 现货价格，反映市场对未来供需的预期' },
    { term: '升水(Contango)', def: '期货 > 现货，通常表示供应充足或存储成本高' },
    { term: '贴水(Backwardation)', def: '期货 < 现货，通常表示供应紧张' },
    { term: '展期收益率', def: '持有近月合约到期后换仓到远月的年化收益/损失' },
    { term: '仓单', def: '存放在交易所指定仓库的标准化商品凭证' },
    { term: '逼仓', def: '多方控制现货供应，迫使空方以高价平仓' },
    { term: 'CTA', def: 'Commodity Trading Advisor，管理期货策略' },
    { term: '趋势跟踪', def: '跟随价格趋势的交易策略，CTA的核心策略' },
    { term: '便利收益', def: '持有实物商品相对于持有期货的额外收益' },
    { term: '持仓量', def: '未平仓合约总数，反映市场参与度' },
    { term: '连续合约', def: '将不同到期月份的合约拼接成连续的价格序列' },
  ]

  return (
    <div className="arb-notes" style={{ marginTop: 16 }}>
      <h3 style={{ cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
        期货术语表 {expanded ? '▲' : '▼'}
      </h3>
      {expanded && (
        <div className="arb-notes-content">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '8px' }}>
            {terms.map((t, i) => (
              <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                <strong>{t.term}</strong>：{t.def}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============ 主组件 ============

export default function FuturesInsight() {
  const [activeTab, setActiveTab] = useState<'overview' | 'financial' | 'institutional' | 'basis' | 'inventory' | 'indices'>('overview')
  const [loadedTabs, setLoadedTabs] = useState<Set<string>>(new Set())

  // 数据状态
  const [categories, setCategories] = useState<Record<string, CategoryData>>({})
  const [cotData, setCotData] = useState<COTItem[]>([])
  const [basisData, setBasisData] = useState<BasisItem[]>([])
  const [rollYieldData, setRollYieldData] = useState<RollYieldItem[]>([])
  const [inventoryData, setInventoryData] = useState<Record<string, InventoryItem>>({})
  const [indices, setIndices] = useState<CommodityIndex[]>([])
  const [allocation, setAllocation] = useState<{ categories: AllocationCategory[]; strategies: AllocationStrategy[] } | null>(null)

  const [loading, setLoading] = useState(false)
  const [selectedVar, setSelectedVar] = useState('AU')
  const [termVar, setTermVar] = useState('AU')

  // 金融期货 + 期限结构 + 套利分析
  const [financialCategories, setFinancialCategories] = useState<Record<string, FinancialFuturesCategory>>({})
  const [termStructure, setTermStructure] = useState<TermStructureData | null>(null)
  const [spreadSignals, setSpreadSignals] = useState<SpreadSignal[]>([])
  const [oiAnalysis, setOIAnalysis] = useState<OIPriceItem[]>([])

  // 加载Tab数据
  const loadTabData = useCallback(async (tab: string) => {
    setLoading(true)
    try {
      if (tab === 'overview') {
        const res = await axios.get(`${API_BASE}/futures/global-commodities`)
        setCategories(res.data.categories || {})
      } else if (tab === 'institutional') {
        const [cotRes, allocRes, oiRes] = await Promise.all([
          axios.get(`${API_BASE}/futures/cot-ranking`),
          axios.get(`${API_BASE}/futures/institutional-allocation`),
          axios.get(`${API_BASE}/futures/oi-analysis`),
        ])
        setCotData(cotRes.data.cot || [])
        setAllocation(allocRes.data)
        setOIAnalysis(oiRes.data.analysis || [])
      } else if (tab === 'basis') {
        const [basisRes, ryRes, tsRes, ssRes] = await Promise.all([
          axios.get(`${API_BASE}/futures/basis`),
          axios.get(`${API_BASE}/futures/roll-yield`, { params: { var: selectedVar } }),
          axios.get(`${API_BASE}/futures/term-structure`, { params: { var: termVar } }),
          axios.get(`${API_BASE}/futures/spread-signals`),
        ])
        setBasisData(basisRes.data.basis || [])
        setRollYieldData(ryRes.data.roll_yield || [])
        setTermStructure(tsRes.data.term_structure || null)
        setSpreadSignals(ssRes.data.signals || [])
      } else if (tab === 'inventory') {
        const res = await axios.get(`${API_BASE}/futures/inventory`)
        setInventoryData(res.data.inventory || {})
      } else if (tab === 'indices') {
        const res = await axios.get(`${API_BASE}/futures/commodity-indices`)
        setIndices(res.data.indices || [])
      } else if (tab === 'financial') {
        const res = await axios.get(`${API_BASE}/futures/financial-futures`)
        setFinancialCategories(res.data.categories || {})
      }
    } catch (e) {
      console.error(`加载${tab}数据失败:`, e)
    } finally {
      setLoading(false)
    }
  }, [selectedVar, termVar])

  // Tab切换时加载数据
  useEffect(() => {
    if (!loadedTabs.has(activeTab)) {
      loadTabData(activeTab)
      setLoadedTabs(prev => new Set(prev).add(activeTab))
    }
  }, [activeTab, loadedTabs, loadTabData])

  // 展期收益率品种切换时重新加载
  const handleSelectVar = useCallback(async (v: string) => {
    setSelectedVar(v)
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/futures/roll-yield`, { params: { var: v } })
      setRollYieldData(res.data.roll_yield || [])
    } catch (e) {
      console.error('获取展期收益率失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // 期限结构品种切换
  const handleSelectTermVar = useCallback(async (v: string) => {
    setTermVar(v)
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/futures/term-structure`, { params: { var: v } })
      setTermStructure(res.data.term_structure || null)
    } catch (e) {
      console.error('获取期限结构失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  const tabs = [
    { key: 'overview', label: '商品全景' },
    { key: 'financial', label: '金融期货' },
    { key: 'institutional', label: '机构视角' },
    { key: 'basis', label: '期现分析' },
    { key: 'inventory', label: '库存仓单' },
    { key: 'indices', label: '商品指数' },
  ]

  return (
    <div>
      <PageSection
        title="期货洞察"
        extra={<button className="btn-add" onClick={() => { setLoadedTabs(new Set()); loadTabData(activeTab); setLoadedTabs(new Set([activeTab])) }}>刷新数据</button>}
        compact
      >
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>商品全景 · 金融期货 · 机构持仓 · 期限结构 · 套利信号 · 库存仓单 · 商品指数</span>
      </PageSection>

      <TabBar
        tabs={tabs}
        activeKey={activeTab}
        onChange={k => setActiveTab(k as any)}
        style={{ marginBottom: 16 }}
      />

      {activeTab === 'overview' && <CommodityOverview categories={categories} loading={loading} />}
      {activeTab === 'financial' && <FinancialFuturesView categories={financialCategories} loading={loading} />}
      {activeTab === 'institutional' && (
        <>
          <InstitutionalView
            cotData={cotData} allocation={allocation} loading={loading}
            cotHistory={rollYieldData} selectedVar={selectedVar} onSelectVar={handleSelectVar}
          />
          <div style={{ marginTop: 24 }}>
            <OIPriceAnalysisSection analysis={oiAnalysis} loading={loading} />
          </div>
        </>
      )}
      {activeTab === 'basis' && (
        <>
          <BasisStructure
            basisData={basisData} rollYieldData={rollYieldData}
            selectedVar={selectedVar} onSelectVar={handleSelectVar} loading={loading}
          />
          <div style={{ marginTop: 24 }}>
            <TermStructureSection
              termStructure={termStructure} termVar={termVar}
              onSelectVar={handleSelectTermVar} loading={loading}
            />
          </div>
          <div style={{ marginTop: 24 }}>
            <SpreadSignalsSection signals={spreadSignals} loading={loading} />
          </div>
        </>
      )}
      {activeTab === 'inventory' && <InventoryReceipts inventoryData={inventoryData} loading={loading} />}
      {activeTab === 'indices' && <CommodityIndicesView indices={indices} loading={loading} />}

      <Glossary />

      <div className="arb-notes" style={{ marginTop: 16 }}>
        <h3>数据说明</h3>
        <div className="arb-notes-content">
          <ul>
            <li><strong>商品快照</strong>：主要期货品种实时行情，数据来源AKShare（新浪/东方财富）</li>
            <li><strong>金融期货</strong>：股指期货(IF/IC/IH/IM)和国债期货(T/TF/TS)实时行情</li>
            <li><strong>COT持仓</strong>：交易所公布的前20名多空持仓排名，每日更新</li>
            <li><strong>基差分析</strong>：现货价格来自100ppi.com，期货价格来自交易所</li>
            <li><strong>期限结构</strong>：同一品种不同到期月份合约的价格曲线，反映市场供需预期</li>
            <li><strong>套利信号</strong>：自动检测极端价差、换月压力和蝶式套利机会</li>
            <li><strong>持仓量分析</strong>：主力合约持仓量与价格关系分析，判断多空力量</li>
            <li><strong>库存数据</strong>：东方财富期货库存数据</li>
            <li><strong>商品指数</strong>：中证商品期货指数（CCCI），由中证指数公司编制</li>
            <li><strong>机构配置</strong>：基于桥水、CTA基金公开数据整理，仅供参考</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
