import api from './client'

// ============ 拖拉机套利API (V2) ============

export const tractorApi = {
  // ---- 系统状态 ----
  /** 获取系统状态 */
  getStatus: () =>
    api.get<Record<string, unknown>>('/tractor/status'),

  // ---- 账户管理 ----
  /** 获取账户列表 */
  getAccounts: () =>
    api.get<Record<string, unknown>>('/tractor/accounts'),

  /** 获取账户资金信息 */
  getAccountBalances: () =>
    api.get<Record<string, unknown>>('/tractor/accounts/balances'),

  /** 添加账户 */
  addAccount: (params: { account_id: string; password: string; broker_type?: string; name?: string }) =>
    api.post<Record<string, unknown>>('/tractor/accounts', params),

  /** 更新账户 */
  updateAccount: (accountId: string, params: Record<string, unknown>) =>
    api.put<Record<string, unknown>>(`/tractor/accounts/${accountId}`, params),

  /** 删除账户 */
  deleteAccount: (accountId: string) =>
    api.delete<Record<string, unknown>>(`/tractor/accounts/${accountId}`),

  /** 同步配置到AutoIt */
  syncConfig: () =>
    api.post<Record<string, unknown>>('/tractor/sync'),

  // ---- 操作执行 ----
  /** 执行操作（带风控） */
  runOperation: (params: {
    operation: string; fund_code?: string; sell_price?: string; sell_quantity?: string;
    account_ids?: string[]; premium_pct?: number; fund_name?: string;
    apply_status?: string; turnover?: number; est_nav?: number; fund_price?: number;
  }) =>
    api.post<Record<string, unknown>>('/tractor/run', params),

  /** 获取操作状态 */
  getOperationStatus: () =>
    api.get<Record<string, unknown>>('/tractor/operation-status'),

  /** 获取操作日志 */
  getLog: (tail?: number) =>
    api.get<Record<string, unknown>>('/tractor/log', { params: { tail } }),

  // ---- 策略引擎 ----
  /** 获取策略总览（扫描+分配+风控一体化） */
  getStrategyOverview: (params?: { min_premium?: number; min_amount?: number; direction?: string }) =>
    api.get<Record<string, unknown>>('/tractor/strategy/overview', { params }),

  /** 扫描套利机会 */
  scanOpportunities: (params?: { min_premium?: number; min_amount?: number; direction?: string }) =>
    api.get<Record<string, unknown>>('/tractor/strategy/scan', { params }),

  /** 计算资金分配方案 */
  calculateAllocation: (params: {
    fund_code: string; fund_name?: string; direction?: string; premium_pct?: number;
    apply_limit?: string; apply_status?: string; est_nav?: number; fund_price?: number;
    account_ids?: string[];
  }) =>
    api.post<Record<string, unknown>>('/tractor/strategy/allocation', params),

  // ---- 风险控制 ----
  /** 获取风控设置 */
  getRiskSettings: () =>
    api.get<Record<string, unknown>>('/tractor/risk/settings'),

  /** 更新风控设置 */
  updateRiskSettings: (params: Record<string, unknown>) =>
    api.put<Record<string, unknown>>('/tractor/risk/settings', params),

  /** 风控预检 */
  checkRisk: (params: {
    operation: string; fund_code?: string; premium_pct?: number;
    amount?: number; apply_status?: string; turnover?: number; account_ids?: string[];
  }) =>
    api.post<Record<string, unknown>>('/tractor/risk/check', params),

  // ---- 操作历史与损益 ----
  /** 获取操作历史 */
  getHistory: (params?: { limit?: number; fund_code?: string; operation?: string }) =>
    api.get<Record<string, unknown>>('/tractor/history', { params }),

  /** 获取损益汇总 */
  getPnLSummary: (days?: number) =>
    api.get<Record<string, unknown>>('/tractor/history/pnl', { params: { days } }),

  /** 回填操作损益 */
  updatePnL: (operationId: string, params: { realized_pnl: number; exit_price?: number }) =>
    api.post<Record<string, unknown>>(`/tractor/history/${operationId}/pnl`, params),
}
