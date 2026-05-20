import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'

const API_BASE = '/api'

interface StockBasic {
  code: string
  name: string
  price: number
  open: number
  high: number
  low: number
  pre_close: number
  change_pct: number
  volume: number
  amount: number
  pe: number | null
  pb: number | null
  market_cap: number
}

interface FinancialReport {
  date: string
  report_name: string
  eps: number | null
  bps: number | null
  roe: number | null
  revenue: number | null
  net_profit: number | null
  revenue_growth: number | null
  profit_growth: number | null
  gross_margin: number | null
  net_margin: number | null
  debt_ratio: number | null
}

interface SearchItem {
  code: string
  name: string
}

interface FundArbitrage {
  fund_id: string
  fund_nm: string
  price: number
  fund_nav: number
  nav_discount_rt: number
  increase_rt: number
  volume: number
  turnover: number
  amount: number
  direction: string
  apply_fee: string
  redeem_fee: string
  apply_status: string
  redeem_status: string
  apply_limit: string
  nav_dt: string
  price_dt: string
  issuer_nm: string
  estimated_profit: number
}

// 热门股票列表
const HOT_STOCKS = [
  { code: '600519', name: '贵州茅台' },
  { code: '000858', name: '五粮液' },
  { code: '600036', name: '招商银行' },
  { code: '601318', name: '中国平安' },
  { code: '000333', name: '美的集团' },
  { code: '002714', name: '牧原股份' },
  { code: '300750', name: '宁德时代' },
  { code: '600900', name: '长江电力' },
  { code: '601888', name: '中国中免' },
  { code: '000568', name: '泸州老窖' },
]

