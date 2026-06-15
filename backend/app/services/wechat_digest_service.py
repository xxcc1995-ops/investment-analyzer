"""
微信公众号日报服务
管理公众号文章，提取正文，生成 AI 摘要

存储：JSON 文件（backend/data/wechat_*.json）
文章获取：直接抓取微信公众号文章页面（mp.weixin.qq.com）
"""

import json
import os
import re
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

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
    "syncDays": 7,
}

# ==================== 缓存 ====================

_cache: dict = {}
_lock = threading.Lock()

def _get_cached(key: str, ttl: int = 60):
    with _lock:
        if key in _cache:
            val, ts = _cache[key]
            if time.time() - ts < ttl:
                return val
    return None

def _set_cached(key: str, val):
    with _lock:
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

# ==================== 配置管理 ====================

def _load_config() -> Dict[str, Any]:
    config = _load_json(CONFIG_FILE, {})
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
    return config

def _save_config(config: Dict[str, Any]):
    _save_json(CONFIG_FILE, config)

# ==================== 核心服务 ====================

class WechatDigestService:
    """微信公众号日报服务"""

    _login_urls: Dict[str, str] = {}

    # ---- 登录流程 ----

    def login_start(self) -> Dict[str, str]:
        """发起登录，返回 uuid 和二维码链接"""
        config = _load_config()
        api_base = config.get("wereadApiBase", "https://weread.111965.xyz")
        try:
            with httpx.Client(timeout=8) as client:
                resp = client.get(f"{api_base}/api/v2/login/platform")
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise RuntimeError(f"连接微信读书代理失败: {e}")
        uuid = data.get("uuid") if isinstance(data, dict) else None
        if not uuid:
            raise RuntimeError("获取 uuid 失败")
        qr_url = data.get("scanUrl") or f"https://login.weixin.qq.com/l/{uuid}"
        self._login_urls[uuid] = qr_url
        return {"uuid": uuid, "qr_url": qr_url}

    def login_check(self, uuid: str) -> Dict[str, Any]:
        """轮询登录结果"""
        config = _load_config()
        api_base = config.get("wereadApiBase", "https://weread.111965.xyz")
        try:
            with httpx.Client(timeout=8) as client:
                resp = client.get(f"{api_base}/api/v2/login/platform/{uuid}")
                resp.raise_for_status()
                data = resp.json()
            if isinstance(data, dict) and data.get("vid") and data.get("token"):
                _save_auth({"vid": str(data["vid"]), "token": data["token"]})
                return {"status": "ok", "vid": data["vid"]}
        except Exception:
            pass
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
        with _lock:
            _cache.clear()

    # ---- 公众号管理（手动添加） ----

    def get_accounts(self) -> List[Dict[str, Any]]:
        """获取已保存的公众号列表（从配置 + 文章文件自动发现）"""
        cached = _get_cached("accounts", 300)
        if cached is not None:
            return cached
        config = _load_config()
        accounts = list(config.get("accounts", []))

        # 从文章文件自动发现未注册的公众号
        known_ids = {a.get("mpId") for a in accounts}
        if os.path.exists(ARTICLES_DIR):
            for fname in os.listdir(ARTICLES_DIR):
                if not fname.endswith(".json"):
                    continue
                mp_id = fname.replace(".json", "")
                if mp_id in known_ids:
                    continue
                articles = self._read_articles_file(mp_id)
                if articles:
                    name = articles[0].get("mpName", mp_id)
                    accounts.append({"mpId": mp_id, "name": name, "autoDiscovered": True})

        for acc in accounts:
            mp_id = acc.get("mpId", "")
            articles = self._read_articles_file(mp_id)
            acc["articleCount"] = len(articles)
            acc["lastSync"] = articles[0].get("fetchedAt", "") if articles else ""
        _set_cached("accounts", accounts)
        return accounts

    def add_account(self, name: str, mp_id: str) -> Dict[str, Any]:
        """手动添加公众号"""
        if not name or not mp_id:
            raise ValueError("名称和ID不能为空")
        config = _load_config()
        accounts = config.get("accounts", [])
        if any(a.get("mpId") == mp_id for a in accounts):
            return {"ok": True, "message": "已存在"}
        accounts.append({"mpId": mp_id, "name": name})
        config["accounts"] = accounts
        _save_config(config)
        with _lock:
            _cache.pop("accounts", None)
        return {"ok": True}

    def remove_account(self, mp_id: str) -> Dict[str, Any]:
        """删除公众号"""
        config = _load_config()
        config["accounts"] = [a for a in config.get("accounts", []) if a.get("mpId") != mp_id]
        _save_config(config)
        with _lock:
            _cache.pop("accounts", None)
        return {"ok": True}

    # ---- 文章管理（通过 URL 手动添加） ----

    def add_article_by_url(self, url: str, mp_name: str = "", mp_id: str = "") -> Dict[str, Any]:
        """通过微信文章链接添加文章"""
        if not url or "mp.weixin.qq.com" not in url:
            raise ValueError("请输入有效的微信公众号文章链接")

        # 检查是否已存在
        for fname in os.listdir(ARTICLES_DIR) if os.path.exists(ARTICLES_DIR) else []:
            if fname.endswith(".json"):
                articles = self._read_articles_file(fname.replace(".json", ""))
                if any(a.get("url") == url for a in articles):
                    return {"ok": True, "message": "文章已存在", "duplicate": True}

        # 提取正文
        title, content = self._extract_article_content(url)

        if not mp_id:
            mp_id = f"manual_{int(time.time())}"
        if not mp_name:
            mp_name = "手动添加"

        article_obj = {
            "title": title or "未知标题",
            "url": url,
            "publishedAt": int(time.time()),
            "fetchedAt": int(time.time()),
            "content": content,
            "mpId": mp_id,
            "mpName": mp_name,
            "summary": self._generate_summary(content),
        }

        self._append_article(mp_id, article_obj)

        # 自动注册公众号（如果不存在）
        config = _load_config()
        accounts = config.get("accounts", [])
        if not any(a.get("mpId") == mp_id for a in accounts):
            accounts.append({"mpId": mp_id, "name": mp_name})
            config["accounts"] = accounts
            _save_config(config)

        with _lock:
            _cache.pop("wechat_digest_daily", None)
            _cache.pop("accounts", None)

        return {"ok": True, "title": title, "mpId": mp_id}

    def add_articles_batch(self, urls: List[str], mp_name: str = "", mp_id: str = "") -> Dict[str, Any]:
        """批量添加文章"""
        results = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            try:
                r = self.add_article_by_url(url, mp_name=mp_name, mp_id=mp_id)
                results.append({"url": url, "ok": True, "title": r.get("title", "")})
            except Exception as e:
                results.append({"url": url, "ok": False, "error": str(e)})
        return {"results": results, "total": len(results)}

    # ---- 文章查询 ----

    def get_articles(self, days: Optional[int] = None, mp_id: Optional[str] = None) -> List[Dict]:
        """获取文章列表（从本地 JSON 读取，瞬间返回）"""
        cache_key = f"articles_{days}_{mp_id}"
        cached = _get_cached(cache_key, 30)
        if cached is not None:
            return cached

        config = _load_config()
        target_days = days or config.get("syncDays", 7)
        cutoff = int((datetime.now() - timedelta(days=target_days)).timestamp())

        all_articles = []
        if not os.path.exists(ARTICLES_DIR):
            return []

        if mp_id:
            files = [f"{mp_id}.json"]
        else:
            files = [f for f in os.listdir(ARTICLES_DIR) if f.endswith(".json")]

        for fname in files:
            mp_id_cur = fname.replace(".json", "")
            articles = self._read_articles_file(mp_id_cur)
            for a in articles:
                ts = a.get("publishedAt") or a.get("fetchedAt") or 0
                if ts >= cutoff:
                    all_articles.append(a)

        all_articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
        _set_cached(cache_key, all_articles)
        return all_articles

    # ---- 日报生成 ----

    def generate_daily_digest(self, days: Optional[int] = None) -> Dict[str, Any]:
        """生成每日日报（从本地数据，瞬间返回）"""
        cache_key = "wechat_digest_daily"
        cached = _get_cached(cache_key, 60)
        if cached and not days:
            return cached

        articles = self.get_articles(days=days)

        if not articles:
            return {
                "title": f"微信公众号日报 - {datetime.now().strftime('%Y-%m-%d')}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "groups": [],
                "totalArticles": 0,
                "totalAccounts": 0,
                "update_time": datetime.now().isoformat(),
            }

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

    def _extract_article_content(self, url: str) -> tuple:
        """提取微信文章标题和正文，返回 (title, content)"""
        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                html = resp.text

            # 提取标题
            title = ""
            title_match = re.search(r'var\s+msg_title\s*=\s*["\']([^"\']+)["\']', html)
            if title_match:
                title = title_match.group(1).strip()
            if not title:
                title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            if not title:
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

            # 方案1：正则提取 content_noencode
            match = re.search(r'var\s+content_noencode\s*=\s*"([\s\S]*?)";', html)
            if match:
                content = match.group(1)
                content = content.replace('\\n', '\n').replace('\\t', '\t')
                content = content.replace('\\"', '"').replace('\\\\', '\\')
                content = re.sub(r'<[^>]+>', '', content)
                return title, content.strip()

            # 方案2：BeautifulSoup
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                js_content = soup.find(id="js_content")
                if js_content:
                    return title, js_content.get_text(separator="\n", strip=True)
                for sel in ["article", ".rich_media_content"]:
                    el = soup.select_one(sel)
                    if el:
                        text = el.get_text(separator="\n", strip=True)
                        if len(text) > 50:
                            return title, text
            except ImportError:
                pass

            return title, "（无法提取正文）"
        except Exception as e:
            logger.warning(f"提取正文失败 {url}: {e}")
            return "", "（提取失败）"

    def _generate_summary(self, content: str, max_len: int = 200) -> str:
        if not content or content in ("（无法提取正文）", "（提取失败）"):
            return "（无摘要）"
        cleaned = re.sub(r'\s+', ' ', content).strip()
        return cleaned if len(cleaned) <= max_len else cleaned[:max_len] + "..."

    def _extract_key_points(self, content: str, max_points: int = 3) -> List[str]:
        if not content or len(content) < 50:
            return []
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
        if not sentences:
            return []
        high_kw = ["关键", "重要", "核心", "必须", "建议", "注意", "风险", "机会",
                    "趋势", "突破", "增长", "下降", "利润", "亏损", "营收", "市值",
                    "政策", "监管", "利率", "通胀", "投资", "融资", "并购", "分红"]
        scored = []
        for s in sentences[:50]:
            score = 0
            if 30 <= len(s) <= 150:
                score += 2
            if re.search(r'\d+[\.\d]*[%％亿万]', s):
                score += 3
            for kw in high_kw:
                if kw in s:
                    score += 3
                    break
            scored.append((score, s))
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
