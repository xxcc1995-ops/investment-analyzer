"""
决策卫士 v2 — 基于认知科学的投资决策审查引擎

融合四本书的核心思想：
- 《思考快与慢》(Kahneman): System 1 vs System 2 双系统检测
- 《噪声》(Kahneman/Sibony/Sunstein): 判断一致性与噪声检测
- 《反直觉思考》(Adam Grant): 反向论证与认知弹性
- 逻辑学: 推理链条验证、谬误检测、因果分析

设计原则：
1. 快思维检测 → 发现直觉陷阱（System 1）
2. 逻辑验证 → 检查推理链条是否自洽
3. 反向论证 → 强制构建对立面
4. 前事分析 → 预演失败路径
5. 决策矩阵 → 量化评估，减少噪声
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Optional

# ============================================================
# 路径
# ============================================================
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
LOG_FILE = os.path.join(LOG_DIR, "decision_log.json")

# ============================================================
# 模块一：快思维检测 (System 1 Trap Detection)
# 来源：《思考快与慢》— 直觉系统的特征：快速、自动、情绪驱动、不费力
# ============================================================

SYSTEM1_TRAPS = {
    "fomo": {
        "name": "错失恐惧 (FOMO)",
        "icon": "🔥",
        "desc": "System 1 在驱动：看到机会就冲动行动，跳过了 System 2 的理性分析",
        "keywords": [
            "错过", "来不及", "最后机会", "暴涨", "起飞", "上车",
            "不买就没了", "大家都在买", "难得的机会", "机不可失",
            "大涨", "翻倍", "十倍", "百倍", "all in", "梭哈",
            "再不买就晚了", "已经涨了", "还会继续涨",
        ],
        "questions": [
            "如果这只标的明天跌20%，你还会做同样的决定吗？",
            "如果你错过了这次机会，最坏的结果是什么？那个结果你能接受吗？",
            "你是经过深思熟虑后做出的决定，还是看到别人赚钱后的心血来潮？",
        ],
    },
    "panic": {
        "name": "恐慌反应 (Panic)",
        "icon": "😱",
        "desc": "System 1 在驱动：亏损触发了损失厌恶，大脑在逃避痛苦而非理性分析",
        "keywords": [
            "亏", "割肉", "清仓", "跑路", "崩盘",
            "受不了", "心慌", "害怕", "赶紧卖", "先出来",
            "跌麻了", "亏麻了", "血亏", "腰斩", "暴跌",
            "割了", "跑了", "清了",
        ],
        "questions": [
            "你卖出是因为基本面变了，还是只是因为看到亏损心里难受？",
            "如果你今天不看账户，你还会做这个决定吗？",
            "假设你卖了之后它涨回来了，你会后悔吗？如果会，说明你内心并不真的想卖。",
        ],
    },
    "revenge": {
        "name": "复仇交易 (Revenge)",
        "icon": "⚔️",
        "desc": "System 1 在驱动：亏损带来的痛苦激活了扳回来的冲动，这不是投资，是赌博",
        "keywords": [
            "回本", "赚回来", "扳回来", "不甘心", "我要把亏的赚回来",
            "加倍", "加大仓位", "翻本", "捞回来",
        ],
        "questions": [
            "你是为了回本才做的这个决策吗？如果之前没有亏损，你还会这么做吗？",
            "你现在的心态是冷静的分析师，还是输了想翻本的赌徒？",
            "如果这笔交易又亏了，你会怎么做？会继续加仓吗？",
        ],
    },
    "herd": {
        "name": "从众效应 (Herd)",
        "icon": "🐑",
        "desc": "System 1 在驱动：用别人也在做替代了独立分析",
        "keywords": [
            "群里", "大V", "老师", "朋友说", "大家都在买",
            "热度", "爆款", "网红", "热搜", "刷屏",
            "雪球", "东财", "股吧", "论坛", "群里都说",
            "跟着", "抄作业", "跟单",
        ],
        "questions": [
            "如果没有人讨论这个标的，你还会关注它吗？",
            "你推荐给你朋友的理由，和你自己的买入理由一样吗？",
            "那些推荐的人，他们自己的持仓是怎样的？你知道吗？",
        ],
    },
    "overconfidence": {
        "name": "过度自信 (Overconfidence)",
        "icon": "💪",
        "desc": "System 1 在驱动：高估自己判断的准确性，低估不确定性",
        "keywords": [
            "肯定赚", "稳赚", "不会亏", "我有把握", "我很有信心",
            "这次不一样", "我比别人看得准", "我研究透了",
            "百分百", "万无一失",
        ],
        "questions": [
            "如果你的判断完全错误，最大亏损是多少？你能承受吗？",
            "你过去类似判断的胜率是多少？有什么统计数据支持？",
            "市场上那么多专业投资者，为什么只有你看到了这个机会？",
        ],
    },
    "anchoring": {
        "name": "锚定效应 (Anchoring)",
        "icon": "⚓",
        "desc": "System 1 在驱动：被某个数字（成本价/历史高点）锚定，而非分析内在价值",
        "keywords": [
            "成本价", "买入价", "回本", "目标价", "之前的价格",
            "曾经到过", "历史最高", "历史最低", "跌到过",
        ],
        "questions": [
            "你的目标价是怎么算出来的？如果买入价不同，目标价还会一样吗？",
            "如果你今天第一次看到这只标的，没有任何历史持仓，你还会给出同样的估值吗？",
            "你是在分析公司的价值，还是在盯着自己的成本价？",
        ],
    },
    "sunk_cost": {
        "name": "沉没成本 (Sunk Cost)",
        "icon": "🕳️",
        "desc": "System 1 在驱动：因为已经投入而不愿放弃，用过去的投入替代了对未来的分析",
        "keywords": [
            "已经亏了", "已经投入", "不甘心", "不能白亏",
            "都亏这么多了", "再等等", "再坚持一下",
        ],
        "questions": [
            "如果今天是第一次看到这只标的，没有任何持仓，你会建仓吗？",
            "你继续持有的理由是基于未来展望，还是因为已经亏了不想认输？",
            "如果这笔钱现在是现金，你会把它投到这个标的上吗？",
        ],
    },
    "confirmation": {
        "name": "确认偏差 (Confirmation)",
        "icon": "🔍",
        "desc": "System 1 在驱动：只看到支持自己观点的信息，自动过滤反面证据",
        "keywords": [
            "肯定", "一定", "绝对", "必须", "毫无疑问",
            "稳了", "铁定", "我确信", "我确定",
        ],
        "questions": [
            "你能列出3个支持**不做**这个决策的理由吗？",
            "有没有权威的反对观点？你认真研究过吗？",
            "如果你最信任的人持完全相反的观点，你会怎么想？",
        ],
    },
}

# ============================================================
# 模块二：逻辑谬误检测 (Logical Fallacy Detection)
# 来源：逻辑学 — 常见推理错误
# ============================================================

LOGICAL_FALLACIES = {
    "post_hoc": {
        "name": "事后归因谬误 (Post Hoc)",
        "icon": "🔗",
        "desc": "把时间先后关系当成了因果关系——A发生了，然后B涨了，所以A导致了B涨",
        "patterns": [
            (r"因为.*所以.*涨", "因果关系需验证"),
            (r"出了.*消息.*肯定.*涨", "消息面≠因果关系"),
            (r"上次.*也是这样.*所以", "样本量不足的类比"),
            (r"一.*就.*", "时间先后≠因果"),
        ],
        "question": "你声称的原因和结果之间，真的存在因果关系吗？还是只是时间上的先后？有没有其他可能的解释？",
    },
    "hasty_generalization": {
        "name": "以偏概全谬误 (Hasty Generalization)",
        "icon": "📊",
        "desc": "用极少的样本得出普遍结论——这只股票上次跌了就涨回来，所以这次也会",
        "patterns": [
            (r"上次.*也是.*所以", "个案不能代表规律"),
            (r"每次.*都.*", "你真的统计过每次吗？"),
            (r"从来都是", "绝对化表述"),
            (r"一直.*都.*", "你确定是'一直'吗？"),
        ],
        "question": "你用了多少个案例来支持这个结论？3个够吗？有没有反例？",
    },
    "false_dilemma": {
        "name": "非此即彼谬误 (False Dilemma)",
        "icon": "⚖️",
        "desc": "把复杂问题简化为两个极端选项——要么现在买，要么永远错过",
        "patterns": [
            (r"要么.*要么", "可能存在其他选项"),
            (r"不.*就.*", "不是非此即彼"),
            (r"现在不.*以后.*", "时间窗口可能比你想的长"),
        ],
        "question": "除了你列出的两个选项，还有没有第三种、第四种可能？比如部分建仓、等待回调、换一个标的？",
    },
    "appeal_to_authority": {
        "name": "诉诸权威谬误 (Appeal to Authority)",
        "icon": "👔",
        "desc": "用权威人物的观点替代自己的独立分析——巴菲特买了所以一定好",
        "patterns": [
            (r"巴菲特|芒格|索罗斯|达利欧|段永平", "权威≠正确"),
            (r"专家说|分析师说|研报说", "专家也会错"),
            (r"大V|老师|大佬", "意见领袖≠专业判断"),
        ],
        "question": "你引用的权威人物，他们买入的逻辑和你一样吗？他们的资金量、投资期限、风险承受能力和你一样吗？",
    },
    "survivorship_bias": {
        "name": "幸存者偏差 (Survivorship Bias)",
        "icon": "🏆",
        "desc": "只看到成功案例，忽略了大量失败案例——他靠这个赚了100倍，但你没看到亏光的那些人",
        "patterns": [
            (r"赚了.*倍", "你看到的是幸存者"),
            (r"翻倍|十倍|百倍", "成功案例被放大了"),
            (r"有人.*靠这个", "幸存者偏差"),
        ],
        "question": "你看到的成功案例，占所有尝试者的比例是多少？那些失败的人你了解过吗？",
    },
    "slippery_slope": {
        "name": "滑坡谬误 (Slippery Slope)",
        "icon": "⛷️",
        "desc": "没有证据地推导出极端后果——不买就会错过，错过就会后悔一辈子",
        "patterns": [
            (r"不.*就会.*就会", "连锁推导需要每一步的证据"),
            (r"再不.*就.*了", "极端推演"),
        ],
        "question": "你推导的链条中，每一步发生的概率分别是多少？最终结果的概率可能远低于你的直觉。",
    },
}

# ============================================================
# 模块三：情绪化表达检测
# ============================================================

EMOTIONAL_PATTERNS = [
    (r"[!！]{2,}", "过度激动的表达"),
    (r"[？?]{2,}", "焦虑/不确定的表达"),
    (r"冲{2,}|买{2,}|卖{2,}", "冲动性重复"),
    (r"啊{2,}|呀{2,}|哦{2,}|靠|卧槽|我草|我靠|尼玛", "情绪化用语"),
    (r"赶紧|赶快|立刻|马上|现在就", "紧迫感表达"),
    (r"(涨停|跌停).*(买|卖)", "追涨杀跌倾向"),
]


# ============================================================
# 数据持久化
# ============================================================

def _load_log() -> list:
    """加载决策日志"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_log(records: list):
    """保存决策日志"""
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ============================================================
# 分析引擎
# ============================================================

