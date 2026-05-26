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
  consumer_confidence?: { latest: any; series: any[] }
  ppi?: { latest: any; series: any[] }
  retail_sales?: { latest: any; series: any[] }
  housing_price?: { latest: any; series: any[] }
  unemployment?: { latest: any; series: any[] }
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
      // 消费拐点指标
      { label: '消费者信心', value: fmt(overview.consumer_confidence?.latest?.confidence, 1), sub: overview.consumer_confidence?.latest?.confidence >= 100 ? '乐观' : '悲观', date: overview.consumer_confidence?.latest?.date, highlight: true },
      { label: 'PPI', value: fmt(overview.ppi?.latest?.value, 1), sub: overview.ppi?.latest?.yoy != null ? `同比 ${overview.ppi.latest.yoy > 0 ? '+' : ''}${fmt(overview.ppi.latest.yoy)}%` : '', date: overview.ppi?.latest?.date, highlight: true },
      { label: '社零增速', value: overview.retail_sales?.latest?.yoy != null ? `${overview.retail_sales.latest.yoy > 0 ? '+' : ''}${fmt(overview.retail_sales.latest.yoy)}%` : '-', sub: `累计 ${fmt(overview.retail_sales?.latest?.cumulative_yoy)}%`, date: overview.retail_sales?.latest?.date, highlight: true },
      { label: '房价同比(一线)', value: overview.housing_price?.latest?.avg_yoy != null ? `${overview.housing_price.latest.avg_yoy > 0 ? '+' : ''}${fmt(overview.housing_price.latest.avg_yoy)}%` : '-', sub: '', date: overview.housing_price?.latest?.date?.slice(0, 10), highlight: true },
      { label: '失业率', value: overview.unemployment?.latest?.value ? `${fmt(overview.unemployment.latest.value, 1)}%` : '-', sub: overview.unemployment?.latest?.value <= 5 ? '良好' : '偏高', date: overview.unemployment?.latest?.date, highlight: true },
    ]

    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', marginBottom: '20px' }}>
        {cards.map(c => (
          <div key={c.label} className="arb-note-item" style={{
            padding: '16px',
            borderLeft: (c as any).highlight ? '3px solid #58a6ff' : undefined,
          }}>
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

              {/* 消费拐点指标 */}
              <div className="arb-section-title" style={{ marginTop: '20px', color: '#58a6ff' }}>消费拐点指标</div>

              <div style={{ marginBottom: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
                消费者信心指数（100为中性线，高于100乐观，低于100悲观）
              </div>
              <Table data={(chinaData.consumer_confidence || []).slice(0, 24)} columns={[
                { key: 'date', label: '月份' },
                { key: 'confidence', label: '总指数' },
                { key: 'satisfaction', label: '满意指数' },
                { key: 'expectation', label: '预期指数' },
              ]} />

              <div style={{ marginBottom: '8px', marginTop: '16px', fontSize: '13px', color: 'var(--text-muted)' }}>
                PPI工业品出厂价格指数（100为基准，高于100通胀，低于100通缩）
              </div>
              <Table data={(chinaData.ppi || []).slice(0, 24)} columns={[
                { key: 'date', label: '月份' },
                { key: 'value', label: '当月指数' },
                { key: 'yoy', label: '同比(%)' },
                { key: 'cumulative', label: '累计' },
              ]} />

              <div style={{ marginBottom: '8px', marginTop: '16px', fontSize: '13px', color: 'var(--text-muted)' }}>
                社会消费品零售总额（亿元）
              </div>
              <Table data={(chinaData.retail_sales || []).slice(0, 24)} columns={[
                { key: 'date', label: '月份' },
                { key: 'value', label: '当月(亿元)' },
                { key: 'yoy', label: '同比(%)' },
                { key: 'cumulative', label: '累计(亿元)' },
                { key: 'cumulative_yoy', label: '累计同比(%)' },
              ]} />

              <div style={{ marginBottom: '8px', marginTop: '16px', fontSize: '13px', color: 'var(--text-muted)' }}>
                一线城市新建住宅价格同比变动（北京/上海均值，%）
              </div>
              <Table data={(chinaData.housing_price || []).slice(0, 24)} columns={[
                { key: 'date', label: '月份' },
                { key: 'avg_yoy', label: '同比变动(%)' },
                { key: 'cities', label: '城市数' },
              ]} />

              <div style={{ marginBottom: '8px', marginTop: '16px', fontSize: '13px', color: 'var(--text-muted)' }}>
                全国城镇调查失业率（%）
              </div>
              <Table data={(chinaData.unemployment || []).slice(0, 24)} columns={[
                { key: 'date', label: '月份' },
                { key: 'value', label: '失业率(%)' },
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
          <div className="arb-risk-section">
            <h4>基础指标</h4>
            <ul>
              <li><strong>数据来源</strong>：AKShare（聚合东方财富、新浪财经等）</li>
              <li><strong>更新频率</strong>：缓存5分钟，实际数据按统计局/央行发布周期更新</li>
              <li><strong>PMI</strong>：50为荣枯线，高于50表示扩张，低于50表示收缩</li>
              <li><strong>LPR</strong>：每月20日更新，2019年8月起实行</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>消费拐点指标 - 拐点信号值</h4>
            <ul>
              <li><strong>消费者信心指数</strong>：100为中性线，当前低于100表示悲观。拐点信号：回升至100以上</li>
              <li><strong>PPI</strong>：100为基准，低于100表示通缩。拐点信号：持续高于100（转正）</li>
              <li><strong>社零增速</strong>：反映居民消费支出。拐点信号：同比增速持续回升至3%以上</li>
              <li><strong>房价同比</strong>：一线城市房价变动。拐点信号：同比跌幅收窄至0%附近</li>
              <li><strong>失业率</strong>：城镇调查失业率。拐点信号：降至5%以下</li>
            </ul>
          </div>
          <div className="arb-risk-section">
            <h4>消费者信心指数 - 计算方法</h4>
            <p>国家统计局编制，基于全国约4万户城镇居民抽样问卷调查（月度）。</p>
            <p>问卷围绕两个维度：</p>
            <ul>
              <li><strong>满意指数</strong>：对当前家庭收入、经济形势的评价</li>
              <li><strong>预期指数</strong>：对未来6个月收入变化、经济形势、购买时机的预期</li>
            </ul>
            <p>每个问题5个选项，赋分如下：</p>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '6px', margin: '8px 0', fontFamily: 'monospace', fontSize: '13px' }}>
              <div>非常满意=100, 满意=75, 一般=50, 不满意=25, 非常不满意=0</div>
              <div style={{ marginTop: '8px' }}>满意指数 = 各选项加权平均</div>
              <div>预期指数 = 各选项加权平均</div>
              <div style={{ marginTop: '8px', color: '#58a6ff' }}>消费者信心指数 = (满意指数 + 预期指数) / 2</div>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              参考值：2019年(疫情前)约127, 2022年(低点)约86, 100以上为乐观区间
            </p>
          </div>
          <div className="arb-risk-section">
            <h4>PPI - 计算方法</h4>
            <p>工业生产者出厂价格指数，反映工业企业产品出厂价格变动趋势。</p>
            <ul>
              <li>以2020年为基期（=100），通过抽样调查全国约4万家工业企业</li>
              <li>涵盖40个工业行业大类、约1300个基本分类的代表产品</li>
              <li>同比 = 当月指数 / 去年同月指数 × 100 - 100</li>
            </ul>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '6px', margin: '8px 0', fontFamily: 'monospace', fontSize: '13px' }}>
              <div>指数 &gt; 100: 工业品价格上涨（通胀）</div>
              <div>指数 = 100: 价格持平</div>
              <div>指数 &lt; 100: 工业品价格下跌（通缩）</div>
            </div>
          </div>
          <div className="arb-risk-section">
            <h4>社零 - 计算方法</h4>
            <p>社会消费品零售总额，反映通过商品渠道售给居民和社会集团的消费品总量。</p>
            <ul>
              <li>统计范围：商品零售 + 餐饮收入</li>
              <li>数据来源：国家统计局对限额以上企业全面调查 + 限额以下抽样调查</li>
              <li>同比增速 = (当月值 - 去年同月值) / 去年同月值 × 100%</li>
              <li>注意：1-2月合并发布（消除春节影响），单月数据波动较大</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
