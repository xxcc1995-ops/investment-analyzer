"""
微信公众号日报服务
通过微信读书 API 获取已关注公众号文章，生成 AI 摘要

认证方式：浏览器 cookie（wr_vid + wr_skey）
获取方式：从 weread.qq.com 的 /web/shelf/sync 和 /web/mp/articles 接口
"""

import json
import os
import re
import time
import html as html_mod
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ==================== 路径 ====================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
COOKIE_FILE = os.path.join(DATA_DIR, "wechat_cookie.json")
ARTICLES_DIR = os.path.join(DATA_DIR, "wechat_articles")
CONFIG_FILE = os.path.join(DATA_DIR, "wechat_config.json")

WEREAD_HOST = "https://weread.qq.com"

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

def _clear_cache(*keys):
    with _lock:
        for k in keys:
            _cache.pop(k, None)

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

# ==================== Cookie 管理 ====================

def _load_cookie() -> Optional[Dict[str, str]]:
    return _load_json(COOKIE_FILE, None)

def _save_cookie(cookie: Dict[str, str]):
    _save_json(COOKIE_FILE, cookie)

def _get_cookie_str() -> str:
    cookie = _load_cookie()
    if not cookie:
        raise ValueError("未设置 cookie，请先登录微信读书")
    parts = []
    for k, v in cookie.items():
        parts.append(f"{k}={v}")
    return "; ".join(parts)

# ==================== 配置 ====================

DEFAULT_CONFIG = {"syncDays": 3, "maxArticlesPerAccount": 30}

def _load_config() -> Dict[str, Any]:
    config = _load_json(CONFIG_FILE, {})
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
    return config

def _save_config(config: Dict[str, Any]):
    _save_json(CONFIG_FILE, config)

# ==================== Weread API ====================

def _weread_api(path: str, params: Dict = None) -> Any:
    """调用 weread.qq.com API"""
    url = f"{WEREAD_HOST}{path}"
    cookie_str = _get_cookie_str()
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if isinstance(data, dict):
        err_code = data.get("errCode") or data.get("errcode")
        if err_code and err_code != 0:
            err_msg = data.get("errMsg") or data.get("errmsg") or ""
            if any(k in err_msg for k in ["用户不存在", "登录", "token", "过期"]):
                raise ValueError(f"cookie 已过期: {err_msg}")
            raise RuntimeError(f"API 错误: {err_msg} (code={err_code})")
    return data

# ==================== 核心服务 ====================

