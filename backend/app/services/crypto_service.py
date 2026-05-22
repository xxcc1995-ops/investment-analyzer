"""
币圈信息服务 - 汇总高质量信息源
"""
from typing import List, Dict


class CryptoInfoService:
    """币圈信息源聚合服务"""

    def get_all_sources(self) -> Dict[str, List[Dict]]:
        """获取所有信息源，按类别分组"""
        return {
            "news": self._news_sources(),
            "research": self._research_sources(),
            "onchain": self._onchain_sources(),
            "social": self._social_sources(),
            "education": self._education_sources(),
            "tools": self._tool_sources(),
        }

    def _news_sources(self) -> List[Dict]:
        return [
            {"name": "CoinDesk", "url": "https://www.coindesk.com", "desc": "最权威的加密货币新闻媒体，报道全面及时", "lang": "EN", "hot": True},
            {"name": "The Block", "url": "https://www.theblock.co", "desc": "深度行业研究+新闻，机构投资者首选", "lang": "EN", "hot": True},
            {"name": "CoinTelegraph", "url": "https://www.cointelegraph.com", "desc": "覆盖全球加密新闻，漫画风格配图", "lang": "EN", "hot": False},
            {"name": "Decrypt", "url": "https://decrypt.co", "desc": "Web3和加密文化报道，可读性强", "lang": "EN", "hot": False},
            {"name": "BlockBeats 律动", "url": "https://www.theblockbeats.info", "desc": "中文加密媒体，快讯速度快，社区活跃", "lang": "CN", "hot": True},
            {"name": "Odaily 星球日报", "url": "https://www.odaily.news", "desc": "中文Web3媒体，深度文章+快讯", "lang": "CN", "hot": True},
            {"name": "PANews", "url": "https://www.panewslab.com", "desc": "中文区块链新闻，数据报告质量高", "lang": "CN", "hot": False},
            {"name": "Foresight News", "url": "https://www.foresightnews.pro", "desc": "中文Web3资讯，项目研报较多", "lang": "CN", "hot": False},
            {"name": "ChainCatcher", "url": "https://www.chaincatcher.com", "desc": "中文Web3新闻，侧重行业分析", "lang": "CN", "hot": False},
        ]

    def _research_sources(self) -> List[Dict]:
        return [
            {"name": "Messari", "url": "https://messari.io", "desc": "专业加密研究报告，项目基本面分析权威", "lang": "EN", "hot": True},
            {"name": "Delphi Digital", "url": "https://www.delphidigital.io", "desc": "顶级加密研究机构，报告深度极高", "lang": "EN", "hot": True},
            {"name": "Glassnode", "url": "https://glassnode.com", "desc": "链上数据分析龙头，链上指标最全", "lang": "EN", "hot": True},
            {"name": "Nansen", "url": "https://www.nansen.ai", "desc": "链上钱包标签分析，追踪聪明钱动向", "lang": "EN", "hot": True},
            {"name": "Dune Analytics", "url": "https://dune.com", "desc": "链上数据可视化平台，社区Dashboard丰富", "lang": "EN", "hot": True},
            {"name": "Token Terminal", "url": "https://tokenterminal.com", "desc": "协议收入/P/E等财务指标，像看股票一样看DeFi", "lang": "EN", "hot": False},
            {"name": "CryptoQuant", "url": "https://cryptoquant.com", "desc": "链上数据+交易所流入流出分析", "lang": "EN", "hot": False},
            {"name": "DefiLlama", "url": "https://defillama.com", "desc": "DeFi TVL数据最全，免费开源", "lang": "EN", "hot": True},
            {"name": "Artemis", "url": "https://artemis.xyz", "desc": "多链活跃地址/交易量对比分析", "lang": "EN", "hot": False},
        ]

    def _onchain_sources(self) -> List[Dict]:
        return [
            {"name": "Etherscan", "url": "https://etherscan.io", "desc": "以太坊区块浏览器，查交易/合约必备", "lang": "EN", "hot": True},
            {"name": "DeBank", "url": "https://debank.com", "desc": "多链钱包资产追踪，查看大户持仓", "lang": "CN", "hot": True},
            {"name": "Arkham", "url": "https://platform.arkhamintelligence.com", "desc": "链上实体标签追踪，机构级分析", "lang": "EN", "hot": True},
            {"name": "Bubblemaps", "url": "https://bubblemaps.io", "desc": "代币持仓分布可视化，识别集中持仓风险", "lang": "EN", "hot": False},
            {"name": "DEX Screener", "url": "https://dexscreener.com", "desc": "DEX实时行情，新币发现利器", "lang": "EN", "hot": True},
            {"name": "DEXTools", "url": "https://www.dextools.io", "desc": "DEX交易数据+代币评分", "lang": "EN", "hot": False},
            {"name": "BscScan", "url": "https://bscscan.com", "desc": "BSC区块浏览器", "lang": "EN", "hot": False},
            {"name": "Solscan", "url": "https://solscan.io", "desc": "Solana区块浏览器", "lang": "EN", "hot": False},
        ]

    def _social_sources(self) -> List[Dict]:
        return [
            {"name": "Crypto Twitter (X)", "url": "https://x.com", "desc": "加密圈最活跃的社交平台，KOL观点首发地", "lang": "EN", "hot": True,
             "tips": "关注: @VitalikButerin @CryptoHayes @Arthur_0x @blknoiz01 @aaborndefund"},
            {"name": "Reddit r/CryptoCurrency", "url": "https://www.reddit.com/r/CryptoCurrency", "desc": "最大加密社区，散户情绪风向标", "lang": "EN", "hot": False},
            {"name": "Reddit r/ethereum", "url": "https://www.reddit.com/r/ethereum", "desc": "以太坊技术讨论社区", "lang": "EN", "hot": False},
            {"name": "Bitcointalk", "url": "https://bitcointalk.org", "desc": "最老牌的比特币论坛，早期项目讨论", "lang": "EN", "hot": False},
            {"name": "Discord (各项目官方)", "url": "", "desc": "项目官方社区，获取一手信息和治理讨论", "lang": "EN", "hot": False,
             "tips": "加入投资组合中项目的Discord，关注Announcement频道"},
            {"name": "Telegram 研报频道", "url": "", "desc": "多个高质量中文研报频道", "lang": "CN", "hot": False,
             "tips": "搜索: 吴说区块链、币圈早知道、Web3CN等频道"},
        ]

    def _education_sources(self) -> List[Dict]:
        return [
            {"name": "CoinGecko Learn", "url": "https://www.coingecko.com/learn", "desc": "加密货币入门百科，适合新手", "lang": "EN", "hot": False},
            {"name": "Binance Academy", "url": "https://academy.binance.com", "desc": "币安学院，中英文区块链教程", "lang": "CN/EN", "hot": False},
            {"name": "Ethereum.org", "url": "https://ethereum.org/en/learn", "desc": "以太坊官方学习资源", "lang": "EN", "hot": False},
            {"name": "Bankless", "url": "https://www.bankless.com", "desc": "Web3教育+播客，深度访谈项目创始人", "lang": "EN", "hot": True},
            {"name": "The DeFi Edge", "url": "https://thedefiedge.com", "desc": "DeFi策略Newsletter，通俗易懂", "lang": "EN", "hot": False},
            {"name": "白话区块链", "url": "https://hellobtc.com", "desc": "中文区块链科普，适合入门", "lang": "CN", "hot": False},
        ]

    def _tool_sources(self) -> List[Dict]:
        return [
            {"name": "CoinGecko", "url": "https://www.coingecko.com", "desc": "加密货币行情数据聚合，免费API", "lang": "EN", "hot": True},
            {"name": "CoinMarketCap", "url": "https://coinmarketcap.com", "desc": "币价数据老牌网站，币种信息全", "lang": "EN", "hot": True},
            {"name": "TradingView", "url": "https://www.tradingview.com", "desc": "专业图表分析工具，支持所有主流交易所", "lang": "EN", "hot": True},
            {"name": "DeFiLlama", "url": "https://defillama.com", "desc": "DeFi数据聚合，TVL/收益/空投追踪", "lang": "EN", "hot": True},
            {"name": "L2Beat", "url": "https://l2beat.com", "desc": "Layer2数据对比，TVL+风险评估", "lang": "EN", "hot": False},
            {"name": "CoinGlass", "url": "https://www.coinglass.com", "desc": "合约数据（爆仓/持仓/资金费率）", "lang": "EN", "hot": True},
            {"name": "Whale Alert", "url": "https://whale-alert.io", "desc": "大额转账监控，追踪巨鲸动向", "lang": "EN", "hot": False},
            {"name": "Rekt News", "url": "https://rekt.news", "desc": "DeFi黑客事件记录，了解安全风险", "lang": "EN", "hot": False},
        ]

    def get_info_tips(self) -> List[Dict]:
        """获取信息筛选方法论"""
        return [
            {"title": "判断信息源质量", "items": [
                "有明确的作者/团队背景，非匿名",
                "信息来源可追溯（链上数据、官方公告）",
                "有历史记录可验证（研报准确率）",
                "不收费荐币、不喊单、不推垃圾币",
                "更新频率稳定，非三天打鱼两天晒网",
            ]},
            {"title": "信息筛选原则", "items": [
                "一手信息 > 二手解读（官方公告 > 媒体解读 > KOL观点）",
                "数据 > 观点（链上数据 > 分析师判断）",
                "多源交叉验证（单一来源不可信）",
                "区分事实和观点（'ETH升级完成'是事实，'ETH会涨'是观点）",
                "警惕FUD和FOMO情绪（恐慌和狂热时信息失真最大）",
            ]},
            {"title": "常见信息陷阱", "items": [
                "付费软文：项目方花钱买的'研报'和'评测'",
                "KOL喊单：收了钱推荐的项目，高位接盘",
                "虚假数据：刷量、假TVL、假用户数",
                "幸存者偏差：只看到赚钱的案例，忽视大量亏损",
                "回测陷阱：历史表现好不代表未来能复现",
            ]},
        ]


crypto_info_service = CryptoInfoService()
