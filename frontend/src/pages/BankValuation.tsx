import { useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { PageSection, StatCard, StatCardGroup } from '../components/ui'

const API_BASE = '/api'

interface BankResult {
  sector: string
  metrics: Record<string, number>
  valuation: Record<string, unknown>
  warnings: string[]
  strengths: string[]
}

export default function BankValuation() {
  const [form, setForm] = useState({
    currentPrice: '', totalShares: '', totalEquity: '', goodwill: '0', intangibleAssets: '0',
    totalAssets: '', netInterestIncome: '', operatingIncome: '', netProfit: '',
    operatingExpense: '', nonPerformingLoans: '', totalLoans: '', loanProvisions: '',
  })
  const [result, setResult] = useState<BankResult | null>(null)
  const [loading, setLoading] = useState(false)

  const handleCalc = async () => {
    const cp = parseFloat(form.currentPrice)
    const ts = parseFloat(form.totalShares)
    const te = parseFloat(form.totalEquity)
    if (!cp || !ts || !te) { alert('请填写股价、总股本、净资产'); return }

    setLoading(true)
    try {
      const body = {
        current_price: cp, total_shares: ts, total_equity: te,
        goodwill: parseFloat(form.goodwill) || 0, intangible_assets: parseFloat(form.intangibleAssets) || 0,
        total_assets: parseFloat(form.totalAssets) || 0,
        net_interest_income: parseFloat(form.netInterestIncome) || 0,
        operating_income: parseFloat(form.operatingIncome) || 0,
        net_profit: parseFloat(form.netProfit) || 0,
        operating_expense: parseFloat(form.operatingExpense) || 0,
        non_performing_loans: parseFloat(form.nonPerformingLoans) || 0,
        total_loans: parseFloat(form.totalLoans) || 0,
        loan_provisions: parseFloat(form.loanProvisions) || 0,
      }
      const res = await fetch(`${API_BASE}/sector-valuation/bank`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json())
      setResult(res)
    } catch (e: any) {
      alert('计算失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', background: '#0d1117', border: '1px solid #30363d', borderRadius: 6, color: '#e6edf3', fontSize: 14 }
  const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 4, color: '#8b949e', fontSize: 13 }

  const getMetricColor = (key: string, val: number) => {
    if (key === 'p_tbv') return val < 0.8 ? '#3fb950' : val < 1.2 ? '#58a6ff' : '#f85149'
    if (key === 'npl_ratio') return val < 1.0 ? '#3fb950' : val < 1.5 ? '#f59e0b' : '#f85149'
    if (key === 'roe') return val > 15 ? '#3fb950' : val > 10 ? '#58a6ff' : '#f85149'
    if (key === 'nim') return val > 2.0 ? '#3fb950' : val > 1.5 ? '#58a6ff' : '#f85149'
    return '#e6edf3'
  }

  // 雷达图
  const getRadarOption = () => {
    if (!result?.metrics) return {}
    const m = result.metrics
    const indicators = [
      { name: 'P/TBV', max: 3 },
      { name: 'NIM', max: 4 },
      { name: 'ROE', max: 25 },
      { name: '资产质量', max: 100 },
      { name: '拨备覆盖', max: 400 },
      { name: '成本效率', max: 100 },
    ]
    const values = [
      m.p_tbv || 0,
      m.nim || 0,
      m.roe || 0,
      100 - (m.npl_ratio || 0) * 20,  // 不良率越低越好
      Math.min(m.provision_coverage || 0, 400),
      100 - (m.cost_income_ratio || 0),
    ]
    return {
      radar: { indicator: indicators, shape: 'circle', splitArea: { areaStyle: { color: ['rgba(88,166,255,0.05)', 'rgba(88,166,255,0.1)'] } }, axisLine: { lineStyle: { color: '#30363d' } }, splitLine: { lineStyle: { color: '#21262d' } }, axisName: { color: '#8b949e', fontSize: 11 } },
      series: [{ type: 'radar', data: [{ value: values, areaStyle: { color: 'rgba(88,166,255,0.2)' }, lineStyle: { color: '#58a6ff', width: 2 }, itemStyle: { color: '#58a6ff' } }] }],
    }
  }

  return (
    <div>
      <PageSection title="银行估值分析">
        <div style={{ display: 'flex', gap: 20 }}>
          {/* 输入面板 */}
          <div style={{ minWidth: 280, padding: 20, background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>市场数据</div>
            <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
              <div><label style={labelStyle}>当前股价 (元)</label><input style={inputStyle} type="number" step="0.01" value={form.currentPrice} onChange={e => setForm({ ...form, currentPrice: e.target.value })} placeholder="5.00" /></div>
              <div><label style={labelStyle}>总股本 (亿股)</label><input style={inputStyle} type="number" value={form.totalShares} onChange={e => setForm({ ...form, totalShares: e.target.value })} placeholder="100" /></div>
            </div>

            <div style={{ fontWeight: 600, marginBottom: 12 }}>资产负债表</div>
            <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
              <div><label style={labelStyle}>净资产 (亿元)</label><input style={inputStyle} type="number" value={form.totalEquity} onChange={e => setForm({ ...form, totalEquity: e.target.value })} placeholder="500" /></div>
              <div><label style={labelStyle}>总资产 (亿元)</label><input style={inputStyle} type="number" value={form.totalAssets} onChange={e => setForm({ ...form, totalAssets: e.target.value })} placeholder="10000" /></div>
              <div><label style={labelStyle}>商誉 (亿元)</label><input style={inputStyle} type="number" value={form.goodwill} onChange={e => setForm({ ...form, goodwill: e.target.value })} /></div>
              <div><label style={labelStyle}>无形资产 (亿元)</label><input style={inputStyle} type="number" value={form.intangibleAssets} onChange={e => setForm({ ...form, intangibleAssets: e.target.value })} /></div>
            </div>

            <div style={{ fontWeight: 600, marginBottom: 12 }}>利润表</div>
            <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
              <div><label style={labelStyle}>净利息收入 (亿元)</label><input style={inputStyle} type="number" value={form.netInterestIncome} onChange={e => setForm({ ...form, netInterestIncome: e.target.value })} placeholder="200" /></div>
              <div><label style={labelStyle}>营业收入 (亿元)</label><input style={inputStyle} type="number" value={form.operatingIncome} onChange={e => setForm({ ...form, operatingIncome: e.target.value })} placeholder="300" /></div>
              <div><label style={labelStyle}>净利润 (亿元)</label><input style={inputStyle} type="number" value={form.netProfit} onChange={e => setForm({ ...form, netProfit: e.target.value })} placeholder="80" /></div>
              <div><label style={labelStyle}>业务管理费 (亿元)</label><input style={inputStyle} type="number" value={form.operatingExpense} onChange={e => setForm({ ...form, operatingExpense: e.target.value })} placeholder="100" /></div>
            </div>

            <div style={{ fontWeight: 600, marginBottom: 12 }}>资产质量</div>
            <div style={{ display: 'grid', gap: 10, marginBottom: 16 }}>
              <div><label style={labelStyle}>不良贷款 (亿元)</label><input style={inputStyle} type="number" value={form.nonPerformingLoans} onChange={e => setForm({ ...form, nonPerformingLoans: e.target.value })} placeholder="50" /></div>
              <div><label style={labelStyle}>贷款总额 (亿元)</label><input style={inputStyle} type="number" value={form.totalLoans} onChange={e => setForm({ ...form, totalLoans: e.target.value })} placeholder="5000" /></div>
              <div><label style={labelStyle}>贷款减值准备 (亿元)</label><input style={inputStyle} type="number" value={form.loanProvisions} onChange={e => setForm({ ...form, loanProvisions: e.target.value })} placeholder="100" /></div>
            </div>

            <button onClick={handleCalc} disabled={loading} style={{ width: '100%', padding: '10px 0', borderRadius: 6, cursor: 'pointer', background: '#58a6ff', border: 'none', color: '#fff', fontWeight: 600 }}>{loading ? '分析中...' : '分析银行估值'}</button>
          </div>

          {/* 结果面板 */}
          <div style={{ flex: 1 }}>
            {!result && <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 500, color: '#8b949e' }}>输入银行财务数据，获取专业估值分析</div>}
            {result && (
              <div>
                {/* 核心指标卡片 */}
                <StatCardGroup columns={4}>
                  {result.metrics.p_tbv !== undefined && <StatCard label="P/TBV" value={result.metrics.p_tbv.toFixed(2)} color={getMetricColor('p_tbv', result.metrics.p_tbv)} />}
                  {result.metrics.nim !== undefined && <StatCard label="NIM净息差" value={result.metrics.nim.toFixed(2) + '%'} color={getMetricColor('nim', result.metrics.nim)} />}
                  {result.metrics.npl_ratio !== undefined && <StatCard label="不良率" value={result.metrics.npl_ratio.toFixed(2) + '%'} color={getMetricColor('npl_ratio', result.metrics.npl_ratio)} />}
                  {result.metrics.roe !== undefined && <StatCard label="ROE" value={result.metrics.roe.toFixed(1) + '%'} color={getMetricColor('roe', result.metrics.roe)} />}
                </StatCardGroup>

                {/* 雷达图 + 详细指标 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
                  <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>综合评估雷达</div>
                    <ReactECharts option={getRadarOption()} style={{ height: 280 }} />
                  </div>
                  <div style={{ background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>详细指标</div>
                    {Object.entries(result.metrics).map(([key, val]) => (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #21262d' }}>
                        <span style={{ color: '#8b949e' }}>{key}</span>
                        <span style={{ color: getMetricColor(key, val as number) }}>{typeof val === 'number' ? val.toFixed(2) : val}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 估值评分 */}
                <div style={{ marginTop: 16, background: '#161b22', borderRadius: 8, border: '1px solid #30363d', padding: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
                    <div style={{ width: 60, height: 60, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: (result.valuation.score as number) >= 70 ? 'rgba(63,185,80,0.15)' : (result.valuation.score as number) >= 50 ? 'rgba(88,166,255,0.15)' : 'rgba(248,81,73,0.15)', border: `2px solid ${(result.valuation.score as number) >= 70 ? '#3fb950' : (result.valuation.score as number) >= 50 ? '#58a6ff' : '#f85149'}` }}>
                      <span style={{ fontSize: 20, fontWeight: 800, color: (result.valuation.score as number) >= 70 ? '#3fb950' : (result.valuation.score as number) >= 50 ? '#58a6ff' : '#f85149' }}>{result.valuation.score as number}</span>
                    </div>
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 700 }}>{result.valuation.grade as string}</div>
                      <div style={{ color: '#8b949e', fontSize: 13 }}>综合估值评分</div>
                    </div>
                  </div>
                </div>

                {/* 优势和风险 */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
                  {result.strengths.length > 0 && (
                    <div style={{ background: 'rgba(63,185,80,0.08)', borderRadius: 8, border: '1px solid rgba(63,185,80,0.2)', padding: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, color: '#3fb950' }}>优势</div>
                      {result.strengths.map((s, i) => <div key={i} style={{ color: '#8b949e', fontSize: 13, marginBottom: 4 }}>{s}</div>)}
                    </div>
                  )}
                  {result.warnings.length > 0 && (
                    <div style={{ background: 'rgba(248,81,73,0.08)', borderRadius: 8, border: '1px solid rgba(248,81,73,0.2)', padding: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, color: '#f85149' }}>风险</div>
                      {result.warnings.map((w, i) => <div key={i} style={{ color: '#8b949e', fontSize: 13, marginBottom: 4 }}>{w}</div>)}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </PageSection>
    </div>
  )
}
