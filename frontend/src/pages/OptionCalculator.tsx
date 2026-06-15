/**
 * 期权年化收益计算器
 * ==================
 * Covered Call & Cash Secured Put 扣费后年化收益计算
 */

import { useState, useMemo, useCallback } from 'react'
import ReactECharts from 'echarts-for-react'
import { PageSection } from '../components/ui'

// ============================================================
// 工具函数
// ============================================================

function getYieldColor(y: number): string {
  if (y >= 30) return '#52c41a'
  if (y >= 15) return '#1890ff'
  if (y >= 5) return '#faad14'
  return '#ff4d4f'
}

function fmtMoney(v: number, d = 2): string {
  return 'HK$' + v.toFixed(d)
}

// ============================================================
// 主组件
// ============================================================

export default function OptionCalculator() {
  // 手续费
  const [tradeFee, setTradeFee] = useState('16')
  const [exerciseFee, setExerciseFee] = useState('100')

  // CSP
  const [putPremium, setPutPremium] = useState('')
  const [putStrike, setPutStrike] = useState('')
  const [putDays, setPutDays] = useState('')
  const [putCollateral, setPutCollateral] = useState('')
  const [putResult, setPutResult] = useState<{
    annualYield: number; annualYieldNet: number; profit: number; profitNet: number;
    annualFactor: number; maxLoss: number; returnOnRisk: number; totalFees: number
  } | null>(null)

  // CC
  const [callSpot, setCallSpot] = useState('')
  const [callPremium, setCallPremium] = useState('')
  const [callStrike, setCallStrike] = useState('')
  const [callDays, setCallDays] = useState('')
  const [callShares, setCallShares] = useState('')
  const [callResult, setCallResult] = useState<{
    annualYield: number; annualYieldNet: number; totalProfit: number; totalProfitNet: number;
    investment: number; maxProfitNet: number; totalFees: number; breakeven: number
  } | null>(null)

  // ── CSP 计算 ──
  const calculatePut = useCallback(() => {
    const premium = parseFloat(putPremium)
    const strike = parseFloat(putStrike)
    const days = parseInt(putDays)
    if (isNaN(premium) || isNaN(strike) || isNaN(days) || premium <= 0 || strike <= 0 || days <= 0) return
    const collateral = putCollateral ? parseFloat(putCollateral) : strike - premium
    if (collateral <= 0) return
    const fv = parseFloat(tradeFee) || 0
    const ef = parseFloat(exerciseFee) || 0
    const totalFees = fv + ef
    const profit = premium
    const profitNet = premium - fv
    const annualFactor = 365 / days
    const annualYield = (profit / collateral) * annualFactor * 100
    const annualYieldNet = (profitNet / collateral) * annualFactor * 100
    const maxLoss = collateral + fv + ef
    const returnOnRisk = (profitNet / maxLoss) * 100
    setPutResult({ annualYield, annualYieldNet, profit, profitNet, annualFactor, maxLoss, returnOnRisk, totalFees })
  }, [putPremium, putStrike, putDays, putCollateral, tradeFee, exerciseFee])

  // ── CC 计算 ──
  const calculateCall = useCallback(() => {
    const spot = parseFloat(callSpot)
    const premium = parseFloat(callPremium)
    const strike = parseFloat(callStrike)
    const days = parseInt(callDays)
    if (isNaN(spot) || isNaN(premium) || isNaN(strike) || isNaN(days)) return
    if (spot <= 0 || days <= 0) return
    const shares = callShares ? parseInt(callShares) : 100
    const fv = parseFloat(tradeFee) || 0
    const ef = parseFloat(exerciseFee) || 0
    const totalFees = fv + ef
    const totalProfit = (strike - spot + premium) * shares
    const totalProfitNet = totalProfit - fv - ef
    const investment = spot * shares
    const breakeven = spot - premium + (fv + ef) / shares
    const annualYield = (totalProfit / investment) * (365 / days) * 100
    const annualYieldNet = (totalProfitNet / investment) * (365 / days) * 100
    setCallResult({ annualYield, annualYieldNet, totalProfit, totalProfitNet, investment, maxProfitNet: totalProfitNet, totalFees, breakeven })
  }, [callSpot, callPremium, callStrike, callDays, callShares, tradeFee, exerciseFee])

  // ── CSP 图表 ──
  const putChart = useMemo(() => {
    if (!putResult) return null
    const premium = parseFloat(putPremium)
    const strike = parseFloat(putStrike)
    if (isNaN(premium) || isNaN(strike)) return null
    const collateral = putCollateral ? parseFloat(putCollateral) : strike - premium
    if (collateral <= 0) return null
    const fv = parseFloat(tradeFee) || 0
    const daysArr: number[] = [], gross: number[] = [], net: number[] = []
    for (let d = 7; d <= 180; d += 7) {
      daysArr.push(d)
      gross.push(Math.round((premium / collateral) * (365 / d) * 10000) / 100)
      net.push(Math.round(((premium - fv) / collateral) * (365 / d) * 10000) / 100)
    }
    const tooltipFormatter = (p: any[]) => { let s = `${p[0].axisValue}天<br/>`; p.forEach((x: any) => { s += `${x.marker} ${x.seriesName}: ${x.value}%<br/>` }); return s; }
    return {
      tooltip: { trigger: 'axis' as const, formatter: tooltipFormatter },
      legend: { data: ['扣费前', '扣费后'], top: 4, textStyle: { color: '#999', fontSize: 11 } },
      grid: { left: 50, right: 20, top: 40, bottom: 40 },
      xAxis: { type: 'category' as const, data: daysArr, axisLabel: { color: '#999', fontSize: 11 } },
      yAxis: { type: 'value' as const, axisLabel: { color: '#999', fontSize: 11, formatter: '{value}%' } },
      series: [
        { name: '扣费前', type: 'line' as const, data: gross, smooth: true, lineStyle: { type: 'dashed' as const, color: '#52c41a' }, itemStyle: { color: '#52c41a' }, symbol: 'none' },
        { name: '扣费后', type: 'line' as const, data: net, smooth: true, itemStyle: { color: '#1890ff' }, areaStyle: { color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(24,144,255,0.2)' }, { offset: 1, color: 'rgba(24,144,255,0)' }] } }, symbol: 'none' },
      ],
    }
  }, [putResult, putPremium, putStrike, putCollateral, tradeFee])

  // ── CC 图表 ──
  const callChart = useMemo(() => {
    if (!callResult) return null
    const spot = parseFloat(callSpot)
    const premium = parseFloat(callPremium)
    const strike = parseFloat(callStrike)
    if (isNaN(spot) || isNaN(premium) || isNaN(strike)) return null
    const shares = callShares ? parseInt(callShares) : 100
    const fv = parseFloat(tradeFee) || 0
    const ef = parseFloat(exerciseFee) || 0
    const daysArr: number[] = [], gross: number[] = [], net: number[] = []
    for (let d = 7; d <= 180; d += 7) {
      daysArr.push(d)
      const gp = ((strike - spot + premium) * shares) / (spot * shares) * (365 / d) * 100
      const np = ((strike - spot + premium) * shares - fv - ef) / (spot * shares) * (365 / d) * 100
      gross.push(Math.round(gp * 100) / 100)
      net.push(Math.round(np * 100) / 100)
    }
    const tooltipFormatter = (p: any[]) => { let s = `${p[0].axisValue}天<br/>`; p.forEach((x: any) => { s += `${x.marker} ${x.seriesName}: ${x.value}%<br/>` }); return s; }
    return {
      tooltip: { trigger: 'axis' as const, formatter: tooltipFormatter },
      legend: { data: ['扣费前', '扣费后'], top: 4, textStyle: { color: '#999', fontSize: 11 } },
      grid: { left: 50, right: 20, top: 40, bottom: 40 },
      xAxis: { type: 'category' as const, data: daysArr, axisLabel: { color: '#999', fontSize: 11 } },
      yAxis: { type: 'value' as const, axisLabel: { color: '#999', fontSize: 11, formatter: '{value}%' } },
      series: [
        { name: '扣费前', type: 'line' as const, data: gross, smooth: true, lineStyle: { type: 'dashed' as const, color: '#52c41a' }, itemStyle: { color: '#52c41a' }, symbol: 'none' },
        { name: '扣费后', type: 'line' as const, data: net, smooth: true, itemStyle: { color: '#1890ff' }, areaStyle: { color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(24,144,255,0.2)' }, { offset: 1, color: 'rgba(24,144,255,0)' }] } }, symbol: 'none' },
      ],
    }
  }, [callResult, callSpot, callPremium, callStrike, callDays, callShares, tradeFee, exerciseFee])

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          期权年化收益计算器
        </h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '6px 0 0' }}>
          Covered Call / Cash Secured Put — 扣除港股手续费后的真实年化收益
        </p>
      </div>

      {/* 手续费 */}
      <div style={{
        background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-lg)', padding: '16px 20px', marginBottom: 20,
        display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>💰 手续费设置</span>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
          交易费
          <input type="number" min="0" step="1" value={tradeFee} onChange={e => setTradeFee(e.target.value)}
            style={{ width: 70, padding: '5px 8px', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', fontSize: 13 }} />
          HK$
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
          行权费
          <input type="number" min="0" step="1" value={exerciseFee} onChange={e => setExerciseFee(e.target.value)}
            style={{ width: 70, padding: '5px 8px', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-sm)', fontSize: 13 }} />
          HK$
        </label>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>开仓/平仓各收一次，行权时额外收取</span>
      </div>

      {/* 双栏布局 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* ── CSP ── */}
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span style={{ color: '#1890ff', fontSize: 16, fontWeight: 700 }}>📉 Cash Secured Put</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>卖Put + 准备现金</span>
          </div>
          <div style={formGridStyle}>
            <div style={formGroupStyle}>
              <label style={labelStyle}>权利金 (每股)</label>
              <input type="number" step="0.01" placeholder="如 2.50" value={putPremium} onChange={e => setPutPremium(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>行权价</label>
              <input type="number" step="0.01" placeholder="如 450" value={putStrike} onChange={e => setPutStrike(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>到期天数</label>
              <input type="number" min="1" placeholder="如 30" value={putDays} onChange={e => setPutDays(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>保证金 (可选)</label>
              <input type="number" step="0.01" placeholder="默认=行权价-权利金" value={putCollateral} onChange={e => setPutCollateral(e.target.value)} style={inputStyle} />
            </div>
          </div>
          <button style={btnStyle} onClick={calculatePut}>计算年化收益</button>

          {putResult && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={resultCardStyle}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>扣费前年化</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: getYieldColor(putResult.annualYield), fontFamily: 'var(--font-mono)' }}>
                    {putResult.annualYield.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>利润 {fmtMoney(putResult.profit)}</div>
                </div>
                <div style={{ ...resultCardStyle, border: '2px solid #1890ff' }}>
                  <div style={{ fontSize: 11, color: '#1890ff', fontWeight: 600 }}>✨ 扣费后年化</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: getYieldColor(putResult.annualYieldNet), fontFamily: 'var(--font-mono)' }}>
                    {putResult.annualYieldNet.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: 12, color: '#52c41a', marginTop: 4 }}>净利 {fmtMoney(putResult.profitNet)}</div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12 }}>
                <div style={miniCardStyle}>
                  <div style={miniLabelStyle}>年化系数</div>
                  <div style={miniValueStyle}>{putResult.annualFactor.toFixed(2)}x</div>
                </div>
                <div style={miniCardStyle}>
                  <div style={miniLabelStyle}>手续费(最坏)</div>
                  <div style={{ ...miniValueStyle, color: '#ff4d4f' }}>{fmtMoney(putResult.totalFees)}</div>
                </div>
                <div style={miniCardStyle}>
                  <div style={miniLabelStyle}>风险收益率</div>
                  <div style={miniValueStyle}>{putResult.returnOnRisk.toFixed(2)}%</div>
                </div>
              </div>
              {putChart && (
                <div style={{ marginTop: 16, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>年化 vs 到期天数</div>
                  <ReactECharts option={putChart} style={{ height: 220 }} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── CC ── */}
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <span style={{ color: '#52c41a', fontSize: 16, fontWeight: 700 }}>📈 Covered Call</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>持有正股 + 卖Call</span>
          </div>
          <div style={formGridStyle}>
            <div style={formGroupStyle}>
              <label style={labelStyle}>正股现价</label>
              <input type="number" step="0.01" placeholder="如 480" value={callSpot} onChange={e => setCallSpot(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>权利金 (每股)</label>
              <input type="number" step="0.01" placeholder="如 3.50" value={callPremium} onChange={e => setCallPremium(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>行权价</label>
              <input type="number" step="0.01" placeholder="如 500" value={callStrike} onChange={e => setCallStrike(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>到期天数</label>
              <input type="number" min="1" placeholder="如 30" value={callDays} onChange={e => setCallDays(e.target.value)} style={inputStyle} />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>股数 (可选)</label>
              <input type="number" min="1" placeholder="默认100" value={callShares} onChange={e => setCallShares(e.target.value)} style={inputStyle} />
            </div>
          </div>
          <button style={{ ...btnStyle, background: '#52c41a', color: '#000' }} onClick={calculateCall}>计算年化收益</button>

          {callResult && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={resultCardStyle}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>扣费前年化</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: getYieldColor(callResult.annualYield), fontFamily: 'var(--font-mono)' }}>
                    {callResult.annualYield.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>收益 {fmtMoney(callResult.totalProfit)}</div>
                </div>
                <div style={{ ...resultCardStyle, border: '2px solid #52c41a' }}>
                  <div style={{ fontSize: 11, color: '#52c41a', fontWeight: 600 }}>✨ 扣费后年化</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: getYieldColor(callResult.annualYieldNet), fontFamily: 'var(--font-mono)' }}>
                    {callResult.annualYieldNet.toFixed(2)}%
                  </div>
                  <div style={{ fontSize: 12, color: '#52c41a', marginTop: 4 }}>净利 {fmtMoney(callResult.maxProfitNet)}</div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 12 }}>
                <div style={miniCardStyle}>
                  <div style={miniLabelStyle}>正股成本</div>
                  <div style={miniValueStyle}>{fmtMoney(callResult.investment)}</div>
                </div>
                <div style={miniCardStyle}>
                  <div style={miniLabelStyle}>手续费</div>
                  <div style={{ ...miniValueStyle, color: '#ff4d4f' }}>{fmtMoney(callResult.totalFees)}</div>
                </div>
                <div style={miniCardStyle}>
                  <div style={miniLabelStyle}>盈亏平衡</div>
                  <div style={miniValueStyle}>{fmtMoney(callResult.breakeven)}</div>
                </div>
              </div>
              {callChart && (
                <div style={{ marginTop: 16, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>年化 vs 到期天数</div>
                  <ReactECharts option={callChart} style={{ height: 220 }} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 说明 */}
      <div style={{
        marginTop: 24, padding: '16px 20px',
        background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)',
        borderRadius: 'var(--radius-lg)', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8,
      }}>
        <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>📖 公式说明</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ fontWeight: 600, color: '#1890ff', marginBottom: 4 }}>Cash Secured Put</div>
            <div>不被行权时收益最高：扣费后年化 = (权利金 − 交易费) ÷ 保证金 × (365 ÷ 天数)</div>
            <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>被行权时：利润 = 权利金 − 交易费 − 行权费</div>
          </div>
          <div>
            <div style={{ fontWeight: 600, color: '#52c41a', marginBottom: 4 }}>Covered Call</div>
            <div>被行权时：扣费后年化 = (行权价 − 现价 + 权利金 − 手续费) ÷ 正股成本 × (365 ÷ 天数)</div>
            <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>手续费默认按最坏情况（被行权）计算</div>
          </div>
        </div>
        <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--text-muted)' }}>
          💡 港股期权手续费：交易 HK$16/笔（开仓+平仓各一次），行权 HK$100。
        </div>
      </div>
    </div>
  )
}

// ============================================================
// 样式常量
// ============================================================

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-secondary)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-lg)',
  padding: '20px 22px',
}

const cardHeaderStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 16,
  paddingBottom: 12,
  borderBottom: '1px solid var(--border-primary)',
}

const formGridStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  gap: 12,
}

const formGroupStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text-secondary)',
}

const inputStyle: React.CSSProperties = {
  padding: '8px 10px',
  fontSize: 14,
  fontFamily: 'var(--font-mono)',
  background: 'var(--bg-tertiary)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-sm)',
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
}

const btnStyle: React.CSSProperties = {
  marginTop: 14,
  padding: '10px 0',
  width: '100%',
  fontSize: 14,
  fontWeight: 700,
  background: '#1890ff',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
}

const resultCardStyle: React.CSSProperties = {
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border-primary)',
  borderRadius: 'var(--radius-md)',
  padding: '14px 16px',
  textAlign: 'center',
}

const miniCardStyle: React.CSSProperties = {
  background: 'var(--bg-tertiary)',
  borderRadius: 'var(--radius-sm)',
  padding: '8px 10px',
  textAlign: 'center',
}

const miniLabelStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--text-muted)',
  marginBottom: 2,
}

const miniValueStyle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  color: 'var(--text-primary)',
  fontFamily: 'var(--font-mono)',
}
