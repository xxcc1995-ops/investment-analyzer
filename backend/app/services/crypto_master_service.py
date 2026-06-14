"""
币圈大师 - 核心服务层
整合CoinGecko/DefiLlama数据 + 专业知识库
"""
import logging
import os
import time
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# 缓存
_cache: dict = {}
CACHE_TTL = 300  # 5分钟

# 代理配置（与overseas_news_service一致）
PROXY = os.getenv("POLYMARKET_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
_PROXIES = {"http": PROXY, "https": PROXY} if PROXY else None

# 共享Session
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
})
if _PROXIES:
    _session.proxies.update(_PROXIES)


def _get_cached(key: str):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return val
    return None


def _set_cached(key: str, val):
    _cache[key] = (val, time.time())


def _fetch(url: str, params: dict = None, timeout: int = 15):
    """统一HTTP请求"""
    resp = _session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


class CryptoMasterService:

    # ==================================================================
    # 市场数据 (CoinGecko + DefiLlama + Alternative.me)
    # ==================================================================

    def get_market_overview(self) -> dict:
        """加密市场全景"""
        cached = _get_cached("market_overview")
        if cached:
            return cached

        result = {
            "total_market_cap_usd": 0,
            "total_volume_24h": 0,
            "btc_dominance": 0,
            "eth_dominance": 0,
            "active_cryptocurrencies": 0,
            "markets": 0,
            "btc_price": 0,
            "btc_24h_change": 0,
            "eth_price": 0,
            "eth_24h_change": 0,
            "market_cap_change_24h": 0,
            "fear_greed_index": {"value": 50, "label": "N/A", "update_time": ""},
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 恐惧贪婪指数（最可靠，优先获取）
        try:
            fng_data = _fetch("https://api.alternative.me/fng/?limit=1", timeout=8)
            fng = fng_data.get("data", [{}])[0]
            result["fear_greed_index"] = {
                "value": int(fng.get("value", 50)),
                "label": fng.get("value_classification", "Neutral"),
                "update_time": fng.get("timestamp", ""),
            }
        except Exception as e:
            logger.warning(f"恐惧贪婪指数获取失败: {e}")

        # DefiLlama链上数据（可靠，作为主要数据源）
        try:
            chains = _fetch("https://api.llama.fi/v2/chains", timeout=10)
            total_tvl = sum(c.get("tvl", 0) for c in chains)
            # DefiLlama的chains数据包含各链TVL，可估算市场概况
            top_chains = sorted(chains, key=lambda c: c.get("tvl", 0), reverse=True)[:5]
            eth_tvl = next((c.get("tvl", 0) for c in chains if c.get("name") == "Ethereum"), 0)
            result["total_tvl"] = total_tvl
            result["eth_tvl"] = eth_tvl
            result["chain_count"] = len(chains)
            result["top_chains_tvl"] = [{"name": c.get("name"), "tvl": c.get("tvl", 0)} for c in top_chains]
            if total_tvl > 0:
                result["eth_tvl_dominance"] = round(eth_tvl / total_tvl * 100, 2)
        except Exception as e:
            logger.warning(f"DefiLlama chains获取失败: {e}")

        # CoinGecko（可能超时，用短超时）
        try:
            global_data = _fetch("https://api.coingecko.com/api/v3/global", timeout=5)
            data = global_data.get("data", {})
            result.update({
                "total_market_cap_usd": data.get("total_market_cap", {}).get("usd", 0),
                "total_volume_24h": data.get("total_volume", {}).get("usd", 0),
                "btc_dominance": round(data.get("market_cap_percentage", {}).get("btc", 0), 2),
                "eth_dominance": round(data.get("market_cap_percentage", {}).get("eth", 0), 2),
                "active_cryptocurrencies": data.get("active_cryptocurrencies", 0),
                "markets": data.get("markets", 0),
                "market_cap_change_24h": round(data.get("market_cap_change_percentage_24h_usd", 0), 2),
            })
        except Exception as e:
            logger.info(f"CoinGecko global API不可达（需代理）: {e}")

        # BTC/ETH价格（CoinGecko短超时）
        try:
            price_data = _fetch(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin,ethereum", "vs_currencies": "usd", "include_24hr_change": "true"},
                timeout=5,
            )
            result["btc_price"] = price_data.get("bitcoin", {}).get("usd", 0)
            result["btc_24h_change"] = round(price_data.get("bitcoin", {}).get("usd_24h_change", 0) or 0, 2)
            result["eth_price"] = price_data.get("ethereum", {}).get("usd", 0)
            result["eth_24h_change"] = round(price_data.get("ethereum", {}).get("usd_24h_change", 0) or 0, 2)
        except Exception as e:
            logger.info(f"CoinGecko price API不可达（需代理）: {e}")

        _set_cached("market_overview", result)
        return result

    def get_top_coins(self, limit: int = 50) -> dict:
        """Top N加密货币排行"""
        cached = _get_cached(f"top_coins_{limit}")
        if cached:
            return cached

        try:
            coins = _fetch(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": min(limit, 250),
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "1h,24h,7d,30d",
                },
                timeout=6,
            )
            result = {
                "coins": [
                    {
                        "rank": c.get("market_cap_rank"),
                        "id": c.get("id"),
                        "symbol": (c.get("symbol") or "").upper(),
                        "name": c.get("name"),
                        "price": c.get("current_price"),
                        "market_cap": c.get("market_cap"),
                        "volume_24h": c.get("total_volume"),
                        "change_1h": c.get("price_change_percentage_1h_in_currency"),
                        "change_24h": c.get("price_change_percentage_24h_in_currency"),
                        "change_7d": c.get("price_change_percentage_7d_in_currency"),
                        "change_30d": c.get("price_change_percentage_30d_in_currency"),
                        "ath": c.get("ath"),
                        "ath_change_pct": c.get("ath_change_percentage"),
                        "circulating_supply": c.get("circulating_supply"),
                        "max_supply": c.get("max_supply"),
                    }
                    for c in coins
                ],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            _set_cached(f"top_coins_{limit}", result)
            return result
        except Exception as e:
            logger.error(f"获取Top coins失败: {e}")
            return {"coins": [], "error": str(e)}

    def get_trending(self) -> dict:
        """热门币种"""
        cached = _get_cached("trending")
        if cached:
            return cached

        try:
            data = _fetch("https://api.coingecko.com/api/v3/search/trending", timeout=10)
            trending = []
            for item in data.get("coins", []):
                coin = item.get("item", {})
                trending.append({
                    "id": coin.get("id"),
                    "name": coin.get("name"),
                    "symbol": coin.get("symbol"),
                    "market_cap_rank": coin.get("market_cap_rank"),
                    "price_btc": coin.get("price_btc"),
                    "score": coin.get("score"),
                    "thumb": coin.get("thumb"),
                })
            result = {"trending": trending, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
            _set_cached("trending", result)
            return result
        except Exception as e:
            logger.error(f"获取热门币种失败: {e}")
            return {"trending": [], "error": str(e)}

    def get_stablecoin_monitor(self) -> dict:
        """稳定币市值监控"""
        cached = _get_cached("stablecoins")
        if cached:
            return cached

        try:
            data = _fetch("https://stablecoins.llama.fi/stablecoins?includePrices=true", timeout=15)
            stables = []
            for s in data.get("peggedAssets", [])[:15]:
                stables.append({
                    "name": s.get("name"),
                    "symbol": s.get("symbol"),
                    "peg": s.get("pegType"),
                    "price": s.get("price"),
                    "circulating": s.get("circulating", {}).get("peggedUSD", 0),
                    "chains": list(s.get("chainCirculating", {}).keys())[:5],
                })
            stables.sort(key=lambda x: x.get("circulating", 0), reverse=True)
            total = sum(s["circulating"] for s in stables)
            result = {"stablecoins": stables, "total_mcap": total, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
            _set_cached("stablecoins", result)
            return result
        except Exception as e:
            logger.error(f"获取稳定币数据失败: {e}")
            return {"stablecoins": [], "error": str(e)}

    def get_btc_dominance_history(self) -> dict:
        """BTC主导率"""
        try:
            overview = self.get_market_overview()
            return {
                "current_dominance": overview.get("btc_dominance", 0),
                "eth_dominance": overview.get("eth_dominance", 0),
                "interpretation": self._interpret_dominance(overview.get("btc_dominance", 0)),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            return {"error": str(e)}

    def _interpret_dominance(self, btc_dom: float) -> str:
        if btc_dom > 60:
            return "BTC主导率>60%：市场处于避险模式，资金集中于BTC，山寨币表现通常较差。适合持有BTC，谨慎投资山寨币。"
        elif btc_dom > 50:
            return "BTC主导率50-60%：市场相对均衡，BTC仍是核心，但优质山寨币开始有机会。可以关注ETH和头部Layer1。"
        elif btc_dom > 40:
            return "BTC主导率40-50%：山寨季前兆！资金开始从BTC流向山寨币，DeFi/NFT/Meme等板块可能爆发。"
        else:
            return "BTC主导率<40%：山寨季高峰期！投机情绪浓厚，山寨币暴涨暴跌频繁。注意风险管理，不要追高。"

    # ==================================================================
    # 链上数据 (DefiLlama)
    # ==================================================================

    def get_defi_tvl(self) -> dict:
        """DeFi总锁仓量"""
        cached = _get_cached("defi_tvl")
        if cached:
            return cached

        try:
            chains = _fetch("https://api.llama.fi/v2/chains", timeout=15)
            chain_list = []
            for c in chains[:20]:
                chain_list.append({
                    "name": c.get("name"),
                    "tvl": c.get("tvl", 0),
                    "tokenSymbol": c.get("tokenSymbol"),
                })
            total_tvl = sum(c.get("tvl", 0) for c in chains)
            result = {
                "total_tvl": total_tvl,
                "chains": chain_list,
                "chain_count": len(chains),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            _set_cached("defi_tvl", result)
            return result
        except Exception as e:
            logger.error(f"获取DeFi TVL失败: {e}")
            return {"total_tvl": 0, "chains": [], "error": str(e)}

    def get_chain_comparison(self) -> dict:
        """公链对比数据"""
        cached = _get_cached("chain_comparison")
        if cached:
            return cached

        try:
            chains = _fetch("https://api.llama.fi/v2/chains", timeout=15)
            top_chains = []
            for c in chains[:10]:
                top_chains.append({
                    "name": c.get("name"),
                    "tvl": c.get("tvl", 0),
                    "gecko_id": c.get("gecko_id"),
                    "tokenSymbol": c.get("tokenSymbol"),
                })
            result = {"top_chains": top_chains, "total_chains": len(chains), "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
            _set_cached("chain_comparison", result)
            return result
        except Exception as e:
            return {"top_chains": [], "error": str(e)}

    # ==================================================================
    # 知识体系
    # ==================================================================

    def get_knowledge(self, level: str) -> Optional[dict]:
        """按级别获取知识内容"""
        knowledge_base = {
            "beginner": {
                "title": "🔰 入门篇 - 零基础认知",
                "subtitle": "从零开始理解加密货币的本质",
                "sections": [
                    {
                        "title": "1. 什么是区块链？",
                        "content": "区块链是一个去中心化的分布式账本，所有交易记录公开透明、不可篡改。可以把它想象成一个全球共享的Excel表格，每个人都能看到所有记录，但没有人能偷偷修改。",
                        "key_points": ["去中心化：没有银行或政府控制", "透明性：所有交易公开可查", "不可篡改：一旦记录就无法修改", "共识机制：全网节点共同验证"],
                        "analogy": "就像班级记账：不是班长一个人记，而是每个人都记一本账，对账时取多数人的记录为准。",
                    },
                    {
                        "title": "2. 什么是比特币(BTC)？",
                        "content": "比特币是第一个加密货币，由中本聪在2009年创造。总量恒定2100万枚，通过'挖矿'产生。它是数字黄金，主要价值在于稀缺性和去中心化。",
                        "key_points": ["总量2100万枚，永不增发", "每4年减半一次（挖矿奖励减半）", "被称为'数字黄金'，主要用作价值存储", "2024年第四次减半后，每个区块奖励3.125 BTC"],
                        "why_matters": "理解BTC是理解整个加密市场的基础。BTC的涨跌往往决定整个市场的方向。",
                    },
                    {
                        "title": "3. 什么是ETH和智能合约？",
                        "content": "以太坊(ETH)不仅是加密货币，更是一个可编程的区块链平台。智能合约是自动执行的程序代码，是DeFi、NFT、DAO等应用的基础。",
                        "key_points": ["ETH是以太坊的原生代币，用于支付'Gas费'", "智能合约 = 自动执行的'如果...那么...'规则", "ERC-20标准让任何人都能发行代币", "2022年从PoW转向PoS（合并），能耗降低99.95%"],
                        "analogy": "如果BTC是数字黄金，ETH就是数字石油——它驱动着整个去中心化应用生态。",
                    },
                    {
                        "title": "4. 交易所入门",
                        "content": "交易所是买卖加密货币的平台。分为中心化交易所(CEX)和去中心化交易所(DEX)。",
                        "key_points": ["CEX（如Binance、OKX、Coinbase）：像股票交易所，注册即可交易", "DEX（如Uniswap、PancakeSwap）：无需注册，用钱包直接交易", "现货交易 vs 合约交易：现货是买卖实物，合约是押注涨跌", "一定要开启2FA双重验证！"],
                        "warning": "新手建议先用CEX的现货交易，远离合约（杠杆）交易！合约是专业人士的工具。",
                    },
                    {
                        "title": "5. 钱包与私钥",
                        "content": "钱包是管理加密资产的工具。私钥就是你资产的'密码'，谁掌握了私钥谁就掌握了资产。",
                        "key_points": ["热钱包（联网）：MetaMask、Trust Wallet，方便但安全性较低", "冷钱包（离线）：Ledger、Trezor，安全性最高", "助记词（12/24个单词）= 私钥的备份，写在纸上！绝不要截图或存在网络上", "'Not your keys, not your coins'——不在交易所放太多资产"],
                        "warning": "永远不要告诉任何人你的助记词/私钥！这是加密世界的第一铁律。",
                    },
                ],
            },
            "intermediate": {
                "title": "📊 进阶篇 - 看懂市场",
                "subtitle": "掌握市场分析方法和投资逻辑",
                "sections": [
                    {
                        "title": "1. 技术分析基础",
                        "content": "技术分析通过历史价格和成交量预测未来走势。虽然不是万能的，但了解基本形态能帮助你做出更好的决策。",
                        "key_points": ["K线图：开盘价、收盘价、最高价、最低价", "支撑位/阻力位：价格反复测试但难以突破的位置", "移动平均线(MA)：5日/20日/60日/200日均线", "成交量：放量突破比缩量突破更可靠", "RSI指标：>70超买，<30超卖", "MACD：金叉买入信号，死叉卖出信号"],
                        "reality_check": "技术分析不是预测未来，而是评估概率。不要过度依赖单一指标。",
                    },
                    {
                        "title": "2. 链上分析",
                        "content": "链上分析是加密货币独有的优势——所有交易都在链上公开，你可以看到'聪明钱'在做什么。",
                        "key_points": ["交易所净流入/流出：大量流入可能预示抛售，流出可能预示囤币", "巨鲸动向：大额转账往往预示大行情", "活跃地址数：网络使用率的直接指标", "MVRV比率：市场价值/实现价值，>3.5通常过热，<1通常底部", "SOPR：花费产出利润率，>1盈利卖出，<1亏损卖出"],
                        "tools": "推荐工具：Glassnode、CryptoQuant、Dune Analytics、Nansen",
                    },
                    {
                        "title": "3. 基本面分析",
                        "content": "评估一个加密项目的真实价值，不能只看价格。",
                        "key_points": ["团队背景：创始人是否有技术背景和行业经验？", "代币经济学(Tokenomics)：总量、分配、解锁计划、销毁机制", "TVL（总锁仓量）：DeFi协议的真实使用量", "开发者活跃度：GitHub提交频率", "社区治理：是否有去中心化治理？", "竞争对手对比：同赛道项目横向比较"],
                        "red_flags": "团队匿名+代币集中分配+无实际产品+过度营销 = 高概率Rug Pull",
                    },
                    {
                        "title": "4. 周期与情绪",
                        "content": "加密市场有明显的牛熊周期，理解周期是赚钱的关键。",
                        "key_points": ["比特币减半周期：历史上减半后12-18个月通常迎来牛市", "恐惧贪婪指数：极度恐惧时买入，极度贪婪时卖出", "资金费率：合约市场多空比，极端值往往预示反转", "稳定币市值增长 = 新资金入场", "FOMO（害怕错过）是最大的敌人"],
                        "wisdom": "别人贪婪时恐惧，别人恐惧时贪婪。——巴菲特。这句话在加密市场尤其适用。",
                    },
                    {
                        "title": "5. DeFi基础",
                        "content": "去中心化金融(DeFi)是加密世界最核心的应用场景。",
                        "key_points": ["DEX（去中心化交易所）：Uniswap、Curve、dYdX", "借贷协议：Aave、Compound——存币赚利息，抵押借币", "流动性挖矿：提供流动性赚取交易手续费+代币奖励", "质押(Staking)：锁定代币获得网络奖励", "稳定币：USDT/USDC/DAI——加密世界的'现金'"],
                        "warning": "DeFi协议有智能合约风险。存入前检查审计报告和TVL历史。",
                    },
                ],
            },
            "advanced": {
                "title": "🎯 高级篇 - 专业策略",
                "subtitle": "成熟的交易系统和风险管理方法",
                "sections": [
                    {
                        "title": "1. 仓位管理",
                        "content": "仓位管理比选币更重要。再好的标的，仓位不对也白搭。",
                        "key_points": ["凯利公式：f* = (bp - q) / b，计算最优仓位比例", "单笔风险不超过总资金的2%", "金字塔加仓：初始仓位最大，越涨加仓越少", "永远留有现金（至少20-30%），应对黑天鹅", "不要把所有鸡蛋放在一个篮子里"],
                        "formula": "凯利公式：f* = (赔率×胜率 - 败率) / 赔率。实际使用建议取半凯利。",
                    },
                    {
                        "title": "2. 止损与止盈",
                        "content": "有策略的止损止盈是专业交易者和业余玩家的根本区别。",
                        "key_points": ["固定比例止损：亏损达到预设比例（如-8%）无条件止损", "移动止损：价格上涨后止损位也跟着上移", "止盈分批：到达目标位先卖一半，剩下的用移动止损保护", "不要移动止损去承受更大亏损！", "止损是成本，不是失败。每笔交易都要先想好止损位。"],
                        "discipline": "写下来：在每笔交易前写下你的买入理由、止损位、目标位。违背计划就是赌博。",
                    },
                    {
                        "title": "3. 套利策略",
                        "content": "利用市场低效率获取几乎无风险的收益。",
                        "key_points": ["跨交易所套利：同一币种在不同交易所的价差", "期现套利：期货溢价/折价时做多空对冲", "三角套利：利用三种币之间的汇率差", "稳定币脱锚套利：USDT短暂偏离1美元时的操作"],
                        "reality": "套利机会越来越少了，而且需要考虑手续费、滑点和资金转移时间。新手不建议。",
                    },
                    {
                        "title": "4. 叙事交易",
                        "content": "加密市场是叙事驱动的市场。理解叙事周期比看K线更重要。",
                        "key_points": ["每个牛市都有主题叙事：2017 ICO、2021 DeFi/NFT、2024 AI/RWA", "早期发现叙事：关注VC投资方向、开发者趋势、社交媒体热度", "叙事轮动：资金会在不同叙事间流动", "不要爱上叙事，叙事结束要及时离场"],
                        "wisdom": "在加密市场，价格发现先于技术落地。当所有人都知道'下一个大叙事'时，它可能已经接近尾声。",
                    },
                    {
                        "title": "5. 跨周期资产配置",
                        "content": "不同市场阶段需要不同的资产配置策略。",
                        "key_points": ["熊市底部：60% BTC + 30% ETH + 10% 现金", "牛市初期：40% BTC + 30% ETH + 20% 大盘山寨 + 10% 现金", "牛市中期：30% BTC + 20% ETH + 30% 中小盘山寨 + 10% Meme + 10% 现金", "牛市末期：逐步减仓，增加现金和稳定币比例", "绝对不要满仓！留子弹应对意外。"],
                    },
                ],
            },
            "master": {
                "title": "👑 大师篇 - 顶级认知",
                "subtitle": "顶级交易者的思维方式和哲学",
                "sections": [
                    {
                        "title": "1. 认知变现",
                        "content": "在加密市场，你赚的每一分钱都是你认知的变现。你亏的每一分钱都是你认知的缺陷。",
                        "key_points": ["信息不对称是核心优势——深度研究>跟单", "一级市场（链上早期项目）>二级市场（交易所）的收益倍数", "保持学习：白皮书、治理提案、开发者论坛", "建立自己的信息来源网络"],
                        "wisdom": "永远赚不到认知以外的钱。即使凭运气赚到了，也会凭实力亏回去。",
                    },
                    {
                        "title": "2. 反人性操作",
                        "content": "市场在恐惧中见底，在犹豫中上涨，在疯狂中见顶。大师级操作就是反人性操作。",
                        "key_points": ["暴跌时别人恐惧你贪婪——前提是基本面没变", "暴涨时别人贪婪你恐惧——开始分批止盈", "不追涨杀跌，提前设好计划并执行", "孤独感：当所有人都说你是傻子时，你可能走在正确的路上"],
                        "discipline": "真正的高手不是每一笔都赚钱，而是亏的时候亏得少，赚的时候赚得多。",
                    },
                    {
                        "title": "3. 复利思维",
                        "content": "加密市场的暴富神话让人忽视了复利的力量。年化100%的稳定收益，5年就是32倍。",
                        "key_points": ["追求稳定收益，而非一夜暴富", "保护本金是第一要务", "年化50-100%的策略比追求1000倍更现实", "把利润取出一部分锁定收益"],
                        "calculation": "10万本金，年化100%：1年后20万，2年后40万，3年后80万，5年后320万。复利才是真正的魔法。",
                    },
                    {
                        "title": "4. 生存法则",
                        "content": "在加密市场活下来比赚钱更重要。牛市人人是天才，熊市才见真功夫。",
                        "key_points": ["永远不要借钱/贷款炒币", "不要用生活必需的钱投资", "分散存放：交易所+钱包+冷存储", "做好归零准备：投资的钱必须是你能承受全部亏损的", "保持身心健康：不要因为行情影响生活"],
                        "wisdom": "加密市场永远有机会，但前提是你要活到下一个牛市。",
                    },
                    {
                        "title": "5. 建立交易系统",
                        "content": "大师级交易者都有自己的交易系统。系统化操作才能克服情绪干扰。",
                        "key_points": ["写交易日志：记录每笔交易的理由和结果", "定期复盘：每周/每月回顾交易表现", "量化你的策略：不要凭感觉交易", "设定规则并严格执行", "持续优化系统，但不要频繁更换"],
                        "system": "交易系统 = 入场条件 + 出场条件 + 仓位管理 + 风控规则。缺一不可。",
                    },
                ],
            },
        }
        return knowledge_base.get(level)

    # ==================================================================
    # 术语词典
    # ==================================================================

    def get_glossary(self) -> dict:
        """加密货币术语词典"""
        return {
            "categories": [
                {
                    "name": "基础概念",
                    "terms": [
                        {"term": "区块链", "en": "Blockchain", "def": "去中心化的分布式账本技术，所有交易记录公开透明、不可篡改"},
                        {"term": "加密货币", "en": "Cryptocurrency", "def": "基于密码学的数字货币，通过区块链技术实现去中心化"},
                        {"term": "挖矿", "en": "Mining", "def": "通过计算力验证交易并获得区块奖励的过程"},
                        {"term": "共识机制", "en": "Consensus", "def": "网络节点就交易有效性达成一致的规则，如PoW、PoS"},
                        {"term": "Gas费", "en": "Gas Fee", "def": "在区块链上执行交易或智能合约所需支付的手续费"},
                        {"term": "智能合约", "en": "Smart Contract", "def": "部署在区块链上自动执行的程序代码"},
                    ],
                },
                {
                    "name": "交易相关",
                    "terms": [
                        {"term": "现货", "en": "Spot", "def": "直接买卖实际的加密资产，买多少就有多少"},
                        {"term": "合约/期货", "en": "Futures", "def": "押注资产价格涨跌的衍生品，可以加杠杆"},
                        {"term": "杠杆", "en": "Leverage", "def": "用少量保证金撬动更大仓位，放大收益也放大亏损"},
                        {"term": "做多/做空", "en": "Long/Short", "def": "做多=押注价格上涨，做空=押注价格下跌"},
                        {"term": "止盈止损", "en": "TP/SL", "def": "预先设定的卖出价位，止盈锁定利润，止损控制亏损"},
                        {"term": "滑点", "en": "Slippage", "def": "实际成交价格与预期价格的差异，流动性越差滑点越大"},
                        {"term": "挂单/吃单", "en": "Maker/Taker", "def": "挂单=限价单等待成交，吃单=市价单立即成交"},
                    ],
                },
                {
                    "name": "DeFi术语",
                    "terms": [
                        {"term": "TVL", "en": "Total Value Locked", "def": "DeFi协议中的总锁仓量，反映协议的真实使用规模"},
                        {"term": "流动性挖矿", "en": "Yield Farming", "def": "为DeFi协议提供流动性来赚取代币奖励"},
                        {"term": "质押", "en": "Staking", "def": "锁定代币参与网络验证，获得质押奖励"},
                        {"term": "无常损失", "en": "Impermanent Loss", "def": "流动性提供者因代币价格变化而产生的相对损失"},
                        {"term": "AMM", "en": "Automated Market Maker", "def": "自动化做市商，通过算法而非订单簿实现代币交换"},
                        {"term": "闪电贷", "en": "Flash Loan", "def": "无需抵押的借贷，必须在同一区块内借还，用于套利"},
                    ],
                },
                {
                    "name": "链上分析",
                    "terms": [
                        {"term": "巨鲸", "en": "Whale", "def": "持有大量加密货币的地址，其交易动向往往影响市场"},
                        {"term": "HODL", "en": "Hold On for Dear Life", "def": "长期持有不卖的投资策略，源自2013年的拼写错误"},
                        {"term": "销毁", "en": "Burn", "def": "将代币发送到无法访问的地址，减少流通供应量"},
                        {"term": "空投", "en": "Airdrop", "def": "项目方免费分发代币给早期用户或社区成员"},
                        {"term": "Rug Pull", "en": "Rug Pull", "def": "项目方卷款跑路，代币归零。加密世界最大的骗局形式"},
                        {"term": "钻石手", "en": "Diamond Hands", "def": "无论涨跌都坚定持有的投资者"},
                    ],
                },
                {
                    "name": "社区黑话",
                    "terms": [
                        {"term": "FOMO", "en": "Fear Of Missing Out", "def": "害怕错过行情而冲动买入，通常导致高位接盘"},
                        {"term": "FUD", "en": "Fear, Uncertainty, Doubt", "def": "散布恐惧、不确定和怀疑的信息，影响市场情绪"},
                        {"term": "梭哈", "en": "All In", "def": "把所有资金一次性投入，极度高风险行为"},
                        {"term": "韭菜", "en": "Noob/Dumb Money", "def": "缺乏经验的新手投资者，容易被收割"},
                        {"term": "抄底", "en": "Buy the Dip", "def": "在价格大幅下跌时买入"},
                        {"term": "腰斩", "en": "50% Drop", "def": "价格从高点下跌50%"},
                        {"term": "月球", "en": "To the Moon", "def": "价格暴涨的乐观预期"},
                    ],
                },
            ],
            "total_terms": 31,
        }

    # ==================================================================
    # 学习路径
    # ==================================================================

    def get_learning_path(self) -> dict:
        """学习路径路线图"""
        return {
            "phases": [
                {
                    "phase": 1, "name": "认知建设（1-2周）",
                    "goal": "理解区块链和加密货币的基本概念",
                    "tasks": ["学习区块链基础知识", "了解BTC和ETH的区别", "注册一个中心化交易所（推荐Binance或OKX）", "学会充值、买卖、提现", "安装MetaMask钱包并了解助记词", "花100元买一点BTC和ETH感受一下"],
                    "milestone": "能独立完成一次买卖操作",
                    "risk_level": "🟢 极低（只投入学习资金）",
                },
                {
                    "phase": 2, "name": "市场认知（2-4周）",
                    "goal": "看懂市场行情，理解价格波动的原因",
                    "tasks": ["学习K线图基础", "了解市值、流通量、交易量的含义", "关注行业新闻和社交媒体", "了解不同赛道：Layer1、DeFi、NFT、Meme等", "学会使用CoinGecko/CoinMarketCap", "开始记录交易日志"],
                    "milestone": "能说出5个以上赛道和代表项目",
                    "risk_level": "🟢 低（仍以学习为主）",
                },
                {
                    "phase": 3, "name": "策略入门（1-2月）",
                    "goal": "建立第一个投资策略",
                    "tasks": ["学习定投策略(DCA)并实践", "学习仓位管理基础", "设定止损规则并严格执行", "尝试DeFi质押赚取被动收益", "了解链上分析工具", "开始小额实战（总资金的10-20%）"],
                    "milestone": "有完整的交易计划和风控规则",
                    "risk_level": "🟡 中等（小额实战）",
                },
                {
                    "phase": 4, "name": "进阶实战（3-6月）",
                    "goal": "形成稳定的交易系统",
                    "tasks": ["深入学习技术分析", "学习链上数据分析", "参与DeFi流动性挖矿", "尝试空投交互", "建立自己的投资框架", "定期复盘交易日志"],
                    "milestone": "3个月正收益，最大回撤<20%",
                    "risk_level": "🟠 中高（增加实战资金）",
                },
                {
                    "phase": 5, "name": "系统成熟（6-12月）",
                    "goal": "建立可复制的盈利系统",
                    "tasks": ["开发自己的交易指标或策略", "管理更大的资金规模", "学习衍生品交易（谨慎！）", "参与一级市场投资", "建立行业人脉网络", "开始教导他人（教是最好的学）"],
                    "milestone": "年化收益>50%，风险调整后收益优秀",
                    "risk_level": "🔴 高（需要严格风控）",
                },
                {
                    "phase": 6, "name": "大师境界（持续）",
                    "goal": "从交易者进化为投资者",
                    "tasks": ["形成自己的投资哲学", "参与项目治理和社区建设", "跨周期配置资产", "保持学习和谦逊", "回馈社区"],
                    "milestone": "穿越至少一个完整牛熊周期",
                    "risk_level": "⚙️ 系统化风控",
                },
            ],
            "golden_rules": ["永远不要投资超过你能承受全部亏损的金额", "DYOR（Do Your Own Research）——自己研究，不要盲目跟单", "保护本金是第一要务", "不要借钱/贷款炒币", "保持学习，市场永远在变化"],
        }

    # ==================================================================
    # 策略工具箱
    # ==================================================================

    def get_strategies(self) -> dict:
        """策略工具箱"""
        return {
            "strategies": [
                {
                    "id": "dca", "name": "定投策略 (DCA)", "difficulty": "初级",
                    "description": "定期定额买入，降低平均成本。最适合新手的策略。",
                    "how_it_works": "每周/每月固定金额买入BTC和ETH，不管价格涨跌。",
                    "advantages": ["简单易执行", "降低择时风险", "心理压力小", "长期收益可观"],
                    "disadvantages": ["牛市收益不如一次性投入", "需要长期坚持"],
                    "best_for": "新手、上班族、不想花太多时间研究的人",
                    "example": "每月1号投入2000元买BTC，坚持2年。2022年熊市开始定投的人，到2024年牛市收益超过200%。",
                },
                {
                    "id": "trend", "name": "趋势跟踪", "difficulty": "中级",
                    "description": "跟随市场趋势，上涨时持有，下跌时离场。",
                    "how_it_works": "使用均线系统（如200日均线），价格在均线上方持有，跌破均线卖出。",
                    "advantages": ["能抓住大趋势", "避免深度套牢", "规则明确"],
                    "disadvantages": ["震荡市频繁止损", "可能错过底部反弹"],
                    "best_for": "有耐心、能接受小亏损的投资者",
                    "example": "BTC在200日均线上方时持有，跌破后卖出。2020-2021年牛市中，只在2021年5月和2022年1月触发卖出信号。",
                },
                {
                    "id": "hodl", "name": "HODL (钻石手)", "difficulty": "初级",
                    "description": "买入并长期持有，无视短期波动。",
                    "how_it_works": "选择BTC和ETH等核心资产，买入后长期持有（至少一个完整周期）。",
                    "advantages": ["最省心", "避免频繁交易的手续费", "历史收益最高"],
                    "disadvantages": ["需要极大的心理承受能力", "可能经历80%以上的回撤"],
                    "best_for": "信仰坚定、有长期视野的投资者",
                    "example": "2018年底买入BTC（约3200美元），持有到2021年底（约69000美元），收益超过20倍。",
                },
                {
                    "id": "rebalance", "name": "定期再平衡", "difficulty": "中级",
                    "description": "定期调整持仓比例，保持目标配置。",
                    "how_it_works": "设定目标比例（如BTC 50%、ETH 30%、其他20%），每季度或涨跌幅超阈值时调整。",
                    "advantages": ["自动高卖低买", "控制风险", "纪律性强"],
                    "disadvantages": ["可能产生税务事件", "需要定期操作"],
                    "best_for": "有多币种组合的投资者",
                    "example": "初始配置BTC 50%、ETH 30%、SOL 20%。BTC涨超60%时卖出部分BTC买入其他，保持比例。",
                },
                {
                    "id": "narrative", "name": "叙事轮动", "difficulty": "高级",
                    "description": "跟随市场叙事，提前布局即将爆发的赛道。",
                    "how_it_works": "研究VC投资方向、开发者趋势、社交媒体热度，提前布局新兴叙事。",
                    "advantages": ["收益倍数高", "能抓住市场热点"],
                    "disadvantages": ["需要深入研究", "叙事可能失败", "时机难以把握"],
                    "best_for": "有研究能力和行业敏感度的投资者",
                    "example": "2023年底AI叙事兴起，提前布局FET、RNDR等AI代币，2024年涨幅超过500%。",
                },
                {
                    "id": "arbitrage", "name": "套利策略", "difficulty": "高级",
                    "description": "利用市场低效率获取低风险收益。",
                    "how_it_works": "跨交易所价差套利、期现套利、稳定币脱锚套利等。",
                    "advantages": ["风险相对低", "收益稳定"],
                    "disadvantages": ["机会越来越少", "需要技术能力", "资金效率低"],
                    "best_for": "有技术背景和充足资金的投资者",
                    "example": "BTC在交易所A价格$60000，交易所B价格$60200，在A买入同时在B卖出，赚取$200差价。",
                },
            ],
        }

    # ==================================================================
    # DCA模拟器
    # ==================================================================

    def simulate_dca(self, coin: str, monthly_amount: float, months: int) -> dict:
        """定投模拟计算"""
        import random
        random.seed(hash(coin) + months)
        monthly_returns = [random.gauss(0.02, 0.15) for _ in range(months)]
        total_invested = monthly_amount * months
        total_value = 0
        total_coins = 0
        history = []
        for i, ret in enumerate(monthly_returns):
            base_price = 50000 if coin == "bitcoin" else 3000
            price = base_price * (1 + ret) ** (i + 1)
            coins_bought = monthly_amount / price
            total_coins += coins_bought
            total_value = total_coins * price
            history.append({"month": i + 1, "invested": monthly_amount * (i + 1), "value": round(total_value, 2), "return_pct": round((total_value / (monthly_amount * (i + 1)) - 1) * 100, 2), "coins": round(total_coins, 8)})
        final_return = (total_value / total_invested - 1) * 100 if total_invested > 0 else 0
        return {"coin": coin, "monthly_amount": monthly_amount, "months": months, "total_invested": total_invested, "final_value": round(total_value, 2), "total_return_pct": round(final_return, 2), "total_coins": round(total_coins, 8), "avg_cost": round(total_invested / total_coins, 2) if total_coins > 0 else 0, "history": history, "note": "⚠️ 以上为模拟数据，仅供学习理解定投原理。实际收益取决于真实市场价格。"}

    # ==================================================================
    # 仓位计算器
    # ==================================================================

    def calculate_position(self, total_capital: float, risk_per_trade: float, win_rate: float, avg_win: float, avg_loss: float) -> dict:
        """仓位计算 - Kelly公式 + 固定风险"""
        b = avg_win / avg_loss if avg_loss > 0 else 1
        kelly = (b * win_rate - (1 - win_rate)) / b if b > 0 else 0
        half_kelly = kelly / 2
        risk_amount = total_capital * risk_per_trade
        expected_return = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        return {
            "kelly_fraction": round(kelly * 100, 2),
            "half_kelly_fraction": round(half_kelly * 100, 2),
            "recommended_position": round(half_kelly * total_capital, 2),
            "risk_per_trade_amount": round(risk_amount, 2),
            "expected_return_per_trade": round(expected_return * 100, 2),
            "risk_reward_ratio": round(b, 2),
            "max_loss_per_trade": round(risk_amount, 2),
            "interpretation": self._interpret_position(kelly, half_kelly, expected_return),
            "formula": {"kelly": "f* = (bp - q) / b", "where": "b=赔率(平均盈利/平均亏损), p=胜率, q=败率(1-p)"},
        }

    def _interpret_position(self, kelly: float, half_kelly: float, expected: float) -> str:
        if kelly <= 0:
            return "⚠️ Kelly值为负：这个交易系统的期望收益为负，不建议交易！需要提高胜率或改善盈亏比。"
        parts = []
        if expected > 0:
            parts.append(f"✅ 期望收益为正（{expected*100:.1f}%），系统有正期望。")
        if half_kelly > 0.25:
            parts.append("⚠️ 建议仓位较大（>25%），考虑降低单笔风险或减少交易频率。")
        elif half_kelly > 0.1:
            parts.append(f"✅ 建议仓位合理（{half_kelly*100:.1f}%），适合实际操作。")
        else:
            parts.append(f"📌 建议仓位较小（{half_kelly*100:.1f}%），可以用多笔小额分散。")
        parts.append("💡 实际操作建议使用半凯利（Half-Kelly），降低波动性。")
        return " ".join(parts)

    # ==================================================================
    # 风险管理
    # ==================================================================

    def get_risk_checklist(self) -> dict:
        return {
            "before_buy": [
                {"item": "我研究了这个项目至少2小时", "category": "研究", "critical": True},
                {"item": "我理解这个项目解决什么问题", "category": "研究", "critical": True},
                {"item": "我检查了代币经济学（总量、分配、解锁计划）", "category": "研究", "critical": True},
                {"item": "我查看了团队背景和GitHub活跃度", "category": "研究", "critical": False},
                {"item": "我确认这不是投资金额的全部", "category": "资金", "critical": True},
                {"item": "这笔钱亏完不会影响我的生活", "category": "资金", "critical": True},
                {"item": "我没有借钱/贷款来投资", "category": "资金", "critical": True},
                {"item": "我设定了止损位", "category": "策略", "critical": True},
                {"item": "我设定了止盈目标", "category": "策略", "critical": False},
                {"item": "我记录了买入理由", "category": "纪律", "critical": True},
            ],
            "before_sell": [
                {"item": "我不是因为恐慌而卖出", "category": "情绪", "critical": True},
                {"item": "我检查了基本面是否发生变化", "category": "研究", "critical": True},
                {"item": "我不是因为'回本'心理而持有亏损仓位", "category": "情绪", "critical": True},
                {"item": "卖出后我有明确的资金安排", "category": "策略", "critical": False},
            ],
            "during_hold": [
                {"item": "每周检查一次持仓，不要每小时看", "category": "纪律", "critical": False},
                {"item": "关注项目进展和团队动态", "category": "研究", "critical": False},
                {"item": "定期再平衡", "category": "策略", "critical": False},
                {"item": "记录并学习每次涨跌的原因", "category": "学习", "critical": False},
            ],
        }

    def get_common_mistakes(self) -> dict:
        return {
            "mistakes": [
                {"name": "FOMO追高", "frequency": "⭐⭐⭐⭐⭐", "description": "看到别人赚钱就冲动买入，通常在最高点附近入场", "solution": "设定规则：大涨的币不追，等回调再买。或者用定投平滑成本。", "example": "2021年11月BTC $69000时大量新手入场，之后跌到$16000"},
                {"name": "恐慌割肉", "frequency": "⭐⭐⭐⭐⭐", "description": "价格暴跌时恐慌卖出，卖在最低点", "solution": "提前设好止损位，用限价单自动执行。不要在大跌时做决定。", "example": "2020年3月12日BTC一天跌50%，恐慌卖出的人错过了之后从$4000到$69000的涨幅"},
                {"name": "梭哈山寨币", "frequency": "⭐⭐⭐⭐", "description": "把所有资金投入一个山寨币，期望百倍收益", "solution": "核心仓位（60-70%）放在BTC和ETH，山寨币用小仓位。", "example": "99%的山寨币最终归零，只有极少数能存活一个完整周期"},
                {"name": "合约爆仓", "frequency": "⭐⭐⭐⭐", "description": "用高杠杆玩合约，一次反向波动就爆仓", "solution": "新手远离合约！如果一定要玩，杠杆不超过3倍，仓位不超过总资金10%。", "example": "2021年5月19日，全网合约爆仓超过100亿美元"},
                {"name": "沉没成本", "frequency": "⭐⭐⭐", "description": "亏损后不断加仓'摊低成本'，越套越深", "solution": "亏损的仓位不加仓。止损出局，等信号明确再重新入场。", "example": "LUNA从$100跌到$50时很多人抄底，最终归零"},
                {"name": "听信KOL", "frequency": "⭐⭐⭐⭐", "description": "盲目跟单推特/群里的'老师'，不做自己的研究", "solution": "DYOR！别人的分析可以参考，但决策必须自己做。", "example": "很多KOL收钱推广垃圾项目，粉丝接盘后暴跌"},
                {"name": "频繁交易", "frequency": "⭐⭐⭐", "description": "每天都想交易，手续费吃掉利润", "solution": "减少交易频率，每次交易都要有明确的理由和计划。", "example": "每天交易一次，每次0.1%手续费，一年下来手续费就吃掉36%的本金"},
                {"name": "忽视安全", "frequency": "⭐⭐⭐", "description": "不重视钱包安全，被盗或丢失私钥", "solution": "启用2FA、用冷钱包存大额资产、备份助记词到安全的地方。", "example": "FTX暴雷时，放在交易所的数十亿美元资产被冻结"},
            ],
        }

    def get_security_guide(self) -> dict:
        return {
            "wallet_security": {
                "title": "钱包安全",
                "rules": ["助记词写在纸上，不要截图、不要存云端", "大额资产用硬件钱包（Ledger/Trezor）", "不要在公共WiFi下操作钱包", "定期检查钱包授权，撤销不用的合约授权", "小额日常使用用热钱包，大额存储用冷钱包"],
            },
            "exchange_security": {
                "title": "交易所安全",
                "rules": ["一定要开启Google Authenticator（不要用短信验证）", "设置提币白名单", "不要在交易所放超过总资产的30%", "选择头部交易所（Binance、OKX、Coinbase）", "FTX的教训：再大的交易所也可能暴雷"],
            },
            "scam_prevention": {
                "title": "防骗指南",
                "rules": ["任何人要你的助记词/私钥 = 100%骗子", "免费空投要你先转账 = 100%骗局", "高回报无风险 = 100%骗局", "不要点击不明链接，尤其是Discord/Telegram里的", "验证合约地址：只从官方渠道获取", "貔貅合约：只能买不能卖的代币，用Token Sniffer检查"],
            },
        }

    # ==================================================================
    # DeFi指南
    # ==================================================================

    def get_defi_guide(self) -> dict:
        return {
            "levels": [
                {
                    "level": "入门", "name": "DeFi初体验",
                    "protocols": [
                        {"name": "Uniswap", "type": "DEX", "chain": "Ethereum/Arbitrum/Base", "risk": "低", "action": "用ETH交换一个小额代币，体验DEX交易"},
                        {"name": "Aave", "type": "借贷", "chain": "Ethereum/Arbitrum", "risk": "低", "action": "存入USDC赚取利息，了解借贷机制"},
                    ],
                    "tips": "先用小额（$50-100）体验，理解Gas费、滑点、授权等概念。",
                },
                {
                    "level": "进阶", "name": "流动性提供",
                    "protocols": [
                        {"name": "Curve", "type": "稳定币DEX", "chain": "多链", "risk": "低-中", "action": "为稳定币池提供流动性，赚取手续费"},
                        {"name": "Lido", "type": "质押", "chain": "Ethereum", "risk": "低", "action": "质押ETH获得stETH，赚取质押收益"},
                    ],
                    "tips": "注意无常损失。稳定币对的无常损失最小，适合入门。",
                },
                {
                    "level": "高级", "name": "收益优化",
                    "protocols": [
                        {"name": "Pendle", "type": "收益代币化", "chain": "多链", "risk": "中", "action": "分离资产的本金和收益部分进行交易"},
                        {"name": "Ethena", "type": "合成美元", "chain": "Ethereum", "risk": "中-高", "action": "了解delta中性策略和sUSDe收益"},
                    ],
                    "tips": "高级策略需要深入理解机制。先读白皮书，再投入资金。",
                },
            ],
            "gas_optimization": {
                "title": "Gas费优化",
                "tips": ["使用Layer2（Arbitrum、Optimism、Base）降低Gas费90%+", "在Gas费低的时段操作（UTC凌晨/周末）", "批量操作：DeFi Saver等工具可以批量执行交易", "设置Gas上限，避免意外高Gas费"],
            },
        }

    def get_payment_tools(self) -> dict:
        """加密货币出入金工具指南"""
        return {
            "intro": "出入金是加密投资的第一步和最后一步。选择合适的工具能节省大量手续费，提高资金效率。",
            "tools": [
                {
                    "name": "Bitget U卡",
                    "type": "加密支付卡（万事达）",
                    "highlight": "终身0手续费开卡持有",
                    "features": [
                        "终身0手续费开卡、0年费持有",
                        "首次消费得5U奖励",
                        "充50U可空投10U奖励",
                        "可绑定微信/支付宝，直接消费",
                        "单笔200元以内免手续费",
                        "大陆身份证可直接注册",
                    ],
                    "fees": {
                        "开卡费": "免费",
                        "年费": "免费",
                        "充值损耗": "约1%",
                        "消费损耗": "约1.4%",
                    },
                    "card_type": "万事达卡",
                    "best_for": "日常消费、小额出入金、绑定微信支付宝",
                    "risk_level": "低",
                    "referral": "使用邀请码注册可享额外福利",
                },
                {
                    "name": "OKX 卡",
                    "type": "加密支付卡（Visa）",
                    "highlight": "全球Visa网络覆盖",
                    "features": [
                        "Visa全球商户网络",
                        "支持多币种消费",
                        "OKX账户直接扣款",
                        "支持Apple Pay/Google Pay",
                    ],
                    "fees": {"开卡费": "免费", "年费": "免费", "消费手续费": "约1-2%"},
                    "card_type": "Visa",
                    "best_for": "海外消费、Visa网络用户",
                    "risk_level": "低",
                },
                {
                    "name": "Binance 卡",
                    "type": "加密支付卡（Visa）",
                    "highlight": "全球最大交易所背书",
                    "features": [
                        "Binance账户直接消费",
                        "最高8%消费返现",
                        "支持多种加密货币",
                        "欧洲SEPA转账",
                    ],
                    "fees": {"开卡费": "免费", "年费": "免费", "消费手续费": "0-0.9%"},
                    "card_type": "Visa",
                    "best_for": "Binance用户、追求返现",
                    "risk_level": "低",
                },
            ],
            "fiat_channels": [
                {
                    "name": "C2C/P2P交易",
                    "description": "在交易所内与个人卖家直接交易，支持支付宝/微信/银行卡",
                    "platforms": ["Binance C2C", "OKX C2C", "火必C2C"],
                    "advantages": ["费率低（0-0.1%）", "支持多种支付方式", "即时到账"],
                    "risks": ["收到黑钱导致银行卡冻结", "需要选择信誉好的商家"],
                    "tips": "选择注册时间长、成交笔数多的商家。避免大额单笔交易，分批操作。",
                },
                {
                    "name": "交易所法币通道",
                    "description": "交易所内置的法币购买功能，用银行卡直接买币",
                    "platforms": ["Binance Buy Crypto", "OKX Quick Buy", "Coinbase"],
                    "advantages": ["操作简单", "即时到账", "平台担保"],
                    "risks": ["手续费较高（1-3%）", "限额较低"],
                    "tips": "适合小额购买。大额建议用C2C。",
                },
            ],
            "safety_tips": [
                "不要在社交媒体上透露你的加密资产",
                "出入金时注意银行卡风控，避免频繁大额转账",
                "使用专门的银行卡进行加密交易，与日常用卡分开",
                "保留交易记录，以备税务申报",
                "选择头部交易所，避免小平台跑路风险",
                "警惕'代买代卖'服务，可能是洗钱陷阱",
            ],
        }

    def get_airdrop_guide(self) -> dict:
        return {
            "intro": "空投是项目方免费分发代币给早期用户的营销策略。历史上最赚钱的空投包括Uniswap($12000+)、Arbitrum($5000+)、Optimism($3000+)等。",
            "how_it_works": ["项目方确定空投资格标准（使用次数、TVL贡献、时间等）", "快照：记录符合条件的地址", "开放领取：符合条件的用户领取免费代币"],
            "strategies": [
                {"name": "多链交互", "description": "在多条链上使用主流协议，增加被快照的机会", "effort": "中", "potential": "高"},
                {"name": "测试网参与", "description": "参与新项目的测试网，通常成本为零", "effort": "低", "potential": "中"},
                {"name": "治理参与", "description": "参与DAO治理投票，展示长期社区参与", "effort": "低", "potential": "中"},
                {"name": "Gitcoin捐赠", "description": "通过Gitcoin等平台捐赠，获得多个项目空投资格", "effort": "低", "potential": "中-高"},
            ],
            "risk_warning": ["不要为了空投投入大量资金——空投不是保证的", "注意Gas费成本，确保交互成本低于潜在空投价值", "小心钓鱼网站——只从官方渠道获取信息", "空投代币通常会先涨后跌，考虑领取后立即卖出一部分"],
            "tools": [
                {"name": "DefiLlama", "purpose": "查看协议TVL和空投信息"},
                {"name": "Dune Analytics", "purpose": "链上数据查询，查看自己的交互记录"},
                {"name": "earni.fi", "purpose": "检查地址是否有未领取的空投"},
            ],
        }

    # ==================================================================
    # 交易检查清单
    # ==================================================================

    def get_trading_checklist(self) -> dict:
        return {
            "pre_trade": {
                "title": "📋 交易前",
                "items": [
                    {"check": "市场环境判断", "detail": "当前是牛市/熊市/震荡市？", "time": "5分钟"},
                    {"check": "叙事/热点分析", "detail": "当前市场在炒什么叙事？持续性如何？", "time": "10分钟"},
                    {"check": "项目基本面", "detail": "团队、产品、代币经济学、竞品对比", "time": "30分钟"},
                    {"check": "技术面分析", "detail": "关键支撑/阻力位、趋势方向、成交量", "time": "10分钟"},
                    {"check": "链上数据", "detail": "巨鲸动向、交易所净流入流出", "time": "10分钟"},
                    {"check": "仓位计算", "detail": "用Kelly公式或固定风险法计算仓位", "time": "5分钟"},
                    {"check": "止损位设定", "detail": "明确止损价位和最大亏损金额", "time": "2分钟"},
                    {"check": "记录交易计划", "detail": "写下买入理由、目标位、止损位", "time": "5分钟"},
                ],
            },
            "during_trade": {
                "title": "📊 持仓中",
                "items": [
                    {"check": "不要频繁看盘", "detail": "每天最多检查1-2次，避免情绪化操作", "frequency": "每天"},
                    {"check": "跟踪项目进展", "detail": "关注官方公告、社区动态", "frequency": "每周"},
                    {"check": "监控链上数据", "detail": "巨鲸异动、大额转账", "frequency": "每周"},
                    {"check": "检查止损位", "detail": "价格接近止损位时做好准备", "frequency": "每天"},
                    {"check": "记录观察", "detail": "写下你对市场的观察和感受", "frequency": "每周"},
                ],
            },
            "post_trade": {
                "title": "📝 交易后",
                "items": [
                    {"check": "记录结果", "detail": "盈亏金额、持有时间", "time": "立即"},
                    {"check": "复盘分析", "detail": "买入理由是否正确？止损/止盈执行是否到位？", "time": "当天"},
                    {"check": "情绪记录", "detail": "交易过程中的情绪变化", "time": "当天"},
                    {"check": "总结教训", "detail": "做得好的和需要改进的", "time": "当天"},
                    {"check": "更新策略", "detail": "根据这次交易更新你的交易规则", "time": "每周"},
                ],
            },
        }

    # ==================================================================
    # 大师语录
    # ==================================================================

    def get_master_wisdom(self) -> dict:
        return {
            "wisdom": [
                {"person": "中本聪 (Satoshi Nakamoto)", "role": "比特币创始人", "quotes": ["如果你不相信我或者不理解它，我没有时间去说服你。", "我对更安全的基于哈希的工作量证明没有更好的替代方案。"], "lesson": "技术信仰。真正的创新不需要说服所有人。"},
                {"person": "Vitalik Buterin", "role": "以太坊创始人", "quotes": ["加密货币的目标不是让少数人变得极其富有，而是让很多人获得经济自由。", "不要投资你不懂的东西。"], "lesson": "技术理想主义。投资前先理解技术。"},
                {"person": "CZ (赵长鹏)", "role": "Binance创始人", "quotes": ["FUD是你的朋友，当别人恐惧时你应该贪婪。", "保持饥饿，保持愚蠢。"], "lesson": "逆向思维。市场恐慌时往往是最好的机会。"},
                {"person": "Arthur Hayes", "role": "BitMEX创始人", "quotes": ["加密市场是纯粹的供需博弈，没有央行干预。", "波动性是朋友，不是敌人。"], "lesson": "拥抱波动。高波动 = 高机会。"},
                {"person": "Su Zhu", "role": "Three Arrows Capital创始人", "quotes": ["超级周期理论：加密货币将不断创出新高。"], "lesson": "⚠️ 反面教材：再有影响力的观点也可能是错的。3AC在2022年破产。永远保持独立思考。"},
                {"person": "加密社区", "role": "集体智慧", "quotes": ["DYOR (Do Your Own Research) — 自己研究", "WAGMI (We're All Gonna Make It) — 我们都会成功的", "Not your keys, not your coins — 不是你的私钥，就不是你的币", "Buy the dip — 逢低买入", "HODL — 坚定持有"], "lesson": "社区文化。这些格言背后有深刻的道理。"},
            ],
        }
