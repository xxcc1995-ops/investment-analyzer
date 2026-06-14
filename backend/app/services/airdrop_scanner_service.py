"""
空投机会扫描器 - 核心服务层
整合 DefiLlama/交易所活动/链上打新/RSS资讯，提供系统化空投机会发现与评分

方法论来源：火山哥空投教程 — 多交易所覆盖 + 链上项目跟踪 + 多号规模化执行
"""
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

# ==================== 基础设施 ====================

_cache: dict = {}
CACHE_TTL_SHORT = 300      # 5分钟
CACHE_TTL_MEDIUM = 1800    # 30分钟
CACHE_TTL_LONG = 3600      # 1小时

PROXY = os.getenv("POLYMARKET_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
_PROXIES = {"http": PROXY, "https": PROXY} if PROXY else None

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
})
if _PROXIES:
    _session.proxies.update(_PROXIES)


def _get_cached(key: str, ttl: int = CACHE_TTL_LONG):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < ttl:
            return val
    return None


def _set_cached(key: str, val):
    _cache[key] = (val, time.time())


def _fetch_json(url: str, params: dict = None, timeout: int = 15) -> Optional[Any]:
    try:
        resp = _session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Fetch failed: {url} - {e}")
        return None


# ==================== 交易所活动数据 ====================

EXCHANGE_CAMPAIGNS = [
    # ---- Binance ----
    {
        "id": "binance_alpha",
        "exchange": "Binance",
        "type": "Alpha",
        "name": "币安 Alpha 积分",
        "description": "通过持有BNB和交易Alpha代币积累积分，定期获得空投。积分越高，空投金额越大。",
        "url": "https://www.binance.com/zh-CN/activity/alpha",
        "status": "active",
        "estimated_value": "$50-500",
        "difficulty": "medium",
        "capital_required": "$500-2000",
        "deadline": None,
        "recurring": True,
    },
    {
        "id": "binance_booster",
        "exchange": "Binance",
        "type": "Booster",
        "name": "币安 Booster 活动",
        "description": "完成链上任务（交互指定协议）获得积分，积分兑换代币空投。通常每期2-4周。",
        "url": "https://www.binance.com/zh-CN/activity/booster",
        "status": "active",
        "estimated_value": "$20-200",
        "difficulty": "medium",
        "capital_required": "$100-500",
        "deadline": None,
        "recurring": True,
    },
    {
        "id": "binance_tge",
        "exchange": "Binance",
        "type": "TGE",
        "name": "币安 TGE 打新",
        "description": "币安钱包专属代币生成事件，需要BNB参与申购，通常有较高收益。",
        "url": "https://www.binance.com/zh-CN/activity/wallet-tge",
        "status": "active",
        "estimated_value": "$100-1000",
        "difficulty": "easy",
        "capital_required": "$200-1000",
        "deadline": None,
        "recurring": True,
    },
    {
        "id": "binance_launchpool",
        "exchange": "Binance",
        "type": "Launchpool",
        "name": "币安 Launchpool",
        "description": "质押BNB/FDUSD挖新币，零风险获取新代币。通常持续3-7天。",
        "url": "https://www.binance.com/zh-CN/launchpool",
        "status": "active",
        "estimated_value": "$50-300",
        "difficulty": "easy",
        "capital_required": "$100+",
        "deadline": None,
        "recurring": True,
    },
    # ---- OKX ----
    {
        "id": "okx_boost",
        "exchange": "OKX",
        "type": "Boost",
        "name": "欧易 Boost 活动",
        "description": "完成指定交易/链上任务获得Boost积分，积分兑换代币奖励。",
        "url": "https://www.okx.com/zh-hans/earn/boost",
        "status": "active",
        "estimated_value": "$20-200",
        "difficulty": "medium",
        "capital_required": "$100-500",
        "deadline": None,
        "recurring": True,
    },
    {
        "id": "okx_wallet_boost",
        "exchange": "OKX",
        "type": "Wallet Boost",
        "name": "欧易钱包 Boost",
        "description": "使用OKX Web3钱包完成链上交互任务，获取额外Boost奖励。",
        "url": "https://www.okx.com/zh-hans/web3/earn/boost",
        "status": "active",
        "estimated_value": "$10-100",
        "difficulty": "medium",
        "capital_required": "$50-200",
        "deadline": None,
        "recurring": True,
    },
    # ---- Bybit ----
    {
        "id": "bybit_launchpool",
        "exchange": "Bybit",
        "type": "Launchpool",
        "name": "Bybit Launchpool",
        "description": "质押代币挖新币，类似币安Launchpool。",
        "url": "https://www.bybit.com/zh-CN/earn/launchpool",
        "status": "active",
        "estimated_value": "$30-200",
        "difficulty": "easy",
        "capital_required": "$100+",
        "deadline": None,
        "recurring": True,
    },
    {
        "id": "bybit_newuser",
        "exchange": "Bybit",
        "type": "新人活动",
        "name": "Bybit 新人奖励",
        "description": "新用户注册+入金+交易可获得确定性奖励，几乎无风险。",
        "url": "https://www.bybit.com/zh-CN/promotion/new-user",
        "status": "active",
        "estimated_value": "$20-100",
        "difficulty": "easy",
        "capital_required": "$100+",
        "deadline": None,
        "recurring": False,
    },
    # ---- Gate ----
    {
        "id": "gate_startup",
        "exchange": "Gate",
        "type": "Startup",
        "name": "Gate Startup 打新",
        "description": "Gate.io的IEO平台，定期上线新项目，持有GT可参与认购。",
        "url": "https://www.gate.io/startup",
        "status": "active",
        "estimated_value": "$10-100",
        "difficulty": "easy",
        "capital_required": "$50+",
        "deadline": None,
        "recurring": True,
    },
    {
        "id": "gate_alpha",
        "exchange": "Gate",
        "type": "Alpha",
        "name": "Gate 芝麻 Alpha",
        "description": "Gate的链上Alpha代币交易活动，通过交易积累积分获取空投。",
        "url": "https://www.gate.io/alpha",
        "status": "active",
        "estimated_value": "$10-100",
        "difficulty": "medium",
        "capital_required": "$100-500",
        "deadline": None,
        "recurring": True,
    },
]

