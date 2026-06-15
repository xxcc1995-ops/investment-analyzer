import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react'
import { Routes, Route, useNavigate, useParams } from 'react-router-dom'
import AppShell from './components/AppShell'
import ErrorBoundary from './components/ErrorBoundary'
import { bondApi, stockApi } from './services/api'

// ============ 懒加载页面组件 ============

const StockAnalysis = lazy(() => import('./pages/StockAnalysis'))
const RationalityGate = lazy(() => import('./components/RationalityGate'))

const HKIpoPage = lazy(() => import('./pages/HKIpoPage'))
const IndexValuation = lazy(() => import('./pages/IndexValuation'))
const DividendScreener = lazy(() => import('./pages/DividendScreener'))
const CigarButtScreener = lazy(() => import('./pages/CigarButtScreener'))
const ValueInvesting = lazy(() => import('./pages/ValueInvesting'))
const REITScreener = lazy(() => import('./pages/REITScreener'))
const MacroData = lazy(() => import('./pages/MacroData'))
const FuturesInsight = lazy(() => import('./pages/FuturesInsight'))
const JCScreener = lazy(() => import('./pages/JCScreener'))
const PolymarketPage = lazy(() => import('./pages/PolymarketPage'))
const ExportChampions = lazy(() => import('./pages/ExportChampions'))
const GridTrading = lazy(() => import('./pages/GridTrading'))
const TTrading = lazy(() => import('./pages/TTrading'))
const NationalTeamMonitor = lazy(() => import('./pages/NationalTeamMonitor'))
const RightSideTrading = lazy(() => import('./pages/RightSideTrading'))
const FundArbitragePage = lazy(() => import('./pages/FundArbitragePage'))
const DecisionGuard = lazy(() => import('./pages/DecisionGuard'))
const BacktestReport = lazy(() => import('./pages/BacktestReport'))
const OptionCalculator = lazy(() => import('./pages/OptionCalculator'))
const ConvertibleBondPage = lazy(() => import('./pages/ConvertibleBondPage'))
const MasterStrategyPage = lazy(() => import('./pages/MasterStrategyPage'))
const FutuOptionChain = lazy(() => import('./pages/FutuOptionChain'))
const DrawdownControl = lazy(() => import('./pages/DrawdownControl'))
const DailyInfo = lazy(() => import('./pages/DailyInfo'))
const TractorPage = lazy(() => import('./pages/TractorPage'))
const MobileSettings = lazy(() => import('./pages/MobileSettings'))
const CBBacktestPage = lazy(() => import('./pages/CBBacktestPage'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const StrategyValidation = lazy(() => import('./pages/StrategyValidation'))
const BankValuation = lazy(() => import('./pages/BankValuation'))
const CryptoMasterPage = lazy(() => import('./pages/CryptoMasterPage'))
const QuantBacktest = lazy(() => import('./pages/QuantBacktest'))
const PrefrontalTraining = lazy(() => import('./pages/PrefrontalTraining'))
const AirdropScannerPage = lazy(() => import('./pages/AirdropScannerPage'))
const WechatDigest = lazy(() => import('./pages/WechatDigest'))

// ============ 类型定义 ============

interface BondYield {
  yield: number; change: number; pe: number; stock_bond_ratio: number
}

interface BondYields {
  cn: BondYield; us: BondYield
}

interface SearchItem {
  code: string; name: string; market?: string
}

// ============ 股票页面包装组件 ============

function StockPageWrapper() {
  const { code } = useParams<{ code: string }>()
  if (!code) {
    return (
      <div className="empty-state">
        <div className="icon">📊</div>
        <div className="text">新源的Invest工具</div>
        <div className="sub-text">输入股票代码开始分析 | 支持A股/港股</div>
      </div>
    )
  }
  return <StockAnalysis code={code} />
}

// ============ 主组件 ============

function App() {
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState<SearchItem[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const searchBoxRef = useRef<HTMLDivElement>(null)
  const [bondYields, setBondYields] = useState<BondYields | null>(null)
  const [bondLoading, setBondLoading] = useState(false)
  const navigate = useNavigate()

  // 理性门卫
  const [showGate, setShowGate] = useState(() => !sessionStorage.getItem('rationality_gate_passed'))
  const [gateDismissed, setGateDismissed] = useState(false)

  // 加载国债收益率
  const loadBondYields = useCallback(async () => {
    setBondLoading(true)
    try {
      const res = await bondApi.getYields()
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
    if (!keyword.trim()) { setSearchResults([]); setSearchLoading(false); return }
    setSearchLoading(true)
    try {
      const res = await stockApi.search(keyword)
      setSearchResults(res.data.results || [])
    } catch { setSearchResults([]) }
    finally { setSearchLoading(false) }
  }, [])

  // 防抖搜索
  useEffect(() => {
    if (!searchKeyword) { setSearchResults([]); setSearchLoading(false); return }
    setSearchLoading(true)
    const timer = setTimeout(() => handleSearch(searchKeyword), 300)
    return () => clearTimeout(timer)
  }, [searchKeyword, handleSearch])

  // 点击外部关闭搜索
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) setShowSearch(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 选择股票 - 导航到 /stock/:code
  const handleSelectStock = useCallback((code: string) => {
    navigate(`/stock/${code}`)
    setShowSearch(false)
    setSearchKeyword('')
  }, [navigate])

  // 全局导航函数，供子页面调用（兼容旧的 window.__navigateTo）
  useEffect(() => {
    (window as any).__navigateTo = (path: string) => navigate(path)
    return () => { delete (window as any).__navigateTo }
  }, [navigate])

  // Gate callbacks
  const handleGatePass = useCallback(() => {
    sessionStorage.setItem('rationality_gate_passed', '1')
    setGateDismissed(true)
  }, [])

  const handleGateFullCheck = useCallback(() => {
    sessionStorage.setItem('rationality_gate_passed', '1')
    setGateDismissed(true)
    navigate('/decision-guard')
  }, [navigate])

  return (
    <>
      {showGate && !gateDismissed && (
        <ErrorBoundary>
          <Suspense fallback={null}>
            <RationalityGate
              onPass={handleGatePass}
              onSkip={handleGatePass}
              onFullCheck={handleGateFullCheck}
            />
          </Suspense>
        </ErrorBoundary>
      )}

      <AppShell
        searchKeyword={searchKeyword}
        onSearchChange={setSearchKeyword}
        searchResults={searchResults}
        showSearch={showSearch}
        onShowSearch={setShowSearch}
        searchLoading={searchLoading}
        onSelectStock={handleSelectStock}
        searchBoxRef={searchBoxRef}
        bondYields={bondYields}
        bondLoading={bondLoading}
        onRefreshBonds={loadBondYields}
      >
        <ErrorBoundary>
          <Suspense fallback={<div className="loading"><div className="spinner"></div>加载中...</div>}>
            <Routes>
              <Route path="/" element={<DailyInfo />} />
              <Route path="/stock/:code?" element={<StockPageWrapper />} />
              <Route path="/index-valuation" element={<IndexValuation />} />
              <Route path="/macro" element={<MacroData />} />
              <Route path="/futures" element={<FuturesInsight />} />
              <Route path="/dividend" element={<DividendScreener />} />
              <Route path="/cigar-butt" element={<CigarButtScreener />} />
              <Route path="/value-investing" element={<ValueInvesting />} />
              <Route path="/reit" element={<REITScreener />} />
              <Route path="/export-champions" element={<ExportChampions />} />
              <Route path="/jc-screener" element={<JCScreener />} />
              <Route path="/t-trading" element={<TTrading />} />
              <Route path="/grid-trading" element={<GridTrading />} />
              <Route path="/right-side" element={<RightSideTrading />} />
              <Route path="/futu-options" element={<FutuOptionChain />} />
              <Route path="/option-calculator" element={<OptionCalculator />} />
              <Route path="/backtest" element={<BacktestReport />} />
              <Route path="/quant-backtest" element={<QuantBacktest />} />
              <Route path="/drawdown" element={<DrawdownControl />} />
              <Route path="/fund-arb" element={<FundArbitragePage />} />
              <Route path="/tractor" element={<TractorPage />} />
              <Route path="/cb" element={<ConvertibleBondPage />} />
              <Route path="/cb-backtest" element={<CBBacktestPage />} />
              <Route path="/master-strategy" element={<MasterStrategyPage />} />
              <Route path="/polymarket" element={<PolymarketPage />} />
              <Route path="/hki" element={<HKIpoPage />} />
              <Route path="/crypto" element={<CryptoMasterPage />} />
              <Route path="/airdrop-scanner" element={<AirdropScannerPage />} />
              <Route path="/wechat-digest" element={<WechatDigest />} />
              <Route path="/national-team" element={<NationalTeamMonitor />} />
              <Route path="/decision-guard" element={<DecisionGuard />} />
              <Route path="/prefrontal-training" element={<PrefrontalTraining />} />
              <Route path="/strategy-validation" element={<StrategyValidation />} />
              <Route path="/bank-valuation" element={<BankValuation />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/settings" element={<MobileSettings />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </AppShell>
    </>
  )
}

export default App
