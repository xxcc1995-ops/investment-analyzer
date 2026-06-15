import api from './client'

const BASE = '/crypto-master'
const CRAWLER_BASE = '/crypto-crawler'

export const cryptoMasterApi = {
  // 市场数据
  getMarketOverview: () => api.get(`${BASE}/market-overview`),
  getTopCoins: (limit = 50) => api.get(`${BASE}/top-coins`, { params: { limit } }),
  getTrending: () => api.get(`${BASE}/trending`),
  getStablecoins: () => api.get(`${BASE}/stablecoins`),
  getBtcDominance: () => api.get(`${BASE}/btc-dominance-history`),

  // 链上数据
  getDefiTvl: () => api.get(`${BASE}/defi-tvl`),
  getChainComparison: () => api.get(`${BASE}/chain-comparison`),

  // 知识体系
  getKnowledge: (level: string) => api.get(`${BASE}/knowledge/${level}`),
  getGlossary: () => api.get(`${BASE}/glossary`),
  getLearningPath: () => api.get(`${BASE}/learning-path`),

  // 策略工具
  getStrategies: () => api.get(`${BASE}/strategies`),
  runDcaSimulation: (data: any) => api.post(`${BASE}/dca-simulator`, data),
  calculatePosition: (data: any) => api.post(`${BASE}/position-calculator`, data),

  // 风险管理
  getRiskChecklist: () => api.get(`${BASE}/risk-checklist`),
  getCommonMistakes: () => api.get(`${BASE}/common-mistakes`),
  getSecurityGuide: () => api.get(`${BASE}/security-guide`),

  // DeFi指南
  getDefiGuide: () => api.get(`${BASE}/defi-guide`),
  getAirdropGuide: () => api.get(`${BASE}/airdrop-guide`),
  getPaymentTools: () => api.get(`${BASE}/payment-tools`),

  // 实战
  getTradingChecklist: () => api.get(`${BASE}/trading-checklist`),
  getMasterWisdom: () => api.get(`${BASE}/master-wisdom`),

  // 情报搜集器
  getIntelLatest: (params?: { category?: string; impact?: string; limit?: number }) =>
    api.get(`${CRAWLER_BASE}/latest`, { params }),
  getIntelHighImpact: (limit = 20) =>
    api.get(`${CRAWLER_BASE}/high-impact`, { params: { limit } }),
  getIntelTrending: () => api.get(`${CRAWLER_BASE}/trending`),
  getIntelSources: () => api.get(`${CRAWLER_BASE}/sources`),
  triggerCrawl: () => api.post(`${CRAWLER_BASE}/crawl`),
}
