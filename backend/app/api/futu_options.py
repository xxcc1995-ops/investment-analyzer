"""富途期权链 API - 真实市场数据 + BSM分析

============================== API使用指南 ==============================

【第一步】确保OpenD已启动
- 下载：https://www.futunn.com/download/OpenAPI
- 用富途账号登录，确保显示"已连接"

【第二步】查看期权链
- GET /chain?stock_code=HK.00700 → 获取腾讯所有期权合约
- 返回的数据已包含Greeks、评分、流动性分析

【第三步】分析策略
- GET /strategy/covered_call → 备兑看涨策略（持股收租）
- GET /strategy/cash_secured_put → 现金担保看跌（等抄底）
- GET /strategy/credit_spread → 价差策略（有限风险）
- GET /strategy/straddle → 跨式策略（赌大行情）
- GET /strategy/iron_condor → 铁鹰式（赌横盘）

【第四步】查看盈亏图
- GET /strategy/pnl?strategy=covered_call → 生成P&L图数据

【辅助功能】
- GET /connection → 检查OpenD连接状态
- GET /hv → 历史波动率
- GET /greeks → BSM计算器（手动算Greeks）
- GET /rolling → 轮动建议（平仓/展期/持有）
- GET /max_pain → 最大痛苦点
- GET /theta_decay → 时间衰减曲线
- GET /iv_surface → 波动率曲面
- GET /screen → 策略筛选器
- GET /philosophy → 交易理念
- GET /help → 使用帮助
"""

from fastapi import APIRouter, Query
import subprocess
import json
import sys
import os

