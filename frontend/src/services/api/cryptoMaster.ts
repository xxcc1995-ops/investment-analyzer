import axios from 'axios'

const BASE = '/api/crypto-master'

export const cryptoMasterApi = {
  // 市场数据
  getMarketOverview: () => axios.get(`${BASE}/market-overview`),
  getTopCoins: (limit = 50) => axios.get(`${BASE}/top-coins`, { params: { limit } }),
  getTrending: () => axios.get(`${BASE}/trending`),
  getStablecoins: () => axios.get(`${BASE}/stablecoins`),
  getBtcDominance: () => axios.get(`${BASE}/btc-dominance-history`),

  // 链上数据
  getDefiTvl: () => axios.get(`${BASE}/defi-tvl`),
  getChainComparison: () => axios.get(`${BASE}/chain-comparison`),

  // 知识体系
  getKnowledge: (level: string) => axios.get(`${BASE}/knowledge/${level}`),
  getGlossary: () => axios.get(`${BASE}/glossary`),
  getLearningPath: () => axios.get(`${BASE}/learning-path`),

  // 策略工具
  getStrategies: () => axios.get(`${BASE}/strategies`),
  runDcaSimulation: (data: any) => axios.post(`${BASE}/dca-simulator`, data),
  calculatePosition: (data: any) => axios.post(`${BASE}/position-calculator`, data),

  // 风险管理
  getRiskChecklist: () => axios.get(`${BASE}/risk-checklist`),
  getCommonMistakes: () => axios.get(`${BASE}/common-mistakes`),
  getSecurityGuide: () => axios.get(`${BASE}/security-guide`),

  // DeFi指南
  getDefiGuide: () => axios.get(`${BASE}/defi-guide`),
  getAirdropGuide: () => axios.get(`${BASE}/airdrop-guide`),

  // 实战
  getTradingChecklist: () => axios.get(`${BASE}/trading-checklist`),
  getMasterWisdom: () => axios.get(`${BASE}/master-wisdom`),
}