def _detect_system1_traps(reason: str, trigger: str) -> list:
    """
    模块一：快思维陷阱检测
    检测决策中 System 1 直觉系统的特征
    """
    text = f"{reason} {trigger}".lower()
    detected = []

    for trap_type, config in SYSTEM1_TRAPS.items():
        matched = [kw for kw in config["keywords"] if kw.lower() in text]
        if matched:
            detected.append({
                "type": trap_type,
                "name": config["name"],
                "icon": config["icon"],
                "desc": config["desc"],
                "matched_keywords": matched,
                "module": "system1",
            })

    # 检测无退出计划
    exit_keywords = ["止损", "止盈", "卖出", "清仓", "目标价", "退出"]
    has_exit_plan = any(kw in text for kw in exit_keywords)
    if not has_exit_plan:
        detected.append({
            "type": "no_exit_plan",
            "name": "无退出计划 (No Exit Plan)",
            "icon": "🚪",
            "desc": "你没有提到任何卖出条件——这不是投资，是买入然后祈祷",
            "matched_keywords": [],
            "module": "system1",
        })

    # 检测仓位过重
    position_keywords = ["全仓", "重仓", "梭哈", "all in", "大部分", "集中"]
    matched_pos = [kw for kw in position_keywords if kw in text]
    if matched_pos:
        detected.append({
            "type": "position_risk",
            "name": "仓位过重 (Concentration)",
            "icon": "⚖️",
            "desc": "单笔投资占比过高，风险集中——鸡蛋放在一个篮子里",
            "matched_keywords": matched_pos,
            "module": "system1",
        })

    # 检测情绪化表达
    emotional_flags = []
    for pattern, desc in EMOTIONAL_PATTERNS:
        if re.search(pattern, f"{reason} {trigger}"):
            emotional_flags.append(desc)

    if emotional_flags:
        detected.append({
            "type": "emotional_language",
            "name": "情绪化表达 (Emotional Language)",
            "icon": "😤",
            "desc": "你的文字充满了情绪——情绪越浓，System 1 越活跃，System 2 越沉默",
            "matched_keywords": emotional_flags,
            "module": "system1",
        })

    return detected


def _detect_logical_fallacies(reason: str, trigger: str) -> list:
    """
    模块二：逻辑谬误检测
    检查推理链条是否逻辑自洽
    """
    text = f"{reason} {trigger}"
    detected = []

    for fallacy_type, config in LOGICAL_FALLACIES.items():
        matched_patterns = []
        for pattern, desc in config["patterns"]:
            if re.search(pattern, text):
                matched_patterns.append(desc)

        if matched_patterns:
            detected.append({
                "type": fallacy_type,
                "name": config["name"],
                "icon": config["icon"],
                "desc": config["desc"],
                "matched_keywords": matched_patterns,
                "module": "logic",
            })

    return detected


def _check_causal_chain(reason: str) -> dict:
    """
    模块三：因果链条分析
    来源：逻辑学 — 因果推理的严谨性检查

    检查用户推理中的因果链条：
    - 提取"因为A，所以B"结构
    - 检查每个环节是否有证据支撑
    - 标记薄弱环节
    """
    issues = []
    strengths = []

    # 检查是否有因果推理结构
    causal_patterns = [
        (r"因为(.{2,30})[，,].*所以(.{2,30})", "因果声明"),
        (r"由于(.{2,30})[，,].*因此(.{2,30})", "因果声明"),
        (r"(.{2,30})导致(.{2,30})", "因果声明"),
        (r"(.{2,30})推动(.{2,30})", "因果声明"),
    ]

    has_causal = False
    for pattern, label in causal_patterns:
        matches = re.findall(pattern, reason)
        if matches:
            has_causal = True
            for match in matches:
                cause = match[0].strip()
                effect = match[1].strip()
                # 检查因果是否过于简单化
                if len(cause) < 5 or len(effect) < 5:
                    issues.append(f"因果描述过于简略：「{cause}→{effect}」，真实的因果关系往往更复杂")
                else:
                    strengths.append(f"检测到因果推理：「{cause}→{effect}」")

    if not has_causal and len(reason) > 30:
        issues.append("你的理由中没有明确的因果推理——你是在陈述结论，而不是在论证")

    # 检查是否有数据支撑
    data_patterns = [
        r"\d+%", r"\d+倍", r"PE", r"PB", r"ROE", r"营收", r"利润",
        r"市盈率", r"市净率", r"股息率", r"估值", r"业绩",
    ]
    has_data = any(re.search(p, reason) for p in data_patterns)
    if has_data:
        strengths.append("引用了具体数据或财务指标")
    elif len(reason) > 50:
        issues.append("你的理由中没有引用任何数据——纯定性分析容易被情绪污染")

    # 检查是否有时间框架
    time_patterns = [r"未来\d+", r"今年", r"明年", r"长期", r"短期", r"几年"]
    has_timeframe = any(re.search(p, reason) for p in time_patterns)
    if has_timeframe:
        strengths.append("提到了时间框架")

    return {
        "issues": issues,
        "strengths": strengths,
        "has_causal": has_causal,
        "has_data": has_data,
        "has_timeframe": has_timeframe,
    }


def _build_reverse_argument(decision_type: str, target: str, reason: str) -> dict:
    """
    模块四：反向论证构建
    来源：《反直觉思考》— 主动寻找反面证据

    不是简单问"你考虑过反面吗"，而是帮用户构建反向论证的框架
    """
    if decision_type == "buy":
        action = "买入"
        reverse_action = "不买/卖出"
        reverse_framework = {
            "thesis": f"反对买入 {target} 的论证框架",
            "points": [
                "估值过高：当前价格是否已经反映了所有利好？",
                "基本面恶化：有哪些负面因素被你忽略了？",
                "机会成本：同样的钱投到其他地方是否更好？",
                "时机问题：即使标的好，现在是好的买入时机吗？",
                "风险不对称：上涨空间和下跌风险哪个更大？",
            ],
            "challenge": "如果你必须用100字说服自己不要买，你会怎么说？",
        }
    elif decision_type == "sell":
        action = "卖出"
        reverse_action = "继续持有"
        reverse_framework = {
            "thesis": f"反对卖出 {target} 的论证框架",
            "points": [
                "基本面是否真的变了？还是只是短期波动？",
                "卖出后资金去哪？有更好的选择吗？",
                "如果卖出后涨了，你能接受吗？",
                "你是在逃避亏损，还是在做理性止损？",
                "当初买入的逻辑还成立吗？如果成立，为什么要卖？",
            ],
            "challenge": "如果你必须用100字说服自己继续持有，你会怎么说？",
        }
    else:
        action = "持有/观望"
        reverse_action = "采取行动"
        reverse_framework = {
            "thesis": f"反对观望 {target} 的论证框架",
            "points": [
                "你在等什么具体信号？如果等不到怎么办？",
                "观望本身也是一种决策——你分析过观望的机会成本吗？",
                "市场不会等你——你确定现在不是好的入场/出场时机吗？",
            ],
            "challenge": "如果你必须用100字说服自己现在就行动，你会怎么说？",
        }

    return reverse_framework


