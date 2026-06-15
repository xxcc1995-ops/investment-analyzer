/**
 * 空投机会扫描器 - API客户端
 * 覆盖：DefiLlama + 交易所活动 + 链上打新 + 测试网 + Twitter大V + RSS聚合(12源) + 机会评分
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

  /** 测试网/激励测试网项目追踪 */
  getTestnetProjects: () => axios.get(`${BASE}/testnet-projects`),

  /** DeFiLlama 已公布空投 + 高概率空投协议 */
  getDefiLlamaAirdrops: () => axios.get(`${BASE}/defillama-airdrops`),

  /** Twitter空投大V推文监控 */
  getTwitterKolFeed: () => axios.get(`${BASE}/twitter-kol`),

  /** 空投资讯聚合（12源RSS） */
  getNews: () => axios.get(`${BASE}/news`),

  /** 综合机会评分 */
  getOpportunityScores: () => axios.get(`${BASE}/opportunity-scores`),
}
