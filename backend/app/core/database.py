"""
SQLite 数据库模块 — 替代 JSON 文件存储

使用 Python 内置 sqlite3，零外部依赖。
数据库文件：backend/data/invest.db

提供：
- get_db()     — 获取数据库连接（线程安全，check_same_thread=False）
- init_db()    — 创建表 + 自动迁移旧 JSON 数据
"""

import json
import os
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ============================================================
# 路径
# ============================================================

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_DB_PATH = os.path.join(_DATA_DIR, "invest.db")


# ============================================================
# 连接管理
# ============================================================

def get_db() -> sqlite3.Connection:
    """获取数据库连接（每次调用返回新连接，适合 FastAPI 依赖注入）"""
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db_ctx():
    """上下文管理器，自动 commit/rollback + 关闭连接"""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 建表
# ============================================================

def _create_tables(conn: sqlite3.Connection):
    """创建所有表（IF NOT EXISTS，可安全重复执行）"""

    conn.executescript("""
        -- 元信息表（schema 版本等）
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- 组合管理：交易记录
        CREATE TABLE IF NOT EXISTS transactions (
            id          TEXT PRIMARY KEY,
            code        TEXT NOT NULL,
            name        TEXT NOT NULL,
            market      TEXT NOT NULL DEFAULT 'A',
            type        TEXT NOT NULL,
            shares      REAL NOT NULL,
            price       REAL NOT NULL,
            amount      REAL NOT NULL,
            fee         REAL NOT NULL DEFAULT 0,
            reason      TEXT NOT NULL DEFAULT '',
            decision_id TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_txn_code ON transactions(code);
        CREATE INDEX IF NOT EXISTS idx_txn_created ON transactions(created_at);

        -- 组合管理：设置（如现金余额）
        CREATE TABLE IF NOT EXISTS portfolio_settings (
            key   TEXT PRIMARY KEY,
            value REAL NOT NULL DEFAULT 0
        );

        -- 决策日志
        CREATE TABLE IF NOT EXISTS decision_log (
            id         TEXT PRIMARY KEY,
            timestamp  TEXT NOT NULL,
            data       TEXT NOT NULL  -- 完整 JSON 记录
        );
        CREATE INDEX IF NOT EXISTS idx_dl_ts ON decision_log(timestamp);

        -- 校准训练日志
        CREATE TABLE IF NOT EXISTS calibration_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            data        TEXT NOT NULL  -- 完整 JSON 记录
        );

        -- 训练日志
        CREATE TABLE IF NOT EXISTS training_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_type TEXT NOT NULL,
            question_id   TEXT NOT NULL,
            data          TEXT NOT NULL  -- 完整 JSON 记录
        );

        -- 做T仓位
        CREATE TABLE IF NOT EXISTS t_positions (
            pos_key   TEXT PRIMARY KEY,  -- "{market}_{code}"
            code      TEXT NOT NULL,
            name      TEXT NOT NULL,
            market    TEXT NOT NULL,
            data      TEXT NOT NULL      -- 完整 JSON 仓位数据
        );

        -- 做T交易记录（扁平化历史）
        CREATE TABLE IF NOT EXISTS t_trades (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            time      TEXT NOT NULL,
            code      TEXT NOT NULL,
            market    TEXT NOT NULL,
            action    TEXT NOT NULL,
            data      TEXT NOT NULL      -- 完整 JSON 交易数据
        );
        CREATE INDEX IF NOT EXISTS idx_tt_code ON t_trades(code);
        CREATE INDEX IF NOT EXISTS idx_tt_time ON t_trades(time);
    """)

    # 标记 schema 版本
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
        ("schema_version", "1"),
    )


# ============================================================
# JSON → SQLite 迁移
# ============================================================

def _migrate_portfolio_json(conn: sqlite3.Connection):
    """从 portfolio.json 迁移数据"""
    portfolio_file = os.path.join(_DATA_DIR, "portfolio.json")
    if not os.path.exists(portfolio_file):
        return

    try:
        with open(portfolio_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    # 检查是否已有数据
    row = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()
    if row[0] > 0:
        logger.info("transactions 表已有数据，跳过 portfolio.json 迁移")
        return

    txns = data.get("transactions", [])
    cash = data.get("cash", 0)

    for t in txns:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (id, code, name, market, type, shares, price, amount, fee, reason, decision_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    t["id"], t["code"], t["name"],
                    t.get("market", "A"), t["type"],
                    t["shares"], t["price"], t["amount"],
                    t.get("fee", 0), t.get("reason", ""),
                    t.get("decision_id", ""), t.get("created_at", ""),
                ),
            )
        except Exception as e:
            logger.warning(f"迁移交易记录失败: {e}")

    # 迁移现金余额
    conn.execute(
        "INSERT OR REPLACE INTO portfolio_settings(key, value) VALUES(?, ?)",
        ("cash", cash),
    )

    logger.info(f"portfolio.json 迁移完成: {len(txns)} 笔交易, 现金={cash}")

    # 重命名旧文件
    backup = portfolio_file + ".bak"
    if not os.path.exists(backup):
        os.rename(portfolio_file, backup)
        logger.info(f"旧文件已备份为 {backup}")


