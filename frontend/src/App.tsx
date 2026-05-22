import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import ReactECharts from 'echarts-for-react'
import HKIpoPage from './pages/HKIpoPage'
import IndexValuation from './pages/IndexValuation'
import USMarket from './pages/USMarket'
import DividendScreener from './pages/DividendScreener'
import CigarButtScreener from './pages/CigarButtScreener'
import ValueInvesting from './pages/ValueInvesting'
import REITScreener from './pages/REITScreener'
import CryptoScreener from './pages/CryptoScreener'
import MacroData from './pages/MacroData'
import FuturesData from './pages/FuturesData'

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
  trade_date?: string
  trade_time?: string
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

interface ConvertibleBond {
  bond_id: string
  bond_nm: string
  stock_id: string
  stock_nm: string
  price: number
  convert_price: number
  convert_value: number
  premium_rt: number
  double_low: number
  maturity_dt: string
  year_left: number
  rating_cd: string
  curr_iss_amt: number
  turnover: number
  stock_price: number
  stock_change: number
  bond_change: number
  force_redeem: string
  is_matured: boolean
}

// 热门股票列表
const HOT_STOCKS: StockBasic[] = [
  { code: '600519', name: '贵州茅台', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '000858', name: '五粮液', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '600036', name: '招商银行', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '601318', name: '中国平安', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '000333', name: '美的集团', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '002714', name: '牧原股份', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '300750', name: '宁德时代', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '600900', name: '长江电力', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '601888', name: '中国中免', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
  { code: '000568', name: '泸州老窖', price: 0, open: 0, high: 0, low: 0, pre_close: 0, change_pct: 0, volume: 0, amount: 0, pe: null, pb: null, market_cap: 0 },
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

  // 期权计算状态
  const [optionTab, setOptionTab] = useState<'put' | 'call'>('put')
  const [putPremium, setPutPremium] = useState('')
  const [putStrike, setPutStrike] = useState('')
  const [putDays, setPutDays] = useState('')
  const [putResult, setPutResult] = useState<{ annualYield: number; profit: number; annualFactor: number } | null>(null)
  const [callCurrentPrice, setCallCurrentPrice] = useState('')
  const [callPremium, setCallPremium] = useState('')
  const [callStrike, setCallStrike] = useState('')
  const [callDays, setCallDays] = useState('')
  const [callResult, setCallResult] = useState<{ annualYield: number; totalProfit: number; investment: number } | null>(null)

  // 可转债双低状态
  const [cbBonds, setCbBonds] = useState<ConvertibleBond[]>([])
  const [cbLoading, setCbLoading] = useState(false)
  const [cbFetchTime, setCbFetchTime] = useState('')
  const [cbTotalBefore, setCbTotalBefore] = useState(0)
  const [cbTotal, setCbTotal] = useState(0)
  const [cbMaxDoubleLow, setCbMaxDoubleLow] = useState(130)
  const [cbTopN, setCbTopN] = useState(20)
  const [cbLoggedIn, setCbLoggedIn] = useState(false)

  // 基金套利状态
  const [mainView, setMainView] = useState<'stock' | 'arbitrage' | 'option' | 'cb' | 'hki' | 'indexVal' | 'usMarket' | 'dividend' | 'cigarButt' | 'valueInvesting' | 'reit' | 'crypto' | 'macro' | 'futures'>('stock')
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

  // 国债收益率状态
  const [bondYields, setBondYields] = useState<{ cn: any; us: any } | null>(null)
  const [bondLoading, setBondLoading] = useState(false)

  // 加载国债收益率
  const loadBondYields = useCallback(async () => {
    setBondLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/bonds/yields`)
      setBondYields({ cn: res.data.cn, us: res.data.us })
    } catch (e) {
      console.error('获取国债收益率失败:', e)
    } finally {
      setBondLoading(false)
    }
  }, [])

  useEffect(() => { loadBondYields() }, [loadBondYields])

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
        params: { min_threshold: 2, min_turnover: 1000, open_subscribe_only: false }
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

  // 加载可转债双低数据
  const loadCB = async (maxDoubleLow?: number, topN?: number) => {
    setCbLoading(true)
    try {
      const res = await axios.get(`${API_BASE}/cb/double-low`, {
        params: {
          max_double_low: maxDoubleLow ?? cbMaxDoubleLow,
          top_n: topN ?? cbTopN,
          min_turnover: 100,
          min_year_left: 1,
          exclude_st: true,
          exclude_force_redeem: true,
        }
      })
      setCbBonds(res.data.bonds || [])
      setCbFetchTime(res.data.fetch_time || '')
      setCbTotalBefore(res.data.total_before_filter || 0)
      setCbTotal(res.data.total || 0)
      setCbLoggedIn(res.data.logged_in || false)
    } catch (err) {
      console.error('加载可转债数据失败:', err)
    } finally {
      setCbLoading(false)
    }
  }

  // 切换到可转债视图
  const switchToCB = () => {
    setMainView('cb')
    loadCB()
  }

  // Sell Put 计算
  const calculatePut = () => {
    const premium = parseFloat(putPremium)
    const strike = parseFloat(putStrike)
    const days = parseInt(putDays)
    if (isNaN(premium) || isNaN(strike) || isNaN(days) || premium <= 0 || strike <= 0 || days <= 0) return
    if (strike - premium <= 0) return
    const profit = premium
    const annualFactor = 365 / days
    const annualYield = (profit / (strike - profit)) * annualFactor * 100
    setPutResult({ annualYield, profit, annualFactor })
  }

  // Sell Call 计算
  const calculateCall = () => {
    const currentPrice = parseFloat(callCurrentPrice)
    const premium = parseFloat(callPremium)
    const strike = parseFloat(callStrike)
    const days = parseInt(callDays)
    if (isNaN(currentPrice) || isNaN(premium) || isNaN(strike) || isNaN(days)) return
    if (currentPrice <= 0 || days <= 0 || currentPrice - premium <= 0) return
    const totalProfit = strike - currentPrice + premium
    const investment = currentPrice - premium
    const annualYield = (totalProfit / investment) * (365 / days) * 100
    setCallResult({ annualYield, totalProfit, investment })
  }

  // 年化收益率颜色
  const getYieldColor = (value: number) => {
    if (value >= 30) return '#52c41a'
    if (value >= 15) return '#faad14'
    return '#ff4d4f'
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
    if (!value) return { level: '-', color: 'var(--text-muted)' }
    if (type === 'pe') {
      if (value < 15) return { level: '低估', color: '#3fb950' }
      if (value < 25) return { level: '合理', color: '#1890ff' }
      if (value < 40) return { level: '偏高', color: '#faad14' }
      return { level: '高估', color: '#ff4d4f' }
    } else {
      if (value < 1) return { level: '低估', color: '#3fb950' }
      if (value < 3) return { level: '合理', color: '#58a6ff' }
      if (value < 5) return { level: '偏高', color: '#d29922' }
      return { level: '高估', color: '#f85149' }
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
        itemStyle: { color: '#58a6ff' },
        areaStyle: { color: 'rgba(88,166,255,0.1)' },
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
          itemStyle: { color: '#58a6ff' }
        },
        {
          name: '净利润增长率',
          type: 'bar',
          data: financials.map(f => f.profit_growth).reverse(),
          itemStyle: { color: '#3fb950' }
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
          itemStyle: { color: '#f85149' }
        },
        {
          name: '净利率',
          type: 'line',
          data: financials.map(f => f.net_margin).reverse(),
          itemStyle: { color: '#58a6ff' }
        },
        {
          name: 'ROE',
          type: 'line',
          data: financials.map(f => f.roe).reverse(),
          itemStyle: { color: '#3fb950' }
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
            if (value < 40) return '#3fb950'
            if (value < 60) return '#d29922'
            return '#f85149'
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

        {/* 国债收益率 & 股债比 */}
        <div style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-primary)',
          background: 'var(--bg-tertiary)',
        }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>十年期国债收益率 & 股债比</span>
            <span
              onClick={loadBondYields}
              style={{ cursor: 'pointer', color: 'var(--accent-blue)' }}
            >
              {bondLoading ? '...' : '刷新'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            {/* 中国 */}
            <div className="bond-yield-card">
              <div className="bond-yield-label">中国 · 沪深300</div>
              <div className="bond-yield-value" style={{ color: '#f85149' }}>
                {bondYields?.cn?.yield?.toFixed(2) ?? '--'}%
              </div>
              <div className="bond-yield-change" style={{
                color: (bondYields?.cn?.change ?? 0) >= 0 ? '#f85149' : '#3fb950',
              }}>
                {bondYields?.cn?.change != null
                  ? `${bondYields.cn.change >= 0 ? '+' : ''}${bondYields.cn.change.toFixed(3)}`
                  : '--'}
              </div>
              <div className="bond-yield-details">
                <div>PE: {bondYields?.cn?.pe ?? '--'}</div>
                <div style={{ marginTop: '2px' }}>
                  股债比: <span style={{
                    fontWeight: 600,
                    color: (bondYields?.cn?.stock_bond_ratio ?? 0) > 1 ? '#3fb950' : '#f85149',
                  }}>
                    {bondYields?.cn?.stock_bond_ratio?.toFixed(2) ?? '--'}
                  </span>
                </div>
              </div>
            </div>
            {/* 美国 */}
            <div className="bond-yield-card">
              <div className="bond-yield-label">美国 · 标普500</div>
              <div className="bond-yield-value" style={{ color: '#58a6ff' }}>
                {bondYields?.us?.yield?.toFixed(2) ?? '--'}%
              </div>
              <div className="bond-yield-change" style={{
                color: (bondYields?.us?.change ?? 0) >= 0 ? '#f85149' : '#3fb950',
              }}>
                {bondYields?.us?.change != null
                  ? `${bondYields.us.change >= 0 ? '+' : ''}${bondYields.us.change.toFixed(3)}`
                  : '--'}
              </div>
              <div className="bond-yield-details">
                <div>PE: {bondYields?.us?.pe ?? '--'}</div>
                <div style={{ marginTop: '2px' }}>
                  股债比: <span style={{
                    fontWeight: 600,
                    color: (bondYields?.us?.stock_bond_ratio ?? 0) > 1 ? '#3fb950' : '#f85149',
                  }}>
                    {bondYields?.us?.stock_bond_ratio?.toFixed(2) ?? '--'}
                  </span>
                </div>
              </div>
            </div>
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
          <div className={`list-tab ${mainView === 'option' ? 'active' : ''}`}
            onClick={() => setMainView('option')}>期权计算</div>
          <div className={`list-tab ${mainView === 'cb' ? 'active' : ''}`}
            onClick={switchToCB}>可转债</div>
          <div className={`list-tab ${mainView === 'hki' ? 'active' : ''}`}
            onClick={() => setMainView('hki')}>港新</div>
          <div className={`list-tab ${mainView === 'indexVal' ? 'active' : ''}`}
            onClick={() => setMainView('indexVal')}>指数估值</div>
          <div className={`list-tab ${mainView === 'usMarket' ? 'active' : ''}`}
            onClick={() => setMainView('usMarket')}>美股/币</div>
          <div className={`list-tab ${mainView === 'dividend' ? 'active' : ''}`}
            onClick={() => setMainView('dividend')}>攒股收息</div>
          <div className={`list-tab ${mainView === 'cigarButt' ? 'active' : ''}`}
            onClick={() => setMainView('cigarButt')}>捡烟蒂</div>
          <div className={`list-tab ${mainView === 'valueInvesting' ? 'active' : ''}`}
            onClick={() => setMainView('valueInvesting')}>价投筛选</div>
          <div className={`list-tab ${mainView === 'reit' ? 'active' : ''}`}
            onClick={() => setMainView('reit')}>REIT筛选</div>
          <div className={`list-tab ${mainView === 'crypto' ? 'active' : ''}`}
            onClick={() => setMainView('crypto')}>币圈信息</div>
          <div className={`list-tab ${mainView === 'macro' ? 'active' : ''}`}
            onClick={() => setMainView('macro')}>宏观数据</div>
          <div className={`list-tab ${mainView === 'futures' ? 'active' : ''}`}
            onClick={() => setMainView('futures')}>期货行业</div>
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
          <div className="stock-list sidebar-info">
            <p>套利数据在右侧显示</p>
            <p>集思录数据源</p>
          </div>
        )}

        {mainView === 'option' && (
          <div className="stock-list sidebar-info">
            <p>期权计算器</p>
            <p>Sell Put / Sell Call</p>
          </div>
        )}

        {mainView === 'cb' && (
          <div className="stock-list sidebar-info">
            <p>可转债双低策略</p>
            <p>双低值 = 价格 + 溢价率</p>
          </div>
        )}

        {mainView === 'hki' && (
          <div className="stock-list sidebar-info">
            <p>港股打新工具箱</p>
            <p>新股日历 · 收益分析 · 模拟器</p>
          </div>
        )}

        {mainView === 'indexVal' && (
          <div className="stock-list sidebar-info">
            <p>指数估值</p>
            <p>PE · PB · ROE · 股息率</p>
          </div>
        )}

        {mainView === 'dividend' && (
          <div className="stock-list sidebar-info">
            <p>王文 & 散户乙</p>
            <p>投资筛选 · 攒股收息</p>
          </div>
        )}

        {mainView === 'cigarButt' && (
          <div className="stock-list sidebar-info">
            <p>港股烟蒂股</p>
            <p>格雷厄姆 · 巴菲特 · 施洛斯</p>
          </div>
        )}

        {mainView === 'valueInvesting' && (
          <div className="stock-list sidebar-info">
            <p>价值投资筛选</p>
            <p>巴菲特 · 芒格 · 李录 · 段永平</p>
          </div>
        )}

        {mainView === 'reit' && (
          <div className="stock-list sidebar-info">
            <p>REIT高分红筛选</p>
            <p>分红率≥5% · 规避陷阱</p>
          </div>
        )}

        {mainView === 'crypto' && (
          <div className="stock-list sidebar-info">
            <p>币圈信息源</p>
            <p>高质量渠道 · 过滤噪音</p>
          </div>
        )}

        {mainView === 'macro' && (
          <div className="stock-list sidebar-info">
            <p>宏观经济数据</p>
            <p>GDP · CPI · PMI · M2 · LPR</p>
          </div>
        )}

        {mainView === 'futures' && (
          <div className="stock-list sidebar-info">
            <p>期货行业数据</p>
            <p>商品快照 · 行业排名 · 资金流向</p>
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
        ) : mainView === 'hki' ? (
          <HKIpoPage />
        ) : mainView === 'indexVal' ? (
          <IndexValuation />
        ) : mainView === 'usMarket' ? (
          <USMarket />
        ) : mainView === 'dividend' ? (
          <DividendScreener />
        ) : mainView === 'cigarButt' ? (
          <CigarButtScreener />
        ) : mainView === 'valueInvesting' ? (
          <ValueInvesting />
        ) : mainView === 'reit' ? (
          <REITScreener />
        ) : mainView === 'crypto' ? (
          <CryptoScreener />
        ) : mainView === 'macro' ? (
          <MacroData />
        ) : mainView === 'futures' ? (
          <FuturesData />
        ) : mainView === 'option' ? (
          /* 期权收益计算器 */
          <div className="option-page">
            <div className="stock-header">
              <div className="stock-title-row">
                <div>
                  <h2>期权年化收益计算器</h2>
                  <span className="stock-code">Sell Put / Sell Call 年化收益率计算</span>
                </div>
              </div>
            </div>

            <div className="option-tabs">
              <div className={`option-tab ${optionTab === 'put' ? 'active' : ''}`}
                onClick={() => setOptionTab('put')}>Sell Put</div>
              <div className={`option-tab ${optionTab === 'call' ? 'active' : ''}`}
                onClick={() => setOptionTab('call')}>Sell Call</div>
            </div>

            <div className="option-form-card">
              {optionTab === 'put' ? (
                <>
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
                  <button className="option-btn" onClick={calculatePut}>计算年化收益率</button>

                  {putResult && (
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
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <>
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
                          <span>¥{callResult.totalProfit.toFixed(2)}</span>
                        </div>
                        <div className="option-detail-row">
                          <span>投资金额：</span>
                          <span>¥{callResult.investment.toFixed(2)}</span>
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
                  <p>适用于未被行权的情况</p>
                  <p className="option-formula">年化收益率 = (权利金 / (行权价 - 权利金)) × (365 / 到期天数)</p>
                </div>
                <div className="option-note-section">
                  <h4>Sell Call 计算器</h4>
                  <p>适用于被行权的情况</p>
                  <p className="option-formula">年化收益率 = (行权价 - 现价 + 权利金) / (现价 - 权利金) × (365 / 到期天数)</p>
                </div>
                <div className="option-note-section">
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>实际交易中请考虑交易成本、滑点等因素。</p>
                </div>
              </div>
            </div>
          </div>
        ) : mainView === 'cb' ? (
          /* 可转债双低轮动策略 */
          <div className="cb-page">
            <div className="stock-header">
              <div className="stock-title-row">
                <div>
                  <h2>可转债双低轮动策略</h2>
                  <span className="stock-code">双低值 = 转债价格 + 转股溢价率 · 低价格 + 低溢价率</span>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <select value={cbMaxDoubleLow} onChange={e => { setCbMaxDoubleLow(Number(e.target.value)); loadCB(Number(e.target.value), cbTopN) }}
                    style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
                    <option value={120}>双低 ≤ 120</option>
                    <option value={130}>双低 ≤ 130</option>
                    <option value={140}>双低 ≤ 140</option>
                    <option value={150}>双低 ≤ 150</option>
                    <option value={999}>不限</option>
                  </select>
                  <select value={cbTopN} onChange={e => { setCbTopN(Number(e.target.value)); loadCB(cbMaxDoubleLow, Number(e.target.value)) }}
                    style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: '4px', fontSize: '13px' }}>
                    <option value={10}>前10只</option>
                    <option value={20}>前20只</option>
                    <option value={30}>前30只</option>
                    <option value={50}>前50只</option>
                  </select>
                  <button className="btn-add" onClick={() => loadCB()}>刷新数据</button>
                </div>
              </div>
              <div className="data-freshness">
                <span className="freshness-tag">更新时间: {cbFetchTime}</span>
                <span className="freshness-tag">原始数据: {cbTotalBefore} 只</span>
                <span className="freshness-tag">筛选后: {cbTotal} 只</span>
                <span className="freshness-tag">显示: {cbBonds.length} 只</span>
              </div>
            </div>

            {/* 策略说明 */}
            <div className="arb-notes">
              <h3>双低轮动策略说明</h3>
              <div className="arb-notes-grid">
                <div className="arb-note-item">
                  <span className="arb-note-label">双低值</span>
                  <span className="arb-note-value">价格 + 溢价率</span>
                  <span className="arb-note-desc">兼顾债性保护（低价格）和股性弹性（低溢价率）</span>
                </div>
                <div className="arb-note-item">
                  <span className="arb-note-label">筛选条件</span>
                  <span className="arb-note-value">双低 ≤ {cbMaxDoubleLow}</span>
                  <span className="arb-note-desc">排除ST、强赎、剩余年限&lt;1年、成交额&lt;100万</span>
                </div>
                <div className="arb-note-item">
                  <span className="arb-note-label">轮动周期</span>
                  <span className="arb-note-value">1~2周</span>
                  <span className="arb-note-desc">定期按最新双低排名调仓，卖出排名下滑标的</span>
                </div>
                <div className="arb-note-item">
                  <span className="arb-note-label">卖出条件</span>
                  <span className="arb-note-value">双低 &gt; 130</span>
                  <span className="arb-note-desc">双低值超过阈值、触发强赎、正股重大风险</span>
                </div>
              </div>
            </div>

            {/* 双低排名表格 */}
            {cbLoading ? (
              <div className="loading">
                <div className="spinner"></div>
                加载中...
              </div>
            ) : (
              <div className="table-container">
                <div className="arb-section-title">双低排名（按双低值升序）</div>
                <table className="arb-table">
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>代码</th>
                      <th>转债名称</th>
                      <th>现价</th>
                      <th>转股溢价率(%)</th>
                      <th>双低值</th>
                      <th>正股名称</th>
                      <th>正股价</th>
                      <th>评级</th>
                      <th>剩余年限</th>
                      <th>成交额(万)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cbBonds.map((b, i) => (
                      <tr key={b.bond_id}>
                        <td>{i + 1}</td>
                        <td>{b.bond_id}</td>
                        <td>{b.bond_nm}</td>
                        <td>{b.price.toFixed(2)}</td>
                        <td className={b.premium_rt <= 0 ? 'down' : ''}>{b.premium_rt.toFixed(2)}</td>
                        <td style={{ fontWeight: 700, color: b.double_low <= 120 ? '#52c41a' : b.double_low <= 130 ? '#1890ff' : '#faad14' }}>
                          {b.double_low.toFixed(2)}
                        </td>
                        <td>{b.stock_nm}</td>
                        <td>{b.stock_price.toFixed(2)}</td>
                        <td>{b.rating_cd}</td>
                        <td>{b.year_left.toFixed(1)}</td>
                        <td>{b.turnover.toFixed(0)}</td>
                      </tr>
                    ))}
                    {cbBonds.length === 0 && (
                      <tr>
                        <td colSpan={11} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                          暂无符合条件的可转债
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* 注意事项 */}
            <div className="arb-notes">
              <h3>可转债双低策略注意事项</h3>
              <div className="arb-notes-content">
                <div className="arb-risk-section">
                  <h4>策略优势</h4>
                  <ul>
                    <li><strong>低价格</strong>：价格低意味着下跌空间有限，债底保护强</li>
                    <li><strong>低溢价率</strong>：溢价率低意味着跟涨能力强，股性好</li>
                    <li><strong>两者结合</strong>：同时满足"债性保护"和"股性弹性"，攻守兼备</li>
                    <li>规则简单、可量化、可执行，历史回测长期年化收益约8%~15%</li>
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>轮动操作</h4>
                  <ul>
                    <li>每1~2周按最新双低排名调仓一次</li>
                    <li>卖出排名跌出前N的转债，买入新进入前N的转债</li>
                    <li>转债触发强赎或到期时及时卖出</li>
                    <li>建议等权持有10~20只分散风险</li>
                  </ul>
                </div>
                <div className="arb-risk-section">
                  <h4>风险提示</h4>
                  <ul>
                    <li><strong>信用风险</strong>：低评级转债可能存在违约风险，建议选择AA-以上评级</li>
                    <li><strong>流动性风险</strong>：成交额过小的转债难以按预期价格买卖</li>
                    <li><strong>市场风险</strong>：极端熊市中双低策略仍有回撤，但通常小于正股</li>
                    <li><strong>强赎风险</strong>：关注强赎公告，避免被低价赎回</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ) : mainView === 'arbitrage' ? (
          /* 基金套利页面 */
          <div className="arbitrage-page">
            <div className="stock-header">
              <div className="stock-title-row">
                <div>
                  <h2>场内外基金套利</h2>
                  <span className="stock-code">LOF 折溢价监控 · 溢价率≥2% · 成交额＞1000万</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn-add" onClick={loadArbitrage}>刷新数据</button>
                  {!arbLoggedIn && (
                    <button className="btn-add" style={{ background: 'var(--accent-purple)' }}
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
                {arbLoggedIn && <span className="freshness-tag success">已登录</span>}
                {!arbLoggedIn && <span className="freshness-tag warning">未登录(数据可能不全)</span>}
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
              <>
                {/* 溢价LOF */}
                <div className="table-container">
                  <div className="arb-section-title">溢价LOF（场外申购 → 转托管 → 场内卖出）</div>
                  <table className="arb-table">
                    <thead>
                      <tr>
                        <th>序号</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th>场内价格</th>
                        <th>场外净值</th>
                        <th>溢价率</th>
                        <th>申购费率</th>
                        <th>预估收益</th>
                        <th>交易额(万)</th>
                        <th>净值日期</th>
                        <th>限购</th>
                      </tr>
                    </thead>
                    <tbody>
                      {arbFunds.filter(f => f.direction === '溢价').map((f, i) => (
                        <tr key={f.fund_id}>
                          <td>{i + 1}</td>
                          <td>{f.fund_id}</td>
                          <td>{f.fund_nm}</td>
                          <td>{f.price.toFixed(3)}</td>
                          <td>{f.fund_nav.toFixed(4)}</td>
                          <td className="up">+{f.nav_discount_rt.toFixed(2)}%</td>
                          <td>{f.apply_fee || '-'}</td>
                          <td style={{ color: f.estimated_profit > 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
                            {f.estimated_profit > 0 ? '+' : ''}{f.estimated_profit.toFixed(2)}%
                          </td>
                          <td>{f.turnover.toFixed(0)}</td>
                          <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{f.nav_dt}</td>
                          <td>{f.apply_limit || '-'}</td>
                        </tr>
                      ))}
                      {arbFunds.filter(f => f.direction === '溢价').length === 0 && (
                        <tr>
                          <td colSpan={11} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                            暂无溢价LOF基金
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* 折价LOF */}
                <div className="table-container">
                  <div className="arb-section-title">折价LOF（场内买入 → 转托管 → 场外赎回）</div>
                  <table className="arb-table">
                    <thead>
                      <tr>
                        <th>序号</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th>场内价格</th>
                        <th>场外净值</th>
                        <th>折价率</th>
                        <th>赎回费率</th>
                        <th>预估收益</th>
                        <th>交易额(万)</th>
                        <th>净值日期</th>
                        <th>限购</th>
                      </tr>
                    </thead>
                    <tbody>
                      {arbFunds.filter(f => f.direction === '折价').map((f, i) => (
                        <tr key={f.fund_id}>
                          <td>{i + 1}</td>
                          <td>{f.fund_id}</td>
                          <td>{f.fund_nm}</td>
                          <td>{f.price.toFixed(3)}</td>
                          <td>{f.fund_nav.toFixed(4)}</td>
                          <td className="down">{f.nav_discount_rt.toFixed(2)}%</td>
                          <td>{f.redeem_fee || '-'}</td>
                          <td style={{ color: f.estimated_profit > 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
                            {f.estimated_profit > 0 ? '+' : ''}{f.estimated_profit.toFixed(2)}%
                          </td>
                          <td>{f.turnover.toFixed(0)}</td>
                          <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{f.nav_dt}</td>
                          <td>{f.apply_limit || '-'}</td>
                        </tr>
                      ))}
                      {arbFunds.filter(f => f.direction === '折价').length === 0 && (
                        <tr>
                          <td colSpan={11} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                            暂无折价LOF基金
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* 计算方式说明 */}
                <div className="arb-notes">
                  <h3>计算方式说明（人工核对用）</h3>
                  <div className="arb-notes-content">
                    <div className="arb-risk-section">
                      <h4>1. 溢价率计算公式</h4>
                      <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '6px', margin: '8px 0', fontFamily: 'monospace' }}>
                        <div><strong>溢价率(%)</strong> = (场内价格 - 场外净值) / 场外净值 × 100%</div>
                        <div style={{ marginTop: '8px', color: 'var(--text-muted)' }}>示例：场内价格 = 1.50元，场外净值 = 1.45元</div>
                        <div style={{ color: 'var(--text-muted)' }}>溢价率 = (1.50 - 1.45) / 1.45 × 100% = 3.45%</div>
                      </div>
                      <ul>
                        <li><strong>场内价格</strong>：LOF基金在证券交易所的实时交易价格</li>
                        <li><strong>场外净值</strong>：基金公司公布的T日净值（T+1公布），非实时估算</li>
                        <li><strong>正数为溢价</strong>（场内价格 {'>'} 场外净值），负数为折价</li>
                      </ul>
                    </div>
                    <div className="arb-risk-section">
                      <h4>2. 预估收益率计算</h4>
                      <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '6px', margin: '8px 0', fontFamily: 'monospace' }}>
                        <div><strong>溢价套利收益率(%)</strong> = 溢价率 - 申购费率</div>
                        <div><strong>折价套利收益率(%)</strong> = 折价率 - 赎回费率</div>
                        <div style={{ marginTop: '8px', color: 'var(--text-muted)' }}>注：还需扣除交易佣金（约0.03%-0.05%）和冲击成本</div>
                      </div>
                    </div>
                    <div className="arb-risk-section">
                      <h4>3. 与 palmmicro 数据差异说明</h4>
                      <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '6px', margin: '8px 0' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text-muted)' }}>对比项</th>
                              <th style={{ textAlign: 'left', padding: '8px', color: 'var(--accent-blue)' }}>本系统</th>
                              <th style={{ textAlign: 'left', padding: '8px', color: 'var(--accent-green)' }}>palmmicro</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: '8px' }}>数据来源</td>
                              <td style={{ padding: '8px' }}>集思录</td>
                              <td style={{ padding: '8px' }}>自建EST估算系统</td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: '8px' }}>净值类型</td>
                              <td style={{ padding: '8px' }}>场外净值（T+1公布）</td>
                              <td style={{ padding: '8px' }}>实时EST估算净值</td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: '8px' }}>溢价率计算</td>
                              <td style={{ padding: '8px' }}>(价格 - 场外净值) / 场外净值</td>
                              <td style={{ padding: '8px' }}>(价格 - EST) / EST</td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: '8px' }}>数据时效</td>
                              <td style={{ padding: '8px' }}>T日净值，T+1公布</td>
                              <td style={{ padding: '8px' }}>实时估算（盘中更新）</td>
                            </tr>
                            <tr>
                              <td style={{ padding: '8px' }}>筛选条件</td>
                              <td style={{ padding: '8px' }}>溢价≥2%，成交额{'>'}1000万</td>
                              <td style={{ padding: '8px' }}>显示全部LOF（53只）</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>
                        <strong>注意</strong>：由于净值来源不同，两个系统的溢价率会有差异。
                        palmmicro的EST是实时估算，而本系统使用的是T日实际净值（T+1公布）。
                        建议以基金公司官方公布的净值为准进行核对。
                      </p>
                    </div>
                    <div className="arb-risk-section">
                      <h4>4. 数据字段说明</h4>
                      <ul>
                        <li><strong>代码</strong>：基金代码，如 161128</li>
                        <li><strong>名称</strong>：基金简称</li>
                        <li><strong>溢价/折价</strong>：基于场外净值计算的折溢价率</li>
                        <li><strong>交易额(万)</strong>：当日场内成交额（万元）</li>
                        <li><strong>限购(元)</strong>：单日申购限额，空表示无限额</li>
                        <li><strong>净值日期</strong>：场外净值的对应日期</li>
                        <li><strong>预估收益</strong>：扣除申购/赎回费后的预估收益率</li>
                      </ul>
                    </div>
                  </div>
                </div>

                {/* 筛选逻辑说明 */}
                <div className="arb-notes">
                  <h3>当前筛选逻辑</h3>
                  <div className="arb-notes-grid">
                    <div className="arb-note-item">
                      <span className="arb-note-label">溢价率阈值</span>
                      <span className="arb-note-value">≥ 2%</span>
                      <span className="arb-note-desc">低于此阈值的套利空间不足以覆盖交易成本和时间风险</span>
                    </div>
                    <div className="arb-note-item">
                      <span className="arb-note-label">最低成交额</span>
                      <span className="arb-note-value">&gt; 1000万</span>
                      <span className="arb-note-desc">确保流动性，避免卖不出去或冲击成本过大</span>
                    </div>
                    <div className="arb-note-item">
                      <span className="arb-note-label">基金类型</span>
                      <span className="arb-note-value">LOF基金</span>
                      <span className="arb-note-desc">仅显示可场内外转托管的LOF基金</span>
                    </div>
                    <div className="arb-note-item">
                      <span className="arb-note-label">数据来源</span>
                      <span className="arb-note-value">集思录</span>
                      <span className="arb-note-desc">登录后可获取完整数据，未登录数据可能不全</span>
                    </div>
                  </div>
                </div>

                {/* 注意事项 */}
                <div className="arb-notes">
                  <h3>基金折溢价套利注意事项</h3>
                  <div className="arb-notes-content">
                    <div className="arb-risk-section">
                      <h4>时间风险（核心风险）</h4>
                      <ul>
                        <li><strong>溢价套利</strong>：场外申购 → T+1确认份额 → T+2转托管到账 → 场内卖出，全程约3-4个工作日</li>
                        <li><strong>折价套利</strong>：场内买入 → T+1转托管到场外 → T+2赎回，全程约2-3个工作日</li>
                        <li>等待期间基金净值可能大幅波动，溢价/折价可能消失甚至反转</li>
                      </ul>
                    </div>
                    <div className="arb-risk-section">
                      <h4>流动性风险</h4>
                      <ul>
                        <li>场内成交量过低会导致无法按预期价格卖出，实际成交价可能大幅低于预期</li>
                        <li>大额套利需考虑冲击成本，单笔交易不宜超过日均成交额的5%-10%</li>
                      </ul>
                    </div>
                    <div className="arb-risk-section">
                      <h4>交易成本</h4>
                      <ul>
                        <li>申购费：一般0.12%-0.15%（部分渠道有折扣）</li>
                        <li>赎回费：持有时间越短费率越高，7天内赎回可能高达1.5%</li>
                        <li>交易佣金：约0.03%-0.05%</li>
                        <li>套利净收益 = 溢价率 - 申购费 - 卖出佣金 - 冲击成本</li>
                      </ul>
                    </div>
                    <div className="arb-risk-section">
                      <h4>其他风险</h4>
                      <ul>
                        <li><strong>限购风险</strong>：基金可能暂停申购或设置单日限额，影响套利规模</li>
                        <li><strong>溢价收窄</strong>：套利资金集中涌入会迅速压缩溢价空间</li>
                        <li><strong>停牌/涨跌停</strong>：成分股异常会影响基金净值和套利效果</li>
                        <li><strong>规模风险</strong>：小规模基金流动性差，虽易产生折溢价但难以变现</li>
                      </ul>
                    </div>
                    <div className="arb-risk-section">
                      <h4>实操建议</h4>
                      <ul>
                        <li>优先选择日均成交额大于3000万的品种</li>
                        <li>使用券商App一键转托管功能可节省时间</li>
                        <li>关注基金是否处于暂停申购状态</li>
                        <li>溢价率建议≥5%再操作，留足安全边际</li>
                        <li>避免在市场剧烈波动期套利</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </>
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
