"""
微信公众号日报服务
通过微信读书 API 代理抓取关注的公众号文章，提取正文，生成 AI 摘要

数据源：https://weread.111965.xyz（微信读书 API 代理）
存储：JSON 文件（backend/data/wechat_*.json）
"""

import json
import os
import re
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ==================== 路径配置 ====================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
AUTH_FILE = os.path.join(DATA_DIR, "wechat_auth.json")
CONFIG_FILE = os.path.join(DATA_DIR, "wechat_config.json")
ARTICLES_DIR = os.path.join(DATA_DIR, "wechat_articles")

# ==================== 默认配置 ====================

DEFAULT_CONFIG = {
    "wereadApiBase": "https://weread.111965.xyz",
    "accounts": [],
    "maxArticlesPerAccount": 20,
    "retryMaxAttempts": 5,
    "retryDelayMs": 400,
    "syncDays": 2,
}

# ==================== 缓存 ====================

_cache: dict = {}
CACHE_TTL_SHORT = 300       # 5分钟
CACHE_TTL_MEDIUM = 1800     # 30分钟
CACHE_TTL_LONG = 3600       # 1小时


def _get_cached(key: str, ttl: int = CACHE_TTL_LONG):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < ttl:
            return val
    return None


def _set_cached(key: str, val):
    _cache[key] = (val, time.time())


# ==================== 文件工具 ====================

def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(ARTICLES_DIR, exist_ok=True)


def _load_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def _save_json(path: str, data):
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 认证管理 ====================

def _load_auth() -> Optional[Dict[str, str]]:
    return _load_json(AUTH_FILE, None)


def _save_auth(auth: Dict[str, str]):
    _save_json(AUTH_FILE, auth)


def _get_auth_headers() -> Dict[str, str]:
    auth = _load_auth()
    if not auth or not auth.get("vid") or not auth.get("token"):
        raise ValueError("未登录，请先扫码登录微信读书")
    return {
        "xid": str(auth["vid"]),
        "Authorization": f"Bearer {auth['token']}",
        "Content-Type": "application/json",
    }


# ==================== 配置管理 ====================

def _load_config() -> Dict[str, Any]:
    config = _load_json(CONFIG_FILE, {})
    # 合并默认值
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
    return config


def _save_config(config: Dict[str, Any]):
    _save_json(CONFIG_FILE, config)


# ==================== HTTP 工具 ====================

def _get_api_base() -> str:
    config = _load_config()
    return config.get("wereadApiBase", "https://weread.111965.xyz")


def _fetch_with_retry(url: str, headers: Optional[Dict] = None,
                      method: str = "GET", json_data: Optional[Dict] = None,
                      allow_empty: bool = False) -> Any:
    """带重试的 HTTP 请求"""
    config = _load_config()
    max_attempts = config.get("retryMaxAttempts", 5)
    retry_delay = config.get("retryDelayMs", 400) / 1000.0

    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=15) as client:
                if method == "GET":
                    resp = client.get(url, headers=headers)
                else:
                    resp = client.post(url, headers=headers, json=json_data)

                resp.raise_for_status()
                data = resp.json()

                # 空数组也重试
                if not allow_empty and isinstance(data, list) and len(data) == 0 and attempt < max_attempts:
                    logger.debug(f"响应为空，第 {attempt}/{max_attempts} 次重试...")
                    time.sleep(retry_delay)
                    continue

                return data
        except Exception as e:
            if attempt == max_attempts:
                raise RuntimeError(f"请求失败（已重试 {max_attempts} 次）: {e}")
            logger.debug(f"请求出错，第 {attempt}/{max_attempts} 次重试: {e}")
            time.sleep(retry_delay)


def _polite_delay():
    """礼貌延迟 300ms"""
    time.sleep(0.3)


# ==================== 核心服务 ====================

