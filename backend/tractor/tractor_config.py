# -*- coding: utf-8 -*-
"""拖拉机账户配置管理

管理多个拖拉机账户的配置信息，支持：
- 华宝证券通达信版独立交易
- 银河证券海王星
"""

import json
import os
from typing import Optional
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path(__file__).parent
ACCOUNTS_FILE = CONFIG_DIR / "accounts.json"

# 默认配置模板
DEFAULT_ACCOUNTS = {
    "accounts": [],
    "default_fund_code": "162411",  # 华宝油气
    "autoit_path": r"C:\Program Files (x86)\AutoIt3\AutoIt3.exe",
    "script_path": str(CONFIG_DIR / "yinhe.au3"),
}


def load_accounts() -> dict:
    """加载账户配置"""
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_ACCOUNTS.copy()


def save_accounts(config: dict) -> bool:
    """保存账户配置"""
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def add_account(account_id: str, password: str, broker_type: str = "huabao", name: str = "") -> dict:
    """添加账户

    Args:
        account_id: 资金账号
        password: 交易密码
        broker_type: 券商类型 (huabao/yinhe)
        name: 账户备注名

    Returns:
        添加的账户信息
    """
    config = load_accounts()

    # 检查是否已存在
    for acc in config["accounts"]:
        if acc["account_id"] == account_id:
            # 更新已有账户
            acc["password"] = password
            acc["broker_type"] = broker_type
            acc["name"] = name or account_id
            save_accounts(config)
            return acc

    # 添加新账户
    account = {
        "account_id": account_id,
        "password": password,
        "broker_type": broker_type,
        "name": name or account_id,
        "enabled": True,
    }
    config["accounts"].append(account)
    save_accounts(config)
    return account


def remove_account(account_id: str) -> bool:
    """删除账户"""
    config = load_accounts()
    config["accounts"] = [a for a in config["accounts"] if a["account_id"] != account_id]
    return save_accounts(config)


def update_account(account_id: str, **kwargs) -> Optional[dict]:
    """更新账户信息"""
    config = load_accounts()
    for acc in config["accounts"]:
        if acc["account_id"] == account_id:
            for key, value in kwargs.items():
                if key in acc:
                    acc[key] = value
            save_accounts(config)
            return acc
    return None


def list_accounts() -> list:
    """列出所有账户（隐藏密码）"""
    config = load_accounts()
    result = []
    for acc in config["accounts"]:
        result.append({
            "account_id": acc["account_id"],
            "name": acc.get("name", acc["account_id"]),
            "broker_type": acc.get("broker_type", "huabao"),
            "enabled": acc.get("enabled", True),
            "password": "***",  # 隐藏密码
        })
    return result


def get_accounts_for_autoit() -> tuple:
    """获取AutoIt脚本格式的账户配置

    Returns:
        (account_ids, passwords) 两个列表
    """
    config = load_accounts()
    accounts = [a for a in config["accounts"] if a.get("enabled", True)]
    account_ids = [a["account_id"] for a in accounts]
    passwords = [a["password"] for a in accounts]
    return account_ids, passwords


def generate_autoit_accounts_file() -> str:
    """生成AutoIt脚本用的账户配置文件内容

    Returns:
        yinheaccounts.au3 文件内容
    """
    account_ids, passwords = get_accounts_for_autoit()
    n = len(account_ids)

    # 格式化数组
    ids_str = '", "'.join(account_ids)
    pw_str = '", "'.join(passwords)

    content = f'Global $arAccount[{n}] = ["{ids_str}"]\n'
    content += f'Global $arPassword[{n}] = ["{pw_str}"]\n'

    return content


def sync_to_autoit() -> bool:
    """同步账户配置到AutoIt脚本"""
    try:
        content = generate_autoit_accounts_file()
        autoit_config = CONFIG_DIR / "yinheaccounts.au3"
        with open(autoit_config, "w", encoding="utf-8-sig") as f:
            f.write(content)
        return True
    except Exception:
        return False
