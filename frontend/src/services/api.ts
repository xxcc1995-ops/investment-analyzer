import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export interface StockBasicInfo {
  code: string;
  name: string;
  pe: number | null;
  pb: number | null;
  roe: number | null;
  market_cap: number | null;
}

export interface StockFinancials {
  code: string;
  name: string;
  revenue: number | null;
  net_profit: number | null;
  revenue_growth: number | null;
  profit_growth: number | null;
  fcf: number | null;
}

export interface DCFValuation {
  code: string;
  name: string;
  current_price: number;
  intrinsic_value: number;
  buy_price: number;
  safety_margin: number;
  upside: number;
  fcf_projections: number[];
  terminal_value: number;
  discount_rate: number;
  growth_rate: number;
  terminal_growth_rate: number;
}

export const stockApi = {
  getBasicInfo: (code: string) =>
    api.get<StockBasicInfo>(`/stocks/${code}/basic`),

  getFinancials: (code: string) =>
    api.get<StockFinancials>(`/stocks/${code}/financials`),
};

export const valuationApi = {
  calculateDCF: (code: string, growthRate?: number, safetyMargin = 0.3) =>
    api.post<DCFValuation>('/valuation/dcf', {
      stock_code: code,
      growth_rate: growthRate,
      safety_margin: safetyMargin,
    }),
};
