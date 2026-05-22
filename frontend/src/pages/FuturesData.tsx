import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface Commodity {
  symbol: string
  name: string
  unit: string
  price?: number
  change_pct?: number
}

interface FuturesItem {
  symbol: string
  name: string
  price?: number
  change_pct?: number
  volume?: number
  open_interest?: number
}

interface IndustryItem {
  rank: number
  name: string
  change_pct?: number
  amount?: number
  turnover?: number
  up_count?: number
  down_count?: number
  leader?: string
  leader_change?: number
}

interface FundFlowItem {
  name: string
  change_pct?: number
  main_net_inflow?: number
  main_net_pct?: number
}

interface NorthFlowItem {
  date: string
  type: string
  net_buy?: number
  net_flow?: number
}

export default function FuturesData() {
  const [commodities, setCommodities] = useState<Commodity[]>([])
  const [futures, setFutures] = useState<FuturesItem[]>([])
  const [industries, setIndustries] = useState<IndustryItem[]>([])
  const [fundFlow, setFundFlow] = useState<FundFlowItem[]>([])
  const [northFlow, setNorthFlow] = useState<NorthFlowItem[]>([])
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'commodities' | 'industry' | 'flow'>('commodities')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [commRes, futuresRes, industryRes, flowRes, northRes] = await Promise.all([
        axios.get(`${API_BASE}/futures/commodities`),
        axios.get(`${API_BASE}/futures/list`),
        axios.get(`${API_BASE}/futures/industry`),
        axios.get(`${API_BASE}/futures/fund-flow`),
        axios.get(`${API_BASE}/futures/north-flow`),
      ])
      setCommodities(commRes.data.commodities || [])
      setFutures(futuresRes.data.futures || [])
      setIndustries(industryRes.data.industries || [])
      setFundFlow(flowRes.data.sectors || [])
      setNorthFlow(northRes.data.flows || [])
    } catch (e) {
      console.error('获取期货数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const fmtAmt = (v: number | undefined | null) => {
    if (v === null || v === undefined) return '-'
    if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
    if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
    return v.toFixed(2)
  }

  const ChgCell = ({ val, suffix = '%', asPct = false }: { val?: number | null; suffix?: string; asPct?: boolean }) => {
    if (val === null || val === undefined) return <td>-</td>
    const display = asPct ? val * 100 : val
    return <td className={display >= 0 ? 'up' : 'down'}>{display >= 0 ? '+' : ''}{display.toFixed(2)}{suffix}</td>
  }

  return (
    <div>
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>期货行业数据</h2>
            <span className="stock-code">商品期货 · 行业板块 · 资金流向</span>
          </div>
          <button className="btn-add" onClick={loadData}>刷新数据</button>
        </div>
      </div>

      <div className="list-tabs" style={{ marginBottom: '16px' }}>
        {(['commodities', 'industry', 'flow'] as const).map(t => (
          <button key={t} className={`list-tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
            {t === 'commodities' ? '商品快照' : t === 'industry' ? '行业排名' : '资金流向'}
          </button>
        ))}
      </div>

      {loading ? <div className="loading"><div className="spinner"></div>加载中...</div> : (
        <>
          {activeTab === 'commodities' && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px', marginBottom: '20px' }}>
                {commodities.map(c => (
                  <div key={c.symbol} className="arb-note-item" style={{ padding: '16px' }}>
                    <span className="arb-note-label">{c.name}</span>
                    <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--accent)' }}>
                      {c.price ? c.price.toLocaleString() : '-'}
                    </span>
                    <span className={c.change_pct && c.change_pct >= 0 ? 'up' : 'down'} style={{ fontSize: '14px' }}>
                      {c.change_pct != null ? `${c.change_pct * 100 >= 0 ? '+' : ''}${(c.change_pct * 100).toFixed(2)}%` : '-'}
                    </span>
                    <span className="arb-note-desc">{c.unit}</span>
                  </div>
                ))}
              </div>

              <div className="arb-section-title">期货实时行情</div>
              <div className="table-container">
                <table className="arb-table">
                  <thead><tr><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>成交量</th><th>持仓量</th></tr></thead>
                  <tbody>
                    {futures.slice(0, 50).map((f, i) => (
                      <tr key={i}>
                        <td style={{ fontFamily: 'monospace' }}>{f.symbol}</td>
                        <td>{f.name}</td>
                        <td>{f.price?.toLocaleString() || '-'}</td>
                        <ChgCell val={f.change_pct} asPct />
                        <td>{fmtAmt(f.volume)}</td>
                        <td>{fmtAmt(f.open_interest)}</td>
                      </tr>
                    ))}
                    {futures.length === 0 && <tr><td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>暂无数据</td></tr>}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {activeTab === 'industry' && (
            <div className="table-container">
              <div className="arb-section-title">行业板块排名（同花顺）</div>
              <table className="arb-table">
                <thead><tr><th>#</th><th>板块</th><th>涨跌幅</th><th>成交额(亿)</th><th>换手率</th><th>涨/跌家数</th><th>领涨股</th><th>领涨幅</th></tr></thead>
                <tbody>
                  {industries.slice(0, 50).map((item, i) => (
                    <tr key={i}>
                      <td>{item.rank || i + 1}</td>
                      <td style={{ fontWeight: 600 }}>{item.name}</td>
                      <ChgCell val={item.change_pct} />
                      <td>{item.amount ? (item.amount / 10000).toFixed(2) : '-'}</td>
                      <td>{item.turnover?.toFixed(2) || '-'}%</td>
                      <td><span className="up">{item.up_count || 0}</span> / <span className="down">{item.down_count || 0}</span></td>
                      <td>{item.leader || '-'}</td>
                      <ChgCell val={item.leader_change} />
                    </tr>
                  ))}
                  {industries.length === 0 && <tr><td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>暂无数据</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'flow' && (
            <>
              <div className="arb-section-title">行业资金流向（今日）</div>
              <div className="table-container" style={{ marginBottom: '20px' }}>
                <table className="arb-table">
                  <thead><tr><th>行业</th><th>涨跌幅</th><th>主力净流入</th><th>主力净占比</th></tr></thead>
                  <tbody>
                    {fundFlow.slice(0, 30).map((item, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{item.name}</td>
                        <ChgCell val={item.change_pct} />
                        <td className={item.main_net_inflow && item.main_net_inflow >= 0 ? 'up' : 'down'}>{fmtAmt(item.main_net_inflow)}</td>
                        <td className={item.main_net_pct && item.main_net_pct >= 0 ? 'up' : 'down'}>{item.main_net_pct?.toFixed(2) || '-'}%</td>
                      </tr>
                    ))}
                    {fundFlow.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>暂无数据</td></tr>}
                  </tbody>
                </table>
              </div>

              <div className="arb-section-title">北向资金（今日）</div>
              <div className="table-container">
                <table className="arb-table">
                  <thead><tr><th>日期</th><th>类型</th><th>成交净买额(亿)</th><th>资金净流入(亿)</th></tr></thead>
                  <tbody>
                    {northFlow.map((item, i) => (
                      <tr key={i}>
                        <td>{item.date}</td>
                        <td>{item.type}</td>
                        <td className={item.net_buy && item.net_buy >= 0 ? 'up' : 'down'}>{item.net_buy != null ? (item.net_buy / 100000000).toFixed(2) : '-'}</td>
                        <td className={item.net_flow && item.net_flow >= 0 ? 'up' : 'down'}>{item.net_flow != null ? (item.net_flow / 100000000).toFixed(2) : '-'}</td>
                      </tr>
                    ))}
                    {northFlow.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>暂无数据</td></tr>}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}

      <div className="arb-notes" style={{ marginTop: '16px' }}>
        <h3>数据说明</h3>
        <div className="arb-notes-content">
          <ul>
            <li><strong>商品快照</strong>：主要期货品种实时行情（沪金/银/铜/铝/锌/螺纹钢/铁矿石/原油）</li>
            <li><strong>行业排名</strong>：同花顺行业板块涨跌幅排名</li>
            <li><strong>资金流向</strong>：行业主力资金净流入/流出</li>
            <li><strong>北向资金</strong>：沪股通+深股通当日净买入</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