# ==================== 链上打新平台 ====================

LAUNCHPAD_PROJECTS = [
    {
        "id": "virtuals_unicorn",
        "project_name": "Virtuals Unicorn 打新",
        "platform": "Virtuals Protocol",
        "platform_url": "https://app.virtuals.io",
        "chain": "Base",
        "status": "active",
        "estimated_allocation": "按积分分配",
        "participation_link": "https://app.virtuals.io/launches",
        "notes": "需要持有VIRTUAL代币并积累积分，嘴撸（社交互动）+持币双重积分",
    },
    {
        "id": "kaito_yaps",
        "project_name": "Kaito Yaps 打新",
        "platform": "Kaito",
        "platform_url": "https://yaps.kaito.ai",
        "chain": "Multi",
        "status": "active",
        "estimated_allocation": "按Yaps积分分配",
        "participation_link": "https://yaps.kaito.ai",
        "notes": "通过Twitter互动（发推、评论、引用）积累Yaps积分，后期可能有空投",
    },
    {
        "id": "megaeth",
        "project_name": "MegaETH 打新",
        "platform": "MegaETH",
        "platform_url": "https://megaeth.com",
        "chain": "MegaETH",
        "status": "upcoming",
        "estimated_allocation": "待定",
        "participation_link": "https://megaeth.com",
        "notes": "高性能L2，融资$20M+，测试网交互可能有空投",
    },
    {
        "id": "buidlpad_falcon",
        "project_name": "buidlpad Falcon 打新",
        "platform": "buidlpad",
        "platform_url": "https://buidlpad.com",
        "chain": "Multi",
        "status": "active",
        "estimated_allocation": "按贡献分配",
        "participation_link": "https://buidlpad.com",
        "notes": "合规打新平台，KYC后可参与，通常需要稳定币贡献",
    },
    {
        "id": "gensyn_echo",
        "project_name": "Gensyn Echo 平台打新",
        "platform": "Echo",
        "platform_url": "https://echo.xyz",
        "chain": "Multi",
        "status": "upcoming",
        "estimated_allocation": "待定",
        "participation_link": "https://echo.xyz",
        "notes": "AI算力协议，通过Echo平台打新",
    },
    {
        "id": "polymarket_interact",
        "project_name": "Polymarket 交互",
        "platform": "Polymarket",
        "platform_url": "https://polymarket.com",
        "chain": "Polygon",
        "status": "active",
        "estimated_allocation": "按交易量分配",
        "participation_link": "https://polymarket.com",
        "notes": "预测市场平台，交易可能积累未来空投资格",
    },
]

