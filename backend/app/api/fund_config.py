"""LOF基金统一配置

合并基金套利、基金EST、QDII估算三个模块的底层资产映射。
作为唯一的基金配置数据源，供所有模块引用。

配置字段说明：
  - name: 基金名称
  - underlying: 底层资产新浪代码 (gb_xxx=美股ETF, hf_xxx=期货, rt_hkxxx=港股指数)
  - underlying_name: 底层资产名称
  - underlying_type: 底层资产类型 (us_etf / futures / hk_index / a_index / multi)
  - position: 仓位比例
  - calibration: 校准值 = 基金官方净值 / (底层资产价格 x 汇率 x 仓位)
  - multi_holdings: 多标的基金的持仓列表 (仅underlying_type="multi"时有效)
"""

from typing import Dict, List, Optional


# ==================== 统一基金配置 ====================
# key = 纯数字基金代码 (6位)
# 合并来源: fund_est.py LOF_FUND_CONFIG + MULTI_UNDERLYING_FUNDS + fund_service.py _UNDERLYING_MAP

FUND_CONFIG: Dict[str, dict] = {
    # =============================================
    # 美股QDII LOF (跟踪单一美股ETF)
    # =============================================

    # 纳指100类
    "161130": {"name": "纳斯达克100LOF", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.001012},
    "513100": {"name": "纳指ETF", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "513110": {"name": "纳指ETF易方达", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # 标普500类
    "161125": {"name": "标普500LOF", "underlying": "gb_spy", "underlying_name": "SPY标普500", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.000660},
    "513500": {"name": "标普ETF", "underlying": "gb_spy", "underlying_name": "SPY标普500", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # 标普行业类
    "161128": {"name": "标普信息科技LOF", "underlying": "gb_xlk", "underlying_name": "XLK信息科技", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.005944},
    "161126": {"name": "标普医疗保健LOF", "underlying": "gb_xlv", "underlying_name": "XLV医疗保健", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.001888},
    "161127": {"name": "标普生物科技LOF", "underlying": "gb_xbi", "underlying_name": "XBI生物科技", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.002163},

    # 美国消费/REIT
    "162415": {"name": "美国消费LOF", "underlying": "gb_xly", "underlying_name": "XLY美国消费", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.003913},
    "160140": {"name": "美国REIT精选LOF", "underlying": "gb_vnq", "underlying_name": "VNQ美国REIT", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.002249},

    # 中概互联网
    "164906": {"name": "中概互联网LOF", "underlying": "gb_kweb", "underlying_name": "KWEB中概互联", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.005742},
    "160644": {"name": "港美互联网LOF", "underlying": "gb_kweb", "underlying_name": "KWEB中概互联", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.012235},

    # 原油类 (部分用期货，部分用ETF)
    "162411": {"name": "华宝油气LOF", "underlying": "gb_xop", "underlying_name": "XOP油气开采", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.000846},
    "160416": {"name": "石油基金LOF", "underlying": "gb_uso", "underlying_name": "USO原油ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.002474},
    "162719": {"name": "石油LOF", "underlying": "gb_uso", "underlying_name": "USO原油ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.003201},
    "161129": {"name": "原油LOF易方达", "underlying": "gb_uso", "underlying_name": "USO原油ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.002060},
    "501018": {"name": "南方原油LOF", "underlying": "gb_uso", "underlying_name": "USO原油ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.002159},
    "160723": {"name": "嘉实原油LOF", "underlying": "gb_uso", "underlying_name": "USO原油ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.002458},

    # 大宗商品类
    "160216": {"name": "国泰商品LOF", "underlying": "gb_gsg", "underlying_name": "GSG商品指数", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.003553},
    "163208": {"name": "全球油气能源LOF", "underlying": "gb_xle", "underlying_name": "XLE能源板块", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.003575},
    "161815": {"name": "抗通胀LOF", "underlying": "gb_tip", "underlying_name": "TIP抗通胀债券", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.001585},
    "501300": {"name": "美元债LOF", "underlying": "gb_agg", "underlying_name": "AGG美国债券", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.001492},

    # 黄金白银类
    "160719": {"name": "嘉实黄金LOF", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.000787},
    "161116": {"name": "黄金主题LOF", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.000654},
    "164701": {"name": "黄金LOF", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.000690},
    "161226": {"name": "国投白银LOF", "underlying": "gb_slv", "underlying_name": "SLV白银ETF", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.005081},

    # 芯片/科技
    "501225": {"name": "全球芯片LOF", "underlying": "gb_soxx", "underlying_name": "SOXX半导体", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.000969},

    # 其他美股
    "165513": {"name": "中信保诚商品LOF", "underlying": "gb_djp", "underlying_name": "DJP商品指数", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.003499},
    "164824": {"name": "印度基金LOF", "underlying": "gb_inda", "underlying_name": "INDA印度基金", "underlying_type": "us_etf", "position": 0.95, "calibration": 0.004203},
    "513300": {"name": "纳指ETF嘉实", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "513390": {"name": "纳指ETF博时", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "513870": {"name": "纳指ETF富国", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159501": {"name": "纳指ETF基金", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159513": {"name": "纳指100ETF", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159632": {"name": "纳指100ETF基金", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159659": {"name": "纳指ETF招商", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159660": {"name": "纳指ETF指数", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159696": {"name": "纳指ETF华安", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159941": {"name": "纳指ETF广发", "underlying": "gb_qqq", "underlying_name": "QQQ纳指100", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "513650": {"name": "标普500ETF", "underlying": "gb_spy", "underlying_name": "SPY标普500", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159612": {"name": "标普500ETF基金", "underlying": "gb_spy", "underlying_name": "SPY标普500", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159655": {"name": "标普ETF博时", "underlying": "gb_spy", "underlying_name": "SPY标普500", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "513400": {"name": "道琼斯ETF", "underlying": "gb_dia", "underlying_name": "DIA道琼斯", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # 生物科技
    "513290": {"name": "纳指生物科技ETF", "underlying": "gb_ibb", "underlying_name": "IBB生物科技", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159502": {"name": "纳指生物科技ETF基金", "underlying": "gb_ibb", "underlying_name": "IBB生物科技", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # 油气
    "513350": {"name": "标普油气ETF", "underlying": "gb_xop", "underlying_name": "XOP油气开采", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159518": {"name": "标普油气ETF基金", "underlying": "gb_xop", "underlying_name": "XOP油气开采", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # 黄金
    "518880": {"name": "黄金ETF", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "518800": {"name": "黄金ETF华安", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159934": {"name": "黄金ETF易方达", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159937": {"name": "黄金ETF博时", "underlying": "gb_gld", "underlying_name": "GLD黄金ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # =============================================
    # 日本QDII LOF (跟踪日本指数)
    # =============================================
    "164821": {"name": "日本东证指数LOF", "underlying": "gb_topix", "underlying_name": "TOPIX东证指数", "underlying_type": "us_etf", "position": 0.95, "calibration": None},
    "513880": {"name": "日经225ETF", "underlying": "gb_ewj", "underlying_name": "EWJ日本ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "159866": {"name": "日经225ETF基金", "underlying": "gb_ewj", "underlying_name": "EWJ日本ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # =============================================
    # 欧洲QDII LOF (跟踪欧洲指数)
    # =============================================
    "513030": {"name": "德国DAX ETF", "underlying": "gb_ewg", "underlying_name": "EWG德国ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    # "513060" 曾误标为法国CAC40 ETF(EWQ)，实际为恒生科技ETF，已在港股ETF section定义
    "513050": {"name": "英国富时100 ETF", "underlying": "gb_ewu", "underlying_name": "EWU英国ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},
    "513150": {"name": "欧洲STOXX50 ETF", "underlying": "gb_fez", "underlying_name": "FEZ欧洲ETF", "underlying_type": "us_etf", "position": 1.0, "calibration": None},

    # =============================================
    # 东南亚/新兴市场QDII
    # =============================================
    # "164824" 印度基金LOF: 已在美股QDII section (line ~75) 定义，此处不再重复
    # "513010" 恒生科技指数ETF: 已在港股ETF section (line ~144) 定义，此处不再重复

    # =============================================
    # 港股QDII LOF (跟踪港股指数)
    # =============================================
    "501025": {"name": "香港银行LOF", "underlying": "rt_hkHSCEI", "underlying_name": "恒生中国企业指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000245},
    "161124": {"name": "港股小盘LOF", "underlying": "rt_hkHSCCI", "underlying_name": "恒生小型股指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000265},
    "160717": {"name": "H股LOF", "underlying": "rt_hkHSCEI", "underlying_name": "恒生中国企业指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000101},
    "161831": {"name": "恒生国企LOF", "underlying": "rt_hkHSCEI", "underlying_name": "恒生中国企业指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000102},
    "501302": {"name": "恒生指数基金LOF", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000054},
    "160924": {"name": "恒生指数LOF", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000047},
    "164705": {"name": "恒生LOF", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 0.95, "calibration": 0.000053},

    # 港股ETF
    "513060": {"name": "恒生科技ETF", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513180": {"name": "恒生科技指数ETF", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513380": {"name": "恒生科技ETF嘉实", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "159740": {"name": "恒生科技ETF基金", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "159741": {"name": "恒生科技ETF易方达", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "159742": {"name": "恒生科技ETF华夏", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513010": {"name": "恒生科技指数ETF", "underlying": "rt_hkHSTECH", "underlying_name": "恒生科技指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513020": {"name": "恒生互联网ETF", "underlying": "rt_hkHSCI", "underlying_name": "恒生互联网指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513130": {"name": "恒生国企ETF", "underlying": "rt_hkHSCEI", "underlying_name": "恒生中国企业指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513160": {"name": "恒生国企指数ETF", "underlying": "rt_hkHSCEI", "underlying_name": "恒生中国企业指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "159823": {"name": "恒生国企ETF基金", "underlying": "rt_hkHSCEI", "underlying_name": "恒生中国企业指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513600": {"name": "恒生指数ETF", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "513660": {"name": "恒生指数ETF华夏", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "159920": {"name": "恒生ETF", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},
    "159710": {"name": "恒生ETF基金", "underlying": "rt_hkHSI", "underlying_name": "恒生指数", "underlying_type": "hk_index", "position": 1.0, "calibration": None},

    # =============================================
    # 多标的基金 (跟踪多个ETF，需加权计算)
    # =============================================
    "501312": {
        "name": "海外科技LOF",
        "underlying": None,
        "underlying_name": "ARK系列ETF",
        "underlying_type": "multi",
        "position": 0.95,
        "calibration": 0.005036,
        "multi_holdings": [
            {"code": "gb_arkk", "name": "ARK Innovation ETF", "weight": 25.0},
            {"code": "gb_arkg", "name": "ARK Genomic Revolution ETF", "weight": 20.0},
            {"code": "gb_arkw", "name": "ARK Next Generation Internet ETF", "weight": 20.0},
            {"code": "gb_arkq", "name": "ARK Autonomous Technology & Robotics ETF", "weight": 15.0},
            {"code": "gb_arkf", "name": "ARK Fintech Innovation ETF", "weight": 10.0},
            {"code": "gb_arkx", "name": "ARK Space Exploration ETF", "weight": 10.0},
        ],
    },

    # =============================================
    # A股LOF基金 (用于做T策略)
    # =============================================
    "501043": {"name": "沪深300LOF", "underlying": "sh000300", "underlying_name": "沪深300指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "160706": {"name": "沪深300LOF", "underlying": "sh000300", "underlying_name": "沪深300指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "161005": {"name": "富国天惠LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "163407": {"name": "兴全沪深300LOF", "underlying": "sh000300", "underlying_name": "沪深300指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "168401": {"name": "红土创新精选LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "161227": {"name": "国投深证100LOF", "underlying": "sz399001", "underlying_name": "深证成指", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "161812": {"name": "深证100LOF", "underlying": "sz399001", "underlying_name": "深证成指", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "161032": {"name": "煤炭龙头LOF", "underlying": "sz399998", "underlying_name": "中证煤炭", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "168204": {"name": "煤炭LOF", "underlying": "sz399998", "underlying_name": "中证煤炭", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "502000": {"name": "500增强LOF", "underlying": "sh000905", "underlying_name": "中证500指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "160225": {"name": "新能源汽车LOF", "underlying": "sz399976", "underlying_name": "新能源汽车指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "160632": {"name": "酒LOF", "underlying": "sz399987", "underlying_name": "中证酒指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "160639": {"name": "高铁LOF", "underlying": "sz399992", "underlying_name": "中证高铁产业", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "161725": {"name": "白酒基金LOF", "underlying": "sz399997", "underlying_name": "中证白酒", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "161726": {"name": "生物医药LOF", "underlying": "sz399441", "underlying_name": "生物医药指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "162412": {"name": "医疗基金LOF", "underlying": "sz399989", "underlying_name": "中证医疗", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "163109": {"name": "申万深成LOF", "underlying": "sz399001", "underlying_name": "深证成指", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "163113": {"name": "申万证券LOF", "underlying": "sz399975", "underlying_name": "证券公司指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "167301": {"name": "保险主题LOF", "underlying": "sz399809", "underlying_name": "保险主题指数", "underlying_type": "a_index", "position": 0.95, "calibration": None},
    "160105": {"name": "南方积极LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "160106": {"name": "南方高增LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "160211": {"name": "国泰小盘LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "160324": {"name": "华夏磐晟LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "160421": {"name": "华安智增LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
    "160518": {"name": "博时睿远LOF", "underlying": None, "underlying_name": "主动管理型", "underlying_type": "active", "position": 0.95, "calibration": None},
}


# ==================== 港股汇率常量 ====================
_HKD_TO_CNY = 0.9


# ==================== 工具函数 ====================

def get_fund_config(fund_code: str) -> Optional[dict]:
    """获取基金配置（支持纯数字代码）"""
    return FUND_CONFIG.get(fund_code)


def get_all_fund_codes() -> List[str]:
    """获取所有配置的基金代码"""
    return list(FUND_CONFIG.keys())


def get_underlying_symbols() -> set:
    """获取所有底层资产的新浪代码（用于批量获取行情）"""
    symbols = set()
    for config in FUND_CONFIG.values():
        if config.get("underlying"):
            symbols.add(config["underlying"])
        for h in config.get("multi_holdings", []):
            symbols.add(h["code"])
    return symbols


def get_fund_name(fund_code: str) -> str:
    """获取基金名称"""
    config = FUND_CONFIG.get(fund_code, {})
    return config.get("name", fund_code)