def _generate_noise_check(reason: str, decision_type: str) -> dict:
    """
    模块五：噪声检测
    来源：《噪声》— 检测当前判断是否偏离了"冷静状态下的你"

    核心思想：好的决策应该在不同时间、不同情绪下保持一致。
    如果你的判断很容易被外部因素左右，那就是噪声。
    """
    noise_signals = []

    # 检查是否受时间压力影响
    urgency_words = ["赶紧", "赶快", "立刻", "马上", "现在就", "今天必须", "来不及"]
    if any(w in reason for w in urgency_words):
        noise_signals.append({
            "signal": "时间压力",
            "detail": "你感受到了时间压力——《噪声》指出，时间压力是判断噪声的最大来源之一",
            "mitigation": "问自己：如果多给我一周时间，我会做同样的决定吗？",
        })

    # 检查是否受近期事件影响
    recent_event_words = ["刚看到", "今天", "刚才", "刚刚", "昨天", "上周"]
    if any(w in reason for w in recent_event_words):
        noise_signals.append({
            "signal": "近因效应",
            "detail": "你的判断受到了近期事件的强烈影响——近因效应会让近期事件的权重被放大",
            "mitigation": "问自己：如果这件事发生在一个月前，我还会这么在意吗？",
        })

    # 检查是否受情绪状态影响
    emotional_words = ["兴奋", "害怕", "焦虑", "开心", "难过", "愤怒", "沮丧", "激动"]
    if any(w in reason for w in emotional_words):
        noise_signals.append({
            "signal": "情绪干扰",
            "detail": "你明确表达了情绪状态——情绪是判断噪声的重要来源",
            "mitigation": "问自己：如果我现在心情平静，会做同样的决定吗？",
        })

    # 检查是否受他人影响
    social_words = ["朋友说", "群里", "大V", "老师", "大家都", "论坛"]
    if any(w in reason for w in social_words):
        noise_signals.append({
            "signal": "社会压力",
            "detail": "你的判断受到了他人观点的影响——《噪声》指出，群体讨论往往增加噪声而非减少",
            "mitigation": "问自己：如果没有人跟我讨论过这个，我还会这么想吗？",
        })

    return {
        "noise_count": len(noise_signals),
        "signals": noise_signals,
        "consistency_prompt": "如果让你在完全不同的时间、完全不同的心情下做这个决定，你觉得结果会一样吗？",
    }


def _generate_pre_mortem(decision_type: str, target: str, reason: str) -> dict:
    """
    模块六：前事分析 (Pre-Mortem)
    来源：《思考快与慢》+ 《反直觉思考》
    — 想象决策已经失败，回溯最可能的失败原因

    不是问"会不会亏"，而是问"如果亏了，最可能的原因是什么"
    """
    if decision_type == "buy":
        scenario = "你买入后一年，这笔投资亏损了50%"
        failure_modes = [
            {"mode": "估值泡沫", "question": "你买入时的估值是否处于历史高位？你确定不是在追高吗？"},
            {"mode": "基本面恶化", "question": "你分析过这个行业/公司可能面临的最坏情况吗？"},
            {"mode": "宏观风险", "question": "如果经济衰退、利率上升、政策变化，你的标的会怎样？"},
            {"mode": "流动性风险", "question": "如果急需用钱，你能以合理价格卖出吗？"},
            {"mode": "认知盲区", "question": "你确定你理解这个标的吗？能用3句话说清楚它的商业模式吗？"},
        ]
    elif decision_type == "sell":
        scenario = "你卖出后一年，这笔投资涨了200%"
        failure_modes = [
            {"mode": "底部割肉", "question": "你确定不是在最恐慌的时候卖出了吗？"},
            {"mode": "错过反弹", "question": "你分析过历史上类似情况的反弹概率吗？"},
            {"mode": "资金去向", "question": "卖出后的资金，你有更好的去处吗？还是只是变成了现金？"},
            {"mode": "情绪驱动", "question": "如果这笔投资没有亏损，你还会卖出吗？"},
            {"mode": "短期视角", "question": "你是在用短期波动来判断长期价值吗？"},
        ]
    else:
        scenario = "你观望了一年，错过了最佳入场/出场时机"
        failure_modes = [
            {"mode": "分析瘫痪", "question": "你是在等待完美时机吗？完美时机永远不会来。"},
            {"mode": "机会成本", "question": "观望期间你的资金在做什么？有没有更好的选择？"},
            {"mode": "信号模糊", "question": "你在等什么具体信号？这个信号真的能告诉你什么吗？"},
        ]

    return {
        "scenario": scenario,
        "failure_modes": failure_modes,
        "instruction": f"假设{scenario}。请认真写下最可能的3个原因。",
    }


def _calculate_decision_matrix(reason: str, system1_traps: list,
                                logical_fallacies: list, noise_check: dict,
                                causal_chain: dict) -> dict:
    """
    模块七：决策矩阵评分
    来源：《噪声》— 用结构化评估替代主观打分，减少评分噪声

    五个维度各20分，总分100：
    1. 情绪控制 (Emotional Control) — System 1 是否被抑制
    2. 逻辑自洽 (Logical Consistency) — 推理链条是否成立
    3. 反向论证 (Reverse Thinking) — 是否考虑了反面
    4. 信息质量 (Information Quality) — 是否有数据支撑
    5. 噪声控制 (Noise Control) — 判断是否稳定一致
    """
    # 维度一：情绪控制（20分）
    emotion_score = 20
    system1_count = len(system1_traps)
    if system1_count >= 3:
        emotion_score = max(0, 20 - system1_count * 5)
    elif system1_count >= 1:
        emotion_score = max(5, 20 - system1_count * 4)

    # 维度二：逻辑自洽（20分）
    logic_score = 20
    fallacy_count = len(logical_fallacies)
    if fallacy_count >= 2:
        logic_score = max(0, 20 - fallacy_count * 6)
    elif fallacy_count >= 1:
        logic_score = max(8, 20 - fallacy_count * 5)

    # 因果链条质量调整
    if not causal_chain.get("has_causal") and len(reason) > 30:
        logic_score = max(0, logic_score - 5)
    if causal_chain.get("has_data"):
        logic_score = min(20, logic_score + 3)

    # 维度三：反向论证（20分）— 在 Step 4 中评估
    # 这里给一个基础分，Step 4 的回答会调整
    reverse_score = 12  # 基础分，等用户回答后调整

    # 维度四：信息质量（20分）
    info_score = 10  # 基础分
    if causal_chain.get("has_data"):
        info_score += 5
    if causal_chain.get("has_causal"):
        info_score += 3
    if causal_chain.get("has_timeframe"):
        info_score += 2

    # 维度五：噪声控制（20分）
    noise_score = 20
    noise_count = noise_check.get("noise_count", 0)
    noise_score = max(0, 20 - noise_count * 5)

    total = emotion_score + logic_score + reverse_score + info_score + noise_score

    return {
        "total": max(0, min(100, total)),
        "dimensions": {
            "emotion": {"score": emotion_score, "max": 20, "name": "情绪控制",
                        "desc": "System 1 是否被有效抑制"},
            "logic": {"score": logic_score, "max": 20, "name": "逻辑自洽",
                      "desc": "推理链条是否严密"},
            "reverse": {"score": reverse_score, "max": 20, "name": "反向论证",
                        "desc": "是否认真考虑了反面"},
            "info": {"score": info_score, "max": 20, "name": "信息质量",
                     "desc": "是否有数据和事实支撑"},
            "noise": {"score": noise_score, "max": 20, "name": "噪声控制",
                      "desc": "判断是否稳定、不被干扰"},
        },
    }


# ============================================================
# 问题生成
# ============================================================