class WechatDigestService:
    """微信公众号日报服务"""

    # 临时存储 uuid → scanUrl 映射（登录流程中使用）
    _login_urls: Dict[str, str] = {}

    # ---- 登录流程 ----

    def login_start(self) -> Dict[str, str]:
        """发起登录，返回 uuid 和二维码链接"""
        api_base = _get_api_base()
        data = _fetch_with_retry(f"{api_base}/api/v2/login/platform", allow_empty=True)
        uuid = data.get("uuid") if isinstance(data, dict) else None
        if not uuid:
            raise RuntimeError("获取 uuid 失败")
        # 优先使用 API 返回的 scanUrl，如果没有则用默认链接
        qr_url = data.get("scanUrl") or f"https://login.weixin.qq.com/l/{uuid}"
        # 保存 scanUrl 供后续生成二维码使用
        self._login_urls[uuid] = qr_url
        return {"uuid": uuid, "qr_url": qr_url}

    def login_qr_image(self, uuid: str) -> str:
        """生成二维码图片，返回 base64 编码的 PNG"""
        import qrcode
        import io
        import base64

        # 使用 login_start 时保存的 scanUrl
        qr_url = self._login_urls.get(uuid) or f"https://login.weixin.qq.com/l/{uuid}"

        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def login_check(self, uuid: str) -> Dict[str, Any]:
        """轮询登录结果"""
        api_base = _get_api_base()
        try:
            data = _fetch_with_retry(
                f"{api_base}/api/v2/login/platform/{uuid}",
                allow_empty=True
            )
            if isinstance(data, dict) and data.get("vid") and data.get("token"):
                _save_auth({"vid": data["vid"], "token": data["token"]})
                # 同步公众号列表
                try:
                    self.sync_accounts()
                except Exception as e:
                    logger.warning(f"同步公众号列表失败: {e}")
                return {"status": "ok", "vid": data["vid"]}
            return {"status": "waiting"}
        except Exception:
            return {"status": "waiting"}

    def get_login_status(self) -> Dict[str, Any]:
        """检查登录状态"""
        auth = _load_auth()
        if not auth or not auth.get("vid"):
            return {"logged_in": False}
        return {"logged_in": True, "vid": auth["vid"]}

    def logout(self):
        """退出登录"""
        if os.path.exists(AUTH_FILE):
            os.remove(AUTH_FILE)
        _cache.clear()

    # ---- 公众号管理 ----

    def sync_accounts(self) -> List[Dict[str, str]]:
        """获取已关注的公众号列表"""
        api_base = _get_api_base()
        headers = _get_auth_headers()

        data = _fetch_with_retry(f"{api_base}/api/v2/platform/mps", headers=headers)
        mps = data if isinstance(data, list) else (data.get("mps") or data.get("data") or [])

        # 更新配置
        config = _load_config()
        config["accounts"] = [
            {"mpId": mp.get("mpId") or mp.get("id", ""), "name": mp.get("name") or mp.get("mpName", "")}
            for mp in mps
        ]
        _save_config(config)

        return config["accounts"]

    def get_accounts(self) -> List[Dict[str, str]]:
        """获取已保存的公众号列表"""
        config = _load_config()
        accounts = config.get("accounts", [])
        # 补充最后同步时间
        for acc in accounts:
            mp_id = acc.get("mpId", "")
            articles = self._read_articles_file(mp_id)
            if articles:
                acc["lastSync"] = articles[0].get("fetchedAt", "")
                acc["articleCount"] = len(articles)
            else:
                acc["lastSync"] = ""
                acc["articleCount"] = 0
        return accounts

    # ---- 文章同步 ----

    def sync_articles(self, mp_id: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
        """同步文章（增量）"""
        config = _load_config()
        sync_days = days or config.get("syncDays", 2)
        accounts = config.get("accounts", [])

        if not accounts:
            # 尝试先同步公众号列表
            try:
                accounts = self.sync_accounts()
            except Exception:
                return {"error": "未找到已关注的公众号", "synced": 0}

        if mp_id:
            # 只同步指定公众号
            target_accounts = [a for a in accounts if a.get("mpId") == mp_id]
            if not target_accounts:
                return {"error": f"未找到公众号 {mp_id}", "synced": 0}
        else:
            target_accounts = accounts

        total_new = 0
        total_skipped = 0
        failed = []
        results = []

        api_base = _get_api_base()
        headers = _get_auth_headers()
        cutoff_time = int((datetime.now() - timedelta(days=sync_days)).timestamp())

        for i, acc in enumerate(target_accounts):
            mp_id_cur = acc.get("mpId", "")
            mp_name = acc.get("name", mp_id_cur)

            try:
                # 拉取文章列表（最多 2 页 = 40 篇）
                all_articles = []
                for page in range(2):
                    _polite_delay()
                    data = _fetch_with_retry(
                        f"{api_base}/api/v2/platform/mps/{mp_id_cur}/articles?page={page}",
                        headers=headers
                    )
                    articles = data if isinstance(data, list) else (data.get("articles") or data.get("data") or [])
                    if not articles:
                        break
                    all_articles.extend(articles)

                # 过滤近 N 天
                recent = [a for a in all_articles if (a.get("createTime") or 0) >= cutoff_time]
                if not recent:
                    results.append({"mpId": mp_id_cur, "name": mp_name, "new": 0})
                    continue

                # 去重 + 提取正文
                existing_urls = set(a["url"] for a in self._read_articles_file(mp_id_cur))
                new_count = 0

                for article in recent:
                    url = article.get("url") or f"https://mp.weixin.qq.com/s/{article.get('articleId', '')}"
                    if url in existing_urls:
                        total_skipped += 1
                        continue

                    _polite_delay()
                    content = self._extract_article_content(url)

                    article_obj = {
                        "title": article.get("title", "未知标题"),
                        "url": url,
                        "publishedAt": article.get("createTime", int(time.time())),
                        "fetchedAt": int(time.time()),
                        "content": content,
                        "mpId": mp_id_cur,
                        "mpName": mp_name,
                        "summary": self._generate_summary(content),
                    }

                    self._append_article(mp_id_cur, article_obj)
                    new_count += 1
                    total_new += 1

                results.append({"mpId": mp_id_cur, "name": mp_name, "new": new_count})

            except Exception as e:
                logger.warning(f"同步 {mp_name} 失败: {e}")
                failed.append(mp_name)

        # 清除缓存
        _cache.pop("wechat_digest_daily", None)
        _cache.pop("wechat_articles_all", None)

        return {
            "synced": total_new,
            "skipped": total_skipped,
            "failed": failed,
            "details": results,
            "syncDays": sync_days,
        }

    # ---- 文章查询 ----

    def get_articles(self, days: Optional[int] = None, mp_id: Optional[str] = None) -> List[Dict]:
        """获取文章列表"""
        config = _load_config()
        target_days = days or config.get("syncDays", 2)
        cutoff = int((datetime.now() - timedelta(days=target_days)).timestamp())

        all_articles = []
        if mp_id:
            files = [f"{mp_id}.json"]
        else:
            _ensure_dirs()
            files = [f for f in os.listdir(ARTICLES_DIR) if f.endswith(".json")]

        for fname in files:
            mp_id_cur = fname.replace(".json", "")
            articles = self._read_articles_file(mp_id_cur)
            for a in articles:
                if (a.get("publishedAt") or a.get("fetchedAt") or 0) >= cutoff:
                    all_articles.append(a)

        all_articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
        return all_articles

    # ---- AI 摘要 ----

    def generate_daily_digest(self, days: Optional[int] = None) -> Dict[str, Any]:
        """生成每日日报（含 AI 摘要）"""
        cache_key = "wechat_digest_daily"
        cached = _get_cached(cache_key, CACHE_TTL_MEDIUM)
        if cached and not days:
            return cached

        config = _load_config()
        target_days = days or config.get("syncDays", 2)
        articles = self.get_articles(days=target_days)

        if not articles:
            return {
                "title": f"微信公众号日报 - {datetime.now().strftime('%Y-%m-%d')}",
                "groups": [],
                "totalArticles": 0,
                "totalAccounts": 0,
                "update_time": datetime.now().isoformat(),
            }

        # 按公众号分组
        groups_map: Dict[str, List] = {}
        for a in articles:
            key = a.get("mpName") or a.get("mpId", "未知")
            groups_map.setdefault(key, []).append(a)

        groups = []
        for mp_name, mp_articles in groups_map.items():
            mp_articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
            items = []
            for a in mp_articles:
                items.append({
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "publishedAt": a.get("publishedAt"),
                    "publishedDate": self._format_timestamp(a.get("publishedAt")),
                    "summary": a.get("summary") or self._generate_summary(a.get("content", "")),
                    "keyPoints": self._extract_key_points(a.get("content", "")),
                    "mpName": a.get("mpName", mp_name),
                })
            groups.append({
                "mpName": mp_name,
                "mpId": mp_articles[0].get("mpId", ""),
                "count": len(items),
                "items": items,
            })

        # 按文章数排序
        groups.sort(key=lambda g: g["count"], reverse=True)

        result = {
            "title": f"微信公众号日报 - {datetime.now().strftime('%Y-%m-%d')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "groups": groups,
            "totalArticles": len(articles),
            "totalAccounts": len(groups),
            "update_time": datetime.now().isoformat(),
        }

        _set_cached(cache_key, result)
        return result

    # ---- 内部工具 ----

    def _read_articles_file(self, mp_id: str) -> List[Dict]:
        path = os.path.join(ARTICLES_DIR, f"{mp_id}.json")
        return _load_json(path, [])

    def _append_article(self, mp_id: str, article: Dict):
        """追加文章到文件（自动去重 + 限制数量）"""
        _ensure_dirs()
        config = _load_config()
        max_articles = config.get("maxArticlesPerAccount", 20)

        articles = self._read_articles_file(mp_id)
        existing_urls = {a["url"] for a in articles}

        if article["url"] in existing_urls:
            return

        articles.insert(0, article)
        articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
        articles = articles[:max_articles]

        path = os.path.join(ARTICLES_DIR, f"{mp_id}.json")
        _save_json(path, articles)

    def _extract_article_content(self, url: str) -> str:
        """提取微信文章正文（双重方案）"""
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                html = resp.text

            # 方案1：正则提取 content_noencode
            match = re.search(r'var\s+content_noencode\s*=\s*"([\s\S]*?)";', html)
            if match:
                content = match.group(1)
                content = content.replace('\\n', '\n').replace('\\t', '\t')
                content = content.replace('\\"', '"').replace('\\\\', '\\')
                content = re.sub(r'<[^>]+>', '', content)  # 去 HTML 标签
                return content.strip()

            # 方案2：BeautifulSoup 解析 #js_content
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                js_content = soup.find(id="js_content")
                if js_content:
                    return js_content.get_text(separator="\n", strip=True)

                # 备选位置
                for selector in ["article", ".rich_media_content", "#page-content"]:
                    el = soup.select_one(selector)
                    if el:
                        text = el.get_text(separator="\n", strip=True)
                        if len(text) > 50:
                            return text
            except ImportError:
                logger.warning("beautifulsoup4 未安装，无法使用方案2")

            return "（无法提取正文）"
        except Exception as e:
            logger.warning(f"提取正文失败 {url}: {e}")
            return "（提取失败）"

    def _generate_summary(self, content: str, max_len: int = 200) -> str:
        """生成摘要（提取式：取前 N 字）"""
        if not content or content in ("（无法提取正文）", "（提取失败）"):
            return "（无摘要）"
        cleaned = re.sub(r'\s+', ' ', content).strip()
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[:max_len] + "..."

    def _extract_key_points(self, content: str, max_points: int = 3) -> List[str]:
        """提取关键要点（基于句子权重）"""
        if not content or len(content) < 50:
            return []

        # 按句号/换行分句
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

        if not sentences:
            return []

        # 关键词权重
        high_weight = [
            "关键", "重要", "核心", "必须", "建议", "注意", "风险", "机会",
            "趋势", "突破", "增长", "下降", "利润", "亏损", "营收", "市值",
            "政策", "监管", "利率", "通胀", "就业", "GDP", "PMI", "CPI",
            "投资", "融资", "并购", "上市", "退市", "分红", "回购",
        ]

        medium_weight = [
            "数据", "报告", "分析", "预测", "预计", "认为", "表示",
            "行业", "市场", "板块", "个股", "基金", "债券",
        ]

        scored = []
        for s in sentences[:50]:  # 只评前50句
            score = 0
            s_lower = s.lower()
            # 长度适中的句子加分
            if 30 <= len(s) <= 150:
                score += 2
            # 含数字/百分比加分
            if re.search(r'\d+[\.\d]*[%％亿万]', s):
                score += 3
            # 关键词加分
            for kw in high_weight:
                if kw in s:
                    score += 3
            for kw in medium_weight:
                if kw in s:
                    score += 1
            # 含引语加分
            if '"' in s or '"' in s or '「' in s:
                score += 1
            scored.append((score, s))

        # 取得分最高的 N 句
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:max_points]]

    def _format_timestamp(self, ts: Optional[int]) -> str:
        if not ts:
            return ""
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return ""


# 单例
wechat_digest_service = WechatDigestService()
