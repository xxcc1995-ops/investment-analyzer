"""价值投资筛选 - 巴菲特、芒格、李录、段永平投资体系"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from app.services.vi_service import screen_stocks
from app.services.dcf import DCFService, calculate_graham_number, estimate_wacc
from app.services.data_service import DataService

router = APIRouter()


# ============================================================
# Request Models
# ============================================================

class DCFRequest(BaseModel):
    current_fcf: float = Field(..., description="当前自由现金流（亿元）")
    growth_rate: float = Field(..., description="增长率（小数，如0.10表示10%）")
    shares: float = Field(..., description="总股本（亿股）")
    discount_rate: float = Field(0.10, description="折现率/WACC（小数）")
    terminal_growth_rate: float = Field(0.03, description="永续增长率（小数）")
    safety_margin: float = Field(0.30, description="安全边际（小数）")
    net_debt: float = Field(0.0, description="净负债（亿元）")
    current_price: float = Field(0.0, description="当前市场价格（元）")


class TwoStageDCFRequest(BaseModel):
    current_fcf: float = Field(..., description="当前自由现金流（亿元）")
    high_growth_rate: float = Field(..., description="高增长阶段增长率（小数）")
    stable_growth_rate: float = Field(0.05, description="稳定增长阶段增长率（小数）")
    shares: float = Field(..., description="总股本（亿股）")
    high_growth_years: int = Field(5, description="高增长阶段年数")
    discount_rate: float = Field(0.10, description="折现率/WACC（小数）")
    terminal_growth_rate: float = Field(0.03, description="永续增长率（小数）")
    safety_margin: float = Field(0.30, description="安全边际（小数）")
    net_debt: float = Field(0.0, description="净负债（亿元）")
    current_price: float = Field(0.0, description="当前市场价格（元）")


class AutoDCFRequest(BaseModel):
    stock_code: str = Field(..., description="股票代码（如 600519、00700、AAPL）")
    market: str = Field("a", description="市场: a/hk/us")
    growth_rate: Optional[float] = Field(None, description="增长率（小数），不填则自动估算")
    discount_rate: Optional[float] = Field(None, description="折现率，不填则自动估算WACC")
    safety_margin: float = Field(0.30, description="安全边际")


class GrahamRequest(BaseModel):
    eps: float = Field(..., description="每股收益（EPS）")
    bvps: float = Field(..., description="每股净资产（BVPS）")
    current_price: float = Field(0.0, description="当前市场价格")


# ============================================================
# 投资理念
# ============================================================

@router.get("/philosophy")
def get_philosophy():
    """获取四位大师的完整投资哲学体系"""
    return {
        'buffett': {
            'name': '沃伦·巴菲特 (Warren Buffett)',
            'title': '伯克希尔·哈撒韦 CEO | 奥马哈的先知',
            'era': '1956年至今 | 年化回报约20%',
            'core_philosophy': '买股票就是买企业的一部分。以合理价格买入具有持久竞争优势的优秀企业，然后长期持有。',
            'investment_framework': [
                {
                    'dimension': '经济护城河',
                    'description': '企业必须拥有持久的竞争优势，使竞争对手无法轻易侵蚀其利润',
                    'criteria': [
                        '品牌护城河：消费者愿意为品牌支付溢价（可口可乐、苹果）',
                        '成本护城河：低成本结构使竞争对手无法匹配（GEICO、好市多）',
                        '转换成本：客户更换产品/服务的成本很高（微软Office、银行系统）',
                        '网络效应：用户越多，产品价值越大（微信、Visa）',
                        '规模经济：规模越大，单位成本越低（沃尔玛、台积电）',
                    ],
                    'key_insight': '护城河比增长更重要。没有护城河的增长只是在为竞争对手创造价值。',
                },
                {
                    'dimension': '管理层品质',
                    'description': '管理层必须诚实、能干，且以股东利益为导向',
                    'criteria': [
                        '理性配置资本：在股价低估时回购，在高估时发行',
                        '坦诚沟通：承认错误，不粉饰业绩',
                        '拒绝跟风：不盲目追求行业趋势或竞争对手的策略',
                        '长期思维：愿意牺牲短期利润换取长期竞争优势',
                    ],
                    'key_insight': '我宁要一个由一流管理层经营的二流企业，也不要一个由二流管理层经营的一流企业。',
                },
                {
                    'dimension': '财务指标',
                    'description': '用数字验证企业的护城河和管理层效率',
                    'criteria': [
                        'ROE持续 > 15%（优秀企业 > 20%）',
                        '毛利率 > 40%（体现定价权和品牌力）',
                        '净利率 > 15%（体现成本控制和定价能力）',
                        '负债率 < 50%（保守的财务结构）',
                        '自由现金流稳定增长',
                    ],
                    'key_insight': '如果只能用一个指标来选股，那就是ROE。ROE衡量的是管理层运用股东资本的效率。',
                },
                {
                    'dimension': '安全边际',
                    'description': '以显著低于内在价值的价格买入，为判断错误留出缓冲',
                    'criteria': [
                        '内在价值 = 未来自由现金流的折现值',
                        '安全边际通常要求50%以上',
                        '越是确定性高的企业，安全边际可以适当降低',
                        '市场恐慌时是买入好企业的最佳时机',
                    ],
                    'key_insight': '用合理的价格买入优秀企业，远胜于用便宜的价格买入平庸企业。',
                },
            ],
            'classic_quotes': [
                '别人恐惧时我贪婪，别人贪婪时我恐惧。',
                '如果你不愿意持有一只股票十年，那就不要持有它十分钟。',
                '价格是你付出的，价值是你得到的。',
                '时间是优秀企业的朋友，是平庸企业的敌人。',
            ],
            'key_cases': '可口可乐、苹果、美国运通、比亚迪、中国石油',
        },
        'munger': {
            'name': '查理·芒格 (Charlie Munger)',
            'title': '伯克希尔·哈撒韦 副主席 | 巴菲特的黄金搭档',
            'era': '1959年至今 | 年化回报约20%',
            'core_philosophy': '多元思维模型 + 逆向思考。与其追求聪明，不如避免做蠢事。',
            'investment_framework': [
                {
                    'dimension': '多元思维模型',
                    'description': '用多学科视角分析企业，避免"锤子综合症"——手里只有锤子，看什么都像钉子',
                    'criteria': [
                        '数学：复利效应、概率思维、排列组合',
                        '心理学：识别25种人类误判心理倾向',
                        '经济学：规模优势、边际效用、竞争优势',
                        '生物学：进化论、适者生存、生态位',
                        '物理学：临界质量、惯性、反馈循环',
                    ],
                    'key_insight': '你必须知道重要学科的重要理论，并且经常使用它们——全部都用上，而不是只用几个。',
                },
                {
                    'dimension': '逆向思维',
                    'description': '"反过来想，总是反过来想"——先考虑如何失败，再考虑如何成功',
                    'criteria': [
                        '这家企业可能因为什么原因失败？',
                        '管理层可能犯什么愚蠢的错误？',
                        '行业可能被什么颠覆？',
                        '我可能在哪些方面自欺欺人？',
                    ],
                    'key_insight': '如果我知道我会死在哪里，我就永远不会去那个地方。',
                },
                {
                    'dimension': '检查清单法',
                    'description': '系统性检查所有可能的风险因素，避免遗漏',
                    'criteria': [
                        '能力圈：我真的理解这个企业吗？',
                        '护城河：竞争优势能持续多久？',
                        '管理层：是否诚实、理性、能干？',
                        '估值：价格是否合理？安全边际够吗？',
                        '风险：最坏情况是什么？我能承受吗？',
                        '心理偏误：我是否被情绪或偏见影响？',
                    ],
                    'key_insight': '聪明人怎样才会破产？酒精、女人、杠杆。',
                },
                {
                    'dimension': '质量优于价格',
                    'description': '芒格改变了巴菲特，从"以便宜价格买入平庸企业"转向"以合理价格买入优秀企业"',
                    'criteria': [
                        '好企业的长期回报远超便宜的烂企业',
                        '为优秀企业支付合理溢价是值得的',
                        '但再好的企业也有价格上限',
                        '宁可错过，也不要买错',
                    ],
                    'key_insight': '以公平的价格买入一家优秀的公司，远好于以极好的价格买入一家平庸的公司。',
                },
            ],
            'classic_quotes': [
                '如果我知道我会死在哪里，我就永远不会去那个地方。',
                '得到你想要的东西最好的方式就是让你自己配得上它。',
                '你不必非常出色，只需要在很长很长的时间内保持比其他人聪明一点点。',
                '大多数人都太急躁，太焦虑。伟大的投资需要很长时间。',
            ],
            'key_cases': '每日期刊、好市多、比亚迪、喜诗糖果',
        },
        'li_lu': {
            'name': '李录 (Li Lu)',
            'title': '喜马拉雅资本创始人 | 中国价值投资先驱',
            'era': '1997年至今 | 喜马拉雅资本年化约30%',
            'core_philosophy': '在中国市场实践价值投资，寻找具有知识优势的企业，以5-10年为投资周期。',
            'investment_framework': [
                {
                    'dimension': '知识优势',
                    'description': '只投资自己真正理解的企业，比市场有更深的认知',
                    'criteria': [
                        '深入理解行业的商业模式和竞争格局',
                        '了解企业在行业中的真实地位',
                        '判断管理层的能力和品格',
                        '识别市场尚未充分反映的价值',
                    ],
                    'key_insight': '投资的本质是对未来做出有依据的预测。你需要比市场更了解一家企业。',
                },
                {
                    'dimension': '中国市场的特殊性',
                    'description': '中国有独特的制度红利、人口红利和消费升级机会',
                    'criteria': [
                        '制度红利：改革开放带来的市场化机会',
                        '人口红利：14亿人口的消费市场',
                        '城镇化：城镇化率从30%到65%的巨大空间',
                        '工程师红利：大量高素质劳动力',
                        '后发优势：可以借鉴发达国家的经验',
                    ],
                    'key_insight': '中国是价值投资的沃土。市场波动大，但优秀企业的增长也大。',
                },
                {
                    'dimension': '行业选择',
                    'description': '选择结构性增长行业，而非周期性行业',
                    'criteria': [
                        '消费行业：品牌力强、复购率高',
                        '金融行业：受益于经济增长和金融深化',
                        '科技行业：具有技术壁垒和规模效应',
                        '新能源：长期结构性增长机会',
                        '避免：强周期行业、政策依赖行业',
                    ],
                    'key_insight': '选择比努力重要。在正确的行业里，优秀的管理层能创造更大的价值。',
                },
                {
                    'dimension': '长期持有',
                    'description': '以5-10年为投资周期，不被短期波动干扰',
                    'criteria': [
                        '短期市场是投票机，长期市场是称重机',
                        '频繁交易是价值投资的大敌',
                        '复利效应需要时间才能显现',
                        '好企业的价值会随着时间增长',
                    ],
                    'key_insight': '我投资比亚迪超过10年，经历了无数次波动，但企业的价值在持续增长。',
                },
            ],
            'classic_quotes': [
                '投资的本质是对未来做出有依据的预测。',
                '在中国做价值投资，需要更多的耐心和更深的理解。',
                '好企业+好价格+好管理层=好的投资。',
                '我投资比亚迪是因为我看到了新能源汽车的未来。',
            ],
            'key_cases': '比亚迪、邮储银行、中国平安、贵州茅台',
        },
        'duan_yongping': {
            'name': '段永平',
            'title': '步步高/OPPO/vivo创始人 | 中国最成功的价值投资者之一',
            'era': '2001年至今 | 投资网易获利百倍以上',
            'core_philosophy': '"买股票就是买公司，买公司就是买未来现金流的折现。"商业模式第一，好生意>好管理>好价格。',
            'investment_framework': [
                {
                    'dimension': '商业模式优先',
                    'description': '好商业模式 > 好管理 > 好价格。这是段永平投资的优先级排序。',
                    'criteria': [
                        '差异化：产品有真实的差异化，不是同质化竞争',
                        '消费者粘性：用户不愿轻易更换品牌或产品',
                        '定价权：能够在不损失客户的情况下提价',
                        '轻资产：不需要大量资本投入就能维持增长',
                        '简单易懂：业务模式清晰，不需要复杂解释',
                    ],
                    'key_insight': '好生意就是有差异化、有护城河、能持续赚钱的生意。',
                },
                {
                    'dimension': '"本分"文化',
                    'description': '做正确的事，不走捷径。管理层要诚信、务实。',
                    'criteria': [
                        '不为了短期利益牺牲长期价值',
                        '不抄袭竞争对手，坚持自己的路线',
                        '对消费者负责，提供真正有价值的产品',
                        '对股东坦诚，不粉饰业绩',
                    ],
                    'key_insight': '"本分"就是做对的事情，把事情做对。',
                },
                {
                    'dimension': '消费者导向',
                    'description': '以消费者需求为中心，而非以竞争对手为中心',
                    'criteria': [
                        '产品是否有真实的用户需求？',
                        '用户是否愿意持续付费？',
                        '用户口碑如何？复购率如何？',
                        '是否在不断改善用户体验？',
                    ],
                    'key_insight': '消费者不傻。长期来看，好的产品一定会胜出。',
                },
                {
                    'dimension': '三条铁律',
                    'description': '不做空、不借钱炒股、不懂不做',
                    'criteria': [
                        '不做空：做空的收益有限，风险无限',
                        '不借钱炒股：杠杆会让人失去理性',
                        '不懂不做：只投资自己真正理解的企业',
                    ],
                    'key_insight': '这三条铁律帮我避免了90%的投资错误。',
                },
                {
                    'dimension': '集中投资',
                    'description': '重仓少数几家真正理解的好公司',
                    'criteria': [
                        '真正好的投资机会非常少',
                        '当机会出现时，要敢于重仓',
                        '分散投资是无知的表现',
                        '但前提是你真的理解这家企业',
                    ],
                    'key_insight': '我一辈子真正重仓的投资不超过10个。',
                },
            ],
            'classic_quotes': [
                '买股票就是买公司，买公司就是买未来现金流的折现。',
                '做对的事情，把事情做对。',
                '消费者不傻。长期来看，好的产品一定会胜出。',
                '投资最重要的是不亏钱，其次才是赚钱。',
            ],
            'key_cases': '网易(2002年<1美元买入)、苹果、茅台、腾讯、拼多多',
        },
        'scoring_system': {
            'name': '四位大师独立评分体系',
            'description': '每位大师有独立的评分逻辑，反映其独特的投资哲学。综合评分为四者平均。',
            'masters': [
                {'name': '巴菲特', 'focus': '护城河 + ROE + 安全边际', 'weight': 'ROE(25) + 护城河(20+15) + 估值(20) + 负债(10) + 成长(10)'},
                {'name': '芒格', 'focus': '企业质量 + 管理层理性 + 风险排除', 'weight': '质量(25) + 管理(20) + 风险排除(20) + 估值(15) + 盈利(10) + 成长(10)'},
                {'name': '李录', 'focus': 'ROE + 护城河 + 结构性增长', 'weight': 'ROE(25) + 护城河(20) + 成长(20) + 估值(15) + 负债(10) + 股息(10)'},
                {'name': '段永平', 'focus': '商业模式 + 成长性 + 财务健康', 'weight': '商业模式(30) + 成长(25) + 负债(15) + 估值(15) + 股息(10) + 安全(5)'},
            ],
            'match_levels': {
                'excellent': '80+ - 四位大师都会认可的优秀企业',
                'good': '65-79 - 多数大师会关注的优质标的',
                'fair': '50-64 - 部分维度突出，有待观察',
                'poor': '<50 - 不符合价值投资标准',
            }
        },
        'risks': [
            '价值陷阱：低PE/PB可能反映基本面恶化，而非低估',
            '护城河侵蚀：技术变革可能摧毁看似牢固的护城河',
            '管理层风险：管理层变动可能改变企业前景',
            '估值锚定：过度依赖历史估值可能错过结构性变化',
            '集中度风险：大师们推崇集中投资，但普通人需要更多分散',
            '幸存者偏差：我们只看到了成功的案例，忽略了失败的投资',
            '市场环境变化：过去有效的策略不一定在未来有效',
            '中国市场特殊性：政策风险、公司治理、信息不对称',
        ]
    }


# ============================================================
# 筛选器
# ============================================================

@router.get("/screener")
def value_investing_screener(
    market: str = Query("all", description="市场: all/a/hk/us"),
    master: str = Query("combined", description="大师: combined/buffett/munger/li_lu/duan_yongping"),
    min_score: int = Query(50, description="最低评分"),
    max_pe: float = Query(30, description="最大PE"),
    max_pb: float = Query(5, description="最大PB"),
    top_n: int = Query(50, description="显示数量"),
):
    """价值投资股票筛选"""
    if market not in ("all", "a", "hk", "us"):
        raise HTTPException(400, "market参数无效")
    if master not in ("combined", "buffett", "munger", "li_lu", "duan_yongping"):
        raise HTTPException(400, "master参数无效")

    try:
        result = screen_stocks(
            market=market, master=master,
            min_score=min_score, max_pe=max_pe, max_pb=max_pb, top_n=top_n,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"筛选失败: {str(e)}")


# ============================================================
# DCF 估值
# ============================================================

@router.post("/dcf")
def dcf_calculator(req: DCFRequest):
    """DCF自由现金流折现计算器（单阶段）"""
    if req.current_fcf <= 0 or req.shares <= 0:
        raise HTTPException(400, "FCF和股本必须大于0")

    try:
        dcf = DCFService(
            discount_rate=req.discount_rate,
            terminal_growth_rate=req.terminal_growth_rate,
            safety_margin=req.safety_margin,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    result = dcf.calculate_intrinsic_value(
        current_fcf=req.current_fcf,
        growth_rate=req.growth_rate,
        shares=req.shares,
        net_debt=req.net_debt,
        current_price=req.current_price,
    )

    # 敏感性分析
    result['sensitivity'] = _build_sensitivity_matrix(req)

    return result


@router.post("/dcf-two-stage")
def dcf_two_stage_calculator(req: TwoStageDCFRequest):
    """两阶段DCF模型（高增长 + 稳定增长）"""
    if req.current_fcf <= 0 or req.shares <= 0:
        raise HTTPException(400, "FCF和股本必须大于0")

    try:
        dcf = DCFService(
            discount_rate=req.discount_rate,
            terminal_growth_rate=req.terminal_growth_rate,
            safety_margin=req.safety_margin,
            projection_years=req.high_growth_years + 5,  # 高增长 + 5年稳定
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    result = dcf.calculate_two_stage_dcf(
        current_fcf=req.current_fcf,
        high_growth_rate=req.high_growth_rate,
        stable_growth_rate=req.stable_growth_rate,
        shares=req.shares,
        high_growth_years=req.high_growth_years,
        net_debt=req.net_debt,
        current_price=req.current_price,
    )

    return result


@router.post("/dcf-auto")
def dcf_auto_fetch(req: AutoDCFRequest):
    """
    自动获取股票数据并计算DCF估值

    自动获取: FCF（从现金流表）、增长率（历史CAGR）、股本、净负债、WACC
    """
    code = req.stock_code.strip()
    market = req.market.lower()
    if market not in ("a", "hk", "us"):
        raise HTTPException(400, "market必须为 a/hk/us")

    try:
        # 获取财务数据
        financials = DataService.get_financial_indicators(code)
        reports = financials.get("reports", [])
        if not reports:
            raise HTTPException(404, f"未找到 {code} 的财务数据")

        annual_reports = [r for r in reports if r.get("report_type") == "annual"]
        if not annual_reports:
            annual_reports = reports[:3]

        # 获取现金流数据
        cashflow_data = DataService.get_financial_statements(code)
        cf_list = cashflow_data.get("cashflow", [])

        # 估算FCF = 经营现金流 - 资本开支
        fcf_estimates = []
        for cf in cf_list[:5]:
            ocf = cf.get("netcash_operate")
            invest = cf.get("netcash_invest")
            if ocf is not None:
                # 简化: FCF = 经营现金流 + 投资现金流（投资通常为负）
                fcf = ocf + (invest if invest and invest < 0 else 0)
                if fcf > 0:
                    fcf_estimates.append(fcf)

        if not fcf_estimates:
            # fallback: 用净利润的80%估算FCF
            latest_profit = annual_reports[0].get("parent_net_profit")
            if latest_profit and latest_profit > 0:
                current_fcf = latest_profit * 0.8
            else:
                raise HTTPException(400, f"无法估算 {code} 的自由现金流，请手动输入")
        else:
            current_fcf = fcf_estimates[0]

        # 估算增长率
        if req.growth_rate is not None:
            growth_rate = req.growth_rate
        elif len(fcf_estimates) >= 2:
            dcf_svc = DCFService(discount_rate=0.10, terminal_growth_rate=0.03, safety_margin=0.30)
            growth_rate = dcf_svc.estimate_growth_rate(fcf_estimates)
        else:
            growth_rate = 0.08  # 默认8%

        # 获取股本和价格
        basic = DataService.get_stock_basic(code)
        if "error" in basic:
            raise HTTPException(404, f"未找到 {code} 的基本信息")

        current_price = basic.get("price", 0)
        market_cap = basic.get("market_cap")  # 亿元
        if not current_price or current_price <= 0:
            raise HTTPException(400, f"无法获取 {code} 的价格数据")
        # 从市值和价格推导股本（亿股）
        shares = market_cap / current_price if market_cap and market_cap > 0 else None
        if not shares or shares <= 0:
            raise HTTPException(400, f"无法获取 {code} 的股本数据")

        # 获取资产负债表数据（用于净负债和WACC估算）
        balance_list = cashflow_data.get("balance", [])
        debt_ratio = annual_reports[0].get("debt_ratio", 0) or 0

        # 净负债估算
        net_debt = 0.0
        if balance_list:
            bal = balance_list[0]
            short_debt = bal.get("short_term_borrowing") or 0
            long_debt = bal.get("long_term_borrowing") or 0
            cash = bal.get("monetary_funds") or 0
            net_debt = short_debt + long_debt - cash

        # WACC估算
        if req.discount_rate is not None:
            discount_rate = req.discount_rate
        else:
            # Beta默认1.0，保守估算
            discount_rate = estimate_wacc(
                risk_free_rate=0.025,
                market_risk_premium=0.06,
                beta=1.0,
                debt_ratio=debt_ratio,
            )

        # DCF计算
        dcf = DCFService(
            discount_rate=discount_rate,
            terminal_growth_rate=0.03,
            safety_margin=req.safety_margin,
        )

        result = dcf.calculate_intrinsic_value(
            current_fcf=current_fcf / 1e8,  # 转为亿元
            growth_rate=growth_rate,
            shares=shares,
            net_debt=net_debt / 1e8,
            current_price=current_price,
        )

        # 附加数据来源信息
        result['data_source'] = {
            'fcf_source': 'cashflow_statement' if fcf_estimates else 'estimated_from_profit',
            'fcf_raw': round(current_fcf / 1e8, 2) if current_fcf > 0 else None,
            'growth_rate_source': 'historical_cagr' if req.growth_rate is None else 'manual',
            'discount_rate_source': 'wacc_estimated' if req.discount_rate is None else 'manual',
            'debt_ratio': round(debt_ratio, 1),
            'report_period': annual_reports[0].get('report_period', ''),
            'report_type': annual_reports[0].get('report_type', ''),
        }

        # 敏感性分析
        class MockReq:
            pass
        mock = MockReq()
        mock.current_fcf = current_fcf / 1e8
        mock.growth_rate = growth_rate
        mock.shares = shares
        mock.discount_rate = discount_rate
        mock.terminal_growth_rate = 0.03
        mock.safety_margin = req.safety_margin
        mock.net_debt = net_debt / 1e8
        mock.current_price = current_price
        result['sensitivity'] = _build_sensitivity_matrix(mock)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"DCF自动估值失败: {str(e)}")


@router.post("/graham")
def graham_number_calculator(req: GrahamRequest):
    """
    格雷厄姆公式计算器

    公式: sqrt(22.5 * EPS * BVPS)
    含义: 15倍PE * 1.5倍PB = 22.5，这是格雷厄姆认为的合理估值上限
    """
    result = calculate_graham_number(eps=req.eps, bvps=req.bvps)

    if result["applicable"] and req.current_price > 0:
        graham_val = result["graham_value"]
        result["current_price"] = req.current_price
        result["upside_pct"] = round((graham_val / req.current_price - 1) * 100, 1)
        result["is_undervalued"] = req.current_price < graham_val
        result["safety_margin_pct"] = round((1 - req.current_price / graham_val) * 100, 1) if graham_val > 0 else 0

    return result


@router.get("/wacc-estimate")
def estimate_wacc_endpoint(
    debt_ratio: float = Query(0.0, description="资产负债率 (%)"),
    beta: float = Query(1.0, description="Beta系数"),
    risk_free_rate: float = Query(0.025, description="无风险利率"),
    market_risk_premium: float = Query(0.06, description="市场风险溢价"),
):
    """WACC估算（基于CAPM模型）"""
    wacc = estimate_wacc(
        risk_free_rate=risk_free_rate,
        market_risk_premium=market_risk_premium,
        beta=beta,
        debt_ratio=debt_ratio,
    )

    cost_of_equity = risk_free_rate + beta * market_risk_premium

    return {
        "wacc": round(wacc, 4),
        "wacc_pct": f"{wacc * 100:.1f}%",
        "cost_of_equity": round(cost_of_equity, 4),
        "cost_of_equity_pct": f"{cost_of_equity * 100:.1f}%",
        "risk_free_rate": risk_free_rate,
        "market_risk_premium": market_risk_premium,
        "beta": beta,
        "debt_ratio": debt_ratio,
        "suggested_discount_rates": {
            "conservative": f"{max(wacc + 0.02, 0.12) * 100:.0f}%",
            "base": f"{wacc * 100:.1f}%",
            "aggressive": f"{max(wacc - 0.02, 0.08) * 100:.0f}%",
        }
    }


# ============================================================
# 辅助函数
# ============================================================

def _build_sensitivity_matrix(req) -> dict:
    """构建DCF敏感性分析矩阵"""
    growth_rates = [0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    discount_rates = [0.08, 0.10, 0.12, 0.15]
    matrix = []

    for gr in growth_rates:
        row = []
        for dr in discount_rates:
            if dr <= req.terminal_growth_rate:
                row.append(None)
                continue
            try:
                s_dcf = DCFService(
                    discount_rate=dr,
                    terminal_growth_rate=req.terminal_growth_rate,
                    safety_margin=req.safety_margin,
                )
                s_result = s_dcf.calculate_intrinsic_value(
                    current_fcf=req.current_fcf,
                    growth_rate=gr,
                    shares=req.shares,
                    net_debt=getattr(req, 'net_debt', 0),
                )
                row.append(s_result['intrinsic_value'])
            except (ValueError, ZeroDivisionError):
                row.append(None)
        matrix.append(row)

    return {
        'growth_rates': [f"{g*100:.0f}%" for g in growth_rates],
        'discount_rates': [f"{d*100:.0f}%" for d in discount_rates],
        'matrix': matrix,
    }