def generate_questions(system1_traps: list, logical_fallacies: list,
                       noise_check: dict, reverse_arg: dict,
                       pre_mortem: dict, decision_type: str) -> list:
    """
    生成针对性的灵魂质问
    每个模块生成1-2个最关键的质问，总共7个
    """
    questions = []
    seen = set()

    # 从 System 1 陷阱中取最关键的2个
    for trap in system1_traps[:2]:
        config = SYSTEM1_TRAPS.get(trap["type"], {})
        qs = config.get("questions", [])
        if qs:
            questions.append({
                "id": len(questions) + 1,
                "question": qs[0],
                "module": "system1",
                "module_name": "快思维检测",
                "tag": trap["name"],
                "answer": "",
            })
            seen.add(trap["type"])

    # 从逻辑谬误中取1个
    for fallacy in logical_fallacies[:1]:
        config = LOGICAL_FALLACIES.get(fallacy["type"], {})
        if config.get("question"):
            questions.append({
                "id": len(questions) + 1,
                "question": config["question"],
                "module": "logic",
                "module_name": "逻辑验证",
                "tag": fallacy["name"],
                "answer": "",
            })

    # 反向论证问题
    questions.append({
        "id": len(questions) + 1,
        "question": reverse_arg.get("challenge", "请认真写下反对你这个决策的最强论证"),
        "module": "reverse",
        "module_name": "反向论证",
        "tag": "反面思考",
        "answer": "",
    })

    # 噪声检测问题
    questions.append({
        "id": len(questions) + 1,
        "question": noise_check.get("consistency_prompt", "如果在完全不同的时间心情下做这个决定，结果会一样吗？"),
        "module": "noise",
        "module_name": "噪声检测",
        "tag": "一致性",
        "answer": "",
    })

    # 前事分析问题
    questions.append({
        "id": len(questions) + 1,
        "question": pre_mortem.get("instruction", "假设这个决策已经失败了，最可能的原因是什么？"),
        "module": "pre_mortem",
        "module_name": "前事分析",
        "tag": "失败预演",
        "answer": "",
    })

    # 因果链条问题
    questions.append({
        "id": len(questions) + 1,
        "question": "请用「因为A，所以B，所以C」的格式，写下你完整的推理链条。每一步都需要有证据支撑。",
        "module": "causal",
        "module_name": "因果分析",
        "tag": "推理链条",
        "answer": "",
    })

    return questions[:7]


# ============================================================
# 诊断评分（含回答质量评估）
# ============================================================

def _evaluate_answers(answers: list, matrix: dict) -> dict:
    """
    评估回答质量，调整反向论证维度的分数
    """
    reverse_score = matrix["dimensions"]["reverse"]["score"]

    # 查找反向论证的回答
    for qa in answers:
        answer = qa.get("answer", "").strip()
        if not answer:
            continue

        # 反向论证回答质量评估
        if qa.get("module") == "reverse":
            if len(answer) > 100:
                reverse_score = 18  # 认真构建了反向论证
            elif len(answer) > 50:
                reverse_score = 15
            elif len(answer) > 20:
                reverse_score = 12
            else:
                reverse_score = 8  # 敷衍

        # 因果链条回答质量评估
        if qa.get("module") == "causal":
            if "因为" in answer and "所以" in answer:
                matrix["dimensions"]["logic"]["score"] = min(
                    20, matrix["dimensions"]["logic"]["score"] + 3
                )
            if any(c.isdigit() for c in answer):
                matrix["dimensions"]["info"]["score"] = min(
                    20, matrix["dimensions"]["info"]["score"] + 2
                )

    matrix["dimensions"]["reverse"]["score"] = reverse_score

    # 重新计算总分
    total = sum(d["score"] for d in matrix["dimensions"].values())
    matrix["total"] = max(0, min(100, total))

    # 检查空回答
    empty_count = sum(1 for qa in answers if not qa.get("answer", "").strip())
    if empty_count > 0:
        penalty = empty_count * 3
        matrix["total"] = max(0, matrix["total"] - penalty)

    return matrix


def _generate_summary(matrix: dict, system1_traps: list, logical_fallacies: list) -> dict:
    """生成诊断总结"""
    total = matrix["total"]

    if total >= 85:
        level = "excellent"
        level_text = "🟢 优秀"
        summary = "你的决策过程展现了高度的理性和自制力。System 2 在主导，逻辑链条清晰，反向论证充分。继续保持。"
    elif total >= 70:
        level = "good"
        level_text = "🔵 良好"
        summary = "你的决策过程整体理性，但有一些值得深挖的盲点。认真审视下面的建议。"
    elif total >= 55:
        level = "caution"
        level_text = "🟡 需谨慎"
        summary = "你的决策中存在明显的认知偏误或逻辑漏洞。建议暂停，至少冷静24小时后再决定。"
    elif total >= 40:
        level = "danger"
        level_text = "🔴 高风险"
        summary = "你的决策被情绪和直觉主导，System 2 几乎没有参与。强烈建议暂停48小时。"
    else:
        level = "critical"
        level_text = "🚨 极高风险"
        summary = "这不是投资决策，这是情绪宣泄。请立即停止，至少冷静72小时。如果可能，找一个你信任的人谈谈。"

    # 生成建议
    suggestions = []
    dim = matrix["dimensions"]

    if dim["emotion"]["score"] < 12:
        suggestions.append("🧘 你的情绪在主导决策。先离开屏幕，做10次深呼吸，等30分钟后再看。")
    if dim["logic"]["score"] < 12:
        suggestions.append("📐 你的推理链条有漏洞。拿出纸笔，写下完整的因果链，检查每一步是否有证据。")
    if dim["reverse"]["score"] < 10:
        suggestions.append("🔄 你没有认真考虑反面。花30分钟，专门寻找反对你这个决策的证据。")
    if dim["info"]["score"] < 10:
        suggestions.append("📊 你的决策缺乏数据支撑。回到基本面，用数字而非感觉来分析。")
    if dim["noise"]["score"] < 10:
        suggestions.append("📡 你的判断受到了外部干扰。关闭所有信息来源，问自己：如果没有这些噪音，我还会这么想吗？")
    if total < 55:
        suggestions.append("⏰ 建议延迟执行决策，给自己至少24小时的冷静期。")

    # 检查是否有无退出计划
    has_exit = any(t["type"] == "no_exit_plan" for t in system1_traps)
    if has_exit:
        suggestions.append("🚪 必须制定明确的止损和止盈计划后再执行。没有退出计划的投资不是投资，是赌博。")

    if not suggestions:
        suggestions.append("✅ 继续保持理性的决策习惯。定期回顾决策日志，用结果校准判断。")

    return {
        "score": total,
        "level": level,
        "level_text": level_text,
        "summary": summary,
        "suggestions": suggestions,
    }


# ============================================================
# 快速扫描（理性门卫用）
# ============================================================

def quick_scan(intention: str, thought: str) -> dict:
    """
    轻量级情绪扫描，用于 App 启动时的理性门卫。

    Args:
        intention: 用户意图 (buy/sell/adjust)
        thought: 用户当前想法（一句话）

    Returns:
        dict: {risk_level, score, triggers, message, recommendation}
    """
    if not thought.strip():
        return {
            "risk_level": "low",
            "score": 90,
            "triggers": [],
            "message": "你没有表达具体想法，这本身就是一个好信号——说明你还没有被情绪驱动。",
            "recommendation": "pass",
        }

    # 快速扫描情绪触发词
    triggers = []
    text = thought.lower()

    # 检查情绪化表达
    for pattern, desc in EMOTIONAL_PATTERNS:
        if re.search(pattern, thought):
            triggers.append(desc)

    # 检查 System 1 陷阱关键词（只检查最危险的几个）
    critical_traps = {
        "fomo": SYSTEM1_TRAPS["fomo"]["keywords"],
        "panic": SYSTEM1_TRAPS["panic"]["keywords"],
        "revenge": SYSTEM1_TRAPS["revenge"]["keywords"],
    }
    for trap_type, keywords in critical_traps.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            triggers.append(SYSTEM1_TRAPS[trap_type]["name"])

    # 检查噪声信号
    noise_words = ["赶紧", "赶快", "立刻", "马上", "现在就", "来不及", "今天必须"]
    if any(w in text for w in noise_words):
        triggers.append("时间压力")

    # 计算分数
    score = 100
    score -= len(triggers) * 15
    score = max(0, min(100, score))

    # 确定风险等级
    if score >= 70:
        risk_level = "low"
        recommendation = "pass"
        message = "你的表达冷静、有逻辑。继续保持理性。"
    elif score >= 40:
        risk_level = "medium"
        recommendation = "warn"
        message = "检测到一些情绪信号。建议先深呼吸，想清楚再行动。"
    else:
        risk_level = "high"
        recommendation = "full_check"
        message = "你的表达充满了情绪。现在不是做投资决策的好时机。"

    return {
        "risk_level": risk_level,
        "score": score,
        "triggers": triggers,
        "message": message,
        "recommendation": recommendation,
    }


# ============================================================
# 模块八：情绪量化评分
# 来源：行为金融学 — 将情绪强度从"感觉"变成"数字"
# ============================================================

