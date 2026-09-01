// ============ Re-export everything from all modules ============

// Client (default export)
export { default as api } from './client'
export { default } from './client'

// Types
export * from './types'

// API objects
export { stockApi, bondApi } from './stocks'
export { fundApi, fundEstApi } from './funds'
export { cbApi, cbBacktestApi, cbNearMatureApi } from './cb'
export type { CBStrategy, CBStrategyRisk, NearMatureBond, NearMatureResponse } from './cb'
export { macroApi, indexValuationApi } from './macro'
export type { MacroIndicator, MacroOverview, ChinaMacroData, UsMacroData } from './macro'
export { futuresApi } from './futures'
export type { FuturesCommodityItem } from './futures'
export { screenerApi } from './screeners'
export type { ScreenerResult } from './screeners'
export { tradingApi, polymarketApi, decisionApi } from './trading'
export { nationalTeamApi, xueqiuApi, cryptoApi } from './nationalTeam'
export { quantdingerApi } from './quantdinger'
export type { AIAnalysisResult, AnalysisHistory, PerformanceStats } from './quantdinger'
export { portfolioApi } from './portfolio'
export { cryptoMasterApi } from './cryptoMaster'
export { airdropScannerApi } from './airdropScanner'
export { relativeValuationApi } from './relativeValuation'
export type { SectorInfo, StockMetric, CompareResult } from './relativeValuation'
export { indexEarningsApi } from './indexEarnings'
export type { IndexEarningsMeta, IndexEarningsData, IndexEarningsRow, EpsCycle } from './indexEarnings'
