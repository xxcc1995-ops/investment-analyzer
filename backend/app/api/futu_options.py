"""富途期权链 API - 真实市场数据 + BSM分析"""

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
    """获取真实期权链数据 + BSM Greeks + 评分"""
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
    """BSM期权计算器"""
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
    """轮动建议：hold/roll/close（改进版：支持传入真实IV）"""
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
