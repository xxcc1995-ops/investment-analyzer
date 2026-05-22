import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

interface MacroOverview {
  gdp?: { latest: any; series: any[] }
  cpi?: { latest: any; series: any[] }
  pmi?: { latest: any; series: any[] }
  money_supply?: { latest: any; series: any[] }
  social_financing?: { latest: any; series: any[] }
  lpr?: { latest: any; series: any[] }
}

export default function MacroData() {
  const [overview, setOverview] = useState<MacroOverview>({})
  const [chinaData, setChinaData] = useState<any>({})
  const [usData, setUsData] = useState<any>({})
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'overview' | 'china' | 'us'>('overview')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, cn, us] = await Promise.all([
        axios.get(`${API_BASE}/macro/overview`),
        axios.get(`${API_BASE}/macro/china`),
        axios.get(`${API_BASE}/macro/us`),
      ])
      setOverview(ov.data)
      setChinaData(cn.data)
      setUsData(us.data)
    } catch (e) {
      console.error('获取宏观数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const fmt = (v: number | null | undefined, digits = 2) => {
    if (v === null || v === undefined) return '-'
    return v.toFixed(digits)
  }

  const fmtBig = (v: number | null | undefined) => {
    if (v === null || v === undefined) return '-'
    if (Math.abs(v) >= 10000) return (v / 10000).toFixed(2) + '万亿'
    return v.toFixed(0) + '亿'
  }

  const renderOverviewCards = () => {
    const cards = [
      { label: 'GDP', value: fmtBig(overview.gdp?.latest?.gdp), sub: overview.gdp?.latest?.gdp_growth ? `同比 ${overview.gdp.latest.gdp_growth}%` : '', date: overview.gdp?.latest?.date },
      { label: 'CPI(全国)', value: fmt(overview.cpi?.latest?.cpi), sub: overview.cpi?.latest?.cpi_yoy ? `同比 ${overview.cpi.latest.cpi_yoy > 0 ? '+' : ''}${fmt(overview.cpi.latest.cpi_yoy)}%` : '', date: overview.cpi?.latest?.date },
      { label: 'PMI制造业', value: fmt(overview.pmi?.latest?.manufacturing, 1), sub: overview.pmi?.latest?.manufacturing >= 50 ? '扩张' : '收缩', date: overview.pmi?.latest?.date },
      { label: 'M2', value: fmtBig(overview.money_supply?.latest?.m2), sub: overview.money_supply?.latest?.m2_growth ? `同比 ${fmt(overview.money_supply.latest.m2_growth)}%` : '', date: overview.money_supply?.latest?.date },
      { label: 'LPR(1Y)', value: overview.lpr?.latest?.lpr_1y ? fmt(overview.lpr.latest.lpr_1y) + '%' : '-', sub: '', date: overview.lpr?.latest?.date },
      { label: 'LPR(5Y)', value: overview.lpr?.latest?.lpr_5y ? fmt(overview.lpr.latest.lpr_5y) + '%' : '-', sub: '', date: overview.lpr?.latest?.date },
    ]

    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', marginBottom: '20px' }}>
        {cards.map(c => (
          <div key={c.label} className="arb-note-item" style={{ padding: '16px' }}>
            <span className="arb-note-label">{c.label}</span>
            <span style={{ fontSize: '22px', fontWeight: 700, color: 'var(--accent)' }}>{c.value}</span>
            {c.sub && <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{c.sub}</span>}
            <span className="arb-note-desc">{c.date}</span>
          </div>
        ))}
      </div>
    )
  }

  const Table = ({ data, columns }: { data: any[]; columns: { key: string; label: string }[] }) => {
    if (!data || data.length === 0) return <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>暂无数据</div>
    return (
      <div className="table-container">
        <table className="arb-table">
          <thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead>
          <tbody>
            {data.slice(0, 24).map((row, i) => (
              <tr key={i}>{columns.map(c => <td key={c.key}>{row[c.key] ?? '-'}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div>
      <div className="stock-header">
        <div className="stock-title-row">
          <div>
            <h2>宏观经济数据</h2>
            <span className="stock-code">中国 + 美国 核心宏观指标</span>
          </div>
          <button className="btn-add" onClick={loadData}>刷新数据</button>
        </div>
      </div>

      <div className="list-tabs" style={{ marginBottom: '16px' }}>
        {(['overview', 'china', 'us'] as const).map(t => (
          <button key={t} className={`list-tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
            {t === 'overview' ? '概览' : t === 'china' ? '中国详情' : '美国'}
          </button>
        ))}
      </div>

      {loading ? <div className="loading"><div className="spinner"></div>加载中...</div> : (
        <>
          {activeTab === 'overview' && renderOverviewCards()}

          {activeTab === 'china' && (
            <>
              <div className="arb-section-title">GDP（国内生产总值）</div>
              <Table data={chinaData.gdp || []} columns={[
                { key: 'date', label: '季度' },
                { key: 'gdp', label: 'GDP(亿元)' },
                { key: 'gdp_growth', label: 'GDP同比(%)' },
                { key: 'primary', label: '第一产业(亿)' },
                { key: 'secondary', label: '第二产业(亿)' },
                { key: 'tertiary', label: '第三产业(亿)' },
              ]} />

              <div className="arb-section-title" style={{ marginTop: '20px' }}>CPI（居民消费价格指数）</div>
              <Table data={chinaData.cpi || []} columns={[
                { key: 'date', label: '月份' },
                { key: 'cpi', label: '全国当月' },
                { key: 'cpi_yoy', label: '同比(%)' },
                { key: 'city', label: '城市当月' },
                { key: 'rural', label: '农村当月' },
              ]} />

              <div className="arb-section-title" style={{ marginTop: '20px' }}>PMI（采购经理指数）</div>
              <Table data={chinaData.pmi || []} columns={[
                { key: 'date', label: '月份' },
                { key: 'manufacturing', label: '制造业PMI' },
                { key: 'mfg_yoy', label: '制造业同比(%)' },
                { key: 'non_manufacturing', label: '非制造业PMI' },
                { key: 'non_mfg_yoy', label: '非制造业同比(%)' },
              ]} />

              <div className="arb-section-title" style={{ marginTop: '20px' }}>货币供应量</div>
              <Table data={chinaData.money_supply || []} columns={[
                { key: 'date', label: '月份' },
                { key: 'm2', label: 'M2(亿元)' },
                { key: 'm2_growth', label: 'M2同比(%)' },
                { key: 'm1', label: 'M1(亿元)' },
                { key: 'm1_growth', label: 'M1同比(%)' },
                { key: 'm0', label: 'M0(亿元)' },
                { key: 'm0_growth', label: 'M0同比(%)' },
              ]} />

              <div className="arb-section-title" style={{ marginTop: '20px' }}>LPR（贷款市场报价利率）</div>
              <Table data={(chinaData.lpr || []).slice().reverse()} columns={[
                { key: 'date', label: '日期' },
                { key: 'lpr_1y', label: '1年期LPR(%)' },
                { key: 'lpr_5y', label: '5年期LPR(%)' },
              ]} />

              <div className="arb-section-title" style={{ marginTop: '20px' }}>社会融资规模</div>
              <Table data={(chinaData.social_financing || []).slice(-24)} columns={[
                { key: 'date', label: '月份' },
                { key: 'value', label: '增量(亿元)' },
              ]} />
            </>
          )}

          {activeTab === 'us' && (
            <>
              <div className="arb-section-title">美国CPI（月度）</div>
              <Table data={(usData.cpi || []).slice(-24)} columns={[
                { key: 'date', label: '日期' },
                { key: 'value', label: 'CPI' },
              ]} />

              <div className="arb-section-title" style={{ marginTop: '20px' }}>美国失业率</div>
              <Table data={(usData.unemployment || []).slice(-24)} columns={[
                { key: 'date', label: '日期' },
                { key: 'value', label: '失业率(%)' },
              ]} />
            </>
          )}
        </>
      )}

      <div className="arb-notes" style={{ marginTop: '16px' }}>
        <h3>数据说明</h3>
        <div className="arb-notes-content">
          <ul>
            <li><strong>数据来源</strong>：AKShare（聚合东方财富、新浪财经等）</li>
            <li><strong>更新频率</strong>：缓存5分钟，实际数据按统计局/央行发布周期更新</li>
            <li><strong>PMI</strong>：50为荣枯线，高于50表示扩张，低于50表示收缩</li>
            <li><strong>LPR</strong>：每月20日更新，2019年8月起实行</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