def _calculate_sentiment_score(reason: str, trigger: str,
                               system1_traps: list, noise_check: dict) -> dict:
    """
    将情绪状态量化为0-100的分数。
    100=完全理性，0=完全情绪化。

    维度：
    1. 语言确定性 — 过度确定=情绪化
    2. 紧迫感 — 时间压力=情绪化
    3. 从众信号 — 跟随他人=缺乏独立思考
    4. 情绪词汇密度 — 情绪词越多越情绪化
    """
    text = f"{reason} {trigger}"
    signals = []

    # 1. 确定性过高（100%确定=情绪化信号）
    certainty_words = ["肯定", "一定", "绝对", "必须", "百分百", "稳赚", "不会亏",
                       "毫无疑问", "铁定", "万无一失"]
    certainty_hits = [w for w in certainty_words if w in text]
    if certainty_hits:
        signals.append({
            "signal": "过度确定",
            "detail": f"你使用了{len(certainty_hits)}个绝对化表达——真正的确定性在投资中几乎不存在",
            "score_penalty": min(20, len(certainty_hits) * 7),
            "type": "certainty",
        })

    # 2. 紧迫感
    urgency_words = ["赶紧", "赶快", "立刻", "马上", "现在就", "来不及",
                     "今天必须", "最后机会", "再不就晚了"]
    urgency_hits = [w for w in urgency_words if w in text]
    if urgency_hits:
        signals.append({
            "signal": "时间压力",
            "detail": f"检测到{len(urgency_hits)}个紧迫感表达——好的投资机会不会因为多想一天就消失",
            "score_penalty": min(20, len(urgency_hits) * 8),
            "type": "urgency",
        })

    # 3. 从众信号
    herd_words = ["大家", "群里", "大V", "老师", "朋友说", "论坛", "跟着",
                  "抄作业", "跟单", "热搜", "刷屏", "爆款"]
    herd_hits = [w for w in herd_words if w in text]
    if herd_hits:
        signals.append({
            "signal": "从众倾向",
            "detail": f"检测到{len(herd_hits)}个从众信号——独立思考是投资盈利的基础",
            "score_penalty": min(15, len(herd_hits) * 5),
            "type": "herd",
        })

    # 4. 情绪词汇密度
    emotional_words = ["兴奋", "害怕", "焦虑", "开心", "难过", "愤怒", "沮丧",
                       "激动", "心慌", "害怕", "恐惧", "贪婪", "后悔", "不甘"]
    emotion_hits = [w for w in emotional_words if w in text]
    if emotion_hits:
        signals.append({
            "signal": "情绪表达",
            "detail": f"检测到{len(emotion_hits)}个情绪词汇——情绪越浓，理性越弱",
            "score_penalty": min(15, len(emotion_hits) * 5),
            "type": "emotion",
        })

    # 计算总扣分
    total_penalty = sum(s["score_penalty"] for s in signals)
    score = max(0, 100 - total_penalty)

    # 从噪声检测中获取额外信号
    noise_count = noise_check.get("noise_count", 0)
    if noise_count > 0:
        score = max(0, score - noise_count * 5)

    # 从System1陷阱中获取额外信号
    if len(system1_traps) > 0:
        score = max(0, score - len(system1_traps) * 8)

    score = max(0, min(100, score))

    if score >= 80:
        level = "rational"
        level_text = "理性"
        advice = "你的情绪状态良好，适合做投资决策。"
    elif score >= 60:
        level = "mild_emotion"
        level_text = "轻微情绪化"
        advice = "有一些情绪信号，建议再审视一遍你的理由。"
    elif score >= 40:
        level = "moderate_emotion"
        level_text = "中度情绪化"
        advice = "情绪在影响你的判断。建议暂停，至少冷静几小时。"
    else:
        level = "high_emotion"
        level_text = "高度情绪化"
        advice = "现在不适合做投资决策。请离开屏幕，等情绪平复后再来。"

    return {
        "score": score,
        "level": level,
        "level_text": level_text,
        "advice": advice,
        "signals": signals,
    }


# ============================================================
# 模块九：多维风险评估
# 来源：风险管理理论 — 从5个维度量化决策风险
# ============================================================

def _assess_risk(decision_type: str, target: str, reason: str,
                 position_pct: str, time_horizon: str,
                 system1_traps: list, logical_fallacies: list) -> dict:
    """
    多维风险评估，输出0-100的风险分数（越高越危险）。

    维度：
    1. 仓位风险 — 仓位越重，风险越高
    2. 认知偏误风险 — 检出的偏误越多，风险越高
    3. 逻辑风险 — 推理漏洞越多，风险越高
    4. 时间框架风险 — 短线+重仓=极高风险
    5. 标的集中风险 — 过度集中于单一标的
    """
    risk_score = 0
    risk_factors = []

    # 1. 仓位风险（0-25分）
    position_risk_map = {
        "light": 5, "medium": 12, "heavy": 20, "all": 25, "": 8,
    }
    pos_risk = position_risk_map.get(position_pct, 8)
    risk_score += pos_risk
    if position_pct in ("heavy", "all"):
        risk_factors.append({
            "factor": "仓位过重",
            "severity": "high" if position_pct == "all" else "medium",
            "detail": f"仓位'{position_pct}'意味着高集中度，单一标的下跌将严重影响整体资产",
            "mitigation": "建议单笔投资不超过总资产的20%",
        })

    # 2. 认知偏误风险（0-25分）
    bias_risk = min(25, len(system1_traps) * 6)
    risk_score += bias_risk
    critical_biases = [t for t in system1_traps if t["type"] in ("fomo", "panic", "revenge")]
    if critical_biases:
        risk_factors.append({
            "factor": "高危认知偏误",
            "severity": "high",
            "detail": f"检出{len(critical_biases)}个高危偏误：{', '.join(t['name'] for t in critical_biases)}",
            "mitigation": "必须至少冷静24小时后再决策",
        })

    # 3. 逻辑风险（0-20分）
    logic_risk = min(20, len(logical_fallacies) * 7)
    risk_score += logic_risk
    if logical_fallacies:
        risk_factors.append({
            "factor": "逻辑漏洞",
            "severity": "medium",
            "detail": f"推理中存在{len(logical_fallacies)}个逻辑谬误",
            "mitigation": "重新审视你的因果推理链条",
        })

    # 4. 时间框架风险（0-15分）
    time_risk_map = {
        "short": 15, "swing": 10, "medium": 5, "long": 3, "": 8,
    }
    time_risk = time_risk_map.get(time_horizon, 8)
    risk_score += time_risk
    if time_horizon == "short" and position_pct in ("heavy", "all"):
        risk_factors.append({
            "factor": "短线+重仓",
            "severity": "critical",
            "detail": "短线交易+重仓是爆仓的典型组合",
            "mitigation": "短线交易仓位不应超过10%",
        })

    # 5. 退出计划风险（0-15分）
    exit_keywords = ["止损", "止盈", "卖出条件", "目标价", "退出"]
    has_exit = any(kw in reason for kw in exit_keywords)
    if not has_exit:
        risk_score += 12
        risk_factors.append({
            "factor": "无退出计划",
            "severity": "high",
            "detail": "没有止损/止盈计划的投资等于赌博",
            "mitigation": "在执行前必须制定明确的止损和止盈价格",
        })

    risk_score = max(0, min(100, risk_score))

    if risk_score <= 25:
        risk_level = "low"
        risk_text = "低风险"
        risk_advice = "风险可控，但仍需保持纪律。"
    elif risk_score <= 50:
        risk_level = "moderate"
        risk_text = "中等风险"
        risk_advice = "存在一些风险因素，建议审视后再执行。"
    elif risk_score <= 75:
        risk_level = "high"
        risk_text = "高风险"
        risk_advice = "风险因素较多，强烈建议降低仓位或推迟决策。"
    else:
        risk_level = "critical"
        risk_text = "极高风险"
        risk_advice = "不建议执行此决策。请大幅降低仓位或放弃。"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_text": risk_text,
        "risk_advice": risk_advice,
        "risk_factors": risk_factors,
        "dimensions": {
            "position": {"score": pos_risk, "max": 25, "name": "仓位风险"},
            "bias": {"score": bias_risk, "max": 25, "name": "认知偏误"},
            "logic": {"score": logic_risk, "max": 25, "name": "逻辑漏洞"},
            "timeframe": {"score": time_risk, "max": 15, "name": "时间框架"},
            "exit_plan": {"score": 12 if not has_exit else 0, "max": 15, "name": "退出计划"},
        },
    }


# ============================================================
# 模块十：仓位建议（基于凯利公式 + 偏误调整）
# 来源：Kelly Criterion + 行为金融学
# ============================================================

def _calculate_position_recommendation(decision_type: str, risk_assessment: dict,
                                       sentiment_score: dict, position_pct: str) -> dict:
    """
    基于凯利公式和风险评估，给出仓位建议。

    不是直接告诉用户"买多少"，而是给出风险调整后的建议仓位上限。
    """
    risk_score = risk_assessment.get("risk_score", 50)
    sentiment = sentiment_score.get("score", 50)

    # 基础建议仓位（基于风险分数）
    if risk_score <= 20:
        suggested_max = 0.20  # 低风险：最多20%
        label = "可适度建仓"
    elif risk_score <= 40:
        suggested_max = 0.15  # 中低风险：最多15%
        label = "建议轻仓"
    elif risk_score <= 60:
        suggested_max = 0.10  # 中等风险：最多10%
        label = "建议小仓位"
    elif risk_score <= 80:
        suggested_max = 0.05  # 高风险：最多5%
        label = "极小仓位试探"
    else:
        suggested_max = 0.00  # 极高风险：不建议
        label = "不建议建仓"

    # 情绪调整：情绪越重，建议仓位越低
    if sentiment < 40:
        suggested_max *= 0.3
        emotion_adj = "情绪极度不理性，仓位降至30%"
    elif sentiment < 60:
        suggested_max *= 0.6
        emotion_adj = "情绪较重，仓位降至60%"
    else:
        emotion_adj = "情绪可控，无需额外调整"

    # 卖出/观望时的建议
    if decision_type == "sell":
        if risk_score > 60:
            label = "建议分批卖出"
            advice_detail = "风险较高，不要一次性清仓，分2-3批卖出降低时机风险"
        else:
            label = "可按计划卖出"
            advice_detail = "风险可控，按原定计划执行即可"
    elif decision_type == "hold":
        label = "继续观望"
        advice_detail = "维持当前仓位，等待更明确的信号"
    else:
        if suggested_max <= 0:
            advice_detail = "当前风险过高，不建议建仓。请等待情绪平复、风险降低后再考虑"
        else:
            pct_text = f"{suggested_max * 100:.0f}%"
            advice_detail = f"建议本次建仓不超过总资产的{pct_text}。分批建仓优于一次性买入"

    return {
        "suggested_max_pct": round(suggested_max * 100, 1),
        "label": label,
        "advice": advice_detail,
        "emotion_adjustment": emotion_adj,
        "risk_score_used": risk_score,
        "sentiment_score_used": sentiment,
    }