router = APIRouter()

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_futu_script(script_content: str, timeout: int = 120) -> dict:
    """Execute a Futu script via subprocess and return result."""
    script_path = os.path.join(BACKEND_DIR, '_futu_temp.py')
    result_path = os.path.join(BACKEND_DIR, '_futu_result.json')

    try:
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        venv_python = os.path.join(BACKEND_DIR, 'venv', 'Scripts', 'python.exe')
        if not os.path.exists(venv_python):
            venv_python = sys.executable

        proc = subprocess.run(
            [venv_python, script_path],
            capture_output=True, text=True, timeout=timeout, cwd=BACKEND_DIR
        )

        try:
            os.remove(script_path)
        except:
            pass

        if proc.returncode == 0 and os.path.exists(result_path):
            with open(result_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            try:
                os.remove(result_path)
            except:
                pass
            return data
        else:
            error = proc.stderr[:300] if proc.stderr else 'unknown error'
            try:
                os.remove(result_path)
            except:
                pass
            return {'error': f'Failed: {error}', 'chain': [], 'update_time': ''}
    except Exception as e:
        return {'error': f'API error: {str(e)}', 'chain': [], 'update_time': ''}


@router.get("/chain")
def option_chain(
    stock_code: str = Query('HK.00700', description="港股代码, 如HK.00700"),
    option_type: str = Query('all', description="期权类型: put/call/all"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    """
    获取完整期权链数据 - 这是最核心的接口

    【返回数据包含什么？】
    每个期权合约都有：
    - 基础信息：行权价、到期日、剩余天数
    - 实时报价：买价、卖价、最新价、成交量、未平仓量
    - Greeks指标：Delta/Gamma/Theta/Vega（衡量风险）
    - 评分（0-100）：综合7个维度的推荐分数
    - 流动性分析：买卖价差、是否适合交易
    - 盈利指标：年化收益率、盈利概率、OTM缓冲

    【怎么用？】
    1. 先看 best_put 和 best_call（系统推荐的最佳合约）
    2. 再看 chain 列表，按 score 排序找高分合约
    3. 关注 can_trade=true 的合约（流动性好）
    """
    try:
        from app.services.futu_option_service import get_option_chain_from_futu
        return get_option_chain_from_futu(stock_code, option_type, risk_free_rate)
    except ImportError:
        return {'error': 'futu-api 未安装，请运行: pip install futu-api', 'chain': [], 'update_time': ''}
    except Exception as e:
        return {'error': str(e), 'chain': [], 'update_time': ''}


@router.get("/connection")
def connection_status():
    """检查 Futu OpenD 连接状态"""
    try:
        from app.services.futu_option_service import check_connection
        return check_connection()
    except ImportError:
        return {'connected': False, 'error': 'futu-api 未安装', 'solution': '运行: pip install futu-api'}


@router.get("/quote")
def option_quote(
    code: str = Query(..., description="期权代码, 如HK.TCH260618C460000"),
):
    """获取单个期权合约报价"""
    try:
        from app.services.futu_option_service import get_option_quote
        return get_option_quote(code)
    except Exception as e:
        return {'error': str(e)}


@router.get("/hv")
def historical_volatility(
    stock_code: str = Query('HK.00700', description="港股代码"),
):
    """获取历史波动率"""
    from app.services.futu_option_service import _fetch_hk_historical, calculate_hv
    prices = _fetch_hk_historical(stock_code, 60)
    hv = calculate_hv(prices, 20) if prices else 0.3
    return {'stock_code': stock_code, 'hv': round(hv * 100, 1), 'prices_count': len(prices)}


@router.get("/greeks")
def greeks(
    spot: float = Query(..., description="标的价格"),
    strike: float = Query(..., description="行权价"),
    days: int = Query(30, description="到期天数"),
    sigma: float = Query(0.3, description="波动率"),
    option_type: str = Query('put', description="期权类型"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    """
    BSM期权计算器 - 手动计算期权理论价格和Greeks

    【什么时候用？】
    当你想自己算一下"这个期权理论上值多少钱"时。
    输入5个参数，系统告诉你理论价格+所有风险指标。

    【参数说明】
    - spot: 股票现价（比如300）
    - strike: 行权价（比如320）
    - days: 还剩多少天到期（比如30）
    - sigma: 波动率（一般0.2-0.5，可以用/hv接口查历史波动率）
    - option_type: 'put'(看跌) 或 'call'(看涨)
    """
    from app.services.futu_option_service import bsm_price
    T = days / 365
    result = bsm_price(spot, strike, T, risk_free_rate, sigma, option_type)
    return {
        'spot': spot, 'strike': strike, 'days': days,
        'sigma': sigma, 'option_type': option_type, 'greeks': result,
    }


@router.get("/rolling")
def rolling(
    spot: float = Query(..., description="当前标的价格"),
    strike: float = Query(..., description="当前持仓行权价"),
    premium: float = Query(..., description="开仓权利金"),
    dte_left: int = Query(..., description="剩余到期天数"),
    entry_dte: int = Query(30, description="开仓时到期天数"),
    option_type: str = Query('put', description="期权类型"),
    hv: float = Query(0.3, description="历史波动率"),
    current_iv: float = Query(None, description="当前真实IV（小数）"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    """
    轮动建议 - 告诉你当前持仓该怎么做

    【什么时候用？】
    你已经卖了一个期权，现在想知道：
    - 该不该平仓？（赚够了或风险太大）
    - 该不该展期？（快到期了想继续做）
    - 还是继续持有？（状态良好）

    【参数说明】
    - spot: 股票现在的价格
    - strike: 你卖的期权的行权价
    - premium: 你当初收了多少权利金
    - dte_left: 还剩多少天到期
    - option_type: 你卖的是put还是call

    【返回值】
    - action: 'close'(平仓) / 'roll'(展期) / 'hold'(持有)
    - reason: 为什么建议这么做
    - profit_pct: 当前赚了百分之多少
    """
    from app.services.futu_option_service import get_rolling_recommendation
    return get_rolling_recommendation(
        spot, strike, premium, dte_left, entry_dte,
        option_type, hv, current_iv=current_iv, risk_free_rate=risk_free_rate,
    )


@router.get("/strategy/covered_call")
def strategy_covered_call(
    stock_code: str = Query('HK.00700', description="港股代码"),
):
    """Covered Call 策略分析：持有正股 + 卖 Call"""
    from app.services.futu_option_service import get_option_chain_from_futu, analyze_covered_call
    chain_data = get_option_chain_from_futu(stock_code, 'call')
    if 'error' in chain_data:
        return chain_data
    calls = [c for c in chain_data.get('chain', []) if c.get('last', 0) > 0]
    return analyze_covered_call(chain_data['spot_price'], calls)


@router.get("/strategy/cash_secured_put")
def strategy_cash_secured_put(
    stock_code: str = Query('HK.00700', description="港股代码"),
    cash_available: float = Query(None, description="可用资金"),
):
    """Cash Secured Put 策略分析：卖 Put + 准备现金"""
    from app.services.futu_option_service import get_option_chain_from_futu, analyze_cash_secured_put
    chain_data = get_option_chain_from_futu(stock_code, 'put')
    if 'error' in chain_data:
        return chain_data
    puts = [c for c in chain_data.get('chain', []) if c.get('last', 0) > 0]
    return analyze_cash_secured_put(chain_data['spot_price'], puts, cash_available)


@router.get("/strategy/credit_spread")
def strategy_credit_spread(
    stock_code: str = Query('HK.00700', description="港股代码"),
    spread_type: str = Query('put', description="价差类型: put/call"),
):
    """Credit Spread 策略分析：卖近价 + 买远价（限制风险）"""
    from app.services.futu_option_service import get_option_chain_from_futu, analyze_credit_spread
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data
    return analyze_credit_spread(chain_data['spot_price'], chain_data.get('chain', []), spread_type)


@router.get("/theta_decay")
def theta_decay(
    spot: float = Query(..., description="标的价格"),
    strike: float = Query(..., description="行权价"),
    premium: float = Query(..., description="开仓权利金"),
    dte: int = Query(30, description="到期天数"),
    option_type: str = Query('put', description="期权类型"),
    iv: float = Query(0.3, description="隐含波动率"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    """Theta 衰减曲线数据"""
    from app.services.futu_option_service import calculate_theta_decay
    return calculate_theta_decay(spot, strike, premium, dte, option_type, iv, risk_free_rate)


@router.get("/iv_surface")
def iv_surface(
    stock_code: str = Query('HK.00700', description="港股代码"),
):
    """IV 曲面数据 (strike x expiry 热力图 + ATM期限结构 + 偏斜)"""
    from app.services.futu_option_service import get_option_chain_from_futu, build_iv_surface
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data
    return build_iv_surface(chain_data.get('chain', []))


@router.get("/max_pain")
def max_pain(
    stock_code: str = Query('HK.00700', description="港股代码"),
):
    """Max Pain 计算: 期权到期时标的最痛苦价格点"""
    from app.services.futu_option_service import get_option_chain_from_futu, calculate_max_pain
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data
    return calculate_max_pain(chain_data.get('chain', []), chain_data.get('spot_price', 0))


@router.get("/screen")
def screen_strategies(
    stock_code: str = Query('HK.00700', description="港股代码"),
    trade_fee: float = Query(16, description="每笔交易手续费(港币)"),
    exercise_fee: float = Query(100, description="行权手续费(港币)"),
    min_yield: float = Query(15, description="最低年化收益率(%)"),
    min_otm: float = Query(3, description="最低OTM距离(%)"),
    min_volume: int = Query(0, description="最低成交量"),
    risk_free_rate: float = Query(0.04, description="无风险利率"),
):
    """
    策略筛选器 - 自动扫描所有期权，找出最赚钱的机会

    【通俗理解】
    这个接口帮你做"选股"工作：
    1. 扫描腾讯的所有期权合约
    2. 扣除手续费后计算真实年化收益
    3. 只保留年化收益 > min_yield 的合约
    4. 按收益从高到低排序

    【参数说明】
    - trade_fee: 每笔交易手续费（富途一般15-20港币）
    - exercise_fee: 行权手续费（富途一般100港币）
    - min_yield: 最低年化收益率（比如15%表示只看年化>15%的）
    - min_otm: 最低OTM距离（比如3%表示行权价至少离现价3%）

    【怎么用？】
    1. 先用默认参数扫描
    2. 看返回的 results 列表
    3. 关注 net_yield（扣费后年化）和 score（综合评分）
    4. 选一个你满意的合约交易
    """
    from app.services.futu_option_service import get_option_chain_from_futu

    chain_data = get_option_chain_from_futu(stock_code, 'all', risk_free_rate)
    if 'error' in chain_data:
        return chain_data

    spot = chain_data['spot_price']
    chain = chain_data.get('chain', [])
    results = []

    for c in chain:
        if c.get('last', 0) <= 0 and c.get('mid', 0) <= 0:
            continue
        if min_volume > 0 and c.get('volume', 0) < min_volume:
            continue

        strike = c['strike']
        dte = c.get('dte', 0)
        if dte <= 0:
            continue
        lot_size = c.get('contract_size', 100)
        premium = c.get('mid', 0) or c.get('last', 0)
        if premium <= 0:
            continue

        otm_pct = c.get('otm_pct', 0)
        annual_factor = 365 / dte

        if c['option_type'] == 'call':
            # Covered Call: 持有正股 + 卖Call
            # 被行权时: 收益 = (行权价 - 现价 + 权利金) * lot_size - 交易费 - 行权费
            # 不被行权: 收益 = 权利金 * lot_size - 交易费
            investment = spot * lot_size
            gross_profit = (strike - spot + premium) * lot_size
            net_profit_exercised = gross_profit - trade_fee - exercise_fee
            net_profit_not_exercised = premium * lot_size - trade_fee

            net_yield_exercised = (net_profit_exercised / investment) * annual_factor * 100
            net_yield_best = (net_profit_not_exercised / investment) * annual_factor * 100
            gross_yield = (gross_profit / investment) * annual_factor * 100

            if otm_pct < min_otm:
                continue

            # 检查是否达标（取被行权时的收益，更保守）
            if net_yield_exercised < min_yield:
                continue

            results.append({
                'strategy': 'cc',
                'strategy_name': 'Covered Call',
                'code': c.get('code', ''),
                'spot': round(spot, 2),
                'strike': strike,
                'premium': round(premium, 4),
                'dte': dte,
                'lot_size': lot_size,
                'otm_pct': round(otm_pct, 1),
                'iv': c.get('iv', 0),
                'delta': round(c.get('delta', 0), 4),
                'pop': c.get('pop', 0),
                'volume': c.get('volume', 0),
                'open_interest': c.get('open_interest', 0),
                'bid': c.get('bid', 0),
                'ask': c.get('ask', 0),
                'spread_pct': c.get('spread_pct', 0),
                'gross_yield': round(gross_yield, 2),
                'net_yield': round(net_yield_exercised, 2),
                'net_yield_best': round(net_yield_best, 2),
                'net_profit': round(net_profit_exercised, 2),
                'premium_income': round(premium * lot_size, 2),
                'investment': round(investment, 2),
                'breakeven': round(spot - premium + (trade_fee + exercise_fee) / lot_size, 2),
                'max_profit': round(net_profit_exercised, 2),
                'score': c.get('score', 0),
            })

        elif c['option_type'] == 'put':
            # Cash Secured Put: 卖Put + 准备现金
            # 不被行权: 收益 = 权利金 * lot_size - 交易费
            # 被行权: 收益 = 权利金 * lot_size - 交易费 - 行权费
            collateral = (strike - premium) * lot_size
            if collateral <= 0:
                continue

            net_profit_best = premium * lot_size - trade_fee
            net_profit_worst = premium * lot_size - trade_fee - exercise_fee

            net_yield_best = (net_profit_best / collateral) * annual_factor * 100
            net_yield_worst = (net_profit_worst / collateral) * annual_factor * 100
            gross_yield = (premium * lot_size / collateral) * annual_factor * 100

            if otm_pct < min_otm:
                continue

            # 检查是否达标（取最坏情况，被行权时）
            if net_yield_worst < min_yield:
                continue

            results.append({
                'strategy': 'csp',
                'strategy_name': 'Cash Secured Put',
                'code': c.get('code', ''),
                'spot': round(spot, 2),
                'strike': strike,
                'premium': round(premium, 4),
                'dte': dte,
                'lot_size': lot_size,
                'otm_pct': round(otm_pct, 1),
                'iv': c.get('iv', 0),
                'delta': round(c.get('delta', 0), 4),
                'pop': c.get('pop', 0),
                'volume': c.get('volume', 0),
                'open_interest': c.get('open_interest', 0),
                'bid': c.get('bid', 0),
                'ask': c.get('ask', 0),
                'spread_pct': c.get('spread_pct', 0),
                'gross_yield': round(gross_yield, 2),
                'net_yield': round(net_yield_worst, 2),
                'net_yield_best': round(net_yield_best, 2),
                'net_profit': round(net_profit_worst, 2),
                'premium_income': round(premium * lot_size, 2),
                'collateral': round(collateral, 2),
                'breakeven': round(strike - premium + trade_fee / lot_size, 2),
                'max_profit': round(net_profit_best, 2),
                'score': c.get('score', 0),
            })

    # 按扣费后年化降序排列
    results.sort(key=lambda x: x['net_yield'], reverse=True)

    return {
        'stock_code': stock_code,
        'spot_price': spot,
        'stock_name': chain_data.get('stock_name', ''),
        'hv': chain_data.get('hv', 0),
        'trade_fee': trade_fee,
        'exercise_fee': exercise_fee,
        'min_yield': min_yield,
        'total_scanned': len(chain),
        'passed_count': len(results),
        'results': results,
        'update_time': chain_data.get('update_time', ''),
    }


@router.get("/strategy/straddle")
def strategy_straddle(
    stock_code: str = Query('HK.00700', description="港股代码"),
    direction: str = Query('long', description="方向: long(买入)/short(卖出)"),
):
    """Straddle (跨式) 策略分析: 同时买入/卖出相同行权价的 Call + Put"""
    from app.services.futu_option_service import get_option_chain_from_futu, analyze_straddle
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data
    return analyze_straddle(chain_data['spot_price'], chain_data.get('chain', []), direction)


@router.get("/strategy/strangle")
def strategy_strangle(
    stock_code: str = Query('HK.00700', description="港股代码"),
    direction: str = Query('long', description="方向: long(买入)/short(卖出)"),
):
    """Strangle (宽跨式) 策略分析: 买入/卖出不同行权价的 OTM Call + OTM Put"""
    from app.services.futu_option_service import get_option_chain_from_futu, analyze_strangle
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data
    return analyze_strangle(chain_data['spot_price'], chain_data.get('chain', []), direction)


@router.get("/strategy/iron_condor")
def strategy_iron_condor(
    stock_code: str = Query('HK.00700', description="港股代码"),
):
    """Iron Condor (铁鹰式) 策略分析: 卖出OTM Put/Call + 买入更远OTM保护"""
    from app.services.futu_option_service import get_option_chain_from_futu, analyze_iron_condor
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data
    return analyze_iron_condor(chain_data['spot_price'], chain_data.get('chain', []))


@router.get("/strategy/pnl")
def strategy_pnl(
    stock_code: str = Query('HK.00700', description="港股代码"),
    strategy: str = Query('covered_call', description="策略: covered_call/csp/credit_spread/straddle/strangle/iron_condor"),
    spread_type: str = Query('put', description="价差类型(仅credit_spread): put/call"),
    direction: str = Query('long', description="方向(仅straddle/strangle): long/short"),
):
    """策略 P&L 盈亏图数据"""
    from app.services.futu_option_service import (
        get_option_chain_from_futu, analyze_covered_call, analyze_cash_secured_put,
        analyze_credit_spread, analyze_straddle, analyze_strangle, analyze_iron_condor,
        generate_pnl_diagram,
    )
    chain_data = get_option_chain_from_futu(stock_code, 'all')
    if 'error' in chain_data:
        return chain_data

    spot = chain_data['spot_price']
    chain = chain_data.get('chain', [])
    active = [c for c in chain if c.get('last', 0) > 0]

    if strategy == 'covered_call':
        calls = [c for c in active if c['option_type'] == 'call']
        result = analyze_covered_call(spot, calls)
    elif strategy == 'csp':
        puts = [c for c in active if c['option_type'] == 'put']
        result = analyze_cash_secured_put(spot, puts)
    elif strategy == 'credit_spread':
        result = analyze_credit_spread(spot, chain, spread_type)
    elif strategy == 'straddle':
        result = analyze_straddle(spot, chain, direction)
    elif strategy == 'strangle':
        result = analyze_strangle(spot, chain, direction)
    elif strategy == 'iron_condor':
        result = analyze_iron_condor(spot, chain)
    else:
        return {'error': f'未知策略: {strategy}'}

    if 'error' in result:
        return result

    pnl_data = generate_pnl_diagram(result, spot)
    return {'strategy_info': result, 'pnl': pnl_data}


@router.get("/philosophy")
def philosophy():
    """期权交易理念（改进版：7维度评分 + 组合策略）"""
    return {
        'title': '卖期权轮动策略（实战版）',
        'subtitle': '基于Futu OpenD真实数据，系统化卖出期权，收取时间价值',
        'concepts': [
            {'name': '卖Put（卖出看跌期权）', 'desc': '收取权利金，承诺在特定价格买入标的。相当于"被付费等待抄底"。', 'suitable': '看好标的但想以更低价格买入时'},
            {'name': '卖Call（卖出看涨期权）', 'desc': '收取权利金，承诺在特定价格卖出标的。相当于"出租持仓收取租金"。', 'suitable': '持有标的但认为短期不会大涨时'},
            {'name': 'Covered Call（备兑看涨）', 'desc': '持有正股 + 卖出虚值 Call，收取权利金增强收益。', 'suitable': '长期持有标的，想增强现金流'},
            {'name': 'Cash Secured Put（现金担保看跌）', 'desc': '卖出虚值 Put，准备资金以行权价买入标的。', 'suitable': '想在更低价格买入标的'},
            {'name': 'Credit Spread（价差策略）', 'desc': '卖近价 + 买远价，限制最大亏损。', 'suitable': '想卖期权但控制风险'},
        ],
        'scoring': {
            'title': '期权评分维度（满分100，7维度）',
            'dimensions': [
                {'name': 'IV/HV溢价', 'weight': 15, 'desc': '隐含波动率高于历史波动率越多，权利金越贵'},
                {'name': 'IV Percentile', 'weight': 15, 'desc': 'IV在历史中的位置，高位卖期权更佳'},
                {'name': '年化收益率', 'weight': 20, 'desc': '权利金/保证金 × 365/到期天数'},
                {'name': 'OTM缓冲', 'weight': 15, 'desc': '行权价距现价越远越安全'},
                {'name': 'Theta效率', 'weight': 15, 'desc': '每日时间衰减占权利金比例'},
                {'name': '盈利概率', 'weight': 10, 'desc': '基于Delta估算的到期盈利概率'},
                {'name': '流动性', 'weight': 10, 'desc': '基于Bid-Ask Spread评估交易成本'},
            ],
        },
        'indicators': {
            'iv_percentile': 'IV在历史中的百分位，>80%表示IV高位，适合卖期权',
            'bid_ask_spread': '买卖价差，越窄流动性越好，交易成本越低',
            'theta_decay': 'Theta随时间衰减的曲线，帮助确定最佳展期时机',
        },
        'risks': [
            '卖出看跌期权：标的大跌时需以行权价买入，可能大幅亏损',
            '卖出看涨期权：标的大涨时错失上涨收益（裸卖Call风险无限）',
            '波动率骤升：IV上升导致期权价格上升，浮亏增加',
            '提前行权风险：美式期权可能被提前行权',
            '流动性风险：深度OTM期权可能流动性不足',
            '价差风险：Bid-Ask Spread过大时交易成本高',
        ],
        'rules': [
            '单笔仓位不超过总资金的5%',
            '优先选择30-45天到期的合约（Theta衰减最快区间）',
            'OTM缓冲至少5%，优选10%以上',
            '临近到期7天内考虑展期（Roll）',
            'IV Percentile > 60% 时是卖期权的好时机',
            'Bid-Ask Spread < 10% 时才适合交易',
            '优先选择流动性好的合约（成交量 > 100）',
        ],
    }


@router.get("/help")
def help_info():
    """使用帮助"""
    return {
        'title': '富途期权链使用指南',
        'steps': [
            {'step': 1, 'title': '下载 Futu OpenD', 'url': 'https://www.futunn.com/download/OpenAPI', 'desc': '访问富途官网下载 OpenD'},
            {'step': 2, 'title': '启动并登录 OpenD', 'desc': '运行 OpenD，使用富途账户登录'},
            {'step': 3, 'title': '确保 OpenD 运行中', 'desc': 'OpenD 默认监听 127.0.0.1:11111'},
            {'step': 4, 'title': '访问期权链页面', 'desc': '点击"检查连接"确认状态'},
        ],
    }
