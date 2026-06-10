"""信用卡权益对比 - 全球支付卡产品信息"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

router = APIRouter()

# ========== 排序字段常量 ==========
VALID_SORT_FIELDS = {"rating", "annual_fee", "signup_bonus_value"}

# ========== 内置信用卡数据库 ==========
# 覆盖主流国家/地区的热门信用卡产品

CARDS_DB = [
    # ===== 美国 =====
    {
        "id": "us-chase-sapphire-reserve",
        "issuer": "Chase",
        "name": "Sapphire Reserve",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Travel",
        "card_network": "Visa",
        "annual_fee": 550,
        "annual_fee_waiver": "",
        "signup_bonus": "60,000 Ultimate Rewards points",
        "signup_bonus_requirement": "3个月内消费$4,000",
        "signup_bonus_value": 900,
        "rewards_rate": {"Travel & Dining": 3, "其他": 1},
        "rewards_type": "积分 (Ultimate Rewards)",
        "key_perks": ["$300旅行报销", "Priority Pass贵宾厅", "Global Entry/TSA PreCheck报销", "DoorDash会员", "Lyft Pink会员"],
        "income_requirement": "",
        "credit_score_requirement": "750+",
        "foreign_transaction_fee": 0,
        "best_for": "频繁旅行者",
        "notes": "UR积分可1:1.5兑换旅行，或转至航空/酒店伙伴",
        "rating": 4.7,
        "tags": ["旅行", "高端", "积分"]
    },
    {
        "id": "us-chase-sapphire-preferred",
        "issuer": "Chase",
        "name": "Sapphire Preferred",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Travel",
        "card_network": "Visa",
        "annual_fee": 95,
        "annual_fee_waiver": "",
        "signup_bonus": "60,000 Ultimate Rewards points",
        "signup_bonus_requirement": "3个月内消费$4,000",
        "signup_bonus_value": 750,
        "rewards_rate": {"Travel & Dining": 3, "流媒体/在线杂货": 3, "其他": 1},
        "rewards_type": "积分 (Ultimate Rewards)",
        "key_perks": ["$50酒店报销", "旅行延误险", "行李延误险"],
        "income_requirement": "",
        "credit_score_requirement": "700+",
        "foreign_transaction_fee": 0,
        "best_for": "入门旅行卡",
        "notes": "性价比最高的旅行入门卡",
        "rating": 4.5,
        "tags": ["旅行", "入门", "积分"]
    },
    {
        "id": "us-amex-platinum",
        "issuer": "American Express",
        "name": "Platinum Card",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Travel",
        "card_network": "Amex",
        "annual_fee": 695,
        "annual_fee_waiver": "",
        "signup_bonus": "80,000 Membership Rewards points",
        "signup_bonus_requirement": "6个月内消费$6,000",
        "signup_bonus_value": 1200,
        "rewards_rate": {"航空": 5, "酒店(预付)": 5, "其他": 1},
        "rewards_type": "积分 (Membership Rewards)",
        "key_perks": ["$200航空报销", "$200酒店报销", "$240数字娱乐报销", "Centurion Lounge", "Priority Pass", "Hilton Gold", "Marriott Gold"],
        "income_requirement": "",
        "credit_score_requirement": "740+",
        "foreign_transaction_fee": 0,
        "best_for": "高端旅行者",
        "notes": "权益丰富但年费高，适合充分利用报销的用户",
        "rating": 4.6,
        "tags": ["旅行", "高端", "积分", "贵宾厅"]
    },
    {
        "id": "us-amex-gold",
        "issuer": "American Express",
        "name": "Gold Card",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Dining",
        "card_network": "Amex",
        "annual_fee": 250,
        "annual_fee_waiver": "",
        "signup_bonus": "60,000 Membership Rewards points",
        "signup_bonus_requirement": "6个月内消费$4,000",
        "signup_bonus_value": 900,
        "rewards_rate": {"餐饮": 4, "超市": 4, "航空": 3, "其他": 1},
        "rewards_type": "积分 (Membership Rewards)",
        "key_perks": ["$120餐饮报销", "$120Uber报销"],
        "income_requirement": "",
        "credit_score_requirement": "700+",
        "foreign_transaction_fee": 0,
        "best_for": "餐饮爱好者",
        "notes": "餐饮和超市4x积分是同类最高",
        "rating": 4.5,
        "tags": ["餐饮", "超市", "积分"]
    },
    {
        "id": "us-citi-double-cash",
        "issuer": "Citi",
        "name": "Double Cash",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Cashback",
        "card_network": "Mastercard",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "$200",
        "signup_bonus_requirement": "3个月内消费$1,500",
        "signup_bonus_value": 200,
        "rewards_rate": {"所有消费": 2},
        "rewards_type": "返现",
        "key_perks": ["无年费", "无外币手续费(已取消)", "简洁返现结构"],
        "income_requirement": "",
        "credit_score_requirement": "680+",
        "foreign_transaction_fee": 3,
        "best_for": "简单返现",
        "notes": "消费1%+还款1%=2%返现，无年费万能卡",
        "rating": 4.2,
        "tags": ["返现", "无年费", "简单"]
    },
    {
        "id": "us-citi-custom-cash",
        "issuer": "Citi",
        "name": "Custom Cash",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Cashback",
        "card_network": "Mastercard",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "$200",
        "signup_bonus_requirement": "3个月内消费$1,500",
        "signup_bonus_value": 200,
        "rewards_rate": {"最高消费类别": 5, "其他": 1},
        "rewards_type": "返现",
        "key_perks": ["自动识别最高消费类别", "5%返现上限$500/月"],
        "income_requirement": "",
        "credit_score_requirement": "680+",
        "foreign_transaction_fee": 3,
        "best_for": "特定类别高返现",
        "notes": "每月自动在最高消费类别给5%返现，上限$500",
        "rating": 4.3,
        "tags": ["返现", "无年费", "高返现"]
    },
    {
        "id": "us-discover-it",
        "issuer": "Discover",
        "name": "Discover it",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Cashback",
        "card_network": "Discover",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "首年返现翻倍",
        "signup_bonus_requirement": "首年所有返现翻倍",
        "signup_bonus_value": 300,
        "rewards_rate": {"轮转类别": 5, "其他": 1},
        "rewards_type": "返现",
        "key_perks": ["首年返现翻倍", "轮转5%类别", "无外币手续费"],
        "income_requirement": "",
        "credit_score_requirement": "670+",
        "foreign_transaction_fee": 0,
        "best_for": "学生/入门",
        "notes": "每季度更换5%类别，首年翻倍非常给力",
        "rating": 4.1,
        "tags": ["返现", "无年费", "学生", "入门"]
    },
    {
        "id": "us-capital-one-venture-x",
        "issuer": "Capital One",
        "name": "Venture X",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Travel",
        "card_network": "Visa",
        "annual_fee": 395,
        "annual_fee_waiver": "",
        "signup_bonus": "75,000 miles",
        "signup_bonus_requirement": "3个月内消费$4,000",
        "signup_bonus_value": 750,
        "rewards_rate": {"所有消费": 2, "Capital One Travel预订": 5},
        "rewards_type": "里程",
        "key_perks": ["$300旅行报销", "Capital One Lounge", "Priority Pass", "10,000周年里程"],
        "income_requirement": "",
        "credit_score_requirement": "740+",
        "foreign_transaction_fee": 0,
        "best_for": "性价比旅行卡",
        "notes": "年费$395但$300报销+10K里程(价值$100)基本打平",
        "rating": 4.6,
        "tags": ["旅行", "里程", "贵宾厅"]
    },
    {
        "id": "us-wells-fargo-autograph",
        "issuer": "Wells Fargo",
        "name": "Autograph",
        "local_name": "",
        "country": "US",
        "currency": "USD",
        "card_type": "Cashback",
        "card_network": "Visa",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "20,000 points",
        "signup_bonus_requirement": "3个月内消费$1,500",
        "signup_bonus_value": 200,
        "rewards_rate": {"餐饮": 3, "旅行": 3, "加油": 3, "交通": 3, "流媒体": 3, "手机": 3, "其他": 1},
        "rewards_type": "积分",
        "key_perks": ["无年费", "无外币手续费", "多类别3x"],
        "income_requirement": "",
        "credit_score_requirement": "670+",
        "foreign_transaction_fee": 0,
        "best_for": "无年费多类别",
        "notes": "无年费且无外币手续费，6个类别3x积分",
        "rating": 4.2,
        "tags": ["返现", "无年费", "旅行"]
    },
    # ===== 中国 =====
    {
        "id": "cn-cmb-visa-signature",
        "issuer": "招商银行",
        "name": "全币种国际信用卡",
        "local_name": "招商银行全币种国际信用卡(VISA Signature)",
        "country": "CN",
        "currency": "CNY",
        "card_type": "Travel",
        "card_network": "Visa",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "",
        "signup_bonus_requirement": "",
        "signup_bonus_value": 0,
        "rewards_rate": {"境外消费": 1},
        "rewards_type": "积分",
        "key_perks": ["全币种免货币转换费", "VISA Signature权益", "境外消费人民币入账"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 0,
        "best_for": "海淘/境外消费",
        "notes": "免货币转换费，境外消费直接人民币入账",
        "rating": 4.3,
        "tags": ["海淘", "免货转", "全币种"]
    },
    {
        "id": "cn-cmb-travel",
        "issuer": "招商银行",
        "name": "经典白金卡",
        "local_name": "招商银行经典白金信用卡",
        "country": "CN",
        "currency": "CNY",
        "card_type": "Travel",
        "card_network": "Visa",
        "annual_fee": 3600,
        "annual_fee_waiver": "年消费满36万免次年",
        "signup_bonus": "",
        "signup_bonus_requirement": "",
        "signup_bonus_value": 0,
        "rewards_rate": {"所有消费": 1},
        "rewards_type": "积分",
        "key_perks": ["机场贵宾厅", "高尔夫", "体检", "航班延误险", "高额旅行险"],
        "income_requirement": "年收入30万+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 1.5,
        "best_for": "高端商旅",
        "notes": "招行经典高端卡，权益全面但年费高",
        "rating": 4.4,
        "tags": ["高端", "旅行", "贵宾厅"]
    },
    {
        "id": "cn-icbc-unionpay-diamond",
        "issuer": "工商银行",
        "name": "银联钻石卡",
        "local_name": "工商银行银联钻石信用卡",
        "country": "CN",
        "currency": "CNY",
        "card_type": "Premium",
        "card_network": "UnionPay",
        "annual_fee": 5000,
        "annual_fee_waiver": "年消费满50万免次年",
        "signup_bonus": "",
        "signup_bonus_requirement": "",
        "signup_bonus_value": 0,
        "rewards_rate": {"所有消费": 1},
        "rewards_type": "积分",
        "key_perks": ["机场贵宾厅", "高端酒店权益", "全球紧急支援", "航班延误险"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 1,
        "best_for": "银联高端用户",
        "notes": "银联最高等级卡组织权益",
        "rating": 4.2,
        "tags": ["高端", "银联", "钻石"]
    },
    {
        "id": "cn-ping-an-good-card",
        "issuer": "平安银行",
        "name": "好车主卡",
        "local_name": "平安银行好车主信用卡",
        "country": "CN",
        "currency": "CNY",
        "card_type": "Cashback",
        "card_network": "UnionPay",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "",
        "signup_bonus_requirement": "",
        "signup_bonus_value": 0,
        "rewards_rate": {"加油": 8, "餐饮": 1, "其他": 0.5},
        "rewards_type": "返现",
        "key_perks": ["加油88折", "免费道路救援", "高额车险折扣"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 1.5,
        "best_for": "车主",
        "notes": "加油返现力度大，有车一族首选",
        "rating": 4.1,
        "tags": ["车主", "加油", "返现", "无年费"]
    },
    # ===== 香港 =====
    {
        "id": "hk-citi-prestige",
        "issuer": "Citibank",
        "name": "Prestige Card",
        "local_name": "花旗銀行Prestige信用卡",
        "country": "HK",
        "currency": "HKD",
        "card_type": "Travel",
        "card_network": "Mastercard",
        "annual_fee": 5000,
        "annual_fee_waiver": "",
        "signup_bonus": "250,000 Citi积分",
        "signup_bonus_requirement": "首3个月消费HK$15,000",
        "signup_bonus_value": 2500,
        "rewards_rate": {"海外": 3, "本地": 1, "指定商户": 5},
        "rewards_type": "积分",
        "key_perks": ["Priority Pass贵宾厅", "机场接送", "酒店礼遇", "高尔夫球场"],
        "income_requirement": "年收入HK$600,000+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 0,
        "best_for": "高端旅行",
        "notes": "香港高端旅行卡代表",
        "rating": 4.4,
        "tags": ["旅行", "高端", "贵宾厅"]
    },
    {
        "id": "hk-dbs-eminent-card",
        "issuer": "DBS",
        "name": "Eminent Card",
        "local_name": "星展銀行Eminent信用卡",
        "country": "HK",
        "currency": "HKD",
        "card_type": "Cashback",
        "card_network": "Visa",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "HK$800",
        "signup_bonus_requirement": "首2个月消费HK$8,000",
        "signup_bonus_value": 800,
        "rewards_rate": {"餐饮": 4, "网购": 4, "其他": 0.4},
        "rewards_type": "Cash Dollar",
        "key_perks": ["无年费", "餐饮4%回赠", "网购4%回赠"],
        "income_requirement": "年收入HK$150,000+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 1.95,
        "best_for": "日常消费",
        "notes": "餐饮和网购4%回赠，无年费实用之选",
        "rating": 4.0,
        "tags": ["返现", "无年费", "餐饮"]
    },
    {
        "id": "hk-hsbc-red-card",
        "issuer": "HSBC",
        "name": "Red Card",
        "local_name": "匯豐Red信用卡",
        "country": "HK",
        "currency": "HKD",
        "card_type": "Cashback",
        "card_network": "Mastercard",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "HK$600",
        "signup_bonus_requirement": "首2个月消费HK$5,000",
        "signup_bonus_value": 600,
        "rewards_rate": {"指定商户": 4, "其他": 0.4},
        "rewards_type": "Cash Dollar",
        "key_perks": ["无年费", "指定商户4%回赠", "灵活现金回赠"],
        "income_requirement": "年收入HK$120,000+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 1.95,
        "best_for": "HSBC用户",
        "notes": "HSBC客户申请更容易，指定商户4%回赠",
        "rating": 3.9,
        "tags": ["返现", "无年费", "HSBC"]
    },
    # ===== 新加坡 =====
    {
        "id": "sg-dbc-altitude",
        "issuer": "DBS",
        "name": "Altitude Card",
        "local_name": "DBS Altitude Visa Signature Card",
        "country": "SG",
        "currency": "SGD",
        "card_type": "Travel",
        "card_network": "Visa",
        "annual_fee": 192.6,
        "annual_fee_waiver": "首年免年费",
        "signup_bonus": "10,000 miles",
        "signup_bonus_requirement": "首3个月消费SG$3,000",
        "signup_bonus_value": 500,
        "rewards_rate": {"海外": 3, "本地": 1.2, "酒店/航空": 6},
        "rewards_type": "里程 (KrisFlyer/Asia Miles)",
        "key_perks": ["里程累积", "旅行保险", "机场贵宾厅折扣"],
        "income_requirement": "年收入SG$30,000+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 0,
        "best_for": "里程累积",
        "notes": "新加坡最热门的里程累积卡之一",
        "rating": 4.2,
        "tags": ["旅行", "里程", "航空"]
    },
    {
        "id": "sg-uob-one-card",
        "issuer": "UOB",
        "name": "One Card",
        "local_name": "UOB One Card",
        "country": "SG",
        "currency": "SGD",
        "card_type": "Cashback",
        "card_network": "Visa",
        "annual_fee": 0,
        "annual_fee_waiver": "永久免年费",
        "signup_bonus": "",
        "signup_bonus_requirement": "",
        "signup_bonus_value": 0,
        "rewards_rate": {"所有消费": 3.33, "指定商户额外": 5},
        "rewards_type": "返现",
        "key_perks": ["无年费", "季度返现高达3.33%", "指定商户额外5%"],
        "income_requirement": "年收入SG$30,000+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 2.5,
        "best_for": "日常返现",
        "notes": "每季度消费满SG$2,000可获3.33%返现",
        "rating": 4.0,
        "tags": ["返现", "无年费", "日常"]
    },
    # ===== 英国 =====
    {
        "id": "uk-amex-gold",
        "issuer": "American Express",
        "name": "Gold Card",
        "local_name": "American Express Preferred Rewards Gold Card",
        "country": "UK",
        "currency": "GBP",
        "card_type": "Rewards",
        "card_network": "Amex",
        "annual_fee": 0,
        "annual_fee_waiver": "首年免年费，之后£160/年",
        "signup_bonus": "20,000 Membership Rewards points",
        "signup_bonus_requirement": "首3个月消费£3,000",
        "signup_bonus_value": 150,
        "rewards_rate": {"所有消费": 1, "Amex Travel预订": 3},
        "rewards_type": "积分 (Membership Rewards)",
        "key_perks": ["4次机场贵宾厅", " Deliveroo £10/月报销", "积分转里程"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 2.99,
        "best_for": "英国入门奖励卡",
        "notes": "首年免年费，积分可转多个航空里程计划",
        "rating": 4.2,
        "tags": ["积分", "旅行", "入门"]
    },
    {
        "id": "uk-barclays-avios-plus",
        "issuer": "Barclays",
        "name": "Avios Plus",
        "local_name": "Barclays Avios Plus Mastercard",
        "country": "UK",
        "currency": "GBP",
        "card_type": "Travel",
        "card_network": "Mastercard",
        "annual_fee": 0,
        "annual_fee_waiver": "需Barclays账户",
        "signup_bonus": "25,000 Avios",
        "signup_bonus_requirement": "首3个月消费£3,000",
        "signup_bonus_value": 250,
        "rewards_rate": {"所有消费": 1.5, "海外消费": 3},
        "rewards_type": "Avios里程",
        "key_perks": ["BA Avios累积", "无年费(需Barclays账户)", "伴侣票(消费满£10K)"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 0,
        "best_for": "BA飞行者",
        "notes": "英国航空Avios累积利器，消费满£10K可获伴侣票",
        "rating": 4.3,
        "tags": ["旅行", "里程", "BA"]
    },
    # ===== 日本 =====
    {
        "id": "jp-rakuten-card",
        "issuer": "楽天",
        "name": "楽天カード",
        "local_name": "楽天カード (年会費無料)",
        "country": "JP",
        "currency": "JPY",
        "card_type": "Cashback",
        "card_network": "Visa",
        "annual_fee": 0,
        "annual_fee_waiver": "永久年会費無料",
        "signup_bonus": "楽天ポイント 5,000pt",
        "signup_bonus_requirement": "初回利用",
        "signup_bonus_value": 5000,
        "rewards_rate": {"楽天市場": 3, "其他": 1},
        "rewards_type": "楽天ポイント",
        "key_perks": ["永久年会費無料", "楽天市場3倍", "楽天ペイ連携"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 1.6,
        "best_for": "楽天用户",
        "notes": "日本最流行的免年费信用卡，楽天生态圈必备",
        "rating": 4.3,
        "tags": ["返现", "无年费", "楽天"]
    },
    {
        "id": "jp-saison-card-gold",
        "issuer": "セゾン",
        "name": "ゴールドカード",
        "local_name": "セゾンカード・ゴールド・アメリカン・エキスプレス",
        "country": "JP",
        "currency": "JPY",
        "card_type": "Travel",
        "card_network": "Amex",
        "annual_fee": 10000,
        "annual_fee_waiver": "",
        "signup_bonus": "10,000ポイント",
        "signup_bonus_requirement": "初回利用",
        "signup_bonus_value": 10000,
        "rewards_rate": {"所有消费": 1, "海外": 2},
        "rewards_type": "永久不滅ポイント",
        "key_perks": ["国内旅行保险", "海外旅行保险", "空港ラウンジ", "ETCカード"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 2,
        "best_for": "日本金卡入门",
        "notes": "年费1万日元，日本金卡入门之选",
        "rating": 4.1,
        "tags": ["旅行", "金卡", "日本"]
    },
    # ===== 加拿大 =====
    {
        "id": "ca-amex-cobalt",
        "issuer": "American Express",
        "name": "Cobalt Card",
        "local_name": "American Express Cobalt Card",
        "country": "CA",
        "currency": "CAD",
        "card_type": "Rewards",
        "card_network": "Amex",
        "annual_fee": 155.88,
        "annual_fee_waiver": "月费$12.99",
        "signup_bonus": "30,000 Membership Rewards points",
        "signup_bonus_requirement": "每月消费$500连续12个月",
        "signup_bonus_value": 300,
        "rewards_rate": {"餐饮/外卖": 5, "旅行/交通": 3, "串流": 3, "其他": 1},
        "rewards_type": "积分 (MR Select)",
        "key_perks": ["餐饮5x积分", "月费制灵活", "积分转Aeroplan/BA"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 2.5,
        "best_for": "加拿大餐饮爱好者",
        "notes": "加拿大最强餐饮卡，5x积分可转航空里程",
        "rating": 4.5,
        "tags": ["积分", "餐饮", "加拿大"]
    },
    {
        "id": "ca-simply-cash-preferred",
        "issuer": "American Express",
        "name": "SimplyCash Preferred",
        "local_name": "SimplyCash Preferred Card",
        "country": "CA",
        "currency": "CAD",
        "card_type": "Cashback",
        "card_network": "Amex",
        "annual_fee": 119.88,
        "annual_fee_waiver": "",
        "signup_bonus": "10%返现(前4个月,上限$2,000消费)",
        "signup_bonus_requirement": "前4个月消费$2,000",
        "signup_bonus_value": 200,
        "rewards_rate": {"所有消费": 2},
        "rewards_type": "返现",
        "key_perks": ["简单2%返现", "旅行保险", "购物保障"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 2.5,
        "best_for": "简单返现",
        "notes": "无类别的简单2%返现，省心之选",
        "rating": 4.0,
        "tags": ["返现", "简单", "加拿大"]
    },
    # ===== 澳大利亚 =====
    {
        "id": "au-amex-explorer",
        "issuer": "American Express",
        "name": "Explorer Card",
        "local_name": "American Express Explorer Credit Card",
        "country": "AU",
        "currency": "AUD",
        "card_type": "Travel",
        "card_network": "Amex",
        "annual_fee": 395,
        "annual_fee_waiver": "",
        "signup_bonus": "100,000 Membership Rewards points",
        "signup_bonus_requirement": "首3个月消费$3,000",
        "signup_bonus_value": 1000,
        "rewards_rate": {"所有消费": 2, "海外": 3},
        "rewards_type": "积分 (Membership Rewards)",
        "key_perks": ["$400旅行报销", "Priority Pass", "旅行保险", "积分转里程"],
        "income_requirement": "",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 0,
        "best_for": "澳洲旅行者",
        "notes": "澳洲最热门的高端旅行卡之一",
        "rating": 4.4,
        "tags": ["旅行", "积分", "澳洲"]
    },
    {
        "id": "au-anz-rewards-black",
        "issuer": "ANZ",
        "name": "Rewards Black",
        "local_name": "ANZ Rewards Black",
        "country": "AU",
        "currency": "AUD",
        "card_type": "Rewards",
        "card_network": "Visa",
        "annual_fee": 375,
        "annual_fee_waiver": "",
        "signup_bonus": "100,000 ANZ Reward Points",
        "signup_bonus_requirement": "首3个月消费$3,000",
        "signup_bonus_value": 500,
        "rewards_rate": {"所有消费": 2, "海外": 3},
        "rewards_type": "积分",
        "key_perks": ["机场贵宾厅", "旅行保险", "购物保障", "积分转KrisFlyer"],
        "income_requirement": "年收入$75,000+",
        "credit_score_requirement": "",
        "foreign_transaction_fee": 0,
        "best_for": "ANZ银行用户",
        "notes": "ANZ高端卡，积分可转多个航空里程计划",
        "rating": 4.2,
        "tags": ["旅行", "积分", "澳洲"]
    },
]

# 预建索引，避免每次请求重建
_CARDS_BY_ID = {c["id"]: c for c in CARDS_DB}


def _filter_cards(
    cards: list,
    country: Optional[str] = None,
    max_annual_fee: Optional[float] = None,
    no_annual_fee: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = "rating",
    limit: int = 50,
) -> list:
    """筛选和排序卡片"""
    result = list(cards)

    # 国家筛选
    if country:
        country_upper = country.upper()
        result = [c for c in result if c["country"] == country_upper]

    # 最高年费筛选
    if max_annual_fee is not None:
        result = [c for c in result if c["annual_fee"] <= max_annual_fee]

    # 仅免年费
    if no_annual_fee:
        result = [c for c in result if c["annual_fee"] == 0]

    # 搜索（卡名、发卡行、本地名、标签）
    if search:
        search_lower = search.lower()
        result = [
            c for c in result
            if search_lower in c["name"].lower()
            or search_lower in c["issuer"].lower()
            or search_lower in c.get("local_name", "").lower()
            or any(search_lower in tag.lower() for tag in c.get("tags", []))
        ]

    # 排序
    effective_sort = sort_by if sort_by in VALID_SORT_FIELDS else "rating"
    if effective_sort == "annual_fee":
        result.sort(key=lambda x: x["annual_fee"])
    elif effective_sort == "signup_bonus_value":
        result.sort(key=lambda x: x.get("signup_bonus_value", 0), reverse=True)
    else:
        result.sort(key=lambda x: x.get("rating", 0), reverse=True)

    return result[:limit]


@router.get("/list")
def get_cards(
    country: Optional[str] = Query(None, description="按国家筛选"),
    max_annual_fee: Optional[float] = Query(None, description="最高年费"),
    no_annual_fee: Optional[bool] = Query(None, description="仅免年费"),
    search: Optional[str] = Query(None, description="搜索卡名/发卡行"),
    sort_by: str = Query("rating", description="排序: rating/annual_fee/signup_bonus_value"),
    limit: int = Query(50, description="返回数量"),
):
    """获取信用卡列表"""
    cards = _filter_cards(CARDS_DB, country, max_annual_fee, no_annual_fee, search, sort_by, limit)
    return {
        "cards": cards,
        "total": len(cards),
        "filters": {
            "country": country,
            "max_annual_fee": max_annual_fee,
            "no_annual_fee": no_annual_fee,
            "search": search,
            "sort_by": sort_by,
        },
    }


@router.get("/countries")
def get_countries():
    """获取支持的国家/地区列表"""
    countries = sorted(set(c["country"] for c in CARDS_DB))
    return {"countries": countries}


@router.get("/stats")
def get_stats():
    """获取统计数据"""
    total = len(CARDS_DB)
    countries = len(set(c["country"] for c in CARDS_DB))
    fees = [c["annual_fee"] for c in CARDS_DB]
    bonuses = [c.get("signup_bonus_value", 0) for c in CARDS_DB]

    return {
        "total_cards": total,
        "countries": countries,
        "avg_annual_fee": round(sum(fees) / total, 2) if total > 0 else 0,
        "highest_bonus": max(bonuses) if bonuses else 0,
    }


@router.get("/compare")
def compare_cards(ids: str = Query(..., description="逗号分隔的卡片ID")):
    """对比多张卡片"""
    id_list = [x.strip() for x in ids.split(",") if x.strip()]
    result = [_CARDS_BY_ID[i] for i in id_list if i in _CARDS_BY_ID]

    return {
        "cards": result,
        "requested": len(id_list),
        "found": len(result),
    }


@router.get("/detail/{card_id}")
def get_card_detail(card_id: str):
    """获取单张卡片详情"""
    card = _CARDS_BY_ID.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"卡片不存在: {card_id}")
    return card