function App() {
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState<SearchItem[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const [selectedStock, setSelectedStock] = useState<StockBasic | null>(null)
  const [financials, setFinancials] = useState<FinancialReport[]>([])
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [watchlist, setWatchlist] = useState<StockBasic[]>(HOT_STOCKS.map(s => ({
    ...s, price: 0, open: 0, high: 0, low: 0, pre_close: 0,
    change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0
  })))
  const [selectedList, setSelectedList] = useState<'watchlist' | 'hot'>('hot')
  const [fetchTime, setFetchTime] = useState('')
  const [latestReport, setLatestReport] = useState('')

  // 基金套利状态
  const [mainView, setMainView] = useState<'stock' | 'arbitrage'>('stock')
  const [arbFunds, setArbFunds] = useState<FundArbitrage[]>([])
  const [arbLoading, setArbLoading] = useState(false)
  const [arbFetchTime, setArbFetchTime] = useState('')
  const [arbDataSource, setArbDataSource] = useState('')
  const [arbTotalBefore, setArbTotalBefore] = useState(0)
  const [arbLoggedIn, setArbLoggedIn] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [loginUser, setLoginUser] = useState('')
  const [loginPass, setLoginPass] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [loginError, setLoginError] = useState('')

  // 搜索股票
  const handleSearch = useCallback(async (keyword: string) => {
    if (!keyword.trim()) {
      setSearchResults([])
      return
    }
    try {
      const res = await axios.get(`${API_BASE}/stocks/search`, { params: { keyword } })
      setSearchResults(res.data.results || [])
    } catch (err) {
      console.error('搜索失败:', err)
    }
  }, [])

  // 防抖搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchKeyword) {
        handleSearch(searchKeyword)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchKeyword, handleSearch])

  // 加载股票数据
  const loadStock = async (code: string) => {
    setLoading(true)
    setShowSearch(false)
    setSearchKeyword('')
    try {
      const [basicRes, finRes] = await Promise.all([
        axios.get(`${API_BASE}/stocks/${code}/basic`),
        axios.get(`${API_BASE}/stocks/${code}/financials`)
      ])
      setSelectedStock(basicRes.data)
      setFinancials(finRes.data.reports || [])
      setFetchTime(basicRes.data.fetch_time || new Date().toLocaleString())
      setLatestReport(finRes.data.latest_report_date || '')
    } catch (err) {
      console.error('加载失败:', err)
    } finally {
      setLoading(false)
    }
  }

  // 添加到自选
  const addToWatchlist = () => {
    if (selectedStock && !watchlist.find(s => s.code === selectedStock.code)) {
      setWatchlist(prev => [selectedStock, ...prev])
    }
  }

  // 加载套利数据
  const loadArbitrage = async () => {
    setArbLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/funds/arbitrage`, {
        params: { min_turnover: 300, open_subscribe_only: true }
      })
      setArbFunds(res.data.funds || [])
      setArbFetchTime(res.data.fetch_time || '')
      setArbDataSource(res.data.data_source || '')
      setArbTotalBefore(res.data.total_before_filter || 0)
      setArbLoggedIn(res.data.logged_in || false)
    } catch (err) {
      console.error('加载套利数据失败:', err)
    } finally {
      setArbLoading(false)
    }
  }

  // 登录集思录
  const handleLogin = async () => {
    if (!loginUser || !loginPass) return
    setLoginLoading(true)
    setLoginError('')
    try {
      await axios.post(`${API_BASE}/funds/login`, {
        user_name: loginUser,
        password: loginPass,
      })
      setShowLogin(false)
      setLoginUser('')
      setLoginPass('')
      // 登录成功后重新加载数据
      loadArbitrage()
    } catch (err: any) {
      setLoginError(err.response?.data?.detail || '登录失败')
    } finally {
      setLoginLoading(false)
    }
  }

  // 切换到套利视图
  const switchToArbitrage = () => {
    setMainView('arbitrage')
    loadArbitrage()
  }

  // 格式化数字
  const formatNum = (num: number | null | undefined, suffix = '') => {
    if (num === null || num === undefined) return '-'
    return num.toFixed(2) + suffix
  }

  // 格式化金额（万元转亿元）
  const formatAmount = (num: number | null | undefined) => {
    if (num === null || num === undefined) return '-'
    if (num >= 10000) return (num / 10000).toFixed(2) + '亿'
    return num.toFixed(2) + '万'
  }

  // 格式化成交量
  const formatVolume = (num: number) => {
    if (num >= 100000000) return (num / 100000000).toFixed(2) + '亿股'
    if (num >= 10000) return (num / 10000).toFixed(2) + '万股'
    return num + '股'
  }

  // 计算估值分位数（简化版）
  const getValuationLevel = (value: number | null, type: 'pe' | 'pb') => {
    if (!value) return { level: '-', color: '#999' }
    if (type === 'pe') {
      if (value < 15) return { level: '低估', color: '#52c41a' }
      if (value < 25) return { level: '合理', color: '#1890ff' }
      if (value < 40) return { level: '偏高', color: '#faad14' }
      return { level: '高估', color: '#ff4d4f' }
    } else {
      if (value < 1) return { level: '低估', color: '#52c41a' }
      if (value < 3) return { level: '合理', color: '#1890ff' }
      if (value < 5) return { level: '偏高', color: '#faad14' }
      return { level: '高估', color: '#ff4d4f' }
    }
  }

  // ROE图表
  const getROEChartOption = () => {
    if (!financials.length) return {}
    const dates = financials.map(f => f.date).reverse()
    const roeData = financials.map(f => f.roe).reverse()
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
      yAxis: { type: 'value', name: '%' },
      series: [{
        name: 'ROE',
        type: 'line',
        data: roeData,
        smooth: true,
        itemStyle: { color: '#1890ff' },
        areaStyle: { color: 'rgba(24,144,255,0.1)' },
        label: { show: true, formatter: '{c}%' }
      }]
    }
  }

  // 成长能力图表
  const getGrowthChartOption = () => {
    if (!financials.length) return {}
    const dates = financials.map(f => f.date).reverse()
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['营收增长率', '净利润增长率'], top: 0 },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
      yAxis: { type: 'value', name: '%' },
      series: [
        {
          name: '营收增长率',
          type: 'bar',
          data: financials.map(f => f.revenue_growth).reverse(),
          itemStyle: { color: '#1890ff' }
        },
        {
          name: '净利润增长率',
          type: 'bar',
          data: financials.map(f => f.profit_growth).reverse(),
          itemStyle: { color: '#52c41a' }
        }
      ]
    }
  }

  // 盈利能力图表
  const getProfitChartOption = () => {
    if (!financials.length) return {}
    const dates = financials.map(f => f.date).reverse()
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['毛利率', '净利率', 'ROE'], top: 0 },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
      yAxis: { type: 'value', name: '%' },
      series: [
        {
          name: '毛利率',
          type: 'line',
          data: financials.map(f => f.gross_margin).reverse(),
          itemStyle: { color: '#ff4d4f' }
        },
        {
          name: '净利率',
          type: 'line',
          data: financials.map(f => f.net_margin).reverse(),
          itemStyle: { color: '#1890ff' }
        },
        {
          name: 'ROE',
          type: 'line',
          data: financials.map(f => f.roe).reverse(),
          itemStyle: { color: '#52c41a' }
        }
      ]
    }
  }

  // 资产负债图表
  const getDebtChartOption = () => {
    if (!financials.length) return {}
    const dates = financials.map(f => f.date).reverse()
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
      yAxis: { type: 'value', name: '%' },
      series: [{
        name: '资产负债率',
        type: 'bar',
        data: financials.map(f => f.debt_ratio).reverse(),
        itemStyle: {
          color: (params: any) => {
            const value = params.value
            if (value < 40) return '#52c41a'
            if (value < 60) return '#faad14'
            return '#ff4d4f'
          }
        }
      }]
    }
  }

  // 计算最新财务指标
  const latestFin = financials.length > 0 ? financials[0] : null
  const peLevel = getValuationLevel(selectedStock?.pe ?? null, 'pe')
  const pbLevel = getValuationLevel(selectedStock?.pb ?? null, 'pb')

  return (
    <div className="app">
      {/* 左侧面板 */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>新源的Invest工具</h1>
          <div className="search-box">
            <input
              type="text"
              placeholder="输入股票代码或名称..."
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onFocus={() => setShowSearch(true)}
            />
            {showSearch && searchResults.length > 0 && (
              <div className="search-results">
                {searchResults.map(item => (
                  <div
                    key={item.code}
                    className="search-item"
                    onClick={() => loadStock(item.code)}
                  >
                    <span>{item.code}</span>
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Tab切换 */}
        <div className="list-tabs">
          <div className={`list-tab ${mainView === 'stock' && selectedList === 'hot' ? 'active' : ''}`}
            onClick={() => { setMainView('stock'); setSelectedList('hot') }}>热门股票</div>
          <div className={`list-tab ${mainView === 'stock' && selectedList === 'watchlist' ? 'active' : ''}`}
            onClick={() => { setMainView('stock'); setSelectedList('watchlist') }}>我的自选</div>
          <div className={`list-tab ${mainView === 'arbitrage' ? 'active' : ''}`}
            onClick={switchToArbitrage}>基金套利</div>
        </div>

        {mainView === 'stock' && (
          <div className="stock-list">
            {(selectedList === 'hot' ? HOT_STOCKS : watchlist).map(stock => (
              <div
                key={stock.code}
                className={`stock-item ${selectedStock?.code === stock.code ? 'active' : ''}`}
                onClick={() => loadStock(stock.code)}
              >
                <div className="stock-item-header">
                  <span className="code">{stock.code}</span>
                  <span className="name">{stock.name}</span>
                </div>
                {stock.price > 0 && (
                  <div className="stock-item-price">
                    <span className="price">{stock.price.toFixed(2)}</span>
                    <span className={`change ${stock.change_pct >= 0 ? 'up' : 'down'}`}>
                      {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {mainView === 'arbitrage' && (
          <div className="stock-list" style={{ padding: '16px', color: '#999', fontSize: '13px', textAlign: 'center' }}>
            <p>套利数据在右侧显示</p>
            <p style={{ marginTop: '8px', fontSize: '12px' }}>集思录数据源</p>
          </div>
        )}
      </div>

      {/* 右侧内容 */}
      <div className="main-content">
        {loading ? (
          <div className="loading">
            <div className="spinner"></div>
            加载中...
          </div>
        ) : mainView === 'arbitrage' ? (
          /* 基金套利页面 */
          <div className="arbitrage-page">
            <div className="stock-header">
              <div className="stock-title-row">
                <div>
                  <h2>场内外基金套利</h2>
                  <span className="stock-code">LOF 折溢价监控 · 成交额≥300万 · 开放申购</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn-add" onClick={loadArbitrage}>刷新数据</button>
                  {!arbLoggedIn && (
                    <button className="btn-add" style={{ background: '#722ed1' }}
                      onClick={() => setShowLogin(!showLogin)}>
                      登录集思录
                    </button>
                  )}
                </div>
              </div>
              <div className="data-freshness">
                <span className="freshness-tag">数据来源: {arbDataSource}</span>
                <span className="freshness-tag">更新时间: {arbFetchTime}</span>
                <span className="freshness-tag">原始数据: {arbTotalBefore} 只</span>
                <span className="freshness-tag">筛选后: {arbFunds.length} 只</span>
                {arbLoggedIn && <span className="freshness-tag" style={{ color: '#52c41a' }}>已登录</span>}
                {!arbLoggedIn && <span className="freshness-tag" style={{ color: '#faad14' }}>未登录(数据可能不全)</span>}
              </div>
            </div>

            {/* 登录表单 */}
            {showLogin && !arbLoggedIn && (
              <div className="arb-login-box">
                <div className="arb-login-title">登录集思录获取完整数据</div>
                <div className="arb-login-form">
                  <input
                    type="text"
                    placeholder="手机号/用户名"
                    value={loginUser}
                    onChange={(e) => setLoginUser(e.target.value)}
                  />
                  <input
                    type="password"
                    placeholder="密码"
                    value={loginPass}
                    onChange={(e) => setLoginPass(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  />
                  <button className="btn-add" onClick={handleLogin} disabled={loginLoading}>
                    {loginLoading ? '登录中...' : '登录'}
                  </button>
                </div>
                {loginError && <div className="arb-login-error">{loginError}</div>}
              </div>
            )}

            {/* 套利说明 */}
            <div className="arb-info">
              <div className="arb-info-item">
                <span className="arb-info-label">溢价套利:</span>
                <span>场外申购 → 转托管到场内 → 卖出 (T+3~T+4)</span>
              </div>
              <div className="arb-info-item">
                <span className="arb-info-label">折价套利:</span>
                <span>场内买入 → 转托管到场外 → 赎回 (T+2~T+3)</span>
              </div>
            </div>

            {/* 套利表格 */}
            {arbLoading ? (
              <div className="loading">
                <div className="spinner"></div>
                加载中...
              </div>
            ) : (
              <div className="table-container">
                <table className="arb-table">
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>成交额(万)</th>
                      <th>溢价率</th>
                      <th>方向</th>
                      <th>预估收益</th>
                      <th>场内价</th>
                      <th>场外净值</th>
                      <th>申购限额</th>
                      <th>申购状态</th>
                      <th>赎回状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {arbFunds.map((f) => (
                      <tr key={f.fund_id}>
                        <td>{f.fund_id}</td>
                        <td>{f.fund_nm}</td>
                        <td>{f.turnover.toFixed(0)}</td>
                        <td className={f.nav_discount_rt > 0 ? 'up' : 'down'}>
                          {f.nav_discount_rt > 0 ? '+' : ''}{f.nav_discount_rt.toFixed(2)}%
                        </td>
                        <td>
                          <span className={`arb-direction ${f.direction === '溢价' ? 'premium' : 'discount'}`}>
                            {f.direction}
                          </span>
                        </td>
                        <td className={f.estimated_profit > 0 ? 'up' : 'down'}>
                          {f.estimated_profit > 0 ? '+' : ''}{f.estimated_profit.toFixed(3)}%
                        </td>
                        <td>{f.price.toFixed(3)}</td>
                        <td>{f.fund_nav.toFixed(4)}</td>
                        <td style={{ fontSize: '11px', maxWidth: '120px' }}>{f.apply_limit || '-'}</td>
                        <td>{f.apply_status || '-'}</td>
                        <td>{f.redeem_status || '-'}</td>
                      </tr>
                    ))}
                    {arbFunds.length === 0 && (
                      <tr>
                        <td colSpan={11} style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                          暂无符合条件的套利机会
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : selectedStock ? (
          <>
            {/* 股票头部 */}
            <div className="stock-header">
              <div className="stock-title-row">
                <div>
                  <h2>{selectedStock.name}</h2>
                  <span className="stock-code">{selectedStock.code}</span>
                  <span className="market-tag">A股</span>
                </div>
                <button className="btn-add" onClick={addToWatchlist}>+ 加入自选</button>
              </div>

              {/* 数据时效信息 */}
              <div className="data-freshness">
                <span className="freshness-tag">行情时间: {selectedStock.trade_date} {selectedStock.trade_time}</span>
                <span className="freshness-tag">最新报告: {latestReport}</span>
                <span className="freshness-tag">数据获取: {fetchTime}</span>
              </div>

              <div className="price-section">
                <div className="current-price">
                  <span className={`price-big ${selectedStock.change_pct >= 0 ? 'up' : 'down'}`}>
                    {selectedStock.price.toFixed(2)}
                  </span>
                  <span className={`change-big ${selectedStock.change_pct >= 0 ? 'up' : 'down'}`}>
                    {selectedStock.change_pct >= 0 ? '+' : ''}{selectedStock.change_pct.toFixed(2)}%
                  </span>
                </div>
                <div className="price-details">
                  <div className="price-item">
                    <span className="label">今开</span>
                    <span className="value">{selectedStock.open.toFixed(2)}</span>
                  </div>
                  <div className="price-item">
                    <span className="label">最高</span>
                    <span className="value up">{selectedStock.high.toFixed(2)}</span>
                  </div>
                  <div className="price-item">
                    <span className="label">最低</span>
                    <span className="value down">{selectedStock.low.toFixed(2)}</span>
                  </div>
                  <div className="price-item">
                    <span className="label">昨收</span>
                    <span className="value">{selectedStock.pre_close.toFixed(2)}</span>
                  </div>
                  <div className="price-item">
                    <span className="label">成交量</span>
                    <span className="value">{formatVolume(selectedStock.volume)}</span>
                  </div>
                  <div className="price-item">
                    <span className="label">成交额</span>
                    <span className="value">{(selectedStock.amount / 100000000).toFixed(2)}亿</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 核心指标卡片 */}
            <div className="metrics-section">
              <h3>核心指标</h3>
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-label">市盈率(PE)</div>
                  <div className="metric-value">{formatNum(selectedStock.pe)}</div>
                  <div className="metric-tag" style={{ color: peLevel.color }}>{peLevel.level}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">市净率(PB)</div>
                  <div className="metric-value">{formatNum(selectedStock.pb)}</div>
                  <div className="metric-tag" style={{ color: pbLevel.color }}>{pbLevel.level}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">ROE</div>
                  <div className="metric-value">{formatNum(latestFin?.roe, '%')}</div>
                  <div className="metric-desc">净资产收益率</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">总市值</div>
                  <div className="metric-value">{selectedStock.market_cap.toFixed(0)}亿</div>
                  <div className="metric-desc">总市值</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">营收增长率</div>
                  <div className={`metric-value ${latestFin?.revenue_growth && latestFin.revenue_growth >= 0 ? 'up' : 'down'}`}>
                    {formatNum(latestFin?.revenue_growth, '%')}
                  </div>
                  <div className="metric-desc">同比增长</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">净利润增长率</div>
                  <div className={`metric-value ${latestFin?.profit_growth && latestFin.profit_growth >= 0 ? 'up' : 'down'}`}>
                    {formatNum(latestFin?.profit_growth, '%')}
                  </div>
                  <div className="metric-desc">同比增长</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">毛利率</div>
                  <div className="metric-value">{formatNum(latestFin?.gross_margin, '%')}</div>
                  <div className="metric-desc">销售毛利率</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">资产负债率</div>
                  <div className="metric-value">{formatNum(latestFin?.debt_ratio, '%')}</div>
                  <div className="metric-desc">财务杠杆</div>
                </div>
              </div>
            </div>

            {/* 巴菲特指标 */}
            <div className="buffett-section">
              <h3>巴菲特选股指标</h3>
              <div className="buffett-grid">
                <div className="buffett-item">
                  <div className="buffett-label">护城河</div>
                  <div className="buffett-value">
                    {latestFin?.gross_margin && latestFin.gross_margin > 50 ? '宽' : latestFin?.gross_margin && latestFin.gross_margin > 30 ? '窄' : '无'}
                  </div>
                  <div className="buffett-desc">毛利率 {formatNum(latestFin?.gross_margin, '%')}</div>
                </div>
                <div className="buffett-item">
                  <div className="buffett-label">盈利能力</div>
                  <div className="buffett-value">
                    {latestFin?.roe && latestFin.roe > 15 ? '优秀' : latestFin?.roe && latestFin.roe > 10 ? '良好' : '一般'}
                  </div>
                  <div className="buffett-desc">ROE {formatNum(latestFin?.roe, '%')}</div>
                </div>
                <div className="buffett-item">
                  <div className="buffett-label">成长性</div>
                  <div className="buffett-value">
                    {latestFin?.profit_growth && latestFin.profit_growth > 15 ? '高增长' : latestFin?.profit_growth && latestFin.profit_growth > 0 ? '稳定' : '下滑'}
                  </div>
                  <div className="buffett-desc">净利润增长 {formatNum(latestFin?.profit_growth, '%')}</div>
                </div>
                <div className="buffett-item">
                  <div className="buffett-label">财务健康</div>
                  <div className="buffett-value">
                    {latestFin?.debt_ratio && latestFin.debt_ratio < 40 ? '优秀' : latestFin?.debt_ratio && latestFin.debt_ratio < 60 ? '良好' : '风险'}
                  </div>
                  <div className="buffett-desc">资产负债率 {formatNum(latestFin?.debt_ratio, '%')}</div>
                </div>
              </div>
            </div>

            {/* Tab切换 */}
            <div className="tabs">
              <div className={`tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>财务概览</div>
              <div className={`tab ${activeTab === 'growth' ? 'active' : ''}`} onClick={() => setActiveTab('growth')}>成长能力</div>
              <div className={`tab ${activeTab === 'profit' ? 'active' : ''}`} onClick={() => setActiveTab('profit')}>盈利能力</div>
              <div className={`tab ${activeTab === 'debt' ? 'active' : ''}`} onClick={() => setActiveTab('debt')}>负债分析</div>
            </div>

            {/* 表格 */}
            <div className="table-container">
              {activeTab === 'overview' && (
                <table>
                  <thead>
                    <tr>
                      <th>报告期</th>
                      <th>每股收益(元)</th>
                      <th>每股净资产(元)</th>
                      <th>ROE(%)</th>
                      <th>营收(万元)</th>
                      <th>净利润(万元)</th>
                      <th>毛利率(%)</th>
                      <th>净利率(%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {financials.map((f, i) => (
                      <tr key={i}>
                        <td>{f.report_name || f.date}</td>
                        <td>{formatNum(f.eps)}</td>
                        <td>{formatNum(f.bps)}</td>
                        <td>{formatNum(f.roe)}</td>
                        <td>{formatAmount(f.revenue)}</td>
                        <td>{formatAmount(f.net_profit)}</td>
                        <td>{formatNum(f.gross_margin)}</td>
                        <td>{formatNum(f.net_margin)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {activeTab === 'growth' && (
                <table>
                  <thead>
                    <tr>
                      <th>报告期</th>
                      <th>营收(万元)</th>
                      <th>营收增长率(%)</th>
                      <th>净利润(万元)</th>
                      <th>净利润增长率(%)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {financials.map((f, i) => (
                      <tr key={i}>
                        <td>{f.report_name || f.date}</td>
                        <td>{formatAmount(f.revenue)}</td>
                        <td className={f.revenue_growth && f.revenue_growth >= 0 ? 'up' : 'down'}>
                          {formatNum(f.revenue_growth)}
                        </td>
                        <td>{formatAmount(f.net_profit)}</td>
                        <td className={f.profit_growth && f.profit_growth >= 0 ? 'up' : 'down'}>
                          {formatNum(f.profit_growth)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {activeTab === 'profit' && (
                <table>
                  <thead>
                    <tr>
                      <th>报告期</th>
                      <th>毛利率(%)</th>
                      <th>净利率(%)</th>
                      <th>ROE(%)</th>
                      <th>每股收益(元)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {financials.map((f, i) => (
                      <tr key={i}>
                        <td>{f.report_name || f.date}</td>
                        <td>{formatNum(f.gross_margin)}</td>
                        <td>{formatNum(f.net_margin)}</td>
                        <td>{formatNum(f.roe)}</td>
                        <td>{formatNum(f.eps)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {activeTab === 'debt' && (
                <table>
                  <thead>
                    <tr>
                      <th>报告期</th>
                      <th>资产负债率(%)</th>
                      <th>每股净资产(元)</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {financials.map((f, i) => (
                      <tr key={i}>
                        <td>{f.report_name || f.date}</td>
                        <td>{formatNum(f.debt_ratio)}</td>
                        <td>{formatNum(f.bps)}</td>
                        <td>
                          <span style={{
                            color: f.debt_ratio && f.debt_ratio < 40 ? '#52c41a' :
                              f.debt_ratio && f.debt_ratio < 60 ? '#faad14' : '#ff4d4f'
                          }}>
                            {f.debt_ratio && f.debt_ratio < 40 ? '健康' :
                              f.debt_ratio && f.debt_ratio < 60 ? '适中' : '偏高'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* 图表 */}
            <div className="charts-row">
              <div className="chart-container">
                <div className="chart-title">ROE趋势</div>
                <ReactECharts option={getROEChartOption()} style={{ height: 300 }} />
              </div>
              <div className="chart-container">
                <div className="chart-title">成长能力</div>
                <ReactECharts option={getGrowthChartOption()} style={{ height: 300 }} />
              </div>
            </div>

            <div className="charts-row">
              <div className="chart-container">
                <div className="chart-title">盈利能力</div>
                <ReactECharts option={getProfitChartOption()} style={{ height: 300 }} />
              </div>
              <div className="chart-container">
                <div className="chart-title">资产负债率</div>
                <ReactECharts option={getDebtChartOption()} style={{ height: 300 }} />
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="icon">📊</div>
            <div className="text">新源的Invest工具</div>
            <div className="sub-text">输入股票代码开始分析 | 支持A股</div>
            <div className="hot-stocks">
              <div className="hot-title">热门股票</div>
              <div className="hot-list">
                {HOT_STOCKS.map(stock => (
                  <div key={stock.code} className="hot-item" onClick={() => loadStock(stock.code)}>
                    <span className="hot-name">{stock.name}</span>
                    <span className="hot-code">{stock.code}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