class WechatDigestService:

    # ---- Cookie 登录 ----

    def set_cookie(self, cookie_str: str) -> Dict[str, Any]:
        """设置 cookie（从浏览器 DevTools 复制）"""
        cookie = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookie[k.strip()] = v.strip()
        if "wr_vid" not in cookie:
            raise ValueError("cookie 中缺少 wr_vid，请确认已登录 weread.qq.com")
        _save_cookie(cookie)
        _clear_cache("shelf", "accounts")
        return {"ok": True, "vid": cookie.get("wr_vid")}

    def set_cookie_direct(self, vid: str, skey: str) -> Dict[str, Any]:
        """直接设置 vid 和 skey"""
        if not vid or not skey:
            raise ValueError("vid 和 skey 不能为空")
        _save_cookie({"wr_vid": vid, "wr_skey": skey})
        _clear_cache("shelf", "accounts")
        return {"ok": True, "vid": vid}

    def get_login_status(self) -> Dict[str, Any]:
        cookie = _load_cookie()
        if not cookie or not cookie.get("wr_vid"):
            return {"logged_in": False}
        # 尝试调用 API 验证 cookie 是否有效
        try:
            _weread_api("/web/shelf/sync", {"userVid": "", "synckey": 0})
            return {"logged_in": True, "vid": cookie["wr_vid"], "valid": True}
        except ValueError:
            return {"logged_in": True, "vid": cookie["wr_vid"], "valid": False, "expired": True}
        except Exception:
            return {"logged_in": True, "vid": cookie["wr_vid"], "valid": False}

    def logout(self):
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        _clear_cache("shelf", "accounts")

    # ---- 自动提取 cookie ----

    def try_extract_cookie(self) -> Dict[str, Any]:
        """尝试从浏览器自动提取 cookie"""
        try:
            import browser_cookie3
        except ImportError:
            return {"ok": False, "error": "需要 browser-cookie3 库"}

        browsers = [
            ("chrome", "Chrome"),
            ("edge", "Edge"),
            ("brave", "Brave"),
        ]
        for fn_name, name in browsers:
            try:
                loader = getattr(browser_cookie3, fn_name, None)
                if not loader:
                    continue
                cookies = loader(domain_name="weread.qq.com")
                cookie_dict = {}
                for c in cookies:
                    if c.name in ("wr_vid", "wr_skey"):
                        cookie_dict[c.name] = c.value
                if "wr_vid" in cookie_dict and "wr_skey" in cookie_dict:
                    _save_cookie(cookie_dict)
                    _clear_cache("shelf", "accounts")
                    return {"ok": True, "vid": cookie_dict["wr_vid"], "browser": name}
            except Exception:
                continue
        return {"ok": False, "error": "未能从浏览器提取 cookie，请手动设置"}

    # ---- 公众号列表 ----

    def get_shelf(self) -> List[Dict]:
        """获取书架（含公众号）"""
        cached = _get_cached("shelf", 300)
        if cached is not None:
            return cached
        data = _weread_api("/web/shelf/sync", {"userVid": "", "synckey": 0})
        books = data.get("books", [])
        _set_cached("shelf", books)
        return books

    def get_accounts(self) -> List[Dict[str, Any]]:
        """获取已关注的公众号列表"""
        cached = _get_cached("accounts", 300)
        if cached is not None:
            return cached
        try:
            books = self.get_shelf()
        except Exception:
            # fallback: 从本地文章文件发现
            return self._discover_accounts_from_files()
        mps = []
        for b in books:
            book_id = b.get("bookId", "")
            if isinstance(book_id, str) and book_id.startswith("MP_WXS_"):
                articles = self._read_articles_file(book_id)
                mps.append({
                    "mpId": book_id,
                    "name": b.get("title", ""),
                    "cover": b.get("cover", ""),
                    "articleCount": len(articles),
                    "lastSync": articles[0].get("fetchedAt", "") if articles else "",
                })
        _set_cached("accounts", mps)
        return mps

    def _discover_accounts_from_files(self) -> List[Dict[str, Any]]:
        """从本地文章文件发现公众号"""
        if not os.path.exists(ARTICLES_DIR):
            return []
        mps = []
        for fname in os.listdir(ARTICLES_DIR):
            if not fname.endswith(".json"):
                continue
            mp_id = fname.replace(".json", "")
            articles = self._read_articles_file(mp_id)
            if articles:
                mps.append({
                    "mpId": mp_id,
                    "name": articles[0].get("mpName", mp_id),
                    "articleCount": len(articles),
                    "lastSync": articles[0].get("fetchedAt", "") if articles else "",
                })
        return mps

    # ---- 文章同步 ----

    def _sync_one_account(self, acc: Dict, limit: int) -> Dict:
        """同步单个公众号"""
        book_id = acc["mpId"]
        mp_name = acc["name"]
        try:
            articles = self._fetch_mp_articles(book_id, limit=limit)
            new_count = 0
            for a in articles:
                url = f"https://mp.weixin.qq.com/s/{a['original_id']}" if a.get("original_id") else ""
                if not url:
                    continue
                existing = self._read_articles_file(book_id)
                if any(e.get("url") == url for e in existing):
                    continue
                article_obj = {
                    "title": a.get("title", ""),
                    "url": url,
                    "publishedAt": a.get("time", int(time.time())),
                    "fetchedAt": int(time.time()),
                    "content": "",
                    "mpId": book_id,
                    "mpName": mp_name,
                    "summary": a.get("summary", ""),
                    "readNum": a.get("read_num", 0),
                    "likeNum": a.get("like_num", 0),
                }
                self._append_article(book_id, article_obj)
                new_count += 1
            return {"mpId": book_id, "name": mp_name, "new": new_count}
        except Exception as e:
            logger.warning(f"同步 {mp_name} 失败: {e}")
            return {"mpId": book_id, "name": mp_name, "error": str(e)}

    def sync_articles(self, mp_id: Optional[str] = None, limit: int = 15) -> Dict[str, Any]:
        """同步文章（并发）"""
        accounts = self.get_accounts()
        if not accounts:
            return {"error": "未找到已关注的公众号", "synced": 0}

        targets = [a for a in accounts if a["mpId"] == mp_id] if mp_id else accounts

        # 并发同步，最多 5 个同时
        from concurrent.futures import ThreadPoolExecutor, as_completed
        details = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._sync_one_account, acc, limit): acc for acc in targets}
            for future in as_completed(futures, timeout=60):
                try:
                    details.append(future.result(timeout=10))
                except Exception as e:
                    acc = futures[future]
                    details.append({"mpId": acc["mpId"], "name": acc["name"], "error": str(e)})

        total_new = sum(d.get("new", 0) for d in details)
        _clear_cache("wechat_digest_daily", "accounts")
        return {"synced": total_new, "details": details}

        _clear_cache("wechat_digest_daily", "accounts")
        return {"synced": total_new, "details": details}

    def _fetch_mp_articles(self, book_id: str, limit: int = 20) -> List[Dict]:
        """获取某公众号的文章列表"""
        articles = []
        offset = 0
        while len(articles) < limit:
            data = _weread_api("/web/mp/articles", {"bookId": book_id, "offset": offset})
            reviews = data.get("reviews", [])
            if not reviews:
                break
            for r in reviews:
                for s in r.get("subReviews", []):
                    info = s.get("review", {}).get("mpInfo", {})
                    if info.get("title"):
                        articles.append({
                            "title": info["title"],
                            "summary": info.get("content", ""),
                            "mp_name": info.get("mp_name", ""),
                            "original_id": info.get("originalId", ""),
                            "read_num": info.get("readNum", 0),
                            "like_num": info.get("likeNum", 0),
                            "time": info.get("time", 0),
                        })
            if data.get("clearAll"):
                break
            min_time = min(r.get("createTime", 0) for r in reviews)
            offset = min_time
            if len(reviews) < 10:
                break
            time.sleep(0.15)
        return articles

    # ---- 文章正文提取 ----

    def extract_content(self, url: str) -> Dict[str, str]:
        """提取微信文章标题和正文"""
        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                resp = client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                html = resp.text
        except Exception as e:
            return {"title": "", "content": f"获取失败: {e}"}

        title = ""
        m = re.search(r'<meta[^>]*property="og:title"[^>]*content="(.*?)"', html)
        if m:
            title = html_mod.unescape(m.group(1)).strip()
        if not title:
            m = re.search(r'var\s+msg_title\s*=\s*["\']([^"\']+)["\']', html)
            if m:
                title = m.group(1).strip()

        # 正文
        content = ""
        m = re.search(r'var\s+content_noencode\s*=\s*"([\s\S]*?)";', html)
        if m:
            content = m.group(1).replace('\\n', '\n').replace('\\t', '\t')
            content = content.replace('\\"', '"').replace('\\\\', '\\')
            content = re.sub(r'<[^>]+>', '', content).strip()
        if not content:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                el = soup.find(id="js_content")
                if el:
                    content = el.get_text(separator="\n", strip=True)
            except ImportError:
                pass
        return {"title": title, "content": content or "（无法提取正文）"}

    # ---- 文章查询 ----

    def get_articles(self, days: Optional[int] = None, mp_id: Optional[str] = None) -> List[Dict]:
        config = _load_config()
        target_days = days or config.get("syncDays", 3)
        cutoff = int((datetime.now() - timedelta(days=target_days)).timestamp())
        if not os.path.exists(ARTICLES_DIR):
            return []
        files = [f"{mp_id}.json"] if mp_id else [f for f in os.listdir(ARTICLES_DIR) if f.endswith(".json")]
        all_articles = []
        for fname in files:
            mp = fname.replace(".json", "")
            for a in self._read_articles_file(mp):
                ts = a.get("publishedAt") or a.get("fetchedAt") or 0
                if ts >= cutoff:
                    all_articles.append(a)
        all_articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
        return all_articles

    # ---- 日报 ----

    def _enrich_article(self, article: Dict) -> Dict:
        """补充文章摘要（如果没有的话，抓取正文生成）"""
        if article.get("summary") and len(article["summary"]) > 20:
            return article
        if article.get("content") and len(article["content"]) > 50:
            article["summary"] = self._make_summary(article["content"])
            return article
        # 抓取正文
        try:
            result = self.extract_content(article.get("url", ""))
            if result.get("content") and len(result["content"]) > 20:
                article["content"] = result["content"]
                article["summary"] = self._make_summary(result["content"])
                if result.get("title") and not article.get("title"):
                    article["title"] = result["title"]
                # 回写到文件
                self._update_article(article)
        except Exception as e:
            logger.debug(f"抓取正文失败: {e}")
        return article

    def _make_summary(self, content: str, max_len: int = 200) -> str:
        """从正文生成摘要（单行，无换行）"""
        if not content:
            return ""
        # 去掉所有换行、制表符、多余空白
        cleaned = re.sub(r'[\r\n\t]+', ' ', content)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        # 跳过开头的无意义内容
        skip_patterns = ['关注', '分享', '收藏', '赞', '在看', '阅读原文', '点击关注']
        for p in skip_patterns:
            if cleaned.startswith(p):
                cleaned = cleaned[len(p):].lstrip(' ,，、')
        if len(cleaned) <= 20:
            return cleaned
        if len(cleaned) <= max_len:
            return cleaned
        # 在句号处截断
        cut = cleaned[:max_len]
        last_period = max(cut.rfind('。'), cut.rfind('！'), cut.rfind('？'))
        if last_period > max_len * 0.5:
            return cut[:last_period + 1]
        return cut + '...'

    def _update_article(self, article: Dict):
        """回写文章数据到文件"""
        mp_id = article.get("mpId", "")
        if not mp_id:
            return
        articles = self._read_articles_file(mp_id)
        for i, a in enumerate(articles):
            if a.get("url") == article.get("url"):
                # 清理 summary 中的换行
                summary = article.get("summary", "")
                summary = re.sub(r'[\r\n\t]+', ' ', summary)
                summary = re.sub(r'\s+', ' ', summary).strip()
                articles[i]["content"] = article.get("content", "")
                articles[i]["summary"] = summary[:200]
                break
        _save_json(os.path.join(ARTICLES_DIR, f"{mp_id}.json"), articles)

    def generate_daily_digest(self, days: Optional[int] = None) -> Dict[str, Any]:
        cached = _get_cached("wechat_digest_daily", 60)
        if cached and not days:
            return cached
        articles = self.get_articles(days=days)
        if not articles:
            return {"title": f"微信公众号日报 - {datetime.now().strftime('%Y-%m-%d')}", "date": datetime.now().strftime("%Y-%m-%d"), "groups": [], "totalArticles": 0, "totalAccounts": 0, "update_time": datetime.now().isoformat()}

        # 并发补充摘要（最多 10 个同时）
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._enrich_article, a) for a in articles]
            for f in as_completed(futures, timeout=30):
                try:
                    f.result(timeout=5)
                except Exception:
                    pass

        # 重新读取（因为 _enrich_article 可能回写了文件）
        articles = self.get_articles(days=days)

        groups_map: Dict[str, List] = {}
        for a in articles:
            key = a.get("mpName") or a.get("mpId", "未知")
            groups_map.setdefault(key, []).append(a)
        groups = []
        for mp_name, mp_articles in groups_map.items():
            mp_articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
            items = [{"title": a.get("title", ""), "url": a.get("url", ""), "publishedAt": a.get("publishedAt"), "publishedDate": self._fmt_ts(a.get("publishedAt")), "summary": a.get("summary", ""), "mpName": a.get("mpName", mp_name)} for a in mp_articles]
            groups.append({"mpName": mp_name, "mpId": mp_articles[0].get("mpId", ""), "count": len(items), "items": items})
        groups.sort(key=lambda g: g["count"], reverse=True)
        result = {"title": f"微信公众号日报 - {datetime.now().strftime('%Y-%m-%d')}", "date": datetime.now().strftime("%Y-%m-%d"), "groups": groups, "totalArticles": len(articles), "totalAccounts": len(groups), "update_time": datetime.now().isoformat()}
        _set_cached("wechat_digest_daily", result)
        return result

    # ---- 内部 ----

    def _read_articles_file(self, mp_id: str) -> List[Dict]:
        return _load_json(os.path.join(ARTICLES_DIR, f"{mp_id}.json"), [])

    def _append_article(self, mp_id: str, article: Dict):
        _ensure_dirs()
        config = _load_config()
        articles = self._read_articles_file(mp_id)
        if any(a.get("url") == article["url"] for a in articles):
            return
        articles.insert(0, article)
        articles.sort(key=lambda x: x.get("publishedAt", 0), reverse=True)
        articles = articles[:config.get("maxArticlesPerAccount", 30)]
        _save_json(os.path.join(ARTICLES_DIR, f"{mp_id}.json"), articles)

    def _fmt_ts(self, ts: Optional[int]) -> str:
        if not ts:
            return ""
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ""


wechat_digest_service = WechatDigestService()
