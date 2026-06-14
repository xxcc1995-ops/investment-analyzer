/**
 * 期权计算器（机构级）
 * ====================
 *
 * 功能：
 * 1. BSM 定价模型 — 欧式期权精确定价
 * 2. Greeks 完整展示 — Delta / Gamma / Theta / Vega / Rho
 * 3. 隐含波动率反算 — Newton-Raphson + Bisection 兜底
 * 4. 策略组合分析 — 9 种经典策略 + 自定义多腿
 * 5. 盈亏图可视化 — ECharts 交互式 Payoff / P&L 图表
 * 6. 原有 Sell Put / Sell Call 年化收益计算（保留）
 */

import { useState, useMemo, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import { StatCard, StatCardGroup, PageSection, TabBar } from '../components/ui'

// ============================================================
// 数学工具
// ============================================================

/** 标准正态分布 PDF */
function normPdf(x: number): number {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI)
}

/** 标准正态分布 CDF (Abramowitz & Stegun 近似, 精度 < 7.5e-8) */
function normCdf(x: number): number {
  const a1 = 0.254829592
  const a2 = -0.284496736
  const a3 = 1.421413741
  const a4 = -1.453152027
  const a5 = 1.061405429
  const p = 0.3275911
  const sign = x < 0 ? -1 : 1
  const absX = Math.abs(x)
  const t = 1 / (1 + p * absX)
  const y = 1 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX / 2)
  return 0.5 * (1 + sign * y)
}

// ============================================================
// BSM 模型
// ============================================================

interface BSMInput {
  S: number    // 标的现价
  K: number    // 行权价
  T: number    // 到期时间（年）
  r: number    // 无风险利率（年化, 如 0.03）
  sigma: number // 波动率（年化, 如 0.25）
  q: number    // 连续分红率（默认 0）
}

interface BSMResult {
  callPrice: number
  putPrice: number
  /** Greeks for Call */
  callDelta: number
  callGamma: number
  callTheta: number  // 每日期权价值变化
  callVega: number   // 波动率变化 1% 对应的价格变化
  callRho: number    // 利率变化 1% 对应的价格变化
  /** Greeks for Put */
  putDelta: number
  putGamma: number
  putTheta: number
  putVega: number
  putRho: number
  /** 中间变量 */
  d1: number
  d2: number
}

/** BSM 定价 + Greeks */
export function bsmPrice(input: BSMInput): BSMResult {
  const { S, K, T, r, sigma, q } = input

  // 边界处理
  if (T <= 0 || sigma <= 0 || S <= 0 || K <= 0) {
    const intrinsicCall = Math.max(S - K, 0)
    const intrinsicPut = Math.max(K - S, 0)
    return {
      callPrice: intrinsicCall,
      putPrice: intrinsicPut,
      callDelta: S > K ? 1 : 0, callGamma: 0, callTheta: 0, callVega: 0, callRho: 0,
      putDelta: S < K ? -1 : 0, putGamma: 0, putTheta: 0, putVega: 0, putRho: 0,
      d1: 0, d2: 0,
    }
  }

  const sqrtT = Math.sqrt(T)
  const d1 = (Math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
  const d2 = d1 - sigma * sqrtT

  const Nd1 = normCdf(d1)
  const Nd2 = normCdf(d2)
  const nd1 = normPdf(d1)
  const expNegQT = Math.exp(-q * T)
  const expNegRT = Math.exp(-r * T)

  const callPrice = S * expNegQT * Nd1 - K * expNegRT * Nd2
  const putPrice = K * expNegRT * normCdf(-d2) - S * expNegQT * normCdf(-d1)

  // Greeks — Call
  const callDelta = expNegQT * Nd1
  const callGamma = (expNegQT * nd1) / (S * sigma * sqrtT)
  // Theta: per day (divide by 365)
  const callTheta = (-(S * expNegQT * nd1 * sigma) / (2 * sqrtT)
    - r * K * expNegRT * Nd2
    + q * S * expNegQT * Nd1) / 365
  // Vega: per 1% vol change (divide by 100)
  const callVega = (S * expNegQT * nd1 * sqrtT) / 100
  // Rho: per 1% rate change (divide by 100)
  const callRho = (K * T * expNegRT * Nd2) / 100

  // Greeks — Put
  const putDelta = -expNegQT * normCdf(-d1)
  const putGamma = callGamma
  const putTheta = (-(S * expNegQT * nd1 * sigma) / (2 * sqrtT)
    + r * K * expNegRT * normCdf(-d2)
    - q * S * expNegQT * normCdf(-d1)) / 365
  const putVega = callVega
  const putRho = (-K * T * expNegRT * normCdf(-d2)) / 100

  return {
    callPrice, putPrice,
    callDelta, callGamma, callTheta, callVega, callRho,
    putDelta, putGamma, putTheta, putVega, putRho,
    d1, d2,
  }
}

// ============================================================
// 隐含波动率 (Newton-Raphson + Bisection)
// ============================================================

/** 从市场价格反算隐含波动率 */
export function impliedVolatility(
  marketPrice: number,
  S: number,
  K: number,
  T: number,
  r: number,
  isCall: boolean,
  q: number = 0,
): number | null {
  if (marketPrice <= 0 || T <= 0) return null

  // 内在价值下限
  const intrinsic = isCall ? Math.max(S * Math.exp(-q * T) - K * Math.exp(-r * T), 0) : Math.max(K * Math.exp(-r * T) - S * Math.exp(-q * T), 0)
  if (marketPrice < intrinsic * 0.999) return null

  // Newton-Raphson
  let sigma = Math.sqrt(2 * Math.PI / T) * marketPrice / S  // 初始猜测
  if (sigma < 0.001) sigma = 0.25

  for (let i = 0; i < 100; i++) {
    const result = bsmPrice({ S, K, T, r, sigma, q })
    const price = isCall ? result.callPrice : result.putPrice
    const vegaRaw = (isCall ? result.callVega : result.putVega) * 100 // 还原到单位 sigma

    const diff = price - marketPrice
    if (Math.abs(diff) < 1e-8) return sigma

    if (vegaRaw < 1e-12) break // vega 太小, Newton 失效

    sigma -= diff / vegaRaw
    if (sigma <= 0) sigma = 0.001
    if (sigma > 5) sigma = 5
  }

  // Bisection fallback
  let lo = 0.001, hi = 5
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2
    const result = bsmPrice({ S, K, T, r, sigma: mid, q })
    const price = isCall ? result.callPrice : result.putPrice
    if (price < marketPrice) lo = mid; else hi = mid
    if (hi - lo < 1e-8) return mid
  }
  return (lo + hi) / 2
}

// ============================================================
// 策略组合
// ============================================================

