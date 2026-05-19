from typing import List

class DCFService:
    """DCF估值计算服务"""

    def __init__(
        self,
        discount_rate: float = 0.10,  # 折现率 10%
        terminal_growth_rate: float = 0.03,  # 永续增长率 3%
        safety_margin: float = 0.30,  # 安全边际 30%
        projection_years: int = 10  # 预测年数
    ):
        self.discount_rate = discount_rate
        self.terminal_growth_rate = terminal_growth_rate
        self.safety_margin = safety_margin
        self.projection_years = projection_years

    def calculate_intrinsic_value(
        self,
        current_fcf: float,  # 当前自由现金流 (亿)
        growth_rate: float,  # 前10年增长率
        shares: float  # 总股本 (亿股)
    ) -> dict:
        """
        计算DCF内在价值

        Returns:
            包含内在价值、买点、各年FCF预测等
        """
        # 1. 预测未来10年FCF
        fcf_projections = []
        for year in range(1, self.projection_years + 1):
            projected_fcf = current_fcf * (1 + growth_rate) ** year
            fcf_projections.append(round(projected_fcf, 2))

        # 2. 计算10年FCF现值
        pv_fcf = 0
        for t, fcf in enumerate(fcf_projections, 1):
            pv_fcf += fcf / (1 + self.discount_rate) ** t

        # 3. 计算终值
        terminal_fcf = fcf_projections[-1] * (1 + self.terminal_growth_rate)
        terminal_value = terminal_fcf / (self.discount_rate - self.terminal_growth_rate)

        # 4. 终值现值
        pv_terminal = terminal_value / (1 + self.discount_rate) ** self.projection_years

        # 5. 企业价值
        enterprise_value = pv_fcf + pv_terminal

        # 6. 每股内在价值
        intrinsic_per_share = enterprise_value / shares

        # 7. 买点（含安全边际）
        buy_price = intrinsic_per_share * (1 - self.safety_margin)

        return {
            "intrinsic_value": round(intrinsic_per_share, 2),
            "buy_price": round(buy_price, 2),
            "enterprise_value": round(enterprise_value, 2),
            "fcf_projections": fcf_projections,
            "terminal_value": round(terminal_value, 2),
            "pv_fcf": round(pv_fcf, 2),
            "pv_terminal": round(pv_terminal, 2),
            "discount_rate": self.discount_rate,
            "growth_rate": growth_rate,
            "terminal_growth_rate": self.terminal_growth_rate,
            "safety_margin": self.safety_margin
        }

    def estimate_growth_rate(
        self,
        historical_fcf: List[float]  # 近5年FCF
    ) -> float:
        """估算FCF增长率（基于历史数据）"""
        if len(historical_fcf) < 2:
            return 0.05  # 默认5%

        # 计算年均复合增长率
        start = historical_fcf[0]
        end = historical_fcf[-1]
        years = len(historical_fcf) - 1

        if start <= 0:
            return 0.05

        cagr = (end / start) ** (1 / years) - 1

        # 保守处理：取历史增长率的80%
        return max(cagr * 0.8, 0.02)  # 最低2%
