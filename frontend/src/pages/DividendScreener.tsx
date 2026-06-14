import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { PageSection, TabBar, DataTable, LoadingSpinner, StatCard, StatCardGroup } from '../components/ui'
import type { Column } from '../components/ui'

const API_BASE = '/api'

interface DividendStock {
  code: string
  name: string
  price: number
  pe: number | null
  pb: number | null
  roe: number | null
  dividend_yield: number | null
  dividend_ratio: number | null
  debt_ratio: number | null
  gross_margin: number | null
  net_margin: number | null
  revenue_growth: number | null
  profit_growth: number | null
  market_cap: number
  consecutive_years: number
  report_period: string
  score: number
  match_level: 'excellent' | 'good' | 'fair'
  dividend_cagr_3y: number | null
  dividend_cagr_5y: number | null
  payout_sustainability: string | null
  has_special_dividend: boolean
}

interface CalculatorInputs {
  stock_price: string
  dividend_per_share: string
  initial_shares: string
  years: string
  dividend_growth_rate: string
  price_appreciation_rate: string
  reinvest: boolean
}

interface CalculatorResult {
  year: number
  shares: number
  dividend_income: number
  cumulative_dividend: number
  portfolio_value: number
  yield_on_cost: number
}

// 王文投资思想核心指标
const WANGWEN_CRITERIA = {
  min_dividend_yield: 4,
  min_consecutive_years: 5,
  max_pe: 15,
  max_pb: 2,
  max_debt_ratio: 60,
  min_dividend_ratio: 30,
  max_dividend_ratio: 70,
}

// 散户乙投资思想核心指标
const SANHUYI_CRITERIA = {
  min_roe: 15,
  min_dividend_yield: 3,
  min_gross_margin: 30,
  min_net_margin: 15,
  max_debt_ratio: 60,
}

