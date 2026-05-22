"""价值投资筛选 - 巴菲特、芒格、李录、段永平投资体系"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.vi_service import screen_stocks
from app.services.dcf import DCFService

router = APIRouter()


class DCFRequest(BaseModel):
    current_fcf: float
    growth_rate: float
    shares: float
    discount_rate: float = 0.10
    terminal_growth_rate: float = 0.03
    safety_margin: float = 0.30


@router.get("/philosophy")
async def get_philosophy():
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


@router.get("/screener")
async def value_investing_screener(
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


@router.post("/dcf")
async def dcf_calculator(req: DCFRequest):
    """DCF自由现金流折现计算器"""
    if req.current_fcf <= 0 or req.shares <= 0:
        raise HTTPException(400, "FCF和股本必须大于0")

    dcf = DCFService(
        discount_rate=req.discount_rate,
        terminal_growth_rate=req.terminal_growth_rate,
        safety_margin=req.safety_margin,
    )

    result = dcf.calculate_intrinsic_value(
        current_fcf=req.current_fcf,
        growth_rate=req.growth_rate,
        shares=req.shares,
    )

    # Sensitivity analysis
    growth_rates = [0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
    discount_rates = [0.08, 0.10, 0.12, 0.15]
    matrix = []

    for gr in growth_rates:
        row = []
        for dr in discount_rates:
            s_dcf = DCFService(
                discount_rate=dr,
                terminal_growth_rate=req.terminal_growth_rate,
                safety_margin=req.safety_margin,
            )
            s_result = s_dcf.calculate_intrinsic_value(
                current_fcf=req.current_fcf,
                growth_rate=gr,
                shares=req.shares,
            )
            row.append(s_result['intrinsic_value'])
        matrix.append(row)

    result['sensitivity'] = {
        'growth_rates': [f"{g*100:.0f}%" for g in growth_rates],
        'discount_rates': [f"{d*100:.0f}%" for d in discount_rates],
        'matrix': matrix,
    }

    return result
