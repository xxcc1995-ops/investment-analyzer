/**
 * 空投机会扫描器 - API客户端
 */
import axios from 'axios'

const BASE = '/api/airdrop-scanner'

export const airdropScannerApi = {
  /** DefiLlama 未发币高TVL协议扫描 */
  getUntokenizedProtocols: () => axios.get(`${BASE}/untokenized-protocols`),

  /** 交易所活动汇总 */
  getExchangeActivities: () => axios.get(`${BASE}/exchange-activities`),

  /** 链上打新/IDO项目追踪 */
  getLaunchpadProjects: () => axios.get(`${BASE}/launchpad-projects`),

  /** 空投资讯聚合 */
  getNews: () => axios.get(`${BASE}/news`),

  /** 综合机会评分 */
  getOpportunityScores: () => axios.get(`${BASE}/opportunity-scores`),
}