export default function DividendScreener() {
  const [activeTab, setActiveTab] = useState<'screener' | 'calculator' | 'philosophy'>('philosophy')
  const [stocks, setStocks] = useState<DividendStock[]>([])
  const [loading, setLoading] = useState(false)
  const [updateTime, setUpdateTime] = useState('')
  const [selectedMaster, setSelectedMaster] = useState<'wangwen' | 'sanhuyi' | 'combined'>('combined')
  const [expandedStock, setExpandedStock] = useState<string | null>(null)

  // 计算器状态
  const [inputs, setInputs] = useState<CalculatorInputs>({
    stock_price: '10',
    dividend_per_share: '0.5',
    initial_shares: '10000',
    years: '10',
    dividend_growth_rate: '5',
    price_appreciation_rate: '0',
    reinvest: true,
  })
  const [results, setResults] = useState<CalculatorResult[]>([])

  // 加载筛选数据
  const loadStocks = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/dividend/screener`, {
        params: { master: selectedMaster }
      })
      setStocks(res.data.stocks || [])
      setUpdateTime(res.data.update_time || '')
    } catch (e) {
      console.error('获取筛选数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [selectedMaster])

  useEffect(() => { loadStocks() }, [loadStocks])

  // 攒股收息计算器（含股价增长+股息再投资）
  const calculateDividend = () => {
    const initialPrice = parseFloat(inputs.stock_price)
    const dps = parseFloat(inputs.dividend_per_share)
    const shares = parseInt(inputs.initial_shares)
    const years = parseInt(inputs.years)
    const growthRate = parseFloat(inputs.dividend_growth_rate) / 100
    const priceGrowth = parseFloat(inputs.price_appreciation_rate) / 100

    if (isNaN(initialPrice) || isNaN(dps) || isNaN(shares) || isNaN(years) || isNaN(growthRate) || isNaN(priceGrowth)) return
    if (initialPrice <= 0 || dps <= 0 || shares <= 0 || years <= 0) return

    const results: CalculatorResult[] = []
    let currentShares = shares
    let currentDps = dps
    let currentPrice = initialPrice
    let cumulativeDividend = 0

    for (let year = 1; year <= years; year++) {
      const dividendIncome = currentShares * currentDps
      cumulativeDividend += dividendIncome

      if (inputs.reinvest) {
        const newShares = Math.floor(dividendIncome / currentPrice)
        currentShares += newShares
      }

      const portfolioValue = currentShares * currentPrice
      const yieldOnCost = (currentDps / initialPrice) * 100

      results.push({
        year,
        shares: currentShares,
        dividend_income: dividendIncome,
        cumulative_dividend: cumulativeDividend,
        portfolio_value: portfolioValue,
        yield_on_cost: yieldOnCost,
      })

      currentDps *= (1 + growthRate)
      currentPrice *= (1 + priceGrowth)
    }

    setResults(results)
  }

  // 计算分红回本年数
  const calcPayback = (stock: DividendStock) => {
    const yield_pct = stock.dividend_yield ?? 0
    if (yield_pct <= 0) return null
    const price = stock.price
    const dps = price * yield_pct / 100  // 每股股息

    // 静态回本年数（不增长不复投）
    const static_years = 100 / yield_pct

    // 不同增长率+是否复投的场景
    const scenarios = [0, 3, 5, 10].map(growth => {
      // 不复投
      let cumDiv = 0
      let years_no_reinvest = 0
      let curDps = dps
      for (let y = 1; y <= 50; y++) {
        cumDiv += curDps
        if (cumDiv >= price && years_no_reinvest === 0) years_no_reinvest = y
        curDps *= (1 + growth / 100)
      }

      // 复投
      let shares = 1
      let cumDivR = 0
      let years_reinvest = 0
      curDps = dps
      for (let y = 1; y <= 50; y++) {
        const income = shares * curDps
        cumDivR += income
        const newShares = income / price
        shares += newShares
        if (cumDivR >= price && years_reinvest === 0) years_reinvest = y
        curDps *= (1 + growth / 100)
      }

      return { growth, years_no_reinvest, years_reinvest }
    })

    return { price, dps, yield_pct, static_years, scenarios }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#52c41a'
    if (score >= 60) return '#1890ff'
    if (score >= 40) return '#faad14'
    return '#ff4d4f'
  }

  const getMatchLevelText = (level: string) => {
    switch (level) {
      case 'excellent': return '优秀'
      case 'good': return '良好'
      case 'fair': return '一般'
      default: return '-'
    }
  }

  return (
    <div className="cb-page">
      <PageSection title="王文 & 散户乙 投资筛选器" compact>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>基于两位大师投资思想的股票筛选 + 攒股收息计算器</span>
      </PageSection>

      <TabBar
        tabs={[
          { key: 'philosophy', label: '投资思想' },
          { key: 'screener', label: '股票筛选' },
          { key: 'calculator', label: '攒股收息计算器' },
        ]}
        activeKey={activeTab}
        onChange={k => setActiveTab(k as any)}
        style={{ marginBottom: 16 }}
      />

      {/* 投资思想页面 */}
      {activeTab === 'philosophy' && (
        <div style={{ padding: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
            {/* 王文投资思想 */}
            <div className="arb-notes" style={{ margin: 0 }}>
              <h3 style={{ color: '#58a6ff', marginBottom: '16px' }}>王文 - 攒股收息派</h3>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心理念</h4>
                  <ul>
                    <li><strong>攒股收息</strong>：通过股息再投资积累股份，享受复利效应</li>
                    <li><strong>长期持有</strong>：不追求短期股价上涨，以年为单位持有</li>
                    <li><strong>安全边际</strong>：买入价格要足够便宜，留足安全边际</li>
                    <li><strong>穿越周期</strong>：耐心持有，穿越牛熊周期</li>
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    <li><strong>股息率</strong>：≥ 4%（理想 &gt; 5%）</li>
                    <li><strong>连续分红</strong>：≥ 5年稳定分红记录</li>
                    <li><strong>分红比例</strong>：30% - 70%（可持续性）</li>
                    <li><strong>市盈率(PE)</strong>：&lt; 15（低估值）</li>
                    <li><strong>市净率(PB)</strong>：&lt; 2（低估值）</li>
                    <li><strong>资产负债率</strong>：&lt; 60%（财务稳健）</li>
                    <li><strong>行业偏好</strong>：银行、保险、能源、公用事业等垄断型行业</li>
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>投资金句</h4>
                  <ul>
                    <li>"买股票就是买公司的一部分"</li>
                    <li>"股息是投资的锚"</li>
                    <li>"低估买入，长期持有，股息再投"</li>
                    <li>"不看K线，只看分红"</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* 散户乙投资思想 */}
            <div className="arb-notes" style={{ margin: 0 }}>
              <h3 style={{ color: '#3fb950', marginBottom: '16px' }}>散户乙 - 价值成长派</h3>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>核心理念</h4>
                  <ul>
                    <li><strong>买股票就是买公司</strong>：以股东视角看待投资</li>
                    <li><strong>长期持有</strong>：不做短线交易，以年为单位持有优质公司</li>
                    <li><strong>知行合一</strong>：强调投资纪律和心态管理</li>
                    <li><strong>复利思维</strong>：通过持续分红再投资，实现复利增长</li>
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>选股标准</h4>
                  <ul>
                    <li><strong>ROE（净资产收益率）</strong>：连续3年 ≥ 15%</li>
                    <li><strong>股息率</strong>：≥ 3%</li>
                    <li><strong>毛利率</strong>：≥ 30%（护城河体现）</li>
                    <li><strong>净利率</strong>：≥ 15%</li>
                    <li><strong>资产负债率</strong>：&lt; 60%</li>
                    <li><strong>商业模式</strong>：简单易懂，行业龙头或垄断地位</li>
                    <li><strong>经典持仓</strong>：泸州老窖、中国神华等高分红高ROE公司</li>
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>投资金句</h4>
                  <ul>
                    <li>"合理价格买入优秀公司，然后长期持有"</li>
                    <li>"关注公司本身，而非股价波动"</li>
                    <li>"不看K线，专注于企业基本面"</li>
                    <li>"高ROE是企业盈利能力的核心指标"</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* 综合筛选逻辑 */}
          <div className="arb-notes" style={{ marginTop: '20px' }}>
            <h3 style={{ color: '#d29922' }}>综合筛选逻辑（王文 + 散户乙）</h3>
            <div className="arb-notes-grid">
              <div className="arb-note-item">
                <span className="arb-note-label">股息率</span>
                <span className="arb-note-value">≥ 4%</span>
                <span className="arb-note-desc">两位大师都重视高股息，提供安全边际和现金流</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">ROE</span>
                <span className="arb-note-value">≥ 15%</span>
                <span className="arb-note-desc">散户乙核心指标，反映企业盈利能力</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">PE</span>
                <span className="arb-note-value">≤ 15</span>
                <span className="arb-note-desc">王文强调低估值买入，留足安全边际</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">连续分红</span>
                <span className="arb-note-value">≥ 5年</span>
                <span className="arb-note-desc">王文要求稳定的分红历史</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">毛利率</span>
                <span className="arb-note-value">≥ 30%</span>
                <span className="arb-note-desc">散户乙护城河指标，体现竞争优势</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">资产负债率</span>
                <span className="arb-note-value">≤ 60%</span>
                <span className="arb-note-desc">两位大师都要求财务稳健</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 股票筛选页面 */}
      {activeTab === 'screener' && (
        <div style={{ padding: '16px 20px' }}>
          {/* 筛选条件切换 */}
          <div style={{
            display: 'flex', gap: '8px', marginBottom: '16px',
          }}>
            {(['combined', 'wangwen', 'sanhuyi'] as const).map(master => (
              <button
                key={master}
                onClick={() => setSelectedMaster(master)}
                style={{
                  padding: '8px 16px',
                  border: '1px solid var(--border-primary)',
                  borderRadius: '6px',
                  background: selectedMaster === master ? 'var(--accent-blue)' : 'var(--bg-secondary)',
                  color: selectedMaster === master ? '#fff' : 'var(--text-primary)',
                  cursor: 'pointer',
                  fontSize: '13px',
                }}
              >
                {master === 'combined' ? '综合筛选' : master === 'wangwen' ? '王文标准' : '散户乙标准'}
              </button>
            ))}
            <button className="btn-add" onClick={loadStocks} style={{ marginLeft: 'auto' }}>
              刷新数据
            </button>
          </div>

          {/* 数据信息 */}
          <div className="data-freshness" style={{ marginBottom: '16px' }}>
            <span className="freshness-tag">筛选标准: {selectedMaster === 'combined' ? '综合' : selectedMaster === 'wangwen' ? '王文' : '散户乙'}</span>
            <span className="freshness-tag">更新时间: {updateTime}</span>
            <span className="freshness-tag">符合条件: {stocks.length} 只</span>
          </div>

          {/* 筛选结果表格 */}
          {loading ? (
            <div className="loading">
              <div className="spinner"></div>
              加载中...
            </div>
          ) : (
            <div className="table-container">
              <table className="arb-table">
                <thead>
                  <tr>
                    <th>排名</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>报告期</th>
                    <th>现价</th>
                    <th>股息率(%)</th>
                    <th>PE</th>
                    <th>PB</th>
                    <th>ROE(%)</th>
                    <th>毛利率(%)</th>
                    <th>资产负债率(%)</th>
                    <th>连续分红(年)</th>
                    <th>股息CAGR(3Y)</th>
                    <th>综合评分</th>
                    <th>匹配度</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((stock, i) => {
                    const isExpanded = expandedStock === stock.code
                    const payback = calcPayback(stock)
                    return (
                      <>
                        <tr key={stock.code} onClick={() => setExpandedStock(isExpanded ? null : stock.code)} style={{ cursor: 'pointer' }}>
                          <td>{i + 1}</td>
                          <td>{stock.code}</td>
                          <td style={{ fontWeight: 600 }}>{stock.name}</td>
                          <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{stock.report_period || '--'}</td>
                          <td>{stock.price.toFixed(2)}</td>
                          <td style={{
                            color: (stock.dividend_yield ?? 0) >= 5 ? '#52c41a' : (stock.dividend_yield ?? 0) >= 4 ? '#1890ff' : '#faad14',
                            fontWeight: 600,
                          }}>
                            {stock.dividend_yield?.toFixed(2) ?? '--'}
                          </td>
                          <td style={{
                            color: (stock.pe ?? 999) <= 10 ? '#52c41a' : (stock.pe ?? 999) <= 15 ? '#1890ff' : '#ff4d4f',
                          }}>
                            {stock.pe?.toFixed(2) ?? '--'}
                          </td>
                          <td>{stock.pb?.toFixed(2) ?? '--'}</td>
                          <td style={{
                            color: (stock.roe ?? 0) >= 20 ? '#52c41a' : (stock.roe ?? 0) >= 15 ? '#1890ff' : '#faad14',
                            fontWeight: 600,
                          }}>
                            {stock.roe?.toFixed(2) ?? '--'}
                          </td>
                          <td>{stock.gross_margin?.toFixed(2) ?? '--'}</td>
                          <td style={{
                            color: (stock.debt_ratio ?? 100) <= 40 ? '#52c41a' : (stock.debt_ratio ?? 100) <= 60 ? '#faad14' : '#ff4d4f',
                          }}>
                            {stock.debt_ratio?.toFixed(2) ?? '--'}
                          </td>
                          <td style={{ fontWeight: 600 }}>{stock.consecutive_years}</td>
                          <td style={{
                            color: (stock.dividend_cagr_3y ?? -999) >= 10 ? '#52c41a' : (stock.dividend_cagr_3y ?? -999) >= 0 ? '#1890ff' : '#ff4d4f',
                            fontWeight: 600,
                          }}>
                            {stock.dividend_cagr_3y != null ? `${stock.dividend_cagr_3y > 0 ? '+' : ''}${stock.dividend_cagr_3y.toFixed(1)}%` : '--'}
                          </td>
                          <td>
                            <span style={{
                              color: getScoreColor(stock.score),
                              fontWeight: 700,
                              fontSize: '15px',
                            }}>
                              {stock.score}
                            </span>
                          </td>
                          <td>
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '12px',
                              fontWeight: 600,
                              background: stock.match_level === 'excellent' ? 'rgba(82,196,26,0.15)' :
                                stock.match_level === 'good' ? 'rgba(24,144,255,0.15)' : 'rgba(250,173,20,0.15)',
                              color: stock.match_level === 'excellent' ? '#52c41a' :
                                stock.match_level === 'good' ? '#1890ff' : '#faad14',
                            }}>
                              {getMatchLevelText(stock.match_level)}
                            </span>
                          </td>
                        </tr>
                        {isExpanded && payback && (
                          <tr key={`${stock.code}-payback`}>
                            <td colSpan={15} style={{ padding: '16px 20px', background: 'var(--bg-secondary)' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
                                {/* 核心指标 */}
                                <div style={{ background: 'var(--bg-tertiary)', padding: 16, borderRadius: 8, borderLeft: '3px solid #58a6ff' }}>
                                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>静态回本年数（不增长不复投）</div>
                                  <div style={{ fontSize: 28, fontWeight: 700, color: payback.static_years <= 15 ? '#52c41a' : payback.static_years <= 25 ? '#58a6ff' : '#d29922' }}>
                                    {payback.static_years.toFixed(1)} 年
                                  </div>
                                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                                    每股股息 ¥{payback.dps.toFixed(3)} / 股价 ¥{payback.price.toFixed(2)}
                                  </div>
                                </div>

                                {/* 股息质量分析 */}
                                <div style={{ background: 'var(--bg-tertiary)', padding: 16, borderRadius: 8, borderLeft: '3px solid #3fb950' }}>
                                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>股息质量分析</div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>3年CAGR</span>
                                      <span style={{ fontWeight: 700, fontSize: 15, color: (stock.dividend_cagr_3y ?? -999) >= 5 ? '#52c41a' : (stock.dividend_cagr_3y ?? -999) >= 0 ? '#1890ff' : '#ff4d4f' }}>
                                        {stock.dividend_cagr_3y != null ? `${stock.dividend_cagr_3y > 0 ? '+' : ''}${stock.dividend_cagr_3y.toFixed(1)}%` : '--'}
                                      </span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>5年CAGR</span>
                                      <span style={{ fontWeight: 700, fontSize: 15, color: (stock.dividend_cagr_5y ?? -999) >= 5 ? '#52c41a' : (stock.dividend_cagr_5y ?? -999) >= 0 ? '#1890ff' : '#ff4d4f' }}>
                                        {stock.dividend_cagr_5y != null ? `${stock.dividend_cagr_5y > 0 ? '+' : ''}${stock.dividend_cagr_5y.toFixed(1)}%` : '--'}
                                      </span>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>派息率可持续性</span>
                                      <span style={{
                                        fontWeight: 600, fontSize: 13, padding: '2px 8px', borderRadius: 4,
                                        background: stock.payout_sustainability === 'sustainable' ? 'rgba(82,196,26,0.15)' :
                                          stock.payout_sustainability === 'high' ? 'rgba(250,173,20,0.15)' :
                                          stock.payout_sustainability === 'unsustainable' ? 'rgba(255,77,79,0.15)' : 'var(--bg-secondary)',
                                        color: stock.payout_sustainability === 'sustainable' ? '#52c41a' :
                                          stock.payout_sustainability === 'high' ? '#faad14' :
                                          stock.payout_sustainability === 'unsustainable' ? '#ff4d4f' : 'var(--text-muted)',
                                      }}>
                                        {stock.payout_sustainability === 'sustainable' ? '可持续' :
                                          stock.payout_sustainability === 'high' ? '偏高' :
                                          stock.payout_sustainability === 'unsustainable' ? '不可持续' : '未知'}
                                      </span>
                                    </div>
                                    {stock.has_special_dividend && (
                                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>特别股息</span>
                                        <span style={{ fontWeight: 600, fontSize: 13, color: '#faad14' }}>疑似存在</span>
                                      </div>
                                    )}
                                  </div>
                                </div>

                                {/* 回本年数表 */}
                                <div style={{ gridColumn: 'span 2', background: 'var(--bg-tertiary)', padding: 16, borderRadius: 8 }}>
                                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
                                    分红回本年数（不同增长率 + 是否复投）
                                  </div>
                                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                                    <thead>
                                      <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                                        <th style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--text-muted)' }}>股息增长率</th>
                                        {payback.scenarios.map(s => (
                                          <th key={s.growth} style={{ textAlign: 'center', padding: '6px 8px', color: 'var(--text-muted)' }}>
                                            {s.growth === 0 ? '不增长' : `+${s.growth}%/年`}
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      <tr style={{ borderBottom: '1px solid var(--border-primary)' }}>
                                        <td style={{ padding: '6px 8px', fontWeight: 600 }}>不复投</td>
                                        {payback.scenarios.map(s => (
                                          <td key={s.growth} style={{ textAlign: 'center', padding: '6px 8px', fontWeight: 700, fontSize: 16, color: s.years_no_reinvest <= 15 ? '#52c41a' : s.years_no_reinvest <= 25 ? '#58a6ff' : '#d29922' }}>
                                            {s.years_no_reinvest}年
                                          </td>
                                        ))}
                                      </tr>
                                      <tr>
                                        <td style={{ padding: '6px 8px', fontWeight: 600 }}>复投</td>
                                        {payback.scenarios.map(s => (
                                          <td key={s.growth} style={{ textAlign: 'center', padding: '6px 8px', fontWeight: 700, fontSize: 16, color: s.years_reinvest <= 15 ? '#52c41a' : s.years_reinvest <= 25 ? '#58a6ff' : '#d29922' }}>
                                            {s.years_reinvest}年
                                          </td>
                                        ))}
                                      </tr>
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    )
                  })}
                  {stocks.length === 0 && (
                    <tr>
                      <td colSpan={15} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        暂无符合条件的股票
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* 筛选说明 */}
          <div className="arb-notes" style={{ marginTop: '16px' }}>
            <h3>评分说明</h3>
            <div className="arb-notes-content">
              <div className="arb-risk-section">
                <h4>综合评分 (0-120分，归一化至100)</h4>
                <ul>
                  <li><strong>股息率</strong> (30分)：≥5%满分，4-5%良好，3-4%及格</li>
                  <li><strong>ROE</strong> (25分)：≥20%满分，15-20%良好，10-15%及格</li>
                  <li><strong>估值</strong> (20分)：PE≤10满分，10-15良好，15-20及格</li>
                  <li><strong>连续分红</strong> (15分)：≥10年满分，5-10年良好，3-5年及格</li>
                  <li><strong>财务健康</strong> (10分)：资产负债率≤40%满分，40-60%良好</li>
                  <li><strong>股息增长</strong> (10分)：CAGR≥10%满分，5-10%良好，0-5%及格</li>
                  <li><strong>派息可持续性</strong> (5分)：30-80%可持续满分，&gt;80%偏高</li>
                </ul>
              </div>
              <div className="arb-risk-section">
                <h4>匹配度等级</h4>
                <ul>
                  <li><strong style={{ color: '#52c41a' }}>优秀 (≥80分)</strong>：高度符合两位大师选股标准</li>
                  <li><strong style={{ color: '#1890ff' }}>良好 (60-79分)</strong>：基本符合，部分指标略低</li>
                  <li><strong style={{ color: '#faad14' }}>一般 (40-59分)</strong>：部分符合，需要进一步分析</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 攒股收息计算器 */}
      {activeTab === 'calculator' && (
        <div style={{ padding: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '20px' }}>
            {/* 输入表单 */}
            <div className="arb-notes" style={{ margin: 0 }}>
              <h3 style={{ marginBottom: '16px' }}>攒股收息计算器</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    股票价格 (元)
                  </label>
                  <input
                    type="number"
                    value={inputs.stock_price}
                    onChange={e => setInputs(prev => ({ ...prev, stock_price: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
                      borderRadius: '6px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    每股股息 (元)
                  </label>
                  <input
                    type="number"
                    value={inputs.dividend_per_share}
                    onChange={e => setInputs(prev => ({ ...prev, dividend_per_share: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
                      borderRadius: '6px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    初始持股数 (股)
                  </label>
                  <input
                    type="number"
                    value={inputs.initial_shares}
                    onChange={e => setInputs(prev => ({ ...prev, initial_shares: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
                      borderRadius: '6px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    投资年限 (年)
                  </label>
                  <input
                    type="number"
                    value={inputs.years}
                    onChange={e => setInputs(prev => ({ ...prev, years: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
                      borderRadius: '6px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    股息增长率 (% / 年)
                  </label>
                  <input
                    type="number"
                    value={inputs.dividend_growth_rate}
                    onChange={e => setInputs(prev => ({ ...prev, dividend_growth_rate: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
                      borderRadius: '6px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    股价年涨幅 (% / 年)
                  </label>
                  <input
                    type="number"
                    value={inputs.price_appreciation_rate}
                    onChange={e => setInputs(prev => ({ ...prev, price_appreciation_rate: e.target.value }))}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border-primary)',
                      borderRadius: '6px', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                    }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="checkbox"
                    id="reinvest"
                    checked={inputs.reinvest}
                    onChange={e => setInputs(prev => ({ ...prev, reinvest: e.target.checked }))}
                  />
                  <label htmlFor="reinvest" style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                    股息再投资（用股息买入更多股份）
                  </label>
                </div>
                <button
                  onClick={calculateDividend}
                  style={{
                    padding: '10px 20px', background: 'var(--accent-blue)', color: '#fff',
                    border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px',
                    fontWeight: 600,
                  }}
                >
                  计算
                </button>
              </div>

              {/* 计算公式说明 */}
              <div style={{ marginTop: '20px', padding: '12px', background: 'rgba(88,166,255,0.08)', borderRadius: '6px' }}>
                <div style={{ fontWeight: 600, color: 'var(--accent-blue)', marginBottom: '8px' }}>计算逻辑</div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  <div>1. 每年股息收入 = 持股数 × 每股股息</div>
                  <div>2. 股息再投资：股息收入 / 当年股价 = 新增股数</div>
                  <div>3. 每年股息按增长率递增</div>
                  <div>4. 股价按年涨幅递增（再投资时影响买入股数）</div>
                  <div>5. 成本收益率 = 当前每股股息 / 初始买入价格</div>
                </div>
              </div>
            </div>

            {/* 计算结果 */}
            <div>
              {results.length > 0 ? (
                <>
                  {/* 汇总信息 */}
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px',
                    marginBottom: '16px',
                  }}>
                    <div className="metric-card">
                      <div className="metric-label">最终持股数</div>
                      <div className="metric-value" style={{ color: '#58a6ff' }}>
                        {results[results.length - 1].shares.toLocaleString()} 股
                      </div>
                      <div className="metric-desc">
                        初始 {parseInt(inputs.initial_shares).toLocaleString()} 股
                      </div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-label">累计股息收入</div>
                      <div className="metric-value" style={{ color: '#52c41a' }}>
                        ¥{results[results.length - 1].cumulative_dividend.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </div>
                      <div className="metric-desc">{inputs.years}年累计</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-label">最终持仓市值</div>
                      <div className="metric-value" style={{ color: '#d29922' }}>
                        ¥{results[results.length - 1].portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </div>
                      <div className="metric-desc">
                        初始 ¥{(parseInt(inputs.initial_shares) * parseFloat(inputs.stock_price)).toLocaleString()}
                      </div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-label">成本收益率</div>
                      <div className="metric-value" style={{ color: '#3fb950' }}>
                        {results[results.length - 1].yield_on_cost.toFixed(2)}%
                      </div>
                      <div className="metric-desc">基于买入成本</div>
                    </div>
                  </div>

                  {/* 详细表格 */}
                  <div className="table-container">
                    <table className="arb-table">
                      <thead>
                        <tr>
                          <th>年份</th>
                          <th>持股数</th>
                          <th>当年股息</th>
                          <th>累计股息</th>
                          <th>持仓市值</th>
                          <th>成本收益率</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map(r => (
                          <tr key={r.year}>
                            <td>第{r.year}年</td>
                            <td style={{ fontWeight: 600 }}>{r.shares.toLocaleString()}</td>
                            <td style={{ color: '#52c41a' }}>
                              ¥{r.dividend_income.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                            <td style={{ color: '#58a6ff' }}>
                              ¥{r.cumulative_dividend.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                            <td>
                              ¥{r.portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                            <td style={{
                              color: r.yield_on_cost >= 10 ? '#52c41a' : r.yield_on_cost >= 5 ? '#1890ff' : '#faad14',
                              fontWeight: 600,
                            }}>
                              {r.yield_on_cost.toFixed(2)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  height: '400px', color: 'var(--text-muted)',
                }}>
                  <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
                  <div style={{ fontSize: '16px' }}>输入参数后点击"计算"</div>
                  <div style={{ fontSize: '13px', marginTop: '8px' }}>查看攒股收息的复利增长效果</div>
                </div>
              )}
            </div>
          </div>

          {/* 策略说明 */}
          <div className="arb-notes" style={{ marginTop: '20px' }}>
            <h3>攒股收息策略说明</h3>
            <div className="arb-notes-grid">
              <div className="arb-note-item">
                <span className="arb-note-label">核心思想</span>
                <span className="arb-note-value">股息再投资</span>
                <span className="arb-note-desc">将收到的股息用于买入更多股份，实现复利增长</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">适合标的</span>
                <span className="arb-note-value">高股息蓝筹股</span>
                <span className="arb-note-desc">银行、能源、公用事业等稳定分红的行业龙头</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">持有周期</span>
                <span className="arb-note-value">5年以上</span>
                <span className="arb-note-desc">时间越长，复利效应越明显</span>
              </div>
              <div className="arb-note-item">
                <span className="arb-note-label">收益来源</span>
                <span className="arb-note-value">股息 + 股价上涨</span>
                <span className="arb-note-desc">本计算器仅计算股息收益，未包含股价上涨收益</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
