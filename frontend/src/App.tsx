import { useState, useEffect, useCallback, useRef, useMemo, lazy, Suspense } from 'react'
import AppShell from './components/AppShell'
import StockAnalysis from './pages/StockAnalysis'
import { bondApi, stockApi } from './services/api'

// ============ 懒加载页面组件 ============

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
const CryptoMasterPage = lazy(() => import('./pages/CryptoMasterPage'))
import RationalityGate from './components/RationalityGate'

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

type MainView =
  | 'stock' | 'fundArb' | 'option' | 'cb' | 'hki' | 'indexVal'
  | 'dividend' | 'cigarButt' | 'valueInvesting' | 'reit' | 'macro' | 'futures'
  | 'jcScreener' | 'polymarket' | 'exportChampions'
  | 'futuOptionChain' | 'gridTrading' | 'nationalTeam' | 'rightSide'
  | 'decisionGuard' | 'tTrading' | 'backtestReport'
  | 'drawdownControl' | 'masterStrategy' | 'tractorTrading' | 'dailyInfo' | 'mobileSettings'
  | 'cbBacktest' | 'portfolio' | 'cryptoMaster'

// ============ 路由映射 ============

const routeMap: Record<string, React.LazyExoticComponent<any>> = {
  dailyInfo: DailyInfo,
  hki: HKIpoPage,
  indexVal: IndexValuation,

  dividend: DividendScreener,
  cigarButt: CigarButtScreener,
  valueInvesting: ValueInvesting,
  reit: REITScreener,

  macro: MacroData,
  futures: FuturesInsight,
  jcScreener: JCScreener,
  tTrading: TTrading,
  polymarket: PolymarketPage,
  exportChampions: ExportChampions,
  backtestReport: BacktestReport,
  futuOptionChain: FutuOptionChain,
  drawdownControl: DrawdownControl,
  gridTrading: GridTrading,

  nationalTeam: NationalTeamMonitor,
  rightSide: RightSideTrading,
  fundArb: FundArbitragePage,
  decisionGuard: DecisionGuard,
  option: OptionCalculator,
  cb: ConvertibleBondPage,
  masterStrategy: MasterStrategyPage,
  tractorTrading: TractorPage,
  mobileSettings: MobileSettings,
  cbBacktest: CBBacktestPage,
  portfolio: Portfolio,
  cryptoMaster: CryptoMasterPage,
}

// ============ 主组件 ============

function App() {
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState<SearchItem[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const searchBoxRef = useRef<HTMLDivElement>(null)
  const [activeStockCode, setActiveStockCode] = useState<string | null>(null)
  const [mainView, setMainView] = useState<MainView>('dailyInfo')
  const [bondYields, setBondYields] = useState<BondYields | null>(null)
  const [bondLoading, setBondLoading] = useState(false)

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

  // 选择股票
  const handleSelectStock = useCallback((code: string) => {
    setActiveStockCode(code)
    setMainView('stock')
    setShowSearch(false)
    setSearchKeyword('')
  }, [])

  // 导航
  const handleNavigate = useCallback((key: string) => {
    if (key === 'stock' && !activeStockCode) {
      // 如果没有选中股票，保持当前视图
      return
    }
    setMainView(key as MainView)
  }, [activeStockCode])

  // 全局导航函数，供子页面调用
  useEffect(() => {
    (window as any).__navigateTo = (key: string) => handleNavigate(key)
    return () => { delete (window as any).__navigateTo }
  }, [handleNavigate])

  // 渲染当前页面 - 用useMemo避免每次App渲染时重建JSX树
  const currentView = useMemo(() => {
    if (mainView === 'stock') {
      if (!activeStockCode) {
        return (
          <div className="empty-state">
            <div className="icon">📊</div>
            <div className="text">新源的Invest工具</div>
            <div className="sub-text">输入股票代码开始分析 | 支持A股/港股</div>
          </div>
        )
      }
      return <StockAnalysis code={activeStockCode} />
    }

    const LazyComponent = routeMap[mainView]
    if (LazyComponent) return <LazyComponent />

    return (
      <div className="empty-state">
        <div className="icon">📊</div>
        <div className="text">新源的Invest工具</div>
        <div className="sub-text">输入股票代码开始分析 | 支持A股/港股</div>
      </div>
    )
  }, [mainView, activeStockCode])

  // Gate callbacks - stable references
  const handleGatePass = useCallback(() => {
    sessionStorage.setItem('rationality_gate_passed', '1')
    setGateDismissed(true)
  }, [])

  const handleGateFullCheck = useCallback(() => {
    sessionStorage.setItem('rationality_gate_passed', '1')
    setGateDismissed(true)
    setMainView('decisionGuard')
  }, [])

  return (
    <>
      {showGate && !gateDismissed && (
        <RationalityGate
          onPass={handleGatePass}
          onSkip={handleGatePass}
          onFullCheck={handleGateFullCheck}
        />
      )}

      <AppShell
        activeKey={mainView}
        onNavigate={handleNavigate}
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
        <Suspense fallback={<div className="loading"><div className="spinner"></div>加载中...</div>}>
          {currentView}
        </Suspense>
      </AppShell>
    </>
  )
}

export default App