def _migrate_decision_log_json(conn: sqlite3.Connection):
    """从 decision_log.json 迁移数据"""
    log_file = os.path.join(_DATA_DIR, "decision_log.json")
    if not os.path.exists(log_file):
        return

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    if not records:
        return

    # 检查是否已有数据
    row = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()
    if row[0] > 0:
        logger.info("decision_log 表已有数据，跳过迁移")
        return

    for r in records:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO decision_log(id, timestamp, data) VALUES(?, ?, ?)",
                (r["id"], r.get("timestamp", ""), json.dumps(r, ensure_ascii=False)),
            )
        except Exception as e:
            logger.warning(f"迁移决策记录失败: {e}")

    logger.info(f"decision_log.json 迁移完成: {len(records)} 条记录")

    backup = log_file + ".bak"
    if not os.path.exists(backup):
        os.rename(log_file, backup)
        logger.info(f"旧文件已备份为 {backup}")


def _migrate_t_positions_json(conn: sqlite3.Connection):
    """从 t_positions.json 迁移数据"""
    pos_file = os.path.join(_DATA_DIR, "t_positions.json")
    if not os.path.exists(pos_file):
        return

    try:
        with open(pos_file, "r", encoding="utf-8") as f:
            positions = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    if not positions:
        return

    # 检查是否已有数据
    row = conn.execute("SELECT COUNT(*) FROM t_positions").fetchone()
    if row[0] > 0:
        logger.info("t_positions 表已有数据，跳过迁移")
        return

    for key, pos in positions.items():
        try:
            conn.execute(
                "INSERT OR IGNORE INTO t_positions(pos_key, code, name, market, data) VALUES(?, ?, ?, ?, ?)",
                (key, pos.get("code", ""), pos.get("name", ""), pos.get("market", ""),
                 json.dumps(pos, ensure_ascii=False)),
            )
        except Exception as e:
            logger.warning(f"迁移做T仓位失败: {e}")

    logger.info(f"t_positions.json 迁移完成: {len(positions)} 个仓位")

    backup = pos_file + ".bak"
    if not os.path.exists(backup):
        os.rename(pos_file, backup)
        logger.info(f"旧文件已备份为 {backup}")


def _migrate_t_trades_json(conn: sqlite3.Connection):
    """从 t_trades.json 迁移数据"""
    trades_file = os.path.join(_DATA_DIR, "t_trades.json")
    if not os.path.exists(trades_file):
        return

    try:
        with open(trades_file, "r", encoding="utf-8") as f:
            trades = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    if not trades:
        return

    # 检查是否已有数据
    row = conn.execute("SELECT COUNT(*) FROM t_trades").fetchone()
    if row[0] > 0:
        logger.info("t_trades 表已有数据，跳过迁移")
        return

    for t in trades:
        try:
            conn.execute(
                "INSERT INTO t_trades(time, code, market, action, data) VALUES(?, ?, ?, ?, ?)",
                (t.get("time", ""), t.get("code", ""), t.get("market", ""),
                 t.get("action", ""), json.dumps(t, ensure_ascii=False)),
            )
        except Exception as e:
            logger.warning(f"迁移做T交易记录失败: {e}")

    logger.info(f"t_trades.json 迁移完成: {len(trades)} 条记录")

    backup = trades_file + ".bak"
    if not os.path.exists(backup):
        os.rename(trades_file, backup)
        logger.info(f"旧文件已备份为 {backup}")


# ============================================================
# 初始化入口
# ============================================================

def init_db():
    """
    初始化数据库：建表 + 自动迁移旧 JSON 数据。

    应在 FastAPI lifespan 中调用一次。
    """
    logger.info(f"初始化数据库: {_DB_PATH}")
    conn = get_db()
    try:
        _create_tables(conn)

        # 迁移旧数据
        _migrate_portfolio_json(conn)
        _migrate_decision_log_json(conn)
        _migrate_t_positions_json(conn)
        _migrate_t_trades_json(conn)

        conn.commit()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
    finally:
        conn.close()