# ============================================================
# 公开 API
# ============================================================

def analyze_decision(decision_type: str, target: str, reason: str,
                     trigger: str = "", position_pct: str = "",
                     time_horizon: str = "") -> dict:
    """
    完整的决策分析流程（Step 2 → Step 3）

    1. 快思维陷阱检测 (System 1)
    2. 逻辑谬误检测
    3. 因果链条分析
    4. 噪声检测
    5. 构建反向论证框架
    6. 前事分析
    7. 生成决策矩阵（基础分）
    8. 生成针对性质问
    """
    # 模块一：快思维检测
    system1_traps = _detect_system1_traps(reason, trigger)

    # 模块二：逻辑谬误检测
    logical_fallacies = _detect_logical_fallacies(reason, trigger)

    # 模块三：因果链条分析
    causal_chain = _check_causal_chain(reason)

    # 模块四：反向论证
    reverse_arg = _build_reverse_argument(decision_type, target, reason)

    # 模块五：噪声检测
    noise_check = _generate_noise_check(reason, decision_type)

    # 模块六：前事分析
    pre_mortem = _generate_pre_mortem(decision_type, target, reason)

    # 模块七：决策矩阵（基础分）
    matrix = _calculate_decision_matrix(
        reason, system1_traps, logical_fallacies, noise_check, causal_chain
    )

    # 模块八：情绪量化评分
    sentiment = _calculate_sentiment_score(
        reason, trigger, system1_traps, noise_check
    )

    # 模块九：多维风险评估
    risk = _assess_risk(
        decision_type, target, reason, position_pct, time_horizon,
        system1_traps, logical_fallacies
    )

    # 模块十：仓位建议
    position_rec = _calculate_position_recommendation(
        decision_type, risk, sentiment, position_pct
    )

    # 生成问题
    questions = generate_questions(
        system1_traps, logical_fallacies, noise_check,
        reverse_arg, pre_mortem, decision_type
    )

    # 创建决策记录
    decision_id = f"d_{int(time.time() * 1000)}"
    record = {
        "id": decision_id,
        "timestamp": datetime.now().isoformat(),
        "decision_type": decision_type,
        "target": target,
        "reason": reason,
        "trigger": trigger,
        "position_pct": position_pct,
        "time_horizon": time_horizon,
        "system1_traps": system1_traps,
        "logical_fallacies": logical_fallacies,
        "causal_chain": causal_chain,
        "noise_check": noise_check,
        "reverse_arg": reverse_arg,
        "pre_mortem": pre_mortem,
        "matrix": matrix,
        "sentiment": sentiment,
        "risk_assessment": risk,
        "position_recommendation": position_rec,
        "questions": questions,
        "diagnosis": None,
        "outcome": None,
    }

    log = _load_log()
    log.append(record)
    _save_log(log)

    return {
        "decision_id": decision_id,
        "system1_traps": system1_traps,
        "logical_fallacies": logical_fallacies,
        "causal_chain": causal_chain,
        "noise_check": noise_check,
        "reverse_arg": reverse_arg,
        "pre_mortem": pre_mortem,
        "matrix": matrix,
        "sentiment": sentiment,
        "risk_assessment": risk,
        "position_recommendation": position_rec,
        "questions": questions,
    }


def submit_diagnosis(decision_id: str, answers: list) -> dict:
    """
    提交回答，生成最终诊断（Step 4 → Step 5）
    """
    log = _load_log()

    record = None
    for r in log:
        if r["id"] == decision_id:
            record = r
            break

    if not record:
        return {"error": "未找到该决策记录"}

    # 更新回答
    for qa in record["questions"]:
        for ans in answers:
            if ans.get("id") == qa["id"]:
                qa["answer"] = ans.get("answer", "")

    # 评估回答质量，调整矩阵分数
    matrix = _evaluate_answers(record["questions"], record["matrix"])

    # 生成诊断总结
    diagnosis = _generate_summary(
        matrix,
        record.get("system1_traps", []),
        record.get("logical_fallacies", [])
    )

    # 添加详细维度信息
    diagnosis["dimensions"] = matrix["dimensions"]

    # 添加检出的风险
    warnings = []
    for trap in record.get("system1_traps", []):
        warnings.append({
            "icon": trap["icon"],
            "title": trap["name"],
            "detail": trap["desc"],
            "module": "快思维检测",
        })
    for fallacy in record.get("logical_fallacies", []):
        warnings.append({
            "icon": fallacy["icon"],
            "title": fallacy["name"],
            "detail": fallacy["desc"],
            "module": "逻辑验证",
        })
    for signal in record.get("noise_check", {}).get("signals", []):
        warnings.append({
            "icon": "📡",
            "title": signal["signal"],
            "detail": signal["detail"],
            "module": "噪声检测",
        })

    diagnosis["warnings"] = warnings

    record["diagnosis"] = diagnosis
    _save_log(log)

    return diagnosis


def get_history(limit: int = 50) -> list:
    """获取决策日志（按时间倒序）"""
    log = _load_log()
    log.reverse()
    return log[:limit]


def record_outcome(decision_id: str, outcome: str, profit_pct: float = None,
                   lesson: str = "") -> dict:
    """补填决策结果"""
    log = _load_log()

    for r in log:
        if r["id"] == decision_id:
            r["outcome"] = {
                "result": outcome,
                "profit_pct": profit_pct,
                "lesson": lesson,
                "recorded_at": datetime.now().isoformat(),
            }
            _save_log(log)
            return {"ok": True, "message": "结果已记录"}

    return {"error": "未找到该决策记录"}


# ============================================================
# 深度理性训练：前额叶激活、校准训练、个人基准率
# ============================================================

def get_prefrontal_warmup(decision_type: str = "", target: str = "",
                          thought: str = "") -> dict:
    """
    生成前额叶热身问题（5个维度）。
    目标：在做投资决策前，用3分钟激活前额叶皮层，
    抑制杏仁核（情绪中心）的过度活跃。
    """
    warmup = {
        "purpose": "前额叶皮层负责延迟满足、冲动控制、概率思维和抽象推理。"
                   "在做投资决策前，先做5个小练习，让理性大脑上线。",
        "exercises": [
            {
                "id": 1,
                "dimension": "perspective_shift",
                "name": "视角切换",
                "icon": "👤",
                "instruction": "你现在不是你自己，而是一个理性的投资顾问，"
                               "一个你最信任的朋友来问你："
                               f"我{'想买' if decision_type == 'buy' else '想卖' if decision_type == 'sell' else '在考虑'}{target}，你觉得怎么样？",
                "prompt": "作为这个投资顾问，你会给朋友什么建议？",
                "hint": "从我切换到顾问视角，能让你跳出情绪，用更理性的眼光看待同一个决策。",
            },
            {
                "id": 2,
                "dimension": "probability_calibration",
                "name": "概率校准",
                "icon": "🎲",
                "instruction": "不要说会涨或会跌，用概率来表达你的判断。",
                "prompt": f"如果{'买入' if decision_type == 'buy' else '卖出' if decision_type == 'sell' else '操作'}{target}，"
                          f"你认为{'盈利' if decision_type == 'buy' else '正确'}的概率是多少？"
                          f"请给出一个具体的百分比（比如65%）。",
                "hint": "理性的人不只是想得对，还知道自己有多确定。"
                        "说70%概率比说应该会涨更理性。",
            },
            {
                "id": 3,
                "dimension": "disconfirmation_search",
                "name": "证伪搜索",
                "icon": "🔍",
                "instruction": "你已经想好了要做什么。现在，花1分钟专门寻找反对你的证据。",
                "prompt": "找到一个支持相反观点的证据。"
                          f"如果{'不应该买' if decision_type == 'buy' else '不应该卖' if decision_type == 'sell' else '不应该操作'}，"
                          "最可能的原因是什么？",
                "hint": "核心思想：不要问我对不对，要问我可能在哪里错了。",
            },
            {
                "id": 4,
                "dimension": "temporal_distance",
                "name": "时间拉远",
                "icon": "⏰",
                "instruction": "从现在切换到未来。想象一年后的你回看今天这个决定。",
                "prompt": "一年后，当你回看今天这个决定，你觉得那时候的你会怎么评价现在的你？"
                          "会说做得好还是会说当时太冲动了？",
                "hint": "研究表明，想象未来的自己能显著降低冲动决策。"
                        "因为你在为未来的自己负责，而不只是现在的自己。",
            },
            {
                "id": 5,
                "dimension": "quantification_forcing",
                "name": "量化强迫",
                "icon": "📊",
                "instruction": "把你的模糊感觉变成具体的数字。模糊的判断容易被情绪污染，数字不会。",
                "prompt": "用一个具体的数字来表达你的判断。例如："
                          "我认为有70%的概率在半年内涨15%，或者我认为最大回撤不会超过10%。",
                "hint": "当你试图把感觉量化时，你会发现自己的判断其实没有那么确定。"
                        "这种不确定性暴露本身就是理性。",
            },
        ],
    }

    return warmup