# ==================== 空投关键词 ====================

AIRDROP_HIGH_KEYWORDS = [
    "airdrop confirmed", "token launch", "claim now", "snapshot date",
    "eligibility check", "airdrop claim", "free tokens", "season 2 airdrop",
    "retroactive airdrop", "token generation event", "TGE announced",
    "空投确认", "快照时间", "领取空投", "代币发行", "空投开始",
]

AIRDROP_MEDIUM_KEYWORDS = [
    "potential airdrop", "points program", "incentivized testnet",
    "season 2", "retroactive", "community rewards", "beta launch",
    "testnet live", "points season", "reward distribution",
    "积分", "激励测试网", "追溯性", "社区奖励", "测试网上线",
]


class AirdropScannerService:
    """空投机会扫描器服务"""

    # ==================================================================
    # 1. 未发币协议扫描 (DefiLlama)
    # ==================================================================

    def get_untokenized_protocols(self) -> Dict[str, Any]:
        """获取 DefiLlama 未发币高TVL协议，带空投评分"""
        cached = _get_cached("untokenized_protocols")
        if cached:
            return cached

        protocols = self._fetch_defillama_protocols()
        if not protocols:
            return {"protocols": [], "count": 0, "update_time": datetime.now().isoformat(), "error": "DefiLlama API不可用"}

        scored_protocols = []
        for p in protocols:
            name = p.get("name", "")
            tvl = p.get("tvl") or 0
            symbol = p.get("symbol", "")
            category = p.get("category", "")
            chain = p.get("chain", "Multi")
            chains = p.get("chains", [])
            gecko_id = p.get("gecko_id")
            url = p.get("url", "")
            description = p.get("description", "")
            listed_at = p.get("listedAt")  # Unix timestamp
            change_1m = p.get("change_1m")  # 1-month TVL change %

            # 判断未发币：symbol 为 "-" 或空，且 gecko_id 为空
            is_no_token = (symbol in ("-", "", "N/A")) and not gecko_id
            if not is_no_token or tvl < 10_000_000:  # TVL > $10M
                continue

            # 计算协议年龄（月）
            age_months = None
            if listed_at:
                try:
                    listed_dt = datetime.fromtimestamp(listed_at)
                    age_months = max(0, (datetime.now() - listed_dt).days // 30)
                except Exception:
                    pass

            # 计算空投评分
            airdrop_score = self._calculate_airdrop_score(
                tvl=tvl,
                age_months=age_months,
                category=category,
                chain_count=len(chains) if chains else 1,
                tvl_change_1m=change_1m,
            )

            scored_protocols.append({
                "name": name,
                "chain": chain if chain and chain != "Multi" else (chains[0] if len(chains) == 1 else "Multi"),
                "chains": chains[:5] if chains else [chain] if chain else [],
                "tvl": round(tvl / 1e6, 2),  # 百万美元
                "category": category,
                "url": url,
                "description": (description or "")[:200],
                "airdrop_score": round(airdrop_score, 1),
                "age_months": age_months,
                "tvl_change_1m": round(change_1m, 2) if change_1m else None,
            })

        # 按空投评分排序
        scored_protocols.sort(key=lambda x: x["airdrop_score"], reverse=True)

        result = {
            "protocols": scored_protocols[:50],
            "count": len(scored_protocols),
            "update_time": datetime.now().isoformat(),
        }
        _set_cached("untokenized_protocols", result)
        return result

    def _calculate_airdrop_score(
        self,
        tvl: float,
        age_months: Optional[int],
        category: str,
        chain_count: int,
        tvl_change_1m: Optional[float],
    ) -> float:
        """
        计算空投概率评分 (0-100)

        评分维度：
        - TVL规模 (0-30分): TVL越高，项目越有实力发空投
        - 协议年龄 (0-20分): 6-24个月是最佳窗口期
        - 赛道类型 (0-15分): DeFi/L2/跨链桥更倾向发币
        - 链数量 (0-15分): 多链部署说明用户基数大
        - TVL增长 (0-20分): 增长中的项目更可能激励用户
        """
        score = 0.0

        # TVL规模 (0-30)
        tvl_m = tvl / 1e6
        if tvl_m >= 1000:
            score += 30
        elif tvl_m >= 500:
            score += 25
        elif tvl_m >= 200:
            score += 20
        elif tvl_m >= 100:
            score += 15
        elif tvl_m >= 50:
            score += 10
        elif tvl_m >= 10:
            score += 5

        # 协议年龄 (0-20) - 6-24个月最佳
        if age_months is not None:
            if 6 <= age_months <= 24:
                score += 20
            elif 3 <= age_months < 6:
                score += 12
            elif 24 < age_months <= 36:
                score += 10
            elif age_months > 36:
                score += 5
            else:
                score += 3  # 太新，不确定

        # 赛道类型 (0-15)
        high_score_categories = [
            "DEX", "Lending", "Bridge", "Liquid Staking", "Yield",
            "CDP", "Derivatives", "RWA", "Restaking", "L2",
            "Rollup", "Cross Chain", "DEX Aggregator",
        ]
        medium_score_categories = [
            "Yield Aggregator", "Indexes", "Options", "Insurance",
            "Liquid Restaking", "Staking", "Farm",
        ]
        cat_lower = category.lower() if category else ""
        if any(c.lower() in cat_lower for c in high_score_categories):
            score += 15
        elif any(c.lower() in cat_lower for c in medium_score_categories):
            score += 10
        else:
            score += 5

        # 链数量 (0-15)
        if chain_count >= 5:
            score += 15
        elif chain_count >= 3:
            score += 12
        elif chain_count >= 2:
            score += 8
        else:
            score += 4

        # TVL增长 (0-20)
        if tvl_change_1m is not None:
            if tvl_change_1m >= 50:
                score += 20
            elif tvl_change_1m >= 20:
                score += 15
            elif tvl_change_1m >= 5:
                score += 10
            elif tvl_change_1m >= 0:
                score += 5
            else:
                score += 0  # TVL下降，不太可能发空投

        return min(100.0, score)

    def _fetch_defillama_protocols(self) -> List[Dict[str, Any]]:
        """从 DefiLlama 获取全量 DeFi 协议列表"""
        return _fetch_json("https://api.llama.fi/protocols", timeout=20) or []

    # ==================================================================
    # 2. 交易所活动
    # ==================================================================

    def get_exchange_activities(self) -> Dict[str, Any]:
        """获取交易所活动列表"""
        cached = _get_cached("exchange_activities")
        if cached:
            return cached

        campaigns = EXCHANGE_CAMPAIGNS.copy()

        # 按交易所分组
        by_exchange: Dict[str, List] = {}
        for c in campaigns:
            ex = c["exchange"]
            if ex not in by_exchange:
                by_exchange[ex] = []
            by_exchange[ex].append(c)

        result = {
            "campaigns": campaigns,
            "by_exchange": by_exchange,
            "total_count": len(campaigns),
            "active_count": sum(1 for c in campaigns if c["status"] == "active"),
            "update_time": datetime.now().isoformat(),
        }
        _set_cached("exchange_activities", result)
        return result

    # ==================================================================
    # 3. 链上打新/IDO
    # ==================================================================

    def get_launchpad_projects(self) -> Dict[str, Any]:
        """获取链上打新项目列表"""
        cached = _get_cached("launchpad_projects")
        if cached:
            return cached

        projects = LAUNCHPAD_PROJECTS.copy()

        # 按平台分组
        by_platform: Dict[str, List] = {}
        for p in projects:
            plat = p["platform"]
            if plat not in by_platform:
                by_platform[plat] = []
            by_platform[plat].append(p)

        result = {
            "projects": projects,
            "by_platform": by_platform,
            "total_count": len(projects),
            "active_count": sum(1 for p in projects if p["status"] == "active"),
            "update_time": datetime.now().isoformat(),
        }
        _set_cached("launchpad_projects", result)
        return result

    # ==================================================================
    # 4. 空投资讯 (RSS聚合)
    # ==================================================================

    def get_airdrop_news(self) -> Dict[str, Any]:
        """获取空投相关RSS资讯"""
        cached = _get_cached("airdrop_news", CACHE_TTL_MEDIUM)
        if cached:
            return cached

        all_items = []
        sources_ok = []
        sources_failed = []

        # RSS源列表
        rss_sources = [
            ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
            ("CoinTelegraph", "https://cointelegraph.com/rss"),
            ("The Block", "https://www.theblock.co/rss.xml"),
            ("Decrypt", "https://decrypt.co/feed"),
        ]

        for source_name, rss_url in rss_sources:
            try:
                items = self._fetch_rss(rss_url, source_name)
                all_items.extend(items)
                sources_ok.append(source_name)
            except Exception as e:
                logger.warning(f"RSS fetch failed for {source_name}: {e}")
                sources_failed.append(source_name)

        # 筛选空投相关新闻
        airdrop_items = []
        for item in all_items:
            title_lower = item.get("title", "").lower()
            summary_lower = item.get("summary", "").lower()
            combined = title_lower + " " + summary_lower

            # 判断影响级别
            impact = "low"
            if any(kw in combined for kw in AIRDROP_HIGH_KEYWORDS):
                impact = "high"
            elif any(kw in combined for kw in AIRDROP_MEDIUM_KEYWORDS):
                impact = "medium"

            # 只保留空投相关的
            if impact != "low":
                # 判断类别
                category = "general"
                exchange_keywords = ["binance", "okx", "bybit", "gate", "币安", "欧易"]
                defi_keywords = ["defi", "protocol", "lending", "dex", "bridge", "swap"]
                l2_keywords = ["layer 2", "l2", "rollup", "arbitrum", "optimism", "base", "zksync"]

                if any(kw in combined for kw in exchange_keywords):
                    category = "exchange"
                elif any(kw in combined for kw in l2_keywords):
                    category = "l2"
                elif any(kw in combined for kw in defi_keywords):
                    category = "defi"

                airdrop_items.append({
                    "title": item.get("title", "")[:100],
                    "summary": item.get("summary", "")[:200],
                    "link": item.get("link", ""),
                    "source": item.get("source", ""),
                    "published": item.get("published", ""),
                    "impact": impact,
                    "category": category,
                })

        # 按影响级别排序
        impact_order = {"high": 0, "medium": 1, "low": 2}
        airdrop_items.sort(key=lambda x: impact_order.get(x["impact"], 9))

        result = {
            "items": airdrop_items[:30],
            "total_scanned": len(all_items),
            "airdrop_related": len(airdrop_items),
            "sources_ok": sources_ok,
            "sources_failed": sources_failed,
            "update_time": datetime.now().isoformat(),
        }
        _set_cached("airdrop_news", result)
        return result

    def _fetch_rss(self, url: str, source_name: str) -> List[Dict[str, str]]:
        """获取RSS feed并解析"""
        try:
            resp = _session.get(url, timeout=10)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            logger.warning(f"RSS fetch error for {source_name}: {e}")
            return []

        items = []
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)

            # 处理RSS 2.0格式
            for item_elem in root.iter("item"):
                title = item_elem.findtext("title", "").strip()
                link = item_elem.findtext("link", "").strip()
                description = item_elem.findtext("description", "").strip()
                pub_date = item_elem.findtext("pubDate", "").strip()

                # 清理HTML标签
                import re
                description = re.sub(r"<[^>]+>", "", description)[:300]

                if title:
                    items.append({
                        "title": title,
                        "summary": description,
                        "link": link,
                        "source": source_name,
                        "published": pub_date,
                    })

            # 处理Atom格式
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title = ""
                link = ""
                summary = ""
                published = ""

                title_el = entry.find("{http://www.w3.org/2005/Atom}title")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()

                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = link_el.get("href", "")

                summary_el = entry.find("{http://www.w3.org/2005/Atom}summary")
                if summary_el is not None and summary_el.text:
                    summary = re.sub(r"<[^>]+>", "", summary_el.text)[:300]

                pub_el = entry.find("{http://www.w3.org/2005/Atom}published")
                if pub_el is None:
                    pub_el = entry.find("{http://www.w3.org/2005/Atom}updated")
                if pub_el is not None and pub_el.text:
                    published = pub_el.text.strip()

                if title:
                    items.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name,
                        "published": published,
                    })

        except Exception as e:
            logger.warning(f"RSS parse error for {source_name}: {e}")

        return items

    # ==================================================================
    # 5. 综合机会评分
    # ==================================================================

    def get_opportunity_scores(self) -> Dict[str, Any]:
        """聚合所有机会并进行多维度评分"""
        cached = _get_cached("opportunity_scores")
        if cached:
            return cached

        # 获取各模块数据
        protocols_data = self.get_untokenized_protocols()
        exchange_data = self.get_exchange_activities()
        launchpad_data = self.get_launchpad_projects()

        scored = []

        # 评分未发币协议
        for p in protocols_data.get("protocols", []):
            score = p.get("airdrop_score", 0)
            certainty = min(10, score / 10)
            expected_return = self._estimate_return("defi", p.get("tvl", 0))
            difficulty = 3  # DeFi交互中等难度
            time_window = 5  # 无明确截止日期
            capital = self._estimate_capital(0)  # 无强制要求

            composite = self._weighted_score(certainty, expected_return, difficulty, time_window, capital)
            scored.append({
                "name": p["name"],
                "source": "defi",
                "source_label": "DeFi协议",
                "detail": f"TVL: ${p['tvl']}M | {p['category']}",
                "url": p.get("url", ""),
                "certainty": round(certainty, 1),
                "expected_return": round(expected_return, 1),
                "difficulty": round(difficulty, 1),
                "time_window": round(time_window, 1),
                "capital_required": round(capital, 1),
                "composite_score": round(composite, 1),
                "risk_tier": self._assign_tier(composite),
            })

        # 评分交易所活动
        for c in exchange_data.get("campaigns", []):
            ev = c.get("estimated_value", "")
            certainty = 8 if c.get("recurring") else 6
            expected_return = self._estimate_return_from_str(ev)
            diff_map = {"easy": 2, "medium": 5, "hard": 8}
            difficulty = diff_map.get(c.get("difficulty", "medium"), 5)
            time_window = 8 if c.get("status") == "active" else 3
            capital = self._estimate_capital_from_str(c.get("capital_required", ""))

            composite = self._weighted_score(certainty, expected_return, difficulty, time_window, capital)
            scored.append({
                "name": c["name"],
                "source": "exchange",
                "source_label": c["exchange"],
                "detail": f"{c['type']} | {c['estimated_value']}",
                "url": c.get("url", ""),
                "certainty": round(certainty, 1),
                "expected_return": round(expected_return, 1),
                "difficulty": round(difficulty, 1),
                "time_window": round(time_window, 1),
                "capital_required": round(capital, 1),
                "composite_score": round(composite, 1),
                "risk_tier": self._assign_tier(composite),
            })

        # 评分链上打新
        for lp in launchpad_data.get("projects", []):
            certainty = 5
            if lp.get("status") == "active":
                certainty = 7
            elif lp.get("status") == "upcoming":
                certainty = 4
            expected_return = 6  # 中等预期
            difficulty = 5
            time_window = 7 if lp.get("status") == "active" else 4
            capital = 4

            composite = self._weighted_score(certainty, expected_return, difficulty, time_window, capital)
            scored.append({
                "name": lp["project_name"],
                "source": "launchpad",
                "source_label": lp["platform"],
                "detail": f"{lp['chain']} | {lp.get('estimated_allocation', 'N/A')}",
                "url": lp.get("participation_link", ""),
                "certainty": round(certainty, 1),
                "expected_return": round(expected_return, 1),
                "difficulty": round(difficulty, 1),
                "time_window": round(time_window, 1),
                "capital_required": round(capital, 1),
                "composite_score": round(composite, 1),
                "risk_tier": self._assign_tier(composite),
            })

        # 按综合评分排序
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        # 统计各风险层级数量
        tier_counts = {"确定赚钱": 0, "必做": 0, "高潜力": 0, "探索性": 0}
        for s in scored:
            tier = s["risk_tier"]
            if tier in tier_counts:
                tier_counts[tier] += 1

        result = {
            "opportunities": scored,
            "tier_counts": tier_counts,
            "total_count": len(scored),
            "update_time": datetime.now().isoformat(),
        }
        _set_cached("opportunity_scores", result)
        return result

    def _weighted_score(self, certainty: float, expected_return: float,
                        difficulty: float, time_window: float, capital: float) -> float:
        """加权综合评分 (difficulty和capital是越低越好，需要反转)"""
        # 权重：确定性30%, 预期收益25%, 难度20%, 时间窗口15%, 资金需求10%
        # difficulty和capital是反向指标（越低越好），用10减去
        w_certainty = certainty * 0.30
        w_return = expected_return * 0.25
        w_difficulty = (10 - difficulty) * 0.20
        w_time = time_window * 0.15
        w_capital = (10 - capital) * 0.10
        return w_certainty + w_return + w_difficulty + w_time + w_capital

    def _assign_tier(self, composite: float) -> str:
        """根据综合评分分配风险层级"""
        if composite >= 7.0:
            return "确定赚钱"
        elif composite >= 5.5:
            return "必做"
        elif composite >= 4.0:
            return "高潜力"
        else:
            return "探索性"

    def _estimate_return(self, source: str, tvl: float) -> float:
        """估算预期收益 (0-10)"""
        tvl_m = tvl / 1e6 if tvl > 1000 else tvl
        if tvl_m >= 1000:
            return 8
        elif tvl_m >= 500:
            return 7
        elif tvl_m >= 200:
            return 6
        elif tvl_m >= 100:
            return 5
        elif tvl_m >= 50:
            return 4
        return 3

    def _estimate_return_from_str(self, value_str: str) -> float:
        """从字符串估算预期收益"""
        if not value_str:
            return 3
        import re
        nums = re.findall(r'\d+', value_str.replace(',', ''))
        if not nums:
            return 3
        max_val = max(int(n) for n in nums)
        if max_val >= 500:
            return 9
        elif max_val >= 200:
            return 7
        elif max_val >= 100:
            return 6
        elif max_val >= 50:
            return 5
        elif max_val >= 20:
            return 4
        return 3

    def _estimate_capital(self, amount: float) -> float:
        """估算资金需求 (0-10, 越低越好)"""
        if amount <= 0:
            return 2  # 无强制要求
        elif amount <= 100:
            return 3
        elif amount <= 500:
            return 5
        elif amount <= 1000:
            return 7
        return 9

    def _estimate_capital_from_str(self, capital_str: str) -> float:
        """从字符串估算资金需求"""
        if not capital_str:
            return 3
        import re
        nums = re.findall(r'\d+', capital_str.replace(',', ''))
        if not nums:
            return 3
        min_val = min(int(n) for n in nums)
        if min_val <= 50:
            return 2
        elif min_val <= 100:
            return 3
        elif min_val <= 500:
            return 5
        elif min_val <= 1000:
            return 7
        elif min_val <= 2000:
            return 8
        return 9
