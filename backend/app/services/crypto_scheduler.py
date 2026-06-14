"""
币圈情报定时搜集调度器
后台线程定期执行搜集任务
"""
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_scheduler_started = False


def start_crypto_crawler_scheduler(interval_minutes: int = 30):
    """启动定时搜集器（每30分钟执行一次）"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def _run():
        # 启动后延迟60秒执行第一次，避免启动时阻塞
        time.sleep(60)
        while True:
            try:
                from app.services.crypto_crawler_service import CryptoCrawlerService
                svc = CryptoCrawlerService()
                logger.info(f"[CryptoCrawler] 开始定时搜集... {datetime.now().strftime('%H:%M:%S')}")
                result = svc.crawl_all()
                new_count = result.get("new_count", 0)
                total = result.get("total_count", 0)
                sources_ok = sum(1 for s in result.get("sources", {}).values() if s.get("status") == "ok")
                sources_err = sum(1 for s in result.get("sources", {}).values() if s.get("status") == "error")
                logger.info(f"[CryptoCrawler] 搜集完成: 新增{new_count}条, 总计{total}条, 成功{sources_ok}源, 失败{sources_err}源")
            except Exception as e:
                logger.error(f"[CryptoCrawler] 搜集异常: {e}")
            time.sleep(interval_minutes * 60)

    t = threading.Thread(target=_run, daemon=True, name="crypto-crawler")
    t.start()
    logger.info(f"[CryptoCrawler] 定时搜集器已启动，间隔{interval_minutes}分钟")