interface Leg {
  type: 'call' | 'put'
  position: 'long' | 'short'
  K: number
  premium: number   // 每份权利金
  quantity: number
}

interface StrategyDef {
  id: string
  name: string
  nameEn: string
  description: string
  legs: (params: StrategyParams) => Leg[]
}

interface StrategyParams {
  S: number
  K1?: number
  K2?: number
  K3?: number
  K4?: number
  callPremiumATM?: number
  putPremiumATM?: number
  callPremiumOTM?: number
  putPremiumOTM?: number
  callPremiumITM?: number
  putPremiumITM?: number
  sigma?: number
  T?: number
  r?: number
}

const STRATEGIES: StrategyDef[] = [
  {
    id: 'covered_call',
    name: '备兑看涨',
    nameEn: 'Covered Call',
    description: '持有标的 + 卖出看涨期权，收取权利金增强收益',
    legs: (p) => [
      { type: 'call', position: 'short', K: p.K1 ?? p.S * 1.05, premium: p.callPremiumOTM ?? p.S * 0.03, quantity: 1 },
    ],
  },
  {
    id: 'protective_put',
    name: '保护性看跌',
    nameEn: 'Protective Put',
    description: '持有标的 + 买入看跌期权，对冲下行风险',
    legs: (p) => [
      { type: 'put', position: 'long', K: p.K1 ?? p.S * 0.95, premium: p.putPremiumOTM ?? p.S * 0.02, quantity: 1 },
    ],
  },
  {
    id: 'bull_call_spread',
    name: '牛市看涨价差',
    nameEn: 'Bull Call Spread',
    description: '买入低行权价看涨 + 卖出高行权价看涨，温和看涨',
    legs: (p) => [
      { type: 'call', position: 'long', K: p.K1 ?? p.S * 0.97, premium: p.callPremiumITM ?? p.S * 0.045, quantity: 1 },
      { type: 'call', position: 'short', K: p.K2 ?? p.S * 1.05, premium: p.callPremiumOTM ?? p.S * 0.02, quantity: 1 },
    ],
  },
  {
    id: 'bear_put_spread',
    name: '熊市看跌价差',
    nameEn: 'Bear Put Spread',
    description: '买入高行权价看跌 + 卖出低行权价看跌，温和看跌',
    legs: (p) => [
      { type: 'put', position: 'long', K: p.K1 ?? p.S * 1.03, premium: p.putPremiumITM ?? p.S * 0.04, quantity: 1 },
      { type: 'put', position: 'short', K: p.K2 ?? p.S * 0.95, premium: p.putPremiumOTM ?? p.S * 0.015, quantity: 1 },
    ],
  },
  {
    id: 'long_straddle',
    name: '多头跨式',
    nameEn: 'Long Straddle',
    description: '同时买入相同行权价的看涨和看跌，押注大幅波动',
    legs: (p) => {
      const K = p.K1 ?? p.S
      return [
        { type: 'call', position: 'long', K, premium: p.callPremiumATM ?? p.S * 0.03, quantity: 1 },
        { type: 'put', position: 'long', K, premium: p.putPremiumATM ?? p.S * 0.03, quantity: 1 },
      ]
    },
  },
  {
    id: 'short_straddle',
    name: '空头跨式',
    nameEn: 'Short Straddle',
    description: '同时卖出相同行权价的看涨和看跌，押注横盘',
    legs: (p) => {
      const K = p.K1 ?? p.S
      return [
        { type: 'call', position: 'short', K, premium: p.callPremiumATM ?? p.S * 0.03, quantity: 1 },
        { type: 'put', position: 'short', K, premium: p.putPremiumATM ?? p.S * 0.03, quantity: 1 },
      ]
    },
  },
  {
    id: 'long_strangle',
    name: '多头宽跨式',
    nameEn: 'Long Strangle',
    description: '买入 OTM 看涨 + OTM 看跌，成本更低但需要更大波动',
    legs: (p) => [
      { type: 'call', position: 'long', K: p.K2 ?? p.S * 1.05, premium: p.callPremiumOTM ?? p.S * 0.015, quantity: 1 },
      { type: 'put', position: 'long', K: p.K1 ?? p.S * 0.95, premium: p.putPremiumOTM ?? p.S * 0.015, quantity: 1 },
    ],
  },
  {
    id: 'iron_condor',
    name: '铁鹰式',
    nameEn: 'Iron Condor',
    description: '卖出 OTM 看涨 + 买入更远 OTM 看涨 + 卖出 OTM 看跌 + 买入更远 OTM 看跌',
    legs: (p) => [
      { type: 'put', position: 'long', K: p.K1 ?? p.S * 0.90, premium: p.putPremiumOTM ?? p.S * 0.005, quantity: 1 },
      { type: 'put', position: 'short', K: p.K2 ?? p.S * 0.95, premium: p.putPremiumOTM ?? p.S * 0.015, quantity: 1 },
      { type: 'call', position: 'short', K: p.K3 ?? p.S * 1.05, premium: p.callPremiumOTM ?? p.S * 0.015, quantity: 1 },
      { type: 'call', position: 'long', K: p.K4 ?? p.S * 1.10, premium: p.callPremiumOTM ?? p.S * 0.005, quantity: 1 },
    ],
  },
  {
    id: 'butterfly',
    name: '蝶式价差',
    nameEn: 'Butterfly Spread',
    description: '买入低K + 卖出2份中K + 买入高K，押注价格在中K附近',
    legs: (p) => {
      const K1 = p.K1 ?? p.S * 0.95
      const K2 = p.K2 ?? p.S
      const K3 = p.K3 ?? p.S * 1.05
      return [
        { type: 'call', position: 'long', K: K1, premium: p.callPremiumITM ?? p.S * 0.055, quantity: 1 },
        { type: 'call', position: 'short', K: K2, premium: p.callPremiumATM ?? p.S * 0.03, quantity: 2 },
        { type: 'call', position: 'long', K: K3, premium: p.callPremiumOTM ?? p.S * 0.015, quantity: 1 },
      ]
    },
  },
]

/** 计算策略在给定标的价格下的组合盈亏 */
function calcStrategyPnL(legs: Leg[], spotPrice: number): number {
  let totalPnL = 0
  for (const leg of legs) {
    const { type, position, K, premium, quantity } = leg
    let payoff: number
    if (type === 'call') {
      payoff = Math.max(spotPrice - K, 0)
    } else {
      payoff = Math.max(K - spotPrice, 0)
    }
    const pnl = position === 'long'
      ? (payoff - premium) * quantity
      : (premium - payoff) * quantity
    totalPnL += pnl
  }
  return totalPnL
}