# 校准训练题库
CALIBRATION_QUESTIONS = [
    {
        "id": "cal_pe_01",
        "category": "估值判断",
        "question": "沪深300指数当前PE约为12倍。你认为3年后PE会是多少？",
        "reference_answer": 13,
        "tolerance": 0.3,
        "unit": "倍",
        "explanation": "沪深300历史PE中枢约12-14倍，极端情况可达8-18倍。",
    },
    {
        "id": "cal_pe_02",
        "category": "估值判断",
        "question": "贵州茅台当前PE约为25倍。你认为1年后PE会是多少？",
        "reference_answer": 24,
        "tolerance": 0.25,
        "unit": "倍",
        "explanation": "茅台PE波动较大，近5年在20-45倍之间。",
    },
    {
        "id": "cal_div_01",
        "category": "收益率",
        "question": "中国10年期国债收益率当前约为1.7%。你认为1年后会是多少？",
        "reference_answer": 1.8,
        "tolerance": 0.3,
        "unit": "%",
        "explanation": "国债收益率受央行政策和经济周期影响较大。",
    },
    {
        "id": "cal_return_01",
        "category": "收益预期",
        "question": "如果你现在买入沪深300ETF并持有3年，你预期的年化收益率是多少？",
        "reference_answer": 8,
        "tolerance": 0.5,
        "unit": "%",
        "explanation": "沪深300长期年化收益约8-10%，但波动很大。",
    },
    {
        "id": "cal_drawdown_01",
        "category": "风险评估",
        "question": "A股市场历史上，从高点到低点的最大回撤通常在多少？",
        "reference_answer": 45,
        "tolerance": 0.3,
        "unit": "%",
        "explanation": "A股历史上最大回撤可达50-70%（如2008年、2015年）。",
    },
    {
        "id": "cal_prob_01",
        "category": "概率判断",
        "question": "一只股票今天涨停（+10%），你认为明天继续涨停的概率是多少？",
        "reference_answer": 8,
        "tolerance": 0.5,
        "unit": "%",
        "explanation": "涨停后次日继续涨停的概率约5-10%，远低于人们的直觉。",
    },
    {
        "id": "cal_prob_02",
        "category": "概率判断",
        "question": "一只股票连续3天上涨，你认为第4天继续上涨的概率是多少？",
        "reference_answer": 48,
        "tolerance": 0.2,
        "unit": "%",
        "explanation": "短期走势接近随机游走，连续3天上涨后第4天上涨概率约48%。",
    },
    {
        "id": "cal_base_01",
        "category": "基准率",
        "question": "A股上市公司中，连续5年ROE大于15%的公司占比大约是多少？",
        "reference_answer": 8,
        "tolerance": 0.5,
        "unit": "%",
        "explanation": "真正优质的公司是少数，连续5年高ROE的公司约5-10%。",
    },
    {
        "id": "cal_base_02",
        "category": "基准率",
        "question": "主动管理型股票基金中，跑赢沪深300指数的比例大约是多少？",
        "reference_answer": 30,
        "tolerance": 0.3,
        "unit": "%",
        "explanation": "长期来看，约70%的主动基金跑输指数。",
    },
    {
        "id": "cal_inflation_01",
        "category": "宏观判断",
        "question": "你认为未来5年中国的平均年通胀率会是多少？",
        "reference_answer": 2.5,
        "tolerance": 0.4,
        "unit": "%",
        "explanation": "中国近年CPI约2-3%，但实际通胀感受可能更高。",
    },
]

CALIBRATION_LOG_FILE = os.path.join(LOG_DIR, "calibration_log.json")