/** 找到策略的盈亏平衡点 */
function findBreakevenPoints(legs: Leg[], priceMin: number, priceMax: number): number[] {
  const points: number[] = []
  const step = (priceMax - priceMin) / 2000
  let prevPnL = calcStrategyPnL(legs, priceMin)
  for (let p = priceMin + step; p <= priceMax; p += step) {
    const currPnL = calcStrategyPnL(legs, p)
    if (prevPnL * currPnL < 0) {
      // 线性插值
      const x = priceMin + (p - priceMin - step) + step * Math.abs(prevPnL) / (Math.abs(prevPnL) + Math.abs(currPnL))
      points.push(Math.round(x * 100) / 100)
    }
    prevPnL = currPnL
  }
  return points
}

// ============================================================
// 颜色与格式化
// ============================================================

function getYieldColor(yieldVal: number): string {
  if (yieldVal >= 30) return '#52c41a'
  if (yieldVal >= 15) return '#1890ff'
  if (yieldVal >= 5) return '#faad14'
  return '#ff4d4f'
}

function fmt(v: number, d = 4): string {
  return v.toFixed(d)
}

function fmtPct(v: number, d = 2): string {
  return (v * 100).toFixed(d) + '%'
}

function fmtMoney(v: number, d = 2): string {
  return '¥' + v.toFixed(d)
}

// ============================================================
// 主组件
// ============================================================

type PageTab = 'bsm' | 'iv' | 'strategy' | 'yield'

export default function OptionCalculator() {
  const [activeTab, setActiveTab] = useState<PageTab>('bsm')

  const tabs = [
    { key: 'bsm', label: 'BSM定价 / Greeks' },
    { key: 'iv', label: '隐含波动率' },
    { key: 'strategy', label: '策略组合' },
    { key: 'yield', label: '年化收益计算' },
  ]

  return (
    <div className="option-page">
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>期权计算器</h2>
            <span className="stock-code">BSM定价 / Greeks / 隐含波动率 / 策略组合 / 年化收益</span>
          </div>
        </div>
      </div>

      <TabBar tabs={tabs} activeKey={activeTab} onChange={(k) => setActiveTab(k as PageTab)} />

      <div style={{ marginTop: 16 }}>
        {activeTab === 'bsm' && <BSMPanel />}
        {activeTab === 'iv' && <IVPanel />}
        {activeTab === 'strategy' && <StrategyPanel />}
        {activeTab === 'yield' && <YieldPanel />}
      </div>
    </div>
  )
}

// ============================================================
// Tab 1: BSM 定价 + Greeks
// ============================================================

function BSMPanel() {
  const [S, setS] = useState('')
  const [K, setK] = useState('')
  const [T, setT] = useState('')
  const [r, setR] = useState('3')
  const [sigma, setSigma] = useState('')
  const [q, setQ] = useState('0')
  const [result, setResult] = useState<BSMResult | null>(null)
  const [inputValues, setInputValues] = useState({ S: 0, K: 0, T: 0, r: 0, sigma: 0, q: 0 })

  const calculate = useCallback(() => {
    const s = parseFloat(S), k = parseFloat(K), t = parseFloat(T) / 365
    const rateVal = parseFloat(r) / 100, vol = parseFloat(sigma) / 100, div = parseFloat(q || '0') / 100
    if (isNaN(s) || isNaN(k) || isNaN(t) || isNaN(rateVal) || isNaN(vol)) return
    if (s <= 0 || k <= 0 || t <= 0 || vol <= 0) return
    const res = bsmPrice({ S: s, K: k, T: t, r: rateVal, sigma: vol, q: div })
    setResult(res)
    setInputValues({ S: s, K: k, T: t, r: rateVal, sigma: vol, q: div })
  }, [S, K, T, r, sigma, q])

  // Payoff 图表配置
  const chartOption = useMemo(() => {
    if (!result) return null
    const { S: s, K: k } = inputValues
    const range = Math.max(k * 0.3, s * 0.2)
    const minP = Math.max(0, Math.min(s, k) - range)
    const maxP = Math.max(s, k) + range
    const step = (maxP - minP) / 200
    const xData: number[] = []
    const callPnL: number[] = []
    const putPnL: number[] = []
    for (let p = minP; p <= maxP; p += step) {
      xData.push(Math.round(p * 100) / 100)
      callPnL.push(Math.round(((Math.max(p - k, 0) - result.callPrice) * 100)) / 100)
      putPnL.push(Math.round(((Math.max(k - p, 0) - result.putPrice) * 100)) / 100)
    }
    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          let s = `<b>标的价格: ${params[0].axisValue}</b><br/>`
          for (const p of params) {
            s += `${p.marker} ${p.seriesName}: ${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}<br/>`
          }
          return s
        },
      },
      legend: { data: ['Call P&L', 'Put P&L'], top: 4 },
      grid: { left: 60, right: 30, top: 40, bottom: 50 },
      xAxis: {
        type: 'category',
        data: xData,
        name: '标的价格',
        axisLabel: { formatter: (v: string) => parseFloat(v).toFixed(0), interval: 19 },
      },
      yAxis: {
        type: 'value',
        name: '盈亏',
        axisLabel: { formatter: (v: number) => v.toFixed(0) },
      },
      series: [
        {
          name: 'Call P&L',
          type: 'line',
          data: callPnL,
          smooth: true,
          lineStyle: { width: 2 },
          itemStyle: { color: '#ff4d4f' },
          markLine: {
            silent: true,
            data: [{ yAxis: 0, lineStyle: { color: '#666', type: 'dashed' } }],
          },
        },
        {
          name: 'Put P&L',
          type: 'line',
          data: putPnL,
          smooth: true,
          lineStyle: { width: 2 },
          itemStyle: { color: '#1890ff' },
        },
      ],
    }
  }, [result, inputValues])

  return (
    <>
      <PageSection title="BSM 定价模型">
        <div className="option-form-card" style={{ border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
            <div className="option-form-group">
              <label>标的价格 (S)</label>
              <input type="number" step="0.01" placeholder="如 100" value={S} onChange={e => setS(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>行权价 (K)</label>
              <input type="number" step="0.01" placeholder="如 105" value={K} onChange={e => setK(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>到期天数</label>
              <input type="number" min="1" placeholder="如 30" value={T} onChange={e => setT(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>无风险利率 (%)</label>
              <input type="number" step="0.1" placeholder="3" value={r} onChange={e => setR(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>波动率 (%)</label>
              <input type="number" step="0.1" placeholder="如 25" value={sigma} onChange={e => setSigma(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>分红率 (%)</label>
              <input type="number" step="0.1" placeholder="0" value={q} onChange={e => setQ(e.target.value)} />
            </div>
          </div>
          <button className="option-btn" onClick={calculate}>计算期权价格与Greeks</button>
        </div>
      </PageSection>

      {result && (
        <>
          <PageSection title="期权价格">
            <StatCardGroup>
              <StatCard label="Call 价格" value={fmtMoney(result.callPrice)} color="#52c41a" />
              <StatCard label="Put 价格" value={fmtMoney(result.putPrice)} color="#1890ff" />
              <StatCard label="d1" value={fmt(result.d1)} />
              <StatCard label="d2" value={fmt(result.d2)} />
            </StatCardGroup>
          </PageSection>

          <PageSection title="Greeks — Call">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
              <GreeksCard name="Delta (Δ)" value={fmt(result.callDelta)} description="标的价格变化1元，期权价格变化" />
              <GreeksCard name="Gamma (Γ)" value={fmt(result.callGamma)} description="Delta的变化率" />
              <GreeksCard name="Theta (Θ)" value={fmt(result.callTheta)} description="每天时间衰减" suffix="/天" />
              <GreeksCard name="Vega (ν)" value={fmt(result.callVega)} description="波动率变化1%，价格变化" suffix="/1%" />
              <GreeksCard name="Rho (ρ)" value={fmt(result.callRho)} description="利率变化1%，价格变化" suffix="/1%" />
            </div>
          </PageSection>

          <PageSection title="Greeks — Put">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
              <GreeksCard name="Delta (Δ)" value={fmt(result.putDelta)} description="标的价格变化1元，期权价格变化" />
              <GreeksCard name="Gamma (Γ)" value={fmt(result.putGamma)} description="Delta的变化率" />
              <GreeksCard name="Theta (Θ)" value={fmt(result.putTheta)} description="每天时间衰减" suffix="/天" />
              <GreeksCard name="Vega (ν)" value={fmt(result.putVega)} description="波动率变化1%，价格变化" suffix="/1%" />
              <GreeksCard name="Rho (ρ)" value={fmt(result.putRho)} description="利率变化1%，价格变化" suffix="/1%" />
            </div>
          </PageSection>

          {chartOption && (
            <PageSection title="到期盈亏图">
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', padding: 16, border: '1px solid var(--border-primary)' }}>
                <ReactECharts option={chartOption} style={{ height: 400 }} />
              </div>
            </PageSection>
          )}
        </>
      )}
    </>
  )
}

function GreeksCard({ name, value, description, suffix }: { name: string; value: string; description: string; suffix?: string }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-primary)',
      borderRadius: 'var(--radius-md)',
      padding: '14px 16px',
    }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{name}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
        {value}{suffix && <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>{suffix}</span>}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{description}</div>
    </div>
  )
}

// ============================================================
// Tab 2: 隐含波动率
// ============================================================

function IVPanel() {
  const [S, setS] = useState('')
  const [K, setK] = useState('')
  const [T, setT] = useState('')
  const [r, setR] = useState('3')
  const [marketPrice, setMarketPrice] = useState('')
  const [optionType, setOptionType] = useState<'call' | 'put'>('call')
  const [ivResult, setIvResult] = useState<number | null>(null)
  const [bsmResult, setBsmResult] = useState<BSMResult | null>(null)

  const calculate = useCallback(() => {
    const s = parseFloat(S), k = parseFloat(K), t = parseFloat(T) / 365
    const rateVal = parseFloat(r) / 100, mp = parseFloat(marketPrice)
    if (isNaN(s) || isNaN(k) || isNaN(t) || isNaN(rateVal) || isNaN(mp)) return
    const iv = impliedVolatility(mp, s, k, t, rateVal, optionType === 'call')
    setIvResult(iv)
    if (iv !== null) {
      setBsmResult(bsmPrice({ S: s, K: k, T: t, r: rateVal, sigma: iv, q: 0 }))
    } else {
      setBsmResult(null)
    }
  }, [S, K, T, r, marketPrice, optionType])

  // IV 曲面: 波动率 vs 期权价格
  const ivChartOption = useMemo(() => {
    if (!ivResult) return null
    const s = parseFloat(S), k = parseFloat(K), t = parseFloat(T) / 365, rateVal = parseFloat(r) / 100
    if (isNaN(s) || isNaN(k) || isNaN(t)) return null

    const volRange: number[] = []
    const callPrices: number[] = []
    const putPrices: number[] = []
    const mp = parseFloat(marketPrice)
    for (let v = 1; v <= 100; v++) {
      volRange.push(v)
      const res = bsmPrice({ S: s, K: k, T: t, r: rateVal, sigma: v / 100, q: 0 })
      callPrices.push(Math.round(res.callPrice * 100) / 100)
      putPrices.push(Math.round(res.putPrice * 100) / 100)
    }

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          let s = `<b>波动率: ${params[0].axisValue}%</b><br/>`
          for (const p of params) {
            s += `${p.marker} ${p.seriesName}: ${p.value.toFixed(2)}<br/>`
          }
          return s
        },
      },
      legend: { data: ['Call 价格', 'Put 价格'], top: 4 },
      grid: { left: 60, right: 30, top: 40, bottom: 50 },
      xAxis: { type: 'category', data: volRange, name: '波动率 (%)', axisLabel: { interval: 9 } },
      yAxis: { type: 'value', name: '期权价格' },
      series: [
        {
          name: 'Call 价格',
          type: 'line',
          data: callPrices,
          smooth: true,
          itemStyle: { color: '#ff4d4f' },
          markLine: {
            silent: true,
            data: [
              { xAxis: Math.round(ivResult * 100), lineStyle: { color: '#faad14', type: 'solid', width: 2 }, label: { formatter: `IV=${(ivResult * 100).toFixed(2)}%` } },
            ],
          },
        },
        {
          name: 'Put 价格',
          type: 'line',
          data: putPrices,
          smooth: true,
          itemStyle: { color: '#1890ff' },
        },
        {
          name: '市场价格',
          type: 'scatter',
          data: [[Math.round(ivResult * 100), mp]],
          symbolSize: 10,
          itemStyle: { color: '#faad14' },
        },
      ],
    }
  }, [ivResult, S, K, T, r, marketPrice])

  return (
    <>
      <PageSection title="隐含波动率计算">
        <div className="option-form-card" style={{ border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
            <div className="option-form-group">
              <label>标的价格 (S)</label>
              <input type="number" step="0.01" placeholder="如 100" value={S} onChange={e => setS(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>行权价 (K)</label>
              <input type="number" step="0.01" placeholder="如 105" value={K} onChange={e => setK(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>到期天数</label>
              <input type="number" min="1" placeholder="如 30" value={T} onChange={e => setT(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>无风险利率 (%)</label>
              <input type="number" step="0.1" placeholder="3" value={r} onChange={e => setR(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>期权市场价格</label>
              <input type="number" step="0.01" placeholder="如 2.50" value={marketPrice} onChange={e => setMarketPrice(e.target.value)} />
            </div>
            <div className="option-form-group">
              <label>期权类型</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className={`option-btn ${optionType === 'call' ? '' : ''}`}
                  onClick={() => setOptionType('call')}
                  style={{
                    flex: 1,
                    padding: '10px',
                    fontSize: 14,
                    background: optionType === 'call' ? '#ff4d4f' : 'var(--bg-tertiary)',
                    color: optionType === 'call' ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border-primary)',
                  }}
                >Call</button>
                <button
                  className={`option-btn`}
                  onClick={() => setOptionType('put')}
                  style={{
                    flex: 1,
                    padding: '10px',
                    fontSize: 14,
                    background: optionType === 'put' ? '#1890ff' : 'var(--bg-tertiary)',
                    color: optionType === 'put' ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border-primary)',
                  }}
                >Put</button>
              </div>
            </div>
          </div>
          <button className="option-btn" onClick={calculate}>计算隐含波动率</button>
        </div>
      </PageSection>

      {ivResult !== null && (
        <>
          <PageSection title="计算结果">
            <StatCardGroup>
              <StatCard label="隐含波动率 (IV)" value={fmtPct(ivResult)} color="#1890ff" />
              <StatCard label="期权理论价格" value={fmtMoney(optionType === 'call' ? bsmResult!.callPrice : bsmResult!.putPrice)} color="#52c41a" />
              <StatCard label="市场价格" value={fmtMoney(parseFloat(marketPrice))} />
              <StatCard label="波动率等级" value={ivResult > 0.5 ? '极高' : ivResult > 0.3 ? '偏高' : ivResult > 0.15 ? '正常' : '偏低'} color={ivResult > 0.3 ? '#ff4d4f' : '#52c41a'} />
            </StatCardGroup>
          </PageSection>

          {bsmResult && (
            <PageSection title="对应 Greeks">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
                {optionType === 'call' ? (
                  <>
                    <GreeksCard name="Delta" value={fmt(bsmResult.callDelta)} description="方向性敞口" />
                    <GreeksCard name="Gamma" value={fmt(bsmResult.callGamma)} description="Delta加速度" />
                    <GreeksCard name="Theta" value={fmt(bsmResult.callTheta)} description="时间衰减/天" />
                    <GreeksCard name="Vega" value={fmt(bsmResult.callVega)} description="波动率敏感度/1%" />
                    <GreeksCard name="Rho" value={fmt(bsmResult.callRho)} description="利率敏感度/1%" />
                  </>
                ) : (
                  <>
                    <GreeksCard name="Delta" value={fmt(bsmResult.putDelta)} description="方向性敞口" />
                    <GreeksCard name="Gamma" value={fmt(bsmResult.putGamma)} description="Delta加速度" />
                    <GreeksCard name="Theta" value={fmt(bsmResult.putTheta)} description="时间衰减/天" />
                    <GreeksCard name="Vega" value={fmt(bsmResult.putVega)} description="波动率敏感度/1%" />
                    <GreeksCard name="Rho" value={fmt(bsmResult.putRho)} description="利率敏感度/1%" />
                  </>
                )}
              </div>
            </PageSection>
          )}

          {ivChartOption && (
            <PageSection title="波动率-价格关系">
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', padding: 16, border: '1px solid var(--border-primary)' }}>
                <ReactECharts option={ivChartOption} style={{ height: 400 }} />
              </div>
            </PageSection>
          )}
        </>
      )}

      {ivResult === null && marketPrice && (
        <PageSection title="计算结果">
          <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', padding: 32, textAlign: 'center' }}>
            <div style={{ fontSize: 16, color: 'var(--text-muted)' }}>无法计算隐含波动率</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>请检查输入参数是否合理（市场价格不应低于内在价值）</div>
          </div>
        </PageSection>
      )}
    </>
  )
}

// ============================================================
// Tab 3: 策略组合
// ============================================================

function StrategyPanel() {
  const [selectedStrategy, setSelectedStrategy] = useState(STRATEGIES[0].id)
  const [S, setS] = useState('')
  const [K1, setK1] = useState('')
  const [K2, setK2] = useState('')
  const [K3, setK3] = useState('')
  const [K4, setK4] = useState('')
  const [premium1, setPremium1] = useState('')
  const [premium2, setPremium2] = useState('')
  const [premium3, setPremium3] = useState('')
  const [premium4, setPremium4] = useState('')
  const [legs, setLegs] = useState<Leg[] | null>(null)
  const [breakevenPts, setBreakevenPts] = useState<number[]>([])

  const strategy = STRATEGIES.find(s => s.id === selectedStrategy)!

  // 策略选择后，自动填充默认行权价
  const handleStrategyChange = useCallback((id: string) => {
    setSelectedStrategy(id)
    setLegs(null)
    setBreakevenPts([])
  }, [])

  const getStrategyLegs = useCallback((): Leg[] => {
    const s = parseFloat(S)
    if (isNaN(s) || s <= 0) return []

    const strat = STRATEGIES.find(st => st.id === selectedStrategy)!
    const params: StrategyParams = {
      S: s,
      K1: K1 ? parseFloat(K1) : undefined,
      K2: K2 ? parseFloat(K2) : undefined,
      K3: K3 ? parseFloat(K3) : undefined,
      K4: K4 ? parseFloat(K4) : undefined,
    }

    const rawLegs = strat.legs(params)

    // 如果用户填了权利金，覆盖默认值
    if (premium1) rawLegs[0] = { ...rawLegs[0], premium: parseFloat(premium1) }
    if (premium2 && rawLegs.length > 1) rawLegs[1] = { ...rawLegs[1], premium: parseFloat(premium2) }
    if (premium3 && rawLegs.length > 2) rawLegs[2] = { ...rawLegs[2], premium: parseFloat(premium3) }
    if (premium4 && rawLegs.length > 3) rawLegs[3] = { ...rawLegs[3], premium: parseFloat(premium4) }

    return rawLegs
  }, [S, K1, K2, K3, K4, premium1, premium2, premium3, premium4, selectedStrategy])

  const calculate = useCallback(() => {
    const computedLegs = getStrategyLegs()
    if (computedLegs.length === 0) return
    setLegs(computedLegs)

    const s = parseFloat(S)
    const range = s * 0.35
    const minP = Math.max(0, s - range)
    const maxP = s + range
    setBreakevenPts(findBreakevenPoints(computedLegs, minP, maxP))
  }, [getStrategyLegs, S])

  // 策略盈亏图
  const chartOption = useMemo(() => {
    if (!legs || !S) return null
    const s = parseFloat(S)
    const allK = legs.map(l => l.K)
    const range = Math.max(s * 0.25, Math.max(...allK.map(k => Math.abs(k - s))) * 1.5 || s * 0.2)
    const minP = Math.max(0, Math.min(s, ...allK) - range * 0.4)
    const maxP = Math.max(s, ...allK) + range * 0.4
    const step = (maxP - minP) / 300

    const xData: number[] = []
    const pnlData: number[] = []
    for (let p = minP; p <= maxP; p += step) {
      xData.push(Math.round(p * 100) / 100)
      pnlData.push(Math.round(calcStrategyPnL(legs, p) * 100) / 100)
    }

    const maxProfit = Math.max(...pnlData)
    const maxLoss = Math.min(...pnlData)

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any[]) => {
          const p = params[0]
          return `<b>标的价格: ${p.axisValue}</b><br/>盈亏: ${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}`
        },
      },
      grid: { left: 60, right: 30, top: 30, bottom: 50 },
      xAxis: {
        type: 'category',
        data: xData,
        name: '标的价格',
        axisLabel: { formatter: (v: string) => parseFloat(v).toFixed(0), interval: 29 },
      },
      yAxis: {
        type: 'value',
        name: '盈亏',
        axisLabel: { formatter: (v: number) => v.toFixed(0) },
      },
      series: [
        {
          name: '策略盈亏',
          type: 'line',
          data: pnlData,
          smooth: true,
          lineStyle: { width: 2.5 },
          itemStyle: { color: '#1890ff' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(24,144,255,0.25)' },
                { offset: 0.5, color: 'rgba(24,144,255,0)' },
                { offset: 1, color: 'rgba(255,77,79,0.25)' },
              ],
            },
          },
          markLine: {
            silent: true,
            data: [
              { yAxis: 0, lineStyle: { color: '#666', type: 'dashed' } },
              { xAxis: s, lineStyle: { color: '#faad14', type: 'dotted', width: 2 }, label: { formatter: `现价 ${s}` } },
              ...breakevenPts.map(bp => ({
                xAxis: bp,
                lineStyle: { color: '#52c41a', type: 'dashdot' },
                label: { formatter: `BEP ${bp}` },
              })),
            ],
          },
          markPoint: {
            data: [
              ...(maxProfit < Infinity ? [{ coord: [xData[pnlData.indexOf(maxProfit)], maxProfit], value: `+${maxProfit.toFixed(0)}`, itemStyle: { color: '#52c41a' }, label: { fontSize: 11 } }] : []),
              ...(maxLoss > -Infinity ? [{ coord: [xData[pnlData.indexOf(maxLoss)], maxLoss], value: `${maxLoss.toFixed(0)}`, itemStyle: { color: '#ff4d4f' }, label: { fontSize: 11 } }] : []),
            ],
            symbolSize: 60,
          },
        },
      ],
    }
  }, [legs, S, breakevenPts])

  // 策略总成本/收益
  const netCost = useMemo(() => {
    if (!legs) return 0
    return legs.reduce((sum, leg) => {
      const cost = leg.position === 'long' ? -leg.premium * leg.quantity : leg.premium * leg.quantity
      return sum + cost
    }, 0)
  }, [legs])

  const maxProfit = useMemo(() => {
    if (!legs || !S) return null
    const s = parseFloat(S)
    // 有限上界计算
    const testHigh = s * 3
    const pnlHigh = calcStrategyPnL(legs, testHigh)
    const pnlHigher = calcStrategyPnL(legs, testHigh * 1.1)
    if (Math.abs(pnlHigh - pnlHigher) < 0.01) return pnlHigh
    return null // unlimited
  }, [legs, S])

  const maxLoss = useMemo(() => {
    if (!legs || !S) return null
    const s = parseFloat(S)
    const testLow = 0.01
    const pnlLow = calcStrategyPnL(legs, testLow)
    const pnlLower = calcStrategyPnL(legs, 0.001)
    if (Math.abs(pnlLow - pnlLower) < 0.01) return pnlLow
    return null // unlimited
  }, [legs, S])

  // 计算需要几组输入行
  const legCount = useMemo(() => {
    const s = parseFloat(S) || 100
    return strategy.legs({ S: s }).length
  }, [strategy, S])

  return (
    <>
      <PageSection title="策略选择">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8, marginBottom: 16 }}>
          {STRATEGIES.map(s => (
            <button
              key={s.id}
              onClick={() => handleStrategyChange(s.id)}
              style={{
                padding: '12px 14px',
                background: selectedStrategy === s.id ? 'linear-gradient(135deg, var(--accent-blue) 0%, #1f6feb 100%)' : 'var(--bg-secondary)',
                color: selectedStrategy === s.id ? '#fff' : 'var(--text-secondary)',
                border: `1px solid ${selectedStrategy === s.id ? '#1f6feb' : 'var(--border-primary)'}`,
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: selectedStrategy === s.id ? 700 : 500,
                textAlign: 'left' as const,
                transition: 'all 0.2s',
              }}
            >
              <div>{s.name}</div>
              <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{s.nameEn}</div>
            </button>
          ))}
        </div>

        <div style={{
          background: 'var(--bg-tertiary)',
          border: '1px solid var(--border-primary)',
          borderRadius: 'var(--radius-md)',
          padding: '12px 16px',
          marginBottom: 16,
          fontSize: 13,
          color: 'var(--text-secondary)',
        }}>
          <strong style={{ color: 'var(--text-primary)' }}>{strategy.name}</strong> — {strategy.description}
        </div>

        <div className="option-form-card" style={{ border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16 }}>
            <div className="option-form-group">
              <label>标的价格 (S)</label>
              <input type="number" step="0.01" placeholder="如 100" value={S} onChange={e => setS(e.target.value)} />
            </div>
            {legCount >= 1 && (
              <>
                <div className="option-form-group">
                  <label>行权价 K1</label>
                  <input type="number" step="0.01" placeholder="自动" value={K1} onChange={e => setK1(e.target.value)} />
                </div>
                <div className="option-form-group">
                  <label>权利金1</label>
                  <input type="number" step="0.01" placeholder="自动" value={premium1} onChange={e => setPremium1(e.target.value)} />
                </div>
              </>
            )}
            {legCount >= 2 && (
              <>
                <div className="option-form-group">
                  <label>行权价 K2</label>
                  <input type="number" step="0.01" placeholder="自动" value={K2} onChange={e => setK2(e.target.value)} />
                </div>
                <div className="option-form-group">
                  <label>权利金2</label>
                  <input type="number" step="0.01" placeholder="自动" value={premium2} onChange={e => setPremium2(e.target.value)} />
                </div>
              </>
            )}
            {legCount >= 3 && (
              <>
                <div className="option-form-group">
                  <label>行权价 K3</label>
                  <input type="number" step="0.01" placeholder="自动" value={K3} onChange={e => setK3(e.target.value)} />
                </div>
                <div className="option-form-group">
                  <label>权利金3</label>
                  <input type="number" step="0.01" placeholder="自动" value={premium3} onChange={e => setPremium3(e.target.value)} />
                </div>
              </>
            )}
            {legCount >= 4 && (
              <>
                <div className="option-form-group">
                  <label>行权价 K4</label>
                  <input type="number" step="0.01" placeholder="自动" value={K4} onChange={e => setK4(e.target.value)} />
                </div>
                <div className="option-form-group">
                  <label>权利金4</label>
                  <input type="number" step="0.01" placeholder="自动" value={premium4} onChange={e => setPremium4(e.target.value)} />
                </div>
              </>
            )}
          </div>
          <button className="option-btn" onClick={calculate}>计算策略盈亏</button>
        </div>
      </PageSection>

      {legs && (
        <>
          <PageSection title="策略概览">
            <StatCardGroup>
              <StatCard label="净收入/支出" value={fmtMoney(netCost)} color={netCost >= 0 ? '#52c41a' : '#ff4d4f'} />
              <StatCard label="最大盈利" value={maxProfit !== null ? fmtMoney(maxProfit) : '无限'} color="#52c41a" />
              <StatCard label="最大亏损" value={maxLoss !== null ? fmtMoney(maxLoss) : '无限'} color="#ff4d4f" />
              <StatCard label="盈亏平衡" value={breakevenPts.length > 0 ? breakevenPts.map(v => fmtMoney(v)).join(' / ') : 'N/A'} />
            </StatCardGroup>
          </PageSection>

          <PageSection title="策略腿明细">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
              {legs.map((leg, i) => (
                <div key={i} style={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-primary)',
                  borderRadius: 'var(--radius-md)',
                  padding: '14px 16px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '2px 10px',
                      borderRadius: 12,
                      fontSize: 12,
                      fontWeight: 700,
                      background: leg.position === 'long' ? 'rgba(82,196,26,0.15)' : 'rgba(255,77,79,0.15)',
                      color: leg.position === 'long' ? '#52c41a' : '#ff4d4f',
                    }}>
                      {leg.position === 'long' ? '买入' : '卖出'} {leg.type === 'call' ? 'Call' : 'Put'}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>x{leg.quantity}</span>
                  </div>
                  <div className="option-detail-row">
                    <span>行权价</span>
                    <span>{fmtMoney(leg.K)}</span>
                  </div>
                  <div className="option-detail-row">
                    <span>权利金</span>
                    <span>{fmtMoney(leg.premium)}</span>
                  </div>
                  <div className="option-detail-row">
                    <span>成本/收入</span>
                    <span style={{ color: leg.position === 'long' ? '#ff4d4f' : '#52c41a' }}>
                      {leg.position === 'long' ? '-' : '+'}{fmtMoney(leg.premium * leg.quantity)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </PageSection>

          {chartOption && (
            <PageSection title="策略盈亏图">
              <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', padding: 16, border: '1px solid var(--border-primary)' }}>
                <ReactECharts option={chartOption} style={{ height: 450 }} />
              </div>
            </PageSection>
          )}
        </>
      )}
    </>
  )
}

// ============================================================
// Tab 4: 年化收益计算 (原有功能，增强版)
// ============================================================

function YieldPanel() {
  const [optionTab, setOptionTab] = useState<'put' | 'call'>('put')

  // Sell Put
  const [putPremium, setPutPremium] = useState('')
  const [putStrike, setPutStrike] = useState('')
  const [putDays, setPutDays] = useState('')
  const [putCollateral, setPutCollateral] = useState('')
  const [putResult, setPutResult] = useState<{ annualYield: number; profit: number; annualFactor: number; maxLoss: number; returnOnRisk: number } | null>(null)

  // Sell Call
  const [callCurrentPrice, setCallCurrentPrice] = useState('')
  const [callPremium, setCallPremium] = useState('')
  const [callStrike, setCallStrike] = useState('')
  const [callDays, setCallDays] = useState('')
  const [callShares, setCallShares] = useState('')
  const [callResult, setCallResult] = useState<{ annualYield: number; totalProfit: number; investment: number; maxProfit: number; maxLoss: number } | null>(null)

  const calculatePut = useCallback(() => {
    const premium = parseFloat(putPremium)
    const strike = parseFloat(putStrike)
    const days = parseInt(putDays)
    if (isNaN(premium) || isNaN(strike) || isNaN(days) || premium <= 0 || strike <= 0 || days <= 0) return
    const collateral = putCollateral ? parseFloat(putCollateral) : strike - premium
    if (collateral <= 0) return
    const profit = premium
    const annualFactor = 365 / days
    const annualYield = (profit / collateral) * annualFactor * 100
    const maxLoss = collateral  // 最坏情况: 行权价归零（裸卖put理论上无限，但保证金模式下近似为行权价）
    const returnOnRisk = (profit / maxLoss) * 100
    setPutResult({ annualYield, profit, annualFactor, maxLoss, returnOnRisk })
  }, [putPremium, putStrike, putDays, putCollateral])

  const calculateCall = useCallback(() => {
    const currentPrice = parseFloat(callCurrentPrice)
    const premium = parseFloat(callPremium)
    const strike = parseFloat(callStrike)
    const days = parseInt(callDays)
    if (isNaN(currentPrice) || isNaN(premium) || isNaN(strike) || isNaN(days)) return
    if (currentPrice <= 0 || days <= 0 || currentPrice - premium <= 0) return
    const shares = callShares ? parseInt(callShares) : 100
    const totalProfit = (strike - currentPrice + premium) * shares
    const investment = (currentPrice - premium) * shares
    const maxProfit = totalProfit  // 被行权时的最大利润
    const maxLoss = investment * -1  // 理论上裸call无限亏损，这里给出参考值
    const annualYield = (totalProfit / investment) * (365 / days) * 100
    setCallResult({ annualYield, totalProfit, investment, maxProfit, maxLoss })
  }, [callCurrentPrice, callPremium, callStrike, callDays, callShares])

  // Put 年化收益 vs 到期天数图表
  const putChartOption = useMemo(() => {
    if (!putResult) return null
    const premium = parseFloat(putPremium)
    const strike = parseFloat(putStrike)
    if (isNaN(premium) || isNaN(strike)) return null
    const collateral = putCollateral ? parseFloat(putCollateral) : strike - premium
    if (collateral <= 0) return null

    const daysArr: number[] = []
    const yields: number[] = []
    for (let d = 7; d <= 180; d += 7) {
      daysArr.push(d)
      yields.push(Math.round((premium / collateral) * (365 / d) * 10000) / 100)
    }
    return {
      tooltip: { trigger: 'axis', formatter: (params: any[]) => `到期天数: ${params[0].axisValue}<br/>年化收益: ${params[0].value}%` },
      grid: { left: 60, right: 30, top: 20, bottom: 50 },
      xAxis: { type: 'category', data: daysArr, name: '到期天数' },
      yAxis: { type: 'value', name: '年化收益 (%)' },
      series: [{
        type: 'line',
        data: yields,
        smooth: true,
        itemStyle: { color: '#52c41a' },
        areaStyle: { color: 'rgba(82,196,26,0.15)' },
      }],
    }
  }, [putResult, putPremium, putStrike, putCollateral])

  return (
    <>
      <div className="option-tabs">
        <div className={`option-tab ${optionTab === 'put' ? 'active' : ''}`}
          onClick={() => setOptionTab('put')}>Sell Put</div>
        <div className={`option-tab ${optionTab === 'call' ? 'active' : ''}`}
          onClick={() => setOptionTab('call')}>Sell Call</div>
      </div>

      <div className="option-form-card">
        {optionTab === 'put' ? (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
              <div className="option-form-group">
                <label>权利金收入</label>
                <input type="number" min="0" step="0.01" placeholder="权利金"
                  value={putPremium} onChange={e => setPutPremium(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>行权价</label>
                <input type="number" min="0" step="0.01" placeholder="行权价"
                  value={putStrike} onChange={e => setPutStrike(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>到期天数</label>
                <input type="number" min="1" max="365" placeholder="到期天数"
                  value={putDays} onChange={e => setPutDays(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>保证金/成本 (可选)</label>
                <input type="number" min="0" step="0.01" placeholder="默认=行权价-权利金"
                  value={putCollateral} onChange={e => setPutCollateral(e.target.value)} />
              </div>
            </div>
            <button className="option-btn" onClick={calculatePut}>计算年化收益率</button>

            {putResult && (
              <>
                <div className="option-result">
                  <div className="option-result-header">年化收益率</div>
                  <div className="option-result-value" style={{ color: getYieldColor(putResult.annualYield) }}>
                    {putResult.annualYield.toFixed(2)}%
                  </div>
                  <div className="option-result-details">
                    <div className="option-detail-row">
                      <span>期权利润：</span>
                      <span>¥{putResult.profit.toFixed(2)}</span>
                    </div>
                    <div className="option-detail-row">
                      <span>年化系数：</span>
                      <span>{putResult.annualFactor.toFixed(2)}</span>
                    </div>
                    <div className="option-detail-row">
                      <span>最大风险：</span>
                      <span style={{ color: '#ff4d4f' }}>¥{putResult.maxLoss.toFixed(2)}</span>
                    </div>
                    <div className="option-detail-row">
                      <span>风险收益率：</span>
                      <span>{putResult.returnOnRisk.toFixed(2)}%</span>
                    </div>
                  </div>
                </div>
                {putChartOption && (
                  <div style={{ marginTop: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', padding: 16, border: '1px solid var(--border-primary)' }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>年化收益 vs 到期天数</div>
                    <ReactECharts option={putChartOption} style={{ height: 280 }} />
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
              <div className="option-form-group">
                <label>现价</label>
                <input type="number" step="0.01" placeholder="现价"
                  value={callCurrentPrice} onChange={e => setCallCurrentPrice(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>权利金收入</label>
                <input type="number" step="0.01" placeholder="权利金"
                  value={callPremium} onChange={e => setCallPremium(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>行权价</label>
                <input type="number" step="0.01" placeholder="行权价"
                  value={callStrike} onChange={e => setCallStrike(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>到期天数</label>
                <input type="number" min="1" placeholder="到期天数"
                  value={callDays} onChange={e => setCallDays(e.target.value)} />
              </div>
              <div className="option-form-group">
                <label>合约张数 (可选)</label>
                <input type="number" min="1" placeholder="默认100股"
                  value={callShares} onChange={e => setCallShares(e.target.value)} />
              </div>
            </div>
            <button className="option-btn" onClick={calculateCall}>计算年化收益率</button>

            {callResult && (
              <div className="option-result">
                <div className="option-result-header">年化收益率</div>
                <div className="option-result-value" style={{ color: getYieldColor(callResult.annualYield) }}>
                  {callResult.annualYield.toFixed(2)}%
                </div>
                <div className="option-result-details">
                  <div className="option-detail-row">
                    <span>总收益：</span>
                    <span style={{ color: '#52c41a' }}>¥{callResult.totalProfit.toFixed(2)}</span>
                  </div>
                  <div className="option-detail-row">
                    <span>投资金额：</span>
                    <span>¥{callResult.investment.toFixed(2)}</span>
                  </div>
                  <div className="option-detail-row">
                    <span>最大利润（被行权）：</span>
                    <span style={{ color: '#52c41a' }}>¥{callResult.maxProfit.toFixed(2)}</span>
                  </div>
                  <div className="option-detail-row">
                    <span>盈亏平衡价：</span>
                    <span>{fmtMoney(parseFloat(callCurrentPrice) - parseFloat(callPremium))}</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="option-notes">
        <h3>使用说明</h3>
        <div className="option-notes-content">
          <div className="option-note-section">
            <h4>Sell Put 计算器</h4>
            <p>适用于未被行权的情况（以保证金模式持有至到期）</p>
            <p className="option-formula">年化收益率 = (权利金 / 保证金) x (365 / 到期天数) x 100%</p>
          </div>
          <div className="option-note-section">
            <h4>Sell Call 计算器</h4>
            <p>适用于被行权的情况（covered call，持有正股）</p>
            <p className="option-formula">年化收益率 = (行权价 - 现价 + 权利金) / (现价 - 权利金) x (365 / 到期天数) x 100%</p>
          </div>
          <div className="option-note-section">
            <h4>BSM 模型</h4>
            <p>Black-Scholes-Merton 定价公式，适用于欧式期权。Greeks 解释：</p>
            <p className="option-formula">Delta: 标的变动1元 → 期权价格变动量 | Gamma: Delta的变动率 | Theta: 每日时间价值衰减 | Vega: 波动率变动1% → 价格变动量 | Rho: 利率变动1% → 价格变动量</p>
          </div>
          <div className="option-note-section">
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>
              实际交易中请考虑交易成本、滑点、保证金变动、提前行权风险等因素。BSM模型假设波动率恒定且标的服从对数正态分布，实际市场存在波动率微笑和跳跃风险。
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