def _load_calibration_log() -> list:
    if os.path.exists(CALIBRATION_LOG_FILE):
        try:
            with open(CALIBRATION_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_calibration_log(records: list):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(CALIBRATION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def get_calibration_question(index: int = None) -> dict:
    """获取一道校准训练题"""
    import random
    if index is not None and 0 <= index < len(CALIBRATION_QUESTIONS):
        q = CALIBRATION_QUESTIONS[index]
    else:
        q = random.choice(CALIBRATION_QUESTIONS)

    return {
        "id": q["id"],
        "category": q["category"],
        "question": q["question"],
        "unit": q["unit"],
        "total_questions": len(CALIBRATION_QUESTIONS),
    }


def submit_calibration_answer(question_id: str, user_answer: float,
                               confidence: int) -> dict:
    """
    提交校准训练答案，评估准确性。
    """
    question = None
    for q in CALIBRATION_QUESTIONS:
        if q["id"] == question_id:
            question = q
            break

    if not question:
        return {"error": "未找到该题目"}

    ref = question["reference_answer"]
    tolerance = question["tolerance"]

    if ref != 0:
        error_pct = abs(user_answer - ref) / abs(ref)
    else:
        error_pct = abs(user_answer)

    if error_pct <= tolerance * 0.5:
        accuracy = "excellent"
        accuracy_text = "非常准确"
        accuracy_score = 100
    elif error_pct <= tolerance:
        accuracy = "good"
        accuracy_text = "在合理范围内"
        accuracy_score = 80
    elif error_pct <= tolerance * 2:
        accuracy = "fair"
        accuracy_text = "有一定偏差"
        accuracy_score = 50
    else:
        accuracy = "poor"
        accuracy_text = "偏差较大"
        accuracy_score = 20

    cal_log = _load_calibration_log()
    cal_log.append({
        "question_id": question_id,
        "user_answer": user_answer,
        "reference_answer": ref,
        "confidence": confidence,
        "accuracy": accuracy,
        "accuracy_score": accuracy_score,
        "error_pct": round(error_pct * 100, 1),
        "timestamp": datetime.now().isoformat(),
    })
    _save_calibration_log(cal_log)

    return {
        "accuracy": accuracy,
        "accuracy_text": accuracy_text,
        "accuracy_score": accuracy_score,
        "user_answer": user_answer,
        "reference_answer": ref,
        "unit": question["unit"],
        "error_pct": round(error_pct * 100, 1),
        "confidence": confidence,
        "explanation": question["explanation"],
    }


def get_calibration_stats() -> dict:
    """
    计算校准训练统计。
    核心指标：用户的置信度是否与实际准确率匹配。
    """
    cal_log = _load_calibration_log()

    if len(cal_log) < 3:
        return {
            "status": "insufficient_data",
            "message": f"需要至少3次训练数据才能计算校准曲线。当前：{len(cal_log)}次",
            "total_sessions": len(cal_log),
            "calibration_curve": [],
            "overall_accuracy": 0,
            "overconfidence_score": 0,
        }

    by_confidence = {}
    for record in cal_log:
        conf = record.get("confidence", 70)
        if conf not in by_confidence:
            by_confidence[conf] = {"correct": 0, "total": 0}
        by_confidence[conf]["total"] += 1
        if record.get("accuracy") in ("excellent", "good"):
            by_confidence[conf]["correct"] += 1

    calibration_curve = []
    for conf in sorted(by_confidence.keys()):
        stats = by_confidence[conf]
        actual_accuracy = round(stats["correct"] / stats["total"] * 100, 1)
        calibration_curve.append({
            "confidence": conf,
            "actual_accuracy": actual_accuracy,
            "sample_size": stats["total"],
            "gap": conf - actual_accuracy,
        })

    total = len(cal_log)
    correct = sum(1 for r in cal_log if r.get("accuracy") in ("excellent", "good"))
    overall_accuracy = round(correct / total * 100, 1)

    avg_confidence = sum(r.get("confidence", 70) for r in cal_log) / total
    overconfidence_score = round(avg_confidence - overall_accuracy, 1)

    if overconfidence_score > 20:
        cal_message = "你严重过度自信。你的实际准确率远低于你的置信度。建议：降低置信度，增加不确定性。"
    elif overconfidence_score > 10:
        cal_message = "你有一定程度的过度自信。建议：在给出高置信度时更加谨慎。"
    elif overconfidence_score > -5:
        cal_message = "你的校准较好。你的置信度和实际准确率基本匹配。"
    else:
        cal_message = "你可能过于保守。你的实际表现比你认为的要好。"

    return {
        "status": "ok",
        "total_sessions": total,
        "overall_accuracy": overall_accuracy,
        "avg_confidence": round(avg_confidence, 1),
        "overconfidence_score": overconfidence_score,
        "cal_message": cal_message,
        "calibration_curve": calibration_curve,
    }


def get_base_rates() -> dict:
    """
    从历史决策记录中计算个人基准率（机构级增强版）。
    包含：胜率、盈亏比、Sharpe比率、Kelly公式、最大回撤、偏误-结果关联。
    """
    import statistics
    log = _load_log()

    if len(log) < 3:
        return {
            "status": "insufficient_data",
            "message": f"需要至少3次决策记录才能计算基准率。当前：{len(log)}次",
            "total_decisions": len(log),
        }

    total = len(log)
    with_outcome = [r for r in log if r.get("outcome")]
    with_diagnosis = [r for r in log if r.get("diagnosis")]

    wins = sum(1 for r in with_outcome if r["outcome"].get("result") == "profit")
    losses = sum(1 for r in with_outcome if r["outcome"].get("result") == "loss")
    breakeven = sum(1 for r in with_outcome if r["outcome"].get("result") == "breakeven")
    outcome_total = len(with_outcome)

    win_rate = round(wins / outcome_total * 100, 1) if outcome_total > 0 else 0

    profits = [r["outcome"]["profit_pct"] for r in with_outcome
               if r["outcome"].get("profit_pct") is not None and r["outcome"]["profit_pct"] > 0]
    loss_pcts = [abs(r["outcome"]["profit_pct"]) for r in with_outcome
                 if r["outcome"].get("profit_pct") is not None and r["outcome"]["profit_pct"] < 0]

    avg_profit = round(sum(profits) / len(profits), 2) if profits else 0
    avg_loss = round(sum(loss_pcts) / len(loss_pcts), 2) if loss_pcts else 0
    profit_loss_ratio = round(avg_profit / avg_loss, 2) if avg_loss > 0 else 0

    # === Sharpe比率（简化版，假设无风险利率=2%） ===
    all_returns = [r["outcome"]["profit_pct"] for r in with_outcome
                   if r["outcome"].get("profit_pct") is not None]
    sharpe_ratio = 0
    if len(all_returns) >= 3:
        mean_ret = statistics.mean(all_returns)
        std_ret = statistics.stdev(all_returns) if len(all_returns) > 1 else 1
        risk_free = 2.0  # 年化无风险利率简化
        sharpe_ratio = round((mean_ret - risk_free) / std_ret, 2) if std_ret > 0 else 0

    # === 最大回撤（基于决策序列） ===
    cumulative = 0
    peak = 0
    max_drawdown = 0
    for r in with_outcome:
        pct = r["outcome"].get("profit_pct")
        if pct is not None:
            cumulative += pct
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)
    max_drawdown = round(max_drawdown, 2)

    # === Kelly公式（最优仓位比例） ===
    kelly_fraction = 0
    half_kelly = 0
    if outcome_total >= 5 and avg_loss > 0:
        win_prob = wins / outcome_total
        loss_prob = losses / outcome_total
        b = avg_profit / avg_loss  # 赔率
        kelly_fraction = round((win_prob * b - loss_prob) / b * 100, 1) if b > 0 else 0
        half_kelly = round(kelly_fraction / 2, 1)

    # === 期望值（每笔交易的预期收益） ===
    expected_value = 0
    if outcome_total > 0:
        expected_value = round(
            (win_rate / 100) * avg_profit - (1 - win_rate / 100) * avg_loss, 2
        )

    # === 按决策类型统计 ===
    by_type = {}
    for r in log:
        dt = r.get("decision_type", "unknown")
        if dt not in by_type:
            by_type[dt] = {"total": 0, "wins": 0, "losses": 0, "returns": []}
        by_type[dt]["total"] += 1
        if r.get("outcome"):
            if r["outcome"].get("result") == "profit":
                by_type[dt]["wins"] += 1
            elif r["outcome"].get("result") == "loss":
                by_type[dt]["losses"] += 1
            pct = r["outcome"].get("profit_pct")
            if pct is not None:
                by_type[dt]["returns"].append(pct)

    type_stats = {}
    for dt, stats in by_type.items():
        wr = round(stats["wins"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
        avg_ret = round(statistics.mean(stats["returns"]), 2) if stats.get("returns") else 0
        type_stats[dt] = {
            "total": stats["total"],
            "win_rate": wr,
            "avg_return": avg_ret,
        }

    # === 偏误-结果关联分析 ===
    bias_counts = {}
    bias_with_outcome = {}
    for r in log:
        for trap in r.get("system1_traps", []):
            bt = trap.get("type", "unknown")
            bias_counts[bt] = bias_counts.get(bt, 0) + 1
            if r.get("outcome"):
                if bt not in bias_with_outcome:
                    bias_with_outcome[bt] = {"wins": 0, "losses": 0}
                if r["outcome"].get("result") == "profit":
                    bias_with_outcome[bt]["wins"] += 1
                elif r["outcome"].get("result") == "loss":
                    bias_with_outcome[bt]["losses"] += 1

    top_biases = sorted(bias_counts.items(), key=lambda x: -x[1])[:5]
    bias_impact = []
    for b_type, count in top_biases:
        bo = bias_with_outcome.get(b_type, {"wins": 0, "losses": 0})
        total_bo = bo["wins"] + bo["losses"]
        loss_rate = round(bo["losses"] / total_bo * 100, 1) if total_bo > 0 else 0
        bias_impact.append({
            "type": b_type,
            "count": count,
            "loss_rate_when_present": loss_rate,
            "sample_size": total_bo,
        })

    # === 月度趋势 ===
    monthly_scores = {}
    for r in with_diagnosis:
        ts = r.get("timestamp", "")
        month = ts[:7]
        score = r["diagnosis"].get("score", 0)
        if month not in monthly_scores:
            monthly_scores[month] = []
        monthly_scores[month].append(score)

    trend = []
    for month in sorted(monthly_scores.keys()):
        scores = monthly_scores[month]
        trend.append({
            "month": month,
            "avg_score": round(sum(scores) / len(scores), 1),
            "count": len(scores),
        })

    # === 校准数据整合 ===
    cal_stats = get_calibration_stats()
    overconfidence_score = cal_stats.get("overconfidence_score", 0) if cal_stats.get("status") == "ok" else None

    return {
        "status": "ok",
        "total_decisions": total,
        "with_outcome": outcome_total,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "avg_profit": avg_profit,
        "avg_loss": avg_loss,
        "profit_loss_ratio": profit_loss_ratio,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "kelly_criterion": {
            "full_kelly": kelly_fraction,
            "half_kelly": half_kelly,
            "description": "Kelly公式建议的最优仓位比例（半Kelly更保守，推荐使用）",
        },
        "expected_value": expected_value,
        "by_type": type_stats,
        "top_biases": [{"type": b[0], "count": b[1]} for b in top_biases],
        "bias_impact": bias_impact,
        "trend": trend,
        "overconfidence_score": overconfidence_score,
    }


def get_decision_stats() -> dict:
    """
    获取决策系统综合统计（仪表盘用）。
    包含：总览、近期表现、风险趋势、校准状态。
    """
    base_rates = get_base_rates()
    cal_stats = get_calibration_stats()
    log = _load_log()

    # 近30天的决策
    from datetime import timedelta
    now = datetime.now()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    recent = [r for r in log if r.get("timestamp", "") >= thirty_days_ago]

    recent_with_outcome = [r for r in recent if r.get("outcome")]
    recent_wins = sum(1 for r in recent_with_outcome
                      if r["outcome"].get("result") == "profit")
    recent_total = len(recent_with_outcome)

    # 最常见的风险因素
    recent_biases = {}
    for r in recent:
        for trap in r.get("system1_traps", []):
            bt = trap.get("type", "unknown")
            recent_biases[bt] = recent_biases.get(bt, 0) + 1

    # 决策质量趋势（最近10次）
    recent_diagnoses = [r for r in log if r.get("diagnosis")][-10:]
    quality_trend = [{
        "target": r.get("target", "?"),
        "score": r["diagnosis"].get("score", 0),
        "type": r.get("decision_type", "?"),
    } for r in recent_diagnoses]

    return {
        "overview": {
            "total_decisions": base_rates.get("total_decisions", 0),
            "win_rate": base_rates.get("win_rate", 0),
            "profit_loss_ratio": base_rates.get("profit_loss_ratio", 0),
            "sharpe_ratio": base_rates.get("sharpe_ratio", 0),
            "expected_value": base_rates.get("expected_value", 0),
        },
        "recent_30d": {
            "decisions": len(recent),
            "with_outcome": recent_total,
            "wins": recent_wins,
            "win_rate": round(recent_wins / recent_total * 100, 1) if recent_total > 0 else 0,
            "top_biases": sorted(recent_biases.items(), key=lambda x: -x[1])[:3],
        },
        "quality_trend": quality_trend,
        "calibration": cal_stats,
        "base_rates": base_rates,
    }
